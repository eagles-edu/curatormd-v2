"""Protocol-level MCP tool tests using the SDK's in-memory client."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
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
    ArtifactRef,
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CodexGoalBinding,
    ConsumerBindingTransitionRequest,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    InMemoryTokenBucket,
    Materiality,
    ProjectAction,
    PurgeError,
    PurgeFailureCode,
    ArtifactPurger,
    ReviewDecision,
    SuccessCriterion,
    build_mcp_server,
    codex_hook_to_event,
)
from curatormd_v2.mcp_server import safe_tool_handler


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


class McpServerTests(unittest.TestCase):
    """Exercise schema discovery and goal lifecycle over real MCP framing."""

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

    def test_hermes_goal_binding_requires_trusted_context_and_active_project_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] Bind current goal\n")
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
                caller = AuthenticatedCaller("host-subject")
                api = AuthenticatedCuratorAPI(
                    {"mcp-project": plugin}, AllowProject(), InMemoryTokenBucket()
                )
                server = build_mcp_server(api, caller, "mcp-project", "mcp-bind-test")

                async def exercise() -> None:
                    async with Client(server, raise_exceptions=True) as client:
                        binding_tool = next(
                            tool
                            for tool in (await client.list_tools()).tools
                            if tool.name == "hermes_goal_bind"
                        )
                        self.assertNotIn("ctx", binding_tool.input_schema["properties"])

                        self.assertFalse((await client.call_tool(
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
                        )).is_error)
                        self.assertTrue((await client.call_tool(
                            "hermes_goal_bind",
                            {"goal_id": "bind-goal"},
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-1",
                                "hermes/durable_event": True,
                            },
                        )).is_error)

                        self.assertFalse((await client.call_tool(
                            "goal_activate",
                            {
                                "event_id": "bind-goal-activate",
                                "goal_id": "bind-goal",
                                "reason": "Accepted for work",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 2,
                            },
                        )).is_error)
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
                        valid_payload = json.loads(valid.content[0].text)
                        self.assertEqual(valid_payload["binding"], "validated")
                        self.assertEqual(valid_payload["goal_id"], "bind-goal")

                        lifecycle_context = {
                            "attempt_id": "attempt-1",
                            "session_id": "session-1",
                        }
                        lifecycle_event = codex_hook_to_event(
                            "codex:turn:start",
                            lifecycle_context,
                            CodexGoalBinding(
                                profile_id="host-subject",
                                project_id="mcp-project",
                                session_id="session-1",
                                goal_id="bind-goal",
                                source_id="hermes-" + hashlib.sha256(
                                    b"host-subject\0mcp-project"
                                ).hexdigest(),
                            ),
                            source_sequence=1,
                            occurred_at="2026-10-19T00:00:00+00:00",
                        )
                        accepted = await client.call_tool(
                            "hermes_codex_event",
                            {
                                "event_type": "codex:turn:start",
                                "goal_id": "bind-goal",
                                "event_id": lifecycle_event.event_id,
                                "source_sequence": 1,
                                "occurred_at": "2026-10-19T00:00:00+00:00",
                                "context": lifecycle_context,
                            },
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-1",
                                "hermes/durable_event": True,
                            },
                        )
                        self.assertFalse(accepted.is_error)
                        assert isinstance(accepted.content[0], TextContent)
                        accepted_receipt = json.loads(accepted.content[0].text)
                        self.assertEqual(accepted_receipt["status"], "processed")

                        replay = await client.call_tool(
                            "hermes_codex_event",
                            {
                                "event_type": "codex:turn:start",
                                "goal_id": "bind-goal",
                                "event_id": lifecycle_event.event_id,
                                "source_sequence": 1,
                                "occurred_at": "2026-10-19T00:00:00+00:00",
                                "context": lifecycle_context,
                            },
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-1",
                                "hermes/durable_event": True,
                            },
                        )
                        self.assertFalse(replay.is_error)
                        assert isinstance(replay.content[0], TextContent)
                        self.assertEqual(
                            json.loads(replay.content[0].text)["status"], "processed"
                        )

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
                        stale = await client.call_tool(
                            "hermes_codex_event",
                            {
                                "event_type": "codex:turn:start",
                                "goal_id": "bind-goal",
                                "event_id": lifecycle_event.event_id,
                                "source_sequence": 1,
                                "occurred_at": "2026-10-19T00:00:00+00:00",
                                "context": lifecycle_context,
                            },
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-1",
                                "hermes/durable_event": True,
                            },
                        )
                        self.assertTrue(stale.is_error)

                        fresh_context = {
                            "attempt_id": "attempt-after-reenrollment",
                            "session_id": "session-2",
                        }
                        fresh_event = codex_hook_to_event(
                            "codex:turn:start",
                            fresh_context,
                            CodexGoalBinding(
                                profile_id="host-subject",
                                project_id="mcp-project",
                                session_id="session-2",
                                goal_id="bind-goal",
                                source_id="hermes-" + hashlib.sha256(
                                    b"host-subject\0mcp-project\0" b"2"
                                ).hexdigest(),
                            ),
                            source_sequence=1,
                            occurred_at="2026-10-19T00:01:00+00:00",
                        )
                        fresh = await client.call_tool(
                            "hermes_codex_event",
                            {
                                "event_type": "codex:turn:start",
                                "goal_id": "bind-goal",
                                "event_id": fresh_event.event_id,
                                "source_sequence": 1,
                                "occurred_at": "2026-10-19T00:01:00+00:00",
                                "context": fresh_context,
                            },
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-2",
                                "hermes/durable_event": True,
                            },
                        )
                        self.assertFalse(fresh.is_error)
                        assert isinstance(fresh.content[0], TextContent)
                        self.assertEqual(
                            json.loads(fresh.content[0].text)["status"], "processed"
                        )

                        self.assertTrue((await client.call_tool(
                            "hermes_codex_event",
                            {
                                "event_type": "codex:turn:start",
                                "goal_id": "bind-goal",
                                "event_id": lifecycle_event.event_id,
                                "source_sequence": 1,
                                "occurred_at": "2026-10-19T00:00:00+00:00",
                                "context": lifecycle_context,
                            },
                            meta={
                                "hermes/profile_id": "host-subject",
                                "hermes/session_id": "session-1",
                            },
                        )).is_error)

                        self.assertTrue((await client.call_tool(
                            "hermes_goal_bind",
                            {"goal_id": "bind-goal"},
                            meta={
                                "hermes/profile_id": "another-profile",
                                "hermes/session_id": "session-1",
                            },
                        )).is_error)

                asyncio.run(exercise())
            finally:
                store.close()

    def test_mcp_sde_assessment_review_persistence_and_purge_are_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            staging = root / ".curatormd-v2" / "staging"
            history = root / "persistence" / "HISTORY.md"
            history.write_text("# History\n")
            (root / "docs" / "tasks.md").write_text("- [ ] MCP SDE task\n")
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
                plugin = bind_test_project(
                    store,
                    root,
                    "host-subject",
                    evidence_verifier=TestVerifier(),
                    review_authorizer=TestReviewAuthorizer(),
                )
                caller = AuthenticatedCaller("host-subject")
                api = AuthenticatedCuratorAPI(
                    {"mcp-project": plugin},
                    AllowProject(),
                    InMemoryTokenBucket(),
                )
                server = build_mcp_server(
                    api, caller, "mcp-project", "mcp-sde-test-stream"
                )
                self._assert_sde_instruction_contract(
                    " ".join((server.instructions or "").split())
                )
                staged = (
                    staging
                    / "mcp-sde-goal"
                    / "import"
                    / "session-evidence.bin"
                )
                unheld_staged = (
                    staging
                    / "mcp-sde-goal"
                    / "scratch"
                    / "reviewed-transient-canary.txt"
                )
                unheld_payload = b"TRANSIENT_CANARY_PURGE_AFTER_CANONICAL_WRITE"

                async def exercise() -> tuple[str, str]:
                    async with Client(server, raise_exceptions=True) as client:
                        async def call_json(name: str, args: dict[str, object]):
                            result = await client.call_tool(name, args)
                            self.assertFalse(result.is_error, f"{name} failed")
                            content = result.content[0]
                            assert isinstance(content, TextContent)
                            return json.loads(content.text)

                        tools = await client.list_tools()
                        self.assertIn("sde_assess", [tool.name for tool in tools.tools])
                        started = await call_json(
                            "goal_start",
                            {
                                "event_id": "mcp-sde-event-1",
                                "goal_id": "mcp-sde-goal",
                                "problem": "Expose verified SDE assessment",
                                "success_criteria": [
                                    {
                                        "criterion_id": "evidence",
                                        "description": "The selected verification passes",
                                    }
                                ],
                                "initial_status": "active",
                                "source_sequence": 1,
                            },
                        )
                        self.assertEqual(started["status"], "processed")
                        producer_payload = b'{"temporary":true}\n'
                        producer_result = await asyncio.to_thread(
                            subprocess.run,
                            [
                                sys.executable,
                                "-m",
                                "curatormd_v2.producer_cli",
                                "--project-root",
                                str(root),
                                "--database",
                                str(Path(temporary) / "global.sqlite3"),
                                "--goal-id",
                                "mcp-sde-goal",
                                "--artifact-class",
                                "import",
                                "--artifact-id",
                                "session-evidence",
                            ],
                            input=producer_payload,
                            capture_output=True,
                            check=False,
                            timeout=15,
                        )
                        self.assertEqual(
                            producer_result.returncode, 0, producer_result.stderr
                        )
                        self.assertNotIn(producer_payload, producer_result.stdout)
                        producer_receipt = json.loads(producer_result.stdout)
                        self.assertEqual(Path(producer_receipt["path"]), staged)
                        self.assertEqual(
                            producer_receipt["sha256"],
                            hashlib.sha256(producer_payload).hexdigest(),
                        )
                        self.assertEqual(staged.read_bytes(), producer_payload)
                        unheld_staged.parent.mkdir(parents=True)
                        unheld_staged.write_bytes(unheld_payload)
                        await call_json(
                            "fact_record",
                            {
                                "event_id": "mcp-sde-event-2",
                                "goal_id": "mcp-sde-goal",
                                "fact_id": "mcp-sde-change",
                                "kind": "change",
                                "bullet": "Added the reviewed SDE assessment path",
                                "source_sequence": 2,
                            },
                        )
                        await call_json(
                            "fact_record",
                            {
                                "event_id": "mcp-sde-event-3",
                                "goal_id": "mcp-sde-goal",
                                "fact_id": "mcp-sde-verification",
                                "kind": "verification",
                                "bullet": "The integration evidence passed",
                                "criterion_id": "evidence",
                                "evidence": [
                                    {
                                        "evidence_kind": "integration-test",
                                        "locator": "test-proof:mcp",
                                        "sha256": hashlib.sha256(
                                            b"mcp-proof"
                                        ).hexdigest(),
                                        "outcome": "passed",
                                    }
                                ],
                                "source_sequence": 3,
                            },
                        )
                        finished = await call_json(
                            "goal_finish",
                            {
                                "event_id": "mcp-sde-event-4",
                                "goal_id": "mcp-sde-goal",
                                "completion_claim": "The evidence-backed goal is complete",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 4,
                            },
                        )
                        self.assertEqual(finished["status"], "processed")
                        completed = await call_json(
                            "goal_status", {"goal_id": "mcp-sde-goal"}
                        )
                        self.assertEqual(completed["goal"]["status"], "complete")

                        candidate = await call_json(
                            "sde_assess",
                            {
                                "goal_id": "mcp-sde-goal",
                                "materiality": "implementation",
                                "rationale": "A durable project change has passing evidence",
                                "impact": "Observed local verification passed",
                                "retrieval_value": "Helps maintainers find the contract",
                                "fact_ids": [
                                    "mcp-sde-change",
                                    "mcp-sde-verification",
                                ],
                            },
                        )
                        self.assertEqual(candidate["status"], "pending_review")
                        queue = await call_json("sde_review_queue", {})
                        self.assertEqual(
                            [item["candidate"]["candidate_id"] for item in queue],
                            [candidate["candidate_id"]],
                        )
                        inventory = await call_json(
                            "artifact_inventory_discover",
                            {"goal_id": "mcp-sde-goal"},
                        )
                        manifest = inventory["artifacts"]
                        self.assertEqual(len(manifest), 2)
                        reviewed_manifest = [
                            (
                                {
                                    **artifact,
                                    "retention_hold": "operational",
                                    "reacquisition_action": "retain_under_hold",
                                }
                                if Path(artifact["path"]) == staged
                                else {
                                    **artifact,
                                    "reacquisition_action": "not_required",
                                }
                            )
                            for artifact in manifest
                        ]

                        packet = await call_json(
                            "sde_review_packet",
                            {
                                "candidate_id": candidate["candidate_id"],
                                "review_artifacts": reviewed_manifest,
                            },
                        )
                        self.assertEqual(
                            packet["detail"]["candidate"]["candidate_id"],
                            candidate["candidate_id"],
                        )
                        self.assertEqual(
                            packet["artifact_inventory"]["scope_goal_id"],
                            "mcp-sde-goal",
                        )
                        self.assertTrue(
                            packet["artifact_inventory"]["usage"][
                                "inventory_complete"
                            ]
                        )
                        self.assertEqual(
                            packet["artifact_inventory"]["artifacts"],
                            inventory["artifacts"],
                        )
                        self.assertEqual(packet["review_artifacts"], reviewed_manifest)
                        self.assertEqual(
                            len(packet["artifact_dependencies"]),
                            len(inventory["artifacts"]),
                        )
                        self.assertEqual(len(packet["dependency_map_sha256"]), 64)

                        self.assertTrue(inventory["usage"]["inventory_complete"])
                        receipt = await call_json(
                            "sde_confirm",
                            {
                                "candidate_id": candidate["candidate_id"],
                                "decision": "approved",
                                "artifacts": reviewed_manifest,
                                "artifact_inventory_complete": True,
                                "dependency_map_sha256": packet[
                                    "dependency_map_sha256"
                                ],
                                "rationale": "Human reviewer approved the bounded facts",
                            },
                        )
                        self.assertEqual(receipt["reviewer_id"], "host-subject")
                        self.assertTrue(receipt["artifact_inventory_complete"])
                        self.assertFalse(receipt["canonical_persisted"])
                        self.assertTrue(receipt["cleanup_authorized"])
                        self.assertEqual(
                            receipt["cleanup_dependency_map_sha256"],
                            packet["dependency_map_sha256"],
                        )
                        self.assertEqual(receipt["purge_status"], "purge_pending")
                        self.assertTrue(staged.exists())
                        pending_health = await call_json("project_health", {})
                        self.assertEqual(pending_health["status"], "degraded")
                        self.assertEqual(
                            pending_health["operational_counts"][
                                "pending_expiry_purge_receipt_count"
                            ],
                            0,
                        )
                        self.assertEqual(
                            pending_health["operational_counts"][
                                "pending_purge_receipt_count"
                            ],
                            1,
                        )

                        self.assertTrue(receipt["artifact_inventory_complete"])
                        self.assertFalse(receipt["canonical_persisted"])
                        self.assertTrue(staged.exists())
                        self.assertTrue(unheld_staged.exists())
                        inventory_health = await call_json("project_health", {})
                        self.assertEqual(
                            inventory_health["operational_counts"][
                                "pending_purge_artifact_count"
                            ],
                            2,
                        )

                        await call_json(
                            "goal_persist",
                            {
                                "goal_id": "mcp-sde-goal",
                                "target": "persistence/HISTORY.md",
                            },
                        )
                        self.assertTrue(staged.exists())
                        self.assertFalse(unheld_staged.exists())
                        self.assertIn("Added the reviewed SDE assessment path", history.read_text())
                        self.assertIn(receipt["receipt_id"], history.read_text())
                        self.assertNotIn(unheld_payload.decode(), history.read_text())

                        purge_result = await call_json(
                            "artifact_purge_status",
                            {"receipt_id": receipt["receipt_id"]},
                        )
                        self.assertEqual(purge_result[0]["purge_status"], "purge_pending")
                        self.assertTrue(purge_result[0]["canonical_persisted"])
                        held_artifact_status = next(
                            item for item in purge_result[1] if item["status"] == "held"
                        )
                        self.assertEqual(
                            held_artifact_status["artifact"]["retention_hold"],
                            "operational",
                        )
                        self.assertEqual(held_artifact_status["attempts"], 0)
                        self.assertIsNotNone(held_artifact_status["created_at"])
                        self.assertGreaterEqual(held_artifact_status["age_seconds"], 0)
                        self.assertIsNone(held_artifact_status["last_attempt_at"])
                        self.assertIsNone(held_artifact_status["next_attempt_at"])
                        self.assertIsNone(
                            held_artifact_status["next_attempt_in_seconds"]
                        )
                        self.assertIsNone(
                            held_artifact_status["last_attempt_age_seconds"]
                        )
                        self.assertEqual(
                            held_artifact_status["safe_recovery_action"],
                            "release_artifact_hold",
                        )
                        self.assertEqual(
                            {item["status"] for item in purge_result[1]},
                            {"held", "purged"},
                        )
                        final_status = await call_json(
                            "goal_status",
                            {
                                "goal_id": "mcp-sde-goal",
                                "sde_offset": 0,
                                "purge_offset": 0,
                            },
                        )
                        self.assertEqual(final_status["goal"]["status"], "complete")
                        self.assertEqual(
                            final_status["sde_candidates"][0]["status"], "approved"
                        )
                        report_result = await client.call_tool(
                            "goal_report",
                            {
                                "goal_id": "mcp-sde-goal",
                                "fact_offset": 0,
                                "fact_limit": 8,
                            },
                        )
                        self.assertFalse(report_result.is_error)
                        report_content = report_result.content[0]
                        assert isinstance(report_content, TextContent)
                        self.assertIn(
                            "- Outcome: `complete` (lifecycle revision `2`)",
                            report_content.text,
                        )
                        self.assertIn(
                            "- Problem: Expose verified SDE assessment",
                            report_content.text,
                        )
                        self.assertIn(
                            "- Next action: none (goal is terminal).",
                            report_content.text,
                        )
                        self.assertIn(
                            "- [x] `evidence` — verified: The selected verification passes; "
                            "proof facts: `mcp-sde-verification`",
                            report_content.text,
                        )
                        self.assertIn(
                            "`mcp-sde-verification` — verification: "
                            "The integration evidence passed",
                            report_content.text,
                        )
                        self.assertIn(
                            f"Purge receipt {receipt['receipt_id']} remains pending",
                            report_content.text,
                        )
                        self.assertIn(
                            "canonical write verified at `persistence/HISTORY.md`",
                            report_content.text,
                        )
                        self.assertIn("purge `purge_pending`", report_content.text)
                        self.assertIn("Resolve purge receipt", report_content.text)

                        release_rationale = "Retention owner approved release"
                        private_error_marker = "SENSITIVE_PURGE_EXCEPTION_SENTINEL"
                        with patch.object(
                            plugin.service.purger,
                            "purge",
                            side_effect=PurgeError(
                                PurgeFailureCode.FILESYSTEM_ERROR,
                                f"private path detail: {private_error_marker}",
                            ),
                        ):
                            failed_receipt = await call_json(
                                "release_artifact_hold",
                                {
                                    "receipt_id": receipt["receipt_id"],
                                    "path": str(staged),
                                    "rationale": release_rationale,
                                },
                            )
                        self.assertEqual(
                            failed_receipt["purge_status"], "purge_pending"
                        )
                        self.assertTrue(staged.exists())
                        failed_purge_status = await call_json(
                            "artifact_purge_status",
                            {"receipt_id": receipt["receipt_id"]},
                        )
                        self.assertEqual(
                            failed_purge_status[1][0]["error"],
                            "filesystem_error",
                        )
                        self.assertNotIn(
                            private_error_marker, json.dumps(failed_purge_status)
                        )
                        plugin.service.purger = ArtifactPurger(staging)
                        self.assertEqual(
                            plugin.service.retry_pending_purges()[0].purge_status.value,
                            "complete",
                        )
                        self.assertFalse(staged.exists())
                        release_replay = await call_json(
                            "release_artifact_hold",
                            {
                                "receipt_id": receipt["receipt_id"],
                                "path": str(staged),
                                "rationale": release_rationale,
                            },
                        )
                        self.assertEqual(release_replay["purge_status"], "complete")
                        released_status = await call_json(
                            "artifact_purge_status",
                            {"receipt_id": receipt["receipt_id"]},
                        )
                        self.assertEqual(released_status[1][0]["status"], "purged")
                        self.assertEqual(
                            released_status[1][0]["hold_created_by"], "host-subject"
                        )
                        self.assertEqual(
                            released_status[1][0]["hold_released_by"], "host-subject"
                        )
                        self.assertEqual(
                            released_status[1][0]["hold_release_rationale"],
                            release_rationale,
                        )
                        completed_report = await client.call_tool(
                            "goal_report", {"goal_id": "mcp-sde-goal"}
                        )
                        self.assertFalse(completed_report.is_error)
                        completed_report_content = completed_report.content[0]
                        assert isinstance(completed_report_content, TextContent)
                        self.assertIn(
                            "- Outcome: `complete` (lifecycle revision `2`)",
                            completed_report_content.text,
                        )
                        self.assertIn(
                            "canonical write verified at `persistence/HISTORY.md`",
                            completed_report_content.text,
                        )
                        self.assertIn(
                            "purge `complete`", completed_report_content.text
                        )
                        self.assertIn(
                            "Purge `complete`: 1 receipt(s)",
                            completed_report_content.text,
                        )
                        self.assertIn(
                            "## Current open gates\n- None recorded.",
                            completed_report_content.text,
                        )
                        self.assertNotIn(
                            "Resolve purge receipt", completed_report_content.text
                        )
                        self.assertIn(
                            "## Open TODOs\n- None recorded for this goal.",
                            completed_report_content.text,
                        )

                        await call_json(
                            "goal_start",
                            {
                                "event_id": "mcp-sde-event-5",
                                "goal_id": "mcp-rejected-goal",
                                "problem": "Keep rejected significance claims factual",
                                "success_criteria": [
                                    {
                                        "criterion_id": "evidence",
                                        "description": "The selected verification passes",
                                    }
                                ],
                                "initial_status": "active",
                                "source_sequence": 5,
                            },
                        )
                        await call_json(
                            "fact_record",
                            {
                                "event_id": "mcp-sde-event-6",
                                "goal_id": "mcp-rejected-goal",
                                "fact_id": "mcp-rejected-change",
                                "kind": "change",
                                "bullet": "Added a bounded local implementation",
                                "source_sequence": 6,
                            },
                        )
                        await call_json(
                            "fact_record",
                            {
                                "event_id": "mcp-sde-event-7",
                                "goal_id": "mcp-rejected-goal",
                                "fact_id": "mcp-rejected-verification",
                                "kind": "verification",
                                "bullet": "The local test passed",
                                "criterion_id": "evidence",
                                "evidence": [
                                    {
                                        "evidence_kind": "unit-test",
                                        "locator": "test-proof:mcp",
                                        "sha256": hashlib.sha256(
                                            b"mcp-proof"
                                        ).hexdigest(),
                                        "outcome": "passed",
                                    }
                                ],
                                "source_sequence": 7,
                            },
                        )
                        await call_json(
                            "goal_finish",
                            {
                                "event_id": "mcp-sde-event-8",
                                "goal_id": "mcp-rejected-goal",
                                "completion_claim": "The tested local change is complete",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 8,
                            },
                        )
                        rejected_candidate = await call_json(
                            "sde_assess",
                            {
                                "goal_id": "mcp-rejected-goal",
                                "materiality": "implementation",
                                "rationale": (
                                    "The change establishes a broad durable production impact"
                                ),
                                "impact": "Expected production impact is unmeasured",
                                "retrieval_value": "Helps distinguish claims from "
                                "observed outcomes",
                                "fact_ids": [
                                    "mcp-rejected-change",
                                    "mcp-rejected-verification",
                                ],
                            },
                        )
                        rejected_artifact = (
                            staging / "mcp-rejected-goal" / "rejected-transient.json"
                        )
                        rejected_artifact.parent.mkdir()
                        rejected_artifact.write_text('{"temporary":"rejected"}\n')
                        rejected_inventory = await call_json(
                            "artifact_inventory_discover",
                            {"goal_id": "mcp-rejected-goal"},
                        )
                        rejected_manifest = rejected_inventory["artifacts"]
                        self.assertEqual(len(rejected_manifest), 1)
                        rejected_manifest = [
                            {
                                **rejected_manifest[0],
                                "reacquisition_action": "not_required",
                            }
                        ]
                        rejected_packet = await call_json(
                            "sde_review_packet",
                            {
                                "candidate_id": rejected_candidate["candidate_id"],
                                "review_artifacts": rejected_manifest,
                            },
                        )
                        rejected_receipt = await call_json(
                            "sde_confirm",
                            {
                                "candidate_id": rejected_candidate["candidate_id"],
                                "decision": "rejected",
                                "artifacts": rejected_manifest,
                                "artifact_inventory_complete": True,
                                "dependency_map_sha256": rejected_packet[
                                    "dependency_map_sha256"
                                ],
                                "rationale": "The evidence proves only a local test result",
                            },
                        )
                        self.assertEqual(rejected_receipt["purge_status"], "purge_pending")
                        self.assertTrue(rejected_receipt["cleanup_authorized"])
                        self.assertTrue(rejected_artifact.exists())
                        await call_json(
                            "sde_quality_feedback_record",
                            {
                                "feedback_id": "mcp-quality-feedback-1",
                                "candidate_id": rejected_candidate["candidate_id"],
                                "label": "not_useful",
                                "rationale": "The proposed impact exceeded the test evidence",
                            },
                        )
                        quality_summary = await call_json(
                            "sde_quality_feedback_summary", {}
                        )
                        self.assertEqual(quality_summary["total"], 1)
                        self.assertEqual(
                            dict(quality_summary["counts"])["not_useful"], 1
                        )
                        await call_json(
                            "goal_persist",
                            {
                                "goal_id": "mcp-rejected-goal",
                                "target": "persistence/HISTORY.md",
                            },
                        )
                        self.assertFalse(rejected_artifact.exists())
                        reconciliation = await call_json(
                            "goal_reconcile",
                            {
                                "goal_id": "mcp-rejected-goal",
                                "target": "persistence/HISTORY.md",
                            },
                        )
                        self.assertEqual(reconciliation["status"], "synced")
                        project_reconciliation = await call_json(
                            "project_reconcile",
                            {
                                "target": "persistence/HISTORY.md",
                                "offset": 0,
                                "limit": 10,
                            },
                        )
                        goal_states = {
                            item["goal_id"]: item["status"]
                            for item in project_reconciliation["goals"]
                        }
                        self.assertEqual(
                            goal_states["mcp-rejected-goal"], "synced"
                        )
                        self.assertTrue(project_reconciliation["inventory_complete"])
                        self.assertFalse(rejected_artifact.exists())
                        history_text = history.read_text()
                        self.assertIn("Added a bounded local implementation", history_text)
                        self.assertIn(rejected_receipt["receipt_id"], history_text)
                        self.assertNotIn(
                            "The change establishes a broad durable production impact",
                            history_text,
                        )
                        rejected_status = await call_json(
                            "goal_status", {"goal_id": "mcp-rejected-goal"}
                        )
                        self.assertEqual(
                            rejected_status["sde_candidates"][0]["status"], "rejected"
                        )
                        rejected_purge = await call_json(
                            "artifact_purge_status",
                            {"receipt_id": rejected_receipt["receipt_id"]},
                        )
                        self.assertEqual(
                            rejected_purge[0]["purge_status"], "complete"
                        )
                        self.assertEqual(
                            {item["status"] for item in rejected_purge[1]},
                            {"purged"},
                        )
                        return candidate["candidate_id"], receipt["receipt_id"]

                asyncio.run(exercise())
            finally:
                store.close()

    def test_mcp_client_drives_a_project_bound_evidence_gated_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] MCP task\n")
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
                plugin = bind_test_project(
                    store,
                    root,
                    "host-subject",
                    evidence_verifier=TestVerifier(),
                    review_authorizer=TestReviewAuthorizer(),
                )
                reviewed_goal = plugin.service.goal_start(
                    "Record an MCP-reviewed correction",
                    (SuccessCriterion("verified", "Test evidence passes"),),
                )
                change, _ = plugin.service.goal_fact(
                    reviewed_goal.goal_id, FactKind.CHANGE, "Implemented the change"
                )
                evidence = EvidenceRef(
                    "unit-test",
                    "test-proof:mcp",
                    hashlib.sha256(b"mcp-proof").hexdigest(),
                    EvidenceOutcome.PASSED,
                )
                verification, _ = plugin.service.goal_fact(
                    reviewed_goal.goal_id,
                    FactKind.VERIFICATION,
                    "MCP test evidence passed",
                    criterion_id="verified",
                    evidence=(evidence,),
                )
                candidate = plugin.service.sde_assess(
                    reviewed_goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "The implementation is durable and verified",
                    (change.fact_id, verification.fact_id),
                    impact="Observed in the bounded test scenario",
                    retrieval_value="Useful for future maintenance review",
                )
                assert candidate is not None
                plugin.service.sde_confirm(
                    candidate.candidate_id,
                    ReviewDecision.APPROVED,
                    (),
                    artifact_inventory_complete=True,
                    authenticated_subject="host-subject",
                )
                caller = AuthenticatedCaller("host-subject")
                api = AuthenticatedCuratorAPI(
                    {"mcp-project": plugin},
                    AllowProject(),
                    InMemoryTokenBucket(),
                )
                server = build_mcp_server(
                    api, caller, "mcp-project", "mcp-test-stream"
                )

                async def exercise() -> tuple[list[str], dict[str, object]]:
                    async with Client(server, raise_exceptions=True) as client:
                        tool_result = await client.list_tools()
                        names = [tool.name for tool in tool_result.tools]
                        activity_status_tool = next(
                            tool
                            for tool in tool_result.tools
                            if tool.name == "project_activity_status"
                        )
                        self.assertIsNotNone(activity_status_tool.annotations)
                        assert activity_status_tool.annotations is not None
                        self.assertTrue(
                            activity_status_tool.annotations.read_only_hint
                        )
                        tools_by_name = {tool.name: tool for tool in tool_result.tools}
                        read_only_names = {
                            "event_queue_status",
                            "project_activity_status",
                            "project_health",
                            "project_metrics",
                            "goal_status",
                            "goal_bullet_projection",
                            "goal_report",
                            "fact_compaction_propose",
                            "fact_archive_receipts",
                            "goal_list",
                            "goal_list_page",
                            "goal_children",
                            "goal_children_page",
                            "project_storage_usage",
                            "goal_reconcile",
                            "project_reconcile",
                            "sde_review_queue",
                            "sde_review_detail",
                            "sde_quality_feedback_summary",
                            "artifact_purge_status",
                        }
                        for name in read_only_names:
                            annotations = tools_by_name[name].annotations
                            self.assertIsNotNone(annotations, name)
                            assert annotations is not None
                            self.assertTrue(annotations.read_only_hint, name)
                        for name in ("goal_start", "sde_confirm", "retry_pending_purges"):
                            annotations = tools_by_name[name].annotations
                            self.assertFalse(
                                bool(annotations and annotations.read_only_hint), name
                            )
                        correction_result = await client.call_tool(
                            "sde_correction_record",
                            {
                                "correction_id": "mcp-correction-1",
                                "candidate_id": candidate.candidate_id,
                                "correction": "Limit the claim to the verified test",
                                "rationale": "The test does not establish production impact",
                            },
                        )
                        self.assertFalse(correction_result.is_error)
                        correction_content = correction_result.content[0]
                        assert isinstance(correction_content, TextContent)
                        correction_value = json.loads(correction_content.text)
                        self.assertEqual(
                            correction_value["reviewer_id"], "host-subject"
                        )
                        self.assertEqual(
                            correction_value["candidate_id"], candidate.candidate_id
                        )
                        start = await client.call_tool(
                            "goal_start",
                            {
                                "event_id": "mcp-event-1",
                                "goal_id": "mcp-goal-1",
                                "problem": "Record the MCP lifecycle",
                                "success_criteria": [
                                    {
                                        "criterion_id": "verified",
                                        "description": "MCP evidence is accepted",
                                    }
                                ],
                                "initial_status": "active",
                                "next_action": "Run the focused lifecycle regression",
                                "source_sequence": 1,
                            },
                        )
                        self.assertFalse(start.is_error)
                        initial_report = await client.call_tool(
                            "goal_report", {"goal_id": "mcp-goal-1"}
                        )
                        initial_report_content = initial_report.content[0]
                        assert isinstance(initial_report_content, TextContent)
                        self.assertIn(
                            "- Next action: Run the focused lifecycle regression",
                            initial_report_content.text,
                        )
                        incomplete = await client.call_tool(
                            "goal_finish",
                            {
                                "event_id": "mcp-event-2",
                                "goal_id": "mcp-goal-1",
                                "completion_claim": "The task is complete",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 2,
                            },
                        )
                        self.assertFalse(incomplete.is_error)
                        open_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-1"}
                        )
                        open_content = open_status.content[0]
                        assert isinstance(open_content, TextContent)
                        open_value = json.loads(open_content.text)
                        self.assertEqual(open_value["goal"]["status"], "open")
                        self.assertEqual(open_value["goal"]["lifecycle_revision"], 2)
                        self.assertEqual(
                            open_value["criteria"][0]["status"], "open"
                        )
                        open_bullets_result = await client.call_tool(
                            "goal_bullet_projection", {"goal_id": "mcp-goal-1"}
                        )
                        self.assertFalse(open_bullets_result.is_error)
                        open_bullets_content = open_bullets_result.content[0]
                        assert isinstance(open_bullets_content, TextContent)
                        open_bullets_value = json.loads(open_bullets_content.text)
                        open_categories = [
                            item["category"] for item in open_bullets_value["bullets"]
                        ]
                        self.assertIn("unverified_claim", open_categories)
                        self.assertIn("open_gate", open_categories)
                        open_report_result = await client.call_tool(
                            "goal_report",
                            {
                                "goal_id": "mcp-goal-1",
                                "fact_offset": 0,
                                "fact_limit": 4,
                            },
                        )
                        self.assertFalse(open_report_result.is_error)
                        open_report_content = open_report_result.content[0]
                        assert isinstance(open_report_content, TextContent)
                        self.assertIn("- Outcome: `open`", open_report_content.text)
                        self.assertIn("Outcome: open", open_report_content.text)
                        self.assertIn("## Success criteria", open_report_content.text)
                        self.assertIn("- Project: `mcp-project`", open_report_content.text)
                        self.assertIn("- Initial state: `active`", open_report_content.text)
                        self.assertIn("- Source event: `mcp-event-1`", open_report_content.text)
                        self.assertIn(
                            "- Next action: Verify unmet success criteria: "
                            "MCP evidence is accepted",
                            open_report_content.text,
                        )
                        self.assertIn("## Open TODOs", open_report_content.text)
                        self.assertIn("Unverified claims or checks", open_report_content.text)

                        await client.call_tool(
                            "fact_record",
                            {
                                "event_id": "mcp-event-3",
                                "goal_id": "mcp-goal-1",
                                "fact_id": "mcp-fact-1",
                                "kind": "verification",
                                "bullet": "The MCP evidence check passed",
                                "criterion_id": "verified",
                                "evidence": [
                                    {
                                        "evidence_kind": "unit-test",
                                        "locator": "test-proof:mcp",
                                        "sha256": hashlib.sha256(b"proof").hexdigest(),
                                        "outcome": "passed",
                                    }
                                ],
                                "source_sequence": 3,
                            },
                        )
                        await client.call_tool(
                            "goal_finish",
                            {
                                "event_id": "mcp-event-4",
                                "goal_id": "mcp-goal-1",
                                "completion_claim": "Evidence-backed completion",
                                "expected_lifecycle_revision": 2,
                                "source_sequence": 4,
                            },
                        )
                        final_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-1"}
                        )
                        final_content = final_status.content[0]
                        assert isinstance(final_content, TextContent)
                        final_value = json.loads(final_content.text)
                        self.assertEqual(final_value["goal"]["status"], "complete")
                        self.assertEqual(final_value["goal"]["lifecycle_revision"], 3)
                        self.assertEqual(
                            final_value["criteria"][0]["status"], "verified"
                        )
                        self.assertEqual(
                            final_value["criteria"][0]["verification_fact_ids"],
                            ["mcp-fact-1"],
                        )
                        final_bullets_result = await client.call_tool(
                            "goal_bullet_projection", {"goal_id": "mcp-goal-1"}
                        )
                        final_bullets_content = final_bullets_result.content[0]
                        assert isinstance(final_bullets_content, TextContent)
                        final_bullets_value = json.loads(final_bullets_content.text)
                        final_categories = [
                            item["category"]
                            for item in final_bullets_value["bullets"]
                        ]
                        self.assertIn("verified_fact", final_categories)
                        self.assertNotIn("open_gate", final_categories)
                        reopened = await client.call_tool(
                            "goal_reopen",
                            {
                                "event_id": "mcp-event-5",
                                "goal_id": "mcp-goal-1",
                                "reason": "A post-release regression was reported",
                                "next_action": "Reproduce and repair the regression",
                                "expected_lifecycle_revision": 3,
                                "source_sequence": 5,
                            },
                        )
                        self.assertFalse(reopened.is_error)
                        reopened_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-1"}
                        )
                        reopened_content = reopened_status.content[0]
                        assert isinstance(reopened_content, TextContent)
                        reopened_value = json.loads(reopened_content.text)
                        self.assertEqual(reopened_value["goal"]["status"], "active")
                        self.assertEqual(reopened_value["goal"]["lifecycle_revision"], 4)
                        self.assertEqual(
                            reopened_value["criteria"][0]["status"], "open"
                        )
                        self.assertTrue(
                            any(
                                fact["fact_id"] == "mcp-fact-1"
                                for fact in reopened_value["facts"]
                            )
                        )
                        amended = await client.call_tool(
                            "goal_amend_criteria",
                            {
                                "event_id": "mcp-event-6",
                                "goal_id": "mcp-goal-1",
                                "expected_revision": 1,
                                "success_criteria": [
                                    {
                                        "criterion_id": "verified",
                                        "description": "Updated MCP evidence is accepted",
                                    }
                                ],
                                "reason": "The acceptance wording was clarified",
                                "next_action": "Run the updated MCP evidence check",
                                "expected_lifecycle_revision": 4,
                                "source_sequence": 6,
                            },
                        )
                        self.assertFalse(amended.is_error)
                        amended_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-1"}
                        )
                        amended_content = amended_status.content[0]
                        assert isinstance(amended_content, TextContent)
                        amended_value = json.loads(amended_content.text)
                        self.assertEqual(
                            amended_value["goal"]["criteria_revision"], 2
                        )
                        self.assertEqual(
                            amended_value["goal"]["lifecycle_revision"], 5
                        )
                        self.assertEqual(len(amended_value["criteria_history"]), 2)
                        self.assertEqual(
                            amended_value["criteria"][0]["status"], "open"
                        )
                        await client.call_tool(
                            "fact_record",
                            {
                                "event_id": "mcp-event-7",
                                "goal_id": "mcp-goal-1",
                                "fact_id": "mcp-routine-1",
                                "kind": "research",
                                "bullet": "Reviewed the compact fact archive workflow",
                            },
                        )
                        proposal_result = await client.call_tool(
                            "fact_compaction_propose",
                            {"goal_id": "mcp-goal-1", "max_facts": 8},
                        )
                        self.assertFalse(proposal_result.is_error)
                        proposal_content = proposal_result.content[0]
                        assert isinstance(proposal_content, TextContent)
                        proposal_value = json.loads(proposal_content.text)
                        approval_result = await client.call_tool(
                            "fact_compaction_approve",
                            {
                                "compaction_id": proposal_value["compaction_id"],
                                "goal_id": "mcp-goal-1",
                                "fact_ids": ["mcp-routine-1"],
                                "source_sha256": proposal_value["source_sha256"],
                                "approval_reason": "Approved the exact routine fact preview",
                            },
                        )
                        self.assertFalse(approval_result.is_error)
                        approval_content = approval_result.content[0]
                        assert isinstance(approval_content, TextContent)
                        approval_value = json.loads(approval_content.text)
                        self.assertEqual(
                            approval_value["reviewer_id"], "host-subject"
                        )
                        self.assertEqual(
                            approval_value["fact_ids"], ["mcp-routine-1"]
                        )
                        archived_status_result = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-1"}
                        )
                        archived_status_content = archived_status_result.content[0]
                        assert isinstance(archived_status_content, TextContent)
                        archived_status_value = json.loads(
                            archived_status_content.text
                        )
                        self.assertTrue(
                            any(
                                fact["fact_id"] == "mcp-routine-1"
                                and fact["bullet"]
                                == "Reviewed the compact fact archive workflow"
                                for fact in archived_status_value["facts"]
                            )
                        )
                        self.assertIn("fact_compaction_propose", names)
                        self.assertIn("fact_compaction_approve", names)
                        archive_receipts_result = await client.call_tool(
                            "fact_archive_receipts",
                            {"goal_id": "mcp-goal-1", "offset": 0, "limit": 10},
                        )
                        self.assertFalse(archive_receipts_result.is_error)
                        archive_receipts_content = archive_receipts_result.content[0]
                        assert isinstance(archive_receipts_content, TextContent)
                        archive_receipts = json.loads(
                            archive_receipts_content.text
                        )
                        self.assertEqual(len(archive_receipts), 1)
                        self.assertEqual(
                            archive_receipts[0]["archive_sha256"],
                            approval_value["archive_sha256"],
                        )
                        plugin.service.store.record_staging_artifact_time(
                            "mcp-project",
                            ArtifactRef(
                                "mcp-goal/import/staged.bin",
                                "f" * 64,
                                device_id=3,
                                inode_id=4,
                                occurrence_id="c" * 32,
                            ),
                        )
                        usage_result = await client.call_tool(
                            "project_storage_usage", {}
                        )
                        self.assertFalse(usage_result.is_error)
                        usage_content = usage_result.content[0]
                        assert isinstance(usage_content, TextContent)
                        usage_value = json.loads(usage_content.text)
                        self.assertEqual(usage_value["project_id"], "mcp-project")
                        self.assertEqual(usage_value["goal_count"], 2)
                        self.assertEqual(usage_value["event_cursor_count"], 1)
                        self.assertGreater(usage_value["event_cursor_record_bytes"], 0)
                        self.assertEqual(usage_value["event_retry_audit_count"], 0)
                        self.assertEqual(
                            usage_value["event_retry_audit_record_bytes"], 0
                        )
                        self.assertEqual(usage_value["staging_artifact_time_count"], 1)
                        self.assertGreater(
                            usage_value["staging_artifact_time_record_bytes"], 0
                        )
                        self.assertEqual(
                            usage_value["staging_artifact_occurrence_count"], 1
                        )
                        self.assertGreater(
                            usage_value["staging_artifact_occurrence_record_bytes"], 0
                        )
                        self.assertNotIn("c" * 32, usage_content.text)
                        self.assertEqual(usage_value["expiry_purge_receipt_count"], 0)
                        self.assertEqual(
                            usage_value["expiry_purge_receipt_record_bytes"], 0
                        )
                        self.assertEqual(usage_value["expiry_purge_target_count"], 0)
                        self.assertEqual(
                            usage_value["expiry_purge_target_record_bytes"], 0
                        )
                        self.assertEqual(usage_value["cleanup_authorization_count"], 0)
                        self.assertEqual(
                            usage_value["cleanup_authorization_record_bytes"], 0
                        )
                        self.assertIsInstance(
                            usage_value["event_payload_scrub_count"], int
                        )
                        self.assertIsInstance(
                            usage_value["event_payload_scrub_record_bytes"], int
                        )
                        self.assertEqual(usage_value["fact_archive_item_count"], 1)
                        self.assertGreater(
                            usage_value["fact_archive_compressed_bytes"], 0
                        )
                        self.assertEqual(
                            usage_value["staging"]["classes"], []
                        )
                        activity_result = await client.call_tool(
                            "project_activity_status", {}
                        )
                        self.assertFalse(activity_result.is_error)
                        activity_content = activity_result.content[0]
                        assert isinstance(activity_content, TextContent)
                        activity_value = json.loads(activity_content.text)
                        self.assertTrue(activity_value["events_observed"])
                        self.assertEqual(activity_value["goal_count"], 2)
                        self.assertGreater(activity_value["event_receipt_count"], 0)
                        health_result = await client.call_tool("project_health", {})
                        self.assertFalse(health_result.is_error)
                        health_content = health_result.content[0]
                        assert isinstance(health_content, TextContent)
                        health_value = json.loads(health_content.text)
                        self.assertEqual(health_value["project_id"], "mcp-project")
                        self.assertEqual(health_value["status"], "degraded")
                        self.assertTrue(
                            health_value["database_observation_complete"]
                        )
                        self.assertIsNotNone(health_value["database_observed_at"])
                        self.assertIsNotNone(health_value["staging_observed_at"])
                        self.assertIn(
                            "dependency_unknown:event_router",
                            health_value["gate_codes"],
                        )
                        metrics_result = await client.call_tool("project_metrics", {})
                        self.assertFalse(metrics_result.is_error)
                        metrics_content = metrics_result.content[0]
                        assert isinstance(metrics_content, TextContent)
                        self.assertIn("curatormd_project_health_state", metrics_content.text)
                        self.assertIn(
                            'curatormd_event_cursors{project_id="mcp-project"} 1',
                            metrics_content.text,
                        )
                        self.assertIn(
                            'curatormd_event_retry_audit_records'
                            '{project_id="mcp-project"} 0',
                            metrics_content.text,
                        )
                        inventory_result = await client.call_tool(
                            "artifact_inventory_discover",
                            {"goal_id": "mcp-goal-1"},
                        )
                        self.assertFalse(inventory_result.is_error)
                        inventory_content = inventory_result.content[0]
                        assert isinstance(inventory_content, TextContent)
                        inventory_value = json.loads(inventory_content.text)
                        self.assertTrue(
                            inventory_value["usage"]["inventory_complete"]
                        )
                        self.assertEqual(inventory_value["artifacts"], [])

                        project_inventory_result = await client.call_tool(
                            "project_artifact_inventory_discover", {}
                        )
                        self.assertFalse(project_inventory_result.is_error)
                        project_inventory_content = project_inventory_result.content[0]
                        assert isinstance(project_inventory_content, TextContent)
                        project_inventory_value = json.loads(
                            project_inventory_content.text
                        )
                        self.assertTrue(
                            project_inventory_value["usage"]["inventory_complete"]
                        )
                        self.assertIsNone(project_inventory_value["scope_goal_id"])

                        expiry_result = await client.call_tool(
                            "project_expiry_inventory_discover", {}
                        )
                        self.assertFalse(expiry_result.is_error)
                        expiry_content = expiry_result.content[0]
                        assert isinstance(expiry_content, TextContent)
                        expiry_value = json.loads(expiry_content.text)
                        self.assertTrue(expiry_value["inventory_complete"])
                        self.assertEqual(expiry_value["eligible_artifacts"], [])
                        self.assertIsNotNone(expiry_value["manifest_sha256"])

                        planned_start = await client.call_tool(
                            "goal_start",
                            {
                                "event_id": "mcp-event-8",
                                "goal_id": "mcp-goal-planned",
                                "problem": "Capture planned work before execution",
                                "success_criteria": [
                                    {
                                        "criterion_id": "planned-proof",
                                        "description": "Work is verified after acceptance",
                                    }
                                ],
                                "source_sequence": 7,
                            },
                        )
                        self.assertFalse(planned_start.is_error)
                        page_result = await client.call_tool(
                            "goal_list_page", {"offset": 0, "limit": 1}
                        )
                        self.assertFalse(page_result.is_error)
                        page_content = page_result.content[0]
                        assert isinstance(page_content, TextContent)
                        page_value = json.loads(page_content.text)
                        self.assertEqual(page_value["total"], 3)
                        self.assertEqual(page_value["next_offset"], 1)
                        self.assertEqual(len(page_value["goals"]), 1)
                        self.assertNotIn("facts", page_value["goals"][0])
                        children_page = await client.call_tool(
                            "goal_children_page",
                            {
                                "parent_goal_id": "mcp-goal-1",
                                "offset": 0,
                                "limit": 5,
                            },
                        )
                        self.assertFalse(children_page.is_error)
                        children_content = children_page.content[0]
                        assert isinstance(children_content, TextContent)
                        children_value = json.loads(children_content.text)
                        self.assertEqual(children_value["total"], 0)
                        self.assertIsNone(children_value["next_offset"])
                        planned_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-planned"}
                        )
                        planned_content = planned_status.content[0]
                        assert isinstance(planned_content, TextContent)
                        planned_value = json.loads(planned_content.text)
                        self.assertEqual(planned_value["goal"]["status"], "planned")
                        activated = await client.call_tool(
                            "goal_activate",
                            {
                                "event_id": "mcp-event-9",
                                "goal_id": "mcp-goal-planned",
                                "reason": "User accepted implementation",
                                "expected_lifecycle_revision": 1,
                                "source_sequence": 8,
                            },
                        )
                        self.assertFalse(activated.is_error)
                        active_status = await client.call_tool(
                            "goal_status", {"goal_id": "mcp-goal-planned"}
                        )
                        active_content = active_status.content[0]
                        assert isinstance(active_content, TextContent)
                        active_value = json.loads(active_content.text)
                        self.assertEqual(active_value["goal"]["status"], "active")
                        self.assertEqual(active_value["goal"]["lifecycle_revision"], 2)
                        self.assertIn("goal_activate", names)
                        return names, final_value

                names, _final = asyncio.run(exercise())
                self.assertIn("goal_start", names)
                self.assertIn("goal_list_page", names)
                self.assertIn("goal_children_page", names)
                self.assertIn("goal_activate", names)
                self.assertIn("goal_bullet_projection", names)
                self.assertIn("goal_report", names)
                self.assertIn("fact_archive_receipts", names)
                self.assertIn("fact_record", names)
                self.assertIn("sde_confirm", names)
                self.assertIn("sde_correction_record", names)
                self.assertIn("sde_quality_feedback_record", names)
                self.assertIn("sde_quality_feedback_summary", names)
                self.assertIn("project_storage_usage", names)
                self.assertIn("artifact_inventory_discover", names)
                self.assertIn("project_artifact_inventory_discover", names)
                self.assertIn("project_expiry_inventory_discover", names)
                self.assertIn("sde_review_packet", names)
                self.assertIn("goal_reopen", names)
                self.assertIn("goal_amend_criteria", names)
                self.assertIn("goal_cancel", names)
                self.assertIn("goal_supersede", names)
                self.assertIn("event_queue_status", names)
                self.assertIn("project_activity_status", names)
                self.assertIn("project_health", names)
                self.assertIn("project_metrics", names)
                self.assertIn("event_quarantine_retry", names)
                self.assertNotIn("project_id", names)
                self.assertNotIn("caller", names)
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
                secret = self._assert_sensitive_event_rejected_without_echo(
                    root, store
                )
                self._assert_sensitive_event_absent_from_storage(
                    secret, database_path, root
                )
            finally:
                store.close()

    def _assert_sensitive_event_rejected_without_echo(
        self, root: Path, store: CuratorStore
    ) -> str:
        """Exercise MCP and logs while returning the test-only canary for scans."""
        plugin = bind_test_project(store, root, "host-subject")
        caller = AuthenticatedCaller("host-subject")
        api = AuthenticatedCuratorAPI(
            {"mcp-project": plugin}, AllowProject(), InMemoryTokenBucket()
        )
        server = build_mcp_server(api, caller, "mcp-project", "privacy-test")
        secret = (
            "ghs_1234567890_"
            + "A" * 480
            + ".eyJhbGciOiJIUzI1NiJ9.signature"
        )
        payload = json.dumps(
            {
                "schema_version": 1,
                "event_id": "sensitive-mcp-event",
                "project_id": "mcp-project",
                "source_id": "privacy-test",
                "source_sequence": 1,
                "occurred_at": "2026-10-20T00:00:00Z",
                "event_type": "goal.started",
                "payload": {
                    "goal_id": "sensitive-mcp-goal",
                    "problem": f"Example token {secret}",
                    "success_criteria": [
                        {"criterion_id": "done", "description": "No leak"}
                    ],
                },
            }
        )

        async def exercise() -> None:
            async with Client(server, raise_exceptions=True) as client:
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
        self.assertNotIn(secret, "\n".join(captured.output))
        return secret

    def _assert_sensitive_event_absent_from_storage(
        self, secret: str, database_path: Path, root: Path
    ) -> None:
        """Scan SQLite sidecars, canonical Markdown, and staging bytes."""
        secret_bytes = secret.encode("utf-8")
        for suffix in ("", "-wal", "-shm", "-journal"):
            database_file = Path(f"{database_path}{suffix}")
            if database_file.exists():
                self.assertNotIn(secret_bytes, database_file.read_bytes())
        history = root / "persistence" / "HISTORY.md"
        self.assertNotIn(secret_bytes, history.read_bytes())
        staging = root / ".curatormd-v2" / "staging"
        for staged_file in staging.rglob("*"):
            if staged_file.is_file():
                self.assertNotIn(secret_bytes, staged_file.read_bytes())


if __name__ == "__main__":
    unittest.main()
