"""Installed stdio launcher contract tests for Curator V2."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import TextContent

from test_hosted_mcp import HostedMcpFixtures, hermes_meta


class InstalledHostedMcpTests(HostedMcpFixtures, unittest.TestCase):
    """Exercise the installed command and project isolation over stdio."""

    def test_stdio_process_pins_real_config_and_rejects_ungranted_goal_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, database = self._project_database(temporary)
            self._provision(root, database, "gptmd-coding")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "curatormd_v2.hosted_mcp",
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
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
                        meta=hermes_meta("gptmd-coding"),
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
                    missing_context = await client.call_tool(
                        "event_queue_status", {}
                    )
                    self.assertTrue(missing_context.is_error)
                    queue = await client.call_tool(
                        "event_queue_status",
                        {},
                        meta=hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(queue.is_error)
                    content = queue.content[0]
                    assert isinstance(content, TextContent)
                    self.assertEqual(json.loads(content.text)["received_count"], 0)

            asyncio.run(exercise())

    def test_installed_launcher_writes_and_reads_a_project_bound_goal(self) -> None:
        """Exercise the packaged command, not only its Python module entrypoint."""

        with tempfile.TemporaryDirectory() as temporary:
            root, database = self._project_database(temporary)
            self._provision(
                root,
                database,
                "gptmd-coding",
                allow_write=True,
                allow_review=True,
            )
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")
            parameters = StdioServerParameters(
                command=str(launcher),
                args=[
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "--profile-id",
                    "gptmd-coding",
                    "--allow-write",
                    "--allow-review",
                ],
                env={
                    "PATH": os.environ.get("PATH", ""),
                },
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tools = await client.list_tools()
                    self.assertIn(
                        "project_artifact_inventory_discover",
                        {tool.name for tool in tools.tools},
                    )
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
                        meta=hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(started.is_error)
                    status = await client.call_tool(
                        "goal_status",
                        {"goal_id": "launcher-goal-1"},
                        meta=hermes_meta("gptmd-coding"),
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
                    inventory_result = await client.call_tool(
                        "project_artifact_inventory_discover",
                        {},
                        meta=hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(inventory_result.is_error)
                    inventory_content = inventory_result.content[0]
                    assert isinstance(inventory_content, TextContent)
                    inventory = json.loads(inventory_content.text)
                    self.assertTrue(inventory["usage"]["inventory_complete"])
                    self.assertIsNone(inventory["scope_goal_id"])

            asyncio.run(exercise())

    def test_installed_launcher_exposes_sde_proposal_context(self) -> None:
        """The installed MCP schema carries compact proposal context fields."""

        with tempfile.TemporaryDirectory() as temporary:
            root, database = self._project_database(temporary)
            self._provision(root, database, "gptmd-coding", allow_write=True)
            launcher = Path(sys.executable).with_name("curatormd-v2-mcp")
            self.assertTrue(launcher.is_file(), f"missing installed launcher: {launcher}")
            parameters = StdioServerParameters(
                command=str(launcher),
                args=[
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "--profile-id",
                    "gptmd-coding",
                    "--allow-write",
                ],
                env={"PATH": os.environ.get("PATH", "")},
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tools = await client.list_tools()
                    assessment = next(
                        tool for tool in tools.tools if tool.name == "sde_assess"
                    )
                    schema = assessment.input_schema
                    properties = schema["properties"]
                    self.assertIn("impact", properties)
                    self.assertIn("retrieval_value", properties)
                    self.assertNotIn("project_id", properties)
                    required = set(schema.get("required", []))
                    self.assertTrue(
                        {"impact", "retrieval_value"}.isdisjoint(required),
                        "routine progress must remain valid without SDE context",
                    )

            asyncio.run(exercise())

    def test_two_stdio_projects_sharing_database_remain_isolated(self) -> None:
        """Separate consumer launchers cannot list or read each other's goals."""

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project_a = base / "consumer-a"
            project_b = base / "consumer-b"
            self._project(project_a, "project-a")
            self._project(project_b, "project-b")
            database = base / "global.sqlite3"
            self._provision(
                project_a, database, "profile-a", allow_write=True
            )
            self._provision(
                project_b, database, "profile-b", allow_write=True
            )
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
                        meta=hermes_meta("profile-a"),
                    )
                    self.assertFalse(started_a.is_error)

                    async with Client(
                        parameters(project_b, "profile-b"), raise_exceptions=True
                    ) as client_b:
                        page_b = await client_b.call_tool(
                            "goal_list_page",
                            {"offset": 0, "limit": 10},
                            meta=hermes_meta("profile-b"),
                        )
                        self.assertFalse(page_b.is_error)
                        page_b_content = page_b.content[0]
                        assert isinstance(page_b_content, TextContent)
                        page_b_value = json.loads(page_b_content.text)
                        self.assertEqual(page_b_value["project_id"], "project-b")
                        self.assertEqual(page_b_value["total"], 0)
                        self.assertEqual(page_b_value["goals"], [])

                        foreign_status = await client_b.call_tool(
                            "goal_status",
                            {"goal_id": "project-a-goal"},
                            meta=hermes_meta("profile-b"),
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
                            meta=hermes_meta("profile-b"),
                        )
                        self.assertFalse(started_b.is_error)

                    page_a = await client_a.call_tool(
                        "goal_list_page",
                        {"offset": 0, "limit": 10},
                        meta=hermes_meta("profile-a"),
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
                        "goal_status",
                        {"goal_id": "project-b-goal"},
                        meta=hermes_meta("profile-a"),
                    )
                    self.assertTrue(foreign_status.is_error)

            asyncio.run(exercise())
