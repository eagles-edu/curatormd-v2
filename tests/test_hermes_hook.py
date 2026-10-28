"""Project plugin adapter tests for Hermes' durable Codex outbox."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict, Unpack, cast

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.types import TextContent

from project_fixtures import (
    bind_test_project,
    configure_stdio_consumer,
)
from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CodexGoalBinding,
    CuratorStore,
    EventDisposition,
    FactKind,
    GoalActivityObserved,
    GoalStatus,
    InMemoryTokenBucket,
    ProjectAction,
    ProjectStatusChangeRequest,
    SuccessCriterion,
    build_mcp_server,
    codex_hook_to_event,
)
from curatormd_v2.hermes_hook import HermesHook, build_hermes_hook_handler
from curatormd_v2.hermes_context import hermes_subject_grant_id

FOREIGN_GOAL_ID = "foreign-project-goal"


def _recording_hook_handler(
    root: Path,
) -> tuple[
    HermesHook,
    list[tuple[str, str, dict[str, object], dict[str, object]]],
]:
    """Build one hook that records the exact managed-MCP call."""

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
            "result": {
                "project_id": "project-a",
                "event_id": "hermes-event-1",
                "status": "processed",
            },
        }

    return build_hermes_hook_handler(root, "curator-project-a", call_mcp=call_mcp), calls


def _response_hook_handler(
    root: Path,
    response: dict[str, object],
) -> HermesHook:
    """Build a hook with one fixed fake MCP response."""

    def call_mcp(*_args: object, **_kwargs: object) -> dict[str, object]:
        return response

    return build_hermes_hook_handler(
        root,
        "curator-project-a",
        call_mcp=call_mcp,
    )


def _lose_first_successful_reply(
    call_tool: Callable[..., Awaitable[str]],
) -> Callable[..., Awaitable[str]]:
    """Simulate a lost MCP response after the server commits its receipt."""

    response_lost = False

    async def call_with_lost_reply(
        arguments: dict[str, object], **kwargs: object
    ) -> str:
        nonlocal response_lost
        response = await call_tool(arguments, **kwargs)
        decoded = json.loads(response)
        if not response_lost and isinstance(decoded, dict) and "result" in decoded:
            response_lost = True
            return json.dumps({"error": "simulated lost response"})
        return response

    return call_with_lost_reply


def _raising_hook_handler(
    root: Path,
) -> HermesHook:
    """Build a hook whose adapter raises a private diagnostic."""

    def call_mcp(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private adapter diagnostic")

    return build_hermes_hook_handler(
        root,
        "curator-project-a",
        call_mcp=call_mcp,
    )


def _assert_recorded_hook_call(
    test_case: unittest.TestCase,
    calls: list[tuple[str, str, dict[str, object], dict[str, object]]],
) -> None:
    """Check the hook forwards only the bounded event fields."""

    test_case.assertEqual(len(calls), 1)
    server, tool, arguments, kwargs = calls[0]
    test_case.assertEqual(server, "curator-project-a")
    test_case.assertEqual(tool, "hermes_codex_event")
    test_case.assertEqual(
        kwargs,
        {
            "timeout": 30.0,
            "session_id": "session-1",
            "hermes_durable_event": True,
        },
    )
    test_case.assertEqual(arguments["event_type"], "codex:turn:start")
    test_case.assertEqual(arguments["goal_id"], "goal-1")
    test_case.assertEqual(
        arguments["context"],
        {"attempt_id": "attempt-1", "session_id": "session-1"},
    )


def _assert_applied_event_receipt(
    test_case: unittest.TestCase,
    store: CuratorStore,
    project_id: str,
    event_id: str,
) -> None:
    """Assert the event has a durable applied receipt."""

    test_case.assertEqual(
        store.event_receipt(project_id, event_id).disposition,
        EventDisposition.APPLIED,
    )


def _create_foreign_consumer_goal(root: Path, database: Path) -> None:
    """Create a second configured project and one isolated goal in the test store."""

    configure_stdio_consumer(root, "foreign-project")
    store = CuratorStore(database)
    try:
        plugin = bind_test_project(store, root, "host-subject")
        plugin.service.goal_start(
            "A goal owned by the other configured project",
            (SuccessCriterion("private", "Its facts remain project-scoped"),),
            goal_id=FOREIGN_GOAL_ID,
        )
    finally:
        store.close()


@dataclass(frozen=True, slots=True)
class _StdioMcpFixture:
    """Bound identities and paths for the separate-process hook test."""

    root: Path
    database: Path
    parameters: StdioServerParameters
    profile_id: str
    session_id: str
    goal_id: str
    hook_context: dict[str, object]

    @property
    def source_id(self) -> str:
        """Return the durable Hermes source ID from its exact event context."""

        return str(self.hook_context["source_id"])

    @property
    def event_id(self) -> str:
        """Return the stable Hermes event ID from its exact event context."""

        return str(self.hook_context["event_id"])


class _HermesCallOptions(TypedDict):
    """Required context passed by the hook to its managed-MCP callback."""

    timeout: float
    session_id: str
    hermes_durable_event: bool


def _make_stdio_mcp_fixture(temporary: Path) -> _StdioMcpFixture:
    """Create stable event identity and paths for one isolated stdio test."""

    root = temporary / "consumer"
    parameters = configure_stdio_consumer(root, "stdio-project")
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
    return _StdioMcpFixture(
        root,
        database,
        parameters,
        profile_id,
        session_id,
        goal_id,
        hook_context,
    )


class _OnlyProject:  # pylint: disable=too-few-public-methods
    """Authorize only the bound test project for this process fixture."""

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Reject every identity or project outside the fixture scope."""

        del action
        return caller.subject_id == "host-subject" and project_id == "project-a"


