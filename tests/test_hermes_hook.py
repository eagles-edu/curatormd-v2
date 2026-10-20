"""Project plugin adapter tests for Hermes' durable Codex outbox."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from typing import cast

from curatormd_v2.hermes_hook import build_hermes_hook_handler
from project_fixtures import create_consumer_repo


class HermesHookAdapterTests(unittest.TestCase):
    """Bind only matching project events and acknowledge only durable receipts."""

    def test_projects_route_to_the_bound_mcp_tool_and_require_processed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            (root / ".git").mkdir()
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "tasks.md").write_text("- [ ] Task\n")
            (root / "persistence").mkdir()
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2" / "staging").mkdir(parents=True)
            (root / ".curatormd-v2.toml").write_text(
                """\
                schema_version = 1
                backend_api_version = 1
                project_id = "project-a"

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
            calls: list[tuple[str, str, dict[str, object], dict[str, object]]] = []

            def call_mcp(
                server: str,
                tool: str,
                arguments: dict[str, object],
                **kwargs: object,
            ) -> dict[str, object]:
                calls.append((server, tool, arguments, kwargs))
                return {
                    "ok": True,
                    "result": {"project_id": "project-a", "status": "processed"},
                }

            handle = build_hermes_hook_handler(root, "curator-project-a", call_mcp=call_mcp)
            event = {
                "project_id": "project-a",
                "goal_id": "goal-1",
                "event_id": "hermes-event-1",
                "source_sequence": 4,
                "occurred_at": "2026-10-19T00:00:00+00:00",
                "attempt_id": "attempt-1",
                "session_id": "session-1",
                "model": "must-not-forward",
                "cwd": "/private/repo",
            }

            self.assertIsNone(asyncio.run(handle("codex:turn:start", {**event, "project_id": "project-b"})))
            self.assertTrue(asyncio.run(handle("codex:turn:start", event)))
            self.assertEqual(len(calls), 1)
            server, tool, arguments, kwargs = calls[0]
            self.assertEqual(server, "curator-project-a")
            self.assertEqual(tool, "hermes_codex_event")
            self.assertEqual(
                kwargs,
                {
                    "timeout": 30.0,
                    "session_id": "session-1",
                    "hermes_durable_event": True,
                },
            )
            self.assertEqual(arguments["event_type"], "codex:turn:start")
            self.assertEqual(arguments["goal_id"], "goal-1")
            self.assertEqual(
                arguments["context"],
                {"attempt_id": "attempt-1", "session_id": "session-1"},
            )

            failing = build_hermes_hook_handler(
                root,
                "curator-project-a",
                call_mcp=lambda *_args, **_kwargs: {"ok": False, "error": "retry"},
            )
            self.assertFalse(asyncio.run(failing("codex:turn:start", event)))

    def test_adapter_routes_a_durable_event_through_the_real_mcp_server(self) -> None:
        """Exercise the adapter, trusted MCP context, translator, and router together."""
        from mcp import Client
        from mcp.types import TextContent

        from curatormd_v2 import (
            AuthenticatedCaller,
            AuthenticatedCuratorAPI,
            CodexGoalBinding,
            CuratorStore,
            FactKind,
            EventDisposition,
            GoalActivityObserved,
            GoalStatus,
            InMemoryTokenBucket,
            ProjectAction,
            ProjectConfig,
            ProjectPlugin,
            build_mcp_server,
            codex_hook_to_event,
        )

        class OnlyProject:
            def authorize(
                self,
                caller: AuthenticatedCaller,
                project_id: str,
                action: ProjectAction,
            ) -> bool:
                return caller.subject_id == "host-subject" and project_id == "project-a"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            (root / ".git").mkdir()
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "docs" / "tasks.md").write_text("- [ ] Task\n")
            (root / "persistence").mkdir()
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2" / "staging").mkdir(parents=True)
            (root / ".curatormd-v2.toml").write_text(
                """\
                schema_version = 1
                backend_api_version = 1
                project_id = "project-a"

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
            db_path = Path(temporary) / "global.sqlite3"
            store = CuratorStore(db_path)
            try:
                plugin = ProjectPlugin.bind(ProjectConfig.load(root), store)
                caller = AuthenticatedCaller("host-subject")
                api = AuthenticatedCuratorAPI(
                    {"project-a": plugin}, OnlyProject(), InMemoryTokenBucket()
                )
                server = build_mcp_server(api, caller, "project-a", "hermes-e2e")
                profile = "host-subject"
                session_id = "session-e2e"

                async def drive() -> None:
                    async with Client(server, raise_exceptions=True) as client:
                        started = await client.call_tool(
                            "goal_start",
                            {
                                "event_id": "hermes-e2e-goal-start",
                                "goal_id": "hermes-e2e-goal",
                                "problem": "Exercise durable Hermes event ingestion",
                                "success_criteria": [
                                    {"criterion_id": "c1", "description": "A typed fact is recorded"}
                                ],
                                "source_sequence": 1,
                            },
                        )
                        assert not started.is_error
                        activated = await client.call_tool(
                            "goal_activate",
                            {
                                "event_id": "hermes-e2e-goal-active",
                                "goal_id": "hermes-e2e-goal",
                                "reason": "Integration test accepted",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 2,
                            },
                        )
                        assert not activated.is_error
                        context = {"attempt_id": "attempt-e2e", "session_id": session_id}
                        event = codex_hook_to_event(
                            "codex:turn:start",
                            context,
                            CodexGoalBinding(
                                profile_id=profile,
                                project_id="project-a",
                                session_id=session_id,
                                goal_id="hermes-e2e-goal",
                                source_id="hermes-"
                                + hashlib.sha256(f"{profile}\0project-a".encode()).hexdigest(),
                            ),
                            source_sequence=1,
                            occurred_at="2026-10-20T00:00:00+00:00",
                        )
                        assert isinstance(event.payload, GoalActivityObserved)

                        async def call_tool(
                            arguments: dict[str, object], **kwargs: object
                        ) -> str:
                            result = await client.call_tool(
                                "hermes_codex_event",
                                arguments,
                                meta={
                                    "hermes/profile_id": profile,
                                    "hermes/session_id": kwargs["session_id"],
                                    "hermes/durable_event": kwargs["hermes_durable_event"],
                                },
                            )
                            content = result.content[0]
                            if not isinstance(content, TextContent):
                                return json.dumps({"error": "unexpected MCP result"})
                            if result.is_error:
                                return json.dumps({"error": content.text})
                            return json.dumps({"result": content.text})

                        handle = build_hermes_hook_handler(
                            root, "curator-project-a", call_tool=call_tool
                        )
                        hook_context = {
                            **context,
                            "event_id": event.event_id,
                            "source_id": event.source_id,
                            "source_sequence": event.source_sequence,
                            "occurred_at": "2026-10-20T00:00:00+00:00",
                            "project_id": "project-a",
                            "goal_id": "hermes-e2e-goal",
                        }
                        self.assertTrue(await handle("codex:turn:start", hook_context))
                        snapshot = api.goal_status(caller, "project-a", "hermes-e2e-goal")
                        self.assertEqual(snapshot.goal.status, GoalStatus.ACTIVE)
                        self.assertEqual(snapshot.facts[-1].kind, FactKind.INTENT)
                        self.assertEqual(
                            store.event_receipt("project-a", event.event_id).disposition,
                            EventDisposition.APPLIED,
                        )

                        deferred = await client.call_tool(
                            "goal_defer",
                            {
                                "event_id": "hermes-e2e-goal-deferred",
                                "goal_id": "hermes-e2e-goal",
                                "reason": "Wait for the consumer test gate",
                                "next_action": "Resume the integration test",
                                "expected_lifecycle_revision": 2,
                                "source_sequence": 3,
                            },
                        )
                        assert not deferred.is_error
                        late_event = codex_hook_to_event(
                            "codex:turn:end",
                            {
                                "attempt_id": "attempt-e2e-late",
                                "session_id": session_id,
                                "turn_id": "turn-e2e-late",
                                "outcome": "completed",
                            },
                            CodexGoalBinding(
                                profile_id=profile,
                                project_id="project-a",
                                session_id=session_id,
                                goal_id="hermes-e2e-goal",
                                source_id=event.source_id,
                            ),
                            source_sequence=2,
                            occurred_at="2026-10-20T00:01:00+00:00",
                        )
                        assert isinstance(late_event.payload, GoalActivityObserved)
                        late_context = {
                            **hook_context,
                            "event_id": late_event.event_id,
                            "source_sequence": late_event.source_sequence,
                            "occurred_at": "2026-10-20T00:01:00+00:00",
                            "attempt_id": "attempt-e2e-late",
                            "turn_id": "turn-e2e-late",
                            "outcome": "completed",
                        }
                        self.assertTrue(await handle("codex:turn:end", late_context))
                        suppressed = store.event_receipt(
                            "project-a", late_event.event_id
                        )
                        self.assertEqual(suppressed.status.value, "processed")
                        self.assertEqual(
                            suppressed.disposition,
                            EventDisposition.SUPPRESSED_NONACTIVE_GOAL,
                        )
                        after_suppression = api.goal_status(
                            caller, "project-a", "hermes-e2e-goal"
                        )
                        retained_ids = {fact.fact_id for fact in after_suppression.facts}
                        self.assertIn(event.payload.fact_id, retained_ids)
                        self.assertNotIn(late_event.payload.fact_id, retained_ids)

                asyncio.run(drive())
            finally:
                store.close()

    def test_adapter_delivers_to_a_separate_durable_mcp_process(self) -> None:
        """Route a Hermes envelope over stdio and reopen the child's receipt."""
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        from mcp.types import TextContent

        from curatormd_v2 import CuratorStore, EventDisposition, FactKind

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] stdio task\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2.toml").write_text(
                """\
                schema_version = 1
                backend_api_version = 1
                project_id = "stdio-project"

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
            database = root / ".curatormd-v2" / "stdio.sqlite3"
            profile_id = "stdio-test-subject"
            session_id = "hermes-stdio-session"
            goal_id = "hermes-stdio-goal"
            attempt_id = "hermes-stdio-attempt"
            source_id = "hermes-" + hashlib.sha256(
                f"{profile_id}\0stdio-project".encode("utf-8")
            ).hexdigest()
            event_id = "hermes-" + hashlib.sha256(
                f"{source_id}\0codex:turn:start\0{attempt_id}".encode("utf-8")
            ).hexdigest()
            hook_context: dict[str, object] = {
                "project_id": "stdio-project",
                "goal_id": goal_id,
                "event_id": event_id,
                "source_id": source_id,
                "source_sequence": 1,
                "occurred_at": "2026-10-20T00:00:00+00:00",
                "attempt_id": attempt_id,
                "session_id": session_id,
            }
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).with_name("mcp_stdio_fixture.py"))],
                env={"CURATOR_TEST_PROJECT_ROOT": str(root)},
                cwd=Path(__file__).parents[1],
            )

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    loop = asyncio.get_running_loop()

                    async def call_json(
                        name: str, arguments: dict[str, object]
                    ) -> dict[str, object]:
                        result = await client.call_tool(name, arguments)
                        self.assertFalse(result.is_error, name)
                        content = result.content[0]
                        assert isinstance(content, TextContent)
                        decoded: object = json.loads(content.text)
                        assert isinstance(decoded, dict)
                        return cast(dict[str, object], decoded)

                    started = await call_json(
                        "goal_start",
                        {
                            "event_id": "stdio-goal-start",
                            "goal_id": goal_id,
                            "problem": "Exercise separate-process Hermes delivery",
                            "success_criteria": [
                                {
                                    "criterion_id": "fact",
                                    "description": "The durable lifecycle fact is stored",
                                }
                            ],
                            "source_sequence": 1,
                        },
                    )
                    self.assertEqual(started["status"], "processed")
                    activated = await call_json(
                        "goal_activate",
                        {
                            "event_id": "stdio-goal-activate",
                            "goal_id": goal_id,
                            "reason": "Activate the synthetic integration goal",
                            "expected_lifecycle_revision": 1,
                            "source_sequence": 2,
                        },
                    )
                    self.assertEqual(activated["status"], "processed")
                    bound = await client.call_tool(
                        "hermes_goal_bind",
                        {"goal_id": goal_id},
                        meta={
                            "hermes/profile_id": profile_id,
                            "hermes/session_id": session_id,
                        },
                    )
                    self.assertFalse(bound.is_error)

                    def call_curator(
                        server: str,
                        tool: str,
                        arguments: dict[str, object],
                        *,
                        timeout: float,
                        session_id: str,
                        hermes_durable_event: bool,
                    ) -> dict[str, object]:
                        self.assertEqual(server, "curator-stdio-project")
                        self.assertEqual(tool, "hermes_codex_event")
                        self.assertTrue(hermes_durable_event)
                        response_future = asyncio.run_coroutine_threadsafe(
                            client.call_tool(
                                tool,
                                arguments,
                                meta={
                                    "hermes/profile_id": profile_id,
                                    "hermes/session_id": session_id,
                                    "hermes/durable_event": hermes_durable_event,
                                },
                            ),
                            loop,
                        )
                        response = response_future.result(timeout=timeout)
                        content = response.content[0]
                        if response.is_error or not isinstance(content, TextContent):
                            return {"ok": False, "error": "stdio event delivery failed"}
                        return {"ok": True, "result": content.text}

                    handler = build_hermes_hook_handler(
                        root, "curator-stdio-project", call_mcp=call_curator
                    )
                    self.assertTrue(
                        await handler("codex:turn:start", hook_context)
                    )
                    self.assertTrue(
                        await handler("codex:turn:start", hook_context)
                    )
                    status = await call_json("goal_status", {"goal_id": goal_id})
                    goal_value = status["goal"]
                    assert isinstance(goal_value, dict)
                    goal = cast(dict[str, object], goal_value)
                    self.assertEqual(goal["status"], "active")
                    facts_value = status["facts"]
                    assert isinstance(facts_value, list)
                    facts = cast(list[dict[str, object]], facts_value)
                    self.assertEqual(
                        len(facts),
                        2,
                    )
                    self.assertEqual(
                        facts[-1]["bullet"],
                        "Codex turn started for the explicitly bound goal.",
                    )

            asyncio.run(exercise())
            store = CuratorStore(database)
            try:
                receipt = store.event_receipt("stdio-project", event_id)
                self.assertEqual(receipt.disposition, EventDisposition.APPLIED)
                facts = store.list_facts(goal_id, "stdio-project")
                self.assertEqual(len(facts), 2)
                self.assertTrue(all(fact.kind is FactKind.INTENT for fact in facts))
                self.assertEqual(
                    facts[-1].bullet,
                    "Codex turn started for the explicitly bound goal.",
                )
            finally:
                store.close()
