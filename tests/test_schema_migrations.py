"""Current schema migration regression coverage."""
# pylint: disable=duplicate-code
# Migration cases repeat schema setup across distinct version/failure contracts.

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from migration_test_support import (
    CONTROL_PLANE_USAGE_COLUMNS,
    PROJECT_USAGE_COLUMNS,
)
from curatormd_v2 import (
    ConflictError,
    CuratorStore,
    EventEnvelope,
    GoalStarted,
    SQLITE_SCHEMA_VERSION,
    SuccessCriterion,
)
from curatormd_v2.schema_migrations import (
    apply_schema_migrations,
    migrate_consumer_binding_lifecycle_v33,
    migrate_consumer_reenrollment_v34,
)


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

    def test_v38_migration_adds_attended_event_archive_receipt_fields(self) -> None:
        """Upgrade v38 inboxes without losing receipts or creating partial archive state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v38.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            for name in (
                "event_archive_fields_complete",
                "event_archive_eligibility",
                "event_archive_immutable",
            ):
                connection.execute(f"DROP TRIGGER {name}")
            connection.execute("DROP INDEX event_inbox_archive")
            connection.execute("DROP INDEX event_inbox_active_capacity")
            for column in (
                "archive_reason", "archive_offset", "archive_inventory_sha256",
                "archived_by", "archived_at", "archive_id",
            ):
                connection.execute(f"ALTER TABLE event_inbox DROP COLUMN {column}")
            connection.execute("PRAGMA user_version = 38")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as upgraded:
                    columns = {
                        row["name"]
                        for row in upgraded.execute(
                            "PRAGMA table_info(event_inbox)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "archive_id", "archived_at", "archived_by",
                            "archive_inventory_sha256", "archive_offset", "archive_reason",
                        }.issubset(columns)
                    )
                    self.assertEqual(
                        upgraded.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

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

    def test_v37_migration_adds_nullable_purge_outcome_without_backfill(self) -> None:
        """Keep old terminal results unknown instead of guessing deleted vs absent."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v37.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE purge_targets DROP COLUMN outcome")
            connection.execute(
                """INSERT INTO purge_targets
                   (receipt_id, path, sha256, status, attempts, created_at)
                   VALUES ('legacy-receipt', '/stage/legacy.txt', ?, 'purged', 1, ?)""",
                ("a" * 64, "2026-10-26T00:00:00+00:00"),
            )
            connection.execute("PRAGMA user_version = 37")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        "SELECT status, outcome FROM purge_targets WHERE receipt_id = ?",
                        ("legacy-receipt",),
                    ).fetchone()
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(
                            "UPDATE purge_targets SET outcome = 'guessed' "
                            "WHERE receipt_id = ?",
                            ("legacy-receipt",),
                        )
                self.assertEqual(version, SQLITE_SCHEMA_VERSION)
                self.assertEqual(row["status"], "purged")
                self.assertIsNone(row["outcome"])
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