class HermesHookAdapterTests(unittest.TestCase):
    """Bind only matching project events and acknowledge only durable receipts."""

    def test_authenticated_hermes_subject_maps_to_an_opaque_grant_id(self) -> None:
        """Provider identities are stable in grants without storing the user claim."""

        subject = 'auth:v1:["oidc","https://issuer.example","user-42"]'
        expected = "hermes-auth:" + hashlib.sha256(subject.encode("utf-8")).hexdigest()
        self.assertEqual(hermes_subject_grant_id(subject), expected)
        self.assertEqual(hermes_subject_grant_id("local-uid:1000"), "local-uid:1000")
        for invalid in (
            'auth:v1:["oidc","https://issuer.example","user-42", "extra"]',
            'auth:v1:["oidc", "https://issuer.example", "user-42"]',
            "auth:v1:not-json",
            "unbound",
            "user with spaces",
        ):
            self.assertIsNone(hermes_subject_grant_id(invalid))

    def test_projects_route_to_the_bound_mcp_tool_and_require_processed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            configure_stdio_consumer(root, "project-a")
            handle, calls = _recording_hook_handler(root)
            event: dict[str, Any] = {
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

            self.assertIsNone(
                asyncio.run(
                    handle("codex:turn:start", {**event, "project_id": "project-b"})
                )
            )
            self.assertTrue(asyncio.run(handle("codex:turn:start", event)))
            _assert_recorded_hook_call(self, calls)

            for stale_receipt in (
                {
                    "project_id": "project-a",
                    "event_id": "different-event",
                    "status": "processed",
                },
                {
                    "project_id": "project-b",
                    "event_id": "hermes-event-1",
                    "status": "duplicate",
                },
            ):
                stale_handler = _response_hook_handler(
                    root, {"ok": True, "result": stale_receipt}
                )
                self.assertFalse(
                    asyncio.run(stale_handler("codex:turn:start", event))
                )

            failing = _response_hook_handler(
                root,
                {"ok": False, "error": "retry"},
            )
            self.assertFalse(asyncio.run(failing("codex:turn:start", event)))

            failing_exception = _raising_hook_handler(root)
            self.assertFalse(
                asyncio.run(failing_exception("codex:turn:start", event))
            )

    def test_work_summary_is_forwarded_only_for_the_configured_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            configure_stdio_consumer(root, "project-a")
            handle, calls = _recording_hook_handler(root)
            from curatormd_v2.project_config import ProjectConfig

            fingerprint = ProjectConfig.load(root).repository_fingerprint
            summary = json.dumps({
                "schema_version": 1,
                "repository_fingerprint": fingerprint,
                "changed_files": [{"path": "src/change.py", "change": "update"}],
                "omitted_files": 0,
                "checks": [],
                "omitted_checks": 0,
            })
            event: dict[str, Any] = {
                "project_id": "project-a",
                "goal_id": "goal-1",
                "event_id": "hermes-event-1",
                "source_sequence": 4,
                "occurred_at": "2026-10-19T00:00:00+00:00",
                "attempt_id": "attempt-1",
                "session_id": "session-1",
                "turn_id": "turn-1",
                "outcome": "completed",
                "work_summary_json": summary,
            }

            self.assertTrue(asyncio.run(handle("codex:turn:end", event)))
            forwarded_context = cast(dict[str, object], calls[-1][2]["context"])
            self.assertEqual(
                forwarded_context["work_summary_json"], summary
            )

            mismatched = json.loads(summary)
            mismatched["repository_fingerprint"] = "b" * 64
            event["work_summary_json"] = json.dumps(mismatched)
            self.assertTrue(asyncio.run(handle("codex:turn:end", event)))
            forwarded_context = cast(dict[str, object], calls[-1][2]["context"])
            self.assertNotIn("work_summary_json", forwarded_context)

    def test_lost_event_response_replays_receipt_after_project_suspension(self) -> None:
        """A lost reply is acked only by exact receipt replay after suspension."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            configure_stdio_consumer(root, "project-a")
            db_path = Path(temporary) / "global.sqlite3"
            store = CuratorStore(db_path)
            try:
                plugin = bind_test_project(store, root, "host-subject")
                caller = AuthenticatedCaller("host-subject")
                api = AuthenticatedCuratorAPI(
                    {"project-a": plugin}, _OnlyProject(), InMemoryTokenBucket()
                )
                server = build_mcp_server(api, caller, "project-a", "hermes-e2e")
                profile = "host-subject"
                session_id = "session-e2e"

                async def drive() -> None:
                    async with Client(server, raise_exceptions=True) as client:
                        self.assertFalse((await client.call_tool(
                            "goal_start",
                            {
                                "event_id": "hermes-e2e-goal-start",
                                "goal_id": "hermes-e2e-goal",
                                "problem": "Exercise durable Hermes event ingestion",
                                "success_criteria": [
                                    {
                                        "criterion_id": "c1",
                                        "description": "A typed fact is recorded",
                                    }
                                ],
                                "source_sequence": 1,
                            },
                        )).is_error)
                        self.assertFalse((await client.call_tool(
                            "goal_activate",
                            {
                                "event_id": "hermes-e2e-goal-active",
                                "goal_id": "hermes-e2e-goal",
                                "reason": "Integration test accepted",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 2,
                            },
                        )).is_error)
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
                                + hashlib.sha256(
                                    f"{profile}\0project-a".encode()
                                ).hexdigest(),
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
                            root,
                            "curator-project-a",
                            call_tool=_lose_first_successful_reply(call_tool),
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
                        self.assertFalse(await handle("codex:turn:start", hook_context))
                        _assert_applied_event_receipt(
                            self, store, "project-a", event.event_id
                        )
                        snapshot = api.goal_status(caller, "project-a", "hermes-e2e-goal")
                        self.assertEqual(snapshot.goal.status, GoalStatus.ACTIVE)
                        self.assertEqual(snapshot.facts[-1].kind, FactKind.INTENT)
                        _assert_applied_event_receipt(
                            self, store, "project-a", event.event_id
                        )

                        self.assertFalse((await client.call_tool(
                            "goal_defer",
                            {
                                "event_id": "hermes-e2e-goal-deferred",
                                "goal_id": "hermes-e2e-goal",
                                "reason": "Wait for the consumer test gate",
                                "next_action": "Resume the integration test",
                                "expected_lifecycle_revision": 2,
                                "source_sequence": 3,
                            },
                        )).is_error)
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

                        registration = store.get_project_registration("project-a")
                        store.set_project_status(
                            ProjectStatusChangeRequest(
                                project_id="project-a",
                                status="suspended",
                                rationale="Exercise exact outbox retry after suspension",
                                expected_revision=registration.revision,
                                transition_id="suspend-after-hermes-receipt-1",
                            ),
                            "test-operator",
                        )
                        self.assertTrue(
                            await handle("codex:turn:start", hook_context)
                        )
                        changed_receipt_context = {
                            **hook_context,
                            "occurred_at": "2026-10-20T00:00:01+00:00",
                        }
                        self.assertFalse(
                            await handle(
                                "codex:turn:start", changed_receipt_context
                            )
                        )

                asyncio.run(drive())
            finally:
                store.close()

    def test_adapter_delivers_to_a_separate_durable_mcp_process(self) -> None:
        """Route a Hermes envelope over stdio and reopen the child's receipt."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = _make_stdio_mcp_fixture(Path(temporary))
            _create_foreign_consumer_goal(
                Path(temporary) / "foreign-consumer", fixture.database
            )
            asyncio.run(self._exercise_stdio_mcp(fixture))
            with CuratorStore(fixture.database) as store:
                self.assertEqual(
                    store.event_receipt("stdio-project", fixture.event_id).disposition,
                    EventDisposition.APPLIED,
                )
                facts = store.list_facts(fixture.goal_id, "stdio-project")
                self.assertEqual(len(facts), 2)
                self.assertTrue(all(fact.kind is FactKind.INTENT for fact in facts))
                self.assertEqual(
                    facts[-1].bullet,
                    "Codex turn started for the explicitly bound goal.",
                )
                self.assertEqual(
                    store.list_facts(FOREIGN_GOAL_ID, "foreign-project"), ()
                )

    async def _exercise_stdio_mcp(self, fixture: _StdioMcpFixture) -> None:
        """Run the durable outbox event through a separate stdio MCP process."""

        async with Client(fixture.parameters, raise_exceptions=True) as client:
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

            self.assertEqual(
                (
                    await call_json(
                        "goal_start",
                        {
                            "event_id": "stdio-goal-start",
                            "goal_id": fixture.goal_id,
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
                )["status"],
                "processed",
            )
            self.assertEqual(
                (
                    await call_json(
                        "goal_activate",
                        {
                            "event_id": "stdio-goal-activate",
                            "goal_id": fixture.goal_id,
                            "reason": "Activate the synthetic integration goal",
                            "expected_lifecycle_revision": 1,
                            "source_sequence": 2,
                        },
                    )
                )["status"],
                "processed",
            )
            self.assertFalse(
                (
                    await client.call_tool(
                        "hermes_goal_bind",
                        {"goal_id": fixture.goal_id},
                        meta={
                            "hermes/profile_id": fixture.profile_id,
                            "hermes/session_id": fixture.session_id,
                        },
                    )
                ).is_error
            )

            def call_curator(
                server: str,
                tool: str,
                arguments: dict[str, object],
                **kwargs: Unpack[_HermesCallOptions],
            ) -> dict[str, object]:
                self.assertEqual(server, "curator-stdio-project")
                self.assertEqual(tool, "hermes_codex_event")
                self.assertTrue(kwargs["hermes_durable_event"])
                response_future = asyncio.run_coroutine_threadsafe(
                    client.call_tool(
                        tool,
                        arguments,
                        meta={
                            "hermes/profile_id": fixture.profile_id,
                            "hermes/session_id": kwargs["session_id"],
                            "hermes/durable_event": kwargs["hermes_durable_event"],
                        },
                    ),
                    loop,
                )
                response = response_future.result(timeout=kwargs["timeout"])
                content = response.content[0]
                if response.is_error or not isinstance(content, TextContent):
                    return {"ok": False, "error": "stdio event delivery failed"}
                return {"ok": True, "result": content.text}

            handler = build_hermes_hook_handler(
                fixture.root,
                "curator-stdio-project",
                call_mcp=call_curator,
            )
            self.assertTrue(
                await handler("codex:turn:start", fixture.hook_context)
            )
            self.assertTrue(
                await handler("codex:turn:start", fixture.hook_context)
            )
            status = await call_json(
                "goal_status", {"goal_id": fixture.goal_id}
            )
            goal_value = status["goal"]
            assert isinstance(goal_value, dict)
            goal = cast(dict[str, object], goal_value)
            self.assertEqual(goal["status"], "active")
            facts_value = status["facts"]
            assert isinstance(facts_value, list)
            facts = cast(list[dict[str, object]], facts_value)
            self.assertEqual(len(facts), 2)
            self.assertEqual(
                facts[-1]["bullet"],
                "Codex turn started for the explicitly bound goal.",
            )

            foreign_attempt = "foreign-project-attempt"
            foreign_event_id = "hermes-" + hashlib.sha256(
                f"{fixture.source_id}\0codex:turn:start\0{foreign_attempt}".encode(
                    "utf-8"
                )
            ).hexdigest()
            foreign_event = {
                **fixture.hook_context,
                "goal_id": FOREIGN_GOAL_ID,
                "event_id": foreign_event_id,
                "source_sequence": 2,
                "attempt_id": foreign_attempt,
            }
            self.assertFalse(
                await handler("codex:turn:start", foreign_event)
            )
