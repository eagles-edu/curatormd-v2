"""Typed, bounded records for the Curator V2 goal ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import TypeGuard
from uuid import uuid4

from .content_safety import validate_safe_text
from .validation import is_exact_int


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVIEWER_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
MAX_SUCCESS_CRITERIA = 32
MAX_CRITERIA_REVISIONS = 16
MAX_GOAL_DEPENDENCIES = 32
MAX_EVIDENCE_REFERENCES = 16
MAX_SDE_SUPPORTING_FACTS = 32
MAX_ARTIFACTS_PER_RECEIPT = 500
MAX_FACTS_PER_GOAL = 512
MAX_FACT_BYTES_PER_GOAL = 512 * 1024
MAX_FACTS_PER_PROJECT = 10_000
MAX_FACT_BYTES_PER_PROJECT = 16 * 1024 * 1024
MAX_FACT_COMPACTION_BATCH_FACTS = 64
MAX_FACT_COMPACTION_SOURCE_BYTES = 256 * 1024
MAX_FACT_ARCHIVE_BYTES_PER_PROJECT = 64 * 1024 * 1024
MAX_SDE_CORRECTIONS_PER_CANDIDATE = 32
MAX_SDE_CORRECTIONS_PER_PROJECT = 1000
MAX_SDE_FEEDBACK_PER_PROJECT = 10_000
MAX_EVENT_RECEIPTS_GLOBAL = 250_000
MAX_EVENT_RECEIPT_BYTES_GLOBAL = 128 * 1024 * 1024
EVENT_FAILURE_METADATA_RESERVE_BYTES = 160
MAX_GOAL_LIST_PAGE = 100
MAX_GOAL_STATUS_CANDIDATES = 32
MAX_GOAL_STATUS_PURGE_RECEIPTS = 16


def utc_now() -> str:
    """Return a sortable UTC timestamp with explicit timezone information."""

    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    """Generate an opaque identifier suitable for ledger records."""

    return uuid4().hex


def _parse_aware_timestamp(name: str, value: object) -> datetime:
    """Parse one bounded timezone-aware timestamp from a runtime value."""

    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError(f"{name} must be a bounded ISO-8601 timestamp")
    parse_failed = False
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parse_failed = True
    if parse_failed or parsed is None:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


class GoalStatus(StrEnum):
    """Persisted lifecycle states for a goal and its open work."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETE = "complete"
    OPEN = "open"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class CriterionStatus(StrEnum):
    """Verification state of one success criterion."""

    VERIFIED = "verified"
    OPEN = "open"


class GoalBulletCategory(StrEnum):
    """Truth labels for the compact user-facing goal projection."""

    PROBLEM = "problem"
    CRITERION = "criterion"
    RECORDED = "recorded_fact"
    VERIFIED = "verified_fact"
    UNVERIFIED = "unverified_claim"
    OPEN = "open_gate"
    NEXT = "next_action"


class FactKind(StrEnum):
    """Typed development facts that may be appended to a goal ledger."""

    INTENT = "intent"
    RESEARCH = "research"
    ADVICE = "advice"
    PROPOSAL = "proposal"
    CHANGE = "change"
    VERIFICATION = "verification"
    OPEN_GATE = "open_gate"
    COMPLETION_CLAIM = "completion_claim"
    OUTCOME = "outcome"
    REOPENED = "reopened"
    CRITERIA_AMENDED = "criteria_amended"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class EvidenceOutcome(StrEnum):
    """Observed result attached to a bounded evidence reference."""

    PASSED = "passed"
    FAILED = "failed"
    OBSERVED = "observed"


class Materiality(StrEnum):
    """Reason category used to assess significant development events."""

    IMPLEMENTATION = "implementation"
    DECISION = "decision"
    RECOVERY = "recovery"
    VERIFIED_LESSON = "verified_lesson"
    ROUTINE = "routine"


class SDEStatus(StrEnum):
    """Review state of a significant development event candidate."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    """Human disposition recorded for an SDE candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


class SDEQualityFeedbackLabel(StrEnum):
    """Explicit human QA labels; they are not inferred or model predictions."""

    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    INACCURATE = "inaccurate"
    DUPLICATE = "duplicate"


class PurgeStatus(StrEnum):
    """Overall purge state attached to an auditable review receipt."""

    PURGE_PENDING = "purge_pending"
    COMPLETE = "complete"


