"""Typed inputs for multi-field atomic goal-store operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from .domain_enums import ArtifactStatus, PurgeOutcome
from .events import EventEnvelope
from .models import Fact, GoalStatus, SuccessCriterion


@dataclass(frozen=True, slots=True)
class PurgeTargetResult:
    """Observed outcome and content-free error for one purge attempt."""

    status: ArtifactStatus
    error: str | None
    outcome: PurgeOutcome | None = None


@dataclass(frozen=True, slots=True)
class ProjectDrainEffectContext:
    """Bind one admitted drain event to its trusted caller context."""

    event: EventEnvelope
    caller_subject: str
    caller_profile: str | None


@dataclass(frozen=True, slots=True)
class SuspendedProcessedEventEpochRequest:
    """Exact event and repository identity for an authorized replay lookup."""

    subject_id: str
    project_id: str
    event_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int


@dataclass(frozen=True, slots=True)
# Pylint: these fields bind the stored disposition to its exact evidence.
class TerminalEventDispositionStoreRequest:  # pylint: disable=too-many-instance-attributes
    """Human-reviewed terminal decision bound to one event and source fence."""

    project_id: str
    event_id: str
    transition_id: str
    actor_id: str
    rationale: str
    expected_binding_revision: int
    expected_source_epoch: int
    expected_payload_sha256: str


class ConsumerDrainStoreRequest(NamedTuple):
    """Exact reviewed inventory and trusted caller fields for drain setup."""

    project_id: str
    transition_id: str
    actor_id: str
    caller_subject: str
    caller_profile: str | None
    expected_revision: int
    expected_inventory_sha256: str
    lifetime_seconds: int


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
