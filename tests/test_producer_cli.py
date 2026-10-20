"""Packaged stdin producer boundary for temporary project artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from curatormd_v2 import CuratorStore, SuccessCriterion
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from project_fixtures import create_consumer_repo


class ProducerCliTests(unittest.TestCase):
    """Ensure external producers inherit plugin scoping and stream safeguards."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(self.temporary) / "consumer"
        create_consumer_repo(self.root)
        (self.root / "docs" / "tasks.md").write_text("- [ ] Capture import\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        config_path = self.root / ".curatormd-v2.toml"
        config_path.write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "producer-consumer"

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
        config_path.chmod(0o600)
        self.database = Path(self.temporary) / "global.sqlite3"
        config = ProjectConfig.load(self.root)
        store = CuratorStore(self.database)
        try:
            plugin = ProjectPlugin.bind(config, store)
            plugin.service.goal_start(
                "Stage an exact producer payload",
                (SuccessCriterion("review", "A reviewer can inspect this import"),),
                goal_id="producer-goal",
            )
        finally:
            store.close()

    def _run(
        self, payload: bytes, goal_id: str = "producer-goal"
    ) -> subprocess.CompletedProcess[bytes]:
        repository = Path(__file__).parents[1]
        source = repository / "src"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(source),
        }
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "curatormd_v2.producer_cli",
                "--project-root",
                str(self.root),
                "--database",
                str(self.database),
                "--goal-id",
                goal_id,
                "--artifact-class",
                "import",
                "--artifact-id",
                "session-1",
            ],
            input=payload,
            capture_output=True,
            cwd=repository,
            env=environment,
            check=False,
            timeout=15,
        )

    def test_stdin_artifact_is_staged_with_digest_and_private_mode(self) -> None:
        payload = b"private producer material\x00" * 128

        result = self._run(payload)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertNotIn(payload, result.stdout)
        value = json.loads(result.stdout)
        path = Path(value["path"])
        self.assertEqual(
            path,
            self.root
            / ".curatormd-v2"
            / "staging"
            / "producer-goal"
            / "import"
            / "session-1.bin",
        )
        self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(value["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_failed_producer_request_does_not_echo_payload_or_leave_partial_file(self) -> None:
        payload = b"private must-not-leak marker"

        result = self._run(payload, goal_id="unbound-goal")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(payload, result.stderr)
        self.assertIn(b"Curator V2 staging failed", result.stderr)
        goal_root = self.root / ".curatormd-v2" / "staging" / "unbound-goal"
        self.assertFalse(goal_root.exists())


if __name__ == "__main__":
    unittest.main()
