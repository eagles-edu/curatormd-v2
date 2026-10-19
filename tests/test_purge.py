"""Regression tests for review receipts and safe, retryable artifact purge."""

from __future__ import annotations

import hashlib
from io import StringIO
from pathlib import Path
import sqlite3
import tempfile
import unittest

from purge_fixtures import FlakyPurger, TestReviewAuthorizer, TestVerifier

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    Materiality,
    ConflictError,
    PurgeError,
    PurgeStatus,
    RetentionHoldKind,
    ReviewAuthorizationError,
    ReviewDecision,
    SDEQualityFeedbackLabel,
    SuccessCriterion,
)
from curatormd_v2.maintenance_cli import main as maintenance_main


class ReceiptCheckingPurger(ArtifactPurger):
    """Require a durable receipt before the test purger deletes an artifact."""

    def __init__(self, staging_root: Path, store: CuratorStore, candidate_id: str):
        super().__init__(staging_root)
        self.store = store
        self.candidate_id = candidate_id
        self.called = False

    def purge(self, artifact: ArtifactRef) -> bool:
        self.assert_receipt_exists()
        self.called = True
        return super().purge(artifact)

    def assert_receipt_exists(self) -> None:
        """Fail if canonical receipt persistence has not happened yet."""

        receipts = self.store.receipts_for_goal(
            self.store.get_sde_candidate(self.candidate_id).goal_id
        )
        receipt = next(
            (item for item in receipts if item.candidate_id == self.candidate_id),
            None,
        )
        if receipt is None or not receipt.canonical_persisted:
            raise AssertionError("purge started before durable audit receipt")


class DeleteThenCrashPurger(ArtifactPurger):
    """Simulate process loss after unlink but before its SQLite result."""

    def __init__(self, staging_root: Path):
        super().__init__(staging_root)
        self.interrupted = False

    def purge(self, artifact: ArtifactRef) -> bool:
        if not self.interrupted:
            removed = super().purge(artifact)
            self.interrupted = True
            raise RuntimeError(f"simulated process loss after deletion: {removed}")
        return super().purge(artifact)


