"""Versioned, bounded lifecycle event contracts for Curator V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import json
import re
from typing import TypeAlias, cast

from .models import (
    MAX_EVIDENCE_REFERENCES,
    MAX_CRITERIA_REVISIONS,
    MAX_GOAL_DEPENDENCIES,
    MAX_SUCCESS_CRITERIA,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    GoalStatus,
    SuccessCriterion,
    utc_now,
)
from .content_safety import validate_safe_text
from .validation import is_exact_int


EVENT_SCHEMA_VERSION = 1
MAX_EVENT_BYTES = 16 * 1024
_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def _validate_lifecycle_revision(revision: int | None) -> None:
    if revision is not None and (not is_exact_int(revision) or revision < 1):
        raise ValueError("expected_lifecycle_revision must be a positive integer")


class EventKind(StrEnum):
    """Supported lifecycle event names for schema version 1."""

    GOAL_STARTED = "goal.started"
    GOAL_ACTIVATED = "goal.activated"
    FACT_RECORDED = "fact.recorded"
    GOAL_ACTIVITY_OBSERVED = "goal.activity_observed"
    GOAL_FINISH_REQUESTED = "goal.finish_requested"
    GOAL_DEFERRED = "goal.deferred"
    GOAL_BLOCKED = "goal.blocked"
    GOAL_REOPENED = "goal.reopened"
    GOAL_CRITERIA_AMENDED = "goal.criteria_amended"
    GOAL_CANCELLED = "goal.cancelled"
    GOAL_SUPERSEDED = "goal.superseded"


class EventInboxStatus(StrEnum):
    """Durable inbox processing state, separate from goal state."""

    RECEIVED = "received"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    PROCESSED = "processed"


class EventDisposition(StrEnum):
    """Durable outcome for an event accepted into the project ledger."""

    APPLIED = "applied"
    SUPPRESSED_NONACTIVE_GOAL = "suppressed_nonactive_goal"


@dataclass(frozen=True, slots=True)
class EventInboxReceipt:
    """Compact durable acceptance/processing receipt for one project event."""

    project_id: str
    event_id: str
    payload_sha256: str
    status: EventInboxStatus
    received_at: str
    processed_at: str | None = None
    last_error_code: str | None = None
    attempts: int = 0
    next_attempt_at: str | None = None
    disposition: EventDisposition | None = None


@dataclass(frozen=True, slots=True)
class EventQueueStatus:
    """Aggregate-only router queue health without exposing event contents."""

    received_count: int
    failed_count: int
    quarantined_count: int
    oldest_pending_received_at: str | None
    oldest_pending_age_seconds: int | None
    claimed_count: int
    expired_claim_count: int


@dataclass(frozen=True, slots=True)
class GoalStarted:
    """A caller-provided goal identity and its unchanged success criteria."""

    goal_id: str
    problem: str
    success_criteria: tuple[SuccessCriterion, ...]
    owner: str | None = None
    checklist_id: str | None = None
    checklist_version: str | None = None
    checklist_source_text: str | None = None
    parent_goal_id: str | None = None
    depends_on_goal_ids: tuple[str, ...] = ()
    initial_status: GoalStatus = GoalStatus.ACTIVE
    next_action: str | None = None

    def __post_init__(self) -> None:
        _validate_goal_started_text(self)
        _validate_goal_started_problem_and_criteria(self)
        _validate_goal_started_status(self)
        _validate_goal_started_relations(self)
        _validate_goal_started_checklist_snapshot(self)


def _validate_goal_started_text(event: GoalStarted) -> None:
    """Apply safe-text checks before evaluating any other event invariant."""

    validate_safe_text(event.problem, "goal_started.problem")
    for field_name, value in (
        ("goal_started.owner", event.owner),
        ("goal_started.checklist_id", event.checklist_id),
        ("goal_started.checklist_source_text", event.checklist_source_text),
        ("goal_started.next_action", event.next_action),
    ):
        if value is not None:
            validate_safe_text(value, field_name)


def _validate_goal_started_problem_and_criteria(event: GoalStarted) -> None:
    """Validate goal identity, problem statement, and criterion count."""

    if not event.goal_id.strip() or not event.problem.strip():
        raise ValueError("goal_id and problem must not be empty")
    if len(event.problem) > 2000 or "\n" in event.problem or "\r" in event.problem:
        raise ValueError("problem must be a compact statement of at most 2000 characters")
    if event.next_action is not None and (
        not event.next_action.strip()
        or len(event.next_action) > 1000
        or "\n" in event.next_action
        or "\r" in event.next_action
    ):
        raise ValueError("next_action must be a single line of at most 1000 characters")
    if not event.success_criteria:
        raise ValueError("at least one success criterion is required")
    if len(event.success_criteria) > MAX_SUCCESS_CRITERIA:
        raise ValueError(
            f"success criteria exceed the limit of {MAX_SUCCESS_CRITERIA}"
        )


def _validate_goal_started_status(event: GoalStarted) -> None:
    """Normalize the initial status before checking relationship fields."""

    try:
        initial_status = GoalStatus(event.initial_status)
    except ValueError as exc:
        raise ValueError("initial_status must be planned or active") from exc
    if initial_status not in {GoalStatus.PLANNED, GoalStatus.ACTIVE}:
        raise ValueError("initial_status must be planned or active")
    object.__setattr__(event, "initial_status", initial_status)


def _validate_goal_started_relations(event: GoalStarted) -> None:
    """Validate criterion uniqueness and parent/dependency relationships."""

    criterion_ids = [item.criterion_id for item in event.success_criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise ValueError("criterion IDs must be unique within a goal")
    if event.parent_goal_id == event.goal_id:
        raise ValueError("a goal cannot be its own parent")
    if len(event.depends_on_goal_ids) != len(set(event.depends_on_goal_ids)):
        raise ValueError("goal dependencies must be unique")
    if len(event.depends_on_goal_ids) > MAX_GOAL_DEPENDENCIES:
        raise ValueError(
            f"goal dependencies exceed the limit of {MAX_GOAL_DEPENDENCIES}"
        )
    if event.goal_id in event.depends_on_goal_ids:
        raise ValueError("a goal cannot depend on itself")


def _validate_goal_started_checklist_snapshot(event: GoalStarted) -> None:
    """Require checklist source text and revision metadata as one tuple."""

    snapshot = (event.checklist_version, event.checklist_source_text)
    if any(value is not None for value in snapshot):
        if event.checklist_id is None or any(value is None for value in snapshot):
            raise ValueError(
                "checklist snapshot requires checklist_id, version, and source text"
            )
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", event.checklist_version or ""):
            raise ValueError("checklist_version must be a SHA-256 source revision")
        source_text = event.checklist_source_text or ""
        if not source_text.strip() or len(source_text) > 4000:
            raise ValueError("checklist source text must contain 1-4000 characters")
        if "\n" in source_text or "\r" in source_text:
            raise ValueError("checklist source text must be one exact item line")


@dataclass(frozen=True, slots=True)
class GoalActivated:
    """Explicitly accept planned work for execution at a known revision."""

    goal_id: str
    reason: str
    expected_lifecycle_revision: int

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_activated.reason")
        if not self.goal_id.strip() or not self.reason.strip():
            raise ValueError("activation requires a goal ID and acceptance reason")
        if len(self.reason) > 500 or "\n" in self.reason or "\r" in self.reason:
            raise ValueError("activation reason must be one line of at most 500 characters")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class FactRecorded:
    """A stable fact identity makes transport retries safely recognizable."""

    goal_id: str
    fact_id: str
    kind: FactKind
    bullet: str
    criterion_id: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        validate_safe_text(self.bullet, "fact_recorded.bullet")
        if not self.goal_id.strip() or not self.fact_id.strip():
            raise ValueError("goal_id and fact_id must not be empty")
        if not self.bullet.strip() or len(self.bullet) > 1000:
            raise ValueError("fact bullet must contain 1-1000 characters")
        if "\n" in self.bullet or "\r" in self.bullet:
            raise ValueError("fact bullet must be a single compact line")
        if self.kind is FactKind.REOPENED:
            raise ValueError("reopened facts must use the goal.reopened event")
        if self.kind is FactKind.CRITERIA_AMENDED:
            raise ValueError("criteria-amended facts must use goal.criteria_amended")
        if self.kind in {FactKind.CANCELLED, FactKind.SUPERSEDED}:
            raise ValueError("retirement facts must use their matching goal event")
        if self.kind is FactKind.VERIFICATION and not self.evidence:
            raise ValueError("verification events require evidence references")
        if len(self.evidence) > MAX_EVIDENCE_REFERENCES:
            raise ValueError(
                f"evidence references exceed the limit of {MAX_EVIDENCE_REFERENCES}"
            )
        if self.kind is FactKind.VERIFICATION and self.criterion_id is None:
            raise ValueError("verification events must identify a success criterion")


@dataclass(frozen=True, slots=True)
class GoalActivityObserved:
    """Status-independent Hermes activity; the processor decides whether to append it."""

    goal_id: str
    fact_id: str
    kind: FactKind
    bullet: str

    def __post_init__(self) -> None:
        validate_safe_text(self.bullet, "goal_activity_observed.bullet")
        if not self.goal_id.strip() or not self.fact_id.strip():
            raise ValueError("goal_id and fact_id must not be empty")
        if self.kind not in {FactKind.INTENT, FactKind.CHANGE, FactKind.OPEN_GATE}:
            raise ValueError("goal activity may only record intent, change, or open_gate")
        if not self.bullet.strip() or len(self.bullet) > 1000:
            raise ValueError("activity bullet must contain 1-1000 characters")
        if "\n" in self.bullet or "\r" in self.bullet:
            raise ValueError("activity bullet must be a single compact line")


@dataclass(frozen=True, slots=True)
class GoalFinishRequested:
    """A request to evaluate completion, not proof of completion."""

    goal_id: str
    completion_claim: str
    expected_lifecycle_revision: int | None = None

    def __post_init__(self) -> None:
        validate_safe_text(self.completion_claim, "goal_finish.completion_claim")
        if not self.goal_id.strip() or not self.completion_claim.strip():
            raise ValueError("goal_id and completion_claim must not be empty")
        if len(self.completion_claim) > 980:
            raise ValueError("completion claim exceeds 980 characters")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class GoalDeferred:
    """A request to defer a goal with an explicit follow-up action."""

    goal_id: str
    reason: str
    next_action: str
    expected_lifecycle_revision: int | None = None

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_deferred.reason")
        validate_safe_text(self.next_action, "goal_deferred.next_action")
        if not self.goal_id.strip() or not self.reason.strip() or not self.next_action.strip():
            raise ValueError("deferred event requires goal_id, reason, and next_action")
        if len(self.next_action) > 1000:
            raise ValueError("next_action exceeds 1000 characters")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class GoalBlocked:
    """A request to record a dependency and its recovery path."""

    goal_id: str
    dependency: str
    recovery: str
    expected_lifecycle_revision: int | None = None

    def __post_init__(self) -> None:
        validate_safe_text(self.dependency, "goal_blocked.dependency")
        validate_safe_text(self.recovery, "goal_blocked.recovery")
        if not self.goal_id.strip() or not self.dependency.strip() or not self.recovery.strip():
            raise ValueError("blocked event requires goal_id, dependency, and recovery")
        if len(self.recovery) > 1000:
            raise ValueError("recovery exceeds 1000 characters")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class GoalReopened:
    """Reopen a completed goal as a new evidence epoch."""

    goal_id: str
    reason: str
    next_action: str
    expected_lifecycle_revision: int | None = None

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_reopened.reason")
        validate_safe_text(self.next_action, "goal_reopened.next_action")
        if not self.goal_id.strip() or not self.reason.strip() or not self.next_action.strip():
            raise ValueError("reopen requires goal_id, reason, and next_action")
        reason = self.reason.strip()
        next_action = self.next_action.strip()
        if len(reason) + len(next_action) + 18 > 1000:
            raise ValueError("reopen reason and next_action exceed the fact bullet limit")
        if any("\n" in value or "\r" in value for value in (reason, next_action)):
            raise ValueError("reopen reason and next_action must be single lines")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class GoalCriteriaAmended:
    """Explicitly replace a goal contract using optimistic revision control."""

    goal_id: str
    expected_revision: int
    success_criteria: tuple[SuccessCriterion, ...]
    reason: str
    next_action: str
    expected_lifecycle_revision: int | None = None

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_criteria_amended.reason")
        validate_safe_text(self.next_action, "goal_criteria_amended.next_action")
        if not self.goal_id.strip() or not self.reason.strip() or not self.next_action.strip():
            raise ValueError("criteria amendment requires goal_id, reason, and next_action")
        if not is_exact_int(self.expected_revision) or self.expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if self.expected_revision >= MAX_CRITERIA_REVISIONS:
            raise ValueError(
                f"criteria history is limited to {MAX_CRITERIA_REVISIONS} revisions"
            )
        if not self.success_criteria or len(self.success_criteria) > MAX_SUCCESS_CRITERIA:
            raise ValueError("amended criteria must contain 1-32 success criteria")
        ids = [item.criterion_id for item in self.success_criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("amended criterion IDs must be unique")
        if len(self.reason) > 500 or len(self.next_action) > 500:
            raise ValueError("amendment reason and next_action must be at most 500 characters")
        if any("\n" in item or "\r" in item for item in (self.reason, self.next_action)):
            raise ValueError("amendment reason and next_action must be single lines")
        _validate_lifecycle_revision(self.expected_lifecycle_revision)


@dataclass(frozen=True, slots=True)
class GoalCancelled:
    """End an unfinished goal without implying that its criteria passed."""

    goal_id: str
    reason: str

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_cancelled.reason")
        if not self.goal_id.strip() or not self.reason.strip():
            raise ValueError("cancellation requires goal_id and reason")
        if len(self.reason) > 500 or "\n" in self.reason or "\r" in self.reason:
            raise ValueError("cancellation reason must be one line of at most 500 characters")


@dataclass(frozen=True, slots=True)
class GoalSuperseded:
    """Replace an unfinished goal with an existing same-project successor."""

    goal_id: str
    replacement_goal_id: str
    reason: str

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "goal_superseded.reason")
        if not self.goal_id.strip() or not self.replacement_goal_id.strip():
            raise ValueError("supersession requires both goal IDs")
        if self.goal_id == self.replacement_goal_id:
            raise ValueError("a goal cannot supersede itself")
        if not self.reason.strip():
            raise ValueError("supersession requires a reason")
        if len(self.reason) > 500 or "\n" in self.reason or "\r" in self.reason:
            raise ValueError("supersession reason must be one line of at most 500 characters")


EventPayload: TypeAlias = (
    GoalStarted
    | GoalActivated
    | FactRecorded
    | GoalActivityObserved
    | GoalFinishRequested
    | GoalDeferred
    | GoalBlocked
    | GoalReopened
    | GoalCriteriaAmended
    | GoalCancelled
    | GoalSuperseded
)


_EVENT_TYPES: dict[type[object], EventKind] = {
    GoalStarted: EventKind.GOAL_STARTED,
    GoalActivated: EventKind.GOAL_ACTIVATED,
    FactRecorded: EventKind.FACT_RECORDED,
    GoalActivityObserved: EventKind.GOAL_ACTIVITY_OBSERVED,
    GoalFinishRequested: EventKind.GOAL_FINISH_REQUESTED,
    GoalDeferred: EventKind.GOAL_DEFERRED,
    GoalBlocked: EventKind.GOAL_BLOCKED,
    GoalReopened: EventKind.GOAL_REOPENED,
    GoalCriteriaAmended: EventKind.GOAL_CRITERIA_AMENDED,
    GoalCancelled: EventKind.GOAL_CANCELLED,
    GoalSuperseded: EventKind.GOAL_SUPERSEDED,
}


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Project-scoped transport envelope; it is not an authorization token."""

    event_id: str
    project_id: str
    payload: EventPayload
    occurred_at: str = field(default_factory=utc_now)
    schema_version: int = EVENT_SCHEMA_VERSION
    source_id: str = "unspecified"
    source_sequence: int | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip() or len(self.event_id) > 128:
            raise ValueError("event_id must contain 1-128 characters")
        validate_safe_text(self.event_id, "event_id")
        if not _PROJECT_ID_RE.fullmatch(self.project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported event schema version: {self.schema_version}")
        if not _SOURCE_ID_RE.fullmatch(self.source_id):
            raise ValueError("source_id must be a bounded opaque identifier")
        if self.source_sequence is not None and (
            isinstance(self.source_sequence, bool) or self.source_sequence < 1
        ):
            raise ValueError("source_sequence must be a positive integer when supplied")
        if self.source_sequence is not None and self.source_id == "unspecified":
            raise ValueError("source_sequence requires an explicit source_id")
        if type(self.payload) not in _EVENT_TYPES:
            raise ValueError("unsupported event payload type")
        try:
            parsed = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("occurred_at must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")

    @property
    def event_kind(self) -> EventKind:
        """Return the event name corresponding to this typed payload."""

        return _EVENT_TYPES[type(self.payload)]

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible envelope mapping."""

        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "project_id": self.project_id,
            "source_id": self.source_id,
            "source_sequence": self.source_sequence,
            "occurred_at": self.occurred_at,
            "event_type": self.event_kind.value,
            "payload": _payload_to_dict(self.payload),
        }

    def to_json(self) -> str:
        """Serialize compactly and enforce the encoded event-size limit."""

        serialized = json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        if _utf8_length(serialized) > MAX_EVENT_BYTES:
            raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
        return serialized

    @classmethod
    def from_json(cls, serialized: str) -> EventEnvelope:
        """Parse a strict version-1 event, rejecting ambiguous JSON fields."""

        if _utf8_length(serialized) > MAX_EVENT_BYTES:
            raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
        try:
            value = json.loads(serialized, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise ValueError("event must be valid UTF-8 JSON") from exc
        envelope = _envelope_from_dict(value)
        # Keep encoder and decoder limits identical, including normalized JSON.
        envelope.to_json()
        return envelope


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _require_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise ValueError(f"{name} must be an object with string keys")
    return cast(dict[str, object], value)


def _require_fields(
    value: dict[str, object],
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        raise ValueError(f"invalid fields; missing={sorted(missing)}, extra={sorted(extra)}")


def _string(value: object, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _optional_revision(value: object) -> int | None:
    if value is None:
        return None
    if not is_exact_int(value) or value < 1:
        raise ValueError("expected_lifecycle_revision must be a positive integer")
    return value


def _payload_to_dict(payload: EventPayload) -> dict[str, object]:
    if isinstance(payload, GoalStarted):
        return {
            "goal_id": payload.goal_id,
            "problem": payload.problem,
            "success_criteria": [
                {"criterion_id": item.criterion_id, "description": item.description}
                for item in payload.success_criteria
            ],
            "owner": payload.owner,
            "checklist_id": payload.checklist_id,
            "checklist_version": payload.checklist_version,
            "checklist_source_text": payload.checklist_source_text,
            "parent_goal_id": payload.parent_goal_id,
            "depends_on_goal_ids": list(payload.depends_on_goal_ids),
            "initial_status": payload.initial_status.value,
            "next_action": payload.next_action,
        }
    if isinstance(payload, GoalActivated):
        return {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, FactRecorded):
        return {
            "goal_id": payload.goal_id,
            "fact_id": payload.fact_id,
            "kind": payload.kind.value,
            "bullet": payload.bullet,
            "criterion_id": payload.criterion_id,
            "evidence": [
                {
                    "evidence_kind": item.evidence_kind,
                    "locator": item.locator,
                    "sha256": item.sha256,
                    "outcome": item.outcome.value,
                }
                for item in payload.evidence
            ],
        }
    if isinstance(payload, GoalActivityObserved):
        return {
            "goal_id": payload.goal_id,
            "fact_id": payload.fact_id,
            "kind": payload.kind.value,
            "bullet": payload.bullet,
        }
    if isinstance(payload, GoalFinishRequested):
        return {
            "goal_id": payload.goal_id,
            "completion_claim": payload.completion_claim,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, GoalDeferred):
        return {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "next_action": payload.next_action,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, GoalBlocked):
        return {
            "goal_id": payload.goal_id,
            "dependency": payload.dependency,
            "recovery": payload.recovery,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, GoalReopened):
        return {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "next_action": payload.next_action,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, GoalCriteriaAmended):
        return {
            "goal_id": payload.goal_id,
            "expected_revision": payload.expected_revision,
            "success_criteria": [
                {"criterion_id": item.criterion_id, "description": item.description}
                for item in payload.success_criteria
            ],
            "reason": payload.reason,
            "next_action": payload.next_action,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    if isinstance(payload, GoalCancelled):
        return {"goal_id": payload.goal_id, "reason": payload.reason}
    return {
        "goal_id": payload.goal_id,
        "replacement_goal_id": payload.replacement_goal_id,
        "reason": payload.reason,
    }


def _success_criteria_from_value(value: object) -> tuple[SuccessCriterion, ...]:
    """Parse an event's success-criteria array without changing its schema errors."""

    if not isinstance(value, list):
        raise ValueError("success_criteria must be an array")
    criteria: list[SuccessCriterion] = []
    for criterion in cast(list[object], value):
        item = _require_object(criterion, "success criterion")
        _require_fields(item, {"criterion_id", "description"})
        criteria.append(
            SuccessCriterion(
                _string(item["criterion_id"], "criterion_id") or "",
                _string(item["description"], "description") or "",
            )
        )
    return tuple(criteria)


def _goal_started_from_dict(value: dict[str, object]) -> GoalStarted:
    """Parse the goal-start contract after validating its exact field set."""

    _require_fields(
        value,
        {"goal_id", "problem", "success_criteria"},
        {
            "owner",
            "checklist_id",
            "checklist_version",
            "checklist_source_text",
            "parent_goal_id",
            "depends_on_goal_ids",
            "initial_status",
            "next_action",
        },
    )
    criteria = _success_criteria_from_value(value["success_criteria"])
    dependency_values = value.get("depends_on_goal_ids", [])
    if not isinstance(dependency_values, list):
        raise ValueError("depends_on_goal_ids must be an array")
    dependencies = tuple(
        _string(item, "dependency goal ID") or ""
        for item in cast(list[object], dependency_values)
    )
    return GoalStarted(
        goal_id=_string(value["goal_id"], "goal_id") or "",
        problem=_string(value["problem"], "problem") or "",
        success_criteria=criteria,
        owner=_string(value.get("owner"), "owner", optional=True),
        checklist_id=_string(value.get("checklist_id"), "checklist_id", optional=True),
        checklist_version=_string(
            value.get("checklist_version"), "checklist_version", optional=True
        ),
        checklist_source_text=_string(
            value.get("checklist_source_text"),
            "checklist_source_text",
            optional=True,
        ),
        parent_goal_id=_string(
            value.get("parent_goal_id"), "parent_goal_id", optional=True
        ),
        depends_on_goal_ids=dependencies,
        initial_status=GoalStatus(
            _string(value.get("initial_status", GoalStatus.ACTIVE.value), "initial_status")
            or GoalStatus.ACTIVE.value
        ),
        next_action=_string(value.get("next_action"), "next_action", optional=True),
    )


def _fact_recorded_from_dict(value: dict[str, object]) -> FactRecorded:
    """Parse a fact event and its bounded evidence references."""

    _require_fields(
        value,
        {"goal_id", "fact_id", "kind", "bullet", "evidence"},
        {"criterion_id"},
    )
    try:
        fact_kind = FactKind(_string(value["kind"], "kind"))
    except ValueError as exc:
        raise ValueError("unknown fact kind") from exc
    if fact_kind is FactKind.REOPENED:
        raise ValueError("reopened facts must use the goal.reopened event")
    if fact_kind is FactKind.CRITERIA_AMENDED:
        raise ValueError("criteria-amended facts must use goal.criteria_amended")
    if fact_kind in {FactKind.CANCELLED, FactKind.SUPERSEDED}:
        raise ValueError("retirement facts must use their matching goal event")
    evidence_value = value["evidence"]
    if not isinstance(evidence_value, list):
        raise ValueError("evidence must be an array")
    evidence: list[EvidenceRef] = []
    for item_value in cast(list[object], evidence_value):
        item = _require_object(item_value, "evidence reference")
        _require_fields(item, {"evidence_kind", "locator", "sha256", "outcome"})
        try:
            outcome = EvidenceOutcome(_string(item["outcome"], "outcome"))
        except ValueError as exc:
            raise ValueError("unknown evidence outcome") from exc
        evidence.append(
            EvidenceRef(
                evidence_kind=_string(item["evidence_kind"], "evidence_kind") or "",
                locator=_string(item["locator"], "locator") or "",
                sha256=_string(item["sha256"], "sha256") or "",
                outcome=outcome,
            )
        )
    return FactRecorded(
        goal_id=_string(value["goal_id"], "goal_id") or "",
        fact_id=_string(value["fact_id"], "fact_id") or "",
        kind=fact_kind,
        bullet=_string(value["bullet"], "bullet") or "",
        criterion_id=_string(value.get("criterion_id"), "criterion_id", optional=True),
        evidence=tuple(evidence),
    )


def _goal_activity_from_dict(value: dict[str, object]) -> GoalActivityObserved:
    _require_fields(value, {"goal_id", "fact_id", "kind", "bullet"})
    try:
        kind = FactKind(_string(value["kind"], "kind"))
    except ValueError as exc:
        raise ValueError("unknown activity fact kind") from exc
    return GoalActivityObserved(
        goal_id=_string(value["goal_id"], "goal_id") or "",
        fact_id=_string(value["fact_id"], "fact_id") or "",
        kind=kind,
        bullet=_string(value["bullet"], "bullet") or "",
    )


def _criteria_amended_from_dict(value: dict[str, object]) -> GoalCriteriaAmended:
    """Parse a criteria-amendment event with exact integer semantics."""

    _require_fields(
        value,
        {"goal_id", "expected_revision", "success_criteria", "reason", "next_action"},
        {"expected_lifecycle_revision"},
    )
    expected_revision = value["expected_revision"]
    if not isinstance(expected_revision, int) or isinstance(expected_revision, bool):
        raise ValueError("expected_revision must be an integer")
    return GoalCriteriaAmended(
        goal_id=_string(value["goal_id"], "goal_id") or "",
        expected_revision=expected_revision,
        success_criteria=_success_criteria_from_value(value["success_criteria"]),
        reason=_string(value["reason"], "reason") or "",
        next_action=_string(value["next_action"], "next_action") or "",
        expected_lifecycle_revision=_optional_revision(
            value.get("expected_lifecycle_revision")
        ),
    )


def _payload_from_dict(kind: EventKind, value: dict[str, object]) -> EventPayload:
    if kind is EventKind.GOAL_STARTED:
        return _goal_started_from_dict(value)
    if kind is EventKind.GOAL_ACTIVATED:
        _require_fields(
            value,
            {"goal_id", "reason", "expected_lifecycle_revision"},
        )
        return GoalActivated(
            goal_id=_string(value["goal_id"], "goal_id") or "",
            reason=_string(value["reason"], "reason") or "",
            expected_lifecycle_revision=_optional_revision(
                value["expected_lifecycle_revision"]
            ) or 0,
        )
    if kind is EventKind.FACT_RECORDED:
        return _fact_recorded_from_dict(value)
    if kind is EventKind.GOAL_ACTIVITY_OBSERVED:
        return _goal_activity_from_dict(value)
    if kind is EventKind.GOAL_FINISH_REQUESTED:
        _require_fields(
            value,
            {"goal_id", "completion_claim"},
            {"expected_lifecycle_revision"},
        )
        return GoalFinishRequested(
            _string(value["goal_id"], "goal_id") or "",
            _string(value["completion_claim"], "completion_claim") or "",
            _optional_revision(value.get("expected_lifecycle_revision")),
        )
    if kind is EventKind.GOAL_DEFERRED:
        _require_fields(
            value,
            {"goal_id", "reason", "next_action"},
            {"expected_lifecycle_revision"},
        )
        return GoalDeferred(
            _string(value["goal_id"], "goal_id") or "",
            _string(value["reason"], "reason") or "",
            _string(value["next_action"], "next_action") or "",
            _optional_revision(value.get("expected_lifecycle_revision")),
        )
    if kind is EventKind.GOAL_REOPENED:
        _require_fields(
            value,
            {"goal_id", "reason", "next_action"},
            {"expected_lifecycle_revision"},
        )
        return GoalReopened(
            _string(value["goal_id"], "goal_id") or "",
            _string(value["reason"], "reason") or "",
            _string(value["next_action"], "next_action") or "",
            _optional_revision(value.get("expected_lifecycle_revision")),
        )
    if kind is EventKind.GOAL_CRITERIA_AMENDED:
        return _criteria_amended_from_dict(value)
    if kind is EventKind.GOAL_CANCELLED:
        _require_fields(value, {"goal_id", "reason"})
        return GoalCancelled(
            _string(value["goal_id"], "goal_id") or "",
            _string(value["reason"], "reason") or "",
        )
    if kind is EventKind.GOAL_SUPERSEDED:
        _require_fields(value, {"goal_id", "replacement_goal_id", "reason"})
        return GoalSuperseded(
            _string(value["goal_id"], "goal_id") or "",
            _string(value["replacement_goal_id"], "replacement_goal_id") or "",
            _string(value["reason"], "reason") or "",
        )
    _require_fields(
        value,
        {"goal_id", "dependency", "recovery"},
        {"expected_lifecycle_revision"},
    )
    return GoalBlocked(
        _string(value["goal_id"], "goal_id") or "",
        _string(value["dependency"], "dependency") or "",
        _string(value["recovery"], "recovery") or "",
        _optional_revision(value.get("expected_lifecycle_revision")),
    )


def _envelope_from_dict(value: object) -> EventEnvelope:
    envelope = _require_object(value, "event envelope")
    _require_fields(
        envelope,
        {"schema_version", "event_id", "project_id", "occurred_at", "event_type", "payload"},
        {"source_id", "source_sequence"},
    )
    version = envelope["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError("schema_version must be an integer")
    try:
        kind = EventKind(_string(envelope["event_type"], "event_type"))
    except ValueError as exc:
        raise ValueError("unknown event type") from exc
    payload = _payload_from_dict(kind, _require_object(envelope["payload"], "payload"))
    if _EVENT_TYPES[type(payload)] is not kind:
        raise ValueError("event_type does not match payload")
    return EventEnvelope(
        event_id=_string(envelope["event_id"], "event_id") or "",
        project_id=_string(envelope["project_id"], "project_id") or "",
        occurred_at=_string(envelope["occurred_at"], "occurred_at") or "",
        schema_version=version,
        payload=payload,
        source_id=_string(envelope.get("source_id", "unspecified"), "source_id")
        or "unspecified",
        source_sequence=_optional_positive_integer(
            envelope.get("source_sequence"), "source_sequence"
        ),
    )


def _optional_positive_integer(value: object, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer when supplied")
    return value


def _utf8_length(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("event contains text that is not valid UTF-8") from exc
