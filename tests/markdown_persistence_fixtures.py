"""Shared setup for canonical Markdown persistence tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from project_fixtures import create_consumer_repo

from curatormd_v2 import (
    ChecklistGoalStartRequest,
    CuratorStore,
    ProjectPlugin,
    ProjectRegistrationRequest,
    SuccessCriterion,
)
from curatormd_v2.project_config import ProjectConfig


class MarkdownPersistenceFixture(unittest.TestCase):  # pylint: disable=too-few-public-methods
    """Create one disposable consumer and bound plugin for persistence tests."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        base = Path(self.temporary)
        self.root = create_consumer_repo(base / "consumer")
        (self.root / "docs" / "tasks.md").write_text("- [ ] Implement adapter\n")
        self.target = self.root / "persistence" / "HISTORY.md"
        self.target.write_text("# Existing project history\n\nKeep this text.\n")
        (self.root / ".curatormd-v2.toml").write_text(
            """\
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
        )
        (self.root / ".curatormd-v2.toml").chmod(0o600)
        self.config = ProjectConfig.load(self.root)
        self.store = CuratorStore(base / "global.sqlite3")
        self.addCleanup(self.store.close)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                self.config, "Register the Markdown persistence test project"
            ),
            "test-admin",
        )
        self.plugin = ProjectPlugin.bind(self.config, self.store)
        self.goal = self.plugin.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Implement the canonical Markdown projection",
                success_criteria=(
                    SuccessCriterion(
                        "write", "A scoped goal is written as compact bullets"
                    ),
                ),
                exact_item_text="- [ ] Implement adapter",
            )
        )

    def _create_other_repo(self) -> Path:
        """Create a separately configured consumer for project-isolation tests."""

        root = create_consumer_repo(Path(self.temporary) / "other-consumer")
        (root / "docs" / "tasks.md").write_text("- [ ] Other task\n")
        (root / "persistence" / "HISTORY.md").write_text("# Other history\n")
        (root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "consumer-b"

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
        )
        (root / ".curatormd-v2.toml").chmod(0o600)
        return root
