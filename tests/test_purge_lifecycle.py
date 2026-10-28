"""Exercise purge lifecycle behavior."""
# pylint: disable=duplicate-code
# Parallel tests repeat setup to exercise distinct failure conditions.

from __future__ import annotations

import hashlib
import json
import sqlite3
from io import StringIO
from unittest.mock import patch

from purge_fixtures import FlakyPurger, TestReviewAuthorizer, TestVerifier
from purge_test_support import (
    ReceiptCheckingPurger,
    DeleteThenCrashPurger,
    PurgeTestSupport,
)

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    ArtifactStatus,
    ConflictError,
    CuratorService,
    CuratorStore,
    PurgeError,
    PurgeOutcome,
    PurgeStatus,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewAuthorizationError,
    ReviewDecision,
    SDEConfirmationRequest,
    SDEQualityFeedbackLabel,
)
from curatormd_v2.maintenance_cli import main as maintenance_main
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.store import ProjectRegistrationRequest, ProjectStatusChangeRequest
from curatormd_v2.store_requests import PurgeTargetResult


class PurgeLifecycleTests(PurgeTestSupport):
    """Exercise purge lifecycle behavior."""

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
        self.assertEqual(target_records[0].outcome, PurgeOutcome.DELETED)
        self.assertEqual(target_records[1].status, ArtifactStatus.FAILED)
        self.assertEqual(target_records[1].outcome, PurgeOutcome.CHANGED)
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
        self.assertEqual(restarted_targets[0].outcome, PurgeOutcome.DELETED)
        self.assertEqual(restarted_targets[1].attempts, 1)
        self.assertEqual(restarted_targets[1].error, "path_changed")
        self.assertTrue(restarted_targets[1].approval_stale)


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
        self.assertEqual(targets[0].outcome, PurgeOutcome.HELD)
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
        self.assertEqual(targets[0].outcome, PurgeOutcome.HELD)
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
        self.assertEqual(targets[0].outcome, PurgeOutcome.DELETED)
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
        self.assertEqual(targets[0].outcome, PurgeOutcome.FAILED)
        self.assertEqual(targets[0].attempts, 1)
        self.assertEqual(targets[0].error, "filesystem_error")
        self.assertNotIn("SENSITIVE_PURGE_PATH_SENTINEL", repr(targets[0]))
        with self.assertRaisesRegex(ValueError, "content-free error code"):
            self.store.record_purge_result(
                receipt.receipt_id,
                str(artifact_path),
                PurgeTargetResult(
                    ArtifactStatus.FAILED,
                    "SENSITIVE_PURGE_PATH_SENTINEL",
                ),
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
            '{"backup_status":"verified","complete":1,"expiry_complete":0,"expiry_pending":0,'
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
        self.assertEqual(
            recovered_targets[0].outcome, PurgeOutcome.ALREADY_ABSENT
        )


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
