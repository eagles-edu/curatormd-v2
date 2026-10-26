"""Protocol-level MCP tool tests using the SDK's in-memory client."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from mcp import Client
from mcp.types import TextContent

from evidence_fixtures import attest_test_evidence
from project_fixtures import (
    bind_test_project,
    configure_stdio_consumer,
    create_consumer_repo,
)
from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CodexGoalBinding,
    CuratorStore,
    EvidenceRef,
    EvidenceVerificationContext,
    InMemoryTokenBucket,
    ProjectAction,
    ProjectPlugin,
    ReviewDecision,
    build_mcp_server,
)
from curatormd_v2.mcp_server import safe_tool_handler
from curatormd_v2.mcp_server import (
    _HermesRequestCaller,  # pyright: ignore[reportPrivateUsage]
    _hermes_identity_middleware,  # pyright: ignore[reportPrivateUsage]
    HermesContextOptions,
    hermes_subject_context,
)
from curatormd_v2.events import EventEnvelope


@dataclass(frozen=True)
class _HermesLifecycleOptions:
    """Optional bounded fields for one Hermes lifecycle delivery."""

    source_sequence: int = 1
    goal_id: str | None = None
    profile_id: str | None = None
    durable_event: bool = True
    include_source_id: bool = True
    event_id_override: str | None = None
    accepted_receipt: dict[str, Any] | None = None


@dataclass(frozen=True)
class _HermesLifecycleCall:
    """One content-free lifecycle request and its trusted host context."""

    binding: CodexGoalBinding
    context: dict[str, str]
    event: EventEnvelope
    occurred_at: str
    options: _HermesLifecycleOptions = _HermesLifecycleOptions()

    @property
    def source_sequence(self) -> int:
        """Return the request's delivery sequence."""
        return self.options.source_sequence

    @property
    def goal_id(self) -> str | None:
        """Return an explicitly overridden goal ID, if present."""
        return self.options.goal_id

    @property
    def profile_id(self) -> str | None:
        """Return an explicitly overridden profile ID, if present."""
        return self.options.profile_id

    @property
    def durable_event(self) -> bool:
        """Return whether the host marks this delivery as durable."""
        return self.options.durable_event

    @property
    def include_source_id(self) -> bool:
        """Return whether the event includes its source epoch identifier."""
        return self.options.include_source_id

    @property
    def event_id_override(self) -> str | None:
        """Return an event ID override, if supplied by this scenario."""
        return self.options.event_id_override

    @property
    def accepted_receipt(self) -> dict[str, Any] | None:
        """Return the original receipt used for exact replay assertions."""
        return self.options.accepted_receipt


@dataclass(frozen=True)
class _McpSdePaths:
    """Paths owned by one disposable MCP SDE scenario."""

    root: Path
    database: Path
    staging: Path
    history: Path


@dataclass(frozen=True)
class _McpSdeArtifacts:
    """Transient artifact state used to assert review-scoped cleanup."""

    staged: Path
    unheld_staged: Path
    unheld_payload: bytes


@dataclass(frozen=True)
class _McpSdeWorkflow:
    """Disposable state shared across the MCP SDE and purge lifecycle."""

    paths: _McpSdePaths
    store: CuratorStore
    plugin: ProjectPlugin
    artifacts: _McpSdeArtifacts

    @property
    def root(self) -> Path:
        """Return the disposable consumer root."""
        return self.paths.root

    @property
    def database(self) -> Path:
        """Return the disposable SQLite database path."""
        return self.paths.database

    @property
    def staging(self) -> Path:
        """Return the disposable staging root."""
        return self.paths.staging

    @property
    def history(self) -> Path:
        """Return the canonical Markdown target."""
        return self.paths.history

    @property
    def staged(self) -> Path:
        """Return the held review artifact path."""
        return self.artifacts.staged

    @property
    def unheld_staged(self) -> Path:
        """Return the unheld transient artifact path."""
        return self.artifacts.unheld_staged

    @property
    def unheld_payload(self) -> bytes:
        """Return the transient test-only canary payload."""
        return self.artifacts.unheld_payload


