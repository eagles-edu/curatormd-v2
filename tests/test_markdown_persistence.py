"""Repository-scoped canonical Markdown projection tests."""

from __future__ import annotations

import os
from pathlib import Path
import hashlib
import tempfile
import unittest
from typing import BinaryIO, cast
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from project_fixtures import create_consumer_repo
from purge_fixtures import TestReviewAuthorizer

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    CuratorStore,
    EventEnvelope,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactRecorded,
    FactKind,
    MarkdownPersistenceAdapter,
    MarkdownPersistenceError,
    MarkdownReconciliationStatus,
    Materiality,
    ProjectPlugin,
    ReviewDecision,
    SuccessCriterion,
)
from curatormd_v2.project_config import ProjectConfig, ProjectConfigError


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


class MarkdownPersistenceTests(unittest.TestCase):
    """Verify explicit, bounded, idempotent project Markdown writes."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        base = Path(self.temporary)
        self.root = create_consumer_repo(base / "consumer")
        (self.root / "docs" / "tasks.md").write_text("- [ ] Implement adapter\n")
        self.target = self.root / "persistence" / "HISTORY.md"
        self.target.write_text("# Existing project history\n\nKeep this text.\n")
        (self.root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "consumer-a"

            [scope]
            read_paths = ["src", "docs"]

            [checklists]
            tasks = "docs/tasks.md"

            [evidence]
            adapters = []

            [staging]
            root = ".curatormd-v2/staging"

            [persistence]
            targets = ["persistence/HISTORY.md"]
            """
        )
        (self.root / ".curatormd-v2.toml").chmod(0o600)
        self.config = ProjectConfig.load(self.root)
        self.store = CuratorStore(base / "global.sqlite3")
        self.addCleanup(self.store.close)
        self.plugin = ProjectPlugin.bind(self.config, self.store)
        self.goal = self.plugin.goal_start_from_checklist(
            "tasks",
            "Implement the canonical Markdown projection",
            (SuccessCriterion("write", "A scoped goal is written as compact bullets"),),
            exact_item_text="- [ ] Implement adapter",
        )

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

    def test_projection_recovers_ledger_first_update_after_store_reopen(self) -> None:
        """Rebuild a missing canonical block from durable ledger state."""

        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            "The ledger update survived before Markdown projection",
        )
        self.store.close()
        self.store = CuratorStore(Path(self.temporary) / "global.sqlite3")
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

    def test_project_reconciliation_pages_goals_and_finds_orphaned_markers(self) -> None:
        second_goal = self.plugin.service.goal_start(
            "A second goal remains absent from Markdown",
            (SuccessCriterion("listed", "The second goal appears in its page"),),
        )
        self.plugin.persist_goal(self.goal.goal_id, self.target)
        orphan_goal_id = "orphaned-markdown-goal"
        orphan_marker_hash = hashlib.sha256(orphan_goal_id.encode("utf-8")).hexdigest()
        malformed_goal_id = "malformed-markdown-goal"
        malformed_marker_hash = hashlib.sha256(
            malformed_goal_id.encode("utf-8")
        ).hexdigest()
        orphan_block = (
            f"<!-- curatormd-v2:goal:{orphan_marker_hash}:start -->\n"
            f"### Goal `{orphan_goal_id}`\n"
            f"<!-- curatormd-v2:goal:{orphan_marker_hash}:end -->\n"
            f"<!-- curatormd-v2:goal:{malformed_marker_hash}:start -->\n"
        )
        existing = self.target.read_text(encoding="utf-8")
        self.target.write_text(existing + orphan_block, encoding="utf-8")
        with_orphan = self.target.read_text(encoding="utf-8")

        first_page = self.plugin.reconcile_project(self.target, offset=0, limit=1)
        second_page = self.plugin.reconcile_project(self.target, offset=1, limit=1)

        self.assertEqual(first_page.total_goals, 2)
        self.assertEqual(first_page.next_offset, 1)
        self.assertEqual(second_page.next_offset, None)
        results = {
            item.goal_id: item.status.value
            for item in first_page.goals + second_page.goals
        }
        self.assertEqual(results[self.goal.goal_id], "synced")
        self.assertEqual(results[second_goal.goal_id], "missing")
        self.assertEqual(first_page.orphan_marker_sha256, (orphan_marker_hash,))
        self.assertEqual(
            first_page.malformed_marker_sha256, (malformed_marker_hash,)
        )
        self.assertTrue(first_page.inventory_complete)
        self.assertEqual(first_page.malformed_marker_count, 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), with_orphan)

    def test_project_reconciliation_marks_over_limit_marker_inventory_incomplete(self) -> None:
        markers = "\n".join(
            "<!-- curatormd-v2:goal:unrecognized -->"
            for _ in range(5001)
        )
        self.target.write_text(markers, encoding="utf-8")

        report = self.plugin.reconcile_project(self.target)

        self.assertFalse(report.inventory_complete)
        self.assertEqual(report.unrecognized_marker_count, 5000)
        self.assertEqual(self.target.read_text(encoding="utf-8"), markers)

    def test_read_only_reconciliation_marks_malformed_markers(self) -> None:
        """Do not choose a side or mutate a projection with unsafe markers."""

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        original = self.target.read_text()
        marker = next(
            line for line in original.splitlines() if line.endswith(":start -->")
        )
        self.target.write_text(original + f"prefix {marker}\n")
        malformed_content = self.target.read_text()

        result = self.plugin.reconcile_goal(self.goal.goal_id, self.target)

        self.assertEqual(result.status, MarkdownReconciliationStatus.MALFORMED)
        self.assertIsNone(result.actual_sha256)
        self.assertEqual(self.target.read_text(), malformed_content)

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

    def test_plugin_persists_review_receipt_before_releasing_purge_gate(self) -> None:
        """Only a written canonical facts/receipt block may trigger deletion."""

        self.plugin = ProjectPlugin.bind(
            self.config, self.store, TestVerifier(self.store), TestReviewAuthorizer()
        )
        self.plugin.goal_activate(
            self.goal.goal_id, "Test accepts the implementation", 1
        )
        change, _ = self.plugin.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Implemented and tested change"
        )
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:passed",
            hashlib.sha256(b"proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        verification, _ = self.plugin.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Unit check passed",
            criterion_id="write",
            evidence=(evidence,),
        )
        candidate = self.plugin.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "Durable implementation with direct test evidence",
            (change.fact_id, verification.fact_id),
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        artifact_path = self.root / ".curatormd-v2" / "staging" / "scratch.json"
        artifact_path.write_text("temporary test artifact")
        artifact = ArtifactRef(
            str(artifact_path),
            hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        )
        receipt = self.plugin.service.sde_confirm(
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (artifact,),
            artifact_inventory_complete=True,
        )
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

        projection = self.plugin.persist_goal(self.goal.goal_id, self.target)

        final_receipt = self.store.get_receipt(receipt.receipt_id, "consumer-a")
        self.assertTrue(purger.called)
        self.assertFalse(artifact_path.exists())
        self.assertTrue(final_receipt.canonical_persisted)
        self.assertEqual(final_receipt.canonical_target, "persistence/HISTORY.md")
        self.assertEqual(final_receipt.canonical_sha256, purger.persisted_digest)
        content = self.target.read_text()
        self.assertIn(f"`{receipt.receipt_id}`", content)
        self.assertIn("purge `complete`", content)
        self.assertEqual(projection.sha256, hashlib.sha256(self.target.read_bytes()).hexdigest())

    def test_retries_projection_when_receipt_commit_fails_after_markdown_write(self) -> None:
        """A durable projection is safely replayed after its receipt update fails."""

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
            self.goal.goal_id,
            Materiality.RECOVERY,
            "The interrupted projection can be retried without changing facts",
            (change.fact_id, verified.fact_id),
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
        )
        assert candidate is not None
        receipt = self.plugin.sde_confirm(
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=True,
        )
        commit_receipt = self.store.mark_receipt_canonical_persisted
        fail_once = True

        def interrupt_receipt_commit(
            receipt_id: str, target: str, sha256: str, project_id: str
        ):
            nonlocal fail_once
            if fail_once:
                fail_once = False
                raise RuntimeError("injected interruption after Markdown replacement")
            return commit_receipt(receipt_id, target, sha256, project_id)

        with patch.object(
            self.store,
            "mark_receipt_canonical_persisted",
            side_effect=interrupt_receipt_commit,
        ):
            with self.assertRaisesRegex(RuntimeError, "injected interruption"):
                self.plugin.persist_goal(self.goal.goal_id, self.target)

            after_interruption = self.store.get_receipt(
                receipt.receipt_id, self.config.project_id
            )
            self.assertFalse(after_interruption.canonical_persisted)
            self.assertEqual(
                self.plugin.reconcile_goal(self.goal.goal_id, self.target).status,
                MarkdownReconciliationStatus.SYNCED,
            )

            self.store.close()
            self.store = CuratorStore(Path(self.temporary) / "global.sqlite3")
            self.addCleanup(self.store.close)
            self.plugin = ProjectPlugin.bind(
                self.config,
                self.store,
                TestVerifier(self.store),
                TestReviewAuthorizer(),
            )
            after_store_restart = self.store.get_receipt(
                receipt.receipt_id, self.config.project_id
            )
            self.assertFalse(after_store_restart.canonical_persisted)
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
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            rationale,
            (change.fact_id, verification.fact_id),
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
        )
        assert candidate is not None
        receipt = self.plugin.sde_confirm(
            candidate.candidate_id,
            ReviewDecision.REJECTED,
            (),
            artifact_inventory_complete=True,
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

        other = ProjectPlugin.bind(
            ProjectConfig.load(self._create_other_repo()), self.store
        ).goal_start_from_checklist(
            "tasks",
            "Other project goal",
            (SuccessCriterion("other", "Complete"),),
            exact_item_text="- [ ] Other task",
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
                return self.source.fileno()

            def read(self, _limit: int) -> bytes:
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

    def _create_other_repo(self) -> Path:
        """Create a separately configured consumer for project-isolation tests."""

        root = create_consumer_repo(Path(self.temporary) / "other-consumer")
        (root / "docs" / "tasks.md").write_text("- [ ] Other task\n")
        (root / "persistence" / "HISTORY.md").write_text("# Other history\n")
        (root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "consumer-b"

            [scope]
            read_paths = ["src", "docs"]

            [checklists]
            tasks = "docs/tasks.md"

            [evidence]
            adapters = []

            [staging]
            root = ".curatormd-v2/staging"

            [persistence]
            targets = ["persistence/HISTORY.md"]
            """
        )
        (root / ".curatormd-v2.toml").chmod(0o600)
        return root


if __name__ == "__main__":
    unittest.main()
