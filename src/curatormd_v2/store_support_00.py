"""Shared SQLite store contracts and implementation support."""

from __future__ import annotations

from _thread import RLock as RLockType
from contextlib import AbstractContextManager, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from types import TracebackType
from typing import Generator, NamedTuple, NoReturn, Protocol, Self, cast
import zlib

from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventDisposition,
    EventInboxStatus,
    EventQueueStatus,
)
from .content_safety import validate_safe_text
from .models import (
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    CleanupAuthorizationReceipt,
    ExpiryPurgeReceipt,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    EventClassStorageUsage,
    EventPayloadScrubUsage,
    EventFailureCategory,
    EventFailureCategoryUsage,
    EventReceiptCompactionItem,
    EventReceiptCompactionProposal,
    EventReceiptArchiveReceipt,
    Fact,
    FactArchiveReceipt,
    FactCapacity,
    FactCompactionProposal,
    FactKind,
    GoalCard,
    GoalCriteriaVersion,
    GoalStatus,
    GoalStatusStorageUsage,
    GlobalEventInboxUsage,
    ProjectControlPlaneStorageUsage,
    SQLiteDatabaseFileUsage,
    SQLiteDatabasePageUsage,
    SQLitePhysicalStorageUsage,
    MAX_CRITERIA_REVISIONS,
    MAX_ARTIFACTS_PER_RECEIPT,
    MAX_FACTS_PER_GOAL,
    MAX_FACT_BYTES_PER_GOAL,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
    MAX_FACT_COMPACTION_BATCH_FACTS,
    MAX_FACT_COMPACTION_SOURCE_BYTES,
    MAX_GOAL_LIST_PAGE,
    MAX_EVENT_RECEIPTS_GLOBAL,
    MAX_EVENT_RECEIPT_BYTES_GLOBAL,
    MAX_EVENT_COMPACTION_PAGE,
    MAX_EVENT_ARCHIVE_BATCH,
    EVENT_FAILURE_METADATA_RESERVE_BYTES,
    MAX_SDE_CORRECTIONS_PER_CANDIDATE,
    MAX_SDE_CORRECTIONS_PER_PROJECT,
    MAX_SDE_FEEDBACK_PER_PROJECT,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    MAX_SUCCESS_CRITERIA,
    Materiality,
    PurgeOutcome,
    StorageClassUsage,
    StoragePhysicalClassUsage,
    ProjectStorageUsage,
    ReacquisitionAction,
    ProjectActivitySnapshot,
    ProjectOperationalCounts,
    PurgeFailureCode,
    PurgeTargetRecord,
    PurgeStatus,
    ReviewDecision,
    RetentionHoldKind,
    StagingArtifactInventory,
    SDECandidate,
    SDEStatus,
    SuccessCriterion,
    new_id,
    utc_now,
)


from .record_validation import parse_optional_aware_timestamp
from .reporting import GoalReportContext
from .schema_migrations import (
    SQLITE_SCHEMA_VERSION,
    apply_schema_migrations,
    finish_unversioned_migrations,
)
from .store_requests import (
    ConsumerDrainStoreRequest,
    GoalCriteriaAmendmentRequest,
    GoalRetirementRequest,
    GoalTransitionRequest,
    PurgeTargetResult,
    ProjectDrainEffectContext,
    SuspendedProcessedEventEpochRequest,
    TerminalEventDispositionStoreRequest,
)
from .validation import is_exact_int


_PURGE_APPROVAL_INVALIDATING_ERRORS = frozenset(
    {
        PurgeFailureCode.PATH_CHANGED.value,
        PurgeFailureCode.HASH_MISMATCH.value,
        PurgeFailureCode.ARTIFACT_CHANGED.value,
    }
)