class OperationalHealth(StrEnum):
    """Conservative aggregate state for one project's observed operations."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class StagingArtifactClass(StrEnum):
    """Bounded temporary artifact classes used for staging attribution."""

    RAW_CHAT = "raw-chat"
    CUE = "cue"
    IMPORT = "import"
    SCRATCH = "scratch"
    GENERATED = "generated"
    DUPLICATE = "duplicate"
    OTHER = "other"


class ArtifactStatus(StrEnum):
    """Purge state of one inventoried transient artifact."""

    PENDING = "pending"
    PURGED = "purged"
    FAILED = "failed"
    HELD = "held"


class PurgeFailureCode(StrEnum):
    """Content-free reasons for retryable artifact purge failures."""

    RETENTION_HOLD = "retention_hold"
    INVALID_PATH = "invalid_path"
    OUTSIDE_STAGING_ROOT = "outside_staging_root"
    STAGING_ROOT = "staging_root"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    NOT_REGULAR_FILE = "not_regular_file"
    ARTIFACT_CHANGED = "artifact_changed"
    HASH_MISMATCH = "hash_mismatch"
    PATH_CHANGED = "path_changed"
    FILESYSTEM_ERROR = "filesystem_error"
    INVALID_ARTIFACT = "invalid_artifact"
    LEGACY_FAILURE_DETAIL_REDACTED = "legacy_failure_detail_redacted"


class RetentionHoldKind(StrEnum):
    """Reason class for an explicit, reviewer-visible artifact retention hold."""

    LEGAL = "legal"
    OPERATIONAL = "operational"


def _is_retention_hold_kind(value: object) -> TypeGuard[RetentionHoldKind]:
    """Reject strings and other impostors passed through dynamic callers."""

    # The dataclass annotation is not runtime validation; exact enum identity is required.
    return type(value) is RetentionHoldKind  # pylint: disable=unidiomatic-typecheck


@dataclass(frozen=True, slots=True)
class SuccessCriterion:
    """One testable condition required to complete a goal."""

    criterion_id: str
    description: str

    def __post_init__(self) -> None:
        validate_safe_text(self.description, "success_criterion.description")
        if not self.criterion_id.strip():
            raise ValueError("criterion_id must not be empty")
        if not self.description.strip():
            raise ValueError("criterion description must not be empty")
        if len(self.description) > 500:
            raise ValueError("criterion description exceeds 500 characters")
        if "\n" in self.description or "\r" in self.description:
            raise ValueError("criterion description must be a single line")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """A compact pointer to proof; output/transcript contents are not stored."""

    evidence_kind: str
    locator: str
    sha256: str
    outcome: EvidenceOutcome

    def __post_init__(self) -> None:
        validate_safe_text(self.evidence_kind, "evidence.evidence_kind")
        validate_safe_text(self.locator, "evidence.locator")
        if not self.evidence_kind.strip() or not self.locator.strip():
            raise ValueError("evidence kind and locator must not be empty")
        if len(self.locator) > 1000:
            raise ValueError("evidence locator exceeds 1000 characters")
        if len(self.evidence_kind) > 64:
            raise ValueError("evidence kind exceeds 64 characters")
        if "\n" in self.locator or "\r" in self.locator:
            raise ValueError("evidence locator must be a single line")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("evidence sha256 must be 64 lowercase hex characters")


@dataclass(frozen=True, slots=True)
class EvidenceAttestation:
    """Compact host-trusted provenance for one accepted evidence reference."""

    evidence_kind: str
    evidence_sha256: str
    project_id: str
    goal_id: str
    criterion_id: str
    adapter_id: str
    authenticated_subject: str
    source_revision: str
    observed_at: str
    verified_at: str
    valid_until: str
    revocation_checked_at: str

    def __post_init__(self) -> None:
        for name, value, limit in (
            ("evidence_kind", self.evidence_kind, 64),
            ("project_id", self.project_id, 128),
            ("goal_id", self.goal_id, 128),
            ("criterion_id", self.criterion_id, 128),
            ("adapter_id", self.adapter_id, 128),
            ("authenticated_subject", self.authenticated_subject, 128),
            ("source_revision", self.source_revision, 256),
        ):
            validate_safe_text(value, f"evidence_attestation.{name}")
            if not value.strip() or len(value) > limit:
                raise ValueError(f"{name} must contain 1-{limit} characters")
            if "\n" in value or "\r" in value:
                raise ValueError(f"{name} must be a single line")
        if not _SHA256_RE.fullmatch(self.evidence_sha256):
            raise ValueError("attested evidence SHA-256 must be 64 lowercase hex characters")
        timestamps: dict[str, datetime] = {}
        for name, value in (
            ("observed_at", self.observed_at),
            ("verified_at", self.verified_at),
            ("valid_until", self.valid_until),
            ("revocation_checked_at", self.revocation_checked_at),
        ):
            timestamps[name] = _parse_aware_timestamp(name, value)
        if timestamps["observed_at"] > timestamps["verified_at"]:
            raise ValueError("evidence cannot be observed after it was verified")
        if timestamps["revocation_checked_at"] > timestamps["verified_at"]:
            raise ValueError("revocation check cannot be after verification")
        if timestamps["valid_until"] <= timestamps["verified_at"]:
            raise ValueError("evidence attestation must remain valid after verification")


@dataclass(frozen=True, slots=True)
class GoalCard:
    """Current project-scoped goal contract and lifecycle state."""

    goal_id: str
    problem: str
    success_criteria: tuple[SuccessCriterion, ...]
    owner: str | None = None
    checklist_id: str | None = None
    checklist_version: str | None = None
    checklist_source_text: str | None = None
    parent_goal_id: str | None = None
    depends_on_goal_ids: tuple[str, ...] = ()
    project_id: str = "default"
    status: GoalStatus = GoalStatus.ACTIVE
    next_action: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    criteria_revision: int = 1
    lifecycle_revision: int = 1
    superseded_by_goal_id: str | None = None

    def __post_init__(self) -> None:
        _validate_goal_text_fields(self)
        _validate_goal_successor(self)
        _validate_goal_problem_and_criteria(self)
        _validate_goal_revisions_and_relations(self)
        _validate_goal_checklist_snapshot(self)


@dataclass(frozen=True, slots=True)
class GoalListPage:
    """Compact, bounded project goal-card listing; facts load on demand."""

    project_id: str
    total: int
    offset: int
    limit: int
    goals: tuple[GoalCard, ...]
    next_offset: int | None

    def __post_init__(self) -> None:
        """Reject inconsistent or over-bound pagination metadata."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", self.project_id):
            raise ValueError("goal page project_id must be a bounded identifier")
        if any(
            not is_exact_int(value) or value < 0
            for value in (self.total, self.offset)
        ):
            raise ValueError("goal page total and offset must be non-negative integers")
        if not is_exact_int(self.limit) or not 1 <= self.limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"goal page limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        if len(self.goals) > self.limit:
            raise ValueError("goal page contains more cards than its limit")
        if self.next_offset is not None and not is_exact_int(self.next_offset):
            raise ValueError("goal page next_offset must be an integer or null")
        expected_next = (
            self.offset + len(self.goals)
            if self.offset + len(self.goals) < self.total
            else None
        )
        if self.next_offset != expected_next:
            raise ValueError("goal page next_offset does not match its contents")
        if any(goal.project_id != self.project_id for goal in self.goals):
            raise ValueError("goal page contains a card from another project")


