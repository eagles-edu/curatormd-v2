"""Typed, bounded records for the Curator V2 goal ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import import_module
import re
from typing import TYPE_CHECKING, TypeGuard
from uuid import uuid4

from .content_safety import validate_safe_text
from .domain_enums import (
    ArtifactStatus,
    EvidenceOutcome,
    FactKind,
    GoalStatus,
    Materiality,
    PurgeStatus,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewDecision,
    SDEQualityFeedbackLabel,
    SDEStatus,
)
from .record_validation import (
    REVIEWER_ID_RE as _REVIEWER_ID_RE,
    SHA256_RE as _SHA256_RE,
    parse_aware_timestamp as _parse_aware_timestamp,
)
from .validation import is_exact_int, validate_checklist_snapshot


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

__all__ = [
    "CriterionProgress",
    "CriterionStatus",
    "FactCapacity",
    "FactCompactionProposal",
    "GoalBulletCategory",
    "GoalCriteriaVersion",
    "GoalSnapshot",
    "OperationalHealth",
    "PurgeFailureCode",
    "ArtifactEvidenceBinding",
    "ArtifactEvidenceDependency",
    "ArtifactReviewDependency",
    "CleanupAuthorizationReceipt",
    "DependencyHealth",
    "DependencyProbeObservation",
    "EventClassStorageUsage",
    "EventPayloadScrubUsage",
    "EventFailureCategory",
    "EventFailureCategoryUsage",
    "ExpiryPurgeReceipt",
    "FactArchiveReceipt",
    "GoalBullet",
    "GoalBulletProjection",
    "GlobalEventInboxUsage",
    "GoalStatusStorageUsage",
    "ProjectActivitySnapshot",
    "ProjectControlPlaneStorageUsage",
    "ProjectHealthSnapshot",
    "ProjectOperationalCounts",
    "ProjectStorageUsage",
    "SQLiteDatabaseFileUsage",
    "SQLiteDatabasePageUsage",
    "SQLitePhysicalStorageUsage",
    "StorageClassUsage",
    "StoragePhysicalClassUsage",
    "SDEReviewDetail",
    "SDEReviewPacket",
    "StagingArtifactInventory",
    "StagingExpirySnapshot",
    "artifact_dependency_map_sha256",
]
_READ_MODEL_NAMES = frozenset(__all__)
_PROJECTION_READ_MODEL_NAMES = frozenset(
    {
        "CriterionProgress",
        "FactCapacity",
        "FactCompactionProposal",
        "GoalCriteriaVersion",
        "GoalSnapshot",
    }
)
_DOMAIN_ENUM_NAMES = frozenset(
    {
        "CriterionStatus",
        "GoalBulletCategory",
        "OperationalHealth",
        "PurgeFailureCode",
    }
)

if TYPE_CHECKING:
    from .domain_enums import (
        CriterionStatus,
        GoalBulletCategory,
        OperationalHealth,
        PurgeFailureCode,
    )
    from .goal_read_models import (
        CriterionProgress,
        FactCapacity,
        FactCompactionProposal,
        GoalCriteriaVersion,
        GoalSnapshot,
    )
    from .read_models import (
        ArtifactEvidenceBinding,
        ArtifactEvidenceDependency,
        ArtifactReviewDependency,
        CleanupAuthorizationReceipt,
        DependencyHealth,
        DependencyProbeObservation,
        EventClassStorageUsage,
        EventPayloadScrubUsage,
        EventFailureCategory,
        EventFailureCategoryUsage,
        ExpiryPurgeReceipt,
        FactArchiveReceipt,
        GoalBullet,
        GoalBulletProjection,
        GlobalEventInboxUsage,
        GoalStatusStorageUsage,
        ProjectActivitySnapshot,
        ProjectControlPlaneStorageUsage,
        ProjectHealthSnapshot,
        ProjectOperationalCounts,
        SQLiteDatabaseFileUsage,
        SQLiteDatabasePageUsage,
        SQLitePhysicalStorageUsage,
        StorageClassUsage,
        StoragePhysicalClassUsage,
        ProjectStorageUsage,
        SDEReviewDetail,
        SDEReviewPacket,
        StagingArtifactInventory,
        StagingExpirySnapshot,
        artifact_dependency_map_sha256,
    )


def __getattr__(name: str) -> object:
    """Preserve model imports for records housed in focused modules."""

    if name not in _READ_MODEL_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name in _DOMAIN_ENUM_NAMES:
        module_name = "domain_enums"
    elif name in _PROJECTION_READ_MODEL_NAMES:
        module_name = "goal_read_models"
    else:
        module_name = "read_models"
    module = import_module(f"{__package__}.{module_name}")
    return getattr(module, name)


def utc_now() -> str:
    """Return a sortable UTC timestamp with explicit timezone information."""

    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    """Generate an opaque identifier suitable for ledger records."""

    return uuid4().hex


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
class GoalStartOptions:
    """Optional ownership and lifecycle metadata for accepted goal intake."""

    owner: str | None = None
    next_action: str | None = None
    parent_goal_id: str | None = None
    depends_on_goal_ids: tuple[str, ...] = ()
    initial_status: GoalStatus = GoalStatus.PLANNED
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChecklistGoalStartRequest:
    """Exact consumer checklist source and explicit goal acceptance fields."""

    checklist_id: str
    problem: str
    success_criteria: tuple[SuccessCriterion, ...]
    exact_item_text: str
    options: GoalStartOptions = GoalStartOptions()


@dataclass(frozen=True, slots=True)
class GoalSubtaskStartRequest:
    """Accepted child-goal criteria and their explicit parent relationship."""

    parent_goal_id: str
    problem: str
    success_criteria: tuple[SuccessCriterion, ...]
    owner: str | None = None
    next_action: str | None = None
    depends_on_goal_ids: tuple[str, ...] = ()
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """A compact pointer to proof; output/transcript contents are not stored."""

    evidence_kind: str
    locator: str
    sha256: str
    outcome: EvidenceOutcome
    occurrence_id: str | None = None

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
        if self.occurrence_id is not None and not re.fullmatch(
            r"[0-9a-f]{32}", self.occurrence_id
        ):
            raise ValueError("evidence occurrence_id must be a lowercase UUID hex value")


@dataclass(frozen=True, slots=True)
class EvidenceAttestation:  # pylint: disable=too-many-instance-attributes  # Versioned evidence receipt fields are atomic.
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
    occurrence_id: str | None = None

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
        if self.occurrence_id is not None and not re.fullmatch(
            r"[0-9a-f]{32}", self.occurrence_id
        ):
            raise ValueError("attested occurrence_id must be a lowercase UUID hex value")
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
class GoalCard:  # pylint: disable=too-many-instance-attributes  # Immutable goal snapshot mirrors the persisted contract.
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


@dataclass(frozen=True, slots=True)
class GoalChildrenPageRequest:
    """Parent and filters for one bounded direct-child goal page."""

    parent_goal_id: str
    offset: int = 0
    limit: int = 50
    statuses: tuple[GoalStatus, ...] = ()


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

    validate_checklist_snapshot(
        goal.checklist_id,
        goal.checklist_version,
        goal.checklist_source_text,
    )


@dataclass(frozen=True, slots=True)
class Fact:  # pylint: disable=too-many-instance-attributes  # Immutable fact record mirrors the persisted contract.
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
                or attestation.occurrence_id != evidence.occurrence_id
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
class SDECandidate:  # pylint: disable=too-many-instance-attributes  # Review candidate fields are persisted as one record.
    """Reviewable significance proposal linked to supporting goal facts."""

    goal_id: str
    materiality: Materiality
    rationale: str
    fact_ids: tuple[str, ...]
    impact: str | None = None
    retrieval_value: str | None = None
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
        for name, value in (
            ("impact", self.impact),
            ("retrieval_value", self.retrieval_value),
        ):
            if value is None:
                continue  # Existing candidates remain readable after migration.
            validate_safe_text(value, f"sde.{name}")
            if not value.strip() or len(value) > 1000:
                raise ValueError(f"SDE {name} must contain 1-1000 characters")
            if "\n" in value or "\r" in value:
                raise ValueError(f"SDE {name} must be a single compact line")
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
    device_id: int | None = None
    inode_id: int | None = None
    occurrence_id: str | None = None
    reacquisition_action: ReacquisitionAction = ReacquisitionAction.NOT_RECORDED

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
        if (self.device_id is None) != (self.inode_id is None):
            raise ValueError("artifact filesystem identity must include device and inode")
        if self.device_id is not None and (
            not is_exact_int(self.device_id)
            or self.device_id < 0
            or not is_exact_int(self.inode_id)
            or self.inode_id < 0
        ):
            raise ValueError("artifact filesystem identity must be nonnegative integers")
        if self.occurrence_id is not None and not re.fullmatch(
            r"[0-9a-f]{32}", self.occurrence_id
        ):
            raise ValueError("artifact occurrence_id must be a lowercase UUID hex value")
        # Exact type rejects runtime values from unrelated enum classes.
        if type(self.reacquisition_action) is not ReacquisitionAction:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("reacquisition_action must be a supported reviewer decision")


@dataclass(frozen=True, slots=True)
class SDEConfirmationRequest:
    """Human disposition and exact inventory submitted as one review request."""

    candidate_id: str
    decision: ReviewDecision
    artifacts: tuple[ArtifactRef, ...]
    artifact_inventory_complete: bool
    dependency_map_sha256: str | None = None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class SDECorrectionRequest:
    """Authenticated correction text linked to one decided SDE candidate."""

    correction_id: str
    candidate_id: str
    correction: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SDEQualityFeedbackRequest:
    """One authenticated reviewer's quality label for a decided candidate."""

    feedback_id: str
    candidate_id: str
    label: SDEQualityFeedbackLabel
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class ArtifactCleanupAuthorizationRequest:
    """Exact displayed inventory and projection digests for cleanup approval."""

    receipt_id: str
    artifacts: tuple[ArtifactRef, ...]
    manifest_sha256: str
    dependency_map_sha256: str
    target: str