EVENT_RETRY_BASE_SECONDS = 5
EVENT_RETRY_MAX_SECONDS = 900
PURGE_RETRY_BASE_SECONDS = 5
PURGE_RETRY_MAX_SECONDS = 900
_EVENT_INBOX_METADATA_BYTES_SQL = """\
length(CAST(project_id AS BLOB)) +
length(CAST(event_id AS BLOB)) +
length(CAST(event_type AS BLOB)) +
length(CAST(payload_sha256 AS BLOB)) +
COALESCE(length(CAST(idempotency_sha256 AS BLOB)), 0) +
length(CAST(payload_bytes AS TEXT)) +
length(CAST(status AS BLOB)) +
length(CAST(received_at AS BLOB)) +
length(CAST(attempts AS TEXT)) +
length(CAST(source_id AS BLOB)) +
COALESCE(length(CAST(source_sequence AS TEXT)), 0) +
COALESCE(length(CAST(processed_at AS BLOB)), 0) +
COALESCE(length(CAST(last_error AS BLOB)), 0) +
COALESCE(length(CAST(next_attempt_at AS BLOB)), 0) +
COALESCE(length(CAST(lease_owner AS BLOB)), 0) +
COALESCE(length(CAST(lease_expires_at AS BLOB)), 0) +
COALESCE(length(CAST(disposition AS BLOB)), 0) +
COALESCE(length(CAST(archive_id AS BLOB)), 0) +
COALESCE(length(CAST(archived_at AS BLOB)), 0) +
COALESCE(length(CAST(archived_by AS BLOB)), 0) +
COALESCE(length(CAST(archive_inventory_sha256 AS BLOB)), 0) +
COALESCE(length(CAST(archive_offset AS TEXT)), 0) +
COALESCE(length(CAST(archive_reason AS BLOB)), 0)"""
_EVENT_INBOX_USAGE_SQL = (
    "SELECT COUNT(*) AS count, COALESCE(SUM("  # nosec B608
    + _EVENT_INBOX_METADATA_BYTES_SQL
    + " + COALESCE(length(CAST(payload_json AS BLOB)), 0)), 0) "
    "AS bytes FROM event_inbox WHERE archive_id IS NULL"  # nosec B608 - fixed SQL and module constant only.
)
_PROJECT_EVENT_USAGE_SQL = (  # nosec B608 - fixed SQL and module constant only.
    "SELECT event_type, status, COUNT(*) AS count, "  # nosec B608
    "COALESCE(SUM(payload_bytes), 0) AS original_bytes, "
    "COALESCE(SUM(COALESCE(length(CAST(payload_json AS BLOB)), 0)), 0) "
    "AS retained_bytes, COALESCE(SUM("
    + _EVENT_INBOX_METADATA_BYTES_SQL
    + "), 0) AS metadata_bytes FROM event_inbox WHERE project_id = ? "
    "GROUP BY event_type, status ORDER BY event_type, status"
)


class NotFoundError(LookupError):
    """A requested goal, fact, candidate, or receipt does not exist."""


class ConflictError(RuntimeError):
    """A requested transition conflicts with already-recorded state."""


class EventClaimError(ConflictError):
    """A worker no longer owns a live lease for the claimed event."""


class FactCapacityError(ConflictError):
    """A goal or project reached its immutable fact-history ceiling."""


class GoalListCapacityError(ConflictError):
    """An unpaged compatibility listing exceeds its safe result ceiling."""


class FactArchiveIntegrityError(RuntimeError):
    """A compressed fact archive failed its integrity or schema checks."""


class EventInboxCapacityError(ConflictError):
    """The global event-inbox count or retained-byte ceiling was reached."""


class EventOrderError(ConflictError):
    """An event sequence is repeated or arrives with a gap."""


@dataclass(frozen=True, slots=True)
# Pylint: these fields mirror the persisted project-registration record.
class ProjectRegistrationRecord:  # pylint: disable=too-many-instance-attributes
    """Current durable binding between an opaque project and host fingerprints."""

    project_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    status: str
    registered_by: str
    registered_at: str
    updated_by: str
    updated_at: str
    revision: int