@dataclass(frozen=True)
class _McpSdeReview:
    """Candidate, disposition receipt, and the artifact tied to that review."""

    candidate: dict[str, Any]
    receipt: dict[str, Any]
    artifact: Path


@dataclass(frozen=True)
class _McpClientWorkflow:
    """Disposable plugin/server state for the broad MCP lifecycle contract."""

    store: CuratorStore
    plugin: ProjectPlugin
    candidate_id: str
    server: Any


class AllowProject:  # pylint: disable=too-few-public-methods
    """Permit read/write operations for the test's scoped host identity."""

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Authorize only the test host's operations in the bound project."""

        return (
            caller.subject_id == "host-subject"
            and project_id == "mcp-project"
            and action in (
                ProjectAction.READ,
                ProjectAction.WRITE,
                ProjectAction.REVIEW,
                ProjectAction.RETENTION_HOLD_RELEASE,
            )
        )


class DenyProject:  # pylint: disable=too-few-public-methods
    """Deny every project action for negative authorization regressions."""

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Return false for every caller and scope."""

        del caller, project_id, action
        return False


class TestVerifier:  # pylint: disable=too-few-public-methods
    """Accept only an explicit MCP integration-test evidence locator."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest the explicit MCP test-proof locator."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:mcp"
            else None
        )


