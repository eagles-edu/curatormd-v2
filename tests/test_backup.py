"""Backup snapshots and restore-to-new-file recovery behavior."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    FactKind,
    SuccessCriterion,
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