class _ProjectRegistrationConfig(Protocol):
    """Structural view of the validated config fields stored in the registry."""

    @property
    def project_id(self) -> str:
        """Return the exact registered project ID."""
        ...

    @property
    def repository_fingerprint(self) -> str:
        """Return the host-computed repository identity digest."""
        ...

    @property
    def config_sha256(self) -> str:
        """Return the digest of the validated consumer configuration."""
        ...

    @property
    def backend_api_version(self) -> int:
        """Return the project's declared backend contract version."""
        ...


def project_registration_binding_fields(
    config: _ProjectRegistrationConfig,
) -> tuple[str, str, str, int]:
    """Return the immutable config fields shared by project binding records."""

    return (
        config.project_id,
        config.repository_fingerprint,
        config.config_sha256,
        config.backend_api_version,
    )


@dataclass(frozen=True, slots=True)
class ProjectRegistrationRequest:
    """Host-verified project binding values to register or update."""

    project_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    rationale: str
    expected_revision: int | None = None

    @classmethod
    def from_project_config(
        cls,
        config: _ProjectRegistrationConfig,
        rationale: str,
        expected_revision: int | None = None,
    ) -> ProjectRegistrationRequest:
        """Build a registry request from one already validated project config."""

        return cls(
            *project_registration_binding_fields(config),
            rationale=rationale,
            expected_revision=expected_revision,
        )


@dataclass(frozen=True, slots=True)
# Pylint: these fields are the explicit project-status transition request.
class ProjectStatusChangeRequest:  # pylint: disable=too-many-instance-attributes
    """One explicit project status transition and its retry identity."""

    project_id: str
    status: str
    rationale: str
    expected_revision: int
    transition_id: str
    review_packet_sha256: str | None = None
    suspension_transition_id: str | None = None
    staging_inventory_sha256: str | None = None
    staging_inventory_count: int | None = None
    staging_inventory_bytes: int | None = None
    staging_inventory_observed_at: str | None = None


@dataclass(frozen=True, slots=True)
# Pylint: this packet preserves the complete reviewer-visible record shape.
class ProjectReactivationReviewPacket:  # pylint: disable=too-many-instance-attributes
    """Fresh, content-free snapshot reviewed before project reactivation."""

    project_id: str
    project_revision: int
    suspension_transition_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    binding_revision: int
    source_epoch: int
    active_grant_count: int
    grant_history_count: int
    grants_sha256: str
    source_cursor_count: int
    source_cursors_sha256: str
    event_count: int
    unresolved_event_count: int
    events_sha256: str
    pending_purge_work_count: int
    purge_inventory_sha256: str
    staging_inventory_sha256: str | None
    staging_inventory_count: int
    staging_inventory_bytes: int
    staging_inventory_observed_at: str
    complete: bool
    packet_sha256: str | None


@dataclass(frozen=True, slots=True)
class ConsumerBindingRecord:
    """Consumer lifecycle state, independent of the project lifecycle."""

    project_id: str
    status: str
    revision: int
    source_epoch: int
    updated_by: str
    updated_at: str


@dataclass(frozen=True, slots=True)
# Pylint: these fields bind one consumer transition to its exact evidence.
class ConsumerBindingTransitionRequest:  # pylint: disable=too-many-instance-attributes
    """One compare-and-set consumer binding transition."""

    project_id: str
    status: str
    rationale: str
    expected_revision: int
    transition_id: str
    expected_source_epoch: int | None = None
    expected_project_revision: int | None = None
    repository_fingerprint: str | None = None
    config_sha256: str | None = None
    backend_api_version: int | None = None