@dataclass(frozen=True, slots=True)
class PurgeTargetRecord:  # pylint: disable=too-many-instance-attributes  # Retry and hold receipt fields are one durable record.
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
    approval_stale: bool = False


@dataclass(frozen=True, slots=True)
class AuditReceipt:  # pylint: disable=too-many-instance-attributes  # Versioned review and purge receipt fields are atomic.
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
    cleanup_authorized: bool = False
    cleanup_reviewer_id: str | None = None
    cleanup_manifest_sha256: str | None = None
    cleanup_dependency_map_sha256: str | None = None
    cleanup_approved_at: str | None = None
    cleanup_canonical_persisted: bool = False

    def __post_init__(self) -> None:
        if self.review_rationale is not None:
            validate_safe_text(self.review_rationale, "review_rationale")
        _validate_receipt_artifact_manifest(self)
        _validate_receipt_reviewer_and_rationale(self)
        _validate_receipt_canonical_proof(self)
        if self.cleanup_authorized:
            if self.cleanup_reviewer_id is None or self.cleanup_manifest_sha256 is None:
                raise ValueError("cleanup authorization requires reviewer and manifest")
            if not _REVIEWER_ID_RE.fullmatch(self.cleanup_reviewer_id):
                raise ValueError("cleanup reviewer must be a bounded opaque identifier")
            if not _SHA256_RE.fullmatch(self.cleanup_manifest_sha256):
                raise ValueError("cleanup manifest must be a lowercase SHA-256")
            if self.cleanup_dependency_map_sha256 is not None and not _SHA256_RE.fullmatch(
                self.cleanup_dependency_map_sha256
            ):
                raise ValueError("cleanup dependency map must be a lowercase SHA-256")
            if self.cleanup_approved_at is None:
                raise ValueError("cleanup authorization requires its approval timestamp")
            _parse_aware_timestamp("cleanup_approved_at", self.cleanup_approved_at)
            if self.cleanup_canonical_persisted and not self.canonical_persisted:
                raise ValueError("cleanup projection cannot precede canonical facts")
        elif any(
            value is not None
            for value in (
                self.cleanup_reviewer_id,
                self.cleanup_manifest_sha256,
                self.cleanup_dependency_map_sha256,
                self.cleanup_approved_at,
            ) or self.cleanup_canonical_persisted
        ):
            raise ValueError("cleanup authorization metadata requires authorization")


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
