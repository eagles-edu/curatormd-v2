"""Least-privilege checks for the local Hermes profile-bound MCP launcher."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import TextContent

from curatormd_v2 import ProjectAction, SQLiteTokenBucket, hosted_mcp
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.mcp_server import safe_tool_handler


class HostedMcpTests(unittest.TestCase):
    """Keep each local MCP process pinned to one project and principal."""

    def _project(self, root: Path, project_id: str = "bound-project") -> None:
        (root / ".git").mkdir()
        (root / "src").mkdir()
        (root / "docs").mkdir()
        (root / "persistence").mkdir()
        (root / ".curatormd-v2" / "staging").mkdir(parents=True)
        (root / "docs" / "tasks.md").write_text("- [ ] Bounded task\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        (root / ".curatormd-v2.toml").write_text(
            f"""\
            schema_version = 1
            backend_api_version = 1
            project_id = "{project_id}"

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

    def test_profile_binding_defaults_to_read_only_and_denies_review_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                self.assertIsInstance(runtime.api.limiter, SQLiteTokenBucket)
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
                for action in (
                    ProjectAction.WRITE,
                    ProjectAction.REVIEW,
                    ProjectAction.PURGE_RETRY,
                    ProjectAction.RETENTION_HOLD_RELEASE,
                    ProjectAction.EVENT_RETRY,
                ):
                    with self.subTest(action=action):
                        self.assertFalse(
                            authorizer.authorize(
                                runtime.caller, "bound-project", action
                            )
                        )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.READ
                    )
                )
            finally:
                runtime.close()

    def test_write_grant_is_exact_to_profile_project_and_still_not_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=Path(temporary) / "global.sqlite3",
                profile_id="gptmd-coding",
                allow_write=True,
            )
            try:
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.WRITE
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        type(runtime.caller)("other-profile"),
                        "bound-project",
                        ProjectAction.WRITE,
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.WRITE
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.REVIEW
                    )
                )
            finally:
                runtime.close()

    def test_database_path_must_be_absolute_and_profile_id_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            with self.assertRaisesRegex(ValueError, "absolute path"):
                build_local_profile_mcp(
                    project_root=root,
                    database="relative.sqlite3",
                    profile_id="gptmd-coding",
                )
            with self.assertRaisesRegex(ValueError, "profile_id"):
                build_local_profile_mcp(
                    project_root=root,
                    database=Path(temporary) / "global.sqlite3",
                    profile_id="bad profile",
                )

    def test_tool_failure_uses_public_error_without_exception_details(self) -> None:
        def fail_with_sensitive_detail() -> None:
            raise RuntimeError("private database path and SQL fragment")

        result = safe_tool_handler(fail_with_sensitive_detail)()
        self.assertTrue(result.is_error)
        content = result.content[0]
        assert isinstance(content, TextContent)
        public_error = json.loads(content.text)
        self.assertEqual(public_error["code"], "internal_error")
        self.assertNotIn("private database path", content.text)
        self.assertNotIn("Traceback", content.text)

    def test_launcher_startup_failure_does_not_echo_exception_detail(self) -> None:
        """Do not copy arbitrary startup exception text into process logs."""

        stderr = StringIO()
        arguments = [
            "--project-root",
            "/tmp/private-project",
            "--database",
            "/tmp/private-database.sqlite3",
            "--profile-id",
            "trusted-profile",
        ]
        for startup_exception in (
            ValueError("private raw payload marker"),
            OSError("private-database.sqlite3 could not be opened"),
            RuntimeError("private SQL fragment"),
        ):
            with self.subTest(exception=type(startup_exception).__name__):
                stderr = StringIO()
                with patch(
                    "curatormd_v2.hosted_mcp.build_local_profile_mcp",
                    side_effect=startup_exception,
                ), redirect_stderr(stderr):
                    exit_code = hosted_mcp.main(arguments)

                self.assertEqual(exit_code, 2)
                self.assertIn("startup failed", stderr.getvalue())
                self.assertNotIn("private raw payload marker", stderr.getvalue())
                self.assertNotIn("private-database.sqlite3", stderr.getvalue())
                self.assertNotIn("private SQL fragment", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_stdio_process_pins_real_config_and_rejects_ungranted_goal_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "curatormd_v2.hosted_mcp",
                    "--project-root",
                    str(root),
                    "--database",
                    str(Path(temporary) / "global.sqlite3"),
                    "--profile-id",
                    "gptmd-coding",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
                },
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=False) as client:
                    denied = await client.call_tool(
                        "goal_start",
                        {
                            "event_id": "denied-event",
                            "goal_id": "denied-goal",
                            "problem": "A write must require the explicit write grant",
                            "success_criteria": [
                                {
                                    "criterion_id": "denied",
                                    "description": "The write is rejected",
                                }
                            ],
                        },
                    )
                    self.assertTrue(denied.is_error)
                    denied_content = denied.content[0]
                    assert isinstance(denied_content, TextContent)
                    public_error = json.loads(denied_content.text)
                    self.assertEqual(public_error["schema_version"], 1)
                    self.assertEqual(public_error["code"], "forbidden")
                    self.assertEqual(
                        public_error["message"],
                        "The caller is not allowed to perform this operation.",
                    )
                    self.assertNotIn("Traceback", denied_content.text)
                    self.assertNotIn("project is not authorized", denied_content.text)
                    queue = await client.call_tool("event_queue_status", {})
                    self.assertFalse(queue.is_error)
                    content = queue.content[0]
                    assert isinstance(content, TextContent)
                    self.assertEqual(json.loads(content.text)["received_count"], 0)

            asyncio.run(exercise())

    def test_installed_launcher_writes_and_reads_a_project_bound_goal(self) -> None:
        """Exercise the packaged command, not only its Python module entrypoint."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")
            parameters = StdioServerParameters(
                command=str(launcher),
                args=[
                    "--project-root",
                    str(root),
                    "--database",
                    str(Path(temporary) / "global.sqlite3"),
                    "--profile-id",
                    "gptmd-coding",
                    "--allow-write",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                },
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tools = await client.list_tools()
                    goal_start = next(
                        tool for tool in tools.tools if tool.name == "goal_start"
                    )
                    self.assertNotIn("project_id", goal_start.input_schema["properties"])
                    self.assertNotIn("caller", goal_start.input_schema["properties"])
                    started = await client.call_tool(
                        "goal_start",
                        {
                            "event_id": "launcher-event-1",
                            "goal_id": "launcher-goal-1",
                            "problem": "Verify the installed Curator V2 MCP launcher",
                            "success_criteria": [
                                {
                                    "criterion_id": "stdio-roundtrip",
                                    "description": "Create and read a scoped goal over MCP stdio",
                                }
                            ],
                        },
                    )
                    self.assertFalse(started.is_error)
                    status = await client.call_tool(
                        "goal_status", {"goal_id": "launcher-goal-1"}
                    )
                    self.assertFalse(status.is_error)
                    content = status.content[0]
                    assert isinstance(content, TextContent)
                    value = json.loads(content.text)
                    goal = value["goal"]
                    self.assertEqual(goal["project_id"], "bound-project")
                    self.assertEqual(goal["status"], "planned")
                    self.assertEqual(
                        goal["problem"],
                        "Verify the installed Curator V2 MCP launcher",
                    )
                    self.assertEqual(
                        goal["success_criteria"][0]["criterion_id"],
                        "stdio-roundtrip",
                    )

            asyncio.run(exercise())

    def test_two_stdio_projects_sharing_database_remain_isolated(self) -> None:
        """Separate consumer launchers cannot list or read each other's goals."""

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project_a = base / "consumer-a"
            project_b = base / "consumer-b"
            project_a.mkdir()
            project_b.mkdir()
            self._project(project_a, "project-a")
            self._project(project_b, "project-b")
            database = base / "global.sqlite3"
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")

            def parameters(root: Path, profile_id: str) -> StdioServerParameters:
                return StdioServerParameters(
                    command=str(launcher),
                    args=[
                        "--project-root",
                        str(root),
                        "--database",
                        str(database),
                        "--profile-id",
                        profile_id,
                        "--allow-write",
                    ],
                    env={"PATH": os.environ.get("PATH", "")},
                    cwd=Path(__file__).parents[1],
                )

            async def exercise() -> None:
                async with Client(
                    parameters(project_a, "profile-a"), raise_exceptions=True
                ) as client_a:
                    started_a = await client_a.call_tool(
                        "goal_start",
                        {
                            "event_id": "project-a-event",
                            "goal_id": "project-a-goal",
                            "problem": "A scoped goal for consumer A",
                            "success_criteria": [
                                {
                                    "criterion_id": "a-only",
                                    "description": "Remain visible only in project A",
                                }
                            ],
                        },
                    )
                    self.assertFalse(started_a.is_error)

                    async with Client(
                        parameters(project_b, "profile-b"), raise_exceptions=True
                    ) as client_b:
                        page_b = await client_b.call_tool(
                            "goal_list_page", {"offset": 0, "limit": 10}
                        )
                        self.assertFalse(page_b.is_error)
                        page_b_content = page_b.content[0]
                        assert isinstance(page_b_content, TextContent)
                        page_b_value = json.loads(page_b_content.text)
                        self.assertEqual(page_b_value["project_id"], "project-b")
                        self.assertEqual(page_b_value["total"], 0)
                        self.assertEqual(page_b_value["goals"], [])

                        foreign_status = await client_b.call_tool(
                            "goal_status", {"goal_id": "project-a-goal"}
                        )
                        self.assertTrue(foreign_status.is_error)

                        started_b = await client_b.call_tool(
                            "goal_start",
                            {
                                "event_id": "project-b-event",
                                "goal_id": "project-b-goal",
                                "problem": "A scoped goal for consumer B",
                                "success_criteria": [
                                    {
                                        "criterion_id": "b-only",
                                        "description": "Remain visible only in project B",
                                    }
                                ],
                            },
                        )
                        self.assertFalse(started_b.is_error)

                    page_a = await client_a.call_tool(
                        "goal_list_page", {"offset": 0, "limit": 10}
                    )
                    self.assertFalse(page_a.is_error)
                    page_a_content = page_a.content[0]
                    assert isinstance(page_a_content, TextContent)
                    page_a_value = json.loads(page_a_content.text)
                    self.assertEqual(page_a_value["project_id"], "project-a")
                    self.assertEqual(page_a_value["total"], 1)
                    self.assertEqual(
                        [goal["goal_id"] for goal in page_a_value["goals"]],
                        ["project-a-goal"],
                    )
                    foreign_status = await client_a.call_tool(
                        "goal_status", {"goal_id": "project-b-goal"}
                    )
                    self.assertTrue(foreign_status.is_error)

            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
