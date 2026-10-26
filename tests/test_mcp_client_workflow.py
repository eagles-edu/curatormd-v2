"""MCP client goal lifecycle workflow tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from mcp import Client
from mcp.types import TextContent
from project_fixtures import create_consumer_repo
from purge_fixtures import approved_empty_inventory_request
from test_mcp_server import (
    AllowProject,
    McpServerTestSupport,
    _McpClientWorkflow,  # pyright: ignore[reportPrivateUsage]
)

from curatormd_v2 import (
    ArtifactRef,
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    InMemoryTokenBucket,
    Materiality,
    ProjectPlugin,
    SuccessCriterion,
    build_mcp_server,
)
from curatormd_v2.service import SDEAssessmentRequest


class McpClientWorkflowTests(McpServerTestSupport):
    """MCP client goal lifecycle workflow tests."""

    def test_mcp_client_drives_a_project_bound_evidence_gated_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workflow = self._create_mcp_client_workflow(Path(temporary))
            try:
                names = asyncio.run(self._exercise_mcp_client_workflow(workflow))
                self._assert_mcp_client_tool_names(names)
            finally:
                workflow.store.close()

    def _create_mcp_client_workflow(self, temporary: Path) -> _McpClientWorkflow:
        """Create isolated project state and one reviewable evidence candidate."""
        root = temporary / "consumer"
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
        store = CuratorStore(temporary / "global.sqlite3")
        plugin = self._bind_reviewable_mcp_project(store, root)
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
            SDEAssessmentRequest(
                reviewed_goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The implementation is durable and verified",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        plugin.service.sde_confirm(
            approved_empty_inventory_request(candidate.candidate_id),
            authenticated_subject="host-subject",
        )
        api = AuthenticatedCuratorAPI(
            {"mcp-project": plugin},
            AllowProject(),
            InMemoryTokenBucket(),
        )
        server = build_mcp_server(
            api, AuthenticatedCaller("host-subject"), "mcp-project", "mcp-test-stream"
        )
        return _McpClientWorkflow(store, plugin, candidate.candidate_id, server)

    async def _exercise_mcp_client_workflow(
        self, workflow: _McpClientWorkflow
    ) -> list[str]:
        """Drive the same goal, review, archive, and health flow over MCP."""
        async with Client(workflow.server, raise_exceptions=True) as client:
            names = await self._assert_mcp_tool_annotations(client)
            await self._record_mcp_sde_correction(client, workflow.candidate_id)
            await self._assert_mcp_goal_stays_open(client)
            await self._complete_mcp_goal(client)
            await self._reopen_mcp_goal(client)
            await self._amend_and_compact_mcp_facts(client, names)
            await self._assert_mcp_usage_and_activity(client, workflow.plugin)
            await self._assert_mcp_health_and_metrics(client)
            await self._assert_mcp_inventories(client)
            await self._activate_planned_mcp_goal(client, names)
        return names

    async def _assert_mcp_tool_annotations(self, client: Client) -> list[str]:
        """Keep read-only and mutating tool hints explicit in MCP discovery."""
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
            "sde_review_queue_cards",
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
        return names

    async def _record_mcp_sde_correction(
        self, client: Client, candidate_id: str
    ) -> None:
        """Verify correction attribution and candidate binding over MCP."""
        correction_result = await client.call_tool(
            "sde_correction_record",
            {
                "correction_id": "mcp-correction-1",
                "candidate_id": candidate_id,
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
            correction_value["candidate_id"], candidate_id
        )

    async def _assert_mcp_goal_stays_open(self, client: Client) -> None:
        """Check that an unsupported completion claim leaves its gate open."""
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

    async def _complete_mcp_goal(self, client: Client) -> None:
        """Verify a current evidence fact allows the goal to complete."""
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

    async def _reopen_mcp_goal(self, client: Client) -> None:
        """Verify reopening creates a fresh evidence epoch."""
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

    async def _amend_and_compact_mcp_facts(
        self, client: Client, names: list[str]
    ) -> None:
        """Verify criteria amendment and exact reviewer-approved compaction."""
        await self._amend_mcp_goal_criteria(client)
        approval_value = await self._approve_mcp_fact_compaction(client)
        await self._assert_mcp_fact_archive(client, approval_value)
        self.assertIn("fact_compaction_propose", names)
        self.assertIn("fact_compaction_approve", names)

    async def _amend_mcp_goal_criteria(self, client: Client) -> None:
        """Check the revised goal criteria and lifecycle revisions."""
        await self._call_mcp_json(
            client,
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
        amended_value = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-goal-1"}
        )
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

    async def _assert_mcp_usage_and_activity(
        self, client: Client, plugin: ProjectPlugin
    ) -> None:
        """Check content-free storage and activity accounting over MCP."""
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
        lifecycle_counts = {
            item["status"]: item["count"]
            for item in activity_value["goal_status_counts"]
        }
        self.assertEqual(
            set(lifecycle_counts),
            {
                "planned", "active", "complete", "open",
                "blocked", "deferred", "cancelled", "superseded",
            },
        )
        self.assertEqual(sum(lifecycle_counts.values()), 2)
        self.assertGreater(activity_value["event_receipt_count"], 0)

    async def _assert_mcp_health_and_metrics(self, client: Client) -> None:
        """Verify unknown dependencies remain degraded in health and metrics."""
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

    async def _assert_mcp_inventories(self, client: Client) -> None:
        """Verify empty goal, project, and expiry inventories over MCP."""
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

    async def _approve_mcp_fact_compaction(
        self, client: Client
    ) -> dict[str, Any]:
        """Approve the exact compact-fact proposal through the MCP tools."""
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
        proposal_value = await self._call_mcp_json(
            client,
            "fact_compaction_propose",
            {"goal_id": "mcp-goal-1", "max_facts": 8},
        )
        approval_value = await self._call_mcp_json(
            client,
            "fact_compaction_approve",
            {
                "compaction_id": proposal_value["compaction_id"],
                "goal_id": "mcp-goal-1",
                "fact_ids": ["mcp-routine-1"],
                "source_sha256": proposal_value["source_sha256"],
                "approval_reason": "Approved the exact routine fact preview",
            },
        )
        self.assertEqual(approval_value["reviewer_id"], "host-subject")
        self.assertEqual(approval_value["fact_ids"], ["mcp-routine-1"])
        return approval_value

    async def _assert_mcp_fact_archive(
        self, client: Client, approval_value: dict[str, Any]
    ) -> None:
        """Check canonical fact retention and its exact archive receipt."""
        archived_status_value = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-goal-1"}
        )
        self.assertTrue(
            any(
                fact["fact_id"] == "mcp-routine-1"
                and fact["bullet"]
                == "Reviewed the compact fact archive workflow"
                for fact in archived_status_value["facts"]
            )
        )
        archive_receipts = await self._call_mcp_json(
            client,
            "fact_archive_receipts",
            {"goal_id": "mcp-goal-1", "offset": 0, "limit": 10},
        )
        self.assertEqual(len(archive_receipts), 1)
        self.assertEqual(
            archive_receipts[0]["archive_sha256"],
            approval_value["archive_sha256"],
        )

    async def _activate_planned_mcp_goal(
        self, client: Client, names: list[str]
    ) -> None:
        """Check planned state, pagination, and explicit activation."""
        await self._call_mcp_json(
            client,
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
        page_value = await self._call_mcp_json(
            client, "goal_list_page", {"offset": 0, "limit": 1}
        )
        self.assertEqual(page_value["total"], 3)
        self.assertEqual(page_value["next_offset"], 1)
        self.assertEqual(len(page_value["goals"]), 1)
        self.assertNotIn("facts", page_value["goals"][0])
        children_value = await self._call_mcp_json(
            client,
            "goal_children_page",
            {
                "parent_goal_id": "mcp-goal-1",
                "offset": 0,
                "limit": 5,
            },
        )
        self.assertEqual(children_value["total"], 0)
        self.assertIsNone(children_value["next_offset"])
        planned_value = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-goal-planned"}
        )
        self.assertEqual(planned_value["goal"]["status"], "planned")
        await self._call_mcp_json(
            client,
            "goal_activate",
            {
                "event_id": "mcp-event-9",
                "goal_id": "mcp-goal-planned",
                "reason": "User accepted implementation",
                "expected_lifecycle_revision": 1,
                "source_sequence": 8,
            },
        )
        active_value = await self._call_mcp_json(
            client, "goal_status", {"goal_id": "mcp-goal-planned"}
        )
        self.assertEqual(active_value["goal"]["status"], "active")
        self.assertEqual(active_value["goal"]["lifecycle_revision"], 2)
        self.assertIn("goal_activate", names)

    def _assert_mcp_client_tool_names(self, names: list[str]) -> None:
        """Ensure the lifecycle exposes the full V2 tool surface."""
        for name in (
            "goal_start",
            "goal_list_page",
            "goal_children_page",
            "goal_activate",
            "goal_bullet_projection",
            "goal_report",
            "fact_archive_receipts",
            "fact_record",
            "sde_confirm",
            "sde_correction_record",
            "sde_quality_feedback_record",
            "sde_quality_feedback_summary",
            "project_storage_usage",
            "artifact_inventory_discover",
            "project_artifact_inventory_discover",
            "project_expiry_inventory_discover",
            "sde_review_packet",
            "goal_reopen",
            "goal_amend_criteria",
            "goal_cancel",
            "goal_supersede",
            "event_queue_status",
            "project_activity_status",
            "project_health",
            "project_metrics",
            "event_quarantine_retry",
        ):
            self.assertIn(name, names)
        self.assertNotIn("project_id", names)
        self.assertNotIn("caller", names)
