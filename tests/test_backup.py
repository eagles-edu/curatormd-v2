"""Backup snapshots and restore-to-new-file recovery behavior."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from store_test_support import temporary_store_database
from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    FactKind,
    SuccessCriterion,
    SQLITE_SCHEMA_VERSION,
    backup_daily,
    backup_database,
    restore_database,
)
from curatormd_v2.events import EventEnvelope, EventInboxStatus, GoalStarted


class DatabaseBackupTests(unittest.TestCase):
    """Exercise consistent, private, and non-overwriting database backups."""

    def test_backup_and_restore_are_consistent_private_and_non_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "live.sqlite3"
            backup_path = root / "backups" / "snapshot.sqlite3"
            restored_path = root / "restore" / "recovered.sqlite3"
            stage = root / "stage"
            stage.mkdir()

            source = CuratorStore(source_path)
            service = CuratorService(
                source,
                ArtifactPurger(stage),
                project_id="backup-project",
            )
            goal = service.goal_start(
                "Preserve recoverable goal state",
                (SuccessCriterion("verified", "A recovery probe passes"),),
            )
            service.goal_fact(goal.goal_id, FactKind.CHANGE, "Before snapshot")
            backup_database(source_path, backup_path)
            service.goal_fact(goal.goal_id, FactKind.CHANGE, "Added after snapshot")
            self.assertEqual(
                [fact.bullet for fact in source.list_facts(goal.goal_id)],
                ["Before snapshot", "Added after snapshot"],
            )

            self.assertEqual(stat.S_IMODE(backup_path.stat().st_mode), 0o600)
            restore_database(backup_path, restored_path)
            self.assertEqual(stat.S_IMODE(restored_path.stat().st_mode), 0o600)

            restored = CuratorStore(restored_path)
            try:
                restored_goal = restored.get_goal(goal.goal_id, "backup-project")
                self.assertEqual(restored_goal.problem, "Preserve recoverable goal state")
                self.assertEqual(
                    [fact.bullet for fact in restored.list_facts(goal.goal_id)],
                    ["Before snapshot"],
                )
            finally:
                restored.close()
                source.close()

            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                backup_database(source_path, backup_path)
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                restore_database(backup_path, restored_path)

    def test_backup_captures_committed_wal_state_while_reader_blocks_checkpoint(self) -> None:
        """The online snapshot includes committed writes despite a held WAL reader."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "live.sqlite3"
            snapshot_path = root / "snapshot.sqlite3"
            stage = root / "stage"
            stage.mkdir()
            source = CuratorStore(source_path)
            service = CuratorService(
                source,
                ArtifactPurger(stage),
                project_id="wal-backup-project",
            )
            goal = service.goal_start(
                "Snapshot around a held reader",
                (SuccessCriterion("saved", "Both committed facts are present"),),
            )
            service.goal_fact(goal.goal_id, FactKind.CHANGE, "Before reader snapshot")

            reader = sqlite3.connect(source_path, isolation_level=None)
            checkpoint = sqlite3.connect(source_path, isolation_level=None)
            try:
                reader.execute("BEGIN")
                initial_count = reader.execute(
                    "SELECT COUNT(*) FROM facts WHERE goal_id = ?", (goal.goal_id,)
                ).fetchone()[0]
                self.assertEqual(initial_count, 1)

                service.goal_fact(goal.goal_id, FactKind.CHANGE, "Committed in WAL")
                checkpoint_result = checkpoint.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                self.assertIsNotNone(checkpoint_result)
                assert checkpoint_result is not None
                self.assertEqual(checkpoint_result[0], 1)

                backup_database(source_path, snapshot_path)
                with CuratorStore(snapshot_path) as snapshot:
                    self.assertEqual(
                        [fact.bullet for fact in snapshot.list_facts(goal.goal_id)],
                        ["Before reader snapshot", "Committed in WAL"],
                    )
                self.assertEqual(
                    reader.execute(
                        "SELECT COUNT(*) FROM facts WHERE goal_id = ?",
                        (goal.goal_id,),
                    ).fetchone()[0],
                    1,
                )
            finally:
                reader.close()
                checkpoint.close()
                source.close()

    def test_corrupt_snapshot_is_rejected_without_creating_restore_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corrupt = root / "corrupt.sqlite3"
            corrupt.write_bytes(b"not a sqlite database")
            corrupt.chmod(0o600)
            destination = root / "restored.sqlite3"

            with self.assertRaises(sqlite3.DatabaseError):
                restore_database(corrupt, destination)

            self.assertFalse(destination.exists())
            self.assertEqual(corrupt.read_bytes(), b"not a sqlite database")
            self.assertEqual(tuple(root.glob(".*.tmp")), ())

    def test_restore_preserves_unsupported_schema_for_isolated_review(self) -> None:
        """A valid future-schema snapshot stays intact and is not activated here."""

        with temporary_store_database() as (root, source):
            future_version = SQLITE_SCHEMA_VERSION + 1
            connection = sqlite3.connect(source)
            connection.execute(f"PRAGMA user_version = {future_version}")
            connection.commit()
            connection.close()

            snapshot = root / "future-snapshot.sqlite3"
            restored = root / "isolated-review.sqlite3"
            backup_database(source, snapshot)
            restore_database(snapshot, restored)

            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                CuratorStore(restored)

            for database in (source, snapshot, restored):
                connection = sqlite3.connect(database)
                try:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        future_version,
                    )
                finally:
                    connection.close()

    def test_concurrent_destination_creation_preserves_winner_and_cleans_temp(self) -> None:
        """A destination race must not overwrite the concurrent file or leak a temp."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.sqlite3"
            source = CuratorStore(source_path)
            source.close()
            destination = root / "backup.sqlite3"
            concurrent_bytes = b"created by the concurrent backup writer"
            original_link = os.link

            def create_destination_then_link(
                source_temp: str | Path, target: str | Path
            ) -> None:
                Path(target).write_bytes(concurrent_bytes)
                original_link(source_temp, target)

            with patch(
                "curatormd_v2.backup.os.link",
                side_effect=create_destination_then_link,
            ):
                with self.assertRaises(FileExistsError):
                    backup_database(source_path, destination)

            self.assertEqual(destination.read_bytes(), concurrent_bytes)
            self.assertEqual(tuple(root.glob(".*.tmp")), ())

    def test_restore_destination_race_preserves_winner_and_cleans_temp(self) -> None:
        """A concurrent restore target must survive verified snapshot installation."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.sqlite3"
            source = CuratorStore(source_path)
            source.close()
            snapshot = root / "snapshot.sqlite3"
            backup_database(source_path, snapshot)

            destination = root / "restored.sqlite3"
            concurrent_bytes = b"created by the concurrent restore writer"
            original_link = os.link

            def create_destination_then_link(
                source_temp: str | Path, target: str | Path
            ) -> None:
                Path(target).write_bytes(concurrent_bytes)
                original_link(source_temp, target)

            with patch(
                "curatormd_v2.backup.os.link",
                side_effect=create_destination_then_link,
            ):
                with self.assertRaises(FileExistsError):
                    restore_database(snapshot, destination)

            self.assertEqual(destination.read_bytes(), concurrent_bytes)
            self.assertTrue(snapshot.is_file())
            self.assertEqual(tuple(root.glob(".*.tmp")), ())

    def test_backup_of_processed_event_contains_receipt_not_source_envelope(self) -> None:
        """Successful event backups retain the digest receipt, not raw JSON."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "live.sqlite3"
            backup_path = root / "backup.sqlite3"
            restored_path = root / "restored.sqlite3"
            stage = root / "stage"
            stage.mkdir()

            source = CuratorStore(source_path)
            service = CuratorService(
                source,
                ArtifactPurger(stage),
                project_id="backup-project",
            )
            event = EventEnvelope(
                "backup-event",
                "backup-project",
                GoalStarted(
                    "backup-goal",
                    "Compact event envelope source text",
                    (SuccessCriterion("verified", "Backup preserves the receipt"),),
                ),
            )
            receipt = service.process_event(event)
            self.assertEqual(receipt.status, EventInboxStatus.PROCESSED)

            backup_database(source_path, backup_path)

            self.assertNotIn(event.to_json().encode("utf-8"), backup_path.read_bytes())
            restore_database(backup_path, restored_path)
            restored = CuratorStore(restored_path)
            try:
                restored_receipt = restored.event_receipt(
                    "backup-project", "backup-event"
                )
                self.assertEqual(restored_receipt.status, EventInboxStatus.PROCESSED)
                self.assertEqual(
                    restored_receipt.payload_sha256,
                    receipt.payload_sha256,
                )
                with restored.transaction() as connection:
                    row = connection.execute(
                        "SELECT payload_json, payload_bytes FROM event_inbox "
                        "WHERE project_id = ? AND event_id = ?",
                        ("backup-project", "backup-event"),
                    ).fetchone()
                self.assertIsNone(row["payload_json"])
                self.assertEqual(row["payload_bytes"], len(event.to_json().encode("utf-8")))
            finally:
                restored.close()
                source.close()

    def test_backup_and_restore_preserve_retry_and_quarantine_payloads(self) -> None:
        """Approved daily backups retain payloads needed for inbox recovery."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "live.sqlite3"
            backup_path = root / "backup.sqlite3"
            restored_path = root / "restored.sqlite3"
            source = CuratorStore(source_path)
            retry_event = EventEnvelope(
                "retry-event", "backup-project",
                GoalStarted(
                    "retry-goal", "Recover a failed local event",
                    (SuccessCriterion("retried", "Retain the retry envelope"),),
                ),
            )
            quarantine_event = EventEnvelope(
                "quarantine-event", "backup-project",
                GoalStarted(
                    "quarantine-goal", "Recover an exhausted local event",
                    (SuccessCriterion("reviewed", "Retain the quarantine envelope"),),
                ),
            )
            try:
                receipt, created = source.ingest_event(retry_event)
                self.assertTrue(created)
                failed = source.mark_event_failed(
                    "backup-project", "retry-event", "temporary_adapter_error"
                )
                self.assertEqual(failed.status, EventInboxStatus.FAILED)
                self.assertEqual(receipt.event_id, failed.event_id)
                source.ingest_event(quarantine_event)
                source.mark_event_failed(
                    "backup-project", "quarantine-event", "temporary_adapter_error"
                )
                quarantined = source.quarantine_event(
                    "backup-project", "quarantine-event", max_attempts=1
                )
                self.assertEqual(quarantined.status, EventInboxStatus.QUARANTINED)

                backup_database(source_path, backup_path)
                restore_database(backup_path, restored_path)

                with CuratorStore(restored_path) as restored:
                    with restored.transaction() as connection:
                        rows = connection.execute(
                            "SELECT payload_json FROM event_inbox "
                            "WHERE project_id = ? ORDER BY event_id",
                            ("backup-project",),
                        ).fetchall()
                    restored_receipts = {
                        event_id: restored.event_receipt("backup-project", event_id)
                        for event_id in ("retry-event", "quarantine-event")
                    }
                    self.assertEqual(
                        restored_receipts["retry-event"].status,
                        EventInboxStatus.FAILED,
                    )
                    self.assertEqual(
                        restored_receipts["quarantine-event"].status,
                        EventInboxStatus.QUARANTINED,
                    )
                    self.assertEqual(
                        {row["payload_json"] for row in rows},
                        {retry_event.to_json(), quarantine_event.to_json()},
                    )
            finally:
                source.close()

    def test_symlink_sources_and_destinations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "source.sqlite3"
            database = CuratorStore(database_path)
            database.close()
            alias = root / "alias.sqlite3"
            alias.symlink_to(database_path)

            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                backup_database(alias, root / "backup.sqlite3")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                backup_database(database_path, alias)

    def test_daily_backup_keeps_seven_verified_copies_and_prunes_after_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "state" / "curator.sqlite3"
            backup_directory = database_path.parent / "backups"
            database = CuratorStore(database_path)
            database.close()
            backup_day = date(2026, 10, 1)

            for offset in range(8):
                current_day = backup_day + timedelta(days=offset)
                backup_daily(database_path, backup_directory, today=current_day)

            retained = sorted(
                path.name for path in backup_directory.glob("curator-v2-*.sqlite3")
            )
            self.assertEqual(len(retained), 7)
            self.assertEqual(
                retained,
                [
                    f"curator-v2-{(backup_day + timedelta(days=offset)).isoformat()}.sqlite3"
                    for offset in range(1, 8)
                ],
            )
            self.assertFalse(
                (backup_directory / f"curator-v2-{backup_day.isoformat()}.sqlite3").exists()
            )
            self.assertEqual(stat.S_IMODE(backup_directory.stat().st_mode), 0o700)
            unrelated = backup_directory / "keep-this-note.txt"
            unrelated.write_text("not a Curator backup", encoding="utf-8")

            today_path = backup_directory / retained[-1]
            before = today_path.read_bytes()
            backup_daily(database_path, backup_directory, today=backup_day + timedelta(days=7))
            self.assertEqual(today_path.read_bytes(), before)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "not a Curator backup")

            with patch(
                "curatormd_v2.backup.backup_database",
                side_effect=sqlite3.OperationalError("injected backup failure"),
            ):
                with self.assertRaises(sqlite3.OperationalError):
                    backup_daily(
                        database_path,
                        backup_directory,
                        today=backup_day + timedelta(days=8),
                    )
            self.assertEqual(
                sorted(path.name for path in backup_directory.glob("curator-v2-*.sqlite3")),
                retained,
            )