@dataclass(frozen=True, slots=True)
# Pylint: these flat fields match the durable binding-audit schema.
class ConsumerBindingAuditRecord:  # pylint: disable=too-many-instance-attributes
    """Immutable receipt for a consumer binding lifecycle transition."""

    audit_id: str
    project_id: str
    actor_id: str
    action: str
    from_status: str | None
    to_status: str
    source_epoch: int
    revision: int
    transition_id: str
    rationale: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ConsumerBindingTransitionResult:
    """Current binding state and durable receipt returned from a transition."""

    binding: ConsumerBindingRecord
    receipt: ConsumerBindingAuditRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class ProjectRetirementRecord:
    """Irreversible project tombstone; it does not authorize data deletion."""

    project_id: str
    transition_id: str
    retired_by: str
    retired_revision: int
    source_epoch: int
    rationale: str
    retired_at: str


@dataclass(frozen=True, slots=True)
# Pylint: these fields mirror the durable terminal-event receipt schema.
class TerminalEventDispositionRecord:  # pylint: disable=too-many-instance-attributes
    """Human-authorized terminal disposition for one exact failed event."""

    project_id: str
    event_id: str
    transition_id: str
    actor_id: str
    prior_status: EventInboxStatus
    payload_sha256: str
    rationale: str
    created_at: str


@dataclass(frozen=True, slots=True)
class TerminalEventCandidate:
    """Content-free inventory row for an unresolved source event."""

    event_id: str
    status: EventInboxStatus
    payload_sha256: str
    source_id: str
    source_sequence: int | None


@dataclass(frozen=True, slots=True)
class TerminalEventInventory:
    """Bounded exact candidate page with an explicit completeness marker."""

    count_after_cursor: int
    events: tuple[TerminalEventCandidate, ...]
    complete: bool
    next_after_event_id: str | None


@dataclass(frozen=True, slots=True)
# Pylint: the snapshot keeps its bounded persisted status counters explicit.
class ProjectLifecycleStatusSnapshot:  # pylint: disable=too-many-instance-attributes
    """One read-transaction view of project, binding, and event lifecycle state."""

    project_id: str
    observed_at: str
    complete: bool
    incomplete_reasons: tuple[str, ...]
    project_status: str
    project_revision: int
    consumer_binding: ConsumerBindingRecord
    retirement: ProjectRetirementRecord | None
    event_status_counts: tuple[tuple[str, int], ...]
    unprocessed_event_count: int
    unprocessed_event_sha256: str
    active_event_lease_count: int
    terminal_event_inventory: TerminalEventInventory


@dataclass(frozen=True, slots=True)
# Pylint: the audit row mirrors the stored project-registry fields.
class ProjectRegistryAuditRecord:  # pylint: disable=too-many-instance-attributes
    """Append-only evidence of a project registration or lifecycle change."""

    audit_id: str
    project_id: str
    actor_id: str
    action: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    rationale: str
    created_at: str
    revision: int
    transition_id: str | None
    review_packet_sha256: str | None = None
    review_packet_json: str | None = None
    suspension_transition_id: str | None = None


def _project_registration_update_retry_matches(
    row: sqlite3.Row,
    request: ProjectRegistrationRequest,
    actor_id: str,
    expected_revision: int,
) -> bool:
    """Match an idempotent update retry against its durable audit row."""

    return (
        row["action"],
        row["actor_id"],
        row["revision"],
        row["repository_fingerprint"],
        row["config_sha256"],
        row["backend_api_version"],
        row["rationale"],
    ) == (
        "updated",
        actor_id,
        expected_revision + 1,
        request.repository_fingerprint,
        request.config_sha256,
        request.backend_api_version,
        request.rationale,
    )


def _project_registration_is_unchanged(
    row: sqlite3.Row,
    request: ProjectRegistrationRequest,
) -> bool:
    """Compare all mutable consumer registration fingerprints."""

    return (
        row["repository_fingerprint"],
        row["config_sha256"],
        row["backend_api_version"],
    ) == (
        request.repository_fingerprint,
        request.config_sha256,
        request.backend_api_version,
    )


