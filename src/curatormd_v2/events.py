"""Versioned, bounded lifecycle event contracts for Curator V2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import hashlib
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
from .event_validation import (
    event_string,
    event_utf8_length,
    optional_event_revision,
    parse_event_enum,
    reject_duplicate_event_keys,
    require_event_fields,
    require_event_object,
    validate_lifecycle_revision,
)
from .validation import is_exact_int


EVENT_SCHEMA_VERSION = 1
MAX_EVENT_BYTES = 16 * 1024
_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


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
class EventInboxReceipt:  # pylint: disable=too-many-instance-attributes
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
class GoalStarted:  # pylint: disable=too-many-instance-attributes
    """Event record mirrors the versioned goal.started payload fields."""

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

    initial_status = parse_event_enum(
        GoalStatus, event.initial_status, "initial_status must be planned or active"
    )
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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
        validate_lifecycle_revision(self.expected_lifecycle_revision)


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
class EventEnvelope:  # pylint: disable=too-many-instance-attributes
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
        parse_failed = False
        parsed: datetime | None = None
        try:
            parsed = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError:
            parse_failed = True
        if parse_failed or parsed is None:
            raise ValueError("occurred_at must be an ISO-8601 timestamp")
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
        if event_utf8_length(serialized) > MAX_EVENT_BYTES:
            raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
        return serialized

    @property
    def idempotency_sha256(self) -> str:
        """Digest event identity and payload while excluding transport time."""

        identity = self.to_dict()
        identity.pop("occurred_at")
        serialized = json.dumps(
            identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, serialized: str) -> EventEnvelope:
        """Parse a strict version-1 event, rejecting ambiguous JSON fields."""

        if event_utf8_length(serialized) > MAX_EVENT_BYTES:
            raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
        decode_failed = False
        value: object = None
        try:
            value = json.loads(serialized, object_pairs_hook=reject_duplicate_event_keys)
        except json.JSONDecodeError:
            # JSONDecodeError retains the complete source in its ``doc`` field.
            decode_failed = True
        if decode_failed:
            raise ValueError("event must be valid UTF-8 JSON")
        envelope = _envelope_from_dict(value)
        # Keep encoder and decoder limits identical, including normalized JSON.
        envelope.to_json()
        return envelope


def _payload_to_dict(payload: EventPayload) -> dict[str, object]:
    payload_data: dict[str, object]
    if isinstance(payload, GoalStarted):
        payload_data = {
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
    elif isinstance(payload, GoalActivated):
        payload_data = {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    elif isinstance(payload, FactRecorded):
        payload_data = {
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
                    **(
                        {"occurrence_id": item.occurrence_id}
                        if item.occurrence_id is not None
                        else {}
                    ),
                }
                for item in payload.evidence
            ],
        }
    elif isinstance(payload, GoalActivityObserved):
        payload_data = {
            "goal_id": payload.goal_id,
            "fact_id": payload.fact_id,
            "kind": payload.kind.value,
            "bullet": payload.bullet,
        }
    elif isinstance(payload, GoalFinishRequested):
        payload_data = {
            "goal_id": payload.goal_id,
            "completion_claim": payload.completion_claim,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    elif isinstance(payload, GoalDeferred):
        payload_data = {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "next_action": payload.next_action,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    elif isinstance(payload, GoalBlocked):
        payload_data = {
            "goal_id": payload.goal_id,
            "dependency": payload.dependency,
            "recovery": payload.recovery,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    elif isinstance(payload, GoalReopened):
        payload_data = {
            "goal_id": payload.goal_id,
            "reason": payload.reason,
            "next_action": payload.next_action,
            "expected_lifecycle_revision": payload.expected_lifecycle_revision,
        }
    elif isinstance(payload, GoalCriteriaAmended):
        payload_data = {
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
    elif isinstance(payload, GoalCancelled):
        payload_data = {"goal_id": payload.goal_id, "reason": payload.reason}
    else:
        payload_data = {
            "goal_id": payload.goal_id,
            "replacement_goal_id": payload.replacement_goal_id,
            "reason": payload.reason,
        }
    return payload_data


def _success_criteria_from_value(value: object) -> tuple[SuccessCriterion, ...]:
    """Parse an event's success-criteria array without changing its schema errors."""

    if not isinstance(value, list):
        raise ValueError("success_criteria must be an array")
    criteria: list[SuccessCriterion] = []
    for criterion in cast(list[object], value):
        item = require_event_object(criterion, "success criterion")
        require_event_fields(item, {"criterion_id", "description"})
        criteria.append(
            SuccessCriterion(
                event_string(item["criterion_id"], "criterion_id") or "",
                event_string(item["description"], "description") or "",
            )
        )
    return tuple(criteria)


