"""MCP SDE review and purge workflow tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from unittest.mock import patch

from mcp import Client
from mcp.types import TextContent
from project_fixtures import (
    create_consumer_repo,
)
from test_mcp_server import (
    AllowProject,
    McpServerTestSupport,
    _McpSdeArtifacts,  # pyright: ignore[reportPrivateUsage]
    _McpSdePaths,  # pyright: ignore[reportPrivateUsage]
    _McpSdeReview,  # pyright: ignore[reportPrivateUsage]
    _McpSdeWorkflow,  # pyright: ignore[reportPrivateUsage]
)
from curatormd_v2 import (
    ArtifactPurger,
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CuratorStore,
    InMemoryTokenBucket,
    PurgeError,
    PurgeFailureCode,
    build_mcp_server,
)


class McpSdeWorkflowTests(McpServerTestSupport):
    """MCP SDE review and purge workflow tests."""

    def test_mcp_sde_assessment_review_persistence_and_purge_are_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workflow = self._create_mcp_sde_workflow(Path(temporary))
            server = self._mcp_sde_server(workflow)

            async def exercise() -> tuple[str, str]:
                async with Client(server, raise_exceptions=True) as client:
                    approved = await self._prepare_approved_sde_review(client, workflow)
                    await self._persist_sde_and_verify_pending_purge(
                        client, approved, workflow
                    )
                    await self._finish_sde_hold_release(client, approved, workflow)
                    await self._assert_sde_report_after_cleanup(client)
                    rejected = await self._prepare_rejected_sde_review(client, workflow)
                    await self._persist_rejected_sde_review(
                        client, rejected, workflow
                    )
                    return (
                        approved.candidate["candidate_id"],
                        approved.receipt["receipt_id"],
                    )

            try:
                asyncio.run(exercise())
            finally:
                workflow.store.close()

    def _create_mcp_sde_workflow(self, temporary: Path) -> _McpSdeWorkflow:
        """Build isolated consumer paths, store, plugin, and staged artifacts."""
        root = temporary / "consumer"
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
        database = temporary / "global.sqlite3"
        store = CuratorStore(database)
        plugin = self._bind_reviewable_mcp_project(store, root)
        return _McpSdeWorkflow(
            _McpSdePaths(root, database, staging, history),
            store,
            plugin,
            _McpSdeArtifacts(
                staging / "mcp-sde-goal" / "import" / "session-evidence.bin",
                staging / "mcp-sde-goal" / "scratch" / "reviewed-transient-canary.txt",
                b"TRANSIENT_CANARY_PURGE_AFTER_CANONICAL_WRITE",
            ),
        )

    def _mcp_sde_server(self, workflow: _McpSdeWorkflow) -> Any:
        """Build the authenticated in-memory MCP server for one workflow."""
        api = AuthenticatedCuratorAPI(
            {"mcp-project": workflow.plugin},
            AllowProject(),
            InMemoryTokenBucket(),
        )
        server = build_mcp_server(
            api,
            AuthenticatedCaller("host-subject"),
            "mcp-project",
            "mcp-sde-test-stream",
        )
        self._assert_sde_instruction_contract(" ".join((server.instructions or "").split()))
        return server

    async def _prepare_approved_sde_review(
        self, client: Client, workflow: _McpSdeWorkflow
    ) -> _McpSdeReview:
        """Produce verified facts, stage artifacts, and approve their exact inventory."""
        tools = await client.list_tools()
        self.assertIn("sde_assess", [tool.name for tool in tools.tools])
        started = await self._call_mcp_json(
            client,
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
        payload = b'{"temporary":true}\n'
        result = await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-m",
                "curatormd_v2.producer_cli",
                "--project-root",
                str(workflow.root),
                "--database",
                str(workflow.database),
                "--goal-id",
                "mcp-sde-goal",
                "--artifact-class",
                "import",
                "--artifact-id",
                "session-evidence",
            ],
            input=payload,
            capture_output=True,
            check=False,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(payload, result.stdout)
        producer_receipt = json.loads(result.stdout)
        self.assertEqual(Path(producer_receipt["path"]), workflow.staged)
        self.assertEqual(producer_receipt["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(workflow.staged.read_bytes(), payload)
        workflow.unheld_staged.parent.mkdir(parents=True)
        workflow.unheld_staged.write_bytes(workflow.unheld_payload)
        await self._record_approved_goal_facts(client)
        candidate = await self._assess_approved_goal(client)
        inventory = await self._call_mcp_json(
            client,
            "artifact_inventory_discover",
            {"goal_id": "mcp-sde-goal"},
        )
        self.assertEqual(len(inventory["artifacts"]), 2)
        reviewed_manifest = [
            (
                {
                    **artifact,
                    "retention_hold": "operational",
                    "reacquisition_action": "retain_under_hold",
                }
                if Path(artifact["path"]) == workflow.staged
                else {
                    **artifact,
                    "reacquisition_action": "not_required",
                }
            )
            for artifact in inventory["artifacts"]
        ]
        packet = await self._call_mcp_json(
            client,
            "sde_review_packet",
            {
                "candidate_id": candidate["candidate_id"],
                "review_artifacts": reviewed_manifest,
            },
        )
        self._assert_review_packet(packet, candidate, inventory, reviewed_manifest)
        receipt = await self._call_mcp_json(
            client,
            "sde_confirm",
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "approved",
                "artifacts": reviewed_manifest,
                "artifact_inventory_complete": True,
                "dependency_map_sha256": packet["dependency_map_sha256"],
                "rationale": "Human reviewer approved the bounded facts",
            },
        )
        self._assert_review_receipt(receipt, packet, workflow)
        return _McpSdeReview(candidate, receipt, workflow.staged)

    async def _record_approved_goal_facts(self, client: Client) -> None:
        """Record the change and passing verification before finishing the goal."""
        await self._call_mcp_json(
            client,
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
        await self._call_mcp_json(
            client,
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
                        "sha256": hashlib.sha256(b"mcp-proof").hexdigest(),
                        "outcome": "passed",
                    }
                ],
                "source_sequence": 3,
            },
        )
        finished = await self._call_mcp_json(
            client,
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
        completed = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-sde-goal"}
        )
        self.assertEqual(completed["goal"]["status"], "complete")

    async def _assess_approved_goal(self, client: Client) -> dict[str, Any]:
        """Create one review candidate and verify it appears in the queue."""
        candidate = await self._call_mcp_json(
            client,
            "sde_assess",
            {
                "goal_id": "mcp-sde-goal",
                "materiality": "implementation",
                "rationale": "A durable project change has passing evidence",
                "impact": "Observed local verification passed",
                "retrieval_value": "Helps maintainers find the contract",
                "fact_ids": ["mcp-sde-change", "mcp-sde-verification"],
            },
        )
        self.assertEqual(candidate["status"], "pending_review")
        queue = await self._call_mcp_json(client, "sde_review_queue", {})
        self.assertEqual(
            [item["candidate"]["candidate_id"] for item in queue],
            [candidate["candidate_id"]],
        )
        cards = await self._call_mcp_json(client, "sde_review_queue_cards", {})
        self.assertEqual(cards["project_id"], "mcp-project")
        self.assertEqual(
            [item["candidate"]["candidate_id"] for item in cards["candidates"]],
            [candidate["candidate_id"]],
        )
        serialized_cards = json.dumps(cards)
        self.assertNotIn("fact_ids", serialized_cards)
        self.assertNotIn("mcp-sde-change", serialized_cards)
        self.assertNotIn("facts", cards["candidates"][0])
        self.assertNotIn("receipt", cards["candidates"][0])
        return candidate

    def _assert_review_packet(
        self,
        packet: dict[str, Any],
        candidate: dict[str, Any],
        inventory: dict[str, Any],
        reviewed_manifest: list[dict[str, Any]],
    ) -> None:
        """Ensure the reviewer packet binds the exact candidate and inventory."""
        self.assertEqual(
            packet["detail"]["candidate"]["candidate_id"], candidate["candidate_id"]
        )
        self.assertEqual(packet["artifact_inventory"]["scope_goal_id"], "mcp-sde-goal")
        self.assertTrue(packet["artifact_inventory"]["usage"]["inventory_complete"])
        self.assertEqual(
            packet["artifact_inventory"]["artifacts"], inventory["artifacts"]
        )
        self.assertEqual(packet["review_artifacts"], reviewed_manifest)
        self.assertEqual(
            len(packet["artifact_dependencies"]), len(inventory["artifacts"])
        )
        self.assertEqual(len(packet["dependency_map_sha256"]), 64)
        self.assertTrue(inventory["usage"]["inventory_complete"])

    def _assert_review_receipt(
        self,
        receipt: dict[str, Any],
        packet: dict[str, Any],
        workflow: _McpSdeWorkflow,
    ) -> None:
        """Check reviewer and exact-cleanup authorization before persistence."""
        self.assertEqual(receipt["reviewer_id"], "host-subject")
        self.assertTrue(receipt["artifact_inventory_complete"])
        self.assertFalse(receipt["canonical_persisted"])
        self.assertTrue(receipt["cleanup_authorized"])
        self.assertEqual(
            receipt["cleanup_dependency_map_sha256"], packet["dependency_map_sha256"]
        )
        self.assertEqual(receipt["purge_status"], "purge_pending")
        self.assertTrue(workflow.staged.exists())

    async def _persist_sde_and_verify_pending_purge(
        self,
        client: Client,
        review: _McpSdeReview,
        workflow: _McpSdeWorkflow,
    ) -> None:
        """Persist canonical facts, purge unheld data, and inspect the held target."""
        pending_health = await self._call_mcp_json(client, "project_health", {})
        self.assertEqual(pending_health["status"], "degraded")
        self.assertEqual(
            pending_health["operational_counts"]["pending_expiry_purge_receipt_count"],
            0,
        )
        self.assertEqual(
            pending_health["operational_counts"]["pending_purge_receipt_count"], 1
        )
        self.assertTrue(review.receipt["artifact_inventory_complete"])
        self.assertFalse(review.receipt["canonical_persisted"])
        self.assertTrue(review.artifact.exists())
        self.assertTrue(workflow.unheld_staged.exists())
        inventory_health = await self._call_mcp_json(client, "project_health", {})
        self.assertEqual(
            inventory_health["operational_counts"]["pending_purge_artifact_count"], 2
        )
        await self._call_mcp_json(
            client,
            "goal_persist",
            {"goal_id": "mcp-sde-goal", "target": "persistence/HISTORY.md"},
        )
        self.assertTrue(review.artifact.exists())
        self.assertFalse(workflow.unheld_staged.exists())
        history_text = workflow.history.read_text()
        self.assertIn("Added the reviewed SDE assessment path", history_text)
        self.assertIn(review.receipt["receipt_id"], history_text)
        self.assertNotIn(workflow.unheld_payload.decode(), history_text)
        await self._assert_pending_purge_receipt(client, review, workflow)

    async def _assert_pending_purge_receipt(
        self,
        client: Client,
        review: _McpSdeReview,
        workflow: _McpSdeWorkflow,
    ) -> None:
        """Verify only the held file remains pending after canonical persistence."""
        purge_result = await self._call_mcp_json(
            client,
            "artifact_purge_status",
            {"receipt_id": review.receipt["receipt_id"]},
        )
        self.assertEqual(purge_result[0]["purge_status"], "purge_pending")
        self.assertTrue(purge_result[0]["canonical_persisted"])
        held_status = next(item for item in purge_result[1] if item["status"] == "held")
        self.assertEqual(held_status["artifact"]["retention_hold"], "operational")
        self.assertEqual(held_status["attempts"], 0)
        self.assertIsNotNone(held_status["created_at"])
        self.assertGreaterEqual(held_status["age_seconds"], 0)
        self.assertIsNone(held_status["last_attempt_at"])
        self.assertIsNone(held_status["next_attempt_at"])
        self.assertIsNone(held_status["next_attempt_in_seconds"])
        self.assertIsNone(held_status["last_attempt_age_seconds"])
        self.assertEqual(held_status["safe_recovery_action"], "release_artifact_hold")
        self.assertEqual(
            {item["status"] for item in purge_result[1]}, {"held", "purged"}
        )
        final_status = await self._call_mcp_json(
            client,
            "goal_status",
            {"goal_id": "mcp-sde-goal", "sde_offset": 0, "purge_offset": 0},
        )
        self.assertEqual(final_status["goal"]["status"], "complete")
        self.assertEqual(final_status["sde_candidates"][0]["status"], "approved")
        self.assertTrue(workflow.history.is_file())
        await self._assert_report_pending_purge(client, review)

    async def _assert_report_pending_purge(
        self, client: Client, review: _McpSdeReview
    ) -> None:
        """The report names the canonical write and unresolved held receipt."""
        result = await client.call_tool(
            "goal_report",
            {"goal_id": "mcp-sde-goal", "fact_offset": 0, "fact_limit": 8},
        )
        self.assertFalse(result.is_error)
        content = result.content[0]
        assert isinstance(content, TextContent)
        for expected in (
            "- Outcome: `complete` (lifecycle revision `2`)",
            "- Problem: Expose verified SDE assessment",
            "- Next action: none (goal is terminal).",
            "- [x] `evidence` — verified: The selected verification passes; "
            "proof facts: `mcp-sde-verification`",
            "`mcp-sde-verification` — verification: The integration evidence passed",
            f"Purge receipt {review.receipt['receipt_id']} remains pending",
            "canonical write verified at `persistence/HISTORY.md`",
            "purge `purge_pending`",
            "Resolve purge receipt",
        ):
            self.assertIn(expected, content.text)

    async def _finish_sde_hold_release(
        self, client: Client, review: _McpSdeReview, workflow: _McpSdeWorkflow
    ) -> None:
        """Check sanitized failure, retry, replay, and hold-release audit fields."""
        rationale = "Retention owner approved release"
        marker = "SENSITIVE_PURGE_EXCEPTION_SENTINEL"
        with patch.object(
            workflow.plugin.service.purger,
            "purge",
            side_effect=PurgeError(
                PurgeFailureCode.FILESYSTEM_ERROR,
                f"private path detail: {marker}",
            ),
        ):
            failed = await self._call_mcp_json(
                client,
                "release_artifact_hold",
                {
                    "receipt_id": review.receipt["receipt_id"],
                    "path": str(review.artifact),
                    "rationale": rationale,
                },
            )
        self.assertEqual(failed["purge_status"], "purge_pending")
        self.assertTrue(review.artifact.exists())
        failed_status = await self._call_mcp_json(
            client,
            "artifact_purge_status",
            {"receipt_id": review.receipt["receipt_id"]},
        )
        self.assertEqual(failed_status[1][0]["error"], "filesystem_error")
        self.assertNotIn(marker, json.dumps(failed_status))
        workflow.plugin.service.purger = ArtifactPurger(workflow.staging)
        self.assertEqual(
            workflow.plugin.service.retry_pending_purges()[0].purge_status.value,
            "complete",
        )
        self.assertFalse(review.artifact.exists())
        replay = await self._call_mcp_json(
            client,
            "release_artifact_hold",
            {
                "receipt_id": review.receipt["receipt_id"],
                "path": str(review.artifact),
                "rationale": rationale,
            },
        )
        self.assertEqual(replay["purge_status"], "complete")
        released = await self._call_mcp_json(
            client,
            "artifact_purge_status",
            {"receipt_id": review.receipt["receipt_id"]},
        )
        self.assertEqual(released[1][0]["status"], "purged")
        self.assertEqual(released[1][0]["hold_created_by"], "host-subject")
        self.assertEqual(released[1][0]["hold_released_by"], "host-subject")
        self.assertEqual(released[1][0]["hold_release_rationale"], rationale)

    async def _assert_sde_report_after_cleanup(self, client: Client) -> None:
        """The final report removes the resolved purge gate."""
        result = await client.call_tool("goal_report", {"goal_id": "mcp-sde-goal"})
        self.assertFalse(result.is_error)
        content = result.content[0]
        assert isinstance(content, TextContent)
        for expected in (
            "- Outcome: `complete` (lifecycle revision `2`)",
            "canonical write verified at `persistence/HISTORY.md`",
            "purge `complete`",
            "Purge `complete`: 1 receipt(s)",
            "## Current open gates\n- None recorded.",
            "## Open TODOs\n- None recorded for this goal.",
        ):
            self.assertIn(expected, content.text)
        self.assertNotIn("Resolve purge receipt", content.text)

    async def _prepare_rejected_sde_review(
        self, client: Client, workflow: _McpSdeWorkflow
    ) -> _McpSdeReview:
        """Build a bounded evidence case and reject its overstated impact claim."""
        await self._call_mcp_json(
            client,
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
        await self._call_mcp_json(
            client,
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
        await self._call_mcp_json(
            client,
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
                        "sha256": hashlib.sha256(b"mcp-proof").hexdigest(),
                        "outcome": "passed",
                    }
                ],
                "source_sequence": 7,
            },
        )
        await self._call_mcp_json(
            client,
            "goal_finish",
            {
                "event_id": "mcp-sde-event-8",
                "goal_id": "mcp-rejected-goal",
                "completion_claim": "The tested local change is complete",
                "expected_lifecycle_revision": 1,
                "source_sequence": 8,
            },
        )
        candidate = await self._call_mcp_json(
            client,
            "sde_assess",
            {
                "goal_id": "mcp-rejected-goal",
                "materiality": "implementation",
                "rationale": "The change establishes a broad durable production impact",
                "impact": "Expected production impact is unmeasured",
                "retrieval_value": "Helps distinguish claims from observed outcomes",
                "fact_ids": ["mcp-rejected-change", "mcp-rejected-verification"],
            },
        )
        artifact = workflow.staging / "mcp-rejected-goal" / "rejected-transient.json"
        artifact.parent.mkdir()
        artifact.write_text('{"temporary":"rejected"}\n')
        inventory = await self._call_mcp_json(
            client, "artifact_inventory_discover", {"goal_id": "mcp-rejected-goal"}
        )
        self.assertEqual(len(inventory["artifacts"]), 1)
        manifest = [
            {
                **inventory["artifacts"][0],
                "reacquisition_action": "not_required",
            }
        ]
        packet = await self._call_mcp_json(
            client,
            "sde_review_packet",
            {
                "candidate_id": candidate["candidate_id"],
                "review_artifacts": manifest,
            },
        )
        receipt = await self._call_mcp_json(
            client,
            "sde_confirm",
            {
                "candidate_id": candidate["candidate_id"],
                "decision": "rejected",
                "artifacts": manifest,
                "artifact_inventory_complete": True,
                "dependency_map_sha256": packet["dependency_map_sha256"],
                "rationale": "The evidence proves only a local test result",
            },
        )
        self.assertEqual(receipt["purge_status"], "purge_pending")
        self.assertTrue(receipt["cleanup_authorized"])
        self.assertTrue(artifact.exists())
        return _McpSdeReview(candidate, receipt, artifact)

    async def _persist_rejected_sde_review(
        self,
        client: Client,
        review: _McpSdeReview,
        workflow: _McpSdeWorkflow,
    ) -> None:
        """Persist rejected disposition and verify feedback, reconciliation, and purge."""
        await self._call_mcp_json(
            client,
            "sde_quality_feedback_record",
            {
                "feedback_id": "mcp-quality-feedback-1",
                "candidate_id": review.candidate["candidate_id"],
                "label": "not_useful",
                "rationale": "The proposed impact exceeded the test evidence",
            },
        )
        summary = await self._call_mcp_json(
            client, "sde_quality_feedback_summary", {}
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(dict(summary["counts"])["not_useful"], 1)
        await self._call_mcp_json(
            client,
            "goal_persist",
            {
                "goal_id": "mcp-rejected-goal",
                "target": "persistence/HISTORY.md",
            },
        )
        self.assertFalse(review.artifact.exists())
        reconciliation = await self._call_mcp_json(
            client,
            "goal_reconcile",
            {
                "goal_id": "mcp-rejected-goal",
                "target": "persistence/HISTORY.md",
            },
        )
        self.assertEqual(reconciliation["status"], "synced")
        project = await self._call_mcp_json(
            client,
            "project_reconcile",
            {"target": "persistence/HISTORY.md", "offset": 0, "limit": 10},
        )
        goal_states = {
            item["goal_id"]: item["status"] for item in project["goals"]
        }
        self.assertEqual(goal_states["mcp-rejected-goal"], "synced")
        self.assertTrue(project["inventory_complete"])
        self.assertFalse(review.artifact.exists())
        history_text = workflow.history.read_text()
        self.assertIn("Added a bounded local implementation", history_text)
        self.assertIn(review.receipt["receipt_id"], history_text)
        self.assertNotIn(
            "The change establishes a broad durable production impact", history_text
        )
        rejected_status = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-rejected-goal"}
        )
        self.assertEqual(rejected_status["sde_candidates"][0]["status"], "rejected")
        purge = await self._call_mcp_json(
            client,
            "artifact_purge_status",
            {"receipt_id": review.receipt["receipt_id"]},
        )
        self.assertEqual(purge[0]["purge_status"], "complete")
        self.assertEqual({item["status"] for item in purge[1]}, {"purged"})
