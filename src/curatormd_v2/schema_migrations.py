"""Sequential, transactional SQLite schema migrations for Curator V2."""

from __future__ import annotations

from collections.abc import Callable
import sqlite3

from .events import EventEnvelope

SQLITE_SCHEMA_VERSION = 22


def migrate_event_router_v2(connection: sqlite3.Connection) -> None:
    """Add durable event attempts, source ordering, and operator retry audit."""

    event_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    for column, declaration in (
        ("attempts", "INTEGER NOT NULL DEFAULT 0"),
        ("source_id", "TEXT NOT NULL DEFAULT 'unspecified'"),
        ("source_sequence", "INTEGER"),
    ):
        if column not in event_columns:
            connection.execute(
                f"ALTER TABLE event_inbox ADD COLUMN {column} {declaration}"
            )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS event_retry_audit (
               retry_id INTEGER PRIMARY KEY,
               project_id TEXT NOT NULL,
               event_id TEXT NOT NULL,
               actor_id TEXT NOT NULL,
               created_at TEXT NOT NULL,
               FOREIGN KEY(project_id, event_id)
                   REFERENCES event_inbox(project_id, event_id)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS event_retry_audit_event "
        "ON event_retry_audit(project_id, event_id, retry_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS event_inbox_source_order "
        "ON event_inbox(project_id, source_id, source_sequence, status)"
    )
    connection.execute("PRAGMA user_version = 2")


def migrate_purge_observability_v3(connection: sqlite3.Connection) -> None:
    """Add artifact queue timestamps for age reporting and operator recovery."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(purge_targets)").fetchall()
    }
    if "created_at" not in columns:
        connection.execute(
            "ALTER TABLE purge_targets ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
        )
    if "last_attempt_at" not in columns:
        connection.execute("ALTER TABLE purge_targets ADD COLUMN last_attempt_at TEXT")
    connection.execute(
        """UPDATE purge_targets SET created_at = COALESCE(
               (SELECT created_at FROM audit_receipts
                WHERE audit_receipts.receipt_id = purge_targets.receipt_id), ''
           ) WHERE created_at = ''"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS purge_targets_queue_age "
        "ON purge_targets(status, created_at, receipt_id)"
    )
    connection.execute("PRAGMA user_version = 3")


def migrate_event_retry_backoff_v4(connection: sqlite3.Connection) -> None:
    """Persist event retry deadlines without delaying legacy failed rows."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    if "next_attempt_at" not in columns:
        connection.execute("ALTER TABLE event_inbox ADD COLUMN next_attempt_at TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS event_inbox_retry_due "
        "ON event_inbox(status, next_attempt_at, received_at, event_id)"
    )
    connection.execute("PRAGMA user_version = 4")


def migrate_event_claim_leases_v5(connection: sqlite3.Connection) -> None:
    """Add expiring claims so concurrent router workers cannot double-send."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    if "lease_owner" not in columns:
        connection.execute("ALTER TABLE event_inbox ADD COLUMN lease_owner TEXT")
    if "lease_expires_at" not in columns:
        connection.execute(
            "ALTER TABLE event_inbox ADD COLUMN lease_expires_at TEXT"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS event_inbox_claim_expiry "
        "ON event_inbox(status, lease_expires_at, received_at, event_id)"
    )
    connection.execute("PRAGMA user_version = 5")


