"""GoalCompletion regressions."""

from __future__ import annotations

from lifecycle_test_support import LifecycleTestSupport

from curatormd_v2 import (
    ConflictError,
    Fact,
    FactKind,
    GoalStatus,
    SuccessCriterion,
    GoalTransitionRequest,
)


class GoalCompletionTests(LifecycleTestSupport):
    """Cover goalcompletion invariants."""

    def test_successful_completion_facts_are_compact_single_bullets(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        self.service.goal_finish(self.goal.goal_id, "Complete")
        for fact in self.store.list_facts(self.goal.goal_id):
            self.assertNotIn("\n", fact.bullet)
            self.assertLessEqual(len(fact.bullet), 1000)
            self.assertTrue(fact.as_bullet().startswith("- "))

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
