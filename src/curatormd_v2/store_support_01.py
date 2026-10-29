"""Shared SQLite store contracts and implementation support."""

# pyright: reportUnusedImport=false, reportUnsupportedDunderAll=false

from __future__ import annotations

# Re-export the prior store support names for the ordered helpers.
from .store_support_00 import (
    RLockType,
    AbstractContextManager,
    contextmanager,
    asdict,
    dataclass,
    UTC,
    datetime,
    timedelta,
    hashlib,
    json,
    os,
    Path,
    re,
    sqlite3,
    stat,
    RLock,
    TracebackType,
    Generator,
    NamedTuple,
    NoReturn,
    Protocol,
    Self,
    cast,
    zlib,
    EventEnvelope,
    EventInboxReceipt,
    EventDisposition,
    EventInboxStatus,
    EventQueueStatus,
    validate_safe_text,
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
    parse_optional_aware_timestamp,
    GoalReportContext,
    SQLITE_SCHEMA_VERSION,
    apply_schema_migrations,
    finish_unversioned_migrations,
    ConsumerDrainStoreRequest,
    GoalCriteriaAmendmentRequest,
    GoalRetirementRequest,
    GoalTransitionRequest,
    PurgeTargetResult,
    ProjectDrainEffectContext,
    SuspendedProcessedEventEpochRequest,
    TerminalEventDispositionStoreRequest,
    is_exact_int,
    _PURGE_APPROVAL_INVALIDATING_ERRORS,
    EVENT_RETRY_BASE_SECONDS,
    EVENT_RETRY_MAX_SECONDS,
    PURGE_RETRY_BASE_SECONDS,
    PURGE_RETRY_MAX_SECONDS,
    _EVENT_INBOX_METADATA_BYTES_SQL,
    _EVENT_INBOX_USAGE_SQL,
    _PROJECT_EVENT_USAGE_SQL,
    NotFoundError,
    ConflictError,
    EventClaimError,
    FactCapacityError,
    GoalListCapacityError,
    FactArchiveIntegrityError,
    EventInboxCapacityError,
    EventOrderError,
    ProjectRegistrationRecord,
    _ProjectRegistrationConfig,
    project_registration_binding_fields,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    ProjectReactivationReviewPacket,
    ConsumerBindingRecord,
    ConsumerBindingTransitionRequest,
    ConsumerBindingAuditRecord,
    ConsumerBindingTransitionResult,
    ProjectRetirementRecord,
    TerminalEventDispositionRecord,
    TerminalEventCandidate,
    TerminalEventInventory,
    ProjectLifecycleStatusSnapshot,
    ProjectRegistryAuditRecord,
    _project_registration_update_retry_matches,
    _project_registration_is_unchanged,
    ProjectRegistrationTransitionResult,
    ProjectGrantRecord,
    _FactStoragePayload,
    _ACCESS_ID_RE,
    _SHA256_RE,
    _REACTIVATION_STAGING_MAX_AGE_SECONDS,
    _ACCESS_RATIONALE_LIMIT,
    _PROJECT_ACCESS_ACTIONS,
    _json_dump,
    _validate_unique_amended_criteria_ids,
    _ERROR_CODE_RE,
    _evidence_to_dict,
    _attestation_to_dict,
    _validate_retirement_request,
    _validate_replacement_goal,
    _validate_retirement_relationships,
    _validate_reopen_parent,
    _validate_reopen_dependencies,
    _validate_reopen_dependents,
    _validate_reopen_relationships,
)
from .store_support_00 import __all__ as _STORE_SUPPORT_EXPORTS



def _requested_artifact_manifest(
    artifacts: tuple[ArtifactRef, ...],
) -> tuple[tuple[str, str, str | None, int | None, int | None, str | None, str], ...]:
    """Return a stable manifest key and reject duplicate artifact paths."""

    paths = [artifact.path for artifact in artifacts]
    if len(paths) != len(set(paths)):
        raise ConflictError("artifact inventory contains duplicate paths")
    return tuple(
        sorted(
            (
                artifact.path,
                artifact.sha256,
                artifact.retention_hold.value if artifact.retention_hold else None,
                artifact.device_id,
                artifact.inode_id,
                artifact.occurrence_id,
                artifact.reacquisition_action.value,
            )
            for artifact in artifacts
        )
    )