def migrate_purge_retry_backoff_v6(connection: sqlite3.Connection) -> None:
    """Add due times for bounded automatic retries of failed artifact purges."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(purge_targets)").fetchall()
    }
    if "next_attempt_at" not in columns:
        connection.execute("ALTER TABLE purge_targets ADD COLUMN next_attempt_at TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS purge_targets_retry_due "
        "ON purge_targets(status, next_attempt_at, created_at, receipt_id)"
    )
    connection.execute("PRAGMA user_version = 6")


def migrate_goal_intake_provenance_v7(connection: sqlite3.Connection) -> None:
    """Retain compact origin IDs and initial state for user-facing reports."""

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(goals)").fetchall()
    }
    if "initial_status" not in columns:
        connection.execute("ALTER TABLE goals ADD COLUMN initial_status TEXT")
    if "source_event_id" not in columns:
        connection.execute("ALTER TABLE goals ADD COLUMN source_event_id TEXT")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS goals_project_source_event "
        "ON goals(project_id, source_event_id) WHERE source_event_id IS NOT NULL"
    )
    connection.execute("PRAGMA user_version = 7")


def migrate_verification_attestations_v8(connection: sqlite3.Connection) -> None:
    """Persist compact trusted provenance beside each immutable fact."""

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(facts)").fetchall()
    }
    if "verification_attestations_json" not in columns:
        connection.execute(
            "ALTER TABLE facts ADD COLUMN verification_attestations_json "
            "TEXT NOT NULL DEFAULT '[]'"
        )
    connection.execute("PRAGMA user_version = 8")


def migrate_artifact_retention_holds_v9(connection: sqlite3.Connection) -> None:
    """Persist explicit legal/operational holds on exact purge targets."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(purge_targets)").fetchall()
    }
    if "retention_hold" not in columns:
        connection.execute("ALTER TABLE purge_targets ADD COLUMN retention_hold TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS purge_targets_hold_status "
        "ON purge_targets(status, retention_hold, receipt_id)"
    )
    connection.execute("PRAGMA user_version = 9")


