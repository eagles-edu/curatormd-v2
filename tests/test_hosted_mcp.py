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

from project_fixtures import create_consumer_repo

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import RequestParamsMeta, TextContent

from curatormd_v2 import (
    AuthenticatedCaller,
    CuratorStore,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectConfig,
    SQLiteTokenBucket,
    hosted_mcp,
)
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.mcp_server import safe_tool_handler

def _hermes_meta(
    profile_id: str, session_id: str = "test-session"
) -> RequestParamsMeta:
    """Build synthetic Hermes context metadata for boundary tests."""

    return {
        "hermes/profile_id": profile_id,
        "hermes/session_id": session_id,
    }


class _TestProjectAdmin:
    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow administration only to the explicitly named test operator."""

        return (
            caller.subject_id == "test-operator"
            and bool(project_id)
            and action
            in {
                ProjectAdministrationAction.REGISTER,
                ProjectAdministrationAction.UPDATE,
                ProjectAdministrationAction.SUSPEND,
                ProjectAdministrationAction.REACTIVATE,
                ProjectAdministrationAction.VIEW,
                ProjectAdministrationAction.GRANT,
                ProjectAdministrationAction.REVOKE,
            }
        )


class HostedMcpTests(unittest.TestCase):
    """Keep each local MCP process pinned to one project and principal."""

    def _project(self, root: Path, project_id: str = "bound-project") -> None:
        create_consumer_repo(root)
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

    def _provision(
        self,
        root: Path,
        database: Path,
        profile_id: str,
        *,
        allow_write: bool = False,
        allow_review: bool = False,
    ) -> None:
        """Seed durable access using the host-only project administration API."""

        config = ProjectConfig.load(root)
        store = CuratorStore(database)
        try:
            manager = ProjectAccessManager(store, _TestProjectAdmin())
            operator = AuthenticatedCaller("test-operator")
            manager.register_project(
                operator,
                config.project_id,
                config.repository_fingerprint,
                config.config_sha256,
                config.backend_api_version,
                "Approve the disposable integration-test project binding",
            )
            for action in (
                ProjectAction.READ,
                ProjectAction.WRITE,
                ProjectAction.REVIEW,
            ):
                if action is ProjectAction.WRITE and not allow_write:
                    continue
                if action is ProjectAction.REVIEW and not allow_review:
                    continue
                manager.grant(
                    operator,
                    config.project_id,
                    profile_id,
                    action,
                    "Grant the disposable integration-test profile exact access",
                )
        finally:
            store.close()

    def test_profile_binding_defaults_to_read_only_and_denies_review_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
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
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
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

    def test_review_grant_is_exact_and_requires_launcher_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(
                root,
                database,
                "reviewer-profile",
                allow_review=True,
            )
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_review=True,
            )
            try:
                authorizer = runtime.api.authorizer
                self.assertTrue(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.REVIEW
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        AuthenticatedCaller("other-profile"),
                        "bound-project",
                        ProjectAction.REVIEW,
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "another-project", ProjectAction.REVIEW
                    )
                )
                self.assertFalse(
                    authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.WRITE
                    )
                )
            finally:
                runtime.close()

            read_only_runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
            )
            try:
                self.assertFalse(
                    read_only_runtime.api.authorizer.authorize(
                        read_only_runtime.caller,
                        "bound-project",
                        ProjectAction.REVIEW,
                    )
                )
            finally:
                read_only_runtime.close()

            store = CuratorStore(database)
            try:
                manager = ProjectAccessManager(store, _TestProjectAdmin())
                manager.grant(
                    AuthenticatedCaller("test-operator"),
                    "bound-project",
                    "read-only-profile",
                    ProjectAction.READ,
                    "Grant only read access for the launcher opt-in test",
                )
            finally:
                store.close()
            with self.assertRaisesRegex(
                ValueError, "requested project review grant is not active"
            ):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="read-only-profile",
                    allow_review=True,
                )

    def test_typed_mcp_event_retry_ignores_regenerated_occurrence_time(self) -> None:
        """A new MCP invocation can safely replay a processed event identity."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding", allow_write=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                allow_write=True,
            )
            try:
                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        arguments = {
                            "event_id": "mcp-replay-event",
                            "goal_id": "mcp-replay-goal",
                            "problem": "Verify typed event retry behavior",
                            "success_criteria": [
                                {"criterion_id": "verified", "description": "Retry is idempotent"}
                            ],
                        }
                        first = await client.call_tool(
                            "goal_start", arguments, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(first.is_error)
                        retry = await client.call_tool(
                            "goal_start", arguments, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertFalse(retry.is_error)

                        changed = dict(arguments)
                        changed["problem"] = "Changed payload must conflict"
                        conflict = await client.call_tool(
                            "goal_start", changed, meta=_hermes_meta("gptmd-coding")
                        )
                        self.assertTrue(conflict.is_error)
                        conflict_content = conflict.content[0]
                        assert isinstance(conflict_content, TextContent)
                        self.assertEqual(json.loads(conflict_content.text)["code"], "conflict")

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_every_local_profile_tool_call_requires_matching_hermes_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        missing = await client.call_tool("project_activity_status", {})
                        self.assertTrue(missing.is_error)
                        missing_content = missing.content[0]
                        assert isinstance(missing_content, TextContent)
                        self.assertEqual(
                            json.loads(missing_content.text)["code"], "unauthenticated"
                        )

                        mismatch = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta=_hermes_meta("another-profile"),
                        )
                        self.assertTrue(mismatch.is_error)

                        no_session = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta={"hermes/profile_id": "gptmd-coding"},
                        )
                        self.assertTrue(no_session.is_error)

                        valid = await client.call_tool(
                            "project_activity_status",
                            {},
                            meta=_hermes_meta("gptmd-coding"),
                        )
                        self.assertFalse(valid.is_error)

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_launcher_requires_registered_fingerprint_and_live_grants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            with self.assertRaisesRegex(ValueError, "registration fingerprint"):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="gptmd-coding",
                )

            self._provision(root, database, "gptmd-coding")
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
            )
            try:
                self.assertTrue(
                    runtime.api.authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
                external_store = CuratorStore(database)
                try:
                    manager = ProjectAccessManager(
                        external_store, _TestProjectAdmin()
                    )
                    manager.set_project_status(
                        AuthenticatedCaller("test-operator"),
                        "bound-project",
                        "suspended",
                        "Suspend the disposable test project",
                    )
                finally:
                    external_store.close()
                self.assertFalse(
                    runtime.api.authorizer.authorize(
                        runtime.caller, "bound-project", ProjectAction.READ
                    )
                )
            finally:
                runtime.close()

            changed = (root / ".curatormd-v2.toml").read_text()
            (root / ".curatormd-v2.toml").write_text(
                changed.replace('project_id = "bound-project"', 'project_id = "changed-project"')
            )
            (root / ".curatormd-v2.toml").chmod(0o600)
            with self.assertRaisesRegex(ValueError, "registration fingerprint"):
                build_local_profile_mcp(
                    project_root=root,
                    database=database,
                    profile_id="gptmd-coding",
                )

    def test_database_path_must_be_absolute_and_profile_id_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
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

        with self.assertLogs("curatormd_v2.mcp_server", level="WARNING") as logs:
            result = safe_tool_handler(fail_with_sensitive_detail)()
        self.assertTrue(result.is_error)
        content = result.content[0]
        assert isinstance(content, TextContent)
        public_error = json.loads(content.text)
        self.assertEqual(public_error["code"], "internal_error")
        self.assertNotIn("private database path", content.text)
        self.assertNotIn("Traceback", content.text)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("code=internal_error", logs.output[0])
        self.assertIn("exception_type=RuntimeError", logs.output[0])
        self.assertNotIn("private database path", logs.output[0])
        self.assertNotIn("SQL fragment", logs.output[0])

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
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
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
                        meta=_hermes_meta("gptmd-coding"),
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
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(queue.is_error)
                    content = queue.content[0]
                    assert isinstance(content, TextContent)
                    self.assertEqual(json.loads(content.text)["received_count"], 0)

            asyncio.run(exercise())

    def test_installed_launcher_writes_and_reads_a_project_bound_goal(self) -> None:
        """Exercise the packaged command, not only its Python module entrypoint."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
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
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(started.is_error)
                    status = await client.call_tool(
                        "goal_status",
                        {"goal_id": "launcher-goal-1"},
                        meta=_hermes_meta("gptmd-coding"),
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
                        meta=_hermes_meta("gptmd-coding"),
                    )
                    self.assertFalse(inventory_result.is_error)
                    inventory_content = inventory_result.content[0]
                    assert isinstance(inventory_content, TextContent)
                    inventory = json.loads(inventory_content.text)
                    self.assertTrue(inventory["usage"]["inventory_complete"])
                    self.assertIsNone(inventory["scope_goal_id"])

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
                        meta=_hermes_meta("profile-a"),
                    )
                    self.assertFalse(started_a.is_error)

                    async with Client(
                        parameters(project_b, "profile-b"), raise_exceptions=True
                    ) as client_b:
                        page_b = await client_b.call_tool(
                            "goal_list_page",
                            {"offset": 0, "limit": 10},
                            meta=_hermes_meta("profile-b"),
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
                            meta=_hermes_meta("profile-b"),
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
                            meta=_hermes_meta("profile-b"),
                        )
                        self.assertFalse(started_b.is_error)

                    page_a = await client_a.call_tool(
                        "goal_list_page",
                        {"offset": 0, "limit": 10},
                        meta=_hermes_meta("profile-a"),
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
                        meta=_hermes_meta("profile-a"),
                    )
                    self.assertTrue(foreign_status.is_error)

            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
