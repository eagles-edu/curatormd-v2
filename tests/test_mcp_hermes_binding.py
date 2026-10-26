"""Trusted Hermes lifecycle binding tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, cast

from mcp import Client
from mcp.types import RequestParamsMeta, TextContent
from project_fixtures import (
    bind_test_project,
    create_consumer_repo,
)
from test_mcp_server import (
    AllowProject,
    DenyProject,
    McpServerTestSupport,
    _HermesLifecycleCall,  # pyright: ignore[reportPrivateUsage]
    _HermesLifecycleOptions,  # pyright: ignore[reportPrivateUsage]
)
from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CodexGoalBinding,
    ConsumerBindingTransitionRequest,
    CuratorStore,
    InMemoryTokenBucket,
    ProjectPlugin,
    build_mcp_server,
    codex_hook_to_event,
)


class HermesBindingTests(McpServerTestSupport):
    """Trusted Hermes lifecycle binding tests."""

    def test_hermes_goal_binding_requires_trusted_context_and_active_project_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] Bind current goal\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            config_path = root / ".curatormd-v2.toml"
            config_path.write_text(
                """\
                schema_version = 1
                backend_api_version = 1
                project_id = "mcp-project"

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
            store = CuratorStore(Path(temporary) / "global.sqlite3")
            try:
                plugin = bind_test_project(store, root, "host-subject")
                caller = AuthenticatedCaller("host-subject", "host-subject")
                api = AuthenticatedCuratorAPI(
                    {"mcp-project": plugin}, AllowProject(), InMemoryTokenBucket()
                )
                server = build_mcp_server(api, caller, "mcp-project", "mcp-bind-test")

                async def exercise() -> None:
                    async with Client(server, raise_exceptions=True) as client:
                        await self._assert_initial_hermes_goal_binding(client)
                        first = await self._accept_first_hermes_event(client)
                        await self._assert_exact_hermes_replay(client, first)
                        self._reenroll_mcp_binding(store)
                        await self._assert_stale_hermes_replay(
                            client, first, plugin, caller
                        )
                        fresh = await self._accept_reenrolled_hermes_event(client)
                        self._retire_mcp_binding(store)
                        await self._assert_retired_hermes_behavior(
                            client, first, fresh
                        )

                asyncio.run(exercise())
            finally:
                store.close()

    async def _assert_initial_hermes_goal_binding(self, client: Client) -> None:
        """Require trusted context and an active goal before binding."""
        binding_tool = next(
            tool
            for tool in (await client.list_tools()).tools
            if tool.name == "hermes_goal_bind"
        )
        self.assertNotIn("ctx", binding_tool.input_schema["properties"])
        started = await client.call_tool(
            "goal_start",
            {
                "event_id": "bind-goal-start",
                "goal_id": "bind-goal",
                "problem": "Bind an active goal to this Hermes session",
                "success_criteria": [
                    {"criterion_id": "c1", "description": "Binding is scoped"}
                ],
                "source_sequence": 1,
            },
        )
        self.assertFalse(started.is_error)
        missing_context = await client.call_tool(
            "hermes_goal_bind",
            {"goal_id": "bind-goal"},
            meta={
                "hermes/profile_id": "host-subject",
                "hermes/session_id": "session-1",
                "hermes/durable_event": True,
            },
        )
        self.assertTrue(missing_context.is_error)
        activated = await client.call_tool(
            "goal_activate",
            {
                "event_id": "bind-goal-activate",
                "goal_id": "bind-goal",
                "reason": "Accepted for work",
                "expected_lifecycle_revision": 1,
                "source_sequence": 2,
            },
        )
        self.assertFalse(activated.is_error)
        valid = await client.call_tool(
            "hermes_goal_bind",
            {"goal_id": "bind-goal"},
            meta={
                "hermes/profile_id": "host-subject",
                "hermes/session_id": "session-1",
            },
        )
        self.assertFalse(valid.is_error)
        assert isinstance(valid.content[0], TextContent)
        payload = json.loads(valid.content[0].text)
        self.assertEqual(payload["binding"], "validated")
        self.assertEqual(payload["goal_id"], "bind-goal")

    async def _accept_first_hermes_event(
        self, client: Client
    ) -> _HermesLifecycleCall:
        """Accept one context-bound lifecycle event for replay checks."""
        context = {"attempt_id": "attempt-1", "session_id": "session-1"}
        binding = CodexGoalBinding(
            profile_id="host-subject",
            project_id="mcp-project",
            session_id="session-1",
            goal_id="bind-goal",
            source_id="hermes-" + hashlib.sha256(
                b"host-subject\0mcp-project"
            ).hexdigest(),
        )
        event = codex_hook_to_event(
            "codex:turn:start",
            context,
            binding,
            source_sequence=1,
            occurred_at="2026-10-19T00:00:00+00:00",
        )
        request = _HermesLifecycleCall(
            binding, context, event, "2026-10-19T00:00:00+00:00"
        )
        accepted = await self._send_hermes_event(client, request)
        self.assertFalse(accepted.is_error)
        assert isinstance(accepted.content[0], TextContent)
        self.assertEqual(
            json.loads(accepted.content[0].text)["status"], "processed"
        )
        return request

    async def _assert_exact_hermes_replay(
        self, client: Client, request: _HermesLifecycleCall
    ) -> None:
        """A delivered lifecycle event replays to its exact processed receipt."""
        replay = await self._send_hermes_event(client, request)
        self.assertFalse(replay.is_error)
        assert isinstance(replay.content[0], TextContent)
        self.assertEqual(json.loads(replay.content[0].text)["status"], "processed")

    def _reenroll_mcp_binding(self, store: CuratorStore) -> None:
        """Deregister and re-enroll the project with a new source epoch."""
        for revision, status, transition_id in (
            (1, "deregistration_pending", "mcp-pending-1"),
            (2, "deregistered", "mcp-final-1"),
        ):
            store.transition_consumer_binding(
                ConsumerBindingTransitionRequest(
                    project_id="mcp-project",
                    status=status,
                    rationale="Integration test consumer lifecycle",
                    expected_revision=revision,
                    transition_id=transition_id,
                ),
                actor_id="host-subject",
            )
        registration = store.get_project_registration("mcp-project")
        store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id="mcp-project",
                status="active",
                rationale="Integration test fresh consumer session",
                expected_revision=3,
                transition_id="mcp-reenroll-1",
                expected_source_epoch=1,
                expected_project_revision=registration.revision,
                repository_fingerprint=registration.repository_fingerprint,
                config_sha256=registration.config_sha256,
                backend_api_version=registration.backend_api_version,
            ),
            actor_id="host-subject",
        )

    async def _assert_stale_hermes_replay(
        self,
        client: Client,
        request: _HermesLifecycleCall,
        plugin: ProjectPlugin,
        caller: AuthenticatedCaller,
    ) -> None:
        """Only the exact processed envelope can reconcile across re-enrollment."""
        stale = await self._send_hermes_event(client, request)
        self.assertFalse(stale.is_error)
        assert isinstance(stale.content[0], TextContent)
        self.assertEqual(json.loads(stale.content[0].text)["status"], "processed")
        changed_request = replace(
            request,
            options=replace(request.options, goal_id="different-goal"),
        )
        changed_replay = await self._send_hermes_event(client, changed_request)
        self.assertTrue(changed_replay.is_error)
        denied_api = AuthenticatedCuratorAPI(
            {"mcp-project": plugin}, DenyProject(), InMemoryTokenBucket()
        )
        with self.assertRaises(PermissionError):
            denied_api.process_event_json(
                caller,
                "mcp-project",
                request.event.to_json(),
                replay_only=True,
            )

    async def _accept_reenrolled_hermes_event(
        self, client: Client
    ) -> _HermesLifecycleCall:
        """Accept a fresh lifecycle event under the incremented source epoch."""
        context = {
            "attempt_id": "attempt-after-reenrollment",
            "session_id": "session-2",
        }
        binding = CodexGoalBinding(
            profile_id="host-subject",
            project_id="mcp-project",
            session_id="session-2",
            goal_id="bind-goal",
            source_id="hermes-" + hashlib.sha256(
                b"host-subject\0mcp-project\0" b"2"
            ).hexdigest(),
        )
        event = codex_hook_to_event(
            "codex:turn:start",
            context,
            binding,
            source_sequence=1,
            occurred_at="2026-10-19T00:01:00+00:00",
        )
        request = _HermesLifecycleCall(
            binding,
            context,
            event,
            "2026-10-19T00:01:00+00:00",
            _HermesLifecycleOptions(include_source_id=False),
        )
        result = await self._send_hermes_event(client, request)
        self.assertFalse(result.is_error, result.content)
        assert isinstance(result.content[0], TextContent)
        receipt = json.loads(result.content[0].text)
        self.assertEqual(receipt["status"], "processed")
        return replace(
            request,
            options=replace(request.options, accepted_receipt=receipt),
        )

    def _retire_mcp_binding(self, store: CuratorStore) -> None:
        """Deregister the re-enrolled source and retire its project binding."""
        for revision, status, transition_id in (
            (4, "deregistration_pending", "mcp-retire-pending"),
            (5, "deregistered", "mcp-retire-deregistered"),
        ):
            store.transition_consumer_binding(
                ConsumerBindingTransitionRequest(
                    project_id="mcp-project",
                    status=status,
                    rationale="Retire the disposable MCP project",
                    expected_revision=revision,
                    transition_id=transition_id,
                ),
                actor_id="host-subject",
            )
        store.retire_project(
            "mcp-project",
            actor_id="host-subject",
            rationale="Retire the disposable MCP project",
            expected_revision=1,
            transition_id="mcp-retire-project",
        )

    async def _assert_retired_hermes_behavior(
        self,
        client: Client,
        old_request: _HermesLifecycleCall,
        fresh_request: _HermesLifecycleCall,
    ) -> None:
        """Retain exact replay while denying unseen events and stale context."""
        retired_replay = await self._send_hermes_event(
            client,
            replace(
                fresh_request,
                options=replace(
                    fresh_request.options, include_source_id=True
                ),
            ),
        )
        self.assertFalse(retired_replay.is_error, retired_replay.content)
        assert isinstance(retired_replay.content[0], TextContent)
        self.assertEqual(
            json.loads(retired_replay.content[0].text),
            fresh_request.accepted_receipt,
        )
        unseen_request = replace(
            fresh_request,
            occurred_at="2026-10-19T00:02:00+00:00",
            options=replace(
                fresh_request.options,
                event_id_override="unseen-event-after-retirement",
                source_sequence=2,
                include_source_id=False,
                accepted_receipt=None,
            ),
        )
        unseen = await self._send_hermes_event(client, unseen_request)
        self.assertTrue(unseen.is_error)
        missing_context = await self._send_hermes_event(
            client,
            replace(
                old_request,
                options=replace(
                    old_request.options,
                    durable_event=False,
                    include_source_id=False,
                ),
            ),
        )
        self.assertTrue(missing_context.is_error)
        wrong_profile = await client.call_tool(
            "hermes_goal_bind",
            {"goal_id": old_request.binding.goal_id},
            meta={
                "hermes/profile_id": "another-profile",
                "hermes/session_id": old_request.binding.session_id,
            },
        )
        self.assertTrue(wrong_profile.is_error)

    async def _send_hermes_event(
        self, client: Client, request: _HermesLifecycleCall
    ) -> Any:
        """Send a bounded lifecycle envelope with selected trusted metadata."""
        metadata: dict[str, Any] = {
            "hermes/profile_id": request.profile_id or request.binding.profile_id,
            "hermes/session_id": request.binding.session_id,
        }
        if request.durable_event:
            metadata["hermes/durable_event"] = True
        arguments: dict[str, object] = {
            "event_type": "codex:turn:start",
            "goal_id": request.goal_id or request.binding.goal_id,
            "event_id": request.event_id_override or request.event.event_id,
            "source_sequence": request.source_sequence,
            "occurred_at": request.occurred_at,
            "context": request.context,
        }
        if request.include_source_id:
            arguments["source_id"] = request.binding.source_id
        return await client.call_tool(
            "hermes_codex_event",
            arguments,
            meta=cast(RequestParamsMeta, metadata),
        )