class PurgeLifecycleTests(unittest.TestCase):
    """Verify SDE approval receipts and retryable transient artifact cleanup."""

    def setUp(self) -> None:
        self.root = Path(
            self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        )
        self.stage = self.root / "stage"
        self.stage.mkdir()
        for directory in (".git", "src", "docs", "persistence"):
            (self.root / directory).mkdir()
        (self.root / "docs" / "tasks.md").write_text("- [ ] Purge retry\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        config_path = self.root / ".curatormd-v2.toml"
        config_path.write_text(
            '''\
schema_version = 1
backend_api_version = 1
project_id = "default"

[scope]
read_paths = ["src", "docs", "persistence"]

[checklists]
tasks = "docs/tasks.md"

[evidence]
adapters = []

[staging]
root = "stage"

[persistence]
targets = ["persistence/HISTORY.md"]
'''
        )
        config_path.chmod(0o600)
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        self.goal = self.service.goal_start(
            "Record and purge reviewed development artifacts",
            (SuccessCriterion("test", "targeted test passes"),),
        )

    def tearDown(self) -> None:
        self.store.close()

    @staticmethod
    def evidence() -> EvidenceRef:
        """Return deterministic passing proof for the purge criterion."""

        return EvidenceRef(
            "test",
            "test-proof:verified",
            hashlib.sha256(b"proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )

    def candidate(self, label: str = "") -> str:
        """Create a verified change proposal and return its candidate ID."""

        change, _ = self.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            f"Added the tested behavior {label}".strip(),
        )
        verification, _ = self.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Targeted test passed",
            criterion_id="test",
            evidence=(self.evidence(),),
        )
        candidate = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "The behavior is durable and verified",
            (change.fact_id, verification.fact_id),
        )
        assert candidate is not None
        return candidate.candidate_id

    def artifact(self, name: str = "scratch.json") -> tuple[Path, ArtifactRef]:
        """Create one staged file and the reference to its exact content hash."""

        path = self.stage / name
        path.write_bytes(b"temporary evidence")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, ArtifactRef(str(path), digest)

    def persist_canonical(
        self, receipt: AuditReceipt, service: CuratorService | None = None
    ) -> AuditReceipt:
        """Record a verified test projection before allowing purge to proceed."""

        active_service = service or self.service
        return active_service.mark_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )

    def test_receipt_is_committed_before_purge_for_approve_and_reject(self) -> None:
        for decision in (ReviewDecision.APPROVED, ReviewDecision.REJECTED):
            with self.subTest(decision=decision):
                candidate_id = self.candidate(decision.value)
                artifact_path, artifact = self.artifact(f"{decision.value}.json")
                purger = ReceiptCheckingPurger(self.stage, self.store, candidate_id)
                service = CuratorService(
                    self.store, purger, TestVerifier(), TestReviewAuthorizer()
                )
                receipt = service.sde_confirm(
                    candidate_id,
                    decision,
                    (artifact,),
                    artifact_inventory_complete=True,
                )
                self.assertTrue(artifact_path.exists())
                self.assertFalse(purger.called)
                receipt = self.persist_canonical(receipt, service)
                self.assertTrue(purger.called)
                self.assertFalse(artifact_path.exists())
                self.assertEqual(receipt.decision, decision)
                self.assertEqual(receipt.reviewer_id, "test-reviewer")
                self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
                self.assertTrue(self.store.list_facts(self.goal.goal_id))

    def test_legal_hold_is_visible_and_never_selected_for_purge(self) -> None:
        candidate_id = self.candidate("legal retention")
        artifact_path, artifact = self.artifact("legal-hold.json")
        held_artifact = ArtifactRef(
            artifact.path, artifact.sha256, RetentionHoldKind.LEGAL
        )

        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (held_artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt)

        self.assertTrue(artifact_path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        receipt, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].status, ArtifactStatus.HELD)
        self.assertEqual(
            targets[0].artifact.retention_hold, RetentionHoldKind.LEGAL
        )
        self.assertEqual(targets[0].attempts, 0)
        self.assertEqual(
            targets[0].safe_recovery_action,
            "release_artifact_hold",
        )
        self.assertEqual(targets[0].hold_created_by, "test-reviewer")
        self.assertIsNotNone(targets[0].hold_created_at)

        self.service.retry_pending_purges()
        self.assertEqual(self.service.retry_due_purges(), ())
        self.assertTrue(artifact_path.exists())
        with self.assertRaisesRegex(PurgeError, "retention hold"):
            ArtifactPurger(self.stage).purge(held_artifact)
        with self.assertRaisesRegex(ConflictError, "missing or already complete"):
            self.store.begin_purge_attempt(
                receipt.receipt_id, held_artifact.path, self.service.project_id
            )
        self.store.close()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
            project_id=self.service.project_id,
        )
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.HELD)
        self.assertEqual(targets[0].attempts, 0)

        receipt = self.service.release_artifact_hold(
            receipt.receipt_id,
            held_artifact.path,
            "Retention owner confirmed release",
            authenticated_subject="test-reviewer",
        )
        self.assertFalse(artifact_path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        replay = self.service.release_artifact_hold(
            receipt.receipt_id,
            held_artifact.path,
            "Retention owner confirmed release",
            authenticated_subject="test-reviewer",
        )
        self.assertEqual(replay.purge_status, PurgeStatus.COMPLETE)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.PURGED)
        self.assertEqual(targets[0].hold_created_by, "test-reviewer")
        self.assertEqual(targets[0].hold_released_by, "test-reviewer")
        self.assertEqual(
            targets[0].hold_release_rationale, "Retention owner confirmed release"
        )
        with self.assertRaisesRegex(ConflictError, "already released differently"):
            self.service.release_artifact_hold(
                receipt.receipt_id,
                held_artifact.path,
                "different release rationale",
                authenticated_subject="test-reviewer",
            )

    def test_inventory_completion_attributes_new_hold_to_authenticated_reviewer(self) -> None:
        candidate_id = self.candidate("hold placement audit")
        first_path, first = self.artifact("first-held.json")
        second_path, second = self.artifact("second-held.json")
        original_hold = ArtifactRef(
            first.path, first.sha256, RetentionHoldKind.LEGAL
        )
        newly_held = ArtifactRef(
            second.path, second.sha256, RetentionHoldKind.OPERATIONAL
        )

        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (original_hold,),
            artifact_inventory_complete=False,
        )
        receipt = self.persist_canonical(receipt)
        receipt = self.service.artifact_inventory_complete(
            receipt.receipt_id,
            (original_hold, newly_held),
            authenticated_subject="inventory-reviewer",
        )

        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        hold_actors = {
            target.artifact.path: target.hold_created_by for target in targets
        }
        self.assertEqual(hold_actors[original_hold.path], "test-reviewer")
        self.assertEqual(hold_actors[newly_held.path], "inventory-reviewer")

    def test_sde_corrections_and_quality_feedback_survive_store_reopen(self) -> None:
        candidate_id = self.candidate("correction history")
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=True,
        )
        correction = self.service.sde_correction_record(
            "correction-1",
            candidate_id,
            "Clarify the measured outcome",
            "The original bullet overstated the observed result",
        )
        receipt_after = self.store.get_receipt(receipt.receipt_id)
        replayed = self.service.sde_correction_record(
            "correction-1",
            candidate_id,
            "Clarify the measured outcome",
            "The original bullet overstated the observed result",
        )
        detail = self.service.sde_review_detail(candidate_id)

        self.assertEqual(correction, replayed)
        self.assertEqual(detail.corrections, (correction,))
        self.assertEqual(correction.reviewer_id, "test-reviewer")
        self.assertEqual(self.store.get_receipt(receipt.receipt_id), receipt_after)
        feedback = self.service.sde_quality_feedback_record(
            "quality-feedback-1",
            candidate_id,
            SDEQualityFeedbackLabel.USEFUL,
            "The decision packet stayed tied to its selected evidence",
        )
        self.assertEqual(
            self.store.sde_quality_feedback_summary("default").total, 1
        )
        with self.assertRaisesRegex(ConflictError, "different content"):
            self.service.sde_correction_record(
                "correction-1", candidate_id, "Changed text", "Changed rationale"
            )
        self.store.close()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        self.assertEqual(
            self.store.list_sde_corrections(candidate_id, "default"), (correction,)
        )
        self.assertEqual(
            self.store.list_sde_quality_feedback(candidate_id, "default"),
            (feedback,),
        )

    def test_sde_correction_fails_closed_without_reviewer(self) -> None:
        candidate_id = self.candidate("unauthorized correction")
        self.service.sde_confirm(
            candidate_id,
            ReviewDecision.REJECTED,
            (),
            artifact_inventory_complete=True,
        )
        service = CuratorService(
            self.store, ArtifactPurger(self.stage), TestVerifier()
        )
        with self.assertRaises(ReviewAuthorizationError):
            service.sde_correction_record(
                "correction-denied",
                candidate_id,
                "Replace a fact",
                "The old fact is inaccurate",
            )

    def test_interrupted_purge_is_visible_and_retryable(self) -> None:
        candidate_id = self.candidate()
        artifact_path, artifact = self.artifact()
        flaky = FlakyPurger(self.stage)
        service = CuratorService(
            self.store, flaky, TestVerifier(), TestReviewAuthorizer()
        )
        receipt = service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt, service)
        self.assertTrue(artifact_path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].attempts, 1)
        self.assertIn("simulated interruption", targets[0].error or "")
        self.assertIsNotNone(targets[0].last_attempt_at)
        self.assertIsNotNone(targets[0].next_attempt_at)
        self.assertIsNotNone(targets[0].next_attempt_in_seconds)
        self.assertIsNotNone(targets[0].age_seconds)
        assert targets[0].age_seconds is not None
        self.assertGreaterEqual(targets[0].age_seconds, 0)
        self.assertEqual(targets[0].safe_recovery_action, "retry_pending_purges")

        retried = service.retry_pending_purges()
        self.assertEqual(len(retried), 1)
        self.assertEqual(retried[0].purge_status, PurgeStatus.COMPLETE)
        self.assertFalse(artifact_path.exists())
        _, targets = service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.PURGED)
        self.assertEqual(targets[0].attempts, 2)
        self.assertIsNone(targets[0].next_attempt_at)
        self.assertEqual(targets[0].safe_recovery_action, "none")

    def test_due_purge_retry_waits_for_backoff_and_runs_after_deadline(self) -> None:
        candidate_id = self.candidate()
        artifact_path, artifact = self.artifact()
        flaky = FlakyPurger(self.stage)
        service = CuratorService(
            self.store, flaky, TestVerifier(), TestReviewAuthorizer()
        )
        receipt = service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt, service)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertTrue(artifact_path.exists())
        self.assertEqual(service.retry_due_purges(), ())
        self.assertEqual(flaky.calls, 1)

        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE purge_targets SET next_attempt_at = ? WHERE receipt_id = ?",
                ("2000-01-01T00:00:00+00:00", receipt.receipt_id),
            )
        self.store.close()
        output = StringIO()
        exit_code = maintenance_main(
            [
                "--project-root",
                str(self.root),
                "--database",
                str(self.root / "curator.sqlite3"),
                "--batch-limit",
                "1",
                "--execute-due-purges",
            ],
            stdout=output,
            stderr=StringIO(),
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output.getvalue(),
            '{"complete":1,"pending":0,"processed":1,"project_id":"default"}\n',
        )
        self.store = CuratorStore(self.root / "curator.sqlite3")
        recovered = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(recovered.purge_status, PurgeStatus.COMPLETE)
        self.assertEqual(flaky.calls, 1)
        self.assertFalse(artifact_path.exists())

    def test_retry_recovers_crash_after_delete_before_receipt_update(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        service = CuratorService(
            self.store,
            DeleteThenCrashPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        receipt = service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        with self.assertRaisesRegex(RuntimeError, "process loss"):
            self.persist_canonical(receipt, service)
        self.assertFalse(path.exists())
        interrupted = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(interrupted.purge_status, PurgeStatus.PURGE_PENDING)
        _, interrupted_targets = service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(interrupted_targets[0].attempts, 1)
        self.assertIsNotNone(interrupted_targets[0].last_attempt_at)

        self.store.close()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        retried = service.retry_pending_purges()
        self.assertEqual(retried[0].purge_status, PurgeStatus.COMPLETE)
        _, recovered_targets = service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(recovered_targets[0].attempts, 2)
        self.assertEqual(recovered_targets[0].status, ArtifactStatus.PURGED)

    def test_sde_assessment_does_not_purge_before_human_decision(self) -> None:
        path, _artifact = self.artifact()
        candidate_id = self.candidate()
        self.assertTrue(path.exists())
        self.assertEqual(
            self.store.get_sde_candidate(candidate_id).status.value,
            "pending_review",
        )
        untrusted = CuratorService(
            self.store, ArtifactPurger(self.stage), TestVerifier()
        )
        with self.assertRaises(ReviewAuthorizationError):
            untrusted.sde_confirm(
                candidate_id,
                ReviewDecision.APPROVED,
                (),
                artifact_inventory_complete=True,
            )
        self.assertTrue(path.exists())
        self.assertEqual(self.store.receipts_for_goal(self.goal.goal_id), ())

    def test_canonical_persistence_proof_is_project_scoped_and_immutable(self) -> None:
        """A review receipt remains pending until its canonical proof is stored."""

        candidate_id = self.candidate()
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=True,
        )
        self.assertFalse(receipt.canonical_persisted)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)

        target = "persistence/HISTORY.md"
        digest = hashlib.sha256(b"canonical goal and receipt").hexdigest()
        persisted = self.service.mark_canonical_persisted(
            receipt.receipt_id, target, digest
        )
        self.assertTrue(persisted.canonical_persisted)
        self.assertEqual(persisted.purge_status, PurgeStatus.COMPLETE)
        self.assertEqual(
            self.service.mark_canonical_persisted(
                receipt.receipt_id, target, digest
            ),
            persisted,
        )
        with self.assertRaises(ConflictError):
            self.service.mark_canonical_persisted(
                receipt.receipt_id,
                target,
                hashlib.sha256(b"different projection").hexdigest(),
            )
        with self.assertRaises(LookupError):
            self.store.mark_receipt_canonical_persisted(
                receipt.receipt_id, target, digest, "another-project"
            )

    def test_legacy_receipts_migrate_to_pending_until_canonical_proof_exists(self) -> None:
        """Do not preserve a legacy green purge status without write evidence."""

        database = self.root / "legacy.sqlite3"
        connection = sqlite3.connect(database)
        connection.execute(
            """CREATE TABLE audit_receipts (
                   receipt_id TEXT PRIMARY KEY,
                   candidate_id TEXT NOT NULL UNIQUE,
                   decision TEXT NOT NULL,
                   facts_sha256 TEXT NOT NULL,
                   artifact_inventory_complete INTEGER NOT NULL,
                   purge_status TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )"""
        )
        connection.execute(
            """INSERT INTO audit_receipts VALUES
               ('legacy-receipt', 'legacy-candidate', 'approved', ?, 1,
                'complete', '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00')""",
            (hashlib.sha256(b"legacy facts").hexdigest(),),
        )
        connection.commit()
        connection.close()
        database.chmod(0o600)

        migrated = CuratorStore(database)
        self.addCleanup(migrated.close)
        receipt = migrated.get_receipt("legacy-receipt")

        self.assertFalse(receipt.canonical_persisted)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)

    def test_hash_mismatch_never_deletes_artifact_and_reports_pending(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        path.write_bytes(b"changed after approval reference")
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.REJECTED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertIn("hash does not match", targets[0].error or "")

    def test_artifact_outside_root_is_not_deleted(self) -> None:
        candidate_id = self.candidate()
        outside = self.root / "outside.json"
        outside.write_text("private", encoding="utf-8")
        artifact = ArtifactRef(
            str(outside), hashlib.sha256(b"private").hexdigest()
        )
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.REJECTED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(outside.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertIn("outside", targets[0].error or "")

    def test_directories_and_symlinks_are_never_purged(self) -> None:
        nested = self.stage / "nested"
        nested.mkdir()
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(str(nested), hashlib.sha256(b"").hexdigest())
            )
        target = self.stage / "target.txt"
        target.write_text("target", encoding="utf-8")
        link = self.stage / "link.txt"
        link.symlink_to(target)
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(str(link), hashlib.sha256(b"target").hexdigest())
            )
        self.assertTrue(target.exists())

        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        outside_file = outside_dir / "keep.txt"
        outside_file.write_text("keep", encoding="utf-8")
        directory_link = self.stage / "directory-link"
        directory_link.symlink_to(outside_dir, target_is_directory=True)
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(
                    str(directory_link / outside_file.name),
                    hashlib.sha256(b"keep").hexdigest(),
                )
            )
        self.assertTrue(outside_file.exists())

    def test_missing_artifact_retry_is_idempotent(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        path.unlink()
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)

    def test_incomplete_empty_inventory_stays_pending_until_explicitly_complete(self) -> None:
        candidate_id = self.candidate()
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=False,
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertFalse(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts()[0].receipt_id, receipt.receipt_id)
        receipt = self.service.artifact_inventory_complete(receipt.receipt_id, ())
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertTrue(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts(), ())

    def test_partial_inventory_blocks_all_deletion_until_manifest_is_complete(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=False,
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(path.exists())
        _, target_status = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(
            target_status[0].safe_recovery_action,
            "artifact_inventory_complete",
        )
        pending = self.service.retry_pending_purges()
        self.assertEqual(pending[0].purge_status, PurgeStatus.PURGE_PENDING)
        self.assertTrue(path.exists())
        receipt = self.service.artifact_inventory_complete(
            receipt.receipt_id, (artifact,)
        )
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertFalse(path.exists())

    def test_replayed_review_cannot_change_approved_artifact_list(self) -> None:
        candidate_id = self.candidate()
        _, original = self.artifact("original.json")
        self.service.sde_confirm(
            candidate_id,
            ReviewDecision.APPROVED,
            (original,),
            artifact_inventory_complete=True,
        )
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                candidate_id,
                ReviewDecision.REJECTED,
                (original,),
                artifact_inventory_complete=True,
            )
        _, replacement = self.artifact("replacement.json")
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                candidate_id,
                ReviewDecision.APPROVED,
                (replacement,),
                artifact_inventory_complete=True,
            )

    def test_rejected_review_decision_cannot_be_changed_to_approved(self) -> None:
        candidate_id = self.candidate("immutable rejection")
        _, artifact = self.artifact("rejected.json")
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.REJECTED,
            (artifact,),
            artifact_inventory_complete=True,
        )

        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                candidate_id,
                ReviewDecision.APPROVED,
                (artifact,),
                artifact_inventory_complete=True,
            )

        stored = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(stored.decision, ReviewDecision.REJECTED)

    def test_receipt_and_facts_survive_store_reopen(self) -> None:
        candidate_id = self.candidate()
        _, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            candidate_id,
            ReviewDecision.REJECTED,
            (artifact,),
            artifact_inventory_complete=True,
        )
        receipt = self.persist_canonical(receipt)
        database = self.root / "curator.sqlite3"
        self.store.close()
        self.store = CuratorStore(database)
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        reloaded = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(reloaded.decision, ReviewDecision.REJECTED)
        self.assertEqual(reloaded.purge_status, PurgeStatus.COMPLETE)
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 2)


if __name__ == "__main__":
    unittest.main()