def _goal_started_from_dict(value: dict[str, object]) -> GoalStarted:
    """Parse the goal-start contract after validating its exact field set."""

    require_event_fields(
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
        event_string(item, "dependency goal ID") or ""
        for item in cast(list[object], dependency_values)
    )
    return GoalStarted(
        goal_id=event_string(value["goal_id"], "goal_id") or "",
        problem=event_string(value["problem"], "problem") or "",
        success_criteria=criteria,
        owner=event_string(value.get("owner"), "owner", optional=True),
        checklist_id=event_string(value.get("checklist_id"), "checklist_id", optional=True),
        checklist_version=event_string(
            value.get("checklist_version"), "checklist_version", optional=True
        ),
        checklist_source_text=event_string(
            value.get("checklist_source_text"),
            "checklist_source_text",
            optional=True,
        ),
        parent_goal_id=event_string(
            value.get("parent_goal_id"), "parent_goal_id", optional=True
        ),
        depends_on_goal_ids=dependencies,
        initial_status=GoalStatus(
            event_string(value.get("initial_status", GoalStatus.ACTIVE.value), "initial_status")
            or GoalStatus.ACTIVE.value
        ),
        next_action=event_string(value.get("next_action"), "next_action", optional=True),
    )


def _fact_recorded_from_dict(value: dict[str, object]) -> FactRecorded:
    """Parse a fact event and its bounded evidence references."""

    require_event_fields(
        value,
        {"goal_id", "fact_id", "kind", "bullet", "evidence"},
        {"criterion_id"},
    )
    fact_kind = parse_event_enum(
        FactKind, event_string(value["kind"], "kind") or "", "unknown fact kind"
    )
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
        item = require_event_object(item_value, "evidence reference")
        require_event_fields(
            item,
            {"evidence_kind", "locator", "sha256", "outcome"},
            {"occurrence_id"},
        )
        outcome = parse_event_enum(
            EvidenceOutcome,
            event_string(item["outcome"], "outcome") or "",
            "unknown evidence outcome",
        )
        evidence.append(
            EvidenceRef(
                evidence_kind=event_string(item["evidence_kind"], "evidence_kind") or "",
                locator=event_string(item["locator"], "locator") or "",
                sha256=event_string(item["sha256"], "sha256") or "",
                outcome=outcome,
                occurrence_id=event_string(
                    item.get("occurrence_id"), "occurrence_id", optional=True
                ),
            )
        )
    return FactRecorded(
        goal_id=event_string(value["goal_id"], "goal_id") or "",
        fact_id=event_string(value["fact_id"], "fact_id") or "",
        kind=fact_kind,
        bullet=event_string(value["bullet"], "bullet") or "",
        criterion_id=event_string(value.get("criterion_id"), "criterion_id", optional=True),
        evidence=tuple(evidence),
    )


def _goal_activity_from_dict(value: dict[str, object]) -> GoalActivityObserved:
    require_event_fields(value, {"goal_id", "fact_id", "kind", "bullet"})
    kind = parse_event_enum(
        FactKind,
        event_string(value["kind"], "kind") or "",
        "unknown activity fact kind",
    )
    return GoalActivityObserved(
        goal_id=event_string(value["goal_id"], "goal_id") or "",
        fact_id=event_string(value["fact_id"], "fact_id") or "",
        kind=kind,
        bullet=event_string(value["bullet"], "bullet") or "",
    )


def _criteria_amended_from_dict(value: dict[str, object]) -> GoalCriteriaAmended:
    """Parse a criteria-amendment event with exact integer semantics."""

    require_event_fields(
        value,
        {"goal_id", "expected_revision", "success_criteria", "reason", "next_action"},
        {"expected_lifecycle_revision"},
    )
    expected_revision = value["expected_revision"]
    if not isinstance(expected_revision, int) or isinstance(expected_revision, bool):
        raise ValueError("expected_revision must be an integer")
    return GoalCriteriaAmended(
        goal_id=event_string(value["goal_id"], "goal_id") or "",
        expected_revision=expected_revision,
        success_criteria=_success_criteria_from_value(value["success_criteria"]),
        reason=event_string(value["reason"], "reason") or "",
        next_action=event_string(value["next_action"], "next_action") or "",
        expected_lifecycle_revision=optional_event_revision(
            value.get("expected_lifecycle_revision")
        ),
    )


