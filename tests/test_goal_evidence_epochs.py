"""GoalEvidenceEpoch regressions."""

from __future__ import annotations

from itertools import permutations

from lifecycle_test_support import LifecycleTestSupport

from curatormd_v2 import (
    ConflictError,
    CriterionStatus,
    FactKind,
    GoalStatus,
    SuccessCriterion,
)
from curatormd_v2.events import GoalCriteriaAmended


class GoalEvidenceEpochTests(LifecycleTestSupport):
    """Cover goalevidenceepoch invariants."""

    def test_all_success_criteria_need_independently_verified_passing_evidence(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        stored = self.service.goal_finish(self.goal.goal_id, "All checks passed")
        self.assertEqual(stored.status, GoalStatus.COMPLETE)
        self.assertEqual(stored.success_criteria, self.criteria)
        progress = self.service.goal_status(self.goal.goal_id).criteria
        self.assertEqual(
            [criterion.status for criterion in progress],
            [CriterionStatus.VERIFIED, CriterionStatus.VERIFIED],
        )
        outcome_facts = tuple(
            fact
            for fact in self.store.list_facts(self.goal.goal_id)
            if fact.kind is FactKind.OUTCOME
        )
        self.assertEqual(len(outcome_facts), 1)
        self.assertTrue(outcome_facts[0].bullet.startswith("completed —"))
        with self.assertRaises(ConflictError):
            self.service.goal_fact(self.goal.goal_id, FactKind.CHANGE, "late edit")

    def test_reopen_starts_new_evidence_epoch_without_erasing_old_facts(self) -> None:
        old_proofs = (
            self.verify("unit", "Original unit suite passed"),
            self.verify("probe", "Original readiness probe passed"),
        )
        old_proof_ids = {fact.fact_id for fact in old_proofs}
        self.assertEqual(
            self.service.goal_finish(self.goal.goal_id, "Initial work is complete").status,
            GoalStatus.COMPLETE,
        )

        reopened = self.service.goal_reopen(
            self.goal.goal_id,
            "A post-release regression was reported",
            "Reproduce and repair the regression",
        )
        reopened_snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(reopened.status, GoalStatus.ACTIVE)
        self.assertEqual(reopened.next_action, "Reproduce and repair the regression")
        self.assertEqual(
            [item.status for item in reopened_snapshot.criteria],
            [CriterionStatus.OPEN, CriterionStatus.OPEN],
        )
        self.assertTrue(
            all(fact.fact_id in {item.fact_id for item in reopened_snapshot.facts}
                for fact in old_proofs)
        )
        self.assertTrue(
            any(fact.kind is FactKind.REOPENED for fact in reopened_snapshot.facts)
        )
        reopened_report = self.service.goal_report(self.goal.goal_id)
        self.assertIn("- Outcome: `active`", reopened_report)
        self.assertIn("- Next action: Reproduce and repair the regression", reopened_report)
        self.assertIn("## Facts to date", reopened_report)
        self.assertIn("Unverified claims or checks", reopened_report)
        self.assertIn("Original unit suite passed", reopened_report)
        self.assertIn("Required criterion remains unverified", reopened_report)
        self.assertIn("## Open TODOs", reopened_report)
        self.assertIn("Verify criterion `unit`", reopened_report)

        still_open = self.service.goal_finish(
            self.goal.goal_id, "The reopened work is complete"
        )
        self.assertEqual(still_open.status, GoalStatus.OPEN)
        self.verify("unit", "Fresh unit suite passed after reopen")
        self.verify("probe", "Fresh readiness probe passed after reopen")
        finished_again = self.service.goal_finish(
            self.goal.goal_id, "Fresh evidence now satisfies the criteria"
        )
        self.assertEqual(finished_again.status, GoalStatus.COMPLETE)
        current = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(
            [item.status for item in current.criteria],
            [CriterionStatus.VERIFIED, CriterionStatus.VERIFIED],
        )
        current_proof_ids = {
            proof_id
            for item in current.criteria
            for proof_id in item.verification_fact_ids
        }
        self.assertFalse(
            old_proof_ids.intersection(current_proof_ids),
            "completion after reopen must use fresh criterion evidence",
        )

    def test_reopen_requires_completed_dependents_and_parent_to_reopen_first(self) -> None:
        prerequisite = self.service.goal_start(
            "Complete the prerequisite",
            (SuccessCriterion("prerequisite", "Prerequisite passes"),),
        )
        dependent = self.service.goal_start(
            "Complete the dependent",
            (SuccessCriterion("dependent", "Dependent passes"),),
            depends_on_goal_ids=(prerequisite.goal_id,),
        )
        self.service.goal_fact(
            prerequisite.goal_id,
            FactKind.VERIFICATION,
            "Prerequisite verified",
            criterion_id="prerequisite",
            evidence=(self.proof("prerequisite"),),
        )
        self.service.goal_finish(prerequisite.goal_id, "Prerequisite complete")
        self.service.goal_fact(
            dependent.goal_id,
            FactKind.VERIFICATION,
            "Dependent verified",
            criterion_id="dependent",
            evidence=(self.proof("dependent"),),
        )
        self.service.goal_finish(dependent.goal_id, "Dependent complete")

        with self.assertRaisesRegex(ConflictError, "dependent goals first"):
            self.service.goal_reopen(
                prerequisite.goal_id, "Prerequisite regression", "Repair prerequisite"
            )
        self.service.goal_reopen(
            dependent.goal_id, "Dependent follow-up", "Revalidate dependent"
        )
        reopened = self.service.goal_reopen(
            prerequisite.goal_id, "Prerequisite regression", "Repair prerequisite"
        )
        self.assertEqual(reopened.status, GoalStatus.ACTIVE)

    def test_reopen_rejects_terminal_parents_and_dependencies_atomically(self) -> None:
        """Terminal relationship history stays fixed; continuation gets new links."""

        for parent_terminal in (GoalStatus.CANCELLED, GoalStatus.SUPERSEDED):
            for dependency_terminal in (GoalStatus.CANCELLED, GoalStatus.SUPERSEDED):
                with self.subTest(
                    parent=parent_terminal, dependency=dependency_terminal
                ):
                    parent, dependency, goal = self._completed_linked_goal()
                    _parent_replacement, dependency_replacement = (
                        self._make_linked_records_terminal(
                            parent,
                            dependency,
                            parent_terminal,
                            dependency_terminal,
                        )
                    )

                    before_goal = self.store.get_goal(goal.goal_id)
                    before_parent = self.store.get_goal(parent.goal_id)
                    before_dependency = self.store.get_goal(dependency.goal_id)
                    before_facts = self.store.list_facts(goal.goal_id)
                    with self.assertRaisesRegex(
                        ConflictError,
                        "terminal parent|cancelled or superseded dependency",
                    ):
                        self.service.goal_reopen(
                            goal.goal_id,
                            "Resume with repaired relationships",
                            "Start a new linked goal",
                            before_goal.lifecycle_revision,
                        )
                    self.assertEqual(self.store.get_goal(goal.goal_id), before_goal)
                    self.assertEqual(self.store.list_facts(goal.goal_id), before_facts)
                    self.assertEqual(self.store.get_goal(parent.goal_id), before_parent)
                    self.assertEqual(self.store.get_goal(dependency.goal_id), before_dependency)
                    self.assertEqual(before_goal.parent_goal_id, parent.goal_id)
                    self.assertEqual(before_goal.depends_on_goal_ids, (dependency.goal_id,))

                    next_parent = self.service.goal_start(
                        "Continuation parent",
                        (SuccessCriterion("next-parent", "Continuation parent passes"),),
                    )
                    continuation = self.service.goal_start(
                        "Continuation dependency",
                        (SuccessCriterion("next-goal", "Continuation passes"),),
                        parent_goal_id=next_parent.goal_id,
                        depends_on_goal_ids=(dependency_replacement.goal_id,),
                    )
                    self.assertEqual(continuation.status, GoalStatus.ACTIVE)
                    self.assertEqual(continuation.parent_goal_id, next_parent.goal_id)
                    self.assertEqual(
                        continuation.depends_on_goal_ids,
                        (dependency_replacement.goal_id,),
                    )

    def test_every_reopen_order_obeys_nested_parent_and_dependency_gates(self) -> None:
        """Exhaust all four-goal reopen orders and preserve facts on rejected edges."""

        labels = ("root", "middle", "leaf", "dependency")
        for index, order in enumerate(permutations(labels)):
            with self.subTest(order=order):
                scenario = f"reopen-order-{index}"
                goals = self._completed_reopen_order_fixture(scenario)
                expected_status = {
                    label: GoalStatus.COMPLETE for label in goals
                }
                expected_revision = {
                    label: goal.lifecycle_revision for label, goal in goals.items()
                }
                for label in order:
                    self._assert_reopen_order_step(
                        scenario,
                        label,
                        goals,
                        expected_status,
                        expected_revision,
                    )

    def test_criteria_amendment_is_versioned_and_starts_a_fresh_evidence_epoch(self) -> None:
        original_criteria = self.goal.success_criteria
        old_proofs = (
            self.verify("unit", "Original unit criteria verified"),
            self.verify("probe", "Original probe criteria verified"),
        )
        amended_criteria = (
            SuccessCriterion("unit", "Updated unit suite passes"),
            SuccessCriterion("probe", "Updated readiness probe passes"),
            SuccessCriterion("release", "Release smoke test passes"),
        )

        amended = self.service.goal_amend_criteria(
            GoalCriteriaAmended(
                goal_id=self.goal.goal_id,
                expected_revision=1,
                success_criteria=amended_criteria,
                reason="The owner added an explicit release smoke criterion",
                next_action="Run all three updated checks",
            )
        )

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(amended.criteria_revision, 2)
        self.assertEqual(amended.success_criteria, amended_criteria)
        self.assertEqual(
            [item.status for item in snapshot.criteria],
            [CriterionStatus.OPEN, CriterionStatus.OPEN, CriterionStatus.OPEN],
        )
        self.assertEqual(
            [version.criteria for version in snapshot.criteria_history],
            [original_criteria, amended_criteria],
        )
        self.assertEqual(snapshot.criteria_history[1].reason,
                         "The owner added an explicit release smoke criterion")
        self.assertTrue(
            all(fact.fact_id in {item.fact_id for item in snapshot.facts} for fact in old_proofs)
        )
        self.assertTrue(
            any(fact.kind is FactKind.CRITERIA_AMENDED for fact in snapshot.facts)
        )

        with self.assertRaisesRegex(ConflictError, "revision changed"):
            self.service.goal_amend_criteria(
                GoalCriteriaAmended(
                    goal_id=self.goal.goal_id,
                    expected_revision=1,
                    success_criteria=amended_criteria,
                    reason="Stale concurrent edit",
                    next_action="Reload the goal first",
                )
            )

        self.assertEqual(
            self.service.goal_finish(self.goal.goal_id, "Claimed complete").status,
            GoalStatus.OPEN,
        )
        for criterion in amended_criteria:
            self.service.goal_fact(
                self.goal.goal_id,
                FactKind.VERIFICATION,
                f"Verified {criterion.criterion_id} under revision two",
                criterion_id=criterion.criterion_id,
                evidence=(self.proof(f"revision-two-{criterion.criterion_id}"),),
            )
        self.assertEqual(
            self.service.goal_finish(
                self.goal.goal_id, "All amended criteria have fresh evidence"
            ).status,
            GoalStatus.COMPLETE,
        )
