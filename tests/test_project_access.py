"""Durable project registration and revocable access-grant tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
import tempfile
import unittest

from curatormd_v2 import (
    AuthenticatedCaller,
    ConflictError,
    CuratorStore,
    ConsumerBindingTransitionRequest,
    NotFoundError,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    SQLiteProjectGrantAuthorizer,
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAuthorizationBinding,
)
from curatormd_v2.events import EventEnvelope, GoalActivityObserved
from curatormd_v2.models import FactKind


class TestProjectAdministrator:  # pylint: disable=too-few-public-methods
    """Allow only explicitly configured host-level project admin actions."""

    def __init__(self) -> None:
        self.allowed: set[tuple[str, str, ProjectAdministrationAction]] = set()

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Match the authenticated subject and exact project/admin action."""

        return (caller.subject_id, project_id, action) in self.allowed


class DurableProjectAccessTests(unittest.TestCase):
    """Prove persistent grants, auditability, revocation, and default denial."""

    def setUp(self) -> None:
        # unittest keeps the directory and store alive until teardown.
        # pylint: disable=consider-using-with
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        # pylint: enable=consider-using-with
        store = CuratorStore(
            f"{temporary}/curator.sqlite3"
        )
        self.store = self.enterContext(store)
        self.admin = TestProjectAdministrator()
        self.manager = ProjectAccessManager(self.store, self.admin)
        self.operator = AuthenticatedCaller("operator-1")
        self.reader = AuthenticatedCaller("consumer-1")
        self.project_id = "project-a"
        self.repository_fingerprint = hashlib.sha256(b"repo-a").hexdigest()
        self.config_sha256 = hashlib.sha256(b"config-v1").hexdigest()

    def _allow_admin(self, action: ProjectAdministrationAction) -> None:
        self.admin.allowed.add((self.operator.subject_id, self.project_id, action))

    def _registration_request(
        self,
        rationale: str,
        *,
        project_id: str | None = None,
        repository_fingerprint: str | None = None,
        config_sha256: str | None = None,
        expected_revision: int | None = None,
    ) -> ProjectRegistrationRequest:
        """Build a typed host registration request for one test case."""

        return ProjectRegistrationRequest(
            project_id=project_id or self.project_id,
            repository_fingerprint=(
                repository_fingerprint or self.repository_fingerprint
            ),
            config_sha256=config_sha256 or self.config_sha256,
            backend_api_version=1,
            rationale=rationale,
            expected_revision=expected_revision,
        )

    def _register(self) -> None:
        self._allow_admin(ProjectAdministrationAction.REGISTER)
        self.manager.register_project(
            self.operator,
            self._registration_request("Approve the pilot repository binding"),
        )

    def _grant(self, action: ProjectAction = ProjectAction.READ):
        self._allow_admin(ProjectAdministrationAction.GRANT)
        return self.manager.grant(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            action,
            "Grant the pilot consumer its explicit read scope",
        )

    def _change_status(
        self,
        status: str,
        rationale: str,
        expected_revision: int,
        transition_id: str,
    ):
        return self.manager.set_project_status(
            self.operator,
            ProjectStatusChangeRequest(
                project_id=self.project_id,
                status=status,
                rationale=rationale,
                expected_revision=expected_revision,
                transition_id=transition_id,
            ),
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

        self._allow_admin(ProjectAdministrationAction.VIEW)
        usage = self.manager.storage_usage(self.operator, self.project_id)
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
                "project_grants": 1,
                "project_grant_revocations": 1,
                "request_rate_buckets": 1,
            },
        )
        self.assertTrue(
            all(count == 0 or logical_bytes[name] > 0 for name, count in counts.items())
        )
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

    def test_consumer_binding_deregistration_is_separate_and_fences_old_grants(self) -> None:
        self._register()
        grant = self._grant()
        binding_config = ProjectAuthorizationBinding(
            project_id=self.project_id,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=self.config_sha256,
            backend_api_version=1,
            allowed_actions=frozenset({ProjectAction.READ}),
        )
        launcher = FingerprintBoundSQLiteProjectGrantAuthorizer(
            self.store, binding_config
        )
        self.assertTrue(launcher.authorize(self.reader, self.project_id, ProjectAction.READ))

        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistration_pending",
            rationale="Disable the detached consumer",
            expected_revision=1,
            transition_id="consumer-cutover-1",
        )
        pending = self.manager.transition_consumer_binding(
            self.operator, pending_request
        )
        self.assertEqual(
            (pending.binding.status, pending.binding.revision),
            ("deregistration_pending", 2),
        )
        self.assertFalse(launcher.authorize(self.reader, self.project_id, ProjectAction.READ))
        self.assertFalse(
            SQLiteProjectGrantAuthorizer(self.store).authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )
        self.assertEqual(self.store.get_project_registration(self.project_id).status, "active")
        self.assertEqual(self.store.get_project_registration(self.project_id).revision, 1)
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        with self.assertRaisesRegex(ConflictError, "consumer binding is not active"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Reject config changes during consumer deregistration",
                    config_sha256=hashlib.sha256(b"config-after-cutover").hexdigest(),
                    expected_revision=1,
                ),
                "config-after-cutover-1",
            )
        replay = self.manager.transition_consumer_binding(
            self.operator, pending_request
        )
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, pending.receipt)
        with self.assertRaisesRegex(ConflictError, "not active"):
            self._grant(ProjectAction.WRITE)

        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        final_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistered",
            rationale="All inventoried events have durable processed receipts",
            expected_revision=2,
            transition_id="consumer-cutover-final-1",
        )
        final = self.manager.transition_consumer_binding(self.operator, final_request)
        self.assertEqual((final.binding.status, final.binding.revision), ("deregistered", 3))
        self.assertEqual(final.binding.source_epoch, 1)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        self.assertEqual(
            len(self.manager.list_consumer_binding_audit(self.operator, self.project_id)),
            3,
        )
        closed_grant = self.store.project_grants(self.project_id)[0]
        self.assertEqual(closed_grant.grant_id, grant.grant_id)
        self.assertEqual(closed_grant.revoked_by, self.operator.subject_id)
        self.assertEqual(closed_grant.revoke_rationale, pending_request.rationale)

    def test_consumer_deregistration_waits_for_unresolved_events(self) -> None:
        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending = self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Stop new consumer activity",
                expected_revision=1,
                transition_id="consumer-pending-unresolved",
            ),
        )
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at)
                   VALUES (?, 'event-pending', 'test.event', ?, 0, 'received', ?)""",
                (self.project_id, "0" * 64, "2026-10-23T00:00:00.000Z"),
            )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        final_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistered",
            rationale="Attempt finalization with an unresolved event",
            expected_revision=pending.binding.revision,
            transition_id="consumer-final-unresolved",
        )
        with self.assertRaisesRegex(ConflictError, "unresolved source events"):
            self.manager.transition_consumer_binding(self.operator, final_request)
        self.assertEqual(
            self.store.get_consumer_binding(self.project_id).status,
            "deregistration_pending",
        )
        history = self.store.consumer_binding_audit(self.project_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1], pending.receipt)

    def test_drain_allows_only_the_reviewed_event_and_matching_profile(self) -> None:
        """A short drain cannot admit new IDs, changed envelopes, or other profiles."""

        self._register()
        event = EventEnvelope(
            "queued-event-1",
            self.project_id,
            GoalActivityObserved("goal-1", "fact-1", FactKind.CHANGE, "Done."),
            source_id="hermes-profile-alpha-generation-1",
            source_sequence=1,
        )
        self.store.ingest_event(event)
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending = self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                self.project_id,
                "deregistration_pending",
                "Stop new consumer work and review the queued event",
                1,
                "drain-transition-1",
            ),
        )
        count, inventory_digest = self.store.consumer_drain_inventory(self.project_id)
        self.assertEqual(count, 1)
        self._allow_admin(ProjectAdministrationAction.DRAIN)
        authorized_count, expires_at = self.manager.authorize_consumer_drain(
            self.operator,
            self.project_id,
            pending.receipt.transition_id,
            pending.binding.revision,
            inventory_digest,
            60,
            "alpha",
        )
        self.assertEqual(authorized_count, 1)
        self.assertTrue(expires_at)
        self.assertTrue(
            self.store.consumer_drain_allows(self.operator.subject_id, "alpha", event)
        )
        self.assertFalse(
            self.store.consumer_drain_allows(self.operator.subject_id, "other", event)
        )
        self.assertFalse(
            self.store.consumer_drain_allows(
                self.operator.subject_id, "alpha", replace(event, event_id="new-event")
            )
        )

    def test_project_retirement_is_irreversible_and_keeps_records(self) -> None:
        """Retirement fences a project but preserves unresolved event records."""

        self._register()
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at)
                   VALUES (?, 'preserved-pending-event', 'test.event', ?, 0,
                           'received', '2026-10-23T00:00:00Z')""",
                (self.project_id, "0" * 64),
            )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                self.project_id, "deregistration_pending", "Close consumer", 1,
                "retire-pending-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.RETIRE)
        receipt = self.manager.retire_project(
            self.operator, self.project_id, "Owner retires this project", 1,
            "retire-project-1",
        )
        self.assertEqual(receipt.retired_revision, 2)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status, "suspended"
        )
        self.assertEqual(self.store.get_project_retirement(self.project_id), receipt)
        with self.store.transaction() as connection:
            preserved_event = connection.execute(
                "SELECT status FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (self.project_id, "preserved-pending-event"),
            ).fetchone()
        self.assertEqual(preserved_event["status"], "received")
        self.assertEqual(
            self.manager.retire_project(
                self.operator, self.project_id, "Owner retires this project", 1,
                "retire-project-1",
            ),
            receipt,
        )
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        with self.assertRaisesRegex(ConflictError, "retired projects"):
            self._change_status("active", "Attempt to reopen retired project", 2,
                                "retire-reactivate-1")

    def test_reenrollment_rotates_source_epoch_without_restoring_grants(self) -> None:
        """A fresh source epoch requires explicit reviewed enrollment and grants."""

        self._register()
        original_grant = self._grant()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Cut over the old consumer source",
                expected_revision=1,
                transition_id="reenroll-pending-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistered",
                rationale="All old events have processed receipts",
                expected_revision=2,
                transition_id="reenroll-final-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        reviewed_config_sha = hashlib.sha256(b"reviewed-config-v2").hexdigest()
        updated = self.manager.update_project_registration(
            self.operator,
            self._registration_request(
                "Review the detached consumer's current repository config",
                config_sha256=reviewed_config_sha,
                expected_revision=1,
            ),
            "reenroll-config-review-1",
        )
        self.assertEqual(updated.registration.revision, 2)
        self._allow_admin(ProjectAdministrationAction.REENROLL)
        request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="active",
            rationale="Approve the fresh consumer source epoch",
            expected_revision=3,
            transition_id="reenroll-epoch-2",
            expected_source_epoch=1,
            expected_project_revision=2,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=reviewed_config_sha,
            backend_api_version=1,
        )

        result = self.manager.transition_consumer_binding(self.operator, request)

        self.assertEqual(result.binding.status, "active")
        self.assertEqual(result.binding.revision, 4)
        self.assertEqual(result.binding.source_epoch, 2)
        self.assertEqual(result.receipt.action, "reenrolled")
        self.assertEqual(result.receipt.source_epoch, 2)
        self.assertFalse(result.replayed)
        self.assertFalse(
            self.store.has_project_grant(
                self.reader.subject_id, self.project_id, ProjectAction.READ.value
            )
        )
        replay = self.manager.transition_consumer_binding(self.operator, request)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, result.receipt)
        self.assertEqual(
            self.store.project_grants(self.project_id)[0].grant_id,
            original_grant.grant_id,
        )

        self._allow_admin(ProjectAdministrationAction.GRANT)
        self.manager.grant(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            ProjectAction.READ,
            "Grant reviewed access to the new consumer source",
        )
        current_launcher = FingerprintBoundSQLiteProjectGrantAuthorizer(
            self.store,
            ProjectAuthorizationBinding(
                project_id=self.project_id,
                repository_fingerprint=self.repository_fingerprint,
                config_sha256=reviewed_config_sha,
                backend_api_version=1,
                allowed_actions=frozenset({ProjectAction.READ}),
            ),
        )
        self.assertTrue(
            current_launcher.authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )

    def test_reenrollment_rejects_stale_epoch_and_unresolved_events(self) -> None:
        """Old source epochs and late pre-cutover receipts cannot be enrolled."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Cut over the old consumer source",
                expected_revision=1,
                transition_id="reenroll-pending-open-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistered",
                rationale="No old events were pending at cutover",
                expected_revision=2,
                transition_id="reenroll-final-open-1",
            ),
        )
        request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="active",
            rationale="Approve the fresh consumer source epoch",
            expected_revision=3,
            transition_id="reenroll-epoch-stale",
            expected_source_epoch=2,
            expected_project_revision=1,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=self.config_sha256,
            backend_api_version=1,
        )
        self._allow_admin(ProjectAdministrationAction.REENROLL)
        with self.assertRaisesRegex(ConflictError, "source epoch is stale"):
            self.manager.transition_consumer_binding(self.operator, request)

        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at)
                   VALUES (?, 'late-old-event', 'test.event', ?, 0, 'received', ?)""",
                (self.project_id, "0" * 64, "2026-10-23T00:00:00.000Z"),
            )
        with self.assertRaisesRegex(ConflictError, "unresolved source events"):
            self.manager.transition_consumer_binding(
                self.operator,
                replace(request, expected_source_epoch=1),
            )
        binding = self.store.get_consumer_binding(self.project_id)
        self.assertEqual(
            (binding.status, binding.revision, binding.source_epoch),
            ("deregistered", 3, 1),
        )


if __name__ == "__main__":
    unittest.main()
