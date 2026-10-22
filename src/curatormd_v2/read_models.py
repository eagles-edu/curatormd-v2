"""Bounded read-side goal, operations, and storage projection records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .content_safety import validate_safe_text
from .models import (
    MAX_ARTIFACTS_PER_RECEIPT,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    MAX_FACT_COMPACTION_BATCH_FACTS,
    ArtifactRef,
    AuditReceipt,
    CriterionProgress,
    EvidenceRef,
    Fact,
    GoalBulletCategory,
    GoalCard,
    GoalStatus,
    OperationalHealth,
    PurgeStatus,
    SDECandidate,
    SDECorrection,
)
from .record_validation import (
    REVIEWER_ID_RE as _REVIEWER_ID_RE,
    SHA256_RE as _SHA256_RE,
    parse_aware_timestamp as _parse_aware_timestamp,
)
from .staging_models import StagingUsage
from .validation import is_exact_bool, is_exact_int


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
class StagingExpirySnapshot:
    """Fact/SDE-ready or max-age purge candidates; no approval is implied."""

    eligible_artifacts: tuple[ArtifactRef, ...]
    held_artifacts: tuple[ArtifactRef, ...]
    inventory_complete: bool
    unknown_age_count: int
    cutoff_at: str
    manifest_sha256: str | None
    pending_sde_artifact_count: int = 0

    def __post_init__(self) -> None:
        if type(self.inventory_complete) is not bool:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("inventory_complete must be boolean")
        if (
            type(self.unknown_age_count) is not int  # pylint: disable=unidiomatic-typecheck
            or self.unknown_age_count < 0
        ):
            raise ValueError("unknown_age_count must be a non-negative integer")
        if self.inventory_complete and self.unknown_age_count:
            raise ValueError("complete expiry inventory cannot have unknown ages")
        if (
            type(self.pending_sde_artifact_count) is not int  # pylint: disable=unidiomatic-typecheck
            or self.pending_sde_artifact_count < 0
        ):
            raise ValueError("pending_sde_artifact_count must be non-negative")
        if self.inventory_complete != (self.manifest_sha256 is not None):
            raise ValueError("only complete expiry snapshots have a manifest")
        if {item.path for item in self.eligible_artifacts} & {
            item.path for item in self.held_artifacts
        }:
            raise ValueError("eligible and held expiry artifacts must be disjoint")
        if any(item.retention_hold is None for item in self.held_artifacts):
            raise ValueError("held expiry artifacts must declare their hold class")
        if self.manifest_sha256 is not None and not _SHA256_RE.fullmatch(
            self.manifest_sha256
        ):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256")
        _parse_aware_timestamp("cutoff_at", self.cutoff_at)


@dataclass(frozen=True, slots=True)
class ExpiryPurgeReceipt:
    """Durable local-human approval for one exact expired artifact inventory."""

    receipt_id: str
    project_id: str
    reviewer_id: str
    manifest_sha256: str
    artifacts: tuple[ArtifactRef, ...]
    status: PurgeStatus
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("project_id", self.project_id),
            ("reviewer_id", self.reviewer_id),
        ):
            if not _REVIEWER_ID_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded opaque identifier")
        if not _SHA256_RE.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256")
        if not self.artifacts or len(self.artifacts) > MAX_ARTIFACTS_PER_RECEIPT:
            raise ValueError("expiry receipt must contain 1-500 exact artifacts")
        paths = tuple(item.path for item in self.artifacts)
        if len(paths) != len(set(paths)):
            raise ValueError("expiry receipt artifacts must have unique paths")
        if self.status not in {PurgeStatus.COMPLETE, PurgeStatus.PURGE_PENDING}:
            raise ValueError("expiry purge receipt has an invalid status")
        _parse_aware_timestamp("created_at", self.created_at)
        _parse_aware_timestamp("updated_at", self.updated_at)


@dataclass(frozen=True, slots=True)
class CleanupAuthorizationReceipt:
    """Distinct audit receipt for cleanup authorized by one SDE review action."""

    receipt_id: str
    project_id: str
    reviewer_id: str
    manifest_sha256: str
    approved_at: str
    canonical_persisted: bool = False
    canonical_target: str | None = None
    canonical_sha256: str | None = None
    canonical_persisted_at: str | None = None

    def __post_init__(self) -> None:
        for name, value in (("receipt_id", self.receipt_id),
                            ("project_id", self.project_id),
                            ("reviewer_id", self.reviewer_id)):
            if not _REVIEWER_ID_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded opaque identifier")
        if not _SHA256_RE.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256")
        _parse_aware_timestamp("approved_at", self.approved_at)
        if self.canonical_persisted:
            if self.canonical_target is None or self.canonical_sha256 is None:
                raise ValueError("persisted cleanup approval requires target and hash")
            if not self.canonical_target.strip() or len(self.canonical_target) > 2000:
                raise ValueError("cleanup canonical target must be bounded")
            if not _SHA256_RE.fullmatch(self.canonical_sha256):
                raise ValueError("cleanup canonical hash must be lowercase SHA-256")
            if self.canonical_persisted_at is None:
                raise ValueError("persisted cleanup approval requires a timestamp")
            _parse_aware_timestamp(
                "canonical_persisted_at", self.canonical_persisted_at
            )


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
    pending_expiry_purge_receipt_count: int
    pending_expiry_purge_artifact_count: int


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
        if not is_exact_bool(self.events_observed):
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
