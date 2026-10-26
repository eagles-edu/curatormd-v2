"""Legacy migrations and unversioned database upgrades."""
# pylint: disable=duplicate-code
# Migration cases repeat schema setup across distinct version/failure contracts.

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from migration_test_support import (
    LegacySchemaMigrationSupport,
    MigrationEvidenceVerifier,
    MigrationReviewAuthorizer,
)
from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    EventEnvelope,
    FactKind,
    GoalStarted,
    SQLITE_SCHEMA_VERSION,
    SuccessCriterion,
)


class LegacyBaseMigrationTests(LegacySchemaMigrationSupport):
    """Exercise the selected legacy migration contracts."""

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