class TestReviewAuthorizer:  # pylint: disable=too-few-public-methods
    """Bind MCP reviews to the authenticated host identity in this fixture."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Return the host identity only for authenticated MCP review calls."""

        del project_id, candidate_id, decision
        if authenticated_subject != "host-subject":
            raise PermissionError("MCP reviewer is not authenticated")
        return authenticated_subject

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Return the authenticated host identity for corrections."""

        del project_id, candidate_id
        if authenticated_subject != "host-subject":
            raise PermissionError("MCP correction reviewer is not authenticated")
        return authenticated_subject

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute quality feedback to the authenticated MCP host subject."""

        return self.authorize_correction(project_id, candidate_id, authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize only the authenticated host's exact hold-release action."""

        del project_id, receipt_id, path, rationale
        if authenticated_subject != "host-subject":
            raise PermissionError("MCP hold-release reviewer is not authenticated")
        return authenticated_subject

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Return the authenticated host identity for an expiry approval."""

        del project_id, manifest_sha256
        if authenticated_subject != "host-subject":
            raise PermissionError("MCP expiry reviewer is not authenticated")
        return authenticated_subject

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Return the authenticated host identity for cleanup approval."""

        del project_id, receipt_id, manifest_sha256
        if authenticated_subject != "host-subject":
            raise PermissionError("MCP cleanup reviewer is not authenticated")
        return authenticated_subject


class McpServerTestSupport(unittest.TestCase):
    """Shared MCP client assertion helper for focused test modules."""

    async def _call_mcp_json(
        self, client: Client, name: str, arguments: dict[str, object]
    ) -> Any:
        """Call a successful MCP tool and decode its JSON result."""
        result = await client.call_tool(name, arguments)
        self.assertFalse(result.is_error, f"{name} failed")
        content = result.content[0]
        assert isinstance(content, TextContent)
        return json.loads(content.text)

    def _bind_reviewable_mcp_project(
        self, store: CuratorStore, root: Path
    ) -> ProjectPlugin:
        """Bind the standard authenticated reviewer fixture for MCP flows."""
        return bind_test_project(
            store,
            root,
            "host-subject",
            evidence_verifier=TestVerifier(),
            review_authorizer=TestReviewAuthorizer(),
        )

    def _assert_sde_instruction_contract(self, instructions: str) -> None:
        """Check safety guidance exposed alongside the MCP SDE tools."""
        for required_guidance in (
            "observable success criteria",
            "record deduplicated compact fact bullets",
            "healthy readiness are not proof",
            "verified criteria separately from open criteria",
            "Store a distinct cleanup receipt and project it",
            "unapproved or failed cleanup visibly pending",
        ):
            self.assertIn(required_guidance, instructions)


class McpServerTests(McpServerTestSupport):
    """Exercise schema discovery and goal lifecycle over real MCP framing."""

    def test_mcp_identity_subject_is_request_scoped_and_required(self) -> None:
        """Bind the host subject to one request and deny calls without it."""

        middleware = cast(
            Any,
            _hermes_identity_middleware(
                HermesContextOptions("renew-ssl-coding", require_authenticated_subject=True)
            ),
        )
        metadata = {
            "hermes/profile_id": "renew-ssl-coding",
            "hermes/session_id": "session-1",
            "hermes/authenticated_subject": (
                'auth:v1:["oidc","https://issuer.example","user-42"]'
            ),
        }
        observed: list[str | None] = []

        async def accepted_call(_ctx: object) -> str:
            observed.append(hermes_subject_context.get())
            return "accepted"

        result = asyncio.run(
            middleware(SimpleNamespace(method="tools/call", meta=metadata), accepted_call)
        )
        expected_subject = "hermes-auth:" + hashlib.sha256(
            str(metadata["hermes/authenticated_subject"]).encode("utf-8")
        ).hexdigest()
        self.assertEqual(result, "accepted")
        self.assertEqual(observed, [expected_subject])
        self.assertIsNone(hermes_subject_context.get())

        caller = _HermesRequestCaller("service-fallback", "renew-ssl-coding")
        caller_token = hermes_subject_context.set(expected_subject)
        try:
            self.assertEqual(caller.subject_id, expected_subject)
        finally:
            hermes_subject_context.reset(caller_token)

        denied = asyncio.run(
            middleware(
                SimpleNamespace(
                    method="tools/call",
                    meta={
                        "hermes/profile_id": "renew-ssl-coding",
                        "hermes/session_id": "session-1",
                    },
                ),
                accepted_call,
            )
        )
        self.assertTrue(denied.is_error)
        self.assertEqual(json.loads(denied.content[0].text)["code"], "unauthenticated")

        invalid = asyncio.run(
            middleware(
                SimpleNamespace(
                    method="tools/call",
                    meta={**metadata, "hermes/authenticated_subject": "auth:v1:not-json"},
                ),
                accepted_call,
            )
        )
        self.assertTrue(invalid.is_error)
        self.assertEqual(json.loads(invalid.content[0].text)["code"], "unauthenticated")

    def test_dynamic_exception_type_name_is_not_logged_or_returned(self) -> None:
        """Do not trust adapter-controlled exception class names in diagnostics."""

        exception_type_canary = "PRIVATE_EXCEPTION_TYPE_CANARY"
        exception_message_canary = "PRIVATE_EXCEPTION_MESSAGE_CANARY"
        private_exception_type = type(exception_type_canary, (RuntimeError,), {})

        def fail_with_private_exception() -> None:
            raise private_exception_type(exception_message_canary)

        handler = safe_tool_handler(fail_with_private_exception)
        with self.assertLogs("curatormd_v2.mcp_server", level="WARNING") as captured:
            result = handler()

        self.assertTrue(result.is_error)
        self.assertNotIn(exception_type_canary, str(result.content))
        self.assertNotIn(exception_message_canary, str(result.content))
        log_output = "\n".join(captured.output)
        self.assertIn("exception_type=unexpected_exception", log_output)
        self.assertNotIn(exception_type_canary, log_output)
        self.assertNotIn(exception_message_canary, log_output)

    def test_project_health_sqlite_failure_serializes_unknown_over_mcp(self) -> None:
        """Do not turn an unavailable health snapshot into wire-level zeros."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] Health transport test\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2.toml").write_text(
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
            (root / ".curatormd-v2.toml").chmod(0o600)
            store = CuratorStore(Path(temporary) / "global.sqlite3")
            try:
                plugin = bind_test_project(store, root, "host-subject")
                api = AuthenticatedCuratorAPI(
                    {"mcp-project": plugin}, AllowProject(), InMemoryTokenBucket()
                )
                server = build_mcp_server(
                    api,
                    AuthenticatedCaller("host-subject"),
                    "mcp-project",
                    "health-failure-test",
                )

                async def exercise() -> None:
                    async with Client(server, raise_exceptions=True) as client:
                        health_result = await client.call_tool("project_health", {})
                        self.assertFalse(health_result.is_error)
                        health_content = health_result.content[0]
                        assert isinstance(health_content, TextContent)
                        health = json.loads(health_content.text)
                        self.assertEqual(health["status"], "unknown")
                        self.assertFalse(health["database_observation_complete"])
                        self.assertIsNone(health["database_observed_at"])
                        self.assertIsNone(health["event_received_count"])
                        self.assertIsNone(health["operational_counts"])
                        self.assertIn(
                            "database_observation_failed", health["gate_codes"]
                        )
                        metrics_result = await client.call_tool("project_metrics", {})
                        self.assertFalse(metrics_result.is_error)
                        metrics_content = metrics_result.content[0]
                        assert isinstance(metrics_content, TextContent)
                        self.assertIn(
                            'curatormd_database_observation_complete'
                            '{project_id="mcp-project"} 0',
                            metrics_content.text,
                        )
                        self.assertIn(
                            'state="unknown"} 1', metrics_content.text
                        )
                        self.assertNotIn("curatormd_event_queue_received", metrics_content.text)
                        self.assertNotIn("private SQLite diagnostic", health_content.text)
                        self.assertNotIn("private SQLite diagnostic", metrics_content.text)

                with patch.object(
                    plugin,
                    "operational_health_inputs",
                    side_effect=sqlite3.OperationalError("private SQLite diagnostic"),
                ):
                    asyncio.run(exercise())
            finally:
                store.close()

    def test_stdio_transport_uses_host_bound_identity_without_tool_identity_args(self) -> None:
        """Exercise an actual MCP stdio child process with no caller parameters."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            parameters = configure_stdio_consumer(root, "stdio-project")

            async def exercise() -> None:
                async with Client(parameters, raise_exceptions=True) as client:
                    tool_result = await client.list_tools()
                    tool_names = [tool.name for tool in tool_result.tools]
                    self.assertTrue(
                        {
                            "host_inventory",
                            "host_proposals",
                            "host_cleanup",
                            "host_cleanup_receipts",
                            "host_cleanup_reconcile",
                        }.isdisjoint(tool_names)
                    )
                    goal_start_tool = next(
                        tool for tool in tool_result.tools if tool.name == "goal_start"
                    )
                    self.assertNotIn("project_id", goal_start_tool.input_schema["properties"])
                    self.assertNotIn("caller", goal_start_tool.input_schema["properties"])
                    started = await client.call_tool(
                        "goal_start",
                        {
                            "event_id": "stdio-event-1",
                            "goal_id": "stdio-goal-1",
                            "problem": "Exercise the real MCP stdio transport",
                            "success_criteria": [
                                {
                                    "criterion_id": "connected",
                                    "description": "The stdio client reads the goal",
                                }
                            ],
                        },
                    )
                    self.assertFalse(started.is_error)
                    status = await client.call_tool(
                        "goal_status", {"goal_id": "stdio-goal-1"}
                    )
                    status_content = status.content[0]
                    assert isinstance(status_content, TextContent)
                    value = json.loads(status_content.text)
                    self.assertEqual(value["goal"]["project_id"], "stdio-project")
                    self.assertEqual(value["goal"]["status"], "planned")
                    activated = await client.call_tool(
                        "goal_activate",
                        {
                            "event_id": "stdio-event-2",
                            "goal_id": "stdio-goal-1",
                            "reason": "The user approved execution",
                            "expected_lifecycle_revision": 1,
                        },
                    )
                    self.assertFalse(activated.is_error)
                    active_status = await client.call_tool(
                        "goal_status", {"goal_id": "stdio-goal-1"}
                    )
                    active_content = active_status.content[0]
                    assert isinstance(active_content, TextContent)
                    active_value = json.loads(active_content.text)
                    self.assertEqual(active_value["goal"]["status"], "active")
                    self.assertIn("goal_activate", tool_names)
                    self.assertIn("goal_persist", tool_names)
                    self.assertIn("goal_reconcile", tool_names)
                    self.assertIn("project_reconcile", tool_names)
                    self.assertIn("artifact_purge_status", tool_names)
                    self.assertIn("artifact_cleanup_approve", tool_names)
                    self.assertIn("sde_review_queue_cards", tool_names)

            asyncio.run(exercise())

    def test_sensitive_event_is_absent_from_mcp_errors_logs_and_storage(self) -> None:
        """Keep rejected credential-like content out of MCP errors and storage."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] Privacy boundary\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2.toml").write_text(
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
            (root / ".curatormd-v2.toml").chmod(0o600)
            database_path = Path(temporary) / "global.sqlite3"
            store = CuratorStore(database_path)
            try:
                secrets = self._assert_sensitive_event_rejected_without_echo(
                    root, store
                )
                self._assert_sensitive_event_absent_from_storage(
                    secrets, database_path, root
                )
            finally:
                store.close()

    def _assert_sensitive_event_rejected_without_echo(
        self, root: Path, store: CuratorStore
    ) -> tuple[str, ...]:
        """Exercise MCP and logs while returning the test-only canary for scans."""
        plugin = bind_test_project(store, root, "host-subject")
        caller = AuthenticatedCaller("host-subject")
        api = AuthenticatedCuratorAPI(
            {"mcp-project": plugin}, AllowProject(), InMemoryTokenBucket()
        )
        server = build_mcp_server(api, caller, "mcp-project", "privacy-test")
        secrets = (
            "ghs_1234567890_" + "A" * 480 + ".eyJhbGciOiJIUzI1NiJ9.signature",
            "TXT value: " + "B" * 43,
        )

        async def exercise() -> None:
            async with Client(server, raise_exceptions=True) as client:
                for index, secret in enumerate(secrets):
                    payload = json.dumps(
                        {
                            "schema_version": 1,
                            "event_id": f"sensitive-mcp-event-{index}",
                            "project_id": "mcp-project",
                            "source_id": "privacy-test",
                            "source_sequence": index + 1,
                            "occurred_at": "2026-10-20T00:00:00Z",
                            "event_type": "goal.started",
                            "payload": {
                                "goal_id": f"sensitive-mcp-goal-{index}",
                                "problem": f"Sensitive input {secret}",
                                "success_criteria": [
                                    {"criterion_id": "done", "description": "No leak"}
                                ],
                            },
                        }
                    )
                    result = await client.call_tool(
                        "event_ingest", {"event_json": payload}
                    )
                    self.assertTrue(result.is_error)
                    content = result.content[0]
                    assert isinstance(content, TextContent)
                    self.assertNotIn(secret, content.text)

        with self.assertLogs("curatormd_v2.mcp_server", level="WARNING") as captured:
            asyncio.run(exercise())
        self.assertTrue(captured.output)
        log_output = "\n".join(captured.output)
        for secret in secrets:
            self.assertNotIn(secret, log_output)
        return secrets

    def _assert_sensitive_event_absent_from_storage(
        self, secrets: tuple[str, ...], database_path: Path, root: Path
    ) -> None:
        """Scan SQLite sidecars, canonical Markdown, and staging bytes."""
        secret_bytes = tuple(secret.encode("utf-8") for secret in secrets)
        for suffix in ("", "-wal", "-shm", "-journal"):
            database_file = Path(f"{database_path}{suffix}")
            if database_file.exists():
                content = database_file.read_bytes()
                for secret in secret_bytes:
                    self.assertNotIn(secret, content)
        history = root / "persistence" / "HISTORY.md"
        history_bytes = history.read_bytes()
        for secret in secret_bytes:
            self.assertNotIn(secret, history_bytes)
        staging = root / ".curatormd-v2" / "staging"
        for staged_file in staging.rglob("*"):
            if staged_file.is_file():
                content = staged_file.read_bytes()
                for secret in secret_bytes:
                    self.assertNotIn(secret, content)



if __name__ == "__main__":
    unittest.main()
