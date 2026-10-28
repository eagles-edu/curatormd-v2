"""Repository-scoped canonical Markdown projection tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
import io
from dataclasses import replace
from pathlib import Path
import hashlib
import subprocess
import sys
from threading import Event
import unittest
from typing import BinaryIO, Self, cast
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from purge_fixtures import TestReviewAuthorizer
from markdown_persistence_fixtures import MarkdownPersistenceFixture

from curatormd_v2 import (
    AuditReceipt,
    ArtifactPurger,
    ArtifactRef,
    ChecklistGoalStartRequest,
    CuratorStore,
    EventEnvelope,
    EvidenceOutcome,
    EvidenceAttestation,
    EvidenceRef,
    EvidenceVerificationContext,
    FactRecorded,
    FactKind,
    MarkdownPersistenceAdapter,
    MarkdownPersistenceError,
    MarkdownReconciliationStatus,
    Materiality,
    ProjectPlugin,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    ReacquisitionAction,
    ReviewDecision,
    SDEConfirmationRequest,
    SuccessCriterion,
    backup_database,
    restore_database,
)
from curatormd_v2.project_config import ProjectConfig, ProjectConfigError
from curatormd_v2.service import SDEAssessmentRequest
from curatormd_v2.store import ConflictError


class TestVerifier:  # pylint: disable=too-few-public-methods
    """Trust the explicit test evidence locator used by this fixture."""

    def __init__(self, store: CuratorStore) -> None:
        self.store = store

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the explicit locator configured for this test."""

        if self.store.transaction_active:
            raise AssertionError(
                "Markdown evidence verification held a SQLite transaction"
            )
        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:passed"
            else None
        )


class PersistedReceiptPurger(ArtifactPurger):  # pylint: disable=too-few-public-methods
    """Require the actual configured Markdown block to exist before unlink."""

    def __init__(self, root: Path, target: Path, receipt_id: str) -> None:
        super().__init__(root)
        self.target = target
        self.receipt_id = receipt_id
        self.called = False
        self.persisted_digest: str | None = None

    def purge(self, artifact: ArtifactRef) -> bool:
        content = self.target.read_text()
        if self.receipt_id not in content:
            raise AssertionError("artifact purge ran before Markdown receipt write")
        self.persisted_digest = hashlib.sha256(self.target.read_bytes()).hexdigest()
        self.called = True
        return super().purge(artifact)