def migrate_artifact_hold_release_audit_v10(connection: sqlite3.Connection) -> None:
    """Persist attributable hold placement and explicit authorized release."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(purge_targets)").fetchall()
    }
    for column in (
        ("hold_created_at", "TEXT"),
        ("hold_created_by", "TEXT"),
        ("hold_released_at", "TEXT"),
        ("hold_released_by", "TEXT"),
        ("hold_release_rationale", "TEXT"),
    ):
        if column[0] not in columns:
            connection.execute(
                f"ALTER TABLE purge_targets ADD COLUMN {column[0]} {column[1]}"
            )
    connection.execute(
        "DROP INDEX IF EXISTS purge_targets_hold_status"
    )
    connection.execute(
        "CREATE INDEX purge_targets_hold_status "
        "ON purge_targets(status, retention_hold, hold_released_at, receipt_id)"
    )
    connection.execute("PRAGMA user_version = 10")


def migrate_durable_project_access_v11(connection: sqlite3.Connection) -> None:
    """Add an auditable project registry and exact, revocable access grants."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS project_registry (
               project_id TEXT PRIMARY KEY,
               repository_fingerprint TEXT NOT NULL UNIQUE,
               config_sha256 TEXT NOT NULL,
               backend_api_version INTEGER NOT NULL,
               status TEXT NOT NULL CHECK(status IN ('active', 'suspended')),
               registered_by TEXT NOT NULL,
               registered_at TEXT NOT NULL,
               updated_by TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS project_registry_audit (
               audit_id TEXT PRIMARY KEY,
               project_id TEXT NOT NULL REFERENCES project_registry(project_id),
               actor_id TEXT NOT NULL,
               action TEXT NOT NULL CHECK(action IN (
                   'registered', 'updated', 'suspended', 'reactivated'
               )),
               repository_fingerprint TEXT NOT NULL,
               config_sha256 TEXT NOT NULL,
               backend_api_version INTEGER NOT NULL,
               rationale TEXT NOT NULL,
               created_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS project_registry_audit_project "
        "ON project_registry_audit(project_id, created_at, audit_id)"
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS project_grants (
               grant_id TEXT PRIMARY KEY,
               project_id TEXT NOT NULL REFERENCES project_registry(project_id),
               subject_id TEXT NOT NULL,
               action TEXT NOT NULL CHECK(action IN (
                   'read', 'write', 'review', 'purge_retry',
                   'retention_hold_release', 'event_retry'
               )),
               granted_by TEXT NOT NULL,
               rationale TEXT NOT NULL,
               granted_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS project_grant_revocations (
               grant_id TEXT PRIMARY KEY REFERENCES project_grants(grant_id),
               revoked_by TEXT NOT NULL,
               rationale TEXT NOT NULL,
               revoked_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS project_grants_scope "
        "ON project_grants(project_id, subject_id, action, granted_at, grant_id)"
    )
    connection.execute("PRAGMA user_version = 11")


def migrate_sde_quality_feedback_v12(connection: sqlite3.Connection) -> None:
    """Add append-only, reviewer-attributed SDE quality feedback records."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS sde_quality_feedback (
               feedback_id TEXT PRIMARY KEY,
               candidate_id TEXT NOT NULL REFERENCES sde_candidates(candidate_id),
               reviewer_id TEXT NOT NULL,
               label TEXT NOT NULL CHECK(label IN (
                   'useful', 'not_useful', 'inaccurate', 'duplicate'
               )),
               rationale TEXT NOT NULL,
               created_at TEXT NOT NULL,
               UNIQUE(candidate_id, reviewer_id)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS sde_quality_feedback_candidate "
        "ON sde_quality_feedback(candidate_id, created_at, feedback_id)"
    )
    connection.execute("PRAGMA user_version = 12")


def migrate_shared_request_limiter_v13(connection: sqlite3.Connection) -> None:
    """Add bounded, cross-process subject/project token-bucket state."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS request_rate_buckets (
               subject_id TEXT NOT NULL,
               project_id TEXT NOT NULL,
               tokens REAL NOT NULL CHECK(tokens >= 0),
               updated_at REAL NOT NULL,
               touched_at REAL NOT NULL,
               PRIMARY KEY(subject_id, project_id)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS request_rate_buckets_touched "
        "ON request_rate_buckets(touched_at)"
    )
    connection.execute("PRAGMA user_version = 13")


def migrate_event_dispositions_v14(connection: sqlite3.Connection) -> None:
    """Persist an explicit applied/suppressed disposition on processed events."""

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    if "disposition" not in columns:
        connection.execute("ALTER TABLE event_inbox ADD COLUMN disposition TEXT")
    connection.execute("PRAGMA user_version = 14")


def migrate_fact_source_events_v15(connection: sqlite3.Connection) -> None:
    """Link newly observed facts to their first durable source event."""

    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(facts)").fetchall()
    }
    if "source_event_id" not in columns:
        connection.execute("ALTER TABLE facts ADD COLUMN source_event_id TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS facts_source_event "
        "ON facts(source_event_id) WHERE source_event_id IS NOT NULL"
    )
    connection.execute("PRAGMA user_version = 15")


def migrate_content_free_purge_errors_v16(connection: sqlite3.Connection) -> None:
    """Replace legacy exception text with a safe code in failed purge rows."""

    connection.execute(
        """UPDATE purge_targets
           SET error = 'legacy_failure_detail_redacted'
           WHERE status = 'failed' AND error IS NOT NULL"""
    )
    connection.execute("PRAGMA user_version = 16")


