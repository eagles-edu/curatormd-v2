"""GoalCompletion regressions."""

from __future__ import annotations

from lifecycle_test_support import LifecycleTestSupport

from curatormd_v2 import (
    ConflictError,
    Fact,
    FactKind,
    GoalStatus,
    Materiality,
    SuccessCriterion,
    GoalTransitionRequest,
)
from curatormd_v2.service import SDEAssessmentRequest


class GoalCompletionTests(LifecycleTestSupport):
    """Cover goalcompletion invariants."""

    def test_single_check_completes_from_local_test_result(self) -> None:
        """A passing local test is enough for an ordinary one-check task."""

        goal = self.service.goal_start(
            "Fix a small task",
            (SuccessCriterion("works", "The change works"),),
        )
        result_fact, _ = self.service.goal_fact(
            goal.goal_id,
            FactKind.CHANGE,
            "The change passed `uv run pytest tests/test_small.py`.",
        )
        completed = self.service.goal_finish(
            goal.goal_id,
            "Checks passed: `uv run pytest tests/test_small.py` passed.",
        )

        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        snapshot = self.service.goal_status(goal.goal_id)
        self.assertEqual(snapshot.criteria[0].status.value, "verified")
        self.assertEqual(len(snapshot.criteria[0].verification_fact_ids), 1)
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The checked task is ready for owner review.",
                (result_fact.fact_id,),
                "The simple task completed after its check passed.",
                "Retrieve the task outcome and its check result.",
            )
        )
        self.assertEqual(candidate.status.value, "pending_review")

    def test_single_check_completes_from_owner_confirmation(self) -> None:
        """An explicit owner confirmation is sufficient task evidence."""

        goal = self.service.goal_start(
            "Confirm a small task",
            (SuccessCriterion("works", "The change works"),),
        )
        completed = self.service.goal_finish(
            goal.goal_id,
            "Owner confirmed: it works and lints cleanly.",
        )

        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertEqual(
            self.service.goal_status(goal.goal_id).criteria[0].status.value,
            "verified",
        )

    def test_single_check_does_not_complete_from_generic_claim(self) -> None:
        """A generic completion claim still leaves the check open."""

        goal = self.service.goal_start(
            "Finish a small task",
            (SuccessCriterion("works", "The change works"),),
        )

        opened = self.service.goal_finish(goal.goal_id, "Claimed complete")

        self.assertEqual(opened.status, GoalStatus.OPEN)
        self.assertEqual(
            self.service.goal_status(goal.goal_id).criteria[0].status.value,
            "open",
        )

    def test_successful_completion_facts_are_compact_single_bullets(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        self.service.goal_finish(self.goal.goal_id, "Complete")
        for fact in self.store.list_facts(self.goal.goal_id):
            self.assertNotIn("\n", fact.bullet)
            self.assertLessEqual(len(fact.bullet), 1000)
            self.assertTrue(fact.as_bullet().startswith("- "))

    def test_completed_child_oneoff_can_be_assessed_while_parent_is_active(self) -> None:
        """Keep a bounded child task's completion and SDE facts independent."""

        parent = self.service.goal_start(
            "Complete the broader alpha",
            (SuccessCriterion("alpha", "The broader alpha is accepted"),),
        )
        child = self.service.goal_start(
            "Create the repository README",
            (SuccessCriterion("readme", "The README meets its requested sections"),),
            parent_goal_id=parent.goal_id,
        )
        change, _ = self.service.goal_fact(
            child.goal_id,
            FactKind.CHANGE,
            "Created the requested repository README sections.",
        )
        verification, _ = self.service.goal_fact(
            child.goal_id,
            FactKind.VERIFICATION,
            "The README sections were checked against the request.",
            criterion_id="readme",
            evidence=(self.proof("readme-child"),),
        )

        completed_child = self.service.goal_finish(
            child.goal_id,
            "The README one-off checks pass.",
            expected_lifecycle_revision=child.lifecycle_revision,
        )
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                child.goal_id,
                Materiality.IMPLEMENTATION,
                "The completed README task is presented for owner review.",
                (change.fact_id, verification.fact_id),
                impact="The repository now has the requested README content.",
                retrieval_value="Review the README task outcome independently of the broader alpha.",
            )
        )

        self.assertEqual(completed_child.status, GoalStatus.COMPLETE)
        self.assertEqual(parent.status, GoalStatus.ACTIVE)
        self.assertEqual(candidate.goal_id, child.goal_id)
        self.assertEqual(candidate.fact_ids, (change.fact_id, verification.fact_id))

    def test_goal_list_can_filter_open_and_complete_goals(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        self.service.goal_finish(self.goal.goal_id, "Complete")
        open_goal = self.service.goal_start(
            "Another task", (SuccessCriterion("next", "next thing passes"),)
        )
        self.service.goal_finish(open_goal.goal_id, "Claimed complete")
        completed = self.service.goal_list((GoalStatus.COMPLETE,))
        opened = self.service.goal_list((GoalStatus.OPEN,))
        self.assertEqual([item.goal.goal_id for item in completed], [self.goal.goal_id])
        self.assertEqual([item.goal.goal_id for item in opened], [open_goal.goal_id])

    def test_failed_transition_rolls_back_facts_and_goal_state_atomically(self) -> None:
        other_goal = self.service.goal_start(
            "Other goal", (SuccessCriterion("other", "other criterion"),)
        )
        misplaced_fact = Fact(
            goal_id=other_goal.goal_id,
            kind=FactKind.OUTCOME,
            bullet="Must not be attached to the first goal",
        )
        with self.assertRaises(ConflictError):
            self.store.transition_goal(
                GoalTransitionRequest(
                    goal_id=self.goal.goal_id,
                    status=GoalStatus.COMPLETE,
                    next_action=None,
                    facts=(misplaced_fact,),
                    expected_lifecycle_revision=1,
                )
            )
        self.assertEqual(self.store.get_goal(self.goal.goal_id).status, GoalStatus.ACTIVE)
        self.assertEqual(self.store.list_facts(self.goal.goal_id), ())