def _stored_artifact_manifest(
    targets: list[sqlite3.Row],
) -> tuple[tuple[str, str, str | None, int | None, int | None, str | None, str], ...]:
    """Return the persisted target key in the same order as a requested manifest."""

    return tuple(
        (
            target["path"], target["sha256"], target["retention_hold"],
            target["device_id"], target["inode_id"],
            target["occurrence_id"],
            target["reacquisition_action"],
        )
        for target in targets
    )


def _insert_purge_targets_from_inventory(
    connection: sqlite3.Connection,
    receipt_id: str,
    artifacts: tuple[ArtifactRef, ...],
    existing_targets: list[sqlite3.Row],
    hold_created_by: str | None,
) -> None:
    """Insert an exact complete inventory while carrying forward matching hold audit."""

    hold_audit = {
        (target["path"], target["sha256"], target["retention_hold"]): (
            target["hold_created_at"],
            target["hold_created_by"],
        )
        for target in existing_targets
        if target["retention_hold"] is not None
    }
    inventory_created_at = utc_now()
    for artifact in artifacts:
        hold_kind = artifact.retention_hold.value if artifact.retention_hold else None
        previous_hold = hold_audit.get(
            (artifact.path, artifact.sha256, hold_kind)
        )
        hold_created_at = (
            previous_hold[0]
            if previous_hold is not None
            else inventory_created_at if hold_kind else None
        )
        hold_actor = (
            previous_hold[1]
            if previous_hold is not None
            else hold_created_by if hold_kind else None
        )
        connection.execute(
            """INSERT INTO purge_targets
               (receipt_id, path, sha256, status, attempts, error,
                created_at, last_attempt_at, next_attempt_at, retention_hold,
                hold_created_at, hold_created_by, device_id, inode_id, occurrence_id,
                approval_stale, reacquisition_action, outcome)
               VALUES (?, ?, ?, ?, 0, NULL, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                receipt_id,
                artifact.path,
                artifact.sha256,
                (
                    ArtifactStatus.HELD
                    if artifact.retention_hold
                    else ArtifactStatus.PENDING
                ).value,
                inventory_created_at,
                hold_kind,
                hold_created_at,
                hold_actor,
                artifact.device_id,
                artifact.inode_id,
                artifact.occurrence_id,
                int(artifact.occurrence_id is None),
                artifact.reacquisition_action.value,
                PurgeOutcome.HELD.value if artifact.retention_hold else None,
            ),
        )


@dataclass(frozen=True, slots=True)
class FactCompactionApprovalRequest:
    """Exact reviewer-approved compaction values passed into the store."""

    compaction_id: str
    goal_id: str
    project_id: str
    fact_ids: tuple[str, ...]
    source_sha256: str
    reviewer_id: str
    approval_reason: str


@dataclass(frozen=True, slots=True)
class _PreparedFactArchive:
    """Validated live facts and their canonical compressed archive payload."""

    facts: tuple[Fact, ...]
    source: bytes
    compressed: bytes
    archive_sha256: str
    created_at: str


@dataclass(frozen=True, slots=True)
# Pylint: these row groups retain the named columns used by storage accounting.
class _ProjectRecordUsageRows:  # pylint: disable=too-many-instance-attributes
    """Aggregates for a project's non-event ledger records."""

    goals: sqlite3.Row
    goal_statuses: list[sqlite3.Row]
    facts: sqlite3.Row
    archives: sqlite3.Row
    candidates: sqlite3.Row
    corrections: sqlite3.Row
    feedback: sqlite3.Row
    receipts: sqlite3.Row
    artifacts: sqlite3.Row
    auxiliary: _ProjectAuxiliaryUsageRows


@dataclass(frozen=True, slots=True)
class _ProjectAuxiliaryUsageRows:
    """Aggregates for project cursors and maintenance receipts."""

    event_cursors: sqlite3.Row
    staging_artifact_times: sqlite3.Row
    staging_artifact_occurrences: sqlite3.Row
    expiry_purge_receipts: sqlite3.Row
    expiry_purge_targets: sqlite3.Row
    cleanup_authorizations: sqlite3.Row


@dataclass(frozen=True, slots=True)
class _ProjectEventUsageRows:
    """Event aggregates and global inbox capacity captured with the ledger read."""

    event_classes: list[sqlite3.Row]
    failures: list[sqlite3.Row]
    retry_audits: sqlite3.Row
    payload_scrubs: sqlite3.Row
    global_capacity: GlobalEventInboxUsage


@dataclass(frozen=True, slots=True)
# Pylint: these counters are the named result of one bounded SQL aggregation.
class _ProjectEventUsageSummary:  # pylint: disable=too-many-instance-attributes
    """Content-free event counts and payload/metadata byte totals."""

    event_classes: tuple[EventClassStorageUsage, ...]
    failures: tuple[EventFailureCategoryUsage, ...]
    event_count: int
    original_bytes: int
    retained_bytes: int
    metadata_bytes: int
    retry_audit_count: int
    retry_audit_bytes: int
    payload_scrub_count: int
    payload_scrub_bytes: int


@dataclass(frozen=True, slots=True)
class _StagingInventorySummary:
    """Exact content-free staging fields used for reactivation review."""

    sha256: str | None
    file_count: int | None
    observed_bytes: int | None
    observed_at: str | None


class _ProjectReactivationInventory(NamedTuple):
    """Content-free ledger inventory digests bound into a reactivation review."""

    grant_history_count: int
    grants_sha256: str
    cursor_count: int
    cursors_sha256: str
    event_count: int
    events_sha256: str
    unresolved_count: int
    pending_purge_count: int
    purge_digest: str
    active_grant_count: int


class _ProjectLifecycleEventSummary(NamedTuple):
    """Compact event status fields read for one lifecycle snapshot."""

    status_counts: tuple[tuple[str, int], ...]
    unprocessed_count: int
    unprocessed_sha256: str
    active_lease_count: int


@dataclass(frozen=True, slots=True)
class _ConsumerBindingTransitionPlan:
    """Validated values for one transactional consumer-binding transition."""

    action: str
    expected_from: str
    next_source_epoch: int
    now: str


def _summarize_project_event_usage(
    rows: _ProjectEventUsageRows,
) -> _ProjectEventUsageSummary:
    """Build typed content-free event usage values from grouped SQLite rows."""

    event_classes = tuple(
        EventClassStorageUsage(
            event_type=row["event_type"],
            status=row["status"],
            count=row["count"],
            original_payload_bytes=row["original_bytes"],
            retained_payload_bytes=row["retained_bytes"],
        )
        for row in rows.event_classes
    )
    failure_counts = {
        EventFailureCategory(row["category"]): int(row["count"])
        for row in rows.failures
    }
    failures = tuple(
        EventFailureCategoryUsage(category, failure_counts.get(category, 0))
        for category in EventFailureCategory
    )
    return _ProjectEventUsageSummary(
        event_classes=event_classes,
        failures=failures,
        event_count=sum(item.count for item in event_classes),
        original_bytes=sum(item.original_payload_bytes for item in event_classes),
        retained_bytes=sum(item.retained_payload_bytes for item in event_classes),
        metadata_bytes=sum(row["metadata_bytes"] for row in rows.event_classes),
        retry_audit_count=int(rows.retry_audits["count"]),
        retry_audit_bytes=int(rows.retry_audits["bytes"]),
        payload_scrub_count=int(rows.payload_scrubs["count"]),
        payload_scrub_bytes=int(rows.payload_scrubs["bytes"]),
    )


def _upgrade_unversioned_goal_schema(connection: sqlite3.Connection) -> None:
    """Repair legacy goal and archive columns before ordered v2 migrations."""

    archive_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(fact_archives)").fetchall()
    }
    if "schema_version" not in archive_columns:
        connection.execute(
            "ALTER TABLE fact_archives ADD COLUMN schema_version "
            "INTEGER NOT NULL DEFAULT 1"
        )
    goal_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(goals)").fetchall()
    }
    if "project_id" not in goal_columns:
        connection.execute(
            "ALTER TABLE goals ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'"
        )
    if "checklist_version" not in goal_columns:
        connection.execute("ALTER TABLE goals ADD COLUMN checklist_version TEXT")
    if "checklist_source_text" not in goal_columns:
        connection.execute("ALTER TABLE goals ADD COLUMN checklist_source_text TEXT")
    if "parent_goal_id" not in goal_columns:
        connection.execute("ALTER TABLE goals ADD COLUMN parent_goal_id TEXT")
    if "depends_on_json" not in goal_columns:
        connection.execute(
            "ALTER TABLE goals ADD COLUMN depends_on_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "criteria_revision" not in goal_columns:
        connection.execute(
            "ALTER TABLE goals ADD COLUMN criteria_revision INTEGER NOT NULL DEFAULT 1"
        )
    if "superseded_by_goal_id" not in goal_columns:
        connection.execute(
            "ALTER TABLE goals ADD COLUMN superseded_by_goal_id TEXT"
        )
    if "lifecycle_revision" not in goal_columns:
        connection.execute(
            "ALTER TABLE goals ADD COLUMN lifecycle_revision INTEGER NOT NULL DEFAULT 1"
        )
        connection.execute("UPDATE goals SET lifecycle_revision = 2")
    connection.execute(
        "INSERT OR IGNORE INTO goal_criteria_versions "
        "(goal_id, revision, criteria_json, reason, created_at) "
        "SELECT goal_id, criteria_revision, criteria_json, 'Initial criteria', created_at "
        "FROM goals"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS goals_parent "
        "ON goals(parent_goal_id, project_id, created_at, goal_id)"
    )


def _upgrade_unversioned_receipt_schema(connection: sqlite3.Connection) -> None:
    """Repair legacy receipt fields and conservatively queue unfinished purges."""

    receipt_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(audit_receipts)").fetchall()
    }
    receipt_migrations = (
        ("reviewer_id", "TEXT"),
        ("review_rationale", "TEXT"),
        ("canonical_persisted", "INTEGER NOT NULL DEFAULT 0"),
        ("canonical_target", "TEXT"),
        ("canonical_sha256", "TEXT"),
        ("canonical_persisted_at", "TEXT"),
    )
    receipt_schema_upgraded = any(
        column not in receipt_columns for column, _declaration in receipt_migrations
    )
    for column, declaration in receipt_migrations:
        if column not in receipt_columns:
            connection.execute(
                f"ALTER TABLE audit_receipts ADD COLUMN {column} {declaration}"
            )
    if receipt_schema_upgraded:
        connection.execute(
            "UPDATE audit_receipts SET purge_status = ? "
            "WHERE canonical_persisted = 0",
            (PurgeStatus.PURGE_PENDING.value,),
        )


