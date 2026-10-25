"""GoalReporting regressions."""

from __future__ import annotations

import json
from unittest.mock import patch

from lifecycle_test_support import (
    LifecycleTestSupport,
    TransactionCheckingVerifier,
)

from curatormd_v2 import (
    CriterionStatus,
    FactKind,
    GoalStatus,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    GoalStarted,
)
from curatormd_v2.reporting import GoalReportPage


class GoalReportingTests(LifecycleTestSupport):
    """Cover goalreporting invariants."""

    def test_incomplete_finish_stays_open_with_concrete_next_action(self) -> None:
        verified = self.verify("unit", "unit test suite passed")
        before_finish = self.service.goal_status(self.goal.goal_id).criteria
        self.assertEqual(before_finish[0].status, CriterionStatus.VERIFIED)
        self.assertEqual(
            before_finish[0].verification_fact_ids, (verified.fact_id,)
        )
        self.assertEqual(before_finish[1].status, CriterionStatus.OPEN)
        stored = self.service.goal_finish(self.goal.goal_id, "Work is finished")
        self.assertEqual(stored.status, GoalStatus.OPEN)
        self.assertIn("readiness probe returns healthy", stored.next_action or "")
        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertTrue(any(fact.kind is FactKind.OPEN_GATE for fact in snapshot.facts))
        outcome = next(
            fact for fact in snapshot.facts if fact.kind is FactKind.OUTCOME
        )
        self.assertEqual(outcome.bullet, "open")
        self.assertEqual(
            [item.status for item in snapshot.criteria],
            [CriterionStatus.VERIFIED, CriterionStatus.OPEN],
        )
        report = self.service.goal_report(self.goal.goal_id)
        self.assertIn("- Outcome: `open`", report)
        self.assertIn("Outcome: open", report)
        self.assertIn("- Owner: agent", report)
        self.assertIn("readiness probe returns healthy", report)
        self.assertIn("unit test suite passed", report)

    def test_bullet_projection_separates_verified_claims_and_current_open_gates(self) -> None:
        self.verify("unit", "Unit test suite passed")
        opened = self.service.goal_finish(
            self.goal.goal_id, "The implementation is complete"
        )
        self.assertEqual(opened.status, GoalStatus.OPEN)
        projection = self.service.goal_bullet_projection(self.goal.goal_id)
        categories = [item.category.value for item in projection.bullets]
        rendered = [item.as_bullet() for item in projection.bullets]

        self.assertIn("verified_fact", categories)
        self.assertIn("unverified_claim", categories)
        self.assertIn("open_gate", categories)
        self.assertTrue(
            any(
                item.category.value == "open_gate" and "probe" in item.text
                for item in projection.bullets
            )
        )
        self.assertTrue(all("\n" not in bullet for bullet in rendered))
        self.assertEqual(projection.next_action, opened.next_action)

        self.verify("probe", "Readiness probe returned healthy")
        completed = self.service.goal_finish(
            self.goal.goal_id, "Every required criterion is verified"
        )
        final_projection = self.service.goal_bullet_projection(self.goal.goal_id)
        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertFalse(
            any(item.category.value == "open_gate" for item in final_projection.bullets)
        )

    def test_evidence_verifier_runs_outside_sqlite_write_transactions(self) -> None:
        verifier = TransactionCheckingVerifier(self.store)
        self.service.evidence_verifier = verifier

        self.verify("unit", "Unit suite passed")
        self.verify("probe", "Readiness probe returned healthy")
        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertTrue(
            all(item.status is CriterionStatus.VERIFIED for item in snapshot.criteria)
        )
        completed = self.service.goal_finish(
            self.goal.goal_id,
            "All criteria have current verified evidence",
            snapshot.goal.lifecycle_revision,
        )

        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertGreaterEqual(verifier.calls, 6)

    def test_goal_report_preserves_truth_labels_and_bounds_fact_pages(self) -> None:
        intake_report = self.service.goal_report(self.goal.goal_id)
        self.assertIn("owner: agent", intake_report)
        self.assertIn(
            "suggested next action: Verify criterion `probe` against its stated "
            "acceptance condition; goal next action: not recorded",
            intake_report,
        )
        self.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            "Implemented the unit check",
        )
        self.verify("unit", "Unit suite passed")
        self.service.goal_finish(
            self.goal.goal_id, "Claimed complete without the readiness probe"
        )

        # Evidence adapters may perform slow I/O. Reporting must not hold the
        # store's BEGIN IMMEDIATE write transaction while evaluating evidence.
        with patch.object(
            self.store,
            "transaction",
            side_effect=AssertionError("read report opened a write transaction"),
        ):
            report = self.service.goal_report(
                self.goal.goal_id, GoalReportPage(fact_limit=1)
            )

        self.assertIn("## Success criteria", report)
        self.assertIn("## Facts to date (showing 1–1 of", report)
        self.assertIn("## Open TODOs", report)
        self.assertIn("Verify criterion `probe`", report)
        self.assertIn("readiness probe returns healthy", report)
        self.assertIn(
            "blocker: Open: success criterion 'readiness probe returns healthy' "
            "lacks passing evidence",
            report,
        )
        self.assertIn("owner: agent", report)
        self.assertIn("More facts available: request `fact_offset=1`", report)
        self.assertNotIn("test-proof:", report)

        second_page = self.service.goal_report(
            self.goal.goal_id, GoalReportPage(fact_offset=1, fact_limit=3)
        )
        self.assertIn("Verified facts", second_page)
        self.assertIn("Unverified claims or checks", second_page)
        self.assertIn("completion claim", second_page)
        with self.assertRaisesRegex(ValueError, "fact_limit"):
            self.service.goal_report(
                self.goal.goal_id, GoalReportPage(fact_limit=17)
            )

    def test_goal_intake_report_preserves_next_action_and_names_open_criteria(self) -> None:
        """Expose the caller's concrete first step without inventing one."""

        goal = self.service.goal_start(
            "Implement the requested lifecycle report",
            (SuccessCriterion("report", "The report lists verified facts and TODOs"),),
            goal_id="goal-with-next-action",
            owner="agent",
            initial_status=GoalStatus.PLANNED,
            next_action="Add the report's bounded next-action field",
        )
        report = self.service.goal_report(goal.goal_id)

        self.assertIn(
            "- Next action: Add the report's bounded next-action field", report
        )
        self.assertIn(
            "blocker: No current passing verification fact is linked to this criterion; "
            "owner: agent; suggested next action: Verify criterion `report` against "
            "its stated acceptance condition; goal next action: Add the report's "
            "bounded next-action field",
            report,
        )
        self.assertIn(
            "Verify criterion `report`: The report lists verified facts and TODOs",
            report,
        )
        self.assertEqual(
            self.service.goal_status(goal.goal_id).goal.next_action,
            "Add the report's bounded next-action field",
        )
        activated = self.service.goal_activate(
            goal.goal_id, "The user accepted the planned work", 1
        )
        self.assertEqual(activated.status, GoalStatus.ACTIVE)
        self.assertEqual(
            activated.next_action,
            "Add the report's bounded next-action field",
        )
        self.service.goal_fact(
            goal.goal_id,
            FactKind.OPEN_GATE,
            "The smoke test has not run on this revision",
            criterion_id="report",
        )
        open_report = self.service.goal_report(goal.goal_id)
        self.assertIn(
            "blocker: The smoke test has not run on this revision; owner: agent; "
            "suggested next action: Verify criterion `report` against its stated "
            "acceptance condition; goal next action: Add the report's bounded "
            "next-action field",
            open_report,
        )
        self.assertIn(
            "- Next action: Add the report's bounded next-action field",
            open_report,
        )

    def test_partial_child_completion_stays_visible_without_completing_parent(self) -> None:
        """Keep completed child history visible while the parent still has work."""

        completed_child = self.service.goal_start(
            "Complete one child task",
            (SuccessCriterion("child-proof", "The child work is verified"),),
            goal_id="child-completed",
            parent_goal_id=self.goal.goal_id,
        )
        self.service.goal_fact(
            completed_child.goal_id,
            FactKind.VERIFICATION,
            "The child acceptance evidence passed",
            criterion_id="child-proof",
            evidence=(self.proof("child-completed-proof"),),
        )
        completed = self.service.goal_finish(
            completed_child.goal_id,
            "The child criterion has passing evidence",
        )
        open_child = self.service.goal_start(
            "Keep another child task open",
            (SuccessCriterion("remaining-work", "The remaining work is tracked"),),
            goal_id="child-open",
            parent_goal_id=self.goal.goal_id,
        )

        report = self.service.goal_report(self.goal.goal_id)
        listed = self.service.goal_list_page(limit=10)
        parent_card = next(
            card for card in listed.goals if card.goal_id == self.goal.goal_id
        )

        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertEqual(open_child.status, GoalStatus.ACTIVE)
        self.assertIn("`child-completed` — `complete`", report)
        self.assertIn("`child-open` — `active`", report)
        self.assertIn("1 child goal(s) remain open overall", report)
        self.assertEqual(parent_card.status, self.goal.status)
        self.assertNotIn("- Outcome: `complete`", report)

    def test_goal_report_uses_bounded_history_pages_and_exact_child_counts(self) -> None:
        for index in range(35):
            self.service.goal_start(
                f"Child task {index}",
                (SuccessCriterion(f"child-{index}", "child criterion remains tracked"),),
                parent_goal_id=self.goal.goal_id,
                goal_id=f"child-{index:02d}",
            )

        with (
            patch.object(
                self.store,
                "list_sde_candidates",
                side_effect=AssertionError("unpaged SDE history loaded"),
            ),
            patch.object(
                self.store,
                "pending_receipts_for_goal",
                side_effect=AssertionError("unpaged purge history loaded"),
            ),
            patch.object(
                self.store,
                "receipts_for_goal",
                side_effect=AssertionError("unpaged receipt history loaded"),
            ),
            patch.object(
                self.store,
                "list_child_goals",
                side_effect=AssertionError("unpaged child history loaded"),
            ),
        ):
            first_page = self.service.goal_report(self.goal.goal_id)
            second_page = self.service.goal_report(
                self.goal.goal_id, GoalReportPage(child_offset=32)
            )

        self.assertIn("35 child goal(s) remain open overall", first_page)
        self.assertIn("3 additional child goal(s) omitted", first_page)
        self.assertIn("`child-00`", first_page)
        self.assertIn("`child-31`", first_page)
        self.assertNotIn("`child-32`", first_page)
        self.assertIn("`child-32`", second_page)
        self.assertIn("`child-34`", second_page)

    def test_goal_status_paginates_candidate_and_purge_histories(self) -> None:
        with self.store.transaction() as connection:
            for index in range(105):
                candidate_id = f"sde-status-{index:03d}"
                receipt_id = f"receipt-status-{index:03d}"
                timestamp = f"2026-10-19T00:00:00.{index:06d}+00:00"
                connection.execute(
                    """INSERT INTO sde_candidates
                       (candidate_id, goal_id, materiality, rationale, fact_ids_json,
                        dedupe_key, status, created_at)
                       VALUES (?, ?, 'implementation', 'bounded test candidate', ?, ?,
                               'pending_review', ?)""",
                    (
                        candidate_id,
                        self.goal.goal_id,
                        json.dumps(["fact-not-required-by-this-read"]),
                        candidate_id,
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO audit_receipts
                       (receipt_id, candidate_id, decision, facts_sha256,
                        artifact_inventory_complete, reviewer_id, review_rationale,
                        canonical_persisted, canonical_target, canonical_sha256,
                        canonical_persisted_at, purge_status, created_at, updated_at)
                       VALUES (?, ?, 'approved', ?, 1, 'reviewer:test', 'fixture',
                               0, NULL, NULL, NULL, 'purge_pending', ?, ?)""",
                    (
                        receipt_id,
                        candidate_id,
                        "a" * 64,
                        timestamp,
                        timestamp,
                    ),
                )

        with (
            patch.object(
                self.store,
                "list_sde_candidates",
                side_effect=AssertionError("unpaged SDE history loaded"),
            ),
            patch.object(
                self.store,
                "pending_receipts_for_goal",
                side_effect=AssertionError("unpaged purge history loaded"),
            ),
        ):
            first_page = self.service.goal_status(self.goal.goal_id)
            second_page = self.service.goal_status(
                self.goal.goal_id, sde_offset=32, purge_offset=16
            )
            final_page = self.service.goal_status(
                self.goal.goal_id, sde_offset=96, purge_offset=96
            )

        self.assertEqual(len(first_page.sde_candidates), 32)
        self.assertEqual(len(first_page.pending_purges), 16)
        self.assertEqual(first_page.sde_candidate_total, 105)
        self.assertEqual(first_page.sde_candidate_status_counts, (("pending_review", 105),))
        self.assertEqual(first_page.sde_candidate_next_offset, 32)
        self.assertEqual(first_page.pending_purge_total, 105)
        self.assertEqual(first_page.pending_purge_next_offset, 16)
        projected = self.service.goal_bullet_projection(self.goal.goal_id)
        projected_text = [bullet.text for bullet in projected.bullets]
        self.assertTrue(
            any(
                "105 SDE candidate(s) await review overall" in text
                and "sde_offset=32" in text
                for text in projected_text
            )
        )
        self.assertTrue(
            any(
                "105 purge receipt(s) remain pending" in text
                and "purge_offset=16" in text
                for text in projected_text
            )
        )
        self.assertEqual(len(second_page.sde_candidates), 32)
        self.assertEqual(len(second_page.pending_purges), 16)
        self.assertEqual(second_page.sde_candidate_next_offset, 64)
        self.assertEqual(second_page.pending_purge_next_offset, 32)
        self.assertEqual(len(final_page.sde_candidates), 9)
        self.assertEqual(len(final_page.pending_purges), 9)
        self.assertIsNone(final_page.sde_candidate_next_offset)
        self.assertIsNone(final_page.pending_purge_next_offset)

    def test_goal_report_keeps_intake_provenance_after_activation_and_reopen(self) -> None:
        criterion = SuccessCriterion("verified", "The request is verified")
        event = EventEnvelope(
            event_id="source-request-17",
            project_id=self.service.project_id,
            source_id="mcp-user-intake",
            payload=GoalStarted(
                goal_id="provenance-goal",
                problem="Preserve request identity in reports",
                success_criteria=(criterion,),
                owner="agent-7",
                checklist_id="release-gate-3",
                checklist_version="sha256:" + "a" * 64,
                checklist_source_text="- [ ] Verify report provenance",
                initial_status=GoalStatus.PLANNED,
            ),
        )
        self.service.process_event(event)
        self.service.goal_activate("provenance-goal", "Accepted for work", 1)
        self.service.goal_fact(
            "provenance-goal",
            FactKind.VERIFICATION,
            "The focused proof passed",
            criterion_id="verified",
            evidence=(self.proof("origin"),),
        )
        self.service.goal_finish("provenance-goal", "The criterion is verified")
        self.service.goal_reopen(
            "provenance-goal",
            "A follow-up regression was reported",
            "Re-run the proof against the regression",
        )

        report = self.service.goal_report("provenance-goal")

        self.assertIn("- Outcome: `active`", report)
        self.assertIn("- Project: `default`", report)
        self.assertIn("- Owner: agent-7", report)
        self.assertIn("- Initial state: `planned`", report)
        self.assertIn("- Source event: `source-request-17`", report)
        self.assertIn("- Checklist: `release-gate-3`", report)
        self.assertIn("revision `aaaaaaaaaaaa`", report)
        self.assertIn(
            "- Checklist item (captured): - \\[ \\] Verify report provenance",
            report,
        )
        self.assertIn("## Current open gates", report)
        self.assertIn("Required criterion remains unverified", report)
        self.assertIn("Re-run the proof against the regression", report)
