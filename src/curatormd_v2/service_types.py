"""Shared service request, receipt, and report types."""

from __future__ import annotations

__all__ = (
    "EvidenceGateError",
    "PurgeTargetStatus",
    "SDEAssessmentRequest",
    "_GoalStartOptions",
    "_GoalFactOptions",
    "_PreparedEvent",
    "_GoalReportSnapshot",
    "_GoalReportRelations",
    "_attestation_lease_end",
    "_timestamp_age_seconds",
    "_timestamp_delay_seconds",
    "_purge_recovery_action",
)

from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
from typing import TypedDict
from .models import (
    ArtifactStatus,
    AuditReceipt,
    EvidenceAttestation,
    EvidenceRef,
    Fact,
    PurgeOutcome,
    PurgeTargetFields,
    GoalBulletProjection,
    GoalCard,
    GoalSnapshot,
    GoalStatus,
    Materiality,
)
from .record_validation import parse_optional_aware_timestamp


class EvidenceGateError(ValueError):
    """A proposed durable conclusion is not supported by direct evidence."""


class _GoalStartOptions(TypedDict, total=False):
    """Precisely type the optional keyword fields accepted by goal_start."""

    owner: str | None
    checklist_id: str | None
    checklist_version: str | None
    checklist_source_text: str | None
    parent_goal_id: str | None
    depends_on_goal_ids: tuple[str, ...]
    goal_id: str | None
    initial_status: GoalStatus
    next_action: str | None
    source_event_id: str | None


class _GoalFactOptions(TypedDict, total=False):
    """Precisely type optional evidence fields accepted by goal_fact."""

    criterion_id: str | None
    evidence: tuple[EvidenceRef, ...]
    fact_id: str | None


@dataclass(frozen=True, slots=True)
# Pylint: these fields preserve the per-target purge status response schema.
class PurgeTargetStatus(PurgeTargetFields):  # pylint: disable=too-many-instance-attributes
    """Current retry state for one artifact named by an audit receipt."""

    next_attempt_in_seconds: int | None
    age_seconds: int | None
    last_attempt_age_seconds: int | None
    safe_recovery_action: str
    hold_created_at: str | None
    hold_created_by: str | None
    hold_released_at: str | None
    hold_released_by: str | None
    hold_release_rationale: str | None
    approval_stale: bool = False
    outcome: PurgeOutcome | None = None


@dataclass(frozen=True, slots=True)
class _PreparedEvent:
    """Evidence and fact context gathered before the event commit transaction."""

    prior_fact_ids: frozenset[str]
    verified_goal_snapshot: GoalCard | None = None
    prepared_fact: Fact | None = None
    finish_snapshot: (
        tuple[
            GoalCard,
            tuple[Fact, ...],
            dict[str, tuple[EvidenceAttestation, ...]],
        ]
        | None
    ) = None
    expected_finish_revision: int | None = None


def _attestation_lease_end(
    attestations: tuple[EvidenceAttestation, ...],
) -> datetime:
    """Return the limiting lease expiry for one complete evidence proof."""

    valid_untils = tuple(
        parse_optional_aware_timestamp(item.valid_until) for item in attestations
    )
    if not valid_untils or any(item is None for item in valid_untils):
        return datetime.min.replace(tzinfo=UTC)
    return min(item for item in valid_untils if item is not None)


@dataclass(frozen=True, slots=True)
class _GoalReportSnapshot:
    """Goal-local data loaded for one bounded status report."""

    snapshot: GoalSnapshot
    projection: GoalBulletProjection
    pending_sde_total: int
    pending_receipt_total: int


@dataclass(frozen=True, slots=True)
class _GoalReportRelations:
    """Bounded child/dependency/receipt pages and their exact aggregates."""

    child_total: int
    children: tuple[GoalCard, ...]
    open_child_total: int
    dependencies: tuple[GoalCard, ...]
    receipt_total: int
    receipts: tuple[AuditReceipt, ...]
    purge_status_counts: tuple[tuple[str, int], ...]


def _timestamp_age_seconds(
    timestamp: str, now: datetime
) -> int | None:
    """Return nonnegative age for a valid timezone-aware durable timestamp."""

    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return max(0, int((now - parsed.astimezone(UTC)).total_seconds()))


def _timestamp_delay_seconds(
    timestamp: str | None, now: datetime
) -> int | None:
    """Return remaining delay for a valid timezone-aware retry deadline."""

    if timestamp is None:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return max(0, int((parsed.astimezone(UTC) - now).total_seconds()))


def _purge_recovery_action(
    receipt: AuditReceipt, status: ArtifactStatus, approval_stale: bool = False
) -> str:
    """Suggest only the next configured action that satisfies current gates."""

    if status is ArtifactStatus.PURGED:
        return "none"
    if status is ArtifactStatus.HELD:
        return "release_artifact_hold"
    if approval_stale:
        return "fresh_inventory_review"
    if not receipt.artifact_inventory_complete:
        return "artifact_inventory_complete"
    if not receipt.canonical_persisted:
        return "goal_persist"
    return "retry_pending_purges"


@dataclass(frozen=True, slots=True)
class SDEAssessmentRequest:
    """Bounded inputs used to validate and stage one SDE proposal."""

    goal_id: str
    materiality: Materiality
    rationale: str
    fact_ids: tuple[str, ...]
    impact: str | None
    retrieval_value: str | None