@dataclass(frozen=True, slots=True)
class ProjectRegistrationTransitionResult:
    """Current registration plus the immutable receipt for one admin change."""

    registration: ProjectRegistrationRecord
    receipt: ProjectRegistryAuditRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
# Pylint: the grant view mirrors the complete durable authorization row.
class ProjectGrantRecord:  # pylint: disable=too-many-instance-attributes
    """An exact project/action grant and optional immutable revocation event."""

    grant_id: str
    project_id: str
    subject_id: str
    action: str
    granted_by: str
    rationale: str
    granted_at: str
    revoked_by: str | None = None
    revoke_rationale: str | None = None
    revoked_at: str | None = None

    @property
    def active(self) -> bool:
        """Whether this grant has no recorded revocation."""

        return self.revoked_at is None


@dataclass(frozen=True, slots=True)
class _FactStoragePayload:
    """Serialized evidence fields and dedupe identity for one fact write."""

    evidence_json: str
    attestations_json: str
    dedupe_key: str


_ACCESS_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REACTIVATION_STAGING_MAX_AGE_SECONDS = 60


_ACCESS_RATIONALE_LIMIT = 1000
_PROJECT_ACCESS_ACTIONS = frozenset(
    {"read", "write", "review", "purge_retry", "retention_hold_release", "event_retry"}
)


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_unique_amended_criteria_ids(
    criteria: tuple[SuccessCriterion, ...],
) -> None:
    """Reject repeated criterion IDs before checking later amendment fields."""

    criterion_ids = tuple(item.criterion_id for item in criteria)
    if len(criterion_ids) != len(set(criterion_ids)):
        raise ValueError("amended criterion IDs must be unique")


_ERROR_CODE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")


def _evidence_to_dict(evidence: EvidenceRef) -> dict[str, str]:
    value = {
        "evidence_kind": evidence.evidence_kind,
        "locator": evidence.locator,
        "sha256": evidence.sha256,
        "outcome": evidence.outcome.value,
    }
    if evidence.occurrence_id is not None:
        value["occurrence_id"] = evidence.occurrence_id
    return value


def _attestation_to_dict(attestation: EvidenceAttestation) -> dict[str, str]:
    """Serialize only the bounded provenance fields retained by the contract."""

    value = {
        "evidence_kind": attestation.evidence_kind,
        "evidence_sha256": attestation.evidence_sha256,
        "project_id": attestation.project_id,
        "goal_id": attestation.goal_id,
        "criterion_id": attestation.criterion_id,
        "adapter_id": attestation.adapter_id,
        "authenticated_subject": attestation.authenticated_subject,
        "source_revision": attestation.source_revision,
        "observed_at": attestation.observed_at,
        "verified_at": attestation.verified_at,
        "valid_until": attestation.valid_until,
        "revocation_checked_at": attestation.revocation_checked_at,
    }
    if attestation.occurrence_id is not None:
        value["occurrence_id"] = attestation.occurrence_id
    return value


def _validate_retirement_request(
    goal_id: str,
    status: GoalStatus,
    reason: str,
    fact: Fact,
    replacement_goal_id: str | None,
) -> None:
    """Validate the immutable inputs for a cancellation or supersession."""

    if status not in {GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}:
        raise ValueError("retirement status must be cancelled or superseded")
    if not reason.strip() or len(reason) > 500 or "\n" in reason or "\r" in reason:
        raise ValueError("retirement requires a single-line reason of at most 500 characters")
    expected_kind = (
        FactKind.CANCELLED if status is GoalStatus.CANCELLED else FactKind.SUPERSEDED
    )
    if fact.goal_id != goal_id or fact.kind is not expected_kind:
        raise ConflictError("retirement transition requires its matching system fact")
    if (status is GoalStatus.SUPERSEDED) != (replacement_goal_id is not None):
        raise ValueError("only supersession has a replacement goal")
    if replacement_goal_id == goal_id:
        raise ValueError("a goal cannot supersede itself")


