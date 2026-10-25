"""Shared expected lifecycle status groups for focused test models."""

from curatormd_v2 import GoalStatus

UNFINISHED_GOAL_STATUSES = frozenset(
    {
        GoalStatus.PLANNED,
        GoalStatus.ACTIVE,
        GoalStatus.OPEN,
        GoalStatus.BLOCKED,
        GoalStatus.DEFERRED,
    }
)
FACT_ACCEPTING_GOAL_STATUSES = frozenset(
    {
        GoalStatus.ACTIVE,
        GoalStatus.OPEN,
        GoalStatus.BLOCKED,
        GoalStatus.DEFERRED,
    }
)
FINISHABLE_GOAL_STATUSES = FACT_ACCEPTING_GOAL_STATUSES | {GoalStatus.COMPLETE}
