"""Project plugin adapter tests for Hermes' durable Codex outbox."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from curatormd_v2.hermes_hook import build_hermes_hook_handler


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
            calls: list[tuple[dict[str, object], dict[str, object]]] = []

            def call_tool(arguments: dict[str, object], **kwargs: object) -> str:
                calls.append((arguments, kwargs))
                return json.dumps(
                    {"result": json.dumps({"project_id": "project-a", "status": "processed"})}
                )

            handle = build_hermes_hook_handler(root, "curator-project-a", call_tool=call_tool)
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
            arguments, kwargs = calls[0]
            self.assertEqual(
                kwargs,
                {"session_id": "session-1", "hermes_durable_event": True},
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
                call_tool=lambda *_args, **_kwargs: json.dumps({"error": "retry"}),
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
