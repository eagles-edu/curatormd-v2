"""Typed inputs for multi-field atomic goal-store operations."""

from __future__ import annotations

from dataclasses import dataclass

from .events import EventEnvelope
from .models import Fact, GoalStatus, SuccessCriterion


@dataclass(frozen=True, slots=True)
class ProjectDrainEffectContext:
    """Bind one admitted drain event to its trusted caller context."""

    event: EventEnvelope
    caller_subject: str
    caller_profile: str | None


@dataclass(frozen=True, slots=True)
class GoalTransitionRequest:
    """Expected-version lifecycle transition and its atomic fact batch."""

    goal_id: str
    status: GoalStatus
    next_action: str | None
    facts: tuple[Fact, ...]
    expected_lifecycle_revision: int
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class GoalRetirementRequest:
    """Cancellation or supersession inputs for one atomic retirement."""

    goal_id: str
    status: GoalStatus
    reason: str
    fact: Fact
    project_id: str | None = None
    replacement_goal_id: str | None = None


@dataclass(frozen=True, slots=True)
class GoalCriteriaRevisionExpectation:
    """Expected criteria and optional lifecycle revisions for an amendment."""

    criteria_revision: int
    lifecycle_revision: int | None = None


@dataclass(frozen=True, slots=True)
class GoalCriteriaAmendmentRequest:
    """Criteria replacement and its lifecycle fact, scoped to one project."""

    goal_id: str
    expected_revisions: GoalCriteriaRevisionExpectation
    criteria: tuple[SuccessCriterion, ...]
    reason: str
    next_action: str
    fact: Fact
    project_id: str | None = None
