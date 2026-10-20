"""Repository config and reference project-plugin boundary tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import io
import os
from pathlib import Path
import stat
import tempfile
import time
import tracemalloc
import unittest
from threading import Event, Lock
from typing import BinaryIO, cast
from unittest.mock import patch

from project_fixtures import create_consumer_repo

from curatormd_v2 import CuratorStore, SuccessCriterion
from curatormd_v2.events import EventEnvelope, GoalStarted
from curatormd_v2.project_config import (
    CONFIG_FILENAME,
    PROJECT_PLUGIN_API_VERSION,
    ProjectConfig,
    ProjectConfigError,
)
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import ConflictError
from curatormd_v2.testing import assert_goal_started_event_contract


class ProjectPluginTests(unittest.TestCase):
    """Verify strict repo-local config and project-bound service access."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(self.temporary) / "consumer"
        create_consumer_repo(self.root)
        self.stage = self.root / ".curatormd-v2" / "staging"
        (self.root / "docs" / "tasks.md").write_text("- [ ] Example task\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        self.write_config()
        self.store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(self.store.close)

    def test_due_purge_scheduler_uses_exclusive_staging_lock(self) -> None:
        """Serialize scheduled deletes against project plugin staging writes."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        probe_fd = os.open(self.stage, os.O_RDONLY | os.O_DIRECTORY)

        def assert_staging_locked(limit: int) -> tuple[()]:
            self.assertEqual(limit, 9)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return ()

        try:
            with patch.object(
                plugin.service,
                "retry_due_purges",
                side_effect=assert_staging_locked,
            ) as retry:
                self.assertEqual(plugin.retry_due_purges(9), ())
            retry.assert_called_once_with(9)
        finally:
            os.close(probe_fd)

    def write_config(self, content: str | None = None) -> None:
        """Write a minimal, valid repository-local config fixture."""

        config = content or """\
            schema_version = 1
            backend_api_version = 1
            project_id = "consumer-a"

            [scope]
            read_paths = ["src", "docs"]

            [checklists]
            tasks = "docs/tasks.md"

            [evidence]
            adapters = []

            [staging]
            root = ".curatormd-v2/staging"

            [persistence]
            targets = ["persistence/HISTORY.md"]
            """
        (self.root / CONFIG_FILENAME).write_text(config)
        (self.root / CONFIG_FILENAME).chmod(0o600)

    @staticmethod
    def _goal(plugin: ProjectPlugin, goal_id: str):
        """Create a scoped goal that owns a fixture staging directory."""

        return plugin.service.goal_start(
            f"Exercise staging scope {goal_id}",
            (SuccessCriterion("verified", "The staging scope is isolated"),),
            goal_id=goal_id,
        )

    def test_valid_config_binds_only_existing_scoped_paths(self) -> None:
        """Load project identity, checklist, staging, and Markdown targets."""

        config = ProjectConfig.load(self.root)

        self.assertEqual(config.backend_api_version, PROJECT_PLUGIN_API_VERSION)
        self.assertEqual(config.project_id, "consumer-a")
        self.assertEqual(
            config.config_sha256,
            hashlib.sha256(
                (self.root / CONFIG_FILENAME).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(len(config.repository_fingerprint), 64)
        self.assertEqual(config.checklist_path("tasks"), self.root / "docs/tasks.md")
        self.assertEqual(config.staging_root, self.stage)
        self.assertEqual(
            config.persistence_targets,
            (self.root / "persistence/HISTORY.md",),
        )
        self.assertIsNone(config.staging_max_project_bytes)
        self.assertIsNone(config.staging_max_project_files)
        with self.assertRaisesRegex(ProjectConfigError, "outside configured read scope"):
            config.resolve_read_path("persistence/HISTORY.md")
        with self.assertRaisesRegex(ProjectConfigError, "not configured"):
            config.checklist_path("unknown")

    def test_invalid_toml_error_does_not_retain_config_source(self) -> None:
        """Sanitized TOML failures must not retain raw configuration text."""

        self.write_config('project_id = "PRIVATE_CONFIG_CANARY\n')
        with self.assertRaisesRegex(ProjectConfigError, "valid UTF-8 TOML") as raised:
            ProjectConfig.load(self.root)
        self.assertNotIn("PRIVATE_CONFIG_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_missing_config_path_error_does_not_echo_untrusted_path(self) -> None:
        """Path resolution errors must not expose a configured filesystem path."""

        self.write_config(
            self._valid_config().replace(
                'tasks = "docs/tasks.md"', 'tasks = "PRIVATE_PATH_CANARY"'
            )
        )
        with self.assertRaisesRegex(ProjectConfigError, "does not exist") as raised:
            ProjectConfig.load(self.root)
        self.assertNotIn("PRIVATE_PATH_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_checklist_utf8_error_does_not_retain_source(self) -> None:
        """Checklist decode failures must not retain the source bytes."""

        config = ProjectConfig.load(self.root)
        (self.root / "docs" / "tasks.md").write_bytes(
            b"PRIVATE_CHECKLIST_CANARY\xff"
        )
        with self.assertRaisesRegex(ProjectConfigError, "bounded UTF-8") as raised:
            config.checklist_snapshot("tasks", "- [ ] Example task")
        self.assertNotIn("PRIVATE_CHECKLIST_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_published_project_config_fixture_loads(self) -> None:
        """Accept the checked-in config example in a matching consumer repo."""

        (self.root / "tests").mkdir()
        (self.root / "docs" / "implementation-checklist.md").write_text(
            "- [ ] Implement the consumer integration\n", encoding="utf-8"
        )
        (self.root / "persistence" / "LESSONS-LEARNED.md").write_text(
            "# Lessons\n", encoding="utf-8"
        )
        example = (
            Path(__file__).resolve().parents[1]
            / "docs/examples/curatormd-v2.toml"
        ).read_text(encoding="utf-8")
        self.write_config(example)

        config = ProjectConfig.load(self.root)

        self.assertEqual(config.project_id, "example-project")
        self.assertEqual(
            config.checklist_path("implementation"),
            self.root / "docs/implementation-checklist.md",
        )
        self.assertEqual(len(config.persistence_targets), 2)
        self.assertEqual(config.staging_root, self.stage)

    def test_project_staging_budgets_are_optional_bounded_integers(self) -> None:
        """Consumer config may opt into finite project-wide staging limits."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        configured = base.replace(
            'root = ".curatormd-v2/staging"',
            'root = ".curatormd-v2/staging"\n'
            "max_project_bytes = 4096\n"
            "max_project_files = 25",
        )
        self.write_config(configured)
        config = ProjectConfig.load(self.root)
        self.assertEqual(config.staging_max_project_bytes, 4096)
        self.assertEqual(config.staging_max_project_files, 25)

        for invalid in ("true", "0", "1099511627777"):
            updated = configured.replace(
                "max_project_bytes = 4096", f"max_project_bytes = {invalid}"
            )
            self.write_config(
                updated
            )
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ProjectConfigError, "staging.max_project_bytes"
            ):
                ProjectConfig.load(self.root)

    def test_reference_plugin_creates_checklist_goal_in_its_project_only(self) -> None:
        """Bind a repo config to the shared store with strict project scoping."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal = plugin.goal_start_from_checklist(
            "tasks",
            "Implement the linked task",
            (SuccessCriterion("done", "Task is verified"),),
            exact_item_text="- [ ] Example task",
            next_action="Inspect the linked implementation files",
        )

        self.assertEqual(goal.project_id, "consumer-a")
        stored = plugin.goal_status(goal.goal_id).goal
        self.assertEqual(stored.checklist_id, "tasks")
        self.assertEqual(stored.checklist_source_text, "- [ ] Example task")
        self.assertEqual(stored.next_action, "Inspect the linked implementation files")
        self.assertTrue((stored.checklist_version or "").startswith("sha256:"))
        original_version = stored.checklist_version
        (self.root / "docs" / "tasks.md").write_text("- [x] Example task\n")
        self.assertEqual(
            plugin.goal_status(goal.goal_id).goal.checklist_version, original_version
        )
        with self.assertRaisesRegex(ProjectConfigError, "exact source line"):
            plugin.goal_start_from_checklist(
                "tasks",
                "Not on the checklist",
                (SuccessCriterion("done", "Task is verified"),),
                exact_item_text="- [ ] Not the source",
            )
        self.assertEqual(len(plugin.goal_list()), 1)
        with self.assertRaises(ProjectConfigError):
            ProjectPlugin(
                config,
                plugin.service.__class__(
                    self.store,
                    plugin.service.purger,
                    project_id="other-project",
                ),
            )

    def test_request_and_accepted_subtask_intake_preserve_explicit_criteria(self) -> None:
        """Create request and child goals without deriving success criteria."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        parent_criteria = (
            SuccessCriterion("intake", "The supplied request criteria are retained"),
        )
        parent = plugin.goal_start_from_request(
            "Implement the explicitly requested feature",
            parent_criteria,
            owner="user-1",
            next_action="Break the accepted request into bounded child work",
        )
        child_criteria = (
            SuccessCriterion("child-test", "The isolated child test passes"),
        )
        child = plugin.goal_start_subtask(
            parent.goal_id,
            "Add the isolated regression test",
            child_criteria,
            owner="agent-1",
        )

        self.assertEqual(parent.success_criteria, parent_criteria)
        self.assertEqual(
            plugin.goal_status(parent.goal_id).goal.next_action,
            "Break the accepted request into bounded child work",
        )
        self.assertEqual(child.success_criteria, child_criteria)
        self.assertEqual(child.parent_goal_id, parent.goal_id)
        self.assertEqual(plugin.goal_status(child.goal_id).goal.parent_goal_id, parent.goal_id)
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_from_request("Criteria must be explicit", ())
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_subtask(parent.goal_id, "No implicit criteria", ())

    def test_checklist_event_intake_rejects_forged_snapshot_and_allows_exact_retry(self) -> None:
        """Bind event-based checklist starts to the configured current source."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        version, source_text = plugin.config.checklist_snapshot(
            "tasks", "- [ ] Example task"
        )
        payload = GoalStarted(
            goal_id="checklist-event-goal",
            problem="Complete the selected checklist task",
            success_criteria=(SuccessCriterion("verified", "The task is verified"),),
            checklist_id="tasks",
            checklist_version=version,
            checklist_source_text=source_text,
        )
        event = EventEnvelope(
            event_id="checklist-event-1",
            project_id="consumer-a",
            source_id="test-producer",
            payload=payload,
        )
        accepted = plugin.process_event(event)
        self.assertEqual(accepted.status.value, "processed")

        # A completed event retry remains idempotent after checklist evolution.
        (self.root / "docs" / "tasks.md").write_text("- [x] Example task\n")
        self.assertEqual(plugin.process_event(event), accepted)

        forged = EventEnvelope(
            event_id="checklist-event-forged",
            project_id="consumer-a",
            source_id="test-producer",
            payload=GoalStarted(
                goal_id="forged-checklist-goal",
                problem="Pretend a checklist line was selected",
                success_criteria=(SuccessCriterion("verified", "The task is verified"),),
                checklist_id="tasks",
                checklist_version=version,
                checklist_source_text="- [ ] Not an actual checklist row",
            ),
        )
        with self.assertRaisesRegex(ProjectConfigError, "exact source line"):
            plugin.process_event(forged)
        self.assertEqual([item.goal.goal_id for item in plugin.goal_list()], [payload.goal_id])

    def test_reusable_producer_backend_contract_assertions(self) -> None:
        """Exercise the importable contract helper against the reference plugin."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        event = EventEnvelope(
            event_id="shared-contract-event-1",
            project_id="consumer-a",
            source_id="contract-test-producer",
            source_sequence=1,
            payload=GoalStarted(
                goal_id="shared-contract-goal-1",
                problem="Preserve producer supplied goal contract fields",
                success_criteria=(
                    SuccessCriterion("persisted", "All supplied fields are retained"),
                ),
                owner="contract-test-owner",
                next_action="Verify the consumer implementation",
            ),
        )

        evidence = assert_goal_started_event_contract(
            plugin,
            event,
            expected_project_id="consumer-a",
        )

        self.assertEqual(evidence.project_id, "consumer-a")
        self.assertEqual(evidence.event_id, event.event_id)
        self.assertEqual(evidence.event_payload_bytes_retained, 0)
        self.assertGreaterEqual(
            evidence.event_payload_bytes_received,
            evidence.event_payload_bytes,
        )

    def test_storage_usage_scans_sizes_without_following_staging_symlinks(self) -> None:
        """Measure nested regular files, but expose a skipped link as incomplete."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        nested = self.stage / "nested"
        nested.mkdir(parents=True)
        (nested / "small.bin").write_bytes(b"12345")
        outside = Path(self.temporary) / "outside.bin"
        outside.write_bytes(b"must not count or be followed")
        (self.stage / "escape").symlink_to(outside)

        usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.regular_file_count, 1)
        self.assertEqual(usage.observed_file_bytes, 5)
        self.assertEqual(usage.directory_count, 1)
        self.assertEqual(usage.symlink_count, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "symlink_skipped")

    def test_storage_usage_marks_a_bounded_partial_scan_incomplete(self) -> None:
        """Stop after the configured entry ceiling and report partial results."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "first.bin").write_bytes(b"a")
        (self.stage / "second.bin").write_bytes(b"bb")

        with patch("curatormd_v2.project_plugin.MAX_STAGING_SCAN_ENTRIES", 1):
            usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.entries_scanned, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "entry_limit")

    def test_storage_usage_attributes_bytes_to_fixed_temporary_classes(self) -> None:
        """Attribute repository staging totals without exposing artifact names."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "goal-classes" / "cue").mkdir(parents=True)
        (self.stage / "goal-classes" / "cue" / "a.bin").write_bytes(b"123")
        (self.stage / "goal-classes" / "raw-chat" / "nested").mkdir(parents=True)
        (self.stage / "goal-classes" / "raw-chat" / "nested" / "b.bin").write_bytes(
            b"12345"
        )
        (self.stage / "legacy-root-file.bin").write_bytes(b"12")

        usage = plugin.storage_usage().staging

        assert usage is not None
        by_class = {item.artifact_class.value: item for item in usage.classes}
        self.assertEqual(usage.regular_file_count, 3)
        self.assertEqual(usage.observed_file_bytes, 10)
        self.assertEqual(by_class["cue"].regular_file_count, 1)
        self.assertEqual(by_class["cue"].observed_file_bytes, 3)
        self.assertEqual(by_class["raw-chat"].regular_file_count, 1)
        self.assertEqual(by_class["raw-chat"].observed_file_bytes, 5)
        self.assertEqual(by_class["other"].regular_file_count, 1)
        self.assertEqual(by_class["other"].observed_file_bytes, 2)
        self.assertTrue(usage.inventory_complete)

    def test_discover_staging_artifacts_streams_hashes_and_returns_exact_paths(self) -> None:
        """Hash regular files in scope while omitting no-follow symlinks."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "scan-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        nested = goal_stage / "nested"
        nested.mkdir(parents=True)
        artifact = nested / "cue.json"
        artifact.write_bytes(b'{"temporary":true}')
        outside = Path(self.temporary) / "outside.json"
        outside.write_bytes(b"outside")
        (goal_stage / "escape.json").symlink_to(outside)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "symlink_skipped")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.scope_goal_id, goal_id)
        self.assertEqual(len(inventory.artifacts), 1)
        self.assertEqual(inventory.artifacts[0].path, str(artifact))
        self.assertEqual(
            inventory.artifacts[0].sha256,
            hashlib.sha256(b'{"temporary":true}').hexdigest(),
        )

    def test_discovery_includes_temporary_artifact_classes_and_duplicates(self) -> None:
        """Inventory each temporary class, retaining same-content file paths."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "classes-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        artifact_files = {
            "raw-chat/session.jsonl": b"temporary chat bytes",
            "cue/event.json": b"cue bytes",
            "import/source.md": b"import bytes",
            "scratch/work.tmp": b"scratch bytes",
            "generated/intermediate.json": b"intermediate bytes",
            "duplicates/copy.tmp": b"scratch bytes",
        }
        for relative_path, contents in artifact_files.items():
            path = goal_stage / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNotNone(inventory.manifest_sha256)
        self.assertEqual(
            {Path(item.path).relative_to(goal_stage).as_posix() for item in inventory.artifacts},
            set(artifact_files),
        )
        scratch_hashes = {
            item.sha256
            for item in inventory.artifacts
            if Path(item.path).relative_to(goal_stage).as_posix()
            in {"scratch/work.tmp", "duplicates/copy.tmp"}
        }
        self.assertEqual(scratch_hashes, {hashlib.sha256(b"scratch bytes").hexdigest()})

    def test_discovery_hash_byte_limit_returns_no_false_complete_manifest(self) -> None:
        """Do not hash past the configured byte budget or claim completeness."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "limit-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        goal_stage.mkdir()
        (goal_stage / "too-large.tmp").write_bytes(b"0123456789")

        with patch("curatormd_v2.project_plugin.MAX_STAGING_HASH_BYTES", 5):
            inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "hash_byte_limit")
        self.assertEqual(inventory.artifacts, ())
        self.assertIsNone(inventory.manifest_sha256)

    def test_stage_artifact_streams_to_atomic_goal_scoped_file(self) -> None:
        """The producer API writes bounded temporary bytes and returns only a digest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-goal"
        self._goal(plugin, goal_id)
        payload = b"temporary cue payload"

        artifact = plugin.stage_artifact(
            goal_id, "cue", "event-1", io.BytesIO(payload)
        )

        self.assertEqual(
            Path(artifact.path),
            self.stage / goal_id / "cue" / "event-1.bin",
        )
        self.assertEqual(artifact.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(Path(artifact.path).read_bytes(), payload)
        self.assertEqual(stat.S_IMODE(Path(artifact.path).stat().st_mode), 0o600)
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, (artifact,))

    def test_large_import_staging_uses_bounded_python_memory(self) -> None:
        """A large producer stream is copied in bounded chunks, not buffered whole."""

        class GeneratedStream:
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

        with patch("curatormd_v2.project_plugin.MAX_STAGED_ARTIFACT_BYTES", 4):
            with self.assertRaisesRegex(ConflictError, "per-file byte ceiling"):
                plugin.stage_artifact(
                    goal_id, "cue", "too-large", io.BytesIO(b"12345")
                )
        self.assertFalse((self.stage / goal_id / "cue" / "too-large.bin").exists())

        first = plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"first"))
        with self.assertRaises(FileExistsError):
            plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"second"))
        self.assertEqual(Path(first.path).read_bytes(), b"first")
        self.assertFalse(any(path.name.endswith(".partial") for path in self.stage.rglob("*")))

    def test_project_staging_budgets_block_excess_without_deleting(self) -> None:
        """Budgeted staging fails closed and reports limits without auto-purge."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\n'
                "max_project_bytes = 5\n"
                "max_project_files = 10",
            )
        )
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "budget-goal"
        self._goal(plugin, goal_id)
        first = plugin.stage_artifact(goal_id, "cue", "first", io.BytesIO(b"1234"))
        # A distinct goal can hit the byte limit during streaming; its partial
        # file is removed and the already-staged artifact is untouched.
        second_goal = "budget-bytes"
        self._goal(plugin, second_goal)
        with self.assertRaisesRegex(ConflictError, "project staging byte budget"):
            plugin.stage_artifact(second_goal, "cue", "too-large", io.BytesIO(b"12"))

        usage = plugin.storage_usage()
        self.assertEqual(usage.staging_project_byte_limit, 5)
        self.assertEqual(usage.staging_project_file_limit, 10)
        self.assertTrue(Path(first.path).is_file())
        self.assertFalse((self.stage / second_goal / "cue" / "too-large.bin").exists())
        self.assertFalse(any(path.name.endswith(".partial") for path in self.stage.rglob("*")))

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
        file_limited = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        file_goal = "file-budget"
        self._goal(file_limited, file_goal)
        file_limited.stage_artifact(file_goal, "cue", "first", io.BytesIO(b"a"))
        with self.assertRaisesRegex(ConflictError, "project staging file-count budget"):
            file_limited.stage_artifact(file_goal, "cue", "second", io.BytesIO(b"b"))

    def test_project_staging_budget_requires_complete_project_inventory(self) -> None:
        """Do not claim quota enforcement if skipped staging entries exist."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\nmax_project_files = 10',
            )
        )
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
        lock_call_guard = Lock()
        lock_calls = 0
        original_flock = fcntl.flock

        class PausingStream(io.BytesIO):
            """Hold a staged write open while another operation requests a lock."""

            def read(self, size: int | None = -1) -> bytes:
                read_entered.set()
                if not allow_read.wait(timeout=5):
                    raise TimeoutError("test did not release the producer stream")
                return super().read(size)

        stream = PausingStream(b"complete artifact bytes")

        def tracked_flock(descriptor: int, operation: int) -> None:
            nonlocal lock_calls
            if operation == fcntl.LOCK_EX:
                with lock_call_guard:
                    lock_calls += 1
                    if lock_calls == 2:
                        contending_lock_attempted.set()
            original_flock(descriptor, operation)

        def discover():
            return plugin.discover_staging_artifacts(goal_id)

        with patch("curatormd_v2.project_plugin.fcntl.flock", tracked_flock):
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
        project_b = ProjectPlugin.bind(ProjectConfig.load(root_b), self.store)

        goal_a = project_a.goal_start_from_checklist(
            "tasks",
            "Project A task",
            (SuccessCriterion("a", "A is done"),),
            exact_item_text="- [ ] Example task",
        )
        goal_b = project_b.goal_start_from_checklist(
            "tasks",
            "Project B task",
            (SuccessCriterion("b", "B is done"),),
            exact_item_text="- [ ] Separate task",
        )

        self.assertEqual([item.goal.goal_id for item in project_a.goal_list()], [goal_a.goal_id])
        self.assertEqual([item.goal.goal_id for item in project_b.goal_list()], [goal_b.goal_id])
        with self.assertRaises(LookupError):
            project_b.goal_status(goal_a.goal_id)

        projection_a = project_a.persist_goal(
            goal_a.goal_id, "persistence/HISTORY.md"
        )
        projection_b = project_b.persist_goal(
            goal_b.goal_id, "persistence/HISTORY.md"
        )
        history_a = (self.root / "persistence/HISTORY.md").read_text(
            encoding="utf-8"
        )
        history_b = (root_b / "persistence/HISTORY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(projection_a.project_id, "consumer-a")
        self.assertEqual(projection_b.project_id, "consumer-b")
        self.assertIn(goal_a.goal_id, history_a)
        self.assertNotIn(goal_b.goal_id, history_a)
        self.assertIn(goal_b.goal_id, history_b)
        self.assertNotIn(goal_a.goal_id, history_b)
        with self.assertRaises(LookupError):
            project_b.persist_goal(goal_a.goal_id, "persistence/HISTORY.md")

    @staticmethod
    def write_config_at(root: Path, content: str) -> None:
        """Write a fixture config in the requested consumer repository."""

        (root / CONFIG_FILENAME).write_text(content)
        (root / CONFIG_FILENAME).chmod(0o600)

    def test_rejects_path_traversal_symlinks_unknown_fields_and_unknown_adapters(self) -> None:
        """Reject unsafe scope, config extensions, and unregistered adapters."""

        traversal = self._valid_config().replace('"src", "docs"', '"../"')
        self.write_config(traversal)
        with self.assertRaises(ProjectConfigError):
            ProjectConfig.load(self.root)

        unknown = self._valid_config().replace(
            'project_id = "consumer-a"',
            'project_id = "consumer-a"\nbackend_database = "./db.sqlite3"',
        )
        self.write_config(unknown)
        with self.assertRaisesRegex(ProjectConfigError, "invalid config fields"):
            ProjectConfig.load(self.root)

        self.write_config()
        adapter = self._valid_config().replace("adapters = []", 'adapters = ["git"]')
        self.write_config(adapter)
        with self.assertRaisesRegex(ProjectConfigError, "unregistered evidence"):
            ProjectConfig.load(self.root)
        self.assertEqual(
            ProjectConfig.load(
                self.root, registered_evidence_adapters=frozenset({"git"})
            ).evidence_adapters,
            ("git",),
        )

    def test_action_adapters_are_read_only_by_default_and_require_opt_in(self) -> None:
        """Actions require both repository allowlisting and host registration."""

        default_config = ProjectConfig.load(self.root)
        self.assertEqual(default_config.action_adapters, ())

        self.write_config(
            self._valid_config()
            + '\n[actions]\nadapters = ["approved-runner"]\n'
        )
        with self.assertRaisesRegex(ProjectConfigError, "unregistered action"):
            ProjectConfig.load(self.root)

        opted_in = ProjectConfig.load(
            self.root,
            registered_action_adapters=frozenset({"approved-runner"}),
        )
        self.assertEqual(opted_in.action_adapters, ("approved-runner",))

        self.write_config()
        outside = Path(self.temporary) / "outside"
        outside.mkdir()
        (self.root / "src" / "escape").symlink_to(outside, target_is_directory=True)
        self.write_config(self._valid_config().replace('"src", "docs"', '"src/escape"'))
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            ProjectConfig.load(self.root)

    def test_rejects_persistence_escape_and_oversized_config(self) -> None:
        """Constrain Markdown destinations and configuration resource use."""

        escaped_target = self._valid_config().replace(
            '"persistence/HISTORY.md"', '"../outside.md"'
        )
        self.write_config(escaped_target)
        with self.assertRaisesRegex(ProjectConfigError, "escape"):
            ProjectConfig.load(self.root)

        self.write_config(self._valid_config() + "\n#" + ("x" * 17_000))
        with self.assertRaisesRegex(ProjectConfigError, "exceeds"):
            ProjectConfig.load(self.root)

    def test_rejects_config_file_symlink(self) -> None:
        """Do not follow a config path outside the consumer repository."""

        external = Path(self.temporary) / "external-config.toml"
        external.write_text(self._valid_config())
        config_path = self.root / CONFIG_FILENAME
        config_path.unlink()
        config_path.symlink_to(external)

        with self.assertRaisesRegex(ProjectConfigError, "missing regular project config"):
            ProjectConfig.load(self.root)

    def test_rejects_config_owned_by_another_account(self) -> None:
        """Require the config to share the repository root's trusted owner."""

        repository_uid = self.root.stat().st_uid
        other_owner = os.stat_result(
            (stat.S_IFREG | 0o644, 1, 1, 1, repository_uid + 1, 1, 1, 1, 1, 1)
        )
        with patch("curatormd_v2.project_config.os.fstat", return_value=other_owner):
            with self.assertRaisesRegex(ProjectConfigError, "owner must match"):
                ProjectConfig.load(self.root)

    def test_rejects_group_or_world_writable_config(self) -> None:
        """Prevent another local account from silently replacing plugin policy."""

        (self.root / CONFIG_FILENAME).chmod(0o666)
        with self.assertRaisesRegex(ProjectConfigError, "must not be group- or world-writable"):
            ProjectConfig.load(self.root)

    def test_rejects_unsupported_backend_contract_version(self) -> None:
        """Refuse a config declaring a backend contract this runtime cannot honor."""

        self.write_config(
            self._valid_config().replace("backend_api_version = 1", "backend_api_version = 2")
        )
        with self.assertRaisesRegex(ProjectConfigError, "backend_api_version is not supported"):
            ProjectConfig.load(self.root)

    def test_rejects_secret_like_config_values_without_echoing_them(self) -> None:
        """Do not allow recognizable credentials in otherwise valid config fields."""

        secret = "sk-" + "A" * 24
        self.write_config(
            self._valid_config().replace('project_id = "consumer-a"', f'project_id = "{secret}"')
        )
        with self.assertRaises(ProjectConfigError) as captured:
            ProjectConfig.load(self.root)
        self.assertNotIn(secret, str(captured.exception))

    def test_rechecks_checklist_and_staging_paths_at_use_time(self) -> None:
        """Catch symlink swaps made after the initial config validation."""

        config = ProjectConfig.load(self.root)
        external = Path(self.temporary) / "outside.md"
        external.write_text("outside scope\n")
        checklist = self.root / "docs" / "tasks.md"
        checklist.unlink()
        checklist.symlink_to(external)
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            config.checklist_path("tasks")

        checklist.unlink()
        checklist.write_text("- [ ] Restored task\n")
        moved_stage = self.root / ".curatormd-v2" / "staging-original"
        self.stage.rename(moved_stage)
        self.stage.symlink_to(Path(self.temporary), target_is_directory=True)
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            ProjectPlugin.bind(config, self.store)

    def _valid_config(self) -> str:
        """Return the same valid TOML fixture used by setup."""

        return (self.root / CONFIG_FILENAME).read_text()


if __name__ == "__main__":
    unittest.main()