def _validate_goal_text_fields(goal: GoalCard) -> None:
    """Apply the shared safe-text policy to optional and required goal text."""

    for field_name, value in (
        ("goal.problem", goal.problem),
        ("goal.owner", goal.owner),
        ("goal.checklist_id", goal.checklist_id),
        ("goal.checklist_source_text", goal.checklist_source_text),
        ("goal.next_action", goal.next_action),
    ):
        if value is not None:
            validate_safe_text(value, field_name)


def _validate_goal_successor(goal: GoalCard) -> None:
    """Validate identity, supersession linkage, and project identifier."""

    if not goal.goal_id.strip():
        raise ValueError("goal_id must not be empty")
    if goal.superseded_by_goal_id is not None:
        if not goal.superseded_by_goal_id.strip():
            raise ValueError("superseded_by_goal_id must not be empty")
        if goal.superseded_by_goal_id == goal.goal_id:
            raise ValueError("a goal cannot supersede itself")
        if goal.status is not GoalStatus.SUPERSEDED:
            raise ValueError("only a superseded goal may reference its successor")
    elif goal.status is GoalStatus.SUPERSEDED:
        raise ValueError("a superseded goal must reference its successor")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", goal.project_id):
        raise ValueError("project_id must be a bounded opaque identifier")


def _validate_goal_problem_and_criteria(goal: GoalCard) -> None:
    """Validate the required problem statement and its success criteria."""

    if not goal.problem.strip():
        raise ValueError("problem must not be empty")
    if len(goal.problem) > 2000:
        raise ValueError("problem exceeds 2000 characters")
    if "\n" in goal.problem or "\r" in goal.problem:
        raise ValueError("problem must be a single compact statement")
    if not goal.success_criteria:
        raise ValueError("at least one success criterion is required")
    if len(goal.success_criteria) > MAX_SUCCESS_CRITERIA:
        raise ValueError(
            f"success criteria exceed the limit of {MAX_SUCCESS_CRITERIA}"
        )
    ids = [criterion.criterion_id for criterion in goal.success_criteria]
    if len(ids) != len(set(ids)):
        raise ValueError("criterion IDs must be unique within a goal")


def _validate_goal_revisions_and_relations(goal: GoalCard) -> None:
    """Validate next action, revisions, parent, and dependency relationships."""

    if goal.next_action is not None and len(goal.next_action) > 1000:
        raise ValueError("next_action exceeds 1000 characters")
    if goal.criteria_revision < 1:
        raise ValueError("criteria_revision must be positive")
    if goal.lifecycle_revision < 1:
        raise ValueError("lifecycle_revision must be positive")
    if goal.parent_goal_id == goal.goal_id:
        raise ValueError("a goal cannot be its own parent")
    if len(goal.depends_on_goal_ids) != len(set(goal.depends_on_goal_ids)):
        raise ValueError("goal dependencies must be unique")
    if len(goal.depends_on_goal_ids) > MAX_GOAL_DEPENDENCIES:
        raise ValueError(
            f"goal dependencies exceed the limit of {MAX_GOAL_DEPENDENCIES}"
        )
    if goal.goal_id in goal.depends_on_goal_ids:
        raise ValueError("a goal cannot depend on itself")


def _validate_goal_checklist_snapshot(goal: GoalCard) -> None:
    """Require checklist source text and revision metadata as one tuple."""

    snapshot = (goal.checklist_version, goal.checklist_source_text)
    if any(value is not None for value in snapshot):
        if goal.checklist_id is None or any(value is None for value in snapshot):
            raise ValueError(
                "checklist snapshot requires checklist_id, version, and source text"
            )
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", goal.checklist_version or ""):
            raise ValueError("checklist_version must be a SHA-256 source revision")
        source_text = goal.checklist_source_text or ""
        if not source_text.strip() or len(source_text) > 4000:
            raise ValueError("checklist source text must contain 1-4000 characters")
        if "\n" in source_text or "\r" in source_text:
            raise ValueError("checklist source text must be one exact item line")