def _upgrade_unversioned_event_schema(connection: sqlite3.Connection) -> None:
    """Repair legacy inbox metadata before recording its v1 schema stamp."""

    event_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    if "event_type" not in event_columns:
        connection.execute(
            "ALTER TABLE event_inbox ADD COLUMN event_type TEXT "
            "NOT NULL DEFAULT 'legacy.unknown'"
        )
    if "payload_bytes" not in event_columns:
        connection.execute(
            "ALTER TABLE event_inbox ADD COLUMN payload_bytes INTEGER "
            "NOT NULL DEFAULT 0"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS event_inbox_usage "
        "ON event_inbox(project_id, event_type, status)"
    )


def _initialize_unversioned_schema(
    connection: sqlite3.Connection, schema: str
) -> None:
    """Apply the atomic legacy bootstrap and ordered v2+ migration sequence."""

    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    _upgrade_unversioned_goal_schema(connection)
    _upgrade_unversioned_receipt_schema(connection)
    _upgrade_unversioned_event_schema(connection)
    connection.execute("PRAGMA user_version = 1")
    finish_unversioned_migrations(connection)

__all__ = [*_STORE_SUPPORT_EXPORTS,
    '_requested_artifact_manifest',
    '_stored_artifact_manifest',
    '_insert_purge_targets_from_inventory',
    'FactCompactionApprovalRequest',
    '_PreparedFactArchive',
    '_ProjectRecordUsageRows',
    '_ProjectAuxiliaryUsageRows',
    '_ProjectEventUsageRows',
    '_ProjectEventUsageSummary',
    '_StagingInventorySummary',
    '_ProjectReactivationInventory',
    '_ProjectLifecycleEventSummary',
    '_ConsumerBindingTransitionPlan',
    '_summarize_project_event_usage',
    '_upgrade_unversioned_goal_schema',
    '_upgrade_unversioned_receipt_schema',
    '_upgrade_unversioned_event_schema',
    '_initialize_unversioned_schema',
]