class MarkdownPersistenceTests(MarkdownPersistenceFixture):
    """Verify explicit, bounded, idempotent project Markdown writes."""


    def test_suspend_during_evidence_check_prevents_projection_write(self) -> None:
        """Recheck the captured project revision after external verification."""

        verification_started = Event()
        allow_verification = Event()

        class BlockingVerifier:  # pylint: disable=too-few-public-methods
            """Pause one external attestation between snapshot and write fence."""

            def __init__(self, store: CuratorStore) -> None:
                self.store = store
                self.block = False

            def attest(
                self,
                evidence: EvidenceRef,
                context: EvidenceVerificationContext,
            ) -> EvidenceAttestation:
                """Block at the resolver boundary and attest after release."""

                if self.store.transaction_active:
                    raise AssertionError("evidence verification ran in a transaction")
                if self.block and not verification_started.is_set():
                    verification_started.set()
                    if not allow_verification.wait(timeout=10):
                        raise AssertionError("projection verification was not released")
                return attest_test_evidence(evidence, context)

        verifier = BlockingVerifier(self.store)
        self.plugin = ProjectPlugin.bind(self.config, self.store, verifier)
        self.plugin.goal_activate(
            self.goal.goal_id, "Enable the persistence race regression", 1
        )
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:passed",
            hashlib.sha256(b"projection proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Projection evidence is valid",
            criterion_id="write",
            evidence=(evidence,),
        )
        original = self.target.read_bytes()
        verifier.block = True
        suspend_store = CuratorStore(self.store.database)
        self.addCleanup(suspend_store.close)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self.plugin.persist_goal, self.goal.goal_id, self.target
            )
            try:
                self.assertTrue(
                    verification_started.wait(timeout=10),
                    "projection did not reach external evidence verification",
                )
                suspend_store.set_project_status(
                    ProjectStatusChangeRequest(
                        project_id=self.config.project_id,
                        status="suspended",
                        rationale="Suspend between evidence verification and write",
                        expected_revision=1,
                        transition_id="suspend-during-projection-1",
                    ),
                    "test-admin",
                )
            finally:
                allow_verification.set()
            with self.assertRaises(ConflictError):
                future.result(timeout=10)

        self.assertEqual(self.target.read_bytes(), original)

    def test_projection_preserves_unrelated_content_and_is_idempotent(self) -> None:
        """Replace one goal block and retain all unrelated project Markdown."""

        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store)
        )
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        event = EventEnvelope(
            "event-markdown-projection",
            "consumer-a",
            FactRecorded(
                self.goal.goal_id,
                "fact-markdown-projection",
                FactKind.CHANGE,
                "Added deterministic Markdown projection",
            ),
        )
        self.plugin.service.process_event(event)
        self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Canonical projection regression test passed",
            criterion_id="write",
            evidence=(
                EvidenceRef(
                    "unit-test",
                    "test-proof:passed",
                    hashlib.sha256(b"criterion-proof").hexdigest(),
                    EvidenceOutcome.PASSED,
                ),
            ),
        )
        first = self.plugin.persist_goal(self.goal.goal_id, "persistence/HISTORY.md")
        content = self.target.read_text()

        self.assertTrue(first.changed)
        self.assertIn("# Existing project history", content)
        self.assertIn("Keep this text.", content)
        self.assertIn("- Change: Added deterministic Markdown projection", content)
        self.assertIn(
            "source event: event\\-markdown\\-projection", content
        )
        self.assertEqual(content.count("- Facts:"), 1)
        self.assertIn("- Checklist: `tasks`", content)
        self.assertIn("- Lifecycle revision: `2`", content)
        self.assertIn(
            "- Checklist item (captured verbatim): \\- \\[ \\] Implement adapter",
            content,
        )
        self.assertIn("- Checklist source revision: `sha256:", content)
        self.assertIn("`verified` — A scoped goal is written as compact bullets", content)
        self.assertEqual(content.count(":start -->"), 1)
        self.assertEqual(content.count(":end -->"), 1)

        second = self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertFalse(second.changed)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(content, self.target.read_text())

        self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.INTENT, "Keep only concise typed bullets"
        )
        third = self.plugin.persist_goal(self.goal.goal_id, self.target)
        updated = self.target.read_text()
        self.assertTrue(third.changed)
        self.assertEqual(updated.count(":start -->"), 1)
        self.assertIn("- Intent: Keep only concise typed bullets", updated)
        self.assertIn("Keep this text.", updated)

    def test_exact_legacy_projection_is_upgraded_with_integrity_marker(self) -> None:
        """Upgrade only an unchanged legacy block whose content matches SQLite."""

        current = MarkdownPersistenceAdapter(
            self.config, self.store, self.target
        ).render_goal(self.goal.goal_id)
        legacy = "\n".join(
            line
            for line in current.splitlines()
            if "curatormd-v2:block-sha256:" not in line
        )
        self.target.write_text(
            "# Existing project history\n\nKeep this text.\n\n"
            + legacy
            + "\n"
        )

        reconciled = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(reconciled.status, MarkdownReconciliationStatus.SYNCED)
        projection = self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertTrue(projection.changed)
        self.assertIn("curatormd-v2:block-sha256:", self.target.read_text())
        self.assertEqual(
            self.plugin.reconcile_goal(self.goal.goal_id, self.target).status,
            MarkdownReconciliationStatus.SYNCED,
        )

    def test_stale_legacy_projection_is_not_replaced_without_reconciliation(self) -> None:
        """Preserve unverifiable legacy blocks after the ledger has advanced."""

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        sealed = self.target.read_text()
        legacy = "\n".join(
            line
            for line in sealed.splitlines()
            if "curatormd-v2:block-sha256:" not in line
        )
        self.target.write_text(legacy + "\n")
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Keep the ledger update safe"
        )
        before = self.target.read_text()

        with self.assertRaisesRegex(MarkdownPersistenceError, "legacy goal block"):
            self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertEqual(self.target.read_text(), before)

    def test_read_only_reconciliation_reports_missing_synced_and_divergent(self) -> None:
        """Compare the block with SQLite without repairing consumer Markdown."""

        initial_content = self.target.read_text()
        missing = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(missing.status, MarkdownReconciliationStatus.MISSING)
        self.assertIsNone(missing.actual_sha256)
        self.assertEqual(self.target.read_text(), initial_content)

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        synced = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(synced.status, MarkdownReconciliationStatus.SYNCED)
        self.assertEqual(synced.expected_sha256, synced.actual_sha256)

        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Commit one ledger-first update"
        )
        stale_projection = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(stale_projection.status, MarkdownReconciliationStatus.DIVERGENT)
        self.plugin.persist_goal(self.goal.goal_id, self.target)
        repaired_projection = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(repaired_projection.status, MarkdownReconciliationStatus.SYNCED)
        self.assertIn("Commit one ledger", self.target.read_text())
        original = self.target.read_text()
        self.target.write_text(original.replace("Implement the canonical", "Edited the canonical"))
        edited = self.target.read_text()
        divergent = self.plugin.reconcile_goal(self.goal.goal_id, self.target)

        self.assertEqual(divergent.status, MarkdownReconciliationStatus.MALFORMED)
        with self.assertRaisesRegex(MarkdownPersistenceError, "checksum mismatch"):
            self.plugin.persist_goal(self.goal.goal_id, self.target)
        self.assertEqual(self.target.read_text(), edited)

    def test_projection_recovers_ledger_first_update_after_backup_restore(self) -> None:
        """Rebuild a missing canonical block from durable ledger state."""

        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            "The ledger update survived before Markdown projection",
        )
        source_database = Path(self.temporary) / "global.sqlite3"
        backup_path = Path(self.temporary) / "review-recovery.sqlite3"
        restored_path = Path(self.temporary) / "review-recovered.sqlite3"
        backup_database(source_database, backup_path)
        restore_database(backup_path, restored_path)
        self.store.close()
        self.store = CuratorStore(restored_path)
        self.addCleanup(self.store.close)
        self.plugin = ProjectPlugin.bind(self.config, self.store)

        before_projection = self.plugin.reconcile_goal(self.goal.goal_id, self.target)
        self.assertEqual(before_projection.status, MarkdownReconciliationStatus.MISSING)
        result = self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertEqual(
            self.plugin.reconcile_goal(self.goal.goal_id, self.target).status,
            MarkdownReconciliationStatus.SYNCED,
        )
        self.assertIn(
            "The ledger update survived before Markdown projection",
            self.target.read_text(),
        )
        self.assertEqual(result.target, self.target)




    def test_supersession_link_is_retained_in_canonical_goal_block(self) -> None:
        replacement = self.plugin.service.goal_start(
            "Revised canonical projection",
            (SuccessCriterion("ready", "Revised work is ready"),),
        )
        self.plugin.service.goal_supersede(
            self.goal.goal_id, replacement.goal_id, "Use revised acceptance"
        )

        block = MarkdownPersistenceAdapter(
            self.config, self.store, self.target
        ).render_goal(self.goal.goal_id)

        self.assertIn(f"Superseded by goal: `{replacement.goal_id}`", block)
        self.assertIn("Superseded by goal", block)

    def _review_artifact_without_canonical_persistence(
        self,
    ) -> tuple[Path, AuditReceipt]:
        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store), TestReviewAuthorizer()
        )
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        change, _ = self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Implemented and tested change"
        )
        verification, _ = self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Unit check passed",
            criterion_id="write",
            evidence=(
                EvidenceRef(
                    "unit-test",
                    "test-proof:passed",
                    hashlib.sha256(b"proof").hexdigest(),
                    EvidenceOutcome.PASSED,
                ),
            ),
        )
        candidate = self.plugin.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable implementation with direct test evidence",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        artifact = self.plugin.stage_artifact(
            self.goal.goal_id,
            "scratch",
            "markdown-persistence-test",
            io.BytesIO(b"temporary test artifact"),
        )
        review_packet = self.plugin.sde_review_packet(
            candidate.candidate_id,
            (replace(artifact, reacquisition_action=ReacquisitionAction.REACQUIRE_FROM_SOURCE),),
        )
        artifact = review_packet.review_artifacts[0]
        receipt = self.plugin.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate.candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
                dependency_map_sha256=review_packet.dependency_map_sha256,
            )
        )
        return Path(artifact.path), receipt

    def test_plugin_persists_review_receipt_before_releasing_purge_gate(self) -> None:
        """Only a written canonical facts/receipt block may trigger deletion."""

        artifact_path, receipt = self._review_artifact_without_canonical_persistence()
        self.assertTrue(artifact_path.exists())
        self.assertFalse(receipt.canonical_persisted)
        purger = PersistedReceiptPurger(
            self.root / ".curatormd-v2" / "staging", self.target, receipt.receipt_id
        )
        self.plugin.service.purger = purger
        with self.assertRaises(ProjectConfigError):
            self.plugin.persist_goal(self.goal.goal_id, "docs/not-configured.md")
        self.assertTrue(artifact_path.exists())
        self.assertFalse(purger.called)

        source_database = Path(self.temporary) / "global.sqlite3"
        backup_path = Path(self.temporary) / "review-receipt-backup.sqlite3"
        restored_path = Path(self.temporary) / "review-receipt-restored.sqlite3"
        backup_database(source_database, backup_path)
        restore_database(backup_path, restored_path)
        self.store.close()
        self.store = CuratorStore(restored_path)
        self.addCleanup(self.store.close)
        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store), TestReviewAuthorizer()
        )
        self.plugin.service.purger = purger
        reopened_receipt = self.store.get_receipt(
            receipt.receipt_id, self.config.project_id
        )
        self.assertFalse(reopened_receipt.canonical_persisted)
        self.assertTrue(artifact_path.exists())
        self.assertFalse(purger.called)

        projection = self.plugin.persist_goal(self.goal.goal_id, self.target)

        final_receipt = self.store.get_receipt(receipt.receipt_id, "consumer-a")
        self.assertTrue(purger.called)
        self.assertFalse(artifact_path.exists())
        self.assertTrue(final_receipt.canonical_persisted)
        self.assertEqual(final_receipt.canonical_target, "persistence/HISTORY.md")
        self.assertEqual(final_receipt.canonical_sha256, purger.persisted_digest)
        original_store = CuratorStore(source_database)
        try:
            original_receipt = original_store.get_receipt(
                receipt.receipt_id, self.config.project_id
            )
            self.assertFalse(original_receipt.canonical_persisted)
        finally:
            original_store.close()
        content = self.target.read_text()
        self.assertIn(f"`{receipt.receipt_id}`", content)
        self.assertIn("purge `complete`", content)
        self.assertEqual(projection.sha256, hashlib.sha256(self.target.read_bytes()).hexdigest())

    def test_recovers_projection_after_process_dies_before_receipt_commit(self) -> None:
        """Recover when a worker exits after Markdown replacement, before receipt commit."""

        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store), TestReviewAuthorizer()
        )
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        change, _ = self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Implemented bounded recovery"
        )
        verified, _ = self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "The recovery regression passes",
            criterion_id="write",
            evidence=(
                EvidenceRef(
                    "unit-test",
                    "test-proof:passed",
                    hashlib.sha256(b"recovery-proof").hexdigest(),
                    EvidenceOutcome.PASSED,
                ),
            ),
        )
        candidate = self.plugin.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.RECOVERY,
                "The interrupted projection can be retried without changing facts",
                (change.fact_id, verified.fact_id),
                "Observed in the bounded test scenario",
                "Useful for future maintenance review",
            )
        )
        assert candidate is not None
        review_packet = self.plugin.sde_review_packet(candidate.candidate_id)
        receipt = self.plugin.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate.candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=True,
                dependency_map_sha256=review_packet.dependency_map_sha256,
            )
        )
        self.store.close()
        database = Path(self.temporary) / "global.sqlite3"
        crash_after_projection = """\
import os
import sys
from pathlib import Path

from evidence_fixtures import attest_test_evidence
from curatormd_v2 import CuratorStore, ProjectPlugin
from curatormd_v2.project_config import ProjectConfig

class TestVerifier:
    def attest(self, evidence, context):
        if evidence.locator == "test-proof:passed":
            return attest_test_evidence(evidence, context)
        return None

config = ProjectConfig.load(Path(sys.argv[1]))
store = CuratorStore(Path(sys.argv[2]))
plugin = ProjectPlugin.bind(config, store, TestVerifier())

def terminate_before_receipt_commit(*_args, **_kwargs):
    os._exit(73)

store.mark_receipt_canonical_persisted = terminate_before_receipt_commit
plugin.persist_goal(sys.argv[3], Path(sys.argv[4]))
raise SystemExit(0)
"""
        crashed = subprocess.run(
            [
                sys.executable,
                "-c",
                crash_after_projection,
                str(self.root),
                str(database),
                self.goal.goal_id,
                str(self.target),
            ],
            capture_output=True,
            check=False,
            cwd=Path(__file__).resolve().parents[1],
                env={
                    **os.environ,
                    "PYTHONPATH": os.pathsep.join(
                        filter(
                            None,
                            (
                                str(Path(__file__).resolve().parent),
                                os.environ.get("PYTHONPATH", ""),
                            ),
                        )
                    ),
                },
            timeout=30,
        )
        self.assertEqual(crashed.returncode, 73, crashed.stderr.decode("utf-8", "replace"))

        self.store = CuratorStore(database)
        self.addCleanup(self.store.close)
        self.plugin = ProjectPlugin.bind(
            self.config,
            self.store,
            TestVerifier(self.store),
            TestReviewAuthorizer(),
        )
        after_process_exit = self.store.get_receipt(
            receipt.receipt_id, self.config.project_id
        )
        self.assertFalse(after_process_exit.canonical_persisted)
        self.assertEqual(
            self.plugin.reconcile_goal(self.goal.goal_id, self.target).status,
            MarkdownReconciliationStatus.SYNCED,
        )
        self.plugin.persist_goal(self.goal.goal_id, self.target)

        recovered = self.store.get_receipt(receipt.receipt_id, self.config.project_id)
        self.assertTrue(recovered.canonical_persisted)
        self.assertEqual(recovered.purge_status.value, "complete")
        self.assertEqual(
            self.plugin.reconcile_goal(self.goal.goal_id, self.target).status,
            MarkdownReconciliationStatus.SYNCED,
        )

    def test_rejected_sde_rationale_is_not_projected_as_canonical_knowledge(self) -> None:
        """Keep rejection audit facts while excluding its proposal narrative."""

        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store), TestReviewAuthorizer()
        )
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        change, _ = self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Implemented a measured improvement"
        )
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:passed",
            hashlib.sha256(b"rejected-proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        verification, _ = self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Unit test passed",
            criterion_id="write",
            evidence=(evidence,),
        )
        rationale = "Proposed SDE narrative that the reviewer rejected"
        candidate = self.plugin.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                rationale,
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        review_packet = self.plugin.sde_review_packet(candidate.candidate_id)
        receipt = self.plugin.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate.candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(),
                artifact_inventory_complete=True,
                dependency_map_sha256=review_packet.dependency_map_sha256,
            )
        )
        correction = self.plugin.sde_correction_record(
            "markdown-correction-1",
            candidate.candidate_id,
            "Limit the statement to the passing unit test",
            "No production measurement was supplied",
        )

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        content = self.target.read_text()

        self.assertNotIn(rationale, content)
        self.assertIn("Review receipts", content)
        self.assertIn(f"`{receipt.receipt_id}`: `rejected`", content)
        self.assertIn("- Change: Implemented a measured improvement", content)
        self.assertIn("SDE corrections (append-only)", content)
        self.assertIn("`markdown\\-correction\\-1`", content)
        self.assertIn("reviewer: `test\\-reviewer`", content)
        self.assertIn(correction.correction, content)

    def test_project_scope_and_explicit_configured_target_are_required(self) -> None:
        """Do not project another project's goal or an unconfigured target."""

        other_config = ProjectConfig.load(self._create_other_repo())
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                other_config, "Register the second isolated persistence fixture"
            ),
            "test-admin",
        )
        other = ProjectPlugin.bind(other_config, self.store).goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Other project goal",
                success_criteria=(SuccessCriterion("other", "Complete"),),
                exact_item_text="- [ ] Other task",
            )
        )

        with self.assertRaises(LookupError):
            self.plugin.persist_goal(other.goal_id, self.target)
        with self.assertRaisesRegex(ProjectConfigError, "not configured"):
            self.plugin.persist_goal(self.goal.goal_id, "docs/other.md")

    def test_rejects_target_replaced_with_symlink(self) -> None:
        """Revalidate the configured destination at each write."""

        outside = Path(self.temporary) / "outside.md"
        outside.write_text("Do not modify outside the repository.\n")
        self.target.unlink()
        self.target.symlink_to(outside)

        with self.assertRaises(ProjectConfigError):
            self.plugin.persist_goal(self.goal.goal_id, self.target)
        self.assertEqual(outside.read_text(), "Do not modify outside the repository.\n")

    def test_rejects_malformed_goal_markers_without_overwriting_content(self) -> None:
        """Refuse marker-like text that could cause a broad block replacement."""

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        original = self.target.read_text()
        start_marker = next(
            line for line in original.splitlines() if line.endswith(":start -->")
        )
        self.target.write_text(original + f"prefix {start_marker}\n")

        with self.assertRaisesRegex(
            MarkdownPersistenceError, "duplicated or incomplete"
        ):
            self.plugin.persist_goal(self.goal.goal_id, self.target)
        self.assertIn(f"prefix {start_marker}", self.target.read_text())

    def test_projection_hash_is_rechecked_before_purge_proof(self) -> None:
        """Detect an external edit between atomic write and receipt release."""

        adapter = MarkdownPersistenceAdapter(self.config, self.store, self.target)
        projection = adapter.persist_goal(self.goal.goal_id)
        self.target.write_text(self.target.read_text() + "External edit.\n")

        with self.assertRaisesRegex(MarkdownPersistenceError, "changed"):
            adapter.verify_projection(projection)

    def test_rejects_oversized_target_without_changing_it(self) -> None:
        """Enforce the Markdown target bound before reading/writing its body."""

        original = "x" * (8 * 1024 * 1024 + 1)
        self.target.write_text(original)

        with self.assertRaisesRegex(MarkdownPersistenceError, "exceeds"):
            self.plugin.persist_goal(self.goal.goal_id, self.target)
        self.assertEqual(self.target.stat().st_size, len(original))

    def test_invalid_markdown_utf8_error_does_not_retain_source(self) -> None:
        """Canonical decoder errors must not retain raw Markdown bytes."""

        self.target.write_bytes(b"PRIVATE_MARKDOWN_CANARY\xff")
        with self.assertRaisesRegex(
            MarkdownPersistenceError, "must be UTF-8"
        ) as raised:
            self.plugin.persist_goal(self.goal.goal_id, self.target)
        self.assertNotIn("PRIVATE_MARKDOWN_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_filesystem_errors_do_not_retain_private_paths(self) -> None:
        """Sanitized persistence failures have no chained OS path detail."""

        adapter = MarkdownPersistenceAdapter(self.config, self.store, self.target)
        private_path = "/srv/private/customer/notes.md"
        with patch(
            "curatormd_v2.markdown_persistence.os.open",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError, "cannot safely open Markdown target"
            ) as raised:
                adapter.persist_goal(self.goal.goal_id)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

        real_fdopen = os.fdopen

        class FailingReader:
            """Raise a path-bearing error from the canonical target read."""

            def __init__(self, source: BinaryIO) -> None:
                self.source = source

            def __enter__(self) -> object:
                return self

            def __exit__(self, *_args: object) -> None:
                self.source.close()

            def fileno(self) -> int:
                """Expose the wrapped descriptor for the injected reader."""
                return self.source.fileno()

            def read(self, _limit: int) -> bytes:
                """Raise a private-path error to test boundary sanitization."""
                raise OSError(f"read failed: {private_path}")

        def wrap_fdopen(descriptor: int, mode: str) -> object:
            return FailingReader(cast(BinaryIO, real_fdopen(descriptor, mode)))

        with patch(
            "curatormd_v2.markdown_persistence.os.fdopen",
            side_effect=wrap_fdopen,
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError, "cannot read canonical Markdown target"
            ) as raised:
                adapter.persist_goal(self.goal.goal_id)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

        with patch(
            "curatormd_v2.markdown_persistence.os.replace",
            side_effect=OSError(f"replace failed: {private_path}"),
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError, "atomic canonical Markdown replacement failed"
            ) as raised:
                adapter.persist_goal(self.goal.goal_id)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_retry_syncs_directory_after_replacement_sync_failure(self) -> None:
        """Retry durability after replacement succeeded but directory sync failed."""

        self.plugin.goal_activate(
            self.goal.goal_id, "Retry a directory durability failure", 1
        )
        with patch(
            "curatormd_v2.markdown_persistence.os.fsync",
            side_effect=[None, OSError("injected directory sync failure")],
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError,
                "atomic canonical Markdown replacement failed",
            ):
                self.plugin.persist_goal(self.goal.goal_id, self.target)

        projected_bytes = self.target.read_bytes()
        self.assertIn(self.goal.goal_id.encode("utf-8"), projected_bytes)
        with patch(
            "curatormd_v2.markdown_persistence.os.fsync",
            wraps=os.fsync,
        ) as retry_fsync:
            retry = self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertFalse(retry.changed)
        self.assertEqual(retry_fsync.call_count, 1)
        self.assertEqual(self.target.read_bytes(), projected_bytes)

    def test_short_canonical_write_preserves_target_and_removes_partial(self) -> None:
        """Reject a short temporary-file write without replacing the target."""

        original_target = self.target.read_bytes()
        original_fdopen = os.fdopen

        class ShortWriter:
            """Write a prefix and report its actual byte count."""

            def __init__(self, stream: BinaryIO) -> None:
                self.stream = stream

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_args: object) -> None:
                self.stream.close()

            def write(self, data: bytes) -> int:
                prefix = data[:2]
                self.stream.write(prefix)
                self.stream.flush()
                return len(prefix)

            def flush(self) -> None:
                self.stream.flush()

            def fileno(self) -> int:
                return self.stream.fileno()

        def short_fdopen(descriptor: int, mode: str) -> BinaryIO:
            stream = cast(BinaryIO, original_fdopen(descriptor, mode))
            if mode == "wb":
                return cast(BinaryIO, ShortWriter(stream))
            return stream

        with patch(
            "curatormd_v2.markdown_persistence.os.fdopen",
            side_effect=short_fdopen,
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError,
                "atomic canonical Markdown replacement failed",
            ):
                self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertEqual(self.target.read_bytes(), original_target)
        self.assertEqual(
            tuple(self.target.parent.glob(".curatormd-v2-write-*")), ()
        )

    def test_file_sync_failure_preserves_target_and_removes_temporary(self) -> None:
        """A temporary-file sync failure cannot publish or damage the target."""

        original_target = self.target.read_bytes()
        with patch(
            "curatormd_v2.markdown_persistence.os.fsync",
            side_effect=OSError("injected file sync failure"),
        ):
            with self.assertRaisesRegex(
                MarkdownPersistenceError,
                "atomic canonical Markdown replacement failed",
            ):
                self.plugin.persist_goal(self.goal.goal_id, self.target)

        self.assertEqual(self.target.read_bytes(), original_target)
        self.assertEqual(
            tuple(self.target.parent.glob(".curatormd-v2-write-*")), ()
        )



if __name__ == "__main__":
    unittest.main()