@dataclass(frozen=True, slots=True)
class Fact:
    """One compact, typed, immutable fact recorded against a goal."""

    goal_id: str
    kind: FactKind
    bullet: str
    fact_id: str = field(default_factory=new_id)
    criterion_id: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()
    verification_attestations: tuple[EvidenceAttestation, ...] = ()
    source_event_id: str | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        validate_safe_text(self.bullet, "fact.bullet")
        normalized = self.bullet.strip()
        if not normalized:
            raise ValueError("fact bullet must not be empty")
        if "\n" in normalized or "\r" in normalized:
            raise ValueError("fact must be one compact bullet, not a paragraph")
        if len(normalized) > 1000:
            raise ValueError("fact bullet exceeds 1000 characters")
        if self.source_event_id is not None:
            validate_safe_text(self.source_event_id, "fact.source_event_id")
            if (
                not self.source_event_id.strip()
                or len(self.source_event_id) > 128
                or "\n" in self.source_event_id
                or "\r" in self.source_event_id
            ):
                raise ValueError("source_event_id must be a bounded single-line identifier")
        if self.kind is FactKind.VERIFICATION and not self.evidence:
            raise ValueError("verification facts require evidence references")
        if len(self.evidence) > MAX_EVIDENCE_REFERENCES:
            raise ValueError(
                f"evidence references exceed the limit of {MAX_EVIDENCE_REFERENCES}"
            )
        if self.kind is FactKind.VERIFICATION and self.criterion_id is None:
            raise ValueError("verification facts must identify a success criterion")
        if self.kind is not FactKind.VERIFICATION and self.verification_attestations:
            raise ValueError("only verification facts may retain evidence attestations")
        if self.verification_attestations:
            if len(self.verification_attestations) != len(self.evidence):
                raise ValueError("each evidence reference must have one attestation")
            if any(
                attestation.evidence_kind != evidence.evidence_kind
                or attestation.evidence_sha256 != evidence.sha256
                or attestation.goal_id != self.goal_id
                or attestation.criterion_id != self.criterion_id
                for evidence, attestation in zip(
                    self.evidence, self.verification_attestations, strict=True
                )
            ):
                raise ValueError("verification attestation does not match its evidence")

    def as_bullet(self) -> str:
        """Render one fact as the short bullet form used in project records."""

        label = self.kind.value.replace("_", " ").capitalize()
        source = (
            f" (source event: {self.source_event_id})"
            if self.source_event_id is not None
            else ""
        )
        return f"- {label}: {self.bullet.strip()}{source}"


@dataclass(frozen=True, slots=True)
class SDECandidate:
    """Reviewable significance proposal linked to supporting goal facts."""

    goal_id: str
    materiality: Materiality
    rationale: str
    fact_ids: tuple[str, ...]
    candidate_id: str = field(default_factory=new_id)
    status: SDEStatus = SDEStatus.PENDING_REVIEW
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        validate_safe_text(self.rationale, "sde.rationale")
        if self.materiality is Materiality.ROUTINE:
            raise ValueError("routine updates are not SDE candidates")
        if not self.rationale.strip() or len(self.rationale) > 1000:
            raise ValueError("SDE rationale must contain 1-1000 characters")
        if "\n" in self.rationale or "\r" in self.rationale:
            raise ValueError("SDE rationale must be a single compact line")
        if not self.fact_ids or len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("SDE candidate requires unique supporting fact IDs")
        if len(self.fact_ids) > MAX_SDE_SUPPORTING_FACTS:
            raise ValueError(
                f"SDE supporting facts exceed the limit of {MAX_SDE_SUPPORTING_FACTS}"
            )


@dataclass(frozen=True, slots=True)
class SDECorrection:
    """Immutable reviewer-attributed correction linked to a prior SDE."""

    correction_id: str
    candidate_id: str
    correction: str
    rationale: str
    reviewer_id: str
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        validate_safe_text(self.correction, "sde_correction.correction")
        validate_safe_text(self.rationale, "sde_correction.rationale")
        for name, value, limit in (
            ("correction_id", self.correction_id, 128),
            ("candidate_id", self.candidate_id, 128),
            ("correction", self.correction, 1000),
            ("rationale", self.rationale, 1000),
        ):
            if not value.strip() or len(value) > limit:
                raise ValueError(f"{name} must contain 1-{limit} characters")
            if "\n" in value or "\r" in value:
                raise ValueError(f"{name} must be a single line")
        if not _REVIEWER_ID_RE.fullmatch(self.reviewer_id):
            raise ValueError("reviewer_id must be a bounded opaque identifier")


