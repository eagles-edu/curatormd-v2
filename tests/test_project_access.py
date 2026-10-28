"""Durable project registration and grant tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
import json
import sqlite3
import unittest
from pathlib import Path

from store_test_support import patch_store_symbol

from project_access_test_support import (
    ProjectAccessTestCase,
)

from curatormd_v2 import (
    AuthenticatedCaller,
    ArtifactRef,
    ConflictError,
    NotFoundError,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    SQLiteProjectGrantAuthorizer,
)

class _ExpiredObservationDatetime(datetime):
    """Advance the store clock beyond a reviewed staging snapshot's TTL."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return super().now(tz) + timedelta(seconds=61)

class DurableProjectAccessTests(ProjectAccessTestCase):
    """Durable project registration and grant tests."""

    def _assert_physical_class_names_cover_schema_tables(
        self, physical_class_names: set[str]
    ) -> None:
        with self.store.transaction() as connection:
            table_names = {
                str(row["name"])
                for row in connection.execute(
                    """SELECT name FROM sqlite_master
                       WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"""
                ).fetchall()
            }
        self.assertSetEqual(physical_class_names, table_names)

    def test_reactivation_review_is_bound_to_current_backlog_and_receipt(self) -> None:
        """A new old-source event invalidates the reviewed reactivation packet."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        suspended = self._change_status(
            "suspended", "Pause for reviewed reactivation", 1, "suspend-review-1"
        )
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        inventory = self._empty_staging_inventory()
        packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        self.assertTrue(packet.complete)
        self.assertEqual(
            packet.suspension_transition_id, suspended.receipt.transition_id
        )
        self.assertIsNotNone(packet.packet_sha256)

        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at, source_id, source_sequence)
                   VALUES (?, 'arrived-after-review', 'test.event', ?, 0,
                           'received', ?, 'old-source', 8)""",
                (
                    self.project_id,
                    "1" * 64,
                    datetime.now(UTC).isoformat(),
                ),
            )

        stale_request = ProjectStatusChangeRequest(
            project_id=self.project_id,
            status="active",
            rationale="Reject a stale reactivation review",
            expected_revision=2,
            transition_id="reactivate-stale-review-1",
            review_packet_sha256=packet.packet_sha256,
            suspension_transition_id=packet.suspension_transition_id,
            staging_inventory_sha256=inventory.manifest_sha256,
            staging_inventory_count=inventory.usage.regular_file_count,
            staging_inventory_bytes=inventory.usage.observed_file_bytes,
            staging_inventory_observed_at=inventory.usage.observed_at,
        )
        with self.assertRaisesRegex(ConflictError, "review packet is incomplete or stale"):
            self.manager.set_project_status(self.operator, stale_request)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status,
            "suspended",
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended.receipt
        )
        self._assert_reactivation_review_rejects_changed_purge_inventory()

        cursor_packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        self.assertTrue(cursor_packet.complete)
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO event_cursors VALUES (?, ?, ?, ?)",
                (
                    self.project_id,
                    "source-after-review",
                    1,
                    datetime.now(UTC).isoformat(),
                ),
            )
        stale_cursor_request = replace(
            stale_request,
            rationale="Reject a cursor change after review",
            transition_id="reactivate-stale-cursor-review-1",
            review_packet_sha256=cursor_packet.packet_sha256,
            staging_inventory_sha256=inventory.manifest_sha256,
        )
        with self.assertRaisesRegex(ConflictError, "review packet is incomplete or stale"):
            self.manager.set_project_status(self.operator, stale_cursor_request)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status,
            "suspended",
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended.receipt
        )

        current = self._change_status(
            "active",
            "Reactivate after the fresh review",
            2,
            "reactivate-fresh-review-1",
        )
        self.assertEqual(current.registration.status, "active")
        self.assertTrue(current.receipt.review_packet_sha256)
        self.assertEqual(
            current.receipt.suspension_transition_id,
            suspended.receipt.transition_id,
        )
        review_receipt = json.loads(current.receipt.review_packet_json or "{}")
        self.assertEqual(
            review_receipt["packet_sha256"], current.receipt.review_packet_sha256
        )
        self.assertEqual(review_receipt["unresolved_event_count"], 1)
        self._assert_reactivation_review_invalidated_by_grant_revocation()

    def _assert_reactivation_review_rejects_changed_purge_inventory(self) -> None:
        """Reject reactivation when an approved purge target changed after review."""

        artifact = ArtifactRef(
            "/staging/project-a/transient.json",
            hashlib.sha256(b"artifact").hexdigest(),
        )
        manifest = hashlib.sha256(
            json.dumps(
                [(artifact.path, artifact.sha256, artifact.occurrence_id)],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt = self.store.create_expiry_purge_receipt(
            self.project_id, "reviewer-1", manifest, (artifact,)
        )
        registration = self.store.get_project_registration(self.project_id)
        suspended = self.store.project_registry_audit(self.project_id)[-1]
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        inventory = self._empty_staging_inventory()
        packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        self.assertTrue(packet.complete)
        self.assertEqual(packet.pending_purge_work_count, 1)

        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE expiry_purge_targets SET status = 'failed', attempts = 1 "
                "WHERE receipt_id = ? AND path = ?",
                (receipt.receipt_id, artifact.path),
            )
        changed_packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        self.assertNotEqual(changed_packet.packet_sha256, packet.packet_sha256)

        stale_request = ProjectStatusChangeRequest(
            project_id=self.project_id,
            status="active",
            rationale="Reject purge-target changes after reactivation review",
            expected_revision=registration.revision,
            transition_id="reactivate-stale-purge-review-1",
            review_packet_sha256=packet.packet_sha256,
            suspension_transition_id=packet.suspension_transition_id,
            staging_inventory_sha256=inventory.manifest_sha256,
            staging_inventory_count=inventory.usage.regular_file_count,
            staging_inventory_bytes=inventory.usage.observed_file_bytes,
            staging_inventory_observed_at=inventory.usage.observed_at,
        )
        with self.assertRaisesRegex(ConflictError, "review packet is incomplete or stale"):
            self.manager.set_project_status(self.operator, stale_request)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status, "suspended"
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended
        )

    def _assert_reactivation_review_invalidated_by_grant_revocation(self) -> None:
        """A changed grant history requires a new review before reactivation."""

        grant = self._grant()
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        registration = self.store.get_project_registration(self.project_id)
        suspended = self._change_status(
            "suspended",
            "Pause before grant review",
            registration.revision,
            "suspend-grant-review-1",
        )
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        self._allow_admin(ProjectAdministrationAction.REVOKE)
        inventory = self._empty_staging_inventory()
        packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        self.assertTrue(packet.complete)
        self.assertEqual(packet.active_grant_count, 1)

        self.manager.revoke(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            ProjectAction.READ,
            "Revoke the reviewed read grant",
        )
        stale_request = ProjectStatusChangeRequest(
            project_id=self.project_id,
            status="active",
            rationale="Reject the review after grant revocation",
            expected_revision=suspended.registration.revision,
            transition_id="reactivate-stale-grant-review-1",
            review_packet_sha256=packet.packet_sha256,
            suspension_transition_id=packet.suspension_transition_id,
            staging_inventory_sha256=inventory.manifest_sha256,
            staging_inventory_count=inventory.usage.regular_file_count,
            staging_inventory_bytes=inventory.usage.observed_file_bytes,
            staging_inventory_observed_at=inventory.usage.observed_at,
        )

        with self.assertRaisesRegex(ConflictError, "review packet is incomplete or stale"):
            self.manager.set_project_status(self.operator, stale_request)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status,
            "suspended",
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended.receipt
        )
        self.assertEqual(
            self.store.project_grants(self.project_id)[-1].grant_id, grant.grant_id
        )

        current = self._change_status(
            "active",
            "Reactivate after fresh grant review",
            suspended.registration.revision,
            "reactivate-fresh-grant-review-1",
        )
        self.assertEqual(current.registration.status, "active")
        self.assertNotEqual(current.receipt.review_packet_sha256, packet.packet_sha256)
        self._assert_reactivation_review_rejects_changed_inventory()

    def _assert_reactivation_review_rejects_changed_inventory(self) -> None:
        """Reject a staging scan digest changed after the operator reviewed it."""

        registration = self.store.get_project_registration(self.project_id)
        suspended = self._change_status(
            "suspended",
            "Pause before staging inventory review",
            registration.revision,
            "suspend-staging-review-1",
        )
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        inventory = self._empty_staging_inventory()
        packet = self.manager.project_reactivation_review_packet(
            self.operator, self.project_id, inventory
        )
        changed_inventory = replace(
            inventory,
            manifest_sha256=hashlib.sha256(b"changed staging inventory").hexdigest(),
        )
        stale_request = ProjectStatusChangeRequest(
            project_id=self.project_id,
            status="active",
            rationale="Reject a staging change after review",
            expected_revision=suspended.registration.revision,
            transition_id="reactivate-stale-staging-review-1",
            review_packet_sha256=packet.packet_sha256,
            suspension_transition_id=packet.suspension_transition_id,
            staging_inventory_sha256=changed_inventory.manifest_sha256,
            staging_inventory_count=changed_inventory.usage.regular_file_count,
            staging_inventory_bytes=changed_inventory.usage.observed_file_bytes,
            staging_inventory_observed_at=changed_inventory.usage.observed_at,
        )

        with self.assertRaisesRegex(ConflictError, "review packet is incomplete or stale"):
            self.manager.set_project_status(self.operator, stale_request)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status,
            "suspended",
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended.receipt
        )

        expired_observation_request = replace(
            stale_request,
            rationale="Reject the expired staging observation",
            transition_id="reactivate-expired-staging-review-1",
            staging_inventory_sha256=inventory.manifest_sha256,
        )
        with patch_store_symbol("datetime", _ExpiredObservationDatetime):
            with self.assertRaisesRegex(
                ConflictError, "review packet is incomplete or stale"
            ):
                self.manager.set_project_status(
                    self.operator, expired_observation_request
                )
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status,
            "suspended",
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1], suspended.receipt
        )

    def test_registration_denial_is_atomic_and_records_no_project(self) -> None:
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.register_project(
                self.operator,
                self._registration_request("Unapproved registration attempt"),
            )
        with self.assertRaises(NotFoundError):
            self.store.get_project_registration(self.project_id)
        with self.store.transaction() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM project_registry").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM project_registry_audit"
                ).fetchone()[0],
                0,
            )

    def test_control_plane_storage_is_project_scoped_and_requires_view(self) -> None:
        self._register()
        grant = self._grant()
        self._allow_admin(ProjectAdministrationAction.REVOKE)
        self.manager.revoke(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            ProjectAction.READ,
            "Revoke the test grant",
        )
        other_project = "project-b"
        self.admin.allowed.add(
            (
                self.operator.subject_id,
                other_project,
                ProjectAdministrationAction.REGISTER,
            )
        )
        self.manager.register_project(
            self.operator,
            ProjectRegistrationRequest(
                project_id=other_project,
                repository_fingerprint=hashlib.sha256(b"repo-b").hexdigest(),
                config_sha256=hashlib.sha256(b"config-b").hexdigest(),
                backend_api_version=1,
                rationale="Register an isolated second project",
            ),
        )
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO request_rate_buckets
                   (subject_id, project_id, tokens, updated_at, touched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (self.reader.subject_id, self.project_id, 3.5, 100.0, 100.0),
            )
            connection.execute(
                """INSERT INTO request_rate_buckets
                   (subject_id, project_id, tokens, updated_at, touched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                ("consumer-b", other_project, 8.0, 100.0, 100.0),
            )
            connection.execute(
                """INSERT INTO event_payload_scrub_queue
                   (scrub_id, project_id, event_id, queued_at, attempts,
                    last_error_code)
                   VALUES (?, NULL, NULL, ?, ?, ?)""",
                (7, "2026-10-23T00:00:00.000Z", 2, "checkpoint_busy"),
            )

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.storage_usage(self.reader, self.project_id)

        database_path = Path(self.store.database)
        backup_directory = database_path.parent / "backups"
        backup_directory.mkdir(mode=0o700)
        backup_file = backup_directory / "curator-v2-2026-10-28.sqlite3"
        backup_file.write_bytes(b"verified-snapshot")
        backup_file.chmod(0o600)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        usage = self.manager.storage_usage(self.operator, self.project_id)
        self.assertIsNotNone(usage.backup_storage)
        assert usage.backup_storage is not None
        self.assertEqual(usage.backup_storage.status, "available")
        self.assertEqual(usage.backup_storage.backup_count, 1)
        self.assertEqual(usage.backup_storage.file_bytes, len(b"verified-snapshot"))
        self.assertEqual(
            usage.backup_storage.allocated_bytes,
            backup_file.stat().st_blocks * 512,
        )
        self.assertEqual(usage.backup_storage.observed_entry_count, 1)
        self.assertEqual(usage.backup_storage.observed_file_count, 1)
        self.assertEqual(
            usage.backup_storage.observed_file_bytes,
            len(b"verified-snapshot"),
        )
        self.assertEqual(
            usage.backup_storage.observed_allocated_bytes,
            backup_file.stat().st_blocks * 512,
        )
        counts = {item.class_name: item.record_count for item in usage.classes}
        logical_bytes = {item.class_name: item.logical_bytes for item in usage.classes}
        self.assertEqual(
            counts,
            {
                "consumer_bindings": 1,
                "consumer_binding_audit": 1,
                "consumer_drain_events": 0,
                "consumer_drain_sessions": 0,
                "project_registry": 1,
                "project_registry_audit": 1,
                "project_retirement_tombstones": 0,
                "terminal_event_dispositions": 0,
                "project_grants": 1,
                "project_grant_revocations": 1,
                "request_rate_buckets": 1,
            },
        )
        self.assertTrue(
            all(count == 0 or logical_bytes[name] > 0 for name, count in counts.items())
        )
        with self.store.transaction() as connection:
            byte_rows = {
                "consumer_bindings": (
                    connection.execute(
                        """SELECT project_id, status, revision, source_epoch,
                                  updated_by, updated_at FROM consumer_bindings
                           WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    ("project_id", "status", "revision", "source_epoch", "updated_by", "updated_at"),
                ),
                "consumer_binding_audit": (
                    connection.execute(
                        """SELECT audit_id, project_id, actor_id, action,
                                  from_status, to_status, source_epoch, revision,
                                  transition_id, rationale, created_at
                           FROM consumer_binding_audit WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    (
                        "audit_id", "project_id", "actor_id", "action", "from_status",
                        "to_status", "source_epoch", "revision", "transition_id",
                        "rationale", "created_at",
                    ),
                ),
                "project_registry": (
                    connection.execute(
                        """SELECT project_id, repository_fingerprint, config_sha256,
                                  backend_api_version, status, registered_by,
                                  registered_at, updated_by, updated_at, revision
                           FROM project_registry WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    (
                        "project_id", "repository_fingerprint", "config_sha256",
                        "backend_api_version", "status", "registered_by",
                        "registered_at", "updated_by", "updated_at", "revision",
                    ),
                ),
                "project_registry_audit": (
                    connection.execute(
                        """SELECT audit_id, project_id, actor_id, action,
                                  repository_fingerprint, config_sha256,
                                  backend_api_version, rationale, created_at, revision,
                                  transition_id FROM project_registry_audit
                           WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    (
                        "audit_id", "project_id", "actor_id", "action",
                        "repository_fingerprint", "config_sha256", "backend_api_version",
                        "rationale", "created_at", "revision", "transition_id",
                    ),
                ),
                "project_grants": (
                    connection.execute(
                        """SELECT grant_id, project_id, subject_id, action, granted_by,
                                  rationale, granted_at FROM project_grants
                           WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    (
                        "grant_id", "project_id", "subject_id", "action", "granted_by",
                        "rationale", "granted_at",
                    ),
                ),
                "project_grant_revocations": (
                    connection.execute(
                        """SELECT r.grant_id, r.revoked_by, r.rationale, r.revoked_at
                           FROM project_grant_revocations AS r
                           JOIN project_grants AS g ON g.grant_id = r.grant_id
                           WHERE g.project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    ("grant_id", "revoked_by", "rationale", "revoked_at"),
                ),
                "request_rate_buckets": (
                    connection.execute(
                        """SELECT subject_id, project_id, tokens, updated_at, touched_at
                           FROM request_rate_buckets WHERE project_id = ?""",
                        (self.project_id,),
                    ).fetchall(),
                    ("subject_id", "project_id", "tokens", "updated_at", "touched_at"),
                ),
            }

        def stored_text_bytes(rows: list[sqlite3.Row], fields: tuple[str, ...]) -> int:
            return sum(
                len((str(row[field]) if row[field] is not None else "").encode("utf-8"))
                for row in rows
                for field in fields
            )

        for class_name, (rows, fields) in byte_rows.items():
            self.assertEqual(logical_bytes[class_name], stored_text_bytes(rows, fields))
        self.assertEqual(usage.logical_record_bytes, sum(logical_bytes.values()))
        self.assertEqual(usage.project_id, self.project_id)
        self.assertNotIn("subject_id", usage.__dataclass_fields__)
        self.assertNotIn(grant.grant_id, repr(usage))
        global_classes = {
            item.class_name: (item.record_count, item.logical_bytes)
            for item in usage.global_classes
        }
        expected_scrub_bytes = sum(
            len(value.encode("utf-8"))
            for value in ("7", "2026-10-23T00:00:00.000Z", "2", "checkpoint_busy")
        )
        self.assertEqual(
            global_classes,
            {"event_payload_scrub_queue_unassigned": (1, expected_scrub_bytes)},
        )
        self.assertEqual(usage.global_logical_bytes, expected_scrub_bytes)
        self.assertNotIn("scrub_id", usage.__dataclass_fields__)
        self.assertNotIn("event_id", usage.__dataclass_fields__)
        physical = usage.sqlite_physical
        self.assertIsNotNone(physical)
        assert physical is not None
        if physical.status == "available":
            pages = physical.pages
            assert pages.attributed_btree_bytes is not None
            assert pages.unattributed_database_bytes is not None
            physical_classes = {item.class_name: item for item in physical.classes}
            self.assertIn("project_registry", physical_classes)
            self.assertGreater(physical_classes["project_registry"].page_count, 0)
            self._assert_physical_class_names_cover_schema_tables(
                set(physical_classes)
            )
            self.assertEqual(
                sum(item.allocated_bytes for item in physical.classes),
                pages.attributed_btree_bytes,
            )
            self.assertEqual(
                pages.allocated_bytes,
                pages.attributed_btree_bytes + pages.unattributed_database_bytes,
            )
            self.assertGreaterEqual(
                pages.unattributed_database_bytes,
                pages.freelist_page_count * pages.page_size,
            )
            self.assertNotIn(grant.grant_id, repr(physical))
        else:
            self.assertEqual(physical.classes, ())
            self.assertIsNone(physical.pages.attributed_btree_bytes)
            self.assertIsNone(physical.pages.unattributed_database_bytes)

    def test_registration_is_unique_and_audits_updates_and_status_changes(self) -> None:
        self._register()
        with self.assertRaisesRegex(ConflictError, "already registered"):
            self.manager.register_project(
                self.operator,
                self._registration_request("Duplicate registration"),
            )

        updated_sha = hashlib.sha256(b"config-v2").hexdigest()
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        updated = self.manager.update_project_registration(
            self.operator,
            self._registration_request(
                "Approve the reviewed plugin configuration update",
                config_sha256=updated_sha,
                expected_revision=1,
            ),
            "config-change-1",
        )
        self.assertEqual(updated.registration.config_sha256, updated_sha)
        self.assertEqual(updated.registration.revision, 2)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        audit_before_replay = self.manager.list_registration_audit(
            self.operator, self.project_id
        )
        replayed_update = self.manager.update_project_registration(
            self.operator,
            self._registration_request(
                "Approve the reviewed plugin configuration update",
                config_sha256=updated_sha,
                expected_revision=1,
            ),
            "config-change-1",
        )
        self.assertTrue(replayed_update.replayed)
        self.assertEqual(replayed_update.receipt, updated.receipt)
        self.assertEqual(replayed_update.registration.revision, 2)
        self.assertEqual(
            self.manager.list_registration_audit(self.operator, self.project_id),
            audit_before_replay,
        )
        with self.assertRaisesRegex(ConflictError, "transition ID"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Conflicting reuse of the same transition ID",
                    config_sha256=hashlib.sha256(b"other-config").hexdigest(),
                    expected_revision=1,
                ),
                "config-change-1",
            )
        with self.assertRaisesRegex(ConflictError, "revision is stale"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Reject the stale config update",
                    config_sha256=hashlib.sha256(b"stale-config").hexdigest(),
                    expected_revision=1,
                ),
                "config-stale-1",
            )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id)[-1].revision, 2
        )

        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        suspended = self._change_status(
            "suspended",
            "Disable the pilot binding while reviewing scope",
            updated.registration.revision,
            "suspend-1",
        )
        self.assertEqual(suspended.registration.status, "suspended")
        self.assertEqual(suspended.registration.revision, 3)
        replayed_suspend = self._change_status(
            "suspended",
            "Disable the pilot binding while reviewing scope",
            updated.registration.revision,
            "suspend-1",
        )
        self.assertTrue(replayed_suspend.replayed)
        self.assertEqual(replayed_suspend.receipt, suspended.receipt)
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        with self.assertRaisesRegex(ConflictError, "revision is stale"):
            self._change_status(
                "active",
                "Reject reactivation reviewed against stale state",
                updated.registration.revision,
                "reactivate-stale-1",
            )
        current_after_stale = self.store.get_project_registration(self.project_id)
        self.assertEqual(current_after_stale.status, "suspended")
        self.assertEqual(current_after_stale.revision, 3)
        active = self._change_status(
            "active",
            "Re-enable the reviewed pilot binding",
            suspended.registration.revision,
            "reactivate-1",
        )
        self.assertEqual(active.registration.status, "active")
        self.assertEqual(active.registration.revision, 4)
        replayed_update_after_later_transitions = self.manager.update_project_registration(
            self.operator,
            self._registration_request(
                "Approve the reviewed plugin configuration update",
                config_sha256=updated_sha,
                expected_revision=1,
            ),
            "config-change-1",
        )
        self.assertTrue(replayed_update_after_later_transitions.replayed)
        self.assertEqual(
            replayed_update_after_later_transitions.receipt, updated.receipt
        )
        self.assertEqual(
            replayed_update_after_later_transitions.registration.revision, 4
        )

        self._allow_admin(ProjectAdministrationAction.VIEW)
        audit = self.manager.list_registration_audit(self.operator, self.project_id)
        self.assertEqual(
            [entry.action for entry in audit],
            ["registered", "updated", "suspended", "reactivated"],
        )
        self.assertEqual([entry.revision for entry in audit], [1, 2, 3, 4])
        self.assertEqual(
            [entry.transition_id for entry in audit],
            [None, "config-change-1", "suspend-1", "reactivate-1"],
        )
        self.assertEqual(
            [entry.actor_id for entry in audit], [self.operator.subject_id] * 4
        )

    def test_status_transition_id_cannot_be_reused_with_changed_input(self) -> None:
        """An idempotent retry must match every persisted transition field."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        self._change_status(
            "suspended",
            "Suspend for a reviewed pause",
            1,
            "suspend-same-id",
        )

        with self.assertRaisesRegex(ConflictError, "transition ID"):
            self._change_status(
                "suspended",
                "Changed rationale under the same transition ID",
                1,
                "suspend-same-id",
            )
        self.assertEqual(
            self.store.get_project_registration(self.project_id).revision,
            2,
        )

    def test_boolean_revision_is_rejected_for_registration_transitions(self) -> None:
        """Bool must not pass the exact-integer revision boundary."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        audit_before = self.store.project_registry_audit(self.project_id)

        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Reject boolean revision",
                    config_sha256=hashlib.sha256(b"config-v2").hexdigest(),
                    expected_revision=True,
                ),
                "boolean-update-1",
            )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self._change_status(
                "suspended",
                "Reject boolean revision",
                True,
                "boolean-status-1",
            )

        self.assertEqual(
            self.store.get_project_registration(self.project_id).revision,
            1,
        )
        self.assertEqual(
            self.store.project_registry_audit(self.project_id),
            audit_before,
        )

    def test_repository_fingerprint_replacement_requires_fresh_enrollment(self) -> None:
        """A direct config update cannot silently replace a consumer binding."""

        self._register()
        grant = self._grant(ProjectAction.WRITE)
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        registration_before = self.store.get_project_registration(self.project_id)
        audit_before = self.store.project_registry_audit(self.project_id)
        grants_before = self.store.project_grants(self.project_id)
        replacement_fingerprint = hashlib.sha256(b"replacement-repository").hexdigest()

        with self.assertRaisesRegex(ConflictError, "fresh enrollment"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Attempt to replace the repository without deregistration",
                    repository_fingerprint=replacement_fingerprint,
                    expected_revision=registration_before.revision,
                ),
                "repository-replacement-1",
            )

        self.assertEqual(
            self.store.get_project_registration(self.project_id), registration_before
        )
        self.assertEqual(self.store.project_registry_audit(self.project_id), audit_before)
        self.assertEqual(self.store.project_grants(self.project_id), grants_before)
        self.assertIsNone(grant.revoked_at)

    def test_repository_fingerprint_cannot_be_registered_under_two_ids(self) -> None:
        self._register()
        self._allow_admin(ProjectAdministrationAction.REGISTER)
        other_project_admin = AuthenticatedCaller("operator-2")
        self.admin.allowed.add(
            (
                other_project_admin.subject_id,
                "project-b",
                ProjectAdministrationAction.REGISTER,
            )
        )
        with self.assertRaisesRegex(ConflictError, "already registered"):
            self.manager.register_project(
                other_project_admin,
                self._registration_request(
                    "Attempt to bind the same repository twice",
                    project_id="project-b",
                ),
            )

    def test_exact_grant_survives_restart_and_revocation_denies_immediately(self) -> None:
        self._register()
        first = self._grant()
        authorizer = SQLiteProjectGrantAuthorizer(self.store)
        self.assertTrue(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.WRITE))
        self.assertFalse(
            authorizer.authorize(
                AuthenticatedCaller("other-user"), self.project_id, ProjectAction.READ
            )
        )
        self.assertFalse(
            authorizer.authorize(self.reader, "other-project", ProjectAction.READ)
        )

        self._allow_admin(ProjectAdministrationAction.REVOKE)
        revoked = self.manager.revoke(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            ProjectAction.READ,
            "The pilot read access is no longer needed",
        )
        self.assertEqual(revoked.grant_id, first.grant_id)
        self.assertFalse(revoked.active)
        self.assertEqual(revoked.revoked_by, self.operator.subject_id)
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))

        second = self._grant()
        self.assertNotEqual(first.grant_id, second.grant_id)
        self.assertTrue(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        self._allow_admin(ProjectAdministrationAction.VIEW)
        history = self.manager.list_grants(self.operator, self.project_id)
        self.assertEqual([entry.grant_id for entry in history], [first.grant_id, second.grant_id])
        self.assertEqual([entry.active for entry in history], [False, True])

    def test_suspended_project_denies_grants_and_authorization_without_deleting_history(
        self,
    ) -> None:
        self._register()
        self._grant()
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        self._change_status(
            "suspended",
            "Suspend access during the pilot pause",
            self.store.get_project_registration(self.project_id).revision,
            "pause-1",
        )
        authorizer = SQLiteProjectGrantAuthorizer(self.store)
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        with self.assertRaisesRegex(ConflictError, "not active"):
            self._grant(ProjectAction.WRITE)
        self.assertEqual(len(self.store.project_grants(self.project_id)), 1)

    def test_denied_grant_and_revoke_leave_durable_state_unchanged(self) -> None:
        self._register()
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.grant(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                ProjectAction.READ,
                "Denied grant attempt",
            )
        self.assertEqual(self.store.project_grants(self.project_id), ())

        granted = self._grant()
        self.admin.allowed.discard(
            (self.operator.subject_id, self.project_id, ProjectAdministrationAction.REVOKE)
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.revoke(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                ProjectAction.READ,
                "Denied revocation attempt",
            )
        self.assertTrue(
            SQLiteProjectGrantAuthorizer(self.store).authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )
        self.assertEqual(self.store.project_grants(self.project_id)[0].grant_id, granted.grant_id)

    def test_grant_administration_rejects_untyped_scope(self) -> None:
        self._register()
        with self.assertRaisesRegex(ValueError, "known ProjectAction"):
            self.manager.grant(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                "read",  # type: ignore[arg-type]
                "A string is not an authorization enum",
            )
        self.assertEqual(self.store.project_grants(self.project_id), ())

if __name__ == "__main__":
    unittest.main()
