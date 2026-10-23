"""Versioned SQLite schema migration and rollback fixtures."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from evidence_fixtures import attest_test_evidence

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    ConflictError,
    CuratorService,
    CuratorStore,
    CriterionStatus,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    EventEnvelope,
    FactKind,
    GoalStarted,
    GoalStatus,
    Materiality,
    ReviewDecision,
    SQLITE_SCHEMA_VERSION,
    SuccessCriterion,
)
from curatormd_v2.schema_migrations import (
    apply_schema_migrations,
    migrate_consumer_binding_lifecycle_v33,
    migrate_consumer_reenrollment_v34,
)


# EvidenceVerifier test double intentionally implements only `attest`.
class MigrationEvidenceVerifier:  # pylint: disable=too-few-public-methods
    """Accept the stable synthetic evidence reference used by this fixture."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the migration fixture's exact proof locator."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:migration"
            else None
        )


class MigrationReviewAuthorizer:
    """Supply a stable reviewer identity for local migration fixtures."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Return a stable reviewer identity for the local fixture."""

        del project_id, candidate_id, decision
        return authenticated_subject or "migration-operator"

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Supply an attributable reviewer for linked correction fixtures."""

        del project_id, candidate_id
        return authenticated_subject or "migration-operator"

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Supply an attributable identity for quality-feedback migration tests."""

        return self.authorize_correction(project_id, candidate_id, authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Supply an attributable identity for migration hold-release tests."""

        del project_id, receipt_id, path, rationale
        return authenticated_subject or "migration-operator"

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute an expiry decision to the migration fixture reviewer."""

        del project_id, manifest_sha256
        return authenticated_subject or "migration-operator"

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute a cleanup decision to the migration fixture reviewer."""

        del project_id, receipt_id, manifest_sha256
        return authenticated_subject or "migration-operator"


PROJECT_USAGE_COLUMNS = {
    "audit_receipts": frozenset(
        {
            "receipt_id", "candidate_id", "decision", "facts_sha256",
            "artifact_inventory_complete", "reviewer_id", "review_rationale",
            "canonical_persisted", "canonical_target", "canonical_sha256",
            "canonical_persisted_at", "purge_status", "created_at", "updated_at",
        }
    ),
    "cleanup_authorizations": frozenset(
        {
            "receipt_id", "project_id", "reviewer_id", "manifest_sha256",
            "approved_at", "canonical_persisted", "canonical_target",
            "canonical_sha256", "canonical_persisted_at", "dependency_map_sha256",
        }
    ),
    "event_cursors": frozenset(
        {"project_id", "source_id", "last_sequence", "updated_at"}
    ),
    "event_inbox": frozenset(
        {
            "project_id", "event_id", "event_type", "payload_sha256",
            "payload_bytes", "payload_json", "status", "received_at", "processed_at",
            "last_error", "next_attempt_at", "lease_owner", "lease_expires_at",
            "disposition", "attempts", "source_id", "source_sequence",
            "idempotency_sha256",
        }
    ),
    "event_payload_scrub_queue": frozenset(
        {"scrub_id", "project_id", "event_id", "queued_at", "attempts", "last_error_code"}
    ),
    "event_retry_audit": frozenset(
        {"retry_id", "project_id", "event_id", "actor_id", "created_at"}
    ),
    "expiry_purge_receipts": frozenset(
        {
            "receipt_id", "project_id", "reviewer_id", "manifest_sha256", "status",
            "created_at", "updated_at",
        }
    ),
    "expiry_purge_targets": frozenset(
        {
            "receipt_id", "path", "sha256", "status", "attempts", "error",
            "created_at", "last_attempt_at", "next_attempt_at", "device_id",
            "inode_id", "occurrence_id", "approval_stale",
        }
    ),
    "fact_archive_items": frozenset(
        {"fact_id", "compaction_id", "project_id", "goal_id", "dedupe_key", "created_at"}
    ),
    "fact_archives": frozenset(
        {
            "compaction_id", "schema_version", "project_id", "goal_id", "source_sha256",
            "archive_sha256", "source_bytes", "compressed_bytes", "fact_count",
            "payload_zlib", "reviewer_id", "approval_reason", "created_at",
        }
    ),
    "facts": frozenset(
        {
            "fact_id", "goal_id", "kind", "bullet", "criterion_id", "evidence_json",
            "verification_attestations_json", "source_event_id", "dedupe_key", "created_at",
        }
    ),
    "goal_criteria_versions": frozenset(
        {"goal_id", "revision", "criteria_json", "reason", "created_at"}
    ),
    "goals": frozenset(
        {
            "goal_id", "project_id", "problem", "criteria_json", "owner", "checklist_id",
            "checklist_version", "checklist_source_text", "parent_goal_id",
            "depends_on_json", "status", "next_action", "superseded_by_goal_id",
            "criteria_revision", "lifecycle_revision", "created_at", "updated_at",
            "initial_status", "source_event_id",
        }
    ),
    "purge_targets": frozenset(
        {
            "receipt_id", "path", "sha256", "status", "attempts", "error", "created_at",
            "last_attempt_at", "next_attempt_at", "retention_hold", "hold_created_at",
            "hold_created_by", "hold_released_at", "hold_released_by",
            "hold_release_rationale", "device_id", "inode_id", "occurrence_id",
            "approval_stale", "reacquisition_action",
        }
    ),
    "sde_candidates": frozenset(
        {
            "candidate_id", "goal_id", "materiality", "rationale", "fact_ids_json",
            "dedupe_key", "status", "created_at", "impact", "retrieval_value",
        }
    ),
    "sde_corrections": frozenset(
        {"correction_id", "candidate_id", "correction", "rationale", "reviewer_id", "created_at"}
    ),
    "sde_quality_feedback": frozenset(
        {"feedback_id", "candidate_id", "reviewer_id", "label", "rationale", "created_at"}
    ),
    "staging_artifact_occurrences": frozenset(
        {"project_id", "path", "sha256", "device_id", "inode_id", "occurrence_id", "observed_at"}
    ),
    "staging_artifact_times": frozenset(
        {"project_id", "path", "sha256", "staged_at", "device_id", "inode_id", "occurrence_id"}
    ),
}

CONTROL_PLANE_USAGE_COLUMNS = {
    "consumer_drain_events": frozenset(
        {
            "project_id", "transition_id", "event_id", "payload_sha256",
            "idempotency_sha256", "source_id", "source_sequence",
        }
    ),
    "consumer_drain_sessions": frozenset(
        {
            "project_id", "transition_id", "actor_id", "caller_subject",
            "caller_profile", "binding_revision", "source_epoch", "config_sha256",
            "inventory_sha256", "created_at", "expires_at", "revoked_at",
        }
    ),
    "consumer_bindings": frozenset(
        {"project_id", "status", "revision", "source_epoch", "updated_by", "updated_at"}
    ),
    "consumer_binding_audit": frozenset(
        {
            "audit_id", "project_id", "actor_id", "action", "from_status", "to_status",
            "source_epoch", "revision", "transition_id", "rationale", "created_at",
        }
    ),
    "project_grant_revocations": frozenset(
        {"grant_id", "revoked_by", "rationale", "revoked_at"}
    ),
    "project_grants": frozenset(
        {"grant_id", "project_id", "subject_id", "action", "granted_by", "rationale", "granted_at"}
    ),
    "project_registry": frozenset(
        {
            "project_id", "repository_fingerprint", "config_sha256", "backend_api_version",
            "status", "registered_by", "registered_at", "updated_by", "updated_at", "revision",
        }
    ),
    "project_registry_audit": frozenset(
        {
            "audit_id", "project_id", "actor_id", "action", "repository_fingerprint",
            "config_sha256", "backend_api_version", "rationale", "created_at", "revision",
            "transition_id", "review_packet_sha256", "review_packet_json",
            "suspension_transition_id",
        }
    ),
    "project_retirement_tombstones": frozenset(
        {
            "project_id", "transition_id", "retired_by", "retired_revision",
            "source_epoch", "rationale", "retired_at",
        }
    ),
    "terminal_event_dispositions": frozenset(
        {
            "project_id", "event_id", "transition_id", "actor_id", "prior_status",
            "payload_sha256", "rationale", "created_at",
        }
    ),
    "request_rate_buckets": frozenset(
        {"subject_id", "project_id", "tokens", "updated_at", "touched_at"}
    ),
}


class SchemaMigrationTests(unittest.TestCase):
    """Verify supported SQLite upgrades and refusal of unknown schemas."""

    def test_current_schema_columns_have_explicit_storage_classes(self) -> None:
        """Require every durable column to enter a storage-class measure."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "accounting.sqlite3"
            store = CuratorStore(database_path)
            connection = sqlite3.connect(database_path)
            try:
                actual_columns = {
                    row[0]: frozenset(
                        column[1]
                        for column in connection.execute(
                            f'PRAGMA table_info("{row[0]}")'
                        )
                    )
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            finally:
                connection.close()
                store.close()

        self.assertTrue(
            set(PROJECT_USAGE_COLUMNS).isdisjoint(CONTROL_PLANE_USAGE_COLUMNS)
        )
        self.assertEqual(
            actual_columns,
            PROJECT_USAGE_COLUMNS | CONTROL_PLANE_USAGE_COLUMNS,
        )

    def test_v35_migration_adds_terminal_event_disposition_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v35.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP TABLE terminal_event_dispositions")
            connection.execute("PRAGMA user_version = 35")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(terminal_event_dispositions)"
                        ).fetchall()
                    }
                    self.assertEqual(
                        columns,
                        {
                            "project_id", "event_id", "transition_id", "actor_id",
                            "prior_status", "payload_sha256", "rationale", "created_at",
                        },
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v36_migration_adds_reactivation_review_receipt_fields(self) -> None:
        """Preserve old lifecycle history with null review provenance."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v36.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            now = "2026-10-24T00:00:00+00:00"
            connection.execute(
                """INSERT INTO project_registry
                   (project_id, repository_fingerprint, config_sha256,
                    backend_api_version, status, registered_by, registered_at,
                    updated_by, updated_at, revision)
                   VALUES ('legacy-review-project', ?, ?, 1, 'suspended',
                           'legacy-admin', ?, 'legacy-admin', ?, 2)""",
                ("1" * 64, "2" * 64, now, now),
            )
            connection.execute(
                """INSERT INTO project_registry_audit
                   (audit_id, project_id, actor_id, action, repository_fingerprint,
                    config_sha256, backend_api_version, rationale, created_at,
                    revision, transition_id)
                   VALUES ('legacy-review-audit', 'legacy-review-project',
                           'legacy-admin', 'suspended', ?, ?, 1, 'legacy suspension',
                           ?, 2, 'legacy-suspend-1')""",
                ("1" * 64, "2" * 64, now),
            )
            connection.execute(
                "ALTER TABLE project_registry_audit DROP COLUMN review_packet_sha256"
            )
            connection.execute(
                "ALTER TABLE project_registry_audit DROP COLUMN review_packet_json"
            )
            connection.execute(
                "ALTER TABLE project_registry_audit DROP COLUMN suspension_transition_id"
            )
            connection.execute("PRAGMA user_version = 36")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(project_registry_audit)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "review_packet_sha256",
                            "review_packet_json",
                            "suspension_transition_id",
                        }.issubset(columns)
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    legacy = connection.execute(
                        """SELECT review_packet_sha256, review_packet_json,
                                  suspension_transition_id
                           FROM project_registry_audit
                           WHERE audit_id = 'legacy-review-audit'"""
                    ).fetchone()
                    self.assertIsNone(legacy["review_packet_sha256"])
                    self.assertIsNone(legacy["review_packet_json"])
                    self.assertIsNone(legacy["suspension_transition_id"])
            finally:
                migrated.close()

    def test_v17_migration_adds_sde_context_and_staging_age_metadata(self) -> None:
        """Keep old proposals readable and add empty staging-age metadata."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                """CREATE TABLE sde_candidates (
                       candidate_id TEXT PRIMARY KEY,
                       goal_id TEXT NOT NULL,
                       materiality TEXT NOT NULL,
                       rationale TEXT NOT NULL,
                       fact_ids_json TEXT NOT NULL,
                       dedupe_key TEXT NOT NULL,
                       status TEXT NOT NULL,
                       created_at TEXT NOT NULL
                   )"""
            )
            connection.execute(
                """INSERT INTO sde_candidates VALUES
                   ('legacy-sde', 'goal', 'implementation', 'legacy', '[]',
                    'legacy-key', 'pending_review', '2026-10-20T00:00:00+00:00')"""
            )
            connection.execute("PRAGMA user_version = 17")
            apply_schema_migrations(connection, 17)

            candidate = connection.execute(
                "SELECT impact, retrieval_value FROM sde_candidates "
                "WHERE candidate_id = 'legacy-sde'"
            ).fetchone()
            self.assertEqual(tuple(candidate), (None, None))
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
            self.assertEqual(
                connection.execute(
                    "PRAGMA table_info(staging_artifact_times)"
                ).fetchall()[0]["name"],
                "project_id",
            )
        finally:
            connection.close()

    def test_v19_migration_adds_expiry_receipts_and_preserves_staging_ages(self) -> None:
        """Add approval receipt tables without changing trusted age records."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v19.sqlite3"
            store = CuratorStore(database_path)
            with store.transaction() as connection:
                connection.execute(
                    """INSERT INTO staging_artifact_times
                       (project_id, path, sha256, staged_at)
                       VALUES (?, ?, ?, ?)""",
                    (
                        "migration-project",
                        "goal-a/scratch/item-a",
                        "a" * 64,
                        "2026-10-20T00:00:00+00:00",
                    ),
                )
                connection.execute("DROP TABLE expiry_purge_targets")
                connection.execute("DROP TABLE expiry_purge_receipts")
                connection.execute("PRAGMA user_version = 19")
            store.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertEqual(
                        tuple(connection.execute(
                            "SELECT path, sha256, staged_at FROM staging_artifact_times"
                        ).fetchone()),
                        ("goal-a/scratch/item-a", "a" * 64, "2026-10-20T00:00:00+00:00"),
                    )
                    self.assertIn(
                        "receipt_id",
                        {
                            row["name"]
                            for row in connection.execute(
                                "PRAGMA table_info(expiry_purge_receipts)"
                            )
                        },
                    )
                    self.assertIn(
                        "next_attempt_at",
                        {
                            row["name"]
                            for row in connection.execute(
                                "PRAGMA table_info(expiry_purge_targets)"
                            )
                        },
                    )
            finally:
                migrated.close()

    def test_v29_migration_requires_explicit_reacquisition_action(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                """CREATE TABLE purge_targets (
                       receipt_id TEXT NOT NULL,
                       path TEXT NOT NULL,
                       status TEXT NOT NULL,
                       next_attempt_at TEXT,
                       approval_stale INTEGER NOT NULL DEFAULT 0,
                       PRIMARY KEY(receipt_id, path)
                   )"""
            )
            connection.executemany(
                "INSERT INTO purge_targets VALUES (?, ?, ?, ?, 0)",
                (
                    ("pending", "/stage/pending", "pending", "2026-10-24T00:00:00+00:00"),
                    ("purged", "/stage/purged", "purged", None),
                ),
            )
            connection.execute("PRAGMA user_version = 29")

            apply_schema_migrations(connection, 29)

            rows = connection.execute(
                "SELECT receipt_id, reacquisition_action, approval_stale, next_attempt_at "
                "FROM purge_targets ORDER BY receipt_id"
            ).fetchall()
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
            self.assertEqual(
                tuple(rows[0]), ("pending", "not_recorded", 1, None)
            )
            self.assertEqual(
                tuple(rows[1]), ("purged", "not_recorded", 0, None)
            )
        finally:
            connection.close()

    def test_v33_migration_backfills_active_consumer_binding(self) -> None:
        """Existing project registrations gain a separate active binding."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """CREATE TABLE project_registry (
                       project_id TEXT PRIMARY KEY,
                       updated_by TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   );
                   INSERT INTO project_registry VALUES (
                       'legacy-project', 'operator', '2026-10-23T00:00:00Z'
                   );"""
            )
            migrate_consumer_binding_lifecycle_v33(connection)
            binding = connection.execute(
                "SELECT * FROM consumer_bindings WHERE project_id = 'legacy-project'"
            ).fetchone()
            self.assertEqual(
                tuple(binding),
                (
                    "legacy-project", "active", 1, 1, "operator",
                    "2026-10-23T00:00:00Z",
                ),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM consumer_binding_audit"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_v34_migration_preserves_audit_and_allows_reenrollment(self) -> None:
        """Preserve binding receipts while extending the action constraint."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """CREATE TABLE project_registry (
                       project_id TEXT PRIMARY KEY,
                       updated_by TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   );
                   INSERT INTO project_registry VALUES (
                       'legacy-project', 'operator', '2026-10-23T00:00:00Z'
                   );"""
            )
            migrate_consumer_binding_lifecycle_v33(connection)
            connection.execute(
                """INSERT INTO consumer_binding_audit
                   (audit_id, project_id, actor_id, action, from_status, to_status,
                    source_epoch, revision, transition_id, rationale, created_at)
                   VALUES ('audit-enrolled', 'legacy-project', 'operator', 'enrolled',
                           NULL, 'active', 1, 1, 'enroll-1', 'legacy',
                           '2026-10-23T00:00:00Z')"""
            )
            migrate_consumer_reenrollment_v34(connection)
            previous = connection.execute(
                "SELECT action, source_epoch FROM consumer_binding_audit"
            ).fetchone()
            self.assertEqual(tuple(previous), ("enrolled", 1))
            connection.execute(
                """INSERT INTO consumer_binding_audit
                   (audit_id, project_id, actor_id, action, from_status, to_status,
                    source_epoch, revision, transition_id, rationale, created_at)
                   VALUES ('audit-reenrolled', 'legacy-project', 'operator',
                           'reenrolled', 'deregistered', 'active', 2, 2,
                           'reenroll-1', 'reviewed config', '2026-10-23T00:01:00Z')"""
            )
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0], 34
            )
        finally:
            connection.close()

    def test_v30_migration_backfills_project_registry_revisions(self) -> None:
        """Preserve current bindings and assign ordered revisions to old audits."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """CREATE TABLE project_registry (
                       project_id TEXT PRIMARY KEY,
                       repository_fingerprint TEXT NOT NULL,
                       config_sha256 TEXT NOT NULL,
                       backend_api_version INTEGER NOT NULL,
                       status TEXT NOT NULL,
                       registered_by TEXT NOT NULL,
                       registered_at TEXT NOT NULL,
                       updated_by TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   );
                   CREATE TABLE project_registry_audit (
                       audit_id TEXT PRIMARY KEY,
                       project_id TEXT NOT NULL,
                       actor_id TEXT NOT NULL,
                       action TEXT NOT NULL,
                       repository_fingerprint TEXT NOT NULL,
                       config_sha256 TEXT NOT NULL,
                       backend_api_version INTEGER NOT NULL,
                       rationale TEXT NOT NULL,
                       created_at TEXT NOT NULL
                   );"""
            )
            connection.execute(
                "INSERT INTO project_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("project-a", "r" * 64, "c" * 64, 1, "active", "owner", "t1", "owner", "t4"),
            )
            connection.executemany(
                "INSERT INTO project_registry_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(
                    (
                        f"audit-{index}",
                        "project-a",
                        "owner",
                        action,
                        "r" * 64,
                        "c" * 64,
                        1,
                        "fixture",
                        "same-time",
                    )
                    for index, action in enumerate(
                        ("registered", "updated", "suspended", "reactivated"), 1
                    )
                ),
            )
            connection.execute("PRAGMA user_version = 30")

            apply_schema_migrations(connection, 30)

            registration = connection.execute(
                "SELECT revision FROM project_registry WHERE project_id = 'project-a'"
            ).fetchone()
            audit_revisions = connection.execute(
                "SELECT revision FROM project_registry_audit ORDER BY created_at"
            ).fetchall()
            transition_ids = connection.execute(
                "SELECT transition_id FROM project_registry_audit"
            ).fetchall()
            transition_index = connection.execute(
                "PRAGMA index_list(project_registry_audit)"
            ).fetchall()
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
            self.assertEqual(registration["revision"], 4)
            self.assertEqual([row["revision"] for row in audit_revisions], [1, 2, 3, 4])
            self.assertEqual([row["transition_id"] for row in transition_ids], [None] * 4)
            self.assertIn(
                "project_registry_transition_id",
                {row["name"] for row in transition_index},
            )
        finally:
            connection.close()

    def test_v20_migration_adds_cleanup_authorizations_without_inventing_them(self) -> None:
        """Preserve legacy SDE receipts while leaving their new approval absent."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "CREATE TABLE audit_receipts (receipt_id TEXT PRIMARY KEY)"
            )
            connection.execute(
                "INSERT INTO audit_receipts (receipt_id) VALUES (?)",
                ("legacy-sde-receipt",),
            )
            connection.execute("PRAGMA user_version = 20")

            apply_schema_migrations(connection, 20)

            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT receipt_id FROM audit_receipts"
                ).fetchone()[0],
                "legacy-sde-receipt",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM cleanup_authorizations"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_v21_migration_queues_one_content_free_legacy_wal_scrub(self) -> None:
        """Schedule one database-wide scrub without copying legacy payloads."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                """CREATE TABLE event_inbox (
                       project_id TEXT NOT NULL,
                       event_id TEXT NOT NULL,
                       payload_json TEXT,
                       PRIMARY KEY(project_id, event_id)
                   )"""
            )
            connection.execute(
                "INSERT INTO event_inbox VALUES (?, ?, ?)",
                ("project-a", "legacy-event", '{"private":"legacy-canary"}'),
            )
            connection.execute("PRAGMA user_version = 21")

            apply_schema_migrations(connection, 21)

            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )
            row = connection.execute(
                "SELECT project_id, event_id, attempts, last_error_code "
                "FROM event_payload_scrub_queue"
            ).fetchone()
            self.assertEqual(
                tuple(row),
                (None, None, 0, None),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT payload_json FROM event_inbox WHERE event_id = ?",
                    ("legacy-event",),
                ).fetchone()[0],
                '{"private":"legacy-canary"}',
            )
        finally:
            connection.close()

    def test_v22_upgrade_failure_rolls_back_lifecycle_schema_changes(self) -> None:
        """An injected v33 failure must leave a v22 database wholly unchanged."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v22.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """CREATE TABLE project_registry (
                           project_id TEXT PRIMARY KEY,
                           updated_by TEXT NOT NULL,
                           updated_at TEXT NOT NULL
                       )"""
                )
                connection.execute(
                    "INSERT INTO project_registry VALUES (?, ?, ?)",
                    ("legacy-project", "legacy-owner", "2026-10-23T00:00:00Z"),
                )
                connection.execute(
                    """CREATE TABLE event_payload_scrub_queue (
                           scrub_id INTEGER PRIMARY KEY,
                           project_id TEXT,
                           event_id TEXT,
                           queued_at TEXT NOT NULL,
                           attempts INTEGER NOT NULL DEFAULT 0,
                           last_error_code TEXT
                       )"""
                )
                # Simulate a conflicting legacy object so v33 fails after v31
                # has already altered project_registry inside the migration tx.
                connection.execute(
                    "CREATE TABLE consumer_bindings (project_id TEXT PRIMARY KEY)"
                )
                connection.execute("PRAGMA user_version = 22")
                connection.commit()
                database_path.chmod(0o600)

                with self.assertRaisesRegex(
                    sqlite3.OperationalError, "no column named status"
                ):
                    CuratorStore(database_path)

                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 22
                )
                registry_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(project_registry)")
                }
                self.assertNotIn("revision", registry_columns)
                self.assertEqual(
                    connection.execute(
                        "SELECT project_id, updated_by, updated_at FROM project_registry"
                    ).fetchone(),
                    ("legacy-project", "legacy-owner", "2026-10-23T00:00:00Z"),
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' "
                        "AND name = 'consumer_binding_audit'"
                    ).fetchone(),
                    None,
                )
                connection.execute("DROP TABLE consumer_bindings")
                connection.commit()
            finally:
                connection.close()

            recovered = CuratorStore(database_path)
            try:
                with recovered.transaction() as migrated:
                    self.assertEqual(
                        migrated.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertEqual(
                        tuple(
                            migrated.execute(
                                "SELECT status, revision, source_epoch "
                                "FROM consumer_bindings WHERE project_id = ?",
                                ("legacy-project",),
                            ).fetchone()
                        ),
                        ("active", 1, 1),
                    )
            finally:
                recovered.close()

    def test_v20_migration_rejects_incompatible_cleanup_authorization_table(self) -> None:
        """Do not stamp v21 over a conflicting object with the expected table name."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                "CREATE TABLE audit_receipts (receipt_id TEXT PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE cleanup_authorizations (unexpected TEXT)"
            )
            connection.execute("PRAGMA user_version = 20")

            with self.assertRaisesRegex(
                RuntimeError, "cleanup authorization table schema is incompatible"
            ):
                apply_schema_migrations(connection, 20)

            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0], 20
            )
            self.assertEqual(
                [
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(cleanup_authorizations)"
                    )
                ],
                ["unexpected"],
            )
        finally:
            connection.close()

    def test_v20_migration_rejects_cleanup_table_without_receipt_foreign_key(self) -> None:
        """Require the migrated authorization to remain tied to an SDE receipt."""

        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(
                "CREATE TABLE audit_receipts (receipt_id TEXT PRIMARY KEY)"
            )
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
                       canonical_persisted_at TEXT
                   )"""
            )
            connection.execute("PRAGMA user_version = 20")

            with self.assertRaisesRegex(
                RuntimeError, "cleanup authorization table schema is incompatible"
            ):
                apply_schema_migrations(connection, 20)

            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0], 20
            )
            self.assertEqual(
                connection.execute(
                    "PRAGMA foreign_key_list(cleanup_authorizations)"
                ).fetchall(),
                [],
            )
        finally:
            connection.close()

    def test_v20_migration_rejects_cleanup_table_with_incompatible_constraints(
        self,
    ) -> None:
        """Reject a wrong default, nullable required field, or missing primary key."""

        schema = """CREATE TABLE cleanup_authorizations (
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
        invalid_schemas = (
            schema.replace("DEFAULT 0", "DEFAULT 1"),
            schema.replace("project_id TEXT NOT NULL", "project_id TEXT"),
            schema.replace("receipt_id TEXT PRIMARY KEY", "receipt_id TEXT"),
        )
        for invalid_schema in invalid_schemas:
            with self.subTest(schema=invalid_schema):
                connection = sqlite3.connect(":memory:")
                try:
                    connection.execute(
                        "CREATE TABLE audit_receipts (receipt_id TEXT PRIMARY KEY)"
                    )
                    connection.execute(invalid_schema)
                    connection.execute("PRAGMA user_version = 20")

                    with self.assertRaisesRegex(
                        RuntimeError,
                        "cleanup authorization table schema is incompatible",
                    ):
                        apply_schema_migrations(connection, 20)

                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0], 20
                    )
                finally:
                    connection.close()

    def test_v15_migration_redacts_legacy_purge_failure_details(self) -> None:
        """Remove potentially sensitive exception text without clearing retry state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v15.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """INSERT INTO purge_targets (
                       receipt_id, path, sha256, status, attempts, error, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "legacy-receipt",
                    "/private/SENSITIVE_PURGE_PATH_SENTINEL",
                    "0" * 64,
                    "failed",
                    3,
                    "cannot safely remove /private/SENSITIVE_PURGE_PATH_SENTINEL",
                    "2026-10-20T00:00:00+00:00",
                ),
            )
            connection.execute(
                """CREATE TRIGGER block_legacy_error_redaction
                   BEFORE UPDATE OF error ON purge_targets
                   BEGIN SELECT RAISE(ABORT, 'injected redaction failure'); END"""
            )
            connection.execute("PRAGMA user_version = 15")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.IntegrityError):
                CuratorStore(database_path)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 15
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT error FROM purge_targets WHERE receipt_id = ?",
                        ("legacy-receipt",),
                    ).fetchone()[0],
                    "cannot safely remove /private/SENSITIVE_PURGE_PATH_SENTINEL",
                )
                connection.execute("DROP TRIGGER block_legacy_error_redaction")
                connection.commit()
            finally:
                connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        """SELECT status, attempts, error
                           FROM purge_targets WHERE receipt_id = ?""",
                        ("legacy-receipt",),
                    ).fetchone()
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SQLITE_SCHEMA_VERSION)
                self.assertEqual(row["status"], "failed")
                self.assertEqual(row["attempts"], 3)
                self.assertEqual(row["error"], "legacy_failure_detail_redacted")
                self.assertNotIn("SENSITIVE_PURGE_PATH_SENTINEL", row["error"])
            finally:
                migrated.close()

    def test_v16_migration_backfills_semantic_digest_for_retained_event(self) -> None:
        """Backfill retry identity only while the bounded payload is retained."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v16.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                event_id="migration-replay-event",
                project_id="migration-project",
                payload=GoalStarted(
                    goal_id="migration-replay-goal",
                    problem="Preserve a received event across schema migration",
                    success_criteria=(
                        SuccessCriterion("verified", "The event remains retryable"),
                    ),
                ),
            )
            store.ingest_event(event)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE event_inbox DROP COLUMN idempotency_sha256")
            connection.execute("PRAGMA user_version = 16")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        "SELECT idempotency_sha256 FROM event_inbox WHERE event_id = ?",
                        (event.event_id,),
                    ).fetchone()
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SQLITE_SCHEMA_VERSION)
                self.assertEqual(row["idempotency_sha256"], event.idempotency_sha256)
            finally:
                migrated.close()

    def test_v16_migration_does_not_guess_identity_for_processed_event(self) -> None:
        """Keep strict replay conflict when the legacy payload was discarded."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v16-processed.sqlite3"
            store = CuratorStore(database_path)
            payload = GoalStarted(
                goal_id="migration-processed-goal",
                problem="Keep processed legacy event identity conservative",
                success_criteria=(
                    SuccessCriterion("verified", "Unknown identity stays unknown"),
                ),
            )
            original = EventEnvelope(
                event_id="migration-processed-event",
                project_id="migration-project",
                payload=payload,
                occurred_at="2026-10-20T08:00:00+00:00",
            )
            store.ingest_event(original)
            store.mark_event_processed(
                "migration-project", "migration-processed-event"
            )
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE event_inbox DROP COLUMN idempotency_sha256")
            connection.execute("PRAGMA user_version = 16")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        """SELECT payload_json, payload_sha256, idempotency_sha256
                           FROM event_inbox WHERE project_id = ? AND event_id = ?""",
                        ("migration-project", "migration-processed-event"),
                    ).fetchone()
                self.assertIsNone(row["payload_json"])
                self.assertTrue(row["payload_sha256"])
                self.assertIsNone(row["idempotency_sha256"])
                retry = EventEnvelope(
                    event_id=original.event_id,
                    project_id=original.project_id,
                    payload=payload,
                    occurred_at="2026-10-20T08:00:01+00:00",
                )
                with self.assertRaisesRegex(ConflictError, "different payload"):
                    migrated.ingest_event(retry)
            finally:
                migrated.close()

    def test_v11_database_migrates_to_current_schema_without_feedback_labels(
        self,
    ) -> None:
        """Upgrade schema v11 without inventing feedback or limiter state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v11.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute("DROP TABLE sde_quality_feedback")
            connection.execute("PRAGMA user_version = 11")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT count(*) FROM sde_quality_feedback"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT count(*) FROM request_rate_buckets"
                        ).fetchone()[0],
                        0,
                    )
            finally:
                migrated.close()

    def test_v12_database_migrates_shared_request_limiter_v13(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v12.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute("PRAGMA user_version = 12")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(request_rate_buckets)"
                        ).fetchall()
                    }
                    self.assertEqual(
                        columns,
                        {"subject_id", "project_id", "tokens", "updated_at", "touched_at"},
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v13_database_adds_event_disposition_without_losing_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v13.sqlite3"
            store = CuratorStore(database_path)
            receipt, inserted = store.ingest_event(
                EventEnvelope(
                    "event-before-disposition",
                    "migration-project",
                    GoalStarted(
                        "migration-goal", "Keep prior event receipts",
                        (SuccessCriterion("done", "Receipt remains available"),),
                    ),
                )
            )
            self.assertTrue(inserted)
            self.assertEqual(receipt.status.value, "received")
            processed = store.mark_event_processed(
                "migration-project", "event-before-disposition"
            )
            self.assertEqual(processed.status.value, "processed")
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE event_inbox DROP COLUMN disposition")
            connection.execute("PRAGMA user_version = 13")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(event_inbox)"
                        ).fetchall()
                    }
                    self.assertIn("disposition", columns)
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                preserved = migrated.event_receipt(
                    "migration-project", "event-before-disposition"
                )
                self.assertEqual(preserved.status.value, "processed")
                self.assertIsNone(preserved.disposition)
            finally:
                migrated.close()

    def test_v14_database_adds_nullable_fact_source_event(self) -> None:
        """Add source provenance without guessing it for existing facts."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v14.sqlite3"
            staging_root = Path(temporary) / "staging"
            staging_root.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging_root),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve fact history through v15",
                (SuccessCriterion("done", "Existing fact remains readable"),),
            )
            fact, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Legacy fact has unknown origin"
            )
            store.close()

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            connection.execute("DROP INDEX facts_source_event")
            connection.execute("ALTER TABLE facts DROP COLUMN source_event_id")
            connection.execute("PRAGMA user_version = 14")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                self.assertIsNone(migrated.get_fact(fact.fact_id).source_event_id)
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertIn(
                        "source_event_id",
                        {
                            row["name"]
                            for row in connection.execute(
                                "PRAGMA table_info(facts)"
                            ).fetchall()
                        },
                    )
            finally:
                migrated.close()

    def test_v12_rate_limiter_migration_rolls_back_on_incompatible_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v12-failed.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute(
                "CREATE TABLE request_rate_buckets (unexpected TEXT)"
            )
            connection.execute("PRAGMA user_version = 12")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.OperationalError):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 12
                )
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(request_rate_buckets)"
                    ).fetchall()
                }
                self.assertEqual(columns, {"unexpected"})
            finally:
                connection.close()

    @staticmethod
    def _create_unversioned_legacy_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.execute(
            """CREATE TABLE goals (
                goal_id TEXT PRIMARY KEY,
                problem TEXT NOT NULL,
                criteria_json TEXT NOT NULL,
                owner TEXT,
                checklist_id TEXT,
                status TEXT NOT NULL,
                next_action TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO goals
               (goal_id, problem, criteria_json, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "legacy-goal",
                "Preserve data through schema migration",
                '[{"criterion_id":"done","description":"Migration passes"}]',
                GoalStatus.ACTIVE.value,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()
        connection.close()
        path.chmod(0o600)

    def test_unversioned_legacy_database_migrates_and_preserves_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "legacy.sqlite3"
            self._create_unversioned_legacy_database(database_path)

            store = CuratorStore(database_path)
            try:
                goal = store.get_goal("legacy-goal", "default")
                self.assertEqual(goal.problem, "Preserve data through schema migration")
                self.assertEqual(goal.lifecycle_revision, 2)
                self.assertEqual(goal.criteria_revision, 1)
                self.assertEqual(len(goal.success_criteria), 1)
                with store.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                store.close()

    def test_failed_migration_rolls_back_ddl_data_repairs_and_version_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "legacy.sqlite3"
            self._create_unversioned_legacy_database(database_path)
            connection = sqlite3.connect(database_path)
            connection.execute(
                """CREATE TRIGGER fail_lifecycle_revision_migration
                   BEFORE UPDATE ON goals
                   BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END"""
            )
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(sqlite3.IntegrityError, "injected migration failure"):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                goal_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(goals)")
                }
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 0
                )
                self.assertNotIn("project_id", goal_columns)
                self.assertNotIn("lifecycle_revision", goal_columns)
                self.assertEqual(tables, {"goals"})
                self.assertEqual(
                    connection.execute(
                        "SELECT problem FROM goals WHERE goal_id = 'legacy-goal'"
                    ).fetchone()[0],
                    "Preserve data through schema migration",
                )
                connection.execute("DROP TRIGGER fail_lifecycle_revision_migration")
                connection.commit()
            finally:
                connection.close()

            store = CuratorStore(database_path)
            try:
                self.assertEqual(
                    store.get_goal("legacy-goal", "default").lifecycle_revision, 2
                )
            finally:
                store.close()

    def test_v1_event_inbox_migrates_to_current_schema_without_losing_receipt(self) -> None:
        """Add router metadata and retry scheduling without losing receipts."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v1.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v1-event",
                "project-a",
                GoalStarted(
                    "v1-goal",
                    "Preserve an accepted event during migration",
                    (SuccessCriterion("done", "The goal remains recorded"),),
                ),
            )
            receipt, inserted = store.ingest_event(event)
            self.assertTrue(inserted)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX purge_targets_queue_age")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN last_attempt_at")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN created_at")
            connection.execute("DROP INDEX event_inbox_retry_due")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("DROP INDEX event_inbox_source_order")
            connection.execute("DROP INDEX event_retry_audit_event")
            connection.execute("DROP TABLE event_retry_audit")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN source_sequence")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN source_id")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN attempts")
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                after = migrated.event_receipt("project-a", "v1-event")
                self.assertEqual(after.payload_sha256, receipt.payload_sha256)
                self.assertEqual(after.status, receipt.status)
                self.assertEqual(after.attempts, 0)
                self.assertIsNone(after.next_attempt_at)
                with migrated.transaction() as migrated_connection:
                    self.assertEqual(
                        migrated_connection.execute(
                            "PRAGMA user_version"
                        ).fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    columns = {
                        row["name"]
                        for row in migrated_connection.execute(
                            "PRAGMA table_info(event_inbox)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {"attempts", "source_id", "source_sequence"} <= columns
                    )
                    self.assertIsNotNone(
                        migrated_connection.execute(
                            "SELECT name FROM sqlite_master "
                            "WHERE type = 'table' AND name = 'event_retry_audit'"
                        ).fetchone()
                    )
            finally:
                migrated.close()

    def test_v2_purge_targets_migrate_with_receipt_age_and_no_attempt(self) -> None:
        """Backfill v2 artifact age from its durable parent receipt."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v2.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Create an artifact receipt before schema migration",
                (SuccessCriterion("verified", "The local migration proof is accepted"),),
            )
            changed, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Prepared the v2 receipt fixture"
            )
            verified, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The migration evidence fixture passed",
                criterion_id="verified",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "a" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            candidate = service.sde_assess(
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable migration fixture",
                (changed.fact_id, verified.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            target = staging / "temporary-artifact.json"
            target_hash = "b" * 64
            receipt = service.sde_confirm(
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                (ArtifactRef(str(target), target_hash),),
                artifact_inventory_complete=True,
            )
            self.assertFalse(receipt.canonical_persisted)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX purge_targets_queue_age")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN last_attempt_at")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN created_at")
            connection.execute("DROP INDEX event_inbox_retry_due")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                stored_receipt = migrated.get_receipt(
                    receipt.receipt_id, "migration-project"
                )
                target_record = migrated.get_purge_target_records(
                    receipt.receipt_id, "migration-project"
                )[0]
                self.assertEqual(stored_receipt.receipt_id, receipt.receipt_id)
                self.assertEqual(target_record.artifact.path, str(target))
                self.assertEqual(target_record.created_at, receipt.created_at)
                self.assertIsNone(target_record.last_attempt_at)
                self.assertEqual(target_record.attempts, 0)
                self.assertEqual(
                    target_record.status.value,
                    "pending",
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v3_failed_events_migrate_without_an_invented_retry_delay(self) -> None:
        """Keep legacy failed payloads immediately eligible after v4 upgrade."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v3.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v3-failed-event",
                "migration-project",
                GoalStarted(
                    "migration-event-goal",
                    "Preserve a failed event through retry schema migration",
                    (SuccessCriterion("done", "The event remains retryable"),),
                ),
            )
            store.ingest_event(event)
            original = store.mark_event_failed(
                "migration-project", event.event_id, "adapter_unavailable"
            )
            self.assertIsNotNone(original.next_attempt_at)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("DROP INDEX event_inbox_retry_due")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN next_attempt_at")
            connection.execute("PRAGMA user_version = 3")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                receipt = migrated.event_receipt("migration-project", event.event_id)
                self.assertEqual(receipt.status.value, "failed")
                self.assertEqual(receipt.attempts, 1)
                self.assertIsNone(receipt.next_attempt_at)
                self.assertEqual(
                    tuple(item.event_id for item in migrated.pending_events()),
                    (event.event_id,),
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v4_retry_deadline_survives_lease_schema_migration(self) -> None:
        """Upgrade v4 inboxes without erasing scheduled retry state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v4.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v4-failed-event",
                "migration-project",
                GoalStarted(
                    "migration-v4-goal",
                    "Preserve a retry deadline while adding worker leases",
                    (SuccessCriterion("done", "The retry remains scheduled"),),
                ),
            )
            store.ingest_event(event)
            original = store.mark_event_failed(
                "migration-project", event.event_id, "adapter_unavailable"
            )
            self.assertIsNotNone(original.next_attempt_at)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("PRAGMA user_version = 4")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                receipt = migrated.event_receipt("migration-project", event.event_id)
                self.assertEqual(receipt.next_attempt_at, original.next_attempt_at)
                self.assertEqual(migrated.pending_events(), ())
                self.assertEqual(migrated.event_queue_status().claimed_count, 0)
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v5_purge_target_stays_pending_without_cleanup_authorization(self) -> None:
        """Migrate the target without inventing either retry delay or approval."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v5.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve a purge target through the v6 migration",
                (SuccessCriterion("verified", "The migration keeps the target"),),
            )
            changed, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Prepared the purge migration fixture"
            )
            verified, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The migration evidence fixture passed",
                criterion_id="verified",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "a" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            candidate = service.sde_assess(
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Purge retry migration fixture",
                (changed.fact_id, verified.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            receipt = service.sde_confirm(
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                (ArtifactRef(str(staging / "temporary.txt"), "b" * 64),),
                artifact_inventory_complete=True,
            )
            receipt = store.mark_receipt_canonical_persisted(
                receipt.receipt_id,
                "persistence/HISTORY.md",
                "c" * 64,
                "migration-project",
            )
            self.assertEqual(receipt.purge_status.value, "purge_pending")
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("PRAGMA user_version = 5")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                target = migrated.get_purge_target_records(
                    receipt.receipt_id, "migration-project"
                )[0]
                self.assertEqual(target.status.value, "pending")
                self.assertEqual(target.attempts, 0)
                self.assertIsNone(target.next_attempt_at)
                self.assertIsNone(
                    migrated.cleanup_authorization(
                        receipt.receipt_id, "migration-project"
                    )
                )
                self.assertEqual(
                    tuple(
                        item.receipt_id
                        for item in migrated.due_pending_purge_receipts(
                            "migration-project"
                        )
                    ),
                    (),
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v6_adds_nullable_goal_intake_provenance_without_inventing_legacy_values(self) -> None:
        """Preserve old goals and leave unknown historical intake fields null."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v6.sqlite3"
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(Path(temporary)),
                project_id="migration-project",
            )
            legacy_goal = service.goal_start(
                "Preserve the v6 goal through provenance migration",
                (SuccessCriterion("done", "The old goal is unchanged"),),
                owner="legacy-owner",
            )
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX goals_project_source_event")
            connection.execute("ALTER TABLE goals DROP COLUMN source_event_id")
            connection.execute("ALTER TABLE goals DROP COLUMN initial_status")
            connection.execute("PRAGMA user_version = 6")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                preserved = migrated.get_goal(legacy_goal.goal_id, "migration-project")
                self.assertEqual(preserved.problem, legacy_goal.problem)
                self.assertEqual(preserved.owner, "legacy-owner")
                legacy_context = migrated.goal_report_context(
                    legacy_goal.goal_id, "migration-project"
                )
                self.assertIsNone(legacy_context.initial_status)
                self.assertIsNone(legacy_context.source_event_id)

                new_service = CuratorService(
                    migrated,
                    ArtifactPurger(Path(temporary)),
                    project_id="migration-project",
                )
                new_goal = new_service.goal_start(
                    "Record provenance for a new goal",
                    (SuccessCriterion("new", "The new fields are saved"),),
                    initial_status=GoalStatus.PLANNED,
                    source_event_id="v7-source-event",
                )
                new_context = migrated.goal_report_context(
                    new_goal.goal_id, "migration-project"
                )
                self.assertEqual(new_context.initial_status, GoalStatus.PLANNED)
                self.assertEqual(new_context.source_event_id, "v7-source-event")
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_verification_attestations_survive_store_reopen(self) -> None:
        """Persisted provenance remains attached to its exact evidence fact."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "attestations.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Retain exact verification provenance",
                (SuccessCriterion("tested", "The stored receipt remains trusted"),),
            )
            original, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The runner receipt verified the criterion",
                criterion_id="tested",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "c" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            store.close()

            reopened = CuratorStore(database_path)
            try:
                facts = reopened.list_facts(goal.goal_id, "migration-project")
                self.assertEqual(len(facts), 1)
                self.assertEqual(
                    facts[0].verification_attestations,
                    original.verification_attestations,
                )
                service = CuratorService(
                    reopened,
                    ArtifactPurger(staging),
                    MigrationEvidenceVerifier(),
                    project_id="migration-project",
                )
                self.assertEqual(
                    service.goal_status(goal.goal_id).criteria[0].status,
                    CriterionStatus.VERIFIED,
                )
                self.assertGreater(
                    reopened.goal_fact_capacity(
                        goal.goal_id, "migration-project"
                    ).goal_fact_bytes,
                    0,
                )
            finally:
                reopened.close()

    def test_v7_attestation_migration_preserves_facts_but_fails_legacy_proof_closed(self) -> None:
        """Legacy verification facts migrate without invented trust provenance."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v7.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve verification history without fabricating provenance",
                (SuccessCriterion("tested", "A passing immutable receipt exists"),),
            )
            original, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "A trusted fixture receipt passed before the schema upgrade",
                criterion_id="tested",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "b" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            self.assertEqual(len(original.verification_attestations), 1)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute(
                "ALTER TABLE facts DROP COLUMN verification_attestations_json"
            )
            connection.execute("PRAGMA user_version = 7")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                service = CuratorService(
                    migrated,
                    ArtifactPurger(staging),
                    MigrationEvidenceVerifier(),
                    project_id="migration-project",
                )
                facts = migrated.list_facts(goal.goal_id, "migration-project")
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0].fact_id, original.fact_id)
                self.assertEqual(facts[0].bullet, original.bullet)
                self.assertEqual(facts[0].verification_attestations, ())
                self.assertEqual(
                    service.goal_status(goal.goal_id).criteria[0].status,
                    CriterionStatus.OPEN,
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    attestation_default = connection.execute(
                        "SELECT verification_attestations_json FROM facts WHERE fact_id = ?",
                        (original.fact_id,),
                    ).fetchone()[0]
                    self.assertEqual(attestation_default, "[]")
            finally:
                migrated.close()

    def test_newer_schema_version_is_refused_without_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "future.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("PRAGMA user_version = 99")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)
            finally:
                connection.close()

    def test_v9_database_migrates_hold_release_audit_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v9.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_hold_status")
            for column in (
                "hold_created_at",
                "hold_created_by",
                "hold_released_at",
                "hold_released_by",
                "hold_release_rationale",
            ):
                connection.execute(f"ALTER TABLE purge_targets DROP COLUMN {column}")
            connection.execute(
                "CREATE INDEX purge_targets_hold_status "
                "ON purge_targets(status, retention_hold, receipt_id)"
            )
            connection.execute("PRAGMA user_version = 9")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(purge_targets)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "hold_created_at",
                            "hold_created_by",
                            "hold_released_at",
                            "hold_released_by",
                            "hold_release_rationale",
                        }.issubset(columns)
                    )
                    index_columns = [
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA index_info(purge_targets_hold_status)"
                        ).fetchall()
                    ]
                    self.assertEqual(
                        index_columns,
                        ["status", "retention_hold", "hold_released_at", "receipt_id"],
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v10_database_migrates_durable_project_access_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v10.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP TABLE project_grant_revocations")
            connection.execute("DROP TABLE project_grants")
            connection.execute("DROP TABLE project_registry_audit")
            connection.execute("DROP TABLE project_registry")
            connection.execute("PRAGMA user_version = 10")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    tables = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "project_registry",
                            "project_registry_audit",
                            "project_grants",
                            "project_grant_revocations",
                        }.issubset(tables)
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v10_project_access_migration_rolls_back_and_retries_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v10-failed-access.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP TABLE project_grant_revocations")
            connection.execute("DROP TABLE project_grants")
            connection.execute("DROP TABLE project_registry_audit")
            connection.execute("DROP TABLE project_registry")
            connection.execute(
                "CREATE TABLE project_registry_audit (unexpected TEXT)"
            )
            connection.execute("PRAGMA user_version = 10")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.OperationalError):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 10
                )
                self.assertNotIn("project_registry", tables)
                self.assertIn("project_registry_audit", tables)
                connection.execute("DROP TABLE project_registry_audit")
                connection.commit()
            finally:
                connection.close()

            retried = CuratorStore(database_path)
            try:
                with retried.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    tables = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    self.assertIn("project_registry", tables)
                    self.assertIn("project_grants", tables)
            finally:
                retried.close()

    def test_v8_database_migrates_with_unheld_artifact_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v8.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_hold_status")
            for column in (
                "hold_created_at",
                "hold_created_by",
                "hold_released_at",
                "hold_released_by",
                "hold_release_rationale",
            ):
                connection.execute(f"ALTER TABLE purge_targets DROP COLUMN {column}")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN retention_hold")
            connection.execute("PRAGMA user_version = 8")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(purge_targets)"
                        ).fetchall()
                    }
                    self.assertIn("retention_hold", columns)
                    self.assertTrue(
                        {
                            "hold_created_at",
                            "hold_created_by",
                            "hold_released_at",
                            "hold_released_by",
                            "hold_release_rationale",
                        }.issubset(columns)
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()


if __name__ == "__main__":
    unittest.main()