@dataclass(frozen=True, slots=True)
class SDEQualityFeedback:
    """Append-only, reviewer-attributed quality label after SDE disposition."""

    feedback_id: str
    candidate_id: str
    reviewer_id: str
    label: SDEQualityFeedbackLabel
    rationale: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        validate_safe_text(self.rationale, "sde_feedback.rationale")
        for name, value, limit in (
            ("feedback_id", self.feedback_id, 128),
            ("candidate_id", self.candidate_id, 128),
        ):
            if not value.strip() or len(value) > limit:
                raise ValueError(f"{name} must contain 1-{limit} characters")
            if "\n" in value or "\r" in value:
                raise ValueError(f"{name} must be a single line")
        if not _REVIEWER_ID_RE.fullmatch(self.reviewer_id):
            raise ValueError("reviewer_id must be a bounded opaque identifier")
        if type(self.label) is not SDEQualityFeedbackLabel:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("label must be an SDEQualityFeedbackLabel")
        if len(self.rationale) > 500 or "\n" in self.rationale or "\r" in self.rationale:
            raise ValueError("feedback rationale must be a single line of at most 500 characters")


@dataclass(frozen=True, slots=True)
class SDEQualityFeedbackSummary:
    """Aggregate explicit reviewer labels without exposing reviewer identities."""

    project_id: str
    counts: tuple[tuple[SDEQualityFeedbackLabel, int], ...]
    total: int

    def __post_init__(self) -> None:
        if not _REVIEWER_ID_RE.fullmatch(self.project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        labels = tuple(label for label, _count in self.counts)
        if labels != tuple(SDEQualityFeedbackLabel):
            raise ValueError("feedback summary must contain each label exactly once in order")
        if any(
            type(count) is not int or count < 0  # pylint: disable=unidiomatic-typecheck
            for _label, count in self.counts
        ):
            raise ValueError("feedback summary counts must be nonnegative integers")
        if (
            type(self.total) is not int  # pylint: disable=unidiomatic-typecheck
            or self.total != sum(count for _label, count in self.counts)
        ):
            raise ValueError("feedback summary total must equal the label counts")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """An exact staged-file reference and optional fail-closed retention hold."""

    path: str
    sha256: str
    retention_hold: RetentionHoldKind | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("artifact path must not be empty")
        if len(self.path) > 4096 or "\n" in self.path or "\r" in self.path:
            raise ValueError("artifact path must be a bounded single line")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be 64 lowercase hex characters")
        if self.retention_hold is not None and not _is_retention_hold_kind(
            self.retention_hold
        ):
            raise ValueError("retention_hold must be legal, operational, or null")


@dataclass(frozen=True, slots=True)
class PurgeTargetRecord:
    """Durable cleanup state; error is a content-free failure code."""

    artifact: ArtifactRef
    status: ArtifactStatus
    attempts: int
    error: str | None
    created_at: str
    last_attempt_at: str | None
    next_attempt_at: str | None
    hold_created_at: str | None = None
    hold_created_by: str | None = None
    hold_released_at: str | None = None
    hold_released_by: str | None = None
    hold_release_rationale: str | None = None


@dataclass(frozen=True, slots=True)
class AuditReceipt:
    """Immutable disposition and purge receipt for a reviewed candidate."""

    candidate_id: str
    decision: ReviewDecision
    facts_sha256: str
    artifacts: tuple[ArtifactRef, ...]
    artifact_inventory_complete: bool = False
    reviewer_id: str | None = None
    review_rationale: str | None = None
    canonical_persisted: bool = False
    canonical_target: str | None = None
    canonical_sha256: str | None = None
    canonical_persisted_at: str | None = None
    receipt_id: str = field(default_factory=new_id)
    purge_status: PurgeStatus = PurgeStatus.PURGE_PENDING
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.review_rationale is not None:
            validate_safe_text(self.review_rationale, "review_rationale")
        _validate_receipt_artifact_manifest(self)
        _validate_receipt_reviewer_and_rationale(self)
        _validate_receipt_canonical_proof(self)


def _validate_receipt_artifact_manifest(receipt: AuditReceipt) -> None:
    """Bound receipt artifact count and require a unique manifest."""

    if len(receipt.artifacts) > MAX_ARTIFACTS_PER_RECEIPT:
        raise ValueError(
            f"artifact inventory exceeds the limit of {MAX_ARTIFACTS_PER_RECEIPT}"
        )
    artifact_paths = [artifact.path for artifact in receipt.artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValueError("artifact inventory paths must be unique")


def _validate_receipt_reviewer_and_rationale(receipt: AuditReceipt) -> None:
    """Validate reviewer identity and rationale after manifest checks."""

    if receipt.reviewer_id is not None and not _REVIEWER_ID_RE.fullmatch(
        receipt.reviewer_id
    ):
        raise ValueError("reviewer_id must be a bounded opaque identifier")
    if receipt.review_rationale is not None:
        if not receipt.review_rationale.strip() or len(receipt.review_rationale) > 1000:
            raise ValueError("review rationale must contain 1-1000 characters")
        if "\n" in receipt.review_rationale or "\r" in receipt.review_rationale:
            raise ValueError("review rationale must be a single line")


def _validate_receipt_canonical_proof(receipt: AuditReceipt) -> None:
    """Require canonical proof fields exactly when persistence is confirmed."""

    proof = (
        receipt.canonical_target,
        receipt.canonical_sha256,
        receipt.canonical_persisted_at,
    )
    if receipt.canonical_persisted:
        if any(value is None or not value.strip() for value in proof):
            raise ValueError("canonical persistence requires target, hash, and timestamp")
        if receipt.canonical_sha256 is None or not _SHA256_RE.fullmatch(
            receipt.canonical_sha256
        ):
            raise ValueError("canonical persistence hash must be SHA-256")
        if receipt.canonical_target is None or len(receipt.canonical_target) > 2000:
            raise ValueError("canonical persistence target must be bounded")
        if "\n" in receipt.canonical_target or "\r" in receipt.canonical_target:
            raise ValueError("canonical persistence target must be one line")
    elif any(value is not None for value in proof):
        raise ValueError("canonical persistence proof fields require persisted=true")


@dataclass(frozen=True, slots=True)
class CriterionProgress:
    """Current verified/open state and proof links for one criterion."""

    criterion_id: str
    description: str
    status: CriterionStatus
    verification_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GoalCriteriaVersion:
    """Immutable snapshot of the original or amended goal contract."""

    revision: int
    criteria: tuple[SuccessCriterion, ...]
    reason: str
    created_at: str

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "criteria_version.reason")


@dataclass(frozen=True, slots=True)
class FactCapacity:
    """Current append budget; reaching it blocks capture without pruning facts."""

    goal_fact_count: int
    goal_fact_bytes: int
    goal_fact_count_limit: int
    goal_fact_bytes_limit: int
    goal_fact_count_remaining: int
    goal_fact_bytes_remaining: int
    project_fact_count: int
    project_fact_bytes: int
    project_fact_count_limit: int
    project_fact_bytes_limit: int
    project_fact_count_remaining: int
    project_fact_bytes_remaining: int
    append_available: bool
    open_gate: str | None = None


@dataclass(frozen=True, slots=True)
class FactCompactionProposal:
    """Exact routine facts proposed for reviewer-approved archival."""

    compaction_id: str
    project_id: str
    goal_id: str
    facts: tuple[Fact, ...]
    source_sha256: str
    source_bytes: int
    estimated_compressed_bytes: int

    def __post_init__(self) -> None:
        if not self.facts or len(self.facts) > MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError("compaction proposal must contain 1-64 facts")
        if len({fact.fact_id for fact in self.facts}) != len(self.facts):
            raise ValueError("compaction proposal fact IDs must be unique")
        if any(fact.goal_id != self.goal_id for fact in self.facts):
            raise ValueError("compaction proposal facts must share its goal")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("compaction source_sha256 must be lowercase SHA-256")
        if not 1 <= self.source_bytes <= MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ValueError("compaction source exceeds the bounded batch size")
        if not 1 <= self.estimated_compressed_bytes <= MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ValueError("compaction estimate exceeds the bounded batch size")


@dataclass(frozen=True, slots=True)
class FactArchiveReceipt:
    """Immutable receipt for compressed facts removed from the active ledger."""

    compaction_id: str
    archive_version: int
    project_id: str
    goal_id: str
    fact_ids: tuple[str, ...]
    source_sha256: str
    archive_sha256: str
    source_bytes: int
    compressed_bytes: int
    reviewer_id: str
    approval_reason: str
    created_at: str

    def __post_init__(self) -> None:
        if self.archive_version != 1:
            raise ValueError("unsupported fact archive version")
        if not self.fact_ids or len(self.fact_ids) > MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError("fact archive must contain 1-64 facts")
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError("fact archive fact IDs must be unique")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("archive source_sha256 must be lowercase SHA-256")
        if not _SHA256_RE.fullmatch(self.archive_sha256):
            raise ValueError("archive archive_sha256 must be lowercase SHA-256")
        if not self.reviewer_id or not _REVIEWER_ID_RE.fullmatch(self.reviewer_id):
            raise ValueError("archive reviewer_id must be a bounded opaque identifier")
        validate_safe_text(self.approval_reason, "fact_archive.approval_reason")
        if not self.approval_reason.strip() or len(self.approval_reason) > 1000:
            raise ValueError("archive approval reason must contain 1-1000 characters")
        if "\n" in self.approval_reason or "\r" in self.approval_reason:
            raise ValueError("archive approval reason must be one line")


@dataclass(frozen=True, slots=True)
class GoalSnapshot:
    """Bounded read model combining a goal with its current ledger state."""

    goal: GoalCard
    facts: tuple[Fact, ...]
    sde_candidates: tuple[SDECandidate, ...]
    pending_purges: tuple[AuditReceipt, ...]
    criteria: tuple[CriterionProgress, ...] = ()
    criteria_history: tuple[GoalCriteriaVersion, ...] = ()
    fact_capacity: FactCapacity | None = None
    sde_candidate_total: int | None = None
    sde_candidate_offset: int = 0
    sde_candidate_next_offset: int | None = None
    sde_candidate_status_counts: tuple[tuple[str, int], ...] = ()
    pending_purge_total: int | None = None
    pending_purge_offset: int = 0
    pending_purge_next_offset: int | None = None

    def __post_init__(self) -> None:
        """Keep status detail pages bounded and pagination metadata consistent."""

        if len(self.sde_candidates) > MAX_GOAL_STATUS_CANDIDATES:
            raise ValueError("goal status contains too many SDE candidates")
        if len(self.pending_purges) > MAX_GOAL_STATUS_PURGE_RECEIPTS:
            raise ValueError("goal status contains too many pending purge receipts")
        for label, total, offset, records, next_offset in (
            (
                "SDE candidate",
                self.sde_candidate_total,
                self.sde_candidate_offset,
                self.sde_candidates,
                self.sde_candidate_next_offset,
            ),
            (
                "pending purge",
                self.pending_purge_total,
                self.pending_purge_offset,
                self.pending_purges,
                self.pending_purge_next_offset,
            ),
        ):
            if total is None:
                if next_offset is not None:
                    raise ValueError(f"{label} next offset requires a total")
                continue
            if not is_exact_int(total) or total < 0:
                raise ValueError(f"{label} total must be a non-negative integer")
            if not is_exact_int(offset) or offset < 0:
                raise ValueError(f"{label} offset must be a non-negative integer")
            expected_next = offset + len(records) if offset + len(records) < total else None
            if next_offset != expected_next:
                raise ValueError(f"{label} next offset does not match its page")
        valid_sde_states = {status.value for status in SDEStatus}
        if any(
            status not in valid_sde_states
            or not is_exact_int(count)
            or count < 0
            for status, count in self.sde_candidate_status_counts
        ):
            raise ValueError(
                "SDE status counts must contain known states and non-negative counts"
            )


@dataclass(frozen=True, slots=True)
class GoalBullet:
    """One compact, source-linked bullet with an explicit truth category."""

    category: GoalBulletCategory
    text: str
    fact_id: str | None = None
    criterion_id: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        validate_safe_text(self.text, "goal_bullet.text")
        if not self.text.strip() or "\n" in self.text or "\r" in self.text:
            raise ValueError("goal projection bullets must be non-empty single lines")
        if len(self.text) > 1200:
            raise ValueError("goal projection bullet exceeds 1200 characters")

    def as_bullet(self) -> str:
        """Render the category and content as one short Markdown bullet."""

        label = self.category.value.replace("_", " ").capitalize()
        return f"- {label}: {self.text}"


@dataclass(frozen=True, slots=True)
class GoalBulletProjection:
    """Queryable compact view separating verified truth from open claims."""

    goal_id: str
    problem: str
    status: GoalStatus
    criteria: tuple[CriterionProgress, ...]
    bullets: tuple[GoalBullet, ...]
    next_action: str | None


@dataclass(frozen=True, slots=True)
class EventClassStorageUsage:
    """Logical event usage by lifecycle type and processing state."""

    event_type: str
    status: str
    count: int
    original_payload_bytes: int
    retained_payload_bytes: int


class EventFailureCategory(StrEnum):
    """Bounded operational class for failed event receipts."""

    EVIDENCE_REJECTED = "evidence_rejected"
    EVIDENCE_ADAPTER_ERROR = "evidence_adapter_error"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EventFailureCategoryUsage:
    """Failed or quarantined event count by fixed, content-free category."""

    category: EventFailureCategory
    count: int


@dataclass(frozen=True, slots=True)
class GoalStatusStorageUsage:
    """Project goal count by lifecycle status, without goal identifiers."""

    status: GoalStatus
    count: int


@dataclass(frozen=True, slots=True)
class GlobalEventInboxUsage:
    """Aggregate event-inbox ceiling without exposing cross-project contents."""

    receipt_count: int
    retained_record_bytes: int
    receipt_count_limit: int
    retained_record_bytes_limit: int
    can_accept_new_event: bool
    open_gate: str | None = None


@dataclass(frozen=True, slots=True)
class StagingUsage:
    """Content-free, bounded scan results for one configured staging tree."""

    entries_scanned: int
    regular_file_count: int
    observed_file_bytes: int
    directory_count: int
    symlink_count: int
    special_file_count: int
    inventory_complete: bool
    error_code: str | None = None
    classes: tuple[StagingClassUsage, ...] = ()

    def __post_init__(self) -> None:
        """Keep per-class observations consistent with scan totals."""

        if len(self.classes) > len(StagingArtifactClass):
            raise ValueError("staging usage has too many artifact classes")
        if len({item.artifact_class for item in self.classes}) != len(self.classes):
            raise ValueError("staging usage must not repeat an artifact class")
        if sum(item.regular_file_count for item in self.classes) != self.regular_file_count:
            raise ValueError("staging class file counts must match scan totals")
        if sum(item.observed_file_bytes for item in self.classes) != self.observed_file_bytes:
            raise ValueError("staging class byte totals must match scan totals")


@dataclass(frozen=True, slots=True)
class StagingClassUsage:
    """Content-free staging totals for one fixed temporary artifact class."""

    artifact_class: StagingArtifactClass
    regular_file_count: int
    observed_file_bytes: int

    def __post_init__(self) -> None:
        """Reject negative or non-integer observed totals."""

        if (
            isinstance(self.regular_file_count, bool)
            or self.regular_file_count < 0
        ):
            raise ValueError("staging class file count must be a non-negative integer")
        if (
            isinstance(self.observed_file_bytes, bool)
            or self.observed_file_bytes < 0
        ):
            raise ValueError("staging class byte count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class StagingArtifactInventory:
    """Hash manifest scoped to one goal beneath a project's staging root."""

    artifacts: tuple[ArtifactRef, ...]
    usage: StagingUsage
    manifest_sha256: str | None
    scope_goal_id: str | None = None

    def __post_init__(self) -> None:
        """Keep any explicit filesystem scope a single bounded identifier."""

        if self.scope_goal_id is not None and not _REVIEWER_ID_RE.fullmatch(
            self.scope_goal_id
        ):
            raise ValueError("scope_goal_id must be a bounded opaque identifier")


@dataclass(frozen=True, slots=True)
class ProjectStorageUsage:
    """Project record/staging estimates plus separate global SQLite file sizes."""

    project_id: str
    goal_count: int
    goal_statuses: tuple[GoalStatusStorageUsage, ...]
    goal_record_bytes: int
    fact_count: int
    fact_record_bytes: int
    sde_candidate_count: int
    sde_record_bytes: int
    sde_correction_count: int
    sde_correction_record_bytes: int
    sde_quality_feedback_count: int
    sde_quality_feedback_record_bytes: int
    audit_receipt_count: int
    audit_record_bytes: int
    artifact_count: int
    artifact_record_bytes: int
    event_receipt_count: int
    event_payload_bytes_received: int
    event_payload_bytes_retained: int
    event_classes: tuple[EventClassStorageUsage, ...]
    event_failures: tuple[EventFailureCategoryUsage, ...]
    global_event_inbox: GlobalEventInboxUsage
    logical_record_bytes: int
    staging: StagingUsage | None
    global_database_bytes: int | None
    global_wal_bytes: int | None
    fact_count_limit: int = MAX_FACTS_PER_PROJECT
    fact_record_bytes_limit: int = MAX_FACT_BYTES_PER_PROJECT
    fact_capacity_reached: bool = False
    fact_archive_batch_count: int = 0
    fact_archive_item_count: int = 0
    fact_archive_compressed_bytes: int = 0
    fact_archive_logical_bytes: int = 0
    fact_archive_logical_bytes_limit: int = MAX_FACT_ARCHIVE_BYTES_PER_PROJECT
    fact_archive_bytes_remaining: int = MAX_FACT_ARCHIVE_BYTES_PER_PROJECT
    staging_project_byte_limit: int | None = None
    staging_project_file_limit: int | None = None


@dataclass(frozen=True, slots=True)
class ProjectOperationalCounts:
    """Exact aggregate queue counts without loading unbounded work records."""

    pending_review_count: int
    pending_purge_receipt_count: int
    pending_purge_artifact_count: int


@dataclass(frozen=True, slots=True)
class ProjectActivitySnapshot:
    """Content-free capture and curation activity, separate from readiness."""

    project_id: str
    observed_at: str
    event_receipt_count: int
    processed_event_count: int
    received_event_count: int
    failed_event_count: int
    quarantined_event_count: int
    last_event_received_at: str | None
    last_event_processed_at: str | None
    goal_count: int
    fact_count: int
    sde_candidate_count: int
    pending_sde_count: int
    approved_sde_count: int
    rejected_sde_count: int
    events_observed: bool

    def __post_init__(self) -> None:
        """Ensure aggregate totals cannot contradict their component counts."""

        counts = (
            self.event_receipt_count,
            self.processed_event_count,
            self.received_event_count,
            self.failed_event_count,
            self.quarantined_event_count,
            self.goal_count,
            self.fact_count,
            self.sde_candidate_count,
            self.pending_sde_count,
            self.approved_sde_count,
            self.rejected_sde_count,
        )
        if any(not is_exact_int(value) or value < 0 for value in counts):
            raise ValueError("activity counts must be non-negative integers")
        if self.event_receipt_count != sum(counts[1:5]):
            raise ValueError("event receipt total must match its processing states")
        if self.sde_candidate_count != sum(counts[8:11]):
            raise ValueError("SDE total must match its review states")
        if type(self.events_observed) is not bool:
            raise ValueError("events_observed must be a boolean")
        if self.events_observed != (self.event_receipt_count > 0):
            raise ValueError("events_observed must match retained event receipts")


@dataclass(frozen=True, slots=True)
class DependencyProbeObservation:
    """One trusted host probe result with its observation timestamp."""

    ready: bool | None
    observed_at: str | None


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    """One required host-owned dependency's reported readiness."""

    name: str
    status: OperationalHealth
    observed_at: str | None = None
    age_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class ProjectHealthSnapshot:
    """Bounded, content-free project health summary with explicit open gates."""

    project_id: str
    observed_at: str
    status: OperationalHealth
    event_received_count: int
    event_failed_count: int
    event_quarantined_count: int
    event_claimed_count: int
    event_expired_claim_count: int
    oldest_pending_event_age_seconds: int | None
    operational_counts: ProjectOperationalCounts
    fact_capacity_reached: bool
    event_capacity_available: bool
    staging_inventory_complete: bool | None
    staging_regular_file_count: int | None
    dependencies: tuple[DependencyHealth, ...]
    gate_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SDEReviewDetail:
    """Review packet containing only the goal and selected supporting facts."""

    candidate: SDECandidate
    goal: GoalCard
    facts: tuple[Fact, ...]
    receipt: AuditReceipt | None = None
    corrections: tuple[SDECorrection, ...] = ()


@dataclass(frozen=True, slots=True)
class SDEReviewPacket:
    """One reviewer's bounded candidate detail and current artifact inventory."""

    detail: SDEReviewDetail
    artifact_inventory: StagingArtifactInventory