def migrate_semantic_event_replay_v17(connection: sqlite3.Connection) -> None:
    """Retain an occurrence-time-independent event identity for transport retries."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(event_inbox)").fetchall()
    }
    if "idempotency_sha256" not in columns:
        connection.execute(
            "ALTER TABLE event_inbox ADD COLUMN idempotency_sha256 TEXT"
        )
    cursor = connection.execute(
        "SELECT project_id, event_id, payload_json FROM event_inbox "
        "WHERE payload_json IS NOT NULL"
    )
    while rows := cursor.fetchmany(128):
        for row in rows:
            try:
                digest = EventEnvelope.from_json(row["payload_json"]).idempotency_sha256
            except (TypeError, ValueError):
                # Unknown legacy payloads retain the strict raw-digest fallback.
                continue
            connection.execute(
                "UPDATE event_inbox SET idempotency_sha256 = ? "
                "WHERE project_id = ? AND event_id = ?",
                (digest, row["project_id"], row["event_id"]),
            )
    connection.execute("PRAGMA user_version = 17")


def migrate_sde_proposal_context_v18(connection: sqlite3.Connection) -> None:
    """Add explicit impact and retrieval-value fields to reviewable SDE proposals."""

    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sde_candidates)").fetchall()
    }
    for column in ("impact", "retrieval_value"):
        if column not in columns:
            connection.execute(
                f"ALTER TABLE sde_candidates ADD COLUMN {column} TEXT"
            )
    connection.execute("PRAGMA user_version = 18")


def migrate_staging_artifact_age_v19(connection: sqlite3.Connection) -> None:
    """Store content-free publication times for files written by the V2 adapter."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS staging_artifact_times (
               project_id TEXT NOT NULL,
               path TEXT NOT NULL,
               sha256 TEXT NOT NULL,
               staged_at TEXT NOT NULL,
               PRIMARY KEY(project_id, path)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS staging_artifact_times_project_age "
        "ON staging_artifact_times(project_id, staged_at)"
    )
    connection.execute("PRAGMA user_version = 19")


def migrate_expiry_purge_receipts_v20(connection: sqlite3.Connection) -> None:
    """Persist attended expiry approvals and their retryable exact targets."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS expiry_purge_receipts (
               receipt_id TEXT PRIMARY KEY,
               project_id TEXT NOT NULL,
               reviewer_id TEXT NOT NULL,
               manifest_sha256 TEXT NOT NULL,
               status TEXT NOT NULL CHECK(status IN ('complete', 'purge_pending')),
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS expiry_purge_targets (
               receipt_id TEXT NOT NULL,
               path TEXT NOT NULL,
               sha256 TEXT NOT NULL,
               status TEXT NOT NULL CHECK(status IN ('pending', 'purged', 'failed')),
               attempts INTEGER NOT NULL DEFAULT 0,
               error TEXT,
               created_at TEXT NOT NULL,
               last_attempt_at TEXT,
               next_attempt_at TEXT,
               PRIMARY KEY(receipt_id, path),
               FOREIGN KEY(receipt_id) REFERENCES expiry_purge_receipts(receipt_id)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS expiry_purge_targets_due "
        "ON expiry_purge_targets(status, next_attempt_at, receipt_id)"
    )
    connection.execute("PRAGMA user_version = 20")


def migrate_cleanup_authorizations_v21(connection: sqlite3.Connection) -> None:
    """Record separate human cleanup approval for reviewed SDE inventories."""

    existing = connection.execute(
        "SELECT type FROM sqlite_master WHERE name = 'cleanup_authorizations'"
    ).fetchone()
    expected_columns = {
        "receipt_id": ("TEXT", 0, 1, None),
        "project_id": ("TEXT", 1, 0, None),
        "reviewer_id": ("TEXT", 1, 0, None),
        "manifest_sha256": ("TEXT", 1, 0, None),
        "approved_at": ("TEXT", 1, 0, None),
        "canonical_persisted": ("INTEGER", 1, 0, "0"),
        "canonical_target": ("TEXT", 0, 0, None),
        "canonical_sha256": ("TEXT", 0, 0, None),
        "canonical_persisted_at": ("TEXT", 0, 0, None),
    }
    if existing is not None:
        if existing[0] != "table":
            raise RuntimeError("cleanup authorization schema object is incompatible")
        actual_columns = {
            row[1]: (
                str(row[2]).upper(),
                int(row[3]),
                int(row[5]),
                str(row[4]) if row[4] is not None else None,
            )
            for row in connection.execute("PRAGMA table_info(cleanup_authorizations)")
        }
        actual_foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute(
                "PRAGMA foreign_key_list(cleanup_authorizations)"
            )
        }
        if actual_columns != expected_columns or actual_foreign_keys != {
            ("audit_receipts", "receipt_id", "receipt_id")
        }:
            raise RuntimeError("cleanup authorization table schema is incompatible")
    else:
        connection.execute(
            """CREATE TABLE cleanup_authorizations (
               receipt_id TEXT PRIMARY KEY,
               project_id TEXT NOT NULL,
               reviewer_id TEXT NOT NULL,
               manifest_sha256 TEXT NOT NULL,
               approved_at TEXT NOT NULL,
               canonical_persisted INTEGER NOT NULL DEFAULT 0,
               canonical_target TEXT,
               canonical_sha256 TEXT,
               canonical_persisted_at TEXT,
               FOREIGN KEY(receipt_id) REFERENCES audit_receipts(receipt_id)
           )"""
        )
    connection.execute("PRAGMA user_version = 21")


def migrate_event_payload_scrub_queue_v22(connection: sqlite3.Connection) -> None:
    """Track WAL truncation needed after transient event payload deletion."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS event_payload_scrub_queue (
               scrub_id INTEGER PRIMARY KEY,
               project_id TEXT,
               event_id TEXT,
               queued_at TEXT NOT NULL,
               attempts INTEGER NOT NULL DEFAULT 0,
               last_error_code TEXT,
               CHECK ((project_id IS NULL AND event_id IS NULL)
                   OR (project_id IS NOT NULL AND event_id IS NOT NULL)),
               UNIQUE(project_id, event_id),
               FOREIGN KEY(project_id, event_id)
                   REFERENCES event_inbox(project_id, event_id)
           )"""
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS event_payload_scrub_project
           ON event_payload_scrub_queue(project_id, scrub_id)"""
    )
    has_event_inbox = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'event_inbox'"
    ).fetchone() is not None
    if has_event_inbox and connection.execute(
        "SELECT 1 FROM event_inbox LIMIT 1"
    ).fetchone() is not None:
        connection.execute(
            """INSERT INTO event_payload_scrub_queue
               (project_id, event_id, queued_at)
               SELECT NULL, NULL, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE NOT EXISTS (
                 SELECT 1 FROM event_payload_scrub_queue WHERE project_id IS NULL
               )"""
        )
    connection.execute("PRAGMA user_version = 22")


