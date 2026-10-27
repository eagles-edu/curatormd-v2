"""Non-overwriting SQLite backup and restore command tests."""

from __future__ import annotations

import json
from pathlib import Path
import stat
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from store_test_support import temporary_store_database
from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    FactKind,
    SuccessCriterion,
)
from curatormd_v2.storage_cli import main


class StorageCliTests(unittest.TestCase):
    """Keep CLI recovery explicit, verified, and isolated to new files."""

    def test_backup_and_restore_round_trip_to_new_private_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            source = root / "source.sqlite3"
            backup = root / "backups" / "snapshot.sqlite3"
            restored = root / "review" / "restored.sqlite3"
            store = CuratorStore(source)
            try:
                service = CuratorService(
                    store, ArtifactPurger(stage), project_id="storage-cli-project"
                )
                goal = service.goal_start(
                    "Verify isolated CLI restore",
                    (SuccessCriterion("recover", "The goal survives restoration"),),
                )
                service.goal_fact(goal.goal_id, FactKind.CHANGE, "Snapshot fact")
            finally:
                store.close()

            backup_output = StringIO()
            backup_errors = StringIO()
            self.assertEqual(
                main(
                    [
                        "backup",
                        "--database",
                        str(source),
                        "--destination",
                        str(backup),
                    ],
                    stdout=backup_output,
                    stderr=backup_errors,
                ),
                0,
            )
            self.assertEqual(backup_errors.getvalue(), "")
            self.assertEqual(
                json.loads(backup_output.getvalue()),
                {"operation": "backup", "status": "verified"},
            )

            restore_output = StringIO()
            restore_errors = StringIO()
            self.assertEqual(
                main(
                    [
                        "restore",
                        "--backup",
                        str(backup),
                        "--destination",
                        str(restored),
                        "--restore-to-new-path",
                    ],
                    stdout=restore_output,
                    stderr=restore_errors,
                ),
                0,
            )
            self.assertEqual(restore_errors.getvalue(), "")
            self.assertEqual(
                json.loads(restore_output.getvalue()),
                {"operation": "restore", "status": "verified"},
            )
            self.assertNotIn(str(source), backup_output.getvalue())
            self.assertNotIn(str(restored), restore_output.getvalue())
            self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o600)

            recovered = CuratorStore(restored)
            try:
                self.assertEqual(
                    recovered.get_goal(goal.goal_id, "storage-cli-project").problem,
                    "Verify isolated CLI restore",
                )
                self.assertEqual(
                    [fact.bullet for fact in recovered.list_facts(goal.goal_id)],
                    ["Snapshot fact"],
                )
            finally:
                recovered.close()

    def test_restore_requires_explicit_new_path_confirmation(self) -> None:
        output = StringIO()
        errors = StringIO()
        with patch("curatormd_v2.storage_cli.restore_database") as restore:
            result = main(
                [
                    "restore",
                    "--backup",
                    "/tmp/backup.sqlite3",
                    "--destination",
                    "/tmp/review.sqlite3",
                ],
                stdout=output,
                stderr=errors,
            )

        self.assertEqual(result, 2)
        self.assertIn("--restore-to-new-path", errors.getvalue())
        restore.assert_not_called()

    def test_failed_backup_does_not_echo_source_or_exception_details(self) -> None:
        canary = "PRIVATE_DATABASE_PATH_CANARY"
        output = StringIO()
        errors = StringIO()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.sqlite3"
            destination = Path(temporary) / "backup.sqlite3"
            with patch(
                "curatormd_v2.storage_cli.backup_database",
                side_effect=OSError(canary),
            ):
                result = main(
                    [
                        "backup",
                        "--database",
                        str(source),
                        "--destination",
                        str(destination),
                    ],
                    stdout=output,
                    stderr=errors,
                )

        self.assertEqual(result, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("source, destination, or database error", errors.getvalue())
        self.assertNotIn(canary, errors.getvalue())
        self.assertNotIn(str(source), errors.getvalue())

    def test_existing_destination_is_preserved(self) -> None:
        with temporary_store_database() as (root, source):
            destination = root / "backup.sqlite3"
            sentinel = b"existing backup must be retained"
            destination.write_bytes(sentinel)
            errors = StringIO()

            result = main(
                [
                    "backup",
                    "--database",
                    str(source),
                    "--destination",
                    str(destination),
                ],
                stderr=errors,
            )

            self.assertEqual(result, 2)
            self.assertEqual(destination.read_bytes(), sentinel)
            self.assertIn("storage failed", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
