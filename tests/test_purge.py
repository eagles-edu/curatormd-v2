"""Regression tests for review receipts and safe, retryable artifact purge."""

from __future__ import annotations

import hashlib
import json
from io import StringIO
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

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
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewAuthorizationError,
    ReviewDecision,
    SDEConfirmationRequest,
    SDEQualityFeedbackLabel,
    SuccessCriterion,
)
from curatormd_v2.maintenance_cli import main as maintenance_main
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.store import (
    NotFoundError,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
)
from curatormd_v2.service import SDEAssessmentRequest


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


# ArtifactPurger test double intentionally overrides only the required `purge`.
class DeleteThenCrashPurger(ArtifactPurger):  # pylint: disable=too-few-public-methods
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
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The behavior is durable and verified",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        return candidate.candidate_id

    def artifact(self, name: str = "scratch.json") -> tuple[Path, ArtifactRef]:
        """Create one staged file and the reference to its exact content hash."""

        path = self.stage / name
        path.write_bytes(b"temporary evidence")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = path.stat()
        return path, ArtifactRef(
            str(path), digest, device_id=metadata.st_dev, inode_id=metadata.st_ino,
            occurrence_id=uuid4().hex,
        )

    def test_same_content_replacement_after_review_is_not_unlinked(self) -> None:
        """A reviewed hash cannot authorize a different file occurrence."""

        candidate_id = self.candidate("same-content replacement")
        path, artifact = self.artifact("same-content-replacement.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        replacement = path.with_name("replacement.tmp")
        replacement.write_bytes(b"temporary evidence")
        self.assertNotEqual(
            (replacement.stat().st_dev, replacement.stat().st_ino),
            (artifact.device_id, artifact.inode_id),
        )
        path.unlink()
        replacement.rename(path)

        result = self.persist_canonical(receipt)

        self.assertTrue(path.exists())
        self.assertEqual(result.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].error, "path_changed")
        self.assertTrue(targets[0].approval_stale)
        self.assertIsNone(targets[0].next_attempt_at)
        self.assertEqual(
            self.store.get_purge_targets(receipt.receipt_id, pending_only=True), ()
        )

        self.service.retry_pending_purges()

        self.assertTrue(path.exists())
        persisted_target = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )[0]
        self.assertEqual(persisted_target.attempts, 1)
        self.assertTrue(persisted_target.approval_stale)

        self.store.close()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        self.assertEqual(
            self.store.due_pending_purge_receipts("default"), ()
        )
        self.service.retry_pending_purges()
        restarted_target = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )[0]
        self.assertEqual(restarted_target.attempts, 1)
        self.assertTrue(restarted_target.approval_stale)
        self.assertTrue(path.exists())

    def test_partial_purge_replacement_stays_stale_after_restart(self) -> None:
        """A partial receipt cannot purge a replacement after a process restart."""

        candidate_id = self.candidate("partial purge replacement")
        first_path, first = self.artifact("a-first.json")
        second_path, second = self.artifact("b-second.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(first, second),
                artifact_inventory_complete=True,
            )
        )
        original_purge = self.service.purger.purge

        def replace_second_then_purge(artifact: ArtifactRef) -> bool:
            if artifact.path == second.path:
                replacement = second_path.with_name("b-replacement.tmp")
                replacement.write_bytes(b"temporary evidence")
                second_path.unlink()
                replacement.rename(second_path)
            return original_purge(artifact)

        with patch.object(
            self.service.purger, "purge", side_effect=replace_second_then_purge
        ):
            result = self.persist_canonical(receipt)

        self.assertFalse(first_path.exists())
        self.assertTrue(second_path.exists())
        self.assertEqual(result.purge_status, PurgeStatus.PURGE_PENDING)
        target_records = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )
        self.assertEqual(target_records[0].status, ArtifactStatus.PURGED)
        self.assertEqual(target_records[1].status, ArtifactStatus.FAILED)
        self.assertEqual(target_records[1].error, "path_changed")
        self.assertTrue(target_records[1].approval_stale)

        self.store.close()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        restarted_receipt = self.service.retry_pending_purges()[0]
        restarted_targets = self.store.get_purge_target_records(
            receipt.receipt_id, "default"
        )

        self.assertEqual(restarted_receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertFalse(first_path.exists())
        self.assertTrue(second_path.exists())
        self.assertEqual(restarted_targets[0].status, ArtifactStatus.PURGED)
        self.assertEqual(restarted_targets[1].attempts, 1)
        self.assertEqual(restarted_targets[1].error, "path_changed")
        self.assertTrue(restarted_targets[1].approval_stale)

    def persist_canonical(
        self, receipt: AuditReceipt, service: CuratorService | None = None
    ) -> AuditReceipt:
        """Record a verified test projection before allowing purge to proceed."""

        active_service = service or self.service
        active_service.mark_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )
        if not receipt.artifact_inventory_complete:
            return active_service.store.get_receipt(receipt.receipt_id)
        with active_service.store.transaction() as connection:
            for artifact in receipt.artifacts:
                action = (
                    ReacquisitionAction.RETAIN_UNDER_HOLD
                    if artifact.retention_hold is not None
                    else ReacquisitionAction.NOT_REQUIRED
                )
                connection.execute(
                    "UPDATE purge_targets SET reacquisition_action = ? "
                    "WHERE receipt_id = ? AND path = ?",
                    (action.value, receipt.receipt_id, artifact.path),
                )
        manifest = json.dumps(
            [
                (item.path, item.sha256, item.occurrence_id)
                for item in sorted(receipt.artifacts, key=lambda item: item.path)
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        _authorization, _pending_receipt = active_service.authorize_artifact_cleanup(
            receipt.receipt_id,
            hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
            "a" * 64,
        )
        return active_service.mark_cleanup_authorization_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )

    def test_sde_disposition_and_canonical_write_do_not_authorize_cleanup(self) -> None:
        candidate_id = self.candidate("separate cleanup authorization")
        artifact_path, artifact = self.artifact("separate-approval.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        self.service.mark_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )
        self.assertTrue(artifact_path.exists())
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
        self.assertIsNone(
            self.store.cleanup_authorization(receipt.receipt_id, "default")
        )
        self.service.retry_pending_purges()
        self.service.retry_due_purges()
        self.assertTrue(artifact_path.exists())
        manifest = json.dumps(
            [(artifact.path, artifact.sha256, artifact.occurrence_id)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
        with self.assertRaises(ConflictError):
            self.service.authorize_artifact_cleanup(
                receipt.receipt_id, "0" * 64, "b" * 64
            )
        self.assertTrue(artifact_path.exists())
        authorization, _pending_receipt = self.service.authorize_artifact_cleanup(
            receipt.receipt_id, manifest_sha256, "b" * 64
        )
        self.assertEqual(authorization.manifest_sha256, manifest_sha256)
        self.assertEqual(authorization.dependency_map_sha256, "b" * 64)
        self.assertEqual(authorization.reviewer_id, "test-reviewer")
        usage = self.store.project_storage_usage("default")
        other_usage = self.store.project_storage_usage("other-project")
        self.assertEqual(usage.cleanup_authorization_count, 1)
        self.assertGreater(usage.cleanup_authorization_record_bytes, 0)
        self.assertGreaterEqual(
            usage.logical_record_bytes, usage.cleanup_authorization_record_bytes
        )
        self.assertEqual(other_usage.cleanup_authorization_count, 0)
        self.assertEqual(other_usage.cleanup_authorization_record_bytes, 0)
        purged = self.service.mark_cleanup_authorization_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(b"cleanup projection").hexdigest(),
        )
        self.assertFalse(artifact_path.exists())
        self.assertEqual(purged.purge_status, PurgeStatus.COMPLETE)

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
                    SDEConfirmationRequest(
                        candidate_id=candidate_id,
                        decision=decision,
                        artifacts=(artifact,),
                        artifact_inventory_complete=True,
                    )
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
            artifact.path,
            artifact.sha256,
            RetentionHoldKind.LEGAL,
            artifact.device_id,
            artifact.inode_id,
            artifact.occurrence_id,
        )

        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(held_artifact,),
                artifact_inventory_complete=True,
            )
        )
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE purge_targets SET reacquisition_action = ? "
                "WHERE receipt_id = ? AND path = ?",
                (
                    ReacquisitionAction.RETAIN_UNDER_HOLD.value,
                    receipt.receipt_id,
                    held_artifact.path,
                ),
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
            first.path, first.sha256, RetentionHoldKind.LEGAL,
            first.device_id, first.inode_id, first.occurrence_id,
        )
        newly_held = ArtifactRef(
            second.path, second.sha256, RetentionHoldKind.OPERATIONAL,
            second.device_id, second.inode_id, second.occurrence_id,
        )

        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(original_hold,),
                artifact_inventory_complete=False,
            )
        )
        receipt = self.persist_canonical(receipt)
        receipt = self.service.artifact_inventory_complete(
            receipt.receipt_id,
            (original_hold, newly_held),
            authenticated_subject="inventory-reviewer",
        )
        receipt = self.persist_canonical(receipt)

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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=True,
            )
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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(),
                artifact_inventory_complete=True,
            )
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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt, service)
        self.assertTrue(artifact_path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].attempts, 1)
        self.assertEqual(targets[0].error, "filesystem_error")
        self.assertNotIn("SENSITIVE_PURGE_PATH_SENTINEL", repr(targets[0]))
        with self.assertRaisesRegex(ValueError, "content-free error code"):
            self.store.record_purge_result(
                receipt.receipt_id,
                str(artifact_path),
                ArtifactStatus.FAILED,
                "SENSITIVE_PURGE_PATH_SENTINEL",
                self.service.project_id,
            )
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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
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
        config = ProjectConfig.load(self.root)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config, "Register the local maintenance retry fixture"
            ),
            "test-admin",
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
            '{"complete":1,"expiry_complete":0,"expiry_pending":0,'
            '"expiry_processed":0,"pending":0,"processed":1,'
            '"project_id":"default"}\n',
        )
        self.store = CuratorStore(self.root / "curator.sqlite3")
        recovered = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(recovered.purge_status, PurgeStatus.COMPLETE)
        self.assertEqual(flaky.calls, 1)
        self.assertFalse(artifact_path.exists())

    def test_suspended_project_blocks_due_purge_retry(self) -> None:
        candidate_id = self.candidate("suspension boundary")
        artifact_path, artifact = self.artifact()
        flaky = FlakyPurger(self.stage)
        service = CuratorService(
            self.store, flaky, TestVerifier(), TestReviewAuthorizer()
        )
        receipt = service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt, service)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertTrue(artifact_path.exists())
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE purge_targets SET next_attempt_at = ? WHERE receipt_id = ?",
                ("2000-01-01T00:00:00+00:00", receipt.receipt_id),
            )

        config = ProjectConfig.load(self.root)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config, "Register the local maintenance suspension fixture"
            ),
            "test-admin",
        )
        self.store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Verify scheduled cleanup respects suspension",
                expected_revision=1,
                transition_id="suspend-maintenance-test",
            ),
            "test-admin",
        )
        self.store.close()

        output = StringIO()
        errors = StringIO()
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
            stderr=errors,
        )

        self.assertEqual(exit_code, 2)
        self.assertIn("maintenance failed", errors.getvalue())
        self.assertEqual(output.getvalue(), "")
        self.assertTrue(artifact_path.exists())
        self.assertEqual(flaky.calls, 1)
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.assertEqual(
            self.store.get_receipt(receipt.receipt_id).purge_status,
            PurgeStatus.PURGE_PENDING,
        )
        self.assertEqual(
            self.store.get_project_registration(config.project_id).status,
            "suspended",
        )

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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
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
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(),
                    artifact_inventory_complete=True,
                )
            )
        self.assertTrue(path.exists())
        self.assertEqual(self.store.receipts_for_goal(self.goal.goal_id), ())

    def test_canonical_persistence_proof_is_project_scoped_and_immutable(self) -> None:
        """A review receipt remains pending until its canonical proof is stored."""

        candidate_id = self.candidate()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=True,
            )
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

    def test_hash_mismatch_never_deletes_artifact_and_reports_pending(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        path.write_bytes(b"changed after approval reference")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].error, "hash_mismatch")

    def test_replacement_after_hash_verification_is_not_unlinked(self) -> None:
        """Leave an unapproved in-root replacement intact and report pending."""

        candidate_id = self.candidate("path replacement race")
        path, artifact = self.artifact("replacement-race.json")
        original_stat = path.stat()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        real_fstat = os.fstat
        matching_fstats = 0

        def replace_after_hash(file_descriptor: int) -> os.stat_result:
            nonlocal matching_fstats
            metadata = real_fstat(file_descriptor)
            if (metadata.st_dev, metadata.st_ino) == (
                original_stat.st_dev,
                original_stat.st_ino,
            ):
                matching_fstats += 1
                if matching_fstats == 2:
                    path.unlink()
                    path.write_bytes(b"unapproved replacement")
            return metadata

        with patch("curatormd_v2.purge.os.fstat", side_effect=replace_after_hash):
            persisted = self.persist_canonical(receipt)

        self.assertEqual(matching_fstats, 2)
        self.assertEqual(path.read_bytes(), b"unapproved replacement")
        self.assertEqual(persisted.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].error, "path_changed")

    def test_artifact_outside_root_is_not_deleted(self) -> None:
        candidate_id = self.candidate()
        outside = self.root / "outside.json"
        outside.write_text("private", encoding="utf-8")
        artifact = ArtifactRef(
            str(outside), hashlib.sha256(b"private").hexdigest(),
            occurrence_id=uuid4().hex,
            reacquisition_action=ReacquisitionAction.REACQUIRE_FROM_SOURCE,
        )
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(outside.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].error, "outside_staging_root")

    def test_purge_errors_do_not_retain_private_paths(self) -> None:
        """Path confinement and filesystem failures expose no chained path."""

        private_path = "/srv/private/customer/staged.json"
        outside = ArtifactRef(private_path, hashlib.sha256(b"secret").hexdigest())
        with self.assertRaisesRegex(
            PurgeError, "artifact is outside the configured staging root"
        ) as raised:
            ArtifactPurger(self.stage).purge(outside)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

        in_scope = self.stage / "inside.json"
        in_scope.write_text("secret", encoding="utf-8")
        artifact = ArtifactRef(
            str(in_scope), hashlib.sha256(b"secret").hexdigest()
        )
        with patch(
            "curatormd_v2.purge.os.fstat",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            with self.assertRaisesRegex(
                PurgeError, "cannot safely inspect or remove artifact"
            ) as raised:
                ArtifactPurger(self.stage).purge(artifact)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_store_missing_purge_target_errors_do_not_echo_path(self) -> None:
        """Direct store failures do not retain caller-supplied artifact paths."""

        candidate_id = self.candidate("missing purge target")
        _, artifact = self.artifact("existing.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        private_path = "/srv/private/customer/not-in-this-receipt.json"

        with self.assertRaises(NotFoundError) as raised:
            self.store.release_artifact_hold(
                receipt.receipt_id,
                private_path,
                self.service.project_id,
                "test-reviewer",
                "Owner requested a hold release",
            )
        self.assertNotIn(private_path, str(raised.exception))

        with self.assertRaises(NotFoundError) as raised:
            self.store.record_purge_result(
                receipt.receipt_id,
                private_path,
                ArtifactStatus.FAILED,
                "filesystem_error",
                self.service.project_id,
            )
        self.assertNotIn(private_path, str(raised.exception))

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
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)

    def test_incomplete_empty_inventory_stays_pending_until_explicitly_complete(self) -> None:
        candidate_id = self.candidate()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=False,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertFalse(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts()[0].receipt_id, receipt.receipt_id)
        receipt = self.service.artifact_inventory_complete(receipt.receipt_id, ())
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertTrue(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts(), ())

    def test_partial_inventory_blocks_all_deletion_until_manifest_is_complete(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=False,
            )
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
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertFalse(path.exists())

    def test_replayed_review_cannot_change_approved_artifact_list(self) -> None:
        candidate_id = self.candidate()
        _, original = self.artifact("original.json")
        self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(original,),
                artifact_inventory_complete=True,
            )
        )
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.REJECTED,
                    artifacts=(original,),
                    artifact_inventory_complete=True,
                )
            )
        _, replacement = self.artifact("replacement.json")
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(replacement,),
                    artifact_inventory_complete=True,
                )
            )

    def test_rejected_review_decision_cannot_be_changed_to_approved(self) -> None:
        candidate_id = self.candidate("immutable rejection")
        _, artifact = self.artifact("rejected.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )

        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(artifact,),
                    artifact_inventory_complete=True,
                )
            )

        stored = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(stored.decision, ReviewDecision.REJECTED)

    def test_receipt_and_facts_survive_store_reopen(self) -> None:
        candidate_id = self.candidate()
        _, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
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
