"""Focused project-plugin configuration and intake tests."""

from __future__ import annotations

import fcntl
import hashlib
import os
import sys
from pathlib import Path
from typing import cast
from unittest.mock import patch

from project_plugin_test_support import ProjectPluginTestSupport

from curatormd_v2 import (
    ChecklistGoalStartRequest,
    GoalStartOptions,
    GoalSubtaskStartRequest,
    ProjectStatusChangeRequest,
    SuccessCriterion,
)
from curatormd_v2.events import EventEnvelope, GoalStarted
from curatormd_v2.project_config import (
    CONFIG_FILENAME,
    PROJECT_PLUGIN_API_VERSION,
    ProjectConfig,
    ProjectConfigError,
    _sensitive_config_category,  # pyright: ignore[reportPrivateUsage]  # Direct traversal regression.
)
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import NotFoundError


class ProjectPluginConfigAndIntakeTests(ProjectPluginTestSupport):
    """Exercise project-plugin configuration and intake behavior."""

    def test_due_purge_scheduler_uses_exclusive_staging_lock(self) -> None:
        """Serialize scheduled deletes against project plugin staging writes."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
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

    def test_staging_open_error_does_not_retain_private_path(self) -> None:
        """Sanitized staging failures do not chain filesystem path details."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        private_path = "/srv/private/customer/staging"
        with patch(
            "curatormd_v2.project_plugin.os.open",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            with self.assertRaisesRegex(
                ProjectConfigError, "staging root cannot be opened safely"
            ) as raised:
                plugin.retry_due_purges(9)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_valid_config_binds_only_existing_scoped_paths(self) -> None:
        """Load project identity, checklist, staging, and Markdown targets."""

        config = ProjectConfig.load(self.root)

        self.assertEqual(config.backend_api_version, PROJECT_PLUGIN_API_VERSION)
        self.assertEqual(config.project_id, "consumer-a")
        self.assertEqual(
            config.config_sha256,
            hashlib.sha256((self.root / CONFIG_FILENAME).read_bytes()).hexdigest(),
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
        with self.assertRaisesRegex(
            ProjectConfigError, "outside configured read scope"
        ):
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

    def test_sensitive_config_error_does_not_retain_credential_value(self) -> None:
        """Credential rejection keeps safe metadata out of retained frames."""

        secret = "PRIVATE_CONFIG_CANARY_7f91a3"
        config = self._valid_config().replace(
            'project_id = "consumer-a"',
            f'project_id = "token={secret}"',
        )
        self.write_config(config)

        caught: ProjectConfigError | None = None
        try:
            ProjectConfig.load(self.root)
        except ProjectConfigError as exc:
            caught = exc

        self.assertIsNotNone(caught)
        error = cast(ProjectConfigError, caught)
        self.assertIn(
            "sensitive content rejected in project config value",
            str(error),
        )
        self.assertNotIn(secret, str(error))
        self.assertIn("credential_assignment", str(error))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        tb = error.__traceback__
        load_frames: list[dict[str, object]] = []
        while tb is not None:
            if tb.tb_frame.f_code.co_name == "load":
                load_frames.append(cast(dict[str, object], tb.tb_frame.f_locals))
            tb = tb.tb_next
        self.assertEqual(len(load_frames), 1)
        self.assertNotIn("root_table", load_frames[0])
        self.assertNotIn(secret, repr(load_frames[0]))

    def test_sensitive_config_scan_handles_deep_nesting(self) -> None:
        """Scan deeply nested TOML values without consuming Python call depth."""

        safe_value: object = "ordinary bounded value"
        sensitive_value: object = "token=private-test-canary"
        for _ in range(sys.getrecursionlimit() + 32):
            safe_value = [safe_value]
            sensitive_value = [sensitive_value]

        self.assertIsNone(_sensitive_config_category(safe_value))
        self.assertEqual(
            _sensitive_config_category(sensitive_value),
            "credential_assignment",
        )

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
        (self.root / "docs" / "tasks.md").write_bytes(b"PRIVATE_CHECKLIST_CANARY\xff")
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
            Path(__file__).resolve().parents[1] / "docs/examples/curatormd-v2.toml"
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
            self.write_config(updated)
            with (
                self.subTest(invalid=invalid),
                self.assertRaisesRegex(ProjectConfigError, "staging.max_project_bytes"),
            ):
                ProjectConfig.load(self.root)

    def test_reference_plugin_creates_checklist_goal_in_its_project_only(self) -> None:
        """Bind a repo config to the shared store with strict project scoping."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal = plugin.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Implement the linked task",
                success_criteria=(SuccessCriterion("done", "Task is verified"),),
                exact_item_text="- [ ] Example task",
                options=GoalStartOptions(
                    next_action="Inspect the linked implementation files"
                ),
            )
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
                ChecklistGoalStartRequest(
                    checklist_id="tasks",
                    problem="Not on the checklist",
                    success_criteria=(SuccessCriterion("done", "Task is verified"),),
                    exact_item_text="- [ ] Not the source",
                )
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

    def test_request_and_accepted_subtask_intake_preserve_explicit_criteria(
        self,
    ) -> None:
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
            GoalSubtaskStartRequest(
                parent_goal_id=parent.goal_id,
                problem="Add the isolated regression test",
                success_criteria=child_criteria,
                owner="agent-1",
            )
        )

        self.assertEqual(parent.success_criteria, parent_criteria)
        self.assertEqual(
            plugin.goal_status(parent.goal_id).goal.next_action,
            "Break the accepted request into bounded child work",
        )
        self.assertEqual(child.success_criteria, child_criteria)
        self.assertEqual(child.parent_goal_id, parent.goal_id)
        self.assertEqual(
            plugin.goal_status(child.goal_id).goal.parent_goal_id, parent.goal_id
        )
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_from_request("Criteria must be explicit", ())
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_subtask(
                GoalSubtaskStartRequest(
                    parent_goal_id=parent.goal_id,
                    problem="No implicit criteria",
                    success_criteria=(),
                )
            )

    def test_checklist_event_intake_rejects_forged_snapshot_and_allows_exact_retry(
        self,
    ) -> None:
        """Bind event-based checklist starts to the configured current source."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
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
                success_criteria=(
                    SuccessCriterion("verified", "The task is verified"),
                ),
                checklist_id="tasks",
                checklist_version=version,
                checklist_source_text="- [ ] Not an actual checklist row",
            ),
        )
        with self.assertRaisesRegex(ProjectConfigError, "exact source line"):
            plugin.process_event(forged)
        self.assertEqual(
            [item.goal.goal_id for item in plugin.goal_list()], [payload.goal_id]
        )

    def test_direct_plugin_event_and_stage_writes_are_fenced_after_suspension(
        self,
    ) -> None:
        """Direct reference-plugin writes cannot bypass project suspension."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "direct-plugin-suspended-stage-goal"
        self._goal(plugin, goal_id)
        self.store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Suspend before direct plugin event processing",
                expected_revision=1,
                transition_id="direct-plugin-suspend-1",
            ),
            "test-admin",
        )
        event = EventEnvelope(
            event_id="direct-plugin-suspended-event",
            project_id=config.project_id,
            source_id="direct-plugin-test",
            payload=GoalStarted(
                goal_id="direct-plugin-suspended-goal",
                problem="Prove suspended plugin writes are fenced",
                success_criteria=(
                    SuccessCriterion("denied", "No event receipt is created"),
                ),
            ),
        )

        self._assert_suspended_start_event_and_stage_denied(plugin, goal_id, event)
        self._assert_suspended_service_effects_denied(plugin, goal_id)
        with self.assertRaises(NotFoundError):
            self.store.event_receipt(config.project_id, event.event_id)
        self.assertEqual([item.goal.goal_id for item in plugin.goal_list()], [goal_id])
        self.assertFalse((self.stage / goal_id).exists())
