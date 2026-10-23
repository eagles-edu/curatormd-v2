"""Bounded read-side goal, operations, and storage projection records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import re
from typing import Literal

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
    EvidenceAttestation,
    EvidenceRef,
    Fact,
    GoalBulletCategory,
    GoalCard,
    GoalStatus,
    OperationalHealth,
    PurgeStatus,
    ReacquisitionAction,
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
# Flat receipt contract keeps archive identity, hashes, and sizes individually serialized.
class FactArchiveReceipt:  # pylint: disable=too-many-instance-attributes
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
class EventPayloadScrubUsage:
    """Global scrub-queue totals and the unassigned subset."""

    record_count: int
    logical_bytes: int
    unassigned_record_count: int
    unassigned_logical_bytes: int


@dataclass(frozen=True, slots=True)
class GlobalEventInboxUsage:
    """Aggregate event capacity and scrub queues without row contents."""

    receipt_count: int
    retained_record_bytes: int
    receipt_count_limit: int
    retained_record_bytes_limit: int
    can_accept_new_event: bool
    payload_scrub_queue: EventPayloadScrubUsage
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
# Flat public receipt contract preserves exact reviewer, manifest, and status fields.
class ExpiryPurgeReceipt:  # pylint: disable=too-many-instance-attributes
    """Durable local-human approval for one exact expired artifact inventory."""

    receipt_id: str
    project_id: str
    reviewer_id: str
    manifest_sha256: str
    artifacts: tuple[ArtifactRef, ...]
    status: PurgeStatus
    created_at: str
    updated_at: str
    approval_stale_artifacts: tuple[ArtifactRef, ...] = ()

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
        stale_paths = tuple(item.path for item in self.approval_stale_artifacts)
        if len(stale_paths) != len(set(stale_paths)) or not set(stale_paths) <= set(paths):
            raise ValueError("stale expiry targets must be unique receipt artifacts")
        if self.status not in {PurgeStatus.COMPLETE, PurgeStatus.PURGE_PENDING}:
            raise ValueError("expiry purge receipt has an invalid status")
        _parse_aware_timestamp("created_at", self.created_at)
        _parse_aware_timestamp("updated_at", self.updated_at)


@dataclass(frozen=True, slots=True)
# Flat authorization receipt contract preserves exact inventory and projection fields.
class CleanupAuthorizationReceipt:  # pylint: disable=too-many-instance-attributes
    """Distinct audit receipt for cleanup authorized by one SDE review action."""

    receipt_id: str
    project_id: str
    reviewer_id: str
    manifest_sha256: str
    dependency_map_sha256: str | None
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
        if self.dependency_map_sha256 is not None and not _SHA256_RE.fullmatch(
            self.dependency_map_sha256
        ):
            raise ValueError("dependency_map_sha256 must be a lowercase SHA-256")
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
# API/MCP contract keeps each content-free storage counter independently serializable.
class ProjectStorageUsage:  # pylint: disable=too-many-instance-attributes
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
    event_cursor_count: int
    event_cursor_record_bytes: int
    event_retry_audit_count: int
    event_retry_audit_record_bytes: int
    staging_artifact_time_count: int
    staging_artifact_time_record_bytes: int
    staging_artifact_occurrence_count: int
    staging_artifact_occurrence_record_bytes: int
    expiry_purge_receipt_count: int
    expiry_purge_receipt_record_bytes: int
    expiry_purge_target_count: int
    expiry_purge_target_record_bytes: int
    cleanup_authorization_count: int
    cleanup_authorization_record_bytes: int
    event_payload_scrub_count: int
    event_payload_scrub_record_bytes: int
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
class StorageClassUsage:
    """Aggregate logical storage for one durable table class."""

    class_name: str
    record_count: int
    logical_bytes: int


@dataclass(frozen=True, slots=True)
class StoragePhysicalClassUsage:
    """Global SQLite page allocation attributed to one table and its indexes."""

    class_name: str
    page_count: int
    allocated_bytes: int
    payload_bytes: int
    unused_bytes: int


@dataclass(frozen=True, slots=True)
class SQLiteDatabasePageUsage:
    """Main-database page allocation, with shared page space separated."""

    page_size: int
    page_count: int
    freelist_page_count: int
    allocated_bytes: int
    attributed_btree_bytes: int | None
    unattributed_database_bytes: int | None


@dataclass(frozen=True, slots=True)
class SQLiteDatabaseFileUsage:
    """Current main database and WAL file sizes, when file-backed."""

    database_bytes: int | None
    wal_file_bytes: int | None


@dataclass(frozen=True, slots=True)
class SQLitePhysicalStorageUsage:
    """Content-free SQLite allocation with page and file facts separated."""

    status: Literal["available", "unsupported"]
    classes: tuple[StoragePhysicalClassUsage, ...]
    pages: SQLiteDatabasePageUsage
    files: SQLiteDatabaseFileUsage


@dataclass(frozen=True, slots=True)
class ProjectControlPlaneStorageUsage:
    """Admin-only project storage plus separate unassigned global classes."""

    project_id: str
    classes: tuple[StorageClassUsage, ...]
    logical_record_bytes: int
    global_classes: tuple[StorageClassUsage, ...] = ()
    global_logical_bytes: int = 0
    sqlite_physical: SQLitePhysicalStorageUsage | None = None


@dataclass(frozen=True, slots=True)
class ProjectOperationalCounts:
    """Exact aggregate queue counts without loading unbounded work records."""

    pending_review_count: int
    pending_purge_receipt_count: int
    pending_purge_artifact_count: int
    pending_expiry_purge_receipt_count: int
    pending_expiry_purge_artifact_count: int


@dataclass(frozen=True, slots=True)
# API/MCP contract keeps activity counters and timestamps as stable top-level fields.
class ProjectActivitySnapshot:  # pylint: disable=too-many-instance-attributes
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
# API/MCP contract keeps dependency gates and operating counts individually serialized.
class ProjectHealthSnapshot:  # pylint: disable=too-many-instance-attributes
    """Bounded, content-free project health summary with explicit open gates."""

    project_id: str
    observed_at: str
    database_observed_at: str | None
    database_observation_complete: bool
    status: OperationalHealth
    event_received_count: int | None
    event_failed_count: int | None
    event_quarantined_count: int | None
    event_claimed_count: int | None
    event_expired_claim_count: int | None
    oldest_pending_event_age_seconds: int | None
    operational_counts: ProjectOperationalCounts | None
    fact_capacity_reached: bool | None
    event_capacity_available: bool | None
    staging_inventory_complete: bool | None
    staging_observed_at: str | None
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


class ArtifactEvidenceBinding(StrEnum):
    """Strength of the relationship between an inventory file and evidence."""

    UNMAPPED = "unmapped"
    PATH_AND_DIGEST_MATCH_OCCURRENCE_UNBOUND = "path_and_digest_match_occurrence_unbound"
    OCCURRENCE_MATCH = "occurrence_match"
    OCCURRENCE_MISMATCH = "occurrence_mismatch"
    OCCURRENCE_UNATTESTED = "occurrence_unattested"
    OCCURRENCE_MIXED = "occurrence_mixed"


@dataclass(frozen=True, slots=True)
class ArtifactEvidenceDependency:
    """One evidence reference tied to its fact and criterion, without its content."""

    fact_id: str
    criterion_id: str | None
    criterion_status: str | None
    evidence: EvidenceRef
    attested_occurrence_id: str | None = None

    def __post_init__(self) -> None:
        if self.attested_occurrence_id is not None and (
            not re.fullmatch(r"[0-9a-f]{32}", self.attested_occurrence_id)
            or self.attested_occurrence_id != self.evidence.occurrence_id
        ):
            raise ValueError("attested occurrence must match the evidence reference")


@dataclass(frozen=True, slots=True)
class ArtifactReviewDependency:
    """Reviewer map entry for one exact staged-file occurrence."""

    artifact: ArtifactRef
    binding: ArtifactEvidenceBinding
    evidence_dependencies: tuple[ArtifactEvidenceDependency, ...] = ()
    reacquisition_action: ReacquisitionAction = ReacquisitionAction.NOT_RECORDED

    def __post_init__(self) -> None:
        if self.binding is ArtifactEvidenceBinding.UNMAPPED:
            if self.evidence_dependencies:
                raise ValueError("unmapped artifacts cannot contain evidence dependencies")
        elif not self.evidence_dependencies:
            raise ValueError("mapped artifacts require an evidence dependency")
        elif any(
            linked.evidence.locator != self.artifact.path
            or linked.evidence.sha256 != self.artifact.sha256
            for linked in self.evidence_dependencies
        ):
            raise ValueError("artifact dependency evidence must match path and digest")
        elif self.binding is ArtifactEvidenceBinding.OCCURRENCE_MATCH and any(
            self.artifact.occurrence_id is None
            or linked.attested_occurrence_id != self.artifact.occurrence_id
            or linked.evidence.occurrence_id != self.artifact.occurrence_id
            for linked in self.evidence_dependencies
        ):
            raise ValueError("occurrence-bound evidence must have a matching attestation")
        elif self.binding is ArtifactEvidenceBinding.OCCURRENCE_UNATTESTED and not any(
            linked.evidence.occurrence_id is not None
            and linked.attested_occurrence_id is None
            for linked in self.evidence_dependencies
        ):
            raise ValueError("unattested occurrence entries require an evidence occurrence ID")
        elif self.binding is ArtifactEvidenceBinding.OCCURRENCE_MISMATCH and not any(
            linked.attested_occurrence_id is not None
            and linked.attested_occurrence_id != self.artifact.occurrence_id
            for linked in self.evidence_dependencies
        ):
            raise ValueError("occurrence mismatch requires a different attested occurrence ID")
        elif self.binding is ArtifactEvidenceBinding.OCCURRENCE_MIXED and not (
            any(
                linked.attested_occurrence_id == self.artifact.occurrence_id
                and self.artifact.occurrence_id is not None
                for linked in self.evidence_dependencies
            )
            and any(
                linked.attested_occurrence_id != self.artifact.occurrence_id
                for linked in self.evidence_dependencies
            )
        ):
            raise ValueError("mixed occurrence entries require both matching and other evidence")
        # Exact type rejects runtime values from unrelated enum classes.
        if type(self.reacquisition_action) is not ReacquisitionAction:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("unsupported artifact reacquisition action")


def build_artifact_review_dependencies(
    facts: tuple[Fact, ...],
    criteria: tuple[CriterionProgress, ...],
    artifacts: tuple[ArtifactRef, ...],
) -> tuple[ArtifactReviewDependency, ...]:
    """Link evidence refs by path/digest and report occurrence identity explicitly."""

    criterion_status = {item.criterion_id: item.status.value for item in criteria}
    evidence_by_path_and_digest: dict[
        tuple[str, str], list[ArtifactEvidenceDependency]
    ] = {}
    for fact in facts:
        attestations: tuple[EvidenceAttestation | None, ...] = (
            fact.verification_attestations
            if fact.verification_attestations
            else (None,) * len(fact.evidence)
        )
        for evidence, attestation in zip(fact.evidence, attestations, strict=True):
            evidence_by_path_and_digest.setdefault(
                (evidence.locator, evidence.sha256), []
            ).append(
                ArtifactEvidenceDependency(
                    fact_id=fact.fact_id,
                    criterion_id=fact.criterion_id,
                    criterion_status=(
                        criterion_status.get(fact.criterion_id)
                        if fact.criterion_id is not None
                        else None
                    ),
                    evidence=evidence,
                    attested_occurrence_id=(
                        attestation.occurrence_id if attestation is not None else None
                    ),
                )
            )
    dependencies: list[ArtifactReviewDependency] = []
    for artifact in artifacts:
        evidence_dependencies = tuple(
            sorted(
                evidence_by_path_and_digest.get(
                    (artifact.path, artifact.sha256), []
                ),
                key=lambda item: (
                    item.fact_id,
                    item.criterion_id or "",
                    item.evidence.evidence_kind,
                    item.evidence.locator,
                    item.evidence.sha256,
                ),
            )
        )
        evidence_occurrences = {
            item.attested_occurrence_id for item in evidence_dependencies
        }
        if not evidence_dependencies:
            binding = ArtifactEvidenceBinding.UNMAPPED
        elif (
            artifact.occurrence_id is not None
            and evidence_occurrences == {artifact.occurrence_id}
        ):
            binding = ArtifactEvidenceBinding.OCCURRENCE_MATCH
        elif any(item.attested_occurrence_id is not None for item in evidence_dependencies):
            if any(
                item.attested_occurrence_id == artifact.occurrence_id
                for item in evidence_dependencies
            ):
                binding = ArtifactEvidenceBinding.OCCURRENCE_MIXED
            else:
                binding = ArtifactEvidenceBinding.OCCURRENCE_MISMATCH
        elif any(item.evidence.occurrence_id is not None for item in evidence_dependencies):
            binding = ArtifactEvidenceBinding.OCCURRENCE_UNATTESTED
        else:
            binding = ArtifactEvidenceBinding.PATH_AND_DIGEST_MATCH_OCCURRENCE_UNBOUND
        dependencies.append(
            ArtifactReviewDependency(
                artifact=artifact,
                binding=binding,
                evidence_dependencies=evidence_dependencies,
                reacquisition_action=artifact.reacquisition_action,
            )
        )
    return tuple(dependencies)


def artifact_dependency_map_sha256(
    dependencies: tuple[ArtifactReviewDependency, ...],
) -> str:
    """Hash the bounded, content-free artifact/evidence dependency map."""

    payload = [
        {
            "artifact": (
                item.artifact.path,
                item.artifact.sha256,
                item.artifact.occurrence_id,
                item.artifact.retention_hold.value
                if item.artifact.retention_hold is not None
                else None,
            ),
            "binding": item.binding.value,
            "reacquisition_action": item.reacquisition_action.value,
            "evidence_dependencies": [
                (
                    linked.fact_id,
                    linked.criterion_id,
                    linked.criterion_status,
                    linked.evidence.evidence_kind,
                    linked.evidence.locator,
                    linked.evidence.sha256,
                    linked.evidence.outcome.value,
                    linked.attested_occurrence_id,
                )
                for linked in item.evidence_dependencies
            ],
        }
        for item in dependencies
    ]
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SDEReviewPacket:
    """Reviewer packet with a content-free, digest-bound dependency map."""

    detail: SDEReviewDetail
    artifact_inventory: StagingArtifactInventory
    review_artifacts: tuple[ArtifactRef, ...]
    artifact_dependencies: tuple[ArtifactReviewDependency, ...] = ()
    dependency_map_sha256: str = ""

    def __post_init__(self) -> None:
        paths = tuple(item.artifact.path for item in self.artifact_dependencies)
        inventory_paths = tuple(item.path for item in self.artifact_inventory.artifacts)
        if paths != inventory_paths:
            raise ValueError("dependency map must cover the exact ordered inventory")
        if tuple(item.path for item in self.review_artifacts) != inventory_paths:
            raise ValueError("review artifacts must match the exact inventory paths")
        if any(
            (
                current.path,
                current.sha256,
                current.device_id,
                current.inode_id,
                current.occurrence_id,
            )
            != (
                reviewed.path,
                reviewed.sha256,
                reviewed.device_id,
                reviewed.inode_id,
                reviewed.occurrence_id,
            )
            or (
                current.retention_hold is not None
                and reviewed.retention_hold is not current.retention_hold
            )
            for current, reviewed in zip(
                self.artifact_inventory.artifacts, self.review_artifacts
            )
        ):
            raise ValueError("review artifacts must preserve current file identity and holds")
        if tuple(item.artifact for item in self.artifact_dependencies) != self.review_artifacts:
            raise ValueError("dependency map must bind the displayed review artifacts")
        if self.dependency_map_sha256 != artifact_dependency_map_sha256(
            self.artifact_dependencies
        ):
            raise ValueError("dependency map digest does not match its contents")