def _payload_from_dict(kind: EventKind, value: dict[str, object]) -> EventPayload:
    if kind is EventKind.GOAL_STARTED:
        payload = _goal_started_from_dict(value)
    elif kind is EventKind.GOAL_ACTIVATED:
        require_event_fields(
            value,
            {"goal_id", "reason", "expected_lifecycle_revision"},
        )
        payload = GoalActivated(
            goal_id=event_string(value["goal_id"], "goal_id") or "",
            reason=event_string(value["reason"], "reason") or "",
            expected_lifecycle_revision=optional_event_revision(
                value["expected_lifecycle_revision"]
            ) or 0,
        )
    elif kind is EventKind.FACT_RECORDED:
        payload = _fact_recorded_from_dict(value)
    elif kind is EventKind.GOAL_ACTIVITY_OBSERVED:
        payload = _goal_activity_from_dict(value)
    elif kind is EventKind.GOAL_FINISH_REQUESTED:
        require_event_fields(
            value,
            {"goal_id", "completion_claim"},
            {"expected_lifecycle_revision"},
        )
        payload = GoalFinishRequested(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["completion_claim"], "completion_claim") or "",
            optional_event_revision(value.get("expected_lifecycle_revision")),
        )
    elif kind is EventKind.GOAL_DEFERRED:
        require_event_fields(
            value,
            {"goal_id", "reason", "next_action"},
            {"expected_lifecycle_revision"},
        )
        payload = GoalDeferred(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["reason"], "reason") or "",
            event_string(value["next_action"], "next_action") or "",
            optional_event_revision(value.get("expected_lifecycle_revision")),
        )
    elif kind is EventKind.GOAL_REOPENED:
        require_event_fields(
            value,
            {"goal_id", "reason", "next_action"},
            {"expected_lifecycle_revision"},
        )
        payload = GoalReopened(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["reason"], "reason") or "",
            event_string(value["next_action"], "next_action") or "",
            optional_event_revision(value.get("expected_lifecycle_revision")),
        )
    elif kind is EventKind.GOAL_CRITERIA_AMENDED:
        payload = _criteria_amended_from_dict(value)
    elif kind is EventKind.GOAL_CANCELLED:
        require_event_fields(value, {"goal_id", "reason"})
        payload = GoalCancelled(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["reason"], "reason") or "",
        )
    elif kind is EventKind.GOAL_SUPERSEDED:
        require_event_fields(value, {"goal_id", "replacement_goal_id", "reason"})
        payload = GoalSuperseded(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["replacement_goal_id"], "replacement_goal_id") or "",
            event_string(value["reason"], "reason") or "",
        )
    else:
        require_event_fields(
            value,
            {"goal_id", "dependency", "recovery"},
            {"expected_lifecycle_revision"},
        )
        payload = GoalBlocked(
            event_string(value["goal_id"], "goal_id") or "",
            event_string(value["dependency"], "dependency") or "",
            event_string(value["recovery"], "recovery") or "",
            optional_event_revision(value.get("expected_lifecycle_revision")),
        )
    return payload


def _envelope_from_dict(value: object) -> EventEnvelope:
    envelope = require_event_object(value, "event envelope")
    require_event_fields(
        envelope,
        {"schema_version", "event_id", "project_id", "occurred_at", "event_type", "payload"},
        {"source_id", "source_sequence"},
    )
    version = envelope["schema_version"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError("schema_version must be an integer")
    kind = parse_event_enum(
        EventKind,
        event_string(envelope["event_type"], "event_type") or "",
        "unknown event type",
    )
    payload = _payload_from_dict(kind, require_event_object(envelope["payload"], "payload"))
    if _EVENT_TYPES[type(payload)] is not kind:
        raise ValueError("event_type does not match payload")
    return EventEnvelope(
        event_id=event_string(envelope["event_id"], "event_id") or "",
        project_id=event_string(envelope["project_id"], "project_id") or "",
        occurred_at=event_string(envelope["occurred_at"], "occurred_at") or "",
        schema_version=version,
        payload=payload,
        source_id=event_string(envelope.get("source_id", "unspecified"), "source_id")
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
