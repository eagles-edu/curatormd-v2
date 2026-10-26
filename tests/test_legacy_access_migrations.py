"""Legacy project access and compatibility migrations."""
# pylint: disable=duplicate-code
# Migration cases repeat schema setup across distinct version/failure contracts.

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from migration_test_support import LegacySchemaMigrationSupport
from curatormd_v2 import CuratorStore, SQLITE_SCHEMA_VERSION


class LegacyAccessMigrationTests(LegacySchemaMigrationSupport):
    """Exercise the selected legacy migration contracts."""

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