def _validate_replacement_goal(
    connection: sqlite3.Connection,
    goal_id: str,
    project_id: str,
    replacement_goal_id: str | None,
) -> None:
    """Require a same-project active replacement outside the retired subtree."""

    if replacement_goal_id is None:
        return
    replacement = connection.execute(
        "SELECT project_id, status, parent_goal_id FROM goals WHERE goal_id = ?",
        (replacement_goal_id,),
    ).fetchone()
    if replacement is None or replacement["project_id"] != project_id:
        raise ConflictError("replacement goal must exist in the same project")
    if GoalStatus(replacement["status"]) is not GoalStatus.ACTIVE:
        raise ConflictError("replacement goal must be active")
    ancestor_id = replacement["parent_goal_id"]
    while ancestor_id is not None:
        if ancestor_id == goal_id:
            raise ConflictError("a goal cannot be superseded by its descendant")
        ancestor = connection.execute(
            "SELECT parent_goal_id FROM goals WHERE goal_id = ? AND project_id = ?",
            (ancestor_id, project_id),
        ).fetchone()
        if ancestor is None:
            raise ConflictError("replacement goal has a broken parent chain")
        ancestor_id = ancestor["parent_goal_id"]


def _validate_retirement_relationships(
    connection: sqlite3.Connection, goal_id: str, project_id: str
) -> None:
    """Reject retirement while this goal has unresolved children or dependents."""

    active_children = connection.execute(
        "SELECT goal_id FROM goals WHERE parent_goal_id = ? AND status NOT IN (?, ?, ?)",
        (
            goal_id,
            GoalStatus.COMPLETE.value,
            GoalStatus.CANCELLED.value,
            GoalStatus.SUPERSEDED.value,
        ),
    ).fetchall()
    if active_children:
        raise ConflictError(
            "resolve child goals before cancelling or superseding their parent: "
            + ", ".join(child["goal_id"] for child in active_children)
        )
    dependent_rows = connection.execute(
        "SELECT goal_id, depends_on_json, status FROM goals "
        "WHERE project_id = ? AND goal_id != ?",
        (project_id, goal_id),
    ).fetchall()
    active_dependents = tuple(
        dependent["goal_id"]
        for dependent in dependent_rows
        if GoalStatus(dependent["status"])
        not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
        and goal_id in json.loads(dependent["depends_on_json"])
    )
    if active_dependents:
        raise ConflictError(
            "resolve dependent goals before retiring this dependency: "
            + ", ".join(active_dependents)
        )


def _validate_reopen_parent(
    connection: sqlite3.Connection, parent_goal_id: str | None, project_id: str
) -> None:
    """Require a reopened goal's parent to remain in an open lifecycle state."""

    if parent_goal_id is None:
        return
    parent = connection.execute(
        "SELECT status FROM goals WHERE goal_id = ? AND project_id = ?",
        (parent_goal_id, project_id),
    ).fetchone()
    if parent is None:
        raise ConflictError("goal parent is missing from its project")
    if GoalStatus(parent["status"]) in {
        GoalStatus.COMPLETE,
        GoalStatus.CANCELLED,
        GoalStatus.SUPERSEDED,
    }:
        raise ConflictError("reopen or replace the terminal parent first")


def _validate_reopen_dependencies(
    connection: sqlite3.Connection, goal_id: str, project_id: str
) -> None:
    """Require every dependency to exist and not be cancelled or superseded."""

    goal_row = connection.execute(
        "SELECT depends_on_json FROM goals WHERE goal_id = ?", (goal_id,)
    ).fetchone()
    for dependency_id in json.loads(goal_row["depends_on_json"]):
        dependency = connection.execute(
            "SELECT status FROM goals WHERE goal_id = ? AND project_id = ?",
            (dependency_id, project_id),
        ).fetchone()
        if dependency is None:
            raise ConflictError("goal dependency is missing from its project")
        if GoalStatus(dependency["status"]) in {
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        }:
            raise ConflictError(
                "replace the cancelled or superseded dependency before reopening"
            )


