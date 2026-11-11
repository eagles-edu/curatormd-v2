"""Two-consumer routing through the coordinator and actual Codex MCP launcher."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import TextContent

from project_fixtures import (
    TestProjectAccess,
    create_consumer_repo,
    register_test_project_access,
    write_consumer_config,
)
from curatormd_v2 import CuratorStore, ProjectAction
from curatormd_v2.bindings_coordinator import coordinate


class BindingsCoordinatorIntegrationTests(unittest.TestCase):
    def test_adding_second_consumer_preserves_first_and_both_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            roots: dict[str, Path] = {}
            databases: dict[str, str] = {}
            for project_id in ("consumer-alpha", "consumer-beta"):
                root = base / project_id
                create_consumer_repo(root)
                (root / "docs/tasks.md").write_text("- [ ] Fixture task\n")
                (root / "persistence/HISTORY.md").write_text("# Fixture history\n")
                write_consumer_config(root, project_id)
                database = base / f"{project_id}.sqlite3"
                store = CuratorStore(database)
                try:
                    register_test_project_access(
                        store, root, f"local-uid:{os.geteuid()}",
                        TestProjectAccess(actions=(ProjectAction.READ, ProjectAction.WRITE)),
                    )
                finally:
                    store.close()
                database.chmod(0o600)
                roots[project_id] = root
                databases[project_id] = str(database)

            map_path = base / "database-bindings.json"
            settings = base / "settings.json"
            settings.write_text(json.dumps({
                "editor.tabSize": 4,
                "curatormdV2.databaseBindings": {
                    "consumer-alpha": databases["consumer-alpha"]
                },
            }))
            launcher = Path(__file__).resolve().parents[1] / "integrations/codex-plugin/bin/launch-curator-mcp.py"

            async def check_consumer(project_id: str) -> None:
                root = roots[project_id]
                parameters = StdioServerParameters(
                    command=sys.executable,
                    args=[str(launcher), "--database-bindings", str(map_path), "--allow-write"],
                    cwd=root,
                    env={"PATH": os.environ.get("PATH", ""), "HOME": str(Path.home())},
                )
                async with Client(parameters, raise_exceptions=True) as client:
                    result = await client.call_tool("goal_list_page", {"offset": 0, "limit": 1})
                    self.assertFalse(result.is_error)
                    content = result.content[0]
                    assert isinstance(content, TextContent)
                    self.assertEqual(json.loads(content.text)["project_id"], project_id)

            map_path.write_text(json.dumps({
                "schema_version": 1,
                "projects": {"consumer-alpha": databases["consumer-alpha"]},
            }))
            map_path.chmod(0o600)
            self.assertEqual(coordinate(map_path, settings, apply=False, replace=False), "in-sync")
            asyncio.run(check_consumer("consumer-alpha"))
            map_path.write_text(json.dumps({"schema_version": 1, "projects": databases}))
            map_path.chmod(0o600)
            self.assertEqual(coordinate(map_path, settings, apply=False, replace=False), "drift")
            command = [
                sys.executable, "-m", "curatormd_v2.bindings_coordinator",
                "--map", str(map_path), "--settings", str(settings), "--apply",
            ]
            first = subprocess.run(
                command, cwd=roots["consumer-beta"], capture_output=True,
                text=True, check=True, timeout=30,
            )
            self.assertEqual(first.stdout.strip(), "Curator database bindings: updated")
            saved = settings.read_bytes()
            saved_stat = settings.stat()
            retry = subprocess.run(
                command, cwd=roots["consumer-beta"], capture_output=True,
                text=True, check=True, timeout=30,
            )
            self.assertEqual(retry.stdout.strip(), "Curator database bindings: in-sync")
            self.assertEqual(settings.read_bytes(), saved)
            self.assertEqual(settings.stat().st_mtime_ns, saved_stat.st_mtime_ns)
            configured = json.loads(saved)
            self.assertEqual(configured["curatormdV2.databaseBindings"], databases)
            self.assertEqual(configured["editor.tabSize"], 4)

            async def check_consumers() -> None:
                for project_id in roots:
                    await check_consumer(project_id)

            asyncio.run(check_consumers())
