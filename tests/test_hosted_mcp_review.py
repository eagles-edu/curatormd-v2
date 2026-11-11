"""Owner review authorization through the attended hosted MCP process."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_api import TestVerifier
from test_hosted_mcp import HostedMcpFixtures, hermes_meta

from mcp import Client
from mcp.types import TextContent

from curatormd_v2 import (
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    Materiality,
    SuccessCriterion,
)
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.service import SDEAssessmentRequest


class HostedMcpReviewTests(HostedMcpFixtures, unittest.TestCase):
    """Exercise an evidence-backed acceptance using the local OS reviewer."""

    def test_outline_exposes_single_check_completion_claim_for_review(self) -> None:
        """Expose an outcome claim alongside its recorded task proof."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(
                root, database, "reviewer-profile", allow_write=True, allow_review=True
            )
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_write=True,
                allow_review=True,
                evidence_verifier=TestVerifier(),
            )
            try:
                plugin = getattr(runtime.api, "_plugins")["bound-project"]
                goal = plugin.service.goal_start(
                    "Expose a completed one-check task in the review outline",
                    (SuccessCriterion("works", "The change works"),),
                )
                changed, _ = plugin.service.goal_fact(
                    goal.goal_id, FactKind.CHANGE, "The tested change is ready for review."
                )
                verified, _ = plugin.service.goal_fact(
                    goal.goal_id, FactKind.VERIFICATION, "The local check passed.",
                    criterion_id="works",
                    evidence=(EvidenceRef("unit-test", "test-proof:verified", "0" * 64, EvidenceOutcome.PASSED),),
                )
                completed = plugin.service.goal_finish(
                    goal.goal_id,
                    "Checks passed: `python -m unittest tests.test_example` passed.",
                    expected_lifecycle_revision=goal.lifecycle_revision,
                )
                candidate = plugin.sde_assess(
                    SDEAssessmentRequest(
                        goal_id=goal.goal_id,
                        materiality=Materiality.IMPLEMENTATION,
                        rationale="Retain the completed task outcome for owner review.",
                        fact_ids=(changed.fact_id, verified.fact_id),
                        impact="The task has a passing one-check completion result.",
                        retrieval_value="Use the review outline to inspect task proof.",
                    )
                )

                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        result = await client.call_tool(
                            "sde_review_outline",
                            {"candidate_id": candidate.candidate_id},
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(result.is_error)
                        content = result.content[0]
                        assert isinstance(content, TextContent)
                        outline = json.loads(content.text)
                        self.assertEqual(outline["goal_status"], "complete")
                        self.assertTrue(outline["successful_completion_evidence_current"])
                        self.assertEqual(
                            outline["completion_claim"]["bullet"],
                            "Completion claim: Checks passed: `python -m unittest "
                            "tests.test_example` passed.",
                        )
                        self.assertEqual(
                            [fact["fact_id"] for fact in outline["supporting_facts"]],
                            [changed.fact_id, verified.fact_id],
                        )
                        self.assertEqual(
                            completed.lifecycle_revision, outline["lifecycle_revision"]
                        )

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_refreshing_stale_review_reopens_goal_and_withdraws_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(
                root, database, "reviewer-profile", allow_write=True, allow_review=True
            )

            class SwitchableVerifier(TestVerifier):
                """Make new verification unavailable after the proof was recorded."""

                stale = False

                def attest(
                    self,
                    evidence: EvidenceRef,
                    context: EvidenceVerificationContext,
                ) -> EvidenceAttestation | None:
                    if self.stale:
                        return None
                    return super().attest(evidence, context)

            verifier = SwitchableVerifier()
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_write=True,
                allow_review=True,
                evidence_verifier=verifier,
            )
            try:
                plugin = getattr(runtime.api, "_plugins")["bound-project"]
                goal = plugin.service.goal_start(
                    "Refresh stale SDE evidence through hosted MCP",
                    (SuccessCriterion("verified", "The selected verification passes"),),
                )
                change, _ = plugin.service.goal_fact(
                    goal.goal_id, FactKind.CHANGE, "The fixture change is ready for review."
                )
                evidence = EvidenceRef(
                    "unit-test", "test-proof:verified", "0" * 64,
                    EvidenceOutcome.PASSED,
                )
                verification, _ = plugin.service.goal_fact(
                    goal.goal_id,
                    FactKind.VERIFICATION,
                    "The fixture verification passed.",
                    criterion_id="verified",
                    evidence=(evidence,),
                )
                completed = plugin.service.goal_finish(
                    goal.goal_id,
                    "The selected verification passed.",
                    expected_lifecycle_revision=goal.lifecycle_revision,
                )
                candidate = plugin.sde_assess(
                    SDEAssessmentRequest(
                        goal_id=goal.goal_id,
                        materiality=Materiality.IMPLEMENTATION,
                        rationale="Exercise recovery of stale review evidence.",
                        fact_ids=(change.fact_id, verification.fact_id),
                        impact="The owner can refresh evidence without losing facts.",
                        retrieval_value="Use a new proof epoch before creating a new proposal.",
                    )
                )
                before_fact_ids = tuple(
                    fact.fact_id
                    for fact in plugin.service.store.list_facts(goal.goal_id, "bound-project")
                )
                verifier.stale = True

                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        outline_result = await client.call_tool(
                            "sde_review_outline",
                            {"candidate_id": candidate.candidate_id},
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(outline_result.is_error)
                        outline_content = outline_result.content[0]
                        assert isinstance(outline_content, TextContent)
                        outline = json.loads(outline_content.text)
                        self.assertEqual(outline["evidence_status"], "current_passing")
                        self.assertEqual(outline["goal_status"], "complete")

                        reopen_result = await client.call_tool(
                            "goal_reopen",
                            {
                                "event_id": "stale-review-reopen-event",
                                "goal_id": goal.goal_id,
                                "reason": "Refresh the expired proof for review.",
                                "next_action": "Record current evidence before a new proposal.",
                                "expected_lifecycle_revision": completed.lifecycle_revision,
                            },
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(reopen_result.is_error)
                        reopen_content = reopen_result.content[0]
                        assert isinstance(reopen_content, TextContent)
                        self.assertEqual(json.loads(reopen_content.text)["status"], "processed")

                        reopened_outline = await client.call_tool(
                            "sde_review_outline",
                            {"candidate_id": candidate.candidate_id},
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(reopened_outline.is_error)
                        reopened_content = reopened_outline.content[0]
                        assert isinstance(reopened_content, TextContent)
                        self.assertEqual(
                            json.loads(reopened_content.text)["evidence_status"],
                            "not_current_or_missing",
                        )

                        withdrawal_result = await client.call_tool(
                            "sde_withdraw_candidates",
                            {
                                "candidate_ids": [candidate.candidate_id],
                                "rationale": "Clear the stale proposal to refresh its source evidence.",
                            },
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(withdrawal_result.is_error)
                        withdrawal_content = withdrawal_result.content[0]
                        assert isinstance(withdrawal_content, TextContent)
                        withdrawals = json.loads(withdrawal_content.text)
                        self.assertEqual(len(withdrawals), 1)
                        self.assertEqual(withdrawals[0]["candidate_id"], candidate.candidate_id)
                        self.assertEqual(
                            withdrawals[0]["reviewer_id"], f"local-uid:{os.geteuid()}"
                        )

                asyncio.run(exercise())
                after_fact_ids = tuple(
                    fact.fact_id
                    for fact in plugin.service.store.list_facts(goal.goal_id, "bound-project")
                )
                self.assertTrue(set(before_fact_ids).issubset(after_fact_ids))
                self.assertEqual(len(after_fact_ids), len(before_fact_ids) + 1)
                self.assertEqual(
                    plugin.service.store.get_sde_candidate(
                        candidate.candidate_id, "bound-project"
                    ).status.value,
                    "withdrawn",
                )
            finally:
                runtime.close()

    def test_local_review_grant_accepts_current_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "reviewer-profile", allow_review=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_review=True,
                evidence_verifier=TestVerifier(),
            )
            try:
                plugin = getattr(runtime.api, "_plugins")["bound-project"]
                goal = plugin.service.goal_start(
                    "Exercise attended local acceptance",
                    (SuccessCriterion("verified", "The selected verification passes"),),
                )
                change, _ = plugin.service.goal_fact(
                    goal.goal_id, FactKind.CHANGE, "The fixture change is ready for review."
                )
                evidence = EvidenceRef(
                    "unit-test", "test-proof:verified", "0" * 64,
                    EvidenceOutcome.PASSED,
                )
                verification, _ = plugin.service.goal_fact(
                    goal.goal_id,
                    FactKind.VERIFICATION,
                    "The fixture verification passed.",
                    criterion_id="verified",
                    evidence=(evidence,),
                )
                completed_goal = plugin.service.goal_finish(
                    goal.goal_id,
                    "The selected verification passed.",
                    expected_lifecycle_revision=goal.lifecycle_revision,
                )
                candidate = plugin.sde_assess(
                    SDEAssessmentRequest(
                        goal_id=goal.goal_id,
                        materiality=Materiality.IMPLEMENTATION,
                        rationale="Exercise a current evidence-backed owner decision.",
                        fact_ids=(change.fact_id, verification.fact_id),
                        impact="The local review path can retain a verified outcome.",
                        retrieval_value="Use the fixture to diagnose alpha approvals.",
                    )
                )

                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        outline_result = await client.call_tool(
                            "sde_review_outline",
                            {"candidate_id": candidate.candidate_id},
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(outline_result.is_error)
                        outline_content = outline_result.content[0]
                        assert isinstance(outline_content, TextContent)
                        outline = json.loads(outline_content.text)
                        self.assertEqual(outline["evidence_status"], "current_passing")
                        self.assertEqual(outline["goal_status"], "complete")
                        self.assertEqual(
                            outline["lifecycle_revision"],
                            completed_goal.lifecycle_revision,
                        )
                        packet_result = await client.call_tool(
                            "sde_review_packet",
                            {"candidate_id": candidate.candidate_id},
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(packet_result.is_error)
                        packet_content = packet_result.content[0]
                        assert isinstance(packet_content, TextContent)
                        packet = json.loads(packet_content.text)
                        result = await client.call_tool(
                            "sde_confirm",
                            {
                                "candidate_id": candidate.candidate_id,
                                "decision": "approved",
                                "artifacts": packet["artifact_inventory"]["artifacts"],
                                "artifact_inventory_complete": packet[
                                    "artifact_inventory"
                                ]["usage"]["inventory_complete"],
                                "dependency_map_sha256": packet[
                                    "dependency_map_sha256"
                                ],
                                "rationale": "Accept the current passing fixture evidence.",
                            },
                            meta=hermes_meta("reviewer-profile"),
                        )
                        self.assertFalse(result.is_error)
                        receipt_content = result.content[0]
                        assert isinstance(receipt_content, TextContent)
                        receipt = json.loads(receipt_content.text)
                        self.assertEqual(receipt["decision"], "approved")
                        self.assertEqual(
                            receipt["reviewer_id"], f"local-uid:{os.geteuid()}"
                        )

                asyncio.run(exercise())
            finally:
                runtime.close()

    def test_edited_review_json_string_survives_mcp_argument_validation(self) -> None:
        """Keep JSON text as a string through the MCP SDK's argument pre-parser."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "global.sqlite3"
            self._provision(root, database, "reviewer-profile", allow_review=True)
            runtime = build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="reviewer-profile",
                allow_review=True,
                evidence_verifier=TestVerifier(),
            )
            try:
                plugin = getattr(runtime.api, "_plugins")["bound-project"]
                goal = plugin.service.goal_start(
                    "Confirm an edited SDE draft through MCP",
                    (SuccessCriterion("verified", "The selected verification passes"),),
                )
                change, _ = plugin.service.goal_fact(
                    goal.goal_id, FactKind.CHANGE, "The fixture change is ready for review."
                )
                evidence = EvidenceRef(
                    "unit-test", "test-proof:verified", "0" * 64,
                    EvidenceOutcome.PASSED,
                )
                verification, _ = plugin.service.goal_fact(
                    goal.goal_id,
                    FactKind.VERIFICATION,
                    "The fixture verification passed.",
                    criterion_id="verified",
                    evidence=(evidence,),
                )
                plugin.service.goal_finish(
                    goal.goal_id,
                    "The selected verification passed.",
                    expected_lifecycle_revision=goal.lifecycle_revision,
                )
                candidate = plugin.sde_assess(
                    SDEAssessmentRequest(
                        goal_id=goal.goal_id,
                        materiality=Materiality.IMPLEMENTATION,
                        rationale="Exercise the edited SDE MCP path.",
                        fact_ids=(change.fact_id, verification.fact_id),
                        impact="An edited review can be recorded against current proof.",
                        retrieval_value="Preserve the tested behavior of edited SDE review.",
                    )
                )
                assert candidate is not None
                draft_json = json.dumps(
                    {
                        "title": "Keep the tested fixture result",
                        "significance": 4,
                        "documents": ["persistence/HISTORY.md"],
                        "problem": "The reviewed outcome needs a durable record.",
                        "completed": ["Implemented and verified the fixture change."],
                        "difficulties": [],
                        "plan_changes": [],
                        "lessons": [],
                        "future_utility": "Use this entry to verify edited review handling.",
                    }
                )

                async def exercise() -> None:
                    async with Client(runtime.server, raise_exceptions=False) as client:
                        meta = hermes_meta("reviewer-profile")
                        packet_result = await client.call_tool(
                            "sde_review_packet",
                            {"candidate_id": candidate.candidate_id},
                            meta=meta,
                        )
                        self.assertFalse(packet_result.is_error)
                        packet_content = packet_result.content[0]
                        assert isinstance(packet_content, TextContent)
                        packet = json.loads(packet_content.text)
                        arguments = {
                            "candidate_id": candidate.candidate_id,
                            "decision": "approved",
                            "artifacts": packet["artifact_inventory"]["artifacts"],
                            "artifact_inventory_complete": packet["artifact_inventory"][
                                "usage"
                            ]["inventory_complete"],
                            "dependency_map_sha256": packet["dependency_map_sha256"],
                            "rationale": "Accept the edited, evidence-backed fixture entry.",
                            "review_draft_json": draft_json,
                        }
                        binding_result = await client.call_tool(
                            "sde_prepare_review_binding", arguments, meta=meta
                        )
                        self.assertFalse(binding_result.is_error)
                        binding_content = binding_result.content[0]
                        assert isinstance(binding_content, TextContent)
                        binding = json.loads(binding_content.text)
                        confirmed = await client.call_tool(
                            "sde_confirm",
                            {
                                **arguments,
                                "expected_review_binding_sha256": binding["sha256"],
                            },
                            meta=meta,
                        )
                        self.assertFalse(confirmed.is_error)
                        receipt_content = confirmed.content[0]
                        assert isinstance(receipt_content, TextContent)
                        receipt = json.loads(receipt_content.text)
                        self.assertEqual(receipt["decision"], "approved")
                        self.assertEqual(
                            json.loads(receipt["review_draft_json"]),
                            json.loads(draft_json),
                        )

                asyncio.run(exercise())
            finally:
                runtime.close()
