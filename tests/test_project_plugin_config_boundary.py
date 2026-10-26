"""Focused project-plugin configuration boundary tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

from project_plugin_test_support import ProjectPluginTestSupport

from curatormd_v2.project_config import (
    CONFIG_FILENAME,
    ProjectConfig,
    ProjectConfigError,
)
from curatormd_v2.project_plugin import ProjectPlugin


class ProjectPluginConfigBoundaryTests(ProjectPluginTestSupport):
    """Exercise project-plugin configuration boundary behavior."""

    def test_rejects_path_traversal_symlinks_unknown_fields_and_unknown_adapters(
        self,
    ) -> None:
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
            self._valid_config() + '\n[actions]\nadapters = ["approved-runner"]\n'
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

        with self.assertRaisesRegex(
            ProjectConfigError, "missing regular project config"
        ):
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
        with self.assertRaisesRegex(
            ProjectConfigError, "must not be group- or world-writable"
        ):
            ProjectConfig.load(self.root)

    def test_rejects_unsupported_backend_contract_version(self) -> None:
        """Refuse a config declaring a backend contract this runtime cannot honor."""

        self.write_config(
            self._valid_config().replace(
                "backend_api_version = 1", "backend_api_version = 2"
            )
        )
        with self.assertRaisesRegex(
            ProjectConfigError, "backend_api_version is not supported"
        ):
            ProjectConfig.load(self.root)

    def test_rejects_secret_like_config_values_without_echoing_them(self) -> None:
        """Do not allow recognizable credentials in otherwise valid config fields."""

        secret = "sk-" + "A" * 24
        self.write_config(
            self._valid_config().replace(
                'project_id = "consumer-a"', f'project_id = "{secret}"'
            )
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