_MIGRATION_STEPS: tuple[Callable[[sqlite3.Connection], None], ...] = (
    migrate_event_router_v2,
    migrate_purge_observability_v3,
    migrate_event_retry_backoff_v4,
    migrate_event_claim_leases_v5,
    migrate_purge_retry_backoff_v6,
    migrate_goal_intake_provenance_v7,
    migrate_verification_attestations_v8,
    migrate_artifact_retention_holds_v9,
    migrate_artifact_hold_release_audit_v10,
    migrate_durable_project_access_v11,
    migrate_sde_quality_feedback_v12,
    migrate_shared_request_limiter_v13,
    migrate_event_dispositions_v14,
    migrate_fact_source_events_v15,
    migrate_content_free_purge_errors_v16,
    migrate_semantic_event_replay_v17,
    migrate_sde_proposal_context_v18,
    migrate_staging_artifact_age_v19,
    migrate_expiry_purge_receipts_v20,
    migrate_cleanup_authorizations_v21,
    migrate_event_payload_scrub_queue_v22,
)


def apply_schema_migrations(
    connection: sqlite3.Connection,
    schema_version: int,
) -> None:
    """Advance a legacy schema to the current version inside caller's transaction."""

    if schema_version > SQLITE_SCHEMA_VERSION:
        raise RuntimeError(
            "database schema version "
            f"{schema_version} is newer than supported version "
            f"{SQLITE_SCHEMA_VERSION}"
        )
    if schema_version == SQLITE_SCHEMA_VERSION:
        return
    if schema_version == 0:
        return
    if schema_version < 1:
        raise RuntimeError(f"no migration path from database schema version {schema_version}")
    for migration in _MIGRATION_STEPS[schema_version - 1 :]:
        migration(connection)


def finish_unversioned_migrations(connection: sqlite3.Connection) -> None:
    """Apply ordered upgrades after the unversioned legacy schema reaches v1."""

    for migration in _MIGRATION_STEPS:
        migration(connection)
