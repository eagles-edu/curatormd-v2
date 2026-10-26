"""Exercise purge migration behavior."""
# pylint: disable=duplicate-code
# Parallel tests repeat setup to exercise distinct failure conditions.

from __future__ import annotations

import hashlib
import json
import sqlite3
from purge_fixtures import TestReviewAuthorizer, TestVerifier
from purge_test_support import PurgeTestSupport
from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    ArtifactStatus,
    ConflictError,
    CuratorService,
    CuratorStore,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewDecision,
    SDEConfirmationRequest,
)


class PurgeMigrationTests(PurgeTestSupport):
    """Exercise purge migration behavior."""

    def test_v28_migration_stales_unpurged_legacy_approvals(self) -> None:
        """Keep old targets visible but remove their automatic delete authority."""

        candidate_id = self.candidate("legacy occurrence identity")
        artifacts = {
            name: self.artifact(f"legacy-{name}.json")
            for name in ("pending", "failed", "held", "purged")
        }
        held = ArtifactRef(
            artifacts["held"][1].path,
            artifacts["held"][1].sha256,
            RetentionHoldKind.LEGAL,
            artifacts["held"][1].device_id,
            artifacts["held"][1].inode_id,
            artifacts["held"][1].occurrence_id,
        )
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=tuple(
                    artifacts[name][1]
                    for name in ("pending", "failed", "purged")
                )
                + (held,),
                artifact_inventory_complete=True,
            )
        )
        self.store.mark_receipt_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(b"legacy canonical proof").hexdigest(),
            "default",
        )

        expiry_artifact = self.artifact("legacy-expiry.json")[1]
        expiry_manifest = hashlib.sha256(
            json.dumps(
                [(expiry_artifact.path, expiry_artifact.sha256, expiry_artifact.occurrence_id)],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        expiry = self.store.create_expiry_purge_receipt(
            "default", "legacy-reviewer", expiry_manifest, (expiry_artifact,)
        )

        self.store.close()
        connection = sqlite3.connect(self.root / "curator.sqlite3")
        connection.execute(
            "UPDATE purge_targets SET occurrence_id = NULL, approval_stale = 0 "
            "WHERE receipt_id = ?",
            (receipt.receipt_id,),
        )
        connection.execute(
            "UPDATE purge_targets SET status = 'failed', attempts = 1, "
            "error = 'path_changed', next_attempt_at = '2026-01-01T00:00:00+00:00' "
            "WHERE receipt_id = ? AND path = ?",
            (receipt.receipt_id, artifacts["failed"][0].as_posix()),
        )
        connection.execute(
            "UPDATE purge_targets SET status = 'purged', attempts = 1 "
            "WHERE receipt_id = ? AND path = ?",
            (receipt.receipt_id, artifacts["purged"][0].as_posix()),
        )
        connection.execute(
            "UPDATE expiry_purge_targets SET occurrence_id = NULL, approval_stale = 0, "
            "status = 'failed', attempts = 1, next_attempt_at = '2026-01-01T00:00:00+00:00' "
            "WHERE receipt_id = ?",
            (expiry.receipt_id,),
        )
        connection.execute("ALTER TABLE purge_targets DROP COLUMN approval_stale")
        connection.execute("ALTER TABLE expiry_purge_targets DROP COLUMN approval_stale")
        connection.execute("PRAGMA user_version = 27")
        connection.commit()
        connection.close()

        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        targets = self.store.get_purge_target_records(receipt.receipt_id, "default")
        by_path = {item.artifact.path: item for item in targets}
        for name in ("pending", "failed", "held"):
            target = by_path[str(artifacts[name][0])]
            self.assertTrue(target.approval_stale)
            self.assertIsNone(target.next_attempt_at)
        self.assertEqual(by_path[str(artifacts["pending"][0])].status.value, "pending")
        self.assertEqual(by_path[str(artifacts["failed"][0])].status.value, "failed")
        self.assertEqual(by_path[str(artifacts["held"][0])].status.value, "held")
        self.assertEqual(
            by_path[str(artifacts["held"][0])].artifact.retention_hold,
            RetentionHoldKind.LEGAL,
        )
        self.assertEqual(by_path[str(artifacts["purged"][0])].status.value, "purged")
        self.assertFalse(by_path[str(artifacts["purged"][0])].approval_stale)
        self.assertEqual(
            self.store.get_purge_targets(receipt.receipt_id, pending_only=True), ()
        )
        with self.assertRaisesRegex(ConflictError, "already complete"):
            self.store.begin_purge_attempt(
                receipt.receipt_id, str(artifacts["pending"][0]), "default"
            )

        self.service.release_artifact_hold(
            receipt.receipt_id,
            str(artifacts["held"][0]),
            "Retention owner confirmed release",
            authenticated_subject="test-reviewer",
        )
        released = self.store.get_purge_target_records(receipt.receipt_id, "default")
        by_path = {item.artifact.path: item for item in released}
        self.assertEqual(by_path[str(artifacts["held"][0])].status.value, "pending")
        self.assertTrue(by_path[str(artifacts["held"][0])].approval_stale)
        self.assertEqual(
            self.store.get_purge_targets(receipt.receipt_id, pending_only=True), ()
        )

        migrated_expiry = self.store.expiry_purge_receipt(expiry.receipt_id, "default")
        self.assertEqual(
            tuple(item.path for item in migrated_expiry.approval_stale_artifacts),
            (expiry_artifact.path,),
        )
        self.assertIsNone(migrated_expiry.approval_stale_artifacts[0].occurrence_id)
        self.assertEqual(self.store.due_expiry_purge_receipts("default"), ())
        self.assertEqual(self.store.expiry_purge_targets(expiry.receipt_id, "default"), ())


    def test_v28_migration_rollback_preserves_legacy_retry_state(self) -> None:
        """A failed stale-approval migration rolls back its DDL and row changes."""

        candidate_id = self.candidate("atomic legacy occurrence migration")
        path, artifact = self.artifact("legacy-retry-state.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        self.store.close()
        connection = sqlite3.connect(self.root / "curator.sqlite3")
        connection.execute(
            "UPDATE purge_targets SET occurrence_id = NULL, status = 'failed', "
            "attempts = 1, error = 'path_changed', "
            "next_attempt_at = '2026-10-24T00:00:00+00:00' WHERE receipt_id = ?",
            (receipt.receipt_id,),
        )
        connection.execute("ALTER TABLE purge_targets DROP COLUMN approval_stale")
        connection.execute(
            """CREATE TRIGGER fail_legacy_occurrence_migration
               BEFORE UPDATE ON purge_targets
               BEGIN SELECT RAISE(ABORT, 'injected occurrence migration failure'); END"""
        )
        connection.execute("PRAGMA user_version = 27")
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError, "injected occurrence migration failure"
        ):
            CuratorStore(self.root / "curator.sqlite3")

        connection = sqlite3.connect(self.root / "curator.sqlite3")
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(purge_targets)")
        }
        failed_target = connection.execute(
            "SELECT status, attempts, error, next_attempt_at FROM purge_targets "
            "WHERE receipt_id = ?",
            (receipt.receipt_id,),
        ).fetchone()
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 27)
        self.assertNotIn("approval_stale", columns)
        self.assertEqual(
            failed_target,
            ("failed", 1, "path_changed", "2026-10-24T00:00:00+00:00"),
        )
        connection.execute("DROP TRIGGER fail_legacy_occurrence_migration")
        connection.commit()
        connection.close()

        self.store = CuratorStore(self.root / "curator.sqlite3")
        migrated_target = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )[0]
        self.assertTrue(migrated_target.approval_stale)
        self.assertEqual(migrated_target.status, ArtifactStatus.FAILED)
        self.assertEqual(migrated_target.attempts, 1)
        self.assertEqual(migrated_target.error, "path_changed")
        self.assertIsNone(migrated_target.next_attempt_at)
        self.assertEqual(
            self.store.get_purge_targets(receipt.receipt_id, pending_only=True), ()
        )
        self.assertTrue(path.exists())


    def test_v29_migration_stales_cleanup_receipts_without_dependency_maps(self) -> None:
        """A v28 approval without a reviewed map cannot authorize another unlink."""

        candidate_id = self.candidate("legacy dependency map")
        artifact_path, artifact = self.artifact("legacy-map-approval.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE purge_targets SET reacquisition_action = ? "
                "WHERE receipt_id = ? AND path = ?",
                (
                    ReacquisitionAction.NOT_REQUIRED.value,
                    receipt.receipt_id,
                    artifact.path,
                ),
            )
        self.store.mark_receipt_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(b"legacy map projection").hexdigest(),
            "default",
        )
        manifest = json.dumps(
            [(artifact.path, artifact.sha256, artifact.occurrence_id)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
        self.store.create_cleanup_authorization(
            receipt.receipt_id,
            "default",
            "test-reviewer",
            manifest_sha256,
            "a" * 64,
        )

        self.store.close()
        connection = sqlite3.connect(self.root / "curator.sqlite3")
        connection.execute(
            "ALTER TABLE cleanup_authorizations DROP COLUMN dependency_map_sha256"
        )
        connection.execute("PRAGMA user_version = 28")
        connection.commit()
        connection.close()

        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        target = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )[0]
        authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "default"
        )

        self.assertTrue(artifact_path.exists())
        self.assertTrue(target.approval_stale)
        self.assertIsNone(target.next_attempt_at)
        self.assertIsNotNone(authorization)
        assert authorization is not None
        self.assertIsNone(authorization.dependency_map_sha256)
        self.assertEqual(
            self.store.get_purge_targets(receipt.receipt_id, pending_only=True), ()
        )