def _validate_reopen_dependents(
    connection: sqlite3.Connection, goal_id: str, project_id: str
) -> None:
    """Keep completed goals from depending on a goal that is reopened."""

    completed_goals = connection.execute(
        "SELECT goal_id, depends_on_json FROM goals "
        "WHERE project_id = ? AND status = ? AND goal_id != ?",
        (project_id, GoalStatus.COMPLETE.value, goal_id),
    ).fetchall()
    completed_dependents = tuple(
        item["goal_id"]
        for item in completed_goals
        if goal_id in json.loads(item["depends_on_json"])
    )
    if completed_dependents:
        raise ConflictError(
            "reopen completed dependent goals first: "
            + ", ".join(completed_dependents)
        )


def _validate_reopen_relationships(
    connection: sqlite3.Connection, goal_id: str, row: sqlite3.Row
) -> None:
    """Validate parent, dependency, and completed-dependent constraints."""

    project_id = row["project_id"]
    _validate_reopen_parent(connection, row["parent_goal_id"], project_id)
    _validate_reopen_dependencies(connection, goal_id, project_id)
    _validate_reopen_dependents(connection, goal_id, project_id)

__all__ = [
    'RLockType',
    'AbstractContextManager',
    'contextmanager',
    'asdict',
    'dataclass',
    'UTC',
    'datetime',
    'timedelta',
    'hashlib',
    'json',
    'os',
    'Path',
    're',
    'sqlite3',
    'stat',
    'RLock',
    'TracebackType',
    'Generator',
    'NamedTuple',
    'NoReturn',
    'Protocol',
    'Self',
    'cast',
    'zlib',
    'EventEnvelope',
    'EventInboxReceipt',
    'EventDisposition',
    'EventInboxStatus',
    'EventQueueStatus',
    'validate_safe_text',
    'ArtifactRef',
    'ArtifactStatus',
    'AuditReceipt',
    'CleanupAuthorizationReceipt',
    'ExpiryPurgeReceipt',
    'EvidenceAttestation',
    'EvidenceOutcome',
    'EvidenceRef',
    'EventClassStorageUsage',
    'EventPayloadScrubUsage',
    'EventFailureCategory',
    'EventFailureCategoryUsage',
    'EventReceiptCompactionItem',
    'EventReceiptCompactionProposal',
    'EventReceiptArchiveReceipt',
    'Fact',
    'FactArchiveReceipt',
    'FactCapacity',
    'FactCompactionProposal',
    'FactKind',
    'GoalCard',
    'GoalCriteriaVersion',
    'GoalStatus',
    'GoalStatusStorageUsage',
    'GlobalEventInboxUsage',
    'ProjectControlPlaneStorageUsage',
    'SQLiteDatabaseFileUsage',
    'SQLiteDatabasePageUsage',
    'SQLitePhysicalStorageUsage',
    'MAX_CRITERIA_REVISIONS',
    'MAX_ARTIFACTS_PER_RECEIPT',
    'MAX_FACTS_PER_GOAL',
    'MAX_FACT_BYTES_PER_GOAL',
    'MAX_FACTS_PER_PROJECT',
    'MAX_FACT_BYTES_PER_PROJECT',
    'MAX_FACT_ARCHIVE_BYTES_PER_PROJECT',
    'MAX_FACT_COMPACTION_BATCH_FACTS',
    'MAX_FACT_COMPACTION_SOURCE_BYTES',
    'MAX_GOAL_LIST_PAGE',
    'MAX_EVENT_RECEIPTS_GLOBAL',
    'MAX_EVENT_RECEIPT_BYTES_GLOBAL',
    'MAX_EVENT_COMPACTION_PAGE',
    'MAX_EVENT_ARCHIVE_BATCH',
    'EVENT_FAILURE_METADATA_RESERVE_BYTES',
    'MAX_SDE_CORRECTIONS_PER_CANDIDATE',
    'MAX_SDE_CORRECTIONS_PER_PROJECT',
    'MAX_SDE_FEEDBACK_PER_PROJECT',
    'SDECorrection',
    'SDEQualityFeedback',
    'SDEQualityFeedbackLabel',
    'SDEQualityFeedbackSummary',
    'MAX_SUCCESS_CRITERIA',
    'Materiality',
    'PurgeOutcome',
    'StorageClassUsage',
    'StoragePhysicalClassUsage',
    'ProjectStorageUsage',
    'ReacquisitionAction',
    'ProjectActivitySnapshot',
    'ProjectOperationalCounts',
    'PurgeFailureCode',
    'PurgeTargetRecord',
    'PurgeStatus',
    'ReviewDecision',
    'RetentionHoldKind',
    'StagingArtifactInventory',
    'SDECandidate',
    'SDEStatus',
    'SuccessCriterion',
    'new_id',
    'utc_now',
    'parse_optional_aware_timestamp',
    'GoalReportContext',
    'SQLITE_SCHEMA_VERSION',
    'apply_schema_migrations',
    'finish_unversioned_migrations',
    'ConsumerDrainStoreRequest',
    'GoalCriteriaAmendmentRequest',
    'GoalRetirementRequest',
    'GoalTransitionRequest',
    'PurgeTargetResult',
    'ProjectDrainEffectContext',
    'SuspendedProcessedEventEpochRequest',
    'TerminalEventDispositionStoreRequest',
    'is_exact_int',
    '_PURGE_APPROVAL_INVALIDATING_ERRORS',
    'EVENT_RETRY_BASE_SECONDS',
    'EVENT_RETRY_MAX_SECONDS',
    'PURGE_RETRY_BASE_SECONDS',
    'PURGE_RETRY_MAX_SECONDS',
    '_EVENT_INBOX_METADATA_BYTES_SQL',
    '_EVENT_INBOX_USAGE_SQL',
    '_PROJECT_EVENT_USAGE_SQL',
    'NotFoundError',
    'ConflictError',
    'EventClaimError',
    'FactCapacityError',
    'GoalListCapacityError',
    'FactArchiveIntegrityError',
    'EventInboxCapacityError',
    'EventOrderError',
    'ProjectRegistrationRecord',
    '_ProjectRegistrationConfig',
    'project_registration_binding_fields',
    'ProjectRegistrationRequest',
    'ProjectStatusChangeRequest',
    'ProjectReactivationReviewPacket',
    'ConsumerBindingRecord',
    'ConsumerBindingTransitionRequest',
    'ConsumerBindingAuditRecord',
    'ConsumerBindingTransitionResult',
    'ProjectRetirementRecord',
    'TerminalEventDispositionRecord',
    'TerminalEventCandidate',
    'TerminalEventInventory',
    'ProjectLifecycleStatusSnapshot',
    'ProjectRegistryAuditRecord',
    '_project_registration_update_retry_matches',
    '_project_registration_is_unchanged',
    'ProjectRegistrationTransitionResult',
    'ProjectGrantRecord',
    '_FactStoragePayload',
    '_ACCESS_ID_RE',
    '_SHA256_RE',
    '_REACTIVATION_STAGING_MAX_AGE_SECONDS',
    '_ACCESS_RATIONALE_LIMIT',
    '_PROJECT_ACCESS_ACTIONS',
    '_json_dump',
    '_validate_unique_amended_criteria_ids',
    '_ERROR_CODE_RE',
    '_evidence_to_dict',
    '_attestation_to_dict',
    '_validate_retirement_request',
    '_validate_replacement_goal',
    '_validate_retirement_relationships',
    '_validate_reopen_parent',
    '_validate_reopen_dependencies',
    '_validate_reopen_dependents',
    '_validate_reopen_relationships',
]
