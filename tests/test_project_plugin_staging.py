"""Focused tests for project-plugin staging."""

from __future__ import annotations

import errno
import hashlib
import io
import os
import sqlite3
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import BinaryIO, IO, Self, cast
from unittest.mock import patch

from project_plugin_test_support import (
    CountingStagingLock,
    PausingStream,
    ProjectPluginTestSupport,
)

from curatormd_v2 import (
    ChecklistGoalStartRequest,
    ProjectRegistrationRequest,
    SuccessCriterion,
)
from curatormd_v2.project_config import CONFIG_FILENAME, ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import ConflictError


class ProjectPluginStagingTests(ProjectPluginTestSupport):
    """Exercise project-plugin staging behavior."""

    def test_producer_api_stages_every_supported_temporary_artifact_class(self) -> None:
        """Inventory every temporary class after publication through the producer API."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "all-producer-classes-goal"
        self._goal(plugin, goal_id)
        classes = (
            "raw-chat",
            "cue",
            "import",
            "scratch",
            "generated",
            "duplicate",
        )
        payloads = {
            artifact_class: io.BytesIO(b"same temporary bytes")
            for artifact_class in classes
        }

        published = {
            artifact_class: plugin.stage_artifact(
                goal_id, artifact_class, f"artifact-{index}", payload
            )
            for index, (artifact_class, payload) in enumerate(payloads.items())
        }
        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNotNone(inventory.manifest_sha256)
        self.assertEqual(
            {Path(item.path).parent.name for item in inventory.artifacts},
            set(classes),
        )
        self.assertEqual(set(inventory.artifacts), set(published.values()))
        self.assertEqual(
            {item.sha256 for item in inventory.artifacts},
            {hashlib.sha256(b"same temporary bytes").hexdigest()},
        )

    def test_large_import_staging_uses_bounded_python_memory(self) -> None:
        """A large producer stream is copied in bounded chunks, not buffered whole."""

        # Stream fixture exposes only the required bounded `read` interface.
        class GeneratedStream:  # pylint: disable=too-few-public-methods
            """Generate a repeatable source without retaining the complete payload."""

            def __init__(self, total_bytes: int) -> None:
                self.remaining = total_bytes
                self.max_read_size = 0

            def read(self, size: int = -1) -> bytes:
                """Return one bounded chunk from the generated fixture input."""

                if size < 0 or size > 64 * 1024:
                    raise AssertionError("staging must request at most a 64 KiB chunk")
                self.max_read_size = max(self.max_read_size, size)
                chunk_size = min(size, self.remaining)
                self.remaining -= chunk_size
                return b"i" * chunk_size

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "large-import-goal"
        self._goal(plugin, goal_id)
        total_bytes = 24 * 1024 * 1024
        generated = GeneratedStream(total_bytes)

        tracemalloc.start()
        try:
            artifact = plugin.stage_artifact(
                goal_id, "import", "large-import", cast(BinaryIO, generated)
            )
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        expected_digest = hashlib.sha256()
        chunk = b"i" * (64 * 1024)
        for _ in range(total_bytes // len(chunk)):
            expected_digest.update(chunk)
        self.assertEqual(generated.remaining, 0)
        self.assertLessEqual(generated.max_read_size, 64 * 1024)
        self.assertEqual(Path(artifact.path).stat().st_size, total_bytes)
        self.assertEqual(artifact.sha256, expected_digest.hexdigest())
        self.assertLess(peak_bytes, 4 * 1024 * 1024)

    def test_stage_artifact_rejects_unsafe_names_oversize_and_overwrite(self) -> None:
        """Writes reject path injection, oversize streams, and artifact replacement."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-limits"
        self._goal(plugin, goal_id)
        with self.assertRaisesRegex(ValueError, "artifact_class"):
            plugin.stage_artifact(goal_id, "../outside", "safe", io.BytesIO(b"x"))
        with self.assertRaisesRegex(ValueError, "artifact_id"):
            plugin.stage_artifact(goal_id, "cue", "../outside", io.BytesIO(b"x"))

        with patch("curatormd_v2.project_plugin_staging.MAX_STAGED_ARTIFACT_BYTES", 4):
            with self.assertRaisesRegex(ConflictError, "per-file byte ceiling"):
                plugin.stage_artifact(goal_id, "cue", "too-large", io.BytesIO(b"12345"))
        self.assertFalse((self.stage / goal_id / "cue" / "too-large.bin").exists())

        first = plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"first"))
        with self.assertRaises(FileExistsError):
            plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"second"))
        self.assertEqual(Path(first.path).read_bytes(), b"first")
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.stage.rglob("*"))
        )

    def test_file_sync_failure_removes_partial_and_never_publishes(self) -> None:
        """A failed file sync leaves neither a final artifact nor a partial."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "file-sync-failure"
        self._goal(plugin, goal_id)

        with patch(
            "curatormd_v2.staging_write.os.fsync",
            side_effect=OSError("injected file sync failure"),
        ):
            with self.assertRaisesRegex(OSError, "injected file sync failure"):
                plugin.stage_artifact(
                    goal_id, "scratch", "not-published", io.BytesIO(b"payload")
                )

        goal_directory = self.stage / goal_id / "scratch"
        self.assertFalse((goal_directory / "not-published.bin").exists())
        self.assertEqual(
            tuple(path for path in goal_directory.iterdir() if path.is_file()), ()
        )
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, ())

    def test_enospc_during_partial_write_removes_temporary_artifact(self) -> None:
        """A storage-full write leaves no final file or staging fragment."""

        class ExhaustedWriter:
            """Write a prefix, then simulate the filesystem running out of space."""

            def __init__(self, stream: IO[bytes]) -> None:
                self.stream = stream

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object) -> None:
                self.stream.close()

            def write(self, content: bytes) -> int:
                self.stream.write(content[:2])
                self.stream.flush()
                raise OSError(errno.ENOSPC, "injected storage exhaustion")

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "write-enospc"
        self._goal(plugin, goal_id)
        original_fdopen = os.fdopen

        def fdopen_then_exhaust(fd: int, mode: str) -> BinaryIO:
            return cast(BinaryIO, ExhaustedWriter(original_fdopen(fd, mode)))

        with patch(
            "curatormd_v2.staging_write.os.fdopen", side_effect=fdopen_then_exhaust
        ):
            with self.assertRaisesRegex(OSError, "injected storage exhaustion"):
                plugin.stage_artifact(
                    goal_id, "scratch", "out-of-space", io.BytesIO(b"payload")
                )

        goal_directory = self.stage / goal_id / "scratch"
        self.assertEqual(tuple(goal_directory.iterdir()), ())
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, ())

    def test_short_write_is_rejected_before_publication(self) -> None:
        """A partial byte count cannot be acknowledged with the full digest."""

        class ShortWriter:
            """Return a partial byte count after writing a temporary prefix."""

            def __init__(self, stream: IO[bytes]) -> None:
                self.stream = stream

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object) -> None:
                self.stream.close()

            def write(self, content: bytes) -> int:
                partial = content[:2]
                self.stream.write(partial)
                self.stream.flush()
                return len(partial)

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "short-write"
        self._goal(plugin, goal_id)
        original_fdopen = os.fdopen

        def fdopen_short_write(fd: int, mode: str) -> BinaryIO:
            return cast(BinaryIO, ShortWriter(original_fdopen(fd, mode)))

        with patch(
            "curatormd_v2.staging_write.os.fdopen", side_effect=fdopen_short_write
        ):
            with self.assertRaisesRegex(OSError, "short write while staging"):
                plugin.stage_artifact(
                    goal_id, "scratch", "partial", io.BytesIO(b"payload")
                )

        goal_directory = self.stage / goal_id / "scratch"
        self.assertEqual(tuple(goal_directory.iterdir()), ())
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, ())

    def test_directory_sync_failure_is_unacknowledged_but_recoverable_by_inventory(
        self,
    ) -> None:
        """Inventory the exact published file after its directory sync fails."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "directory-sync-failure"
        self._goal(plugin, goal_id)

        with patch(
            "curatormd_v2.staging_write.os.fsync",
            side_effect=[None, OSError("injected directory sync failure")],
        ):
            with self.assertRaisesRegex(OSError, "injected directory sync failure"):
                plugin.stage_artifact(
                    goal_id, "scratch", "uncertain", io.BytesIO(b"complete payload")
                )

        final_path = self.stage / goal_id / "scratch" / "uncertain.bin"
        self.assertEqual(final_path.read_bytes(), b"complete payload")
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.stage.rglob("*"))
        )

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(len(inventory.artifacts), 1)
        self.assertEqual(inventory.artifacts[0].path, str(final_path))
        self.assertEqual(
            inventory.artifacts[0].sha256,
            hashlib.sha256(b"complete payload").hexdigest(),
        )
        timestamp_before = self.store.staging_artifact_times(
            plugin.config.project_id, inventory.artifacts
        )
        self.assertEqual(timestamp_before, {})

        retry = plugin.stage_artifact(
            goal_id, "scratch", "uncertain", io.BytesIO(b"complete payload")
        )

        self.assertEqual(retry.path, inventory.artifacts[0].path)
        self.assertEqual(retry.device_id, inventory.artifacts[0].device_id)
        self.assertEqual(retry.inode_id, inventory.artifacts[0].inode_id)
        self.assertEqual(retry.occurrence_id, inventory.artifacts[0].occurrence_id)
        after_retry = plugin.discover_staging_artifacts(goal_id)
        timestamp_after = self.store.staging_artifact_times(
            plugin.config.project_id, after_retry.artifacts
        )
        self.assertEqual(set(timestamp_after), {str(final_path)})
        repeated_retry = plugin.stage_artifact(
            goal_id, "scratch", "uncertain", io.BytesIO(b"complete payload")
        )
        self.assertEqual(repeated_retry.occurrence_id, retry.occurrence_id)
        repeated_inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertEqual(
            self.store.staging_artifact_times(
                plugin.config.project_id, repeated_inventory.artifacts
            ),
            timestamp_after,
        )
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.stage.rglob("*"))
        )

    def test_staging_age_receipt_failure_removes_published_file(self) -> None:
        """Undo publication when its durable age receipt cannot be written."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "age-receipt-failure"
        self._goal(plugin, goal_id)

        with patch.object(
            self.store,
            "record_staging_artifact_time",
            side_effect=sqlite3.OperationalError("injected metadata write failure"),
        ):
            with self.assertRaisesRegex(
                sqlite3.OperationalError, "injected metadata write failure"
            ):
                plugin.stage_artifact(
                    goal_id, "scratch", "not-recorded", io.BytesIO(b"payload")
                )

        goal_directory = self.stage / goal_id / "scratch"
        self.assertFalse((goal_directory / "not-recorded.bin").exists())
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.stage.rglob("*"))
        )
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, ())

    def test_project_staging_byte_threshold_warns_without_blocking_or_deleting(self) -> None:
        """The project byte threshold is advisory; writes remain bounded per goal."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\n'
                "max_project_bytes = 5\n"
                "max_project_files = 10",
            )
        )
        self._register_project("Update the project staging budget fixture")
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "budget-goal"
        self._goal(plugin, goal_id)
        first = plugin.stage_artifact(goal_id, "cue", "first", io.BytesIO(b"1234"))
        # A distinct goal can exceed the project warning threshold. Per-goal
        # hard limits still apply, and no staged artifact is removed.
        second_goal = "budget-bytes"
        self._goal(plugin, second_goal)
        second = plugin.stage_artifact(
            second_goal, "cue", "above-threshold", io.BytesIO(b"12")
        )

        usage = plugin.storage_usage()
        self.assertEqual(usage.staging_project_byte_limit, 5)
        self.assertEqual(usage.staging_project_file_limit, 10)
        self.assertTrue(Path(first.path).is_file())
        self.assertTrue(Path(second.path).is_file())
        staging = usage.staging
        self.assertIsNotNone(staging)
        assert staging is not None
        self.assertGreater(staging.observed_file_bytes, 5)
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.stage.rglob("*"))
        )

        # A separate consumer-selected staging root demonstrates the file cap.
        second_root = self.root / ".curatormd-v2" / "staging-files"
        second_root.mkdir()
        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        base = base.replace("max_project_bytes = 5\n", "").replace(
            "max_project_files = 10\n", ""
        )
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging-files"\nmax_project_files = 1',
            )
        )
        self._register_project("Update the project file budget fixture")
        file_limited = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        file_goal = "file-budget"
        self._goal(file_limited, file_goal)
        file_limited.stage_artifact(file_goal, "cue", "first", io.BytesIO(b"a"))
        file_limited.stage_artifact(file_goal, "cue", "second", io.BytesIO(b"b"))
        self.assertEqual(len(file_limited.discover_staging_artifacts(file_goal).artifacts), 2)

    def test_exact_staging_retry_and_new_paths_work_above_project_threshold(self) -> None:
        """Thresholds allow new writes and preserve exact retry semantics."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        (self.root / ".curatormd-v2" / "staging-retry-bytes").mkdir()
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging-retry-bytes"\n'
                "max_project_bytes = 4\n"
                "max_project_files = 2",
            )
        )
        self._register_project("Set staging retry byte-cap fixture")
        byte_limited = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        byte_goal = "budget-byte-retry"
        self._goal(byte_limited, byte_goal)
        first = byte_limited.stage_artifact(
            byte_goal, "cue", "same", io.BytesIO(b"data")
        )
        retry = byte_limited.stage_artifact(
            byte_goal, "cue", "same", io.BytesIO(b"data")
        )
        self.assertEqual(retry.occurrence_id, first.occurrence_id)
        with self.assertRaisesRegex(FileExistsError, "already in use"):
            byte_limited.stage_artifact(
                byte_goal, "cue", "same", io.BytesIO(b"else")
            )
        self.assertEqual(Path(first.path).read_bytes(), b"data")
        byte_limited.stage_artifact(byte_goal, "cue", "new", io.BytesIO(b"x"))

        (self.root / ".curatormd-v2" / "staging-retry-files").mkdir()
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging-retry-files"\n'
                "max_project_bytes = 10\n"
                "max_project_files = 1",
            )
        )
        self._register_project("Set staging retry file-cap fixture")
        file_limited = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        file_goal = "budget-file-retry"
        self._goal(file_limited, file_goal)
        first_file = file_limited.stage_artifact(
            file_goal, "cue", "same", io.BytesIO(b"x")
        )
        retry_file = file_limited.stage_artifact(
            file_goal, "cue", "same", io.BytesIO(b"x")
        )
        self.assertEqual(retry_file.occurrence_id, first_file.occurrence_id)
        file_limited.stage_artifact(file_goal, "cue", "new", io.BytesIO(b"y"))
        self.assertFalse(
            any(path.name.endswith(".partial") for path in self.root.rglob("*"))
        )

    def test_project_staging_budget_requires_complete_project_inventory(self) -> None:
        """Do not write against an incomplete inventory used for warning status."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\nmax_project_files = 10',
            )
        )
        self._register_project("Update the incomplete inventory fixture")
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "incomplete-budget"
        self._goal(plugin, goal_id)
        outside = Path(self.temporary) / "outside-budget.bin"
        outside.write_bytes(b"unaccounted")
        (self.stage / "skipped-link").symlink_to(outside)

        with self.assertRaisesRegex(ConflictError, "incomplete inventory"):
            plugin.stage_artifact(goal_id, "cue", "blocked", io.BytesIO(b"x"))
        self.assertFalse((self.stage / goal_id / "cue" / "blocked.bin").exists())

    def test_inventory_waits_for_plugin_writer_atomic_publication(self) -> None:
        """A concurrent review scan cannot adopt an in-progress partial file."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-race"
        self._goal(plugin, goal_id)
        read_entered = Event()
        allow_read = Event()
        contending_lock_attempted = Event()
        stream = PausingStream(b"complete artifact bytes", read_entered, allow_read)
        tracked_staging_lock = CountingStagingLock(
            getattr(plugin, "_locked_staging_root"), contending_lock_attempted
        )

        def discover():
            return plugin.discover_staging_artifacts(goal_id)

        with patch.object(plugin, "_locked_staging_root", tracked_staging_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                writer = pool.submit(
                    plugin.stage_artifact,
                    goal_id,
                    "cue",
                    "atomic",
                    stream,
                )
                self.assertTrue(read_entered.wait(timeout=2))
                review_scan = pool.submit(discover)
                self.assertTrue(contending_lock_attempted.wait(timeout=2))
                time.sleep(0.05)
                self.assertFalse(review_scan.done())
                allow_read.set()
                artifact = writer.result(timeout=2)
                inventory = review_scan.result(timeout=2)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, (artifact,))
        self.assertEqual(Path(artifact.path).read_bytes(), b"complete artifact bytes")

    def test_staging_manifests_are_isolated_by_goal(self) -> None:
        """One goal's approved manifest cannot include another goal's files."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        self._goal(plugin, "goal-alpha")
        self._goal(plugin, "goal-beta")
        alpha = self.stage / "goal-alpha"
        beta = self.stage / "goal-beta"
        alpha.mkdir()
        beta.mkdir()
        alpha_file = alpha / "raw-event.json"
        beta_file = beta / "raw-event.json"
        alpha_file.write_bytes(b"alpha temporary artifact")
        beta_file.write_bytes(b"beta temporary artifact")

        alpha_inventory = plugin.discover_staging_artifacts("goal-alpha")
        beta_inventory = plugin.discover_staging_artifacts("goal-beta")

        self.assertTrue(alpha_inventory.usage.inventory_complete)
        self.assertTrue(beta_inventory.usage.inventory_complete)
        self.assertEqual(alpha_inventory.scope_goal_id, "goal-alpha")
        self.assertEqual(beta_inventory.scope_goal_id, "goal-beta")
        self.assertEqual(
            tuple(item.path for item in alpha_inventory.artifacts),
            (str(alpha_file),),
        )
        self.assertEqual(
            tuple(item.path for item in beta_inventory.artifacts),
            (str(beta_file),),
        )

    def test_project_inventory_includes_orphaned_goal_directories(self) -> None:
        """A project snapshot covers every class and orphaned goal directories."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        self._goal(plugin, "goal-alpha")
        self._goal(plugin, "goal-beta")
        artifacts = {
            "raw-chat": self.stage / "goal-alpha" / "raw-chat" / "raw.bin",
            "cue": self.stage / "goal-alpha" / "cue" / "cue.bin",
            "import": self.stage / "goal-beta" / "import" / "import.bin",
            "scratch": self.stage / "goal-beta" / "scratch" / "scratch.bin",
            "generated": self.stage / "goal-alpha" / "generated" / "generated.bin",
            "duplicate": self.stage / "orphaned-goal" / "duplicate" / "duplicate.bin",
            "other": self.stage / "orphaned-goal" / "unrecognized" / "other.bin",
        }
        for artifact_class, artifact in artifacts.items():
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(artifact_class.encode())

        inventory = plugin.discover_project_staging_artifacts()

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNone(inventory.scope_goal_id)
        self.assertEqual(inventory.usage.regular_file_count, len(artifacts))
        self.assertEqual(
            {item.path for item in inventory.artifacts},
            {str(artifact) for artifact in artifacts.values()},
        )
        self.assertEqual(
            {item.artifact_class.value for item in inventory.usage.classes},
            {"raw-chat", "cue", "import", "scratch", "generated", "duplicate", "other"},
        )
        self.assertEqual(len(inventory.manifest_sha256 or ""), 64)

    def test_goal_staging_scope_does_not_follow_a_symlink(self) -> None:
        """Reject a goal directory replaced by a symlink outside the staging root."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "symlink-goal"
        self._goal(plugin, goal_id)
        outside = Path(self.temporary) / "outside-stage"
        outside.mkdir()
        (outside / "must-remain.json").write_bytes(b"outside scope")
        (self.stage / goal_id).symlink_to(outside, target_is_directory=True)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "scope_unavailable")
        self.assertEqual(inventory.artifacts, ())
        self.assertEqual(inventory.scope_goal_id, goal_id)

    def test_staging_enumeration_permission_error_is_incomplete_and_private(
        self,
    ) -> None:
        """Do not turn an unreadable directory into a complete empty manifest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "scan-permission-goal"
        self._goal(plugin, goal_id)
        plugin.stage_artifact(
            goal_id, "scratch", "private", io.BytesIO(b"private contents")
        )
        private_path = "/srv/private/customer/staging"

        with patch(
            "curatormd_v2.staging_scan.os.scandir",
            side_effect=PermissionError(f"cannot enumerate {private_path}"),
        ):
            inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "permission_denied")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.artifacts, ())
        self.assertNotIn(private_path, repr(inventory))

    def test_missing_goal_staging_directory_is_a_scoped_empty_manifest(self) -> None:
        """A goal with no staged files has an explicit, complete empty manifest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "empty-stage-goal"
        self._goal(plugin, goal_id)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.regular_file_count, 0)
        self.assertEqual(inventory.artifacts, ())
        self.assertEqual(inventory.scope_goal_id, goal_id)
        self.assertEqual(inventory.manifest_sha256, hashlib.sha256(b"[]").hexdigest())

    def test_two_repository_plugins_share_backend_without_sharing_goals(self) -> None:
        """Keep each plugin's config and goals isolated in one global store."""

        project_a = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        root_b = Path(self.temporary) / "consumer-b"
        root_b.mkdir()
        (root_b / ".git").mkdir()
        (root_b / "src").mkdir()
        (root_b / "docs").mkdir()
        (root_b / "persistence").mkdir()
        (root_b / ".curatormd-v2" / "staging").mkdir(parents=True)
        (root_b / "docs" / "tasks.md").write_text("- [ ] Separate task\n")
        (root_b / "persistence" / "HISTORY.md").write_text("# B history\n")
        config_b = self._valid_config().replace(
            'project_id = "consumer-a"', 'project_id = "consumer-b"'
        )
        self.write_config_at(root_b, config_b)
        config_b = ProjectConfig.load(root_b)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config_b, "Register the second isolated plugin fixture"
            ),
            "test-admin",
        )
        project_b = ProjectPlugin.bind(config_b, self.store)

        goal_a = project_a.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Project A task",
                success_criteria=(SuccessCriterion("a", "A is done"),),
                exact_item_text="- [ ] Example task",
            )
        )
        goal_b = project_b.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Project B task",
                success_criteria=(SuccessCriterion("b", "B is done"),),
                exact_item_text="- [ ] Separate task",
            )
        )

        artifact_a = (
            self.root
            / ".curatormd-v2"
            / "staging"
            / goal_a.goal_id
            / "import"
            / "project-a-only.bin"
        )
        artifact_a.parent.mkdir(parents=True)
        artifact_a.write_bytes(b"project-a-private-artifact")

        self.assertEqual(
            [item.goal.goal_id for item in project_a.goal_list()], [goal_a.goal_id]
        )
        self.assertEqual(
            [item.goal.goal_id for item in project_b.goal_list()], [goal_b.goal_id]
        )
        with self.assertRaises(LookupError):
            project_b.goal_status(goal_a.goal_id)
        with self.assertRaises(LookupError):
            project_b.discover_staging_artifacts(goal_a.goal_id)
        project_inventory_b = project_b.discover_project_staging_artifacts()
        self.assertTrue(project_inventory_b.usage.inventory_complete)
        self.assertNotIn(
            str(artifact_a), {item.path for item in project_inventory_b.artifacts}
        )

        projection_a = project_a.persist_goal(goal_a.goal_id, "persistence/HISTORY.md")
        projection_b = project_b.persist_goal(goal_b.goal_id, "persistence/HISTORY.md")
        history_a = (self.root / "persistence/HISTORY.md").read_text(encoding="utf-8")
        history_b = (root_b / "persistence/HISTORY.md").read_text(encoding="utf-8")

        self.assertEqual(projection_a.project_id, "consumer-a")
        self.assertEqual(projection_b.project_id, "consumer-b")
        self.assertIn(goal_a.goal_id, history_a)
        self.assertNotIn(goal_b.goal_id, history_a)
        self.assertIn(goal_b.goal_id, history_b)
        self.assertNotIn(goal_a.goal_id, history_b)
        with self.assertRaises(LookupError):
            project_b.persist_goal(goal_a.goal_id, "persistence/HISTORY.md")
