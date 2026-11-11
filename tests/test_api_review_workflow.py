"""SDE review lifecycle API regression tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from typing import NoReturn
from unittest.mock import patch

from test_api import (
    AllowProject,
    ArtifactRef,
    AuthenticatedCuratorAPI,
    BytesIO,
    EvidenceGateError,
    FactKind,
    Materiality,
    NotFoundError,
    CuratorStore,
    ProjectAction,
    ProjectConfig,
    ProjectPlugin,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewDecision,
    ReviewHost,
    SDEAssessmentRequest,
    SDEConfirmationRequest,
    SuccessCriterion,
    TestVerifier,
    _ApiTestSupport,
    hashlib,
    json,
)
from curatormd_v2 import (
    AuditReceipt,
    AuthenticatedCaller,
    ConflictError,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    SDECandidate,
)
from curatormd_v2.sde_review_draft import SDEReviewBinding, SDEReviewDraft


class ApiReviewWorkflowTests(_ApiTestSupport):
    """Exercise apireviewworkflow behavior."""

    def test_unattested_result_can_be_proposed_and_owner_approved(self) -> None:
        """Keep missing proof visible without blocking recording or owner review."""
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost())
        api = self._api_with_healthy_dependencies(plugin, AllowProject({
            ("hermes-user-1", "project-a", ProjectAction.READ),
            ("hermes-user-1", "project-a", ProjectAction.WRITE),
            ("hermes-user-1", "project-a", ProjectAction.REVIEW),
        }))
        goal = plugin.service.goal_start("Remove prose wrapping", (SuccessCriterion("done", "Prose lines are joined"),))
        change, _ = plugin.service.goal_fact(goal.goal_id, FactKind.CHANGE, "Joined the prose lines.")
        candidate = api.sde_assess(self.caller, "project-a", SDEAssessmentRequest(
            goal.goal_id, Materiality.IMPLEMENTATION, "Useful editor change",
            (change.fact_id,), "Paragraphs can be joined", "Find the editor change",
        ))
        self.assertEqual(candidate.status.value, "pending_review")
        completed = plugin.service.goal_finish(goal.goal_id, "Observed: prose lines are joined")
        self.assertEqual(completed.status.value, "complete")
        self.assertEqual(plugin.service.goal_status(goal.goal_id).criteria[0].status.value, "open")
        self.assertFalse(plugin.service.sde_review_has_current_passing_evidence(candidate.candidate_id))
        draft = SDEReviewDraft(title="Join prose", significance=3,
            documents=("persistence/HISTORY.md",), problem="Wrapped prose",
            completed=("Joined prose",), difficulties=(), plan_changes=(), lessons=(),
            future_utility="Readable paragraphs")
        request = SDEConfirmationRequest(candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED, artifacts=(), artifact_inventory_complete=False,
            dependency_map_sha256="0" * 64, rationale="Owner approved", review_draft=draft)
        binding = api.prepare_sde_review_binding(self.caller, "project-a", request)
        receipt = api.sde_confirm(self.caller, "project-a", replace(request, expected_review_binding_sha256=binding.sha256()))
        self.assertEqual(receipt.decision, ReviewDecision.APPROVED)
        self.assertFalse(receipt.cleanup_authorized)

    def test_changed_artifact_does_not_block_persistence_or_authorize_purge(self) -> None:
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost())
        verified = self._create_verified_goal(plugin, "Retain reviewed work", "Change made", "Check passed")
        staged = plugin.stage_artifact(verified.goal_id, "scratch", "changed", BytesIO(b"before"))
        api = self._api_with_healthy_dependencies(plugin, AllowProject({
            ("hermes-user-1", "project-a", ProjectAction.READ),
            ("hermes-user-1", "project-a", ProjectAction.WRITE),
            ("hermes-user-1", "project-a", ProjectAction.REVIEW),
        }))
        candidate = api.sde_assess(self.caller, "project-a", SDEAssessmentRequest(
            verified.goal_id, Materiality.IMPLEMENTATION, "Retain change",
            (verified.change_fact_id, verified.verification_fact_id), "Useful change", "Useful later",
        ))
        initial = api.sde_review_packet(self.caller, "project-a", candidate.candidate_id)
        artifacts = tuple(replace(item, reacquisition_action=ReacquisitionAction.NOT_REQUIRED)
                          for item in initial.artifact_inventory.artifacts)
        packet = api.sde_review_packet(self.caller, "project-a", candidate.candidate_id, artifacts)
        draft = SDEReviewDraft(title="Reviewed change", significance=3,
            documents=("persistence/HISTORY.md",), problem="Review the change",
            completed=("Change made",), difficulties=(), plan_changes=(), lessons=(), future_utility="Useful later")
        request = SDEConfirmationRequest(candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED, artifacts=artifacts, artifact_inventory_complete=True,
            dependency_map_sha256=packet.dependency_map_sha256, rationale="Owner approved", review_draft=draft)
        binding = api.prepare_sde_review_binding(self.caller, "project-a", request)
        receipt = api.sde_confirm(self.caller, "project-a", replace(request, expected_review_binding_sha256=binding.sha256()))
        Path(staged.path).write_bytes(b"changed after review")
        for prepare in (True, False):
            api.sde_project_review_target(self.caller, "project-a", receipt.receipt_id,
                                          "persistence/HISTORY.md", prepare_only=prepare)
        pending = api.sde_finalize_review_projection(self.caller, "project-a", receipt.receipt_id)
        self.assertTrue(pending.canonical_persisted)
        self.assertEqual(pending.purge_status.value, "purge_pending")
        self.assertEqual(Path(staged.path).read_bytes(), b"changed after review")
        cleanup = self.store.cleanup_authorization(receipt.receipt_id, "project-a")
        assert cleanup is not None
        self.assertFalse(cleanup.canonical_persisted)
        retry = api.sde_finalize_review_projection(self.caller, "project-a", receipt.receipt_id)
        self.assertEqual(retry.receipt_id, pending.receipt_id)
        self.assertEqual(retry.purge_status.value, "purge_pending")

    def test_owner_evidence_override_persists_and_replays(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(plugin, "Review override", "Change made", "Check passed")
        staged = plugin.stage_artifact(verified.goal_id, "scratch", "held-for-inventory", BytesIO(b"keep"))
        api = self._api_with_healthy_dependencies(plugin, AllowProject({
            ("hermes-user-1", "project-a", ProjectAction.READ),
            ("hermes-user-1", "project-a", ProjectAction.WRITE),
            ("hermes-user-1", "project-a", ProjectAction.REVIEW),
        }))
        candidate = api.sde_assess(self.caller, "project-a", SDEAssessmentRequest(
            verified.goal_id, Materiality.IMPLEMENTATION, "Retain useful change",
            (verified.change_fact_id, verified.verification_fact_id), "Useful change", "Useful later",
        ))
        goal = plugin.service.goal_status(verified.goal_id).goal
        plugin.service.goal_reopen(verified.goal_id, "Continue work", "Check again", expected_lifecycle_revision=goal.lifecycle_revision)
        draft = SDEReviewDraft(title="Reviewed change", significance=3,
            documents=("persistence/HISTORY.md",), problem="Review the change",
            completed=("Change made",), difficulties=(), plan_changes=(), lessons=(),
            future_utility="Useful later")
        request = SDEConfirmationRequest(candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED, artifacts=(),
            artifact_inventory_complete=False, dependency_map_sha256="0" * 64,
            rationale="Owner approved", review_draft=draft)
        self.assertIsNotNone(api.prepare_sde_review_binding(self.caller, "project-a", request))
        request = replace(request, evidence_override_reason="Owner reviewed despite missing evidence")
        binding = api.prepare_sde_review_binding(self.caller, "project-a", request)
        self.assertEqual(SDEReviewBinding.from_json(binding.canonical_bytes().decode()), binding)
        request = replace(request, expected_review_binding_sha256=binding.sha256())
        with self.assertRaises(ConflictError):
            api.sde_confirm(self.caller, "project-a", replace(request, evidence_override_reason="Different reason"))
        receipt = api.sde_confirm(self.caller, "project-a", request)
        self.assertFalse(receipt.cleanup_authorized)
        self.assertEqual(api.sde_confirm(self.caller, "project-a", request).receipt_id, receipt.receipt_id)
        for prepare in (True, False):
            api.sde_project_review_target(self.caller, "project-a", receipt.receipt_id,
                                          "persistence/HISTORY.md", prepare_only=prepare)
        saved = (self.root / "persistence/HISTORY.md").read_text()
        self.assertIn("Owner reviewed despite missing evidence", saved)
        self.assertIn("Cleanup inventory: incomplete; no artifacts authorized for deletion.", saved)
        result = api.sde_finalize_review_projection(self.caller, "project-a", receipt.receipt_id)
        self.assertTrue(result.canonical_persisted)
        self.assertFalse(result.cleanup_authorized)
        self.assertEqual(result.purge_status.value, "purge_pending")
        self.assertTrue(Path(staged.path).exists())

    def test_single_check_completion_proof_is_enough_for_sde_approval(self) -> None:
        """Use the recorded attestation for an ordinary local check."""

        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        goal = plugin.service.goal_start(
            "Retain a locally tested task outcome",
            (SuccessCriterion("works", "The change works"),),
        )
        changed, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Implemented the requested small change"
        )
        verified, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.VERIFICATION, "The local check passed.",
            criterion_id="works",
            evidence=(EvidenceRef("unit-test", "test-proof:verified", "0" * 64, EvidenceOutcome.PASSED),),
        )
        plugin.service.goal_finish(
            goal.goal_id, "Checks passed: `uv run pytest tests/test_small.py` passed."
        )
        reviewer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.READ),
                ("hermes-user-1", "project-a", ProjectAction.WRITE),
                ("hermes-user-1", "project-a", ProjectAction.REVIEW),
            }
        )
        api = self._api_with_healthy_dependencies(plugin, reviewer)
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The checked result may be useful to retain",
                (changed.fact_id, verified.fact_id),
                "The scoped task passed its local check",
                "Find the implementation and its check when maintaining this area",
            ),
        )
        packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        self.assertTrue(
            plugin.service.sde_review_evidence_state(
                candidate.candidate_id, require_passing=True
            )
        )
        request = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=packet.artifact_inventory.artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="Owner approved the supported task facts",
        )
        start = Barrier(2)

        def confirm() -> AuditReceipt:
            start.wait(timeout=10)
            return api.sde_confirm(self.caller, "project-a", request)

        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(confirm)
            second = workers.submit(confirm)
            receipt = first.result(timeout=15)
            concurrent_retry = second.result(timeout=15)
        replayed = api.sde_confirm(self.caller, "project-a", request)

        self.assertEqual(receipt.decision, ReviewDecision.APPROVED)
        self.assertTrue(receipt.artifact_inventory_complete)
        self.assertEqual(concurrent_retry.receipt_id, receipt.receipt_id)
        self.assertEqual(replayed.receipt_id, receipt.receipt_id)
        with self.assertRaises(ConflictError):
            api.sde_confirm(
                self.caller, "project-a", replace(request, rationale="Changed after approval")
            )
        with self.store.transaction() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM audit_receipts WHERE candidate_id = ?",
                (candidate.candidate_id,),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_one_sde_approval_persists_verifies_then_clears_eligible_artifacts(self) -> None:
        """One SDE decision authorizes cleanup after canonical readback, without a second approval."""

        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Persist the approved SDE before automatic artifact cleanup",
            "Implemented the approved lifecycle change",
            "The end-to-end review check passed",
        )
        staged = plugin.stage_artifact(
            verified.goal_id, "scratch", "approved-sde", BytesIO(b"transient review artifact")
        )
        api = self._api_with_healthy_dependencies(
            plugin,
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
        )
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "Retain the completed lifecycle behavior.",
                (verified.change_fact_id, verified.verification_fact_id),
                "The reviewed lifecycle now completes and cleans up automatically.",
                "Use this entry when maintaining the SDE approval path.",
            ),
        )
        inventory = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        reviewed_artifacts = tuple(
            replace(item, reacquisition_action=ReacquisitionAction.NOT_REQUIRED)
            for item in inventory.artifact_inventory.artifacts
        )
        packet = api.sde_review_packet(
            self.caller,
            "project-a",
            candidate.candidate_id,
            reviewed_artifacts,
        )
        draft = SDEReviewDraft(
            title="Persist the approved lifecycle change",
            significance=4,
            documents=("persistence/HISTORY.md",),
            problem="The completed lifecycle behavior needs a durable record.",
            completed=("Implemented and verified the approved lifecycle change.",),
            difficulties=(),
            plan_changes=(),
            lessons=(),
            future_utility="Use when maintaining SDE approval and artifact cleanup.",
        )
        request = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=reviewed_artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="Owner approved the pending SDE summary.",
            review_draft=draft,
        )
        binding = api.prepare_sde_review_binding(self.caller, "project-a", request)
        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            replace(request, expected_review_binding_sha256=binding.sha256()),
        )

        self.assertTrue(Path(staged.path).exists())
        self.assertTrue(receipt.cleanup_authorized)
        self.assertFalse(receipt.canonical_persisted)
        self.assertEqual(receipt.purge_status.value, "purge_pending")
        for prepare_only in (True, False):
            api.sde_project_review_target(
                self.caller,
                "project-a",
                receipt.receipt_id,
                "persistence/HISTORY.md",
                prepare_only=prepare_only,
            )
        projection = api.sde_review_projection_status(
            self.caller, "project-a", receipt.receipt_id
        )
        self.assertEqual(len(projection), 1)
        self.assertIsNotNone(projection[0][1])
        self.assertIsNotNone(projection[0][2])
        history = self.root / "persistence" / "HISTORY.md"
        history_text = history.read_text(encoding="utf-8")
        self.assertIn(draft.completed[0].replace(".", r"\."), history_text)
        self.assertIn(receipt.receipt_id, history_text)
        artifact_manifest = packet.artifact_inventory.manifest_sha256
        assert artifact_manifest is not None
        self.assertIn(artifact_manifest, history_text)
        self.assertIn(packet.dependency_map_sha256, history_text)
        self.assertNotIn(b"transient review artifact", history.read_bytes())

        reflected_entry = history.read_bytes()
        altered_entry = history_text.replace(
            artifact_manifest, "f" * 64, 1
        ).encode("utf-8")
        history.write_bytes(altered_entry)
        with self.assertRaises(ConflictError):
            api.sde_finalize_review_projection(
                self.caller, "project-a", receipt.receipt_id
            )
        self.assertTrue(Path(staged.path).exists())
        self.assertEqual(
            api.artifact_purge_status(self.caller, "project-a", receipt.receipt_id)[0]
            .purge_status.value,
            "purge_pending",
        )
        history.write_bytes(reflected_entry)

        finalized = api.sde_finalize_review_projection(
            self.caller, "project-a", receipt.receipt_id
        )

        self.assertTrue(finalized.canonical_persisted)
        self.assertEqual(finalized.purge_status.value, "complete")
        self.assertFalse(Path(staged.path).exists())
        cleanup_authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "project-a"
        )
        self.assertIsNotNone(cleanup_authorization)
        assert cleanup_authorization is not None
        self.assertTrue(cleanup_authorization.canonical_persisted)
        purge_receipt, targets = api.artifact_purge_status(
            self.caller, "project-a", receipt.receipt_id
        )
        self.assertEqual(purge_receipt.purge_status.value, "complete")
        self.assertEqual([target.status.value for target in targets], ["purged"])

    def test_exact_stale_sde_batch_can_be_withdrawn_without_losing_facts(self) -> None:
        """Clear stale alpha proposals atomically and retain owner audit receipts."""

        goal = self.plugin.service.goal_start(
            "Prepare stale SDE withdrawal coverage",
            (SuccessCriterion("withdrawal", "A stale review proposal is clearable"),),
        )
        fact, _ = self.plugin.service.goal_fact(
            goal.goal_id,
            FactKind.RESEARCH,
            "A source fact remains available after withdrawal",
        )
        candidates = tuple(
            SDECandidate(
                goal_id=goal.goal_id,
                materiality=materiality,
                rationale=f"Proposal to withdraw for {materiality.value} review retest",
                fact_ids=(fact.fact_id,),
                impact="A test proposal appears in the pending queue",
                retrieval_value="Use this fixture to retest the review flow",
            )
            for materiality in (Materiality.IMPLEMENTATION, Materiality.ROUTINE)
        )
        for candidate in candidates:
            self.store.add_sde_candidate(candidate, "project-a")
        reviewer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.READ),
                ("hermes-user-1", "project-a", ProjectAction.WRITE),
                ("hermes-user-1", "project-a", ProjectAction.REVIEW),
            }
        )
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(self.store), ReviewHost()
        )
        api = self._api_with_healthy_dependencies(plugin, reviewer)
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        rationale = "Withdraw stale alpha review proposals before a clean retest"

        with self.assertRaisesRegex(NotFoundError, "SDE candidate not found"):
            api.sde_withdraw_candidates(
                self.caller,
                "project-a",
                (candidate_ids[0], "missing-candidate"),
                rationale,
            )
        self.assertEqual(
            self.store.get_sde_candidate(candidate_ids[0], "project-a").status.value,
            "pending_review",
        )

        withdrawals = api.sde_withdraw_candidates(
            self.caller, "project-a", candidate_ids, rationale
        )
        retry = api.sde_withdraw_candidates(
            self.caller, "project-a", candidate_ids, rationale
        )

        self.assertEqual(len(withdrawals), 2)
        self.assertEqual(
            tuple(item.withdrawal_id for item in retry),
            tuple(item.withdrawal_id for item in withdrawals),
        )
        self.assertTrue(all(len(item.candidate_sha256) == 64 for item in withdrawals))
        self.assertEqual(
            tuple(item.candidate.status.value for item in api.sde_review_queue(
                self.caller, "project-a"
            )),
            (),
        )
        self.assertEqual(
            self.store.get_fact(fact.fact_id, "project-a").bullet,
            "A source fact remains available after withdrawal",
        )
        activity = api.project_activity_status(self.caller, "project-a")
        self.assertEqual(activity.pending_sde_count, 0)
        self.assertEqual(activity.withdrawn_sde_count, 2)
        self.assertEqual(activity.sde_candidate_count, 2)

    def test_edited_sde_fields_are_bound_to_the_durable_review_receipt(self) -> None:
        """Persist the exact editable entry and its authenticated review binding."""

        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Keep an edited SDE review bound to its evidence",
            "Implemented the reviewed change",
            "The reviewed change passed its focused verification",
        )
        api = self._api_with_healthy_dependencies(
            plugin,
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
        )
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "The task result is useful to retain",
                (verified.change_fact_id, verified.verification_fact_id),
                "The reviewed change completed the task successfully",
                "The entry can guide future maintenance",
            ),
        )
        assert candidate is not None
        packet = api.sde_review_packet(self.caller, "project-a", candidate.candidate_id)
        draft = SDEReviewDraft(
            title="Keep the reviewed task result",
            significance=4,
            documents=("persistence/HISTORY.md",),
            problem="The task outcome needs a durable, reviewable record.",
            completed=("Implemented the scoped change.",),
            difficulties=("The first attempt lacked current evidence.",),
            plan_changes=("Added a focused verification step.",),
            lessons=("Bind the retained result to current proof.",),
            future_utility="Use this when reviewing related changes.",
        )
        request = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=packet.artifact_inventory.artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="The edited entry matches the completed task and its proof.",
            review_draft=draft,
        )
        binding = api.prepare_sde_review_binding(self.caller, "project-a", request)

        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            replace(request, expected_review_binding_sha256=binding.sha256()),
        )
        saved = self.store.get_receipt(receipt.receipt_id, "project-a")

        self.assertEqual(SDEReviewDraft.from_json(saved.review_draft_json or ""), draft)
        self.assertEqual(saved.review_binding_sha256, binding.sha256())
        self.assertEqual(
            SDEReviewBinding.from_json(saved.review_binding_json or ""), binding
        )
        self.assertEqual(
            self.store.sde_review_targets(saved.receipt_id, "project-a"),
            (("persistence/HISTORY.md", None, None),),
        )

    def test_projection_and_cleanup_receipt_failures_keep_artifact_until_retry(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Keep reviewed data until its decision is persisted",
            "Implemented the bounded change",
            "The bounded verification passed",
        )
        staged = plugin.stage_artifact(
            verified.goal_id,
            "scratch",
            "projection-failure",
            BytesIO(b"reviewed transient data"),
        )
        review_authorizer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.READ),
                ("hermes-user-1", "project-a", ProjectAction.WRITE),
                ("hermes-user-1", "project-a", ProjectAction.REVIEW),
            }
        )
        api = self._api_with_healthy_dependencies(plugin, review_authorizer)
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "Retain the verified bounded change",
                (verified.change_fact_id, verified.verification_fact_id),
                "Observed in the local regression scenario",
                "Useful for future maintenance review",
            ),
        )
        assert candidate is not None
        packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        selected_artifacts = tuple(
            replace(item, reacquisition_action=ReacquisitionAction.NOT_REQUIRED)
            for item in packet.artifact_inventory.artifacts
        )
        packet = api.sde_review_packet(
            self.caller,
            "project-a",
            candidate.candidate_id,
            selected_artifacts,
        )
        confirmation = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=selected_artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="Approve only after the canonical projection is durable",
        )
        saved_receipts: list[AuditReceipt] = []
        create_receipt = self.store.create_receipt
        authorize_cleanup = plugin.service.authorize_artifact_cleanup

        def capture_saved_receipt(
            receipt: AuditReceipt, project_id: str | None = None
        ) -> AuditReceipt:
            saved = create_receipt(receipt, project_id)
            saved_receipts.append(saved)
            return saved

        def authorize_then_interrupt(
            receipt_id: str,
            manifest_sha256: str,
            dependency_map_sha256: str,
            *,
            authenticated_subject: str | None = None,
        ) -> None:
            authorize_cleanup(
                receipt_id,
                manifest_sha256,
                dependency_map_sha256,
                authenticated_subject=authenticated_subject,
            )
            raise OSError("interrupted after cleanup authorization write")

        with patch.object(self.store, "create_receipt", side_effect=capture_saved_receipt):
            with patch.object(
                plugin.service,
                "authorize_artifact_cleanup",
                side_effect=authorize_then_interrupt,
            ):
                with self.assertRaisesRegex(
                    OSError, "interrupted after cleanup authorization write"
                ):
                    api.sde_confirm(self.caller, "project-a", confirmation)

        self.assertEqual(len(saved_receipts), 1)
        first_receipt = saved_receipts[0]
        self.assertIsNone(
            self.store.cleanup_authorization(first_receipt.receipt_id, "project-a")
        )
        with self.assertRaises(NotFoundError):
            self.store.get_purge_target_records(
                first_receipt.receipt_id, project_id="project-a"
            )
        self.assertTrue(Path(staged.path).exists())

        database_path = self.store.database
        self.store.close()
        self.store = CuratorStore(database_path)
        self.addCleanup(self.store.close)
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root),
            self.store,
            TestVerifier(),
            ReviewHost(),
        )
        api = self._api_with_healthy_dependencies(plugin, review_authorizer)
        committed_receipts: list[AuditReceipt] = []
        confirm_review = plugin.sde_confirm

        def commit_then_interrupt(
            request: SDEConfirmationRequest,
            *,
            authenticated_subject: str | None = None,
        ) -> AuditReceipt:
            saved = confirm_review(
                request, authenticated_subject=authenticated_subject
            )
            committed_receipts.append(saved)
            raise OSError("interrupted after review transaction commit")

        with patch.object(plugin, "sde_confirm", side_effect=commit_then_interrupt):
            with self.assertRaisesRegex(
                OSError, "interrupted after review transaction commit"
            ):
                api.sde_confirm(self.caller, "project-a", confirmation)

        self.assertEqual(len(committed_receipts), 1)
        committed_receipt = committed_receipts[0]
        self.assertIsNotNone(
            self.store.cleanup_authorization(
                committed_receipt.receipt_id, "project-a"
            )
        )
        self.assertTrue(Path(staged.path).exists())
        target_record = self.store.get_purge_target_records(
            committed_receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(target_record.attempts, 0)

        database_path = self.store.database
        self.store.close()
        self.store = CuratorStore(database_path)
        self.addCleanup(self.store.close)
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root),
            self.store,
            TestVerifier(),
            ReviewHost(),
        )
        api = self._api_with_healthy_dependencies(plugin, review_authorizer)
        receipt = api.sde_confirm(self.caller, "project-a", confirmation)
        self.assertEqual(receipt.receipt_id, committed_receipt.receipt_id)
        self.assertEqual(len(saved_receipts), 1)
        self.assertIsNotNone(
            self.store.cleanup_authorization(receipt.receipt_id, "project-a")
        )
        self.assertTrue(Path(staged.path).exists())
        target_record = self.store.get_purge_target_records(
            receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(target_record.attempts, 0)
        target = self.root / "persistence" / "HISTORY.md"
        authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "project-a"
        )
        assert authorization is not None
        self.assertFalse(authorization.canonical_persisted)
        self.assertTrue(Path(staged.path).exists())

        with patch(
            "curatormd_v2.project_plugin_views.MarkdownPersistenceAdapter.persist_goal",
            side_effect=OSError("projection write failed"),
        ):
            with self.assertRaisesRegex(OSError, "projection write failed"):
                api.persist_goal(
                    self.caller, "project-a", verified.goal_id, str(target)
                )

        pending = self.store.get_receipt(receipt.receipt_id, "project-a")
        authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "project-a"
        )
        assert authorization is not None
        self.assertFalse(pending.canonical_persisted)
        self.assertFalse(authorization.canonical_persisted)
        self.assertTrue(Path(staged.path).exists())
        target_record = self.store.get_purge_target_records(
            receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(target_record.attempts, 0)

        with patch.object(
            plugin.service,
            "mark_cleanup_authorization_canonical_persisted",
            side_effect=OSError("cleanup receipt write failed"),
        ):
            with self.assertRaisesRegex(OSError, "cleanup receipt write failed"):
                api.persist_goal(
                    self.caller, "project-a", verified.goal_id, str(target)
                )

        projected_receipt = self.store.get_receipt(receipt.receipt_id, "project-a")
        authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "project-a"
        )
        assert authorization is not None
        self.assertTrue(projected_receipt.canonical_persisted)
        self.assertFalse(authorization.canonical_persisted)
        self.assertIn(receipt.receipt_id, target.read_text(encoding="utf-8"))
        self.assertTrue(Path(staged.path).exists())
        target_record = self.store.get_purge_target_records(
            receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(target_record.attempts, 0)

        persist_projection = api.persist_goal

        def persist_then_interrupt(
            caller: AuthenticatedCaller,
            project_id: str,
            goal_id: str,
            projection_target: str,
        ) -> NoReturn:
            persist_projection(caller, project_id, goal_id, projection_target)
            raise OSError("interrupted after final purge status commit")

        with patch.object(api, "persist_goal", side_effect=persist_then_interrupt):
            with self.assertRaisesRegex(
                OSError, "interrupted after final purge status commit"
            ):
                api.persist_goal(
                    self.caller, "project-a", verified.goal_id, str(target)
                )

        completed = self.store.get_receipt(receipt.receipt_id, "project-a")
        authorization = self.store.cleanup_authorization(
            receipt.receipt_id, "project-a"
        )
        assert authorization is not None
        self.assertTrue(completed.canonical_persisted)
        self.assertTrue(authorization.canonical_persisted)
        self.assertFalse(Path(staged.path).exists())
        target_record = self.store.get_purge_target_records(
            receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(target_record.attempts, 1)

        database_path = self.store.database
        self.store.close()
        self.store = CuratorStore(database_path)
        self.addCleanup(self.store.close)
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root),
            self.store,
            TestVerifier(),
            ReviewHost(),
        )
        api = self._api_with_healthy_dependencies(plugin, review_authorizer)
        api.persist_goal(self.caller, "project-a", verified.goal_id, str(target))
        completed_after_retry = self.store.get_receipt(
            receipt.receipt_id, "project-a"
        )
        self.assertTrue(completed_after_retry.canonical_persisted)
        self.assertFalse(Path(staged.path).exists())
        recovered_target = self.store.get_purge_target_records(
            receipt.receipt_id, project_id="project-a"
        )[0]
        self.assertEqual(recovered_target.attempts, 1)

    def test_sde_assessment_rejects_advice_and_proposal_facts(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier()
        )
        verified = self._create_verified_goal(
            plugin,
            "Assess supported knowledge only",
            "Implemented the reviewed behavior",
            "The required verification passed",
            complete=False,
        )
        proposal, _ = plugin.service.goal_fact(
            verified.goal_id, FactKind.PROPOSAL, "Maybe change the behavior later"
        )
        advice, _ = plugin.service.goal_fact(
            verified.goal_id, FactKind.ADVICE, "Consider a different design"
        )
        plugin.service.goal_finish(
            verified.goal_id, "The required verification passed"
        )
        api = AuthenticatedCuratorAPI({"project-a": plugin}, self.authorizer)

        for unsupported_fact in (proposal, advice):
            with self.subTest(kind=unsupported_fact.kind.value):
                with self.assertRaisesRegex(EvidenceGateError, "only research, change"):
                    api.sde_assess(
                        self.caller,
                        "project-a",
                        SDEAssessmentRequest(
                            verified.goal_id,
                            Materiality.IMPLEMENTATION,
                            "Do not retain an advice or proposal as a fact",
                            (
                                verified.change_fact_id,
                                verified.verification_fact_id,
                                unsupported_fact.fact_id,
                            ),
                            "Observed in the bounded test scenario",
                            "Useful for future maintenance review",
                        ),
                    )

        self.assertEqual(plugin.service.sde_review_queue(), ())

    def test_existing_candidate_with_proposal_cannot_be_approved(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Recheck queued retained knowledge",
            "Implemented the reviewed behavior",
            "The required verification passed",
            complete=False,
        )
        proposal, _ = plugin.service.goal_fact(
            verified.goal_id, FactKind.PROPOSAL, "Change the behavior later"
        )
        plugin.service.goal_finish(
            verified.goal_id, "The required verification passed"
        )
        candidate = SDECandidate(
            goal_id=verified.goal_id,
            materiality=Materiality.IMPLEMENTATION,
            rationale="Legacy candidate with a proposal fact",
            fact_ids=(
                verified.change_fact_id,
                verified.verification_fact_id,
                proposal.fact_id,
            ),
            impact="The change affects behavior",
            retrieval_value="The change may matter for future maintenance",
        )
        self.store.add_sde_candidate(candidate, "project-a")
        api = self._api_with_healthy_dependencies(
            plugin,
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
        )
        packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        approval = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=packet.artifact_inventory.artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="Only facts can be approved for retention",
        )

        with self.assertRaisesRegex(EvidenceGateError, "cannot retain advice, proposals"):
            api.sde_confirm(self.caller, "project-a", approval)
        self.assertIsNone(
            self.store.receipt_for_candidate(candidate.candidate_id, "project-a")
        )
        rejected = api.sde_confirm(
            self.caller,
            "project-a",
            SDEConfirmationRequest(
                candidate_id=candidate.candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=approval.artifacts,
                artifact_inventory_complete=approval.artifact_inventory_complete,
                dependency_map_sha256=approval.dependency_map_sha256,
                rationale="Reject a queued candidate containing a proposal",
            ),
        )
        self.assertEqual(rejected.decision, ReviewDecision.REJECTED)

    def test_approval_rechecks_current_evidence_but_stale_candidate_can_be_rejected(
        self,
    ) -> None:
        class RevocableVerifier:  # pylint: disable=too-few-public-methods
            """Test evidence that can become unavailable after assessment."""

            def __init__(self) -> None:
                self.current = True
                self.delegate = TestVerifier()

            def attest(
                self,
                evidence: EvidenceRef,
                context: EvidenceVerificationContext,
            ) -> EvidenceAttestation | None:
                if not self.current:
                    return None
                return self.delegate.attest(evidence, context)

        verifier = RevocableVerifier()
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, verifier, ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Review evidence that can expire",
            "Implemented the scoped change",
            "The scoped verification passed",
        )
        api = self._api_with_healthy_dependencies(
            plugin,
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
        )
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "A verified change should be reviewable",
                (verified.verification_fact_id,),
                "Observed in the bounded test scenario",
                "Useful for future maintenance review",
            ),
        )
        assert candidate is not None
        packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        request = SDEConfirmationRequest(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.APPROVED,
            artifacts=packet.artifact_inventory.artifacts,
            artifact_inventory_complete=packet.artifact_inventory.usage.inventory_complete,
            dependency_map_sha256=packet.dependency_map_sha256,
            rationale="Review the current evidence state",
        )

        completed_goal = plugin.service.goal_status(verified.goal_id).goal
        plugin.service.goal_reopen(
            verified.goal_id,
            "Continue development after historical review was prepared",
            "Rerun the scoped verification before completing the task",
            expected_lifecycle_revision=completed_goal.lifecycle_revision,
        )
        verifier.current = False
        approved = api.sde_confirm(self.caller, "project-a", request)
        self.assertEqual(approved.decision, ReviewDecision.APPROVED)

    def test_sde_assessment_requires_write_scope_and_verified_goal_facts(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier()
        )
        verified = self._create_verified_goal(
            plugin,
            "Assess a verified implementation",
            "Implemented the scoped change",
            "The scoped verification passed",
        )
        read_only = AllowProject(
            {("hermes-user-1", "project-a", ProjectAction.READ)}
        )
        read_api = AuthenticatedCuratorAPI({"project-a": plugin}, read_only)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            read_api.sde_assess(
                self.caller,
                "project-a",
                SDEAssessmentRequest(
                    verified.goal_id,
                    Materiality.IMPLEMENTATION,
                    "A verified change should be reviewable",
                    (verified.change_fact_id, verified.verification_fact_id),
                    "Observed in the bounded test scenario",
                    "Useful for future maintenance review",
                ),
            )

        api = AuthenticatedCuratorAPI({"project-a": plugin}, self.authorizer)
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "A verified change should be reviewable",
                (verified.change_fact_id, verified.verification_fact_id),
                "Observed in the bounded test scenario",
                "Useful for future maintenance review",
            ),
        )
        assert candidate is not None
        self.assertEqual(candidate.status.value, "pending_review")
        self.assertEqual(
            candidate.fact_ids,
            (verified.change_fact_id, verified.verification_fact_id),
        )
        activity = api.project_activity_status(self.caller, "project-a")
        self.assertEqual(activity.sde_candidate_count, 1)
        self.assertEqual(activity.pending_sde_count, 1)
        self.assertEqual(activity.approved_sde_count, 0)
        self.assertEqual(activity.rejected_sde_count, 0)
        self.assertEqual(
            tuple(item.candidate.candidate_id for item in api.sde_review_queue(
                self.caller, "project-a"
            )),
            (candidate.candidate_id,),
        )
        review_health = api.project_health(self.caller, "project-a")
        assert review_health.operational_counts is not None
        self.assertEqual(review_health.operational_counts.pending_review_count, 1)
        fully_probed_api = self._api_with_healthy_dependencies(plugin)
        review_health = fully_probed_api.project_health(self.caller, "project-a")
        self.assertEqual(review_health.status.value, "healthy")
        self.assertNotIn("review_backlog", review_health.gate_codes)
        with self.assertRaisesRegex(EvidenceGateError, "fact IDs must be unique"):
            api.sde_assess(
                self.caller,
                "project-a",
                SDEAssessmentRequest(
                    verified.goal_id,
                    Materiality.IMPLEMENTATION,
                    "Repeated support is invalid",
                    (verified.verification_fact_id, verified.verification_fact_id),
                    "Observed in the bounded test scenario",
                    "Useful for future maintenance review",
                ),
            )
        with self.assertRaisesRegex(EvidenceGateError, "supporting fact limit"):
            api.sde_assess(
                self.caller,
                "project-a",
                SDEAssessmentRequest(
                    verified.goal_id,
                    Materiality.IMPLEMENTATION,
                    "Oversized support is invalid",
                    (verified.verification_fact_id,) * 33,
                    "Observed in the bounded test scenario",
                    "Useful for future maintenance review",
                ),
            )

        routine_candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.ROUTINE,
                "Owner review: decide whether this verified task lesson is worth keeping",
                (verified.verification_fact_id,),
                "Observed in the bounded test scenario",
                "Useful for future maintenance review",
            ),
        )
        self.assertIsNotNone(routine_candidate)
        assert routine_candidate is not None
        self.assertEqual(routine_candidate.materiality, Materiality.ROUTINE)
        self.assertEqual(routine_candidate.status.value, "pending_review")

    def test_project_health_reports_held_purge_receipt_and_artifact_as_required_work(
        self,
    ) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        verified = self._create_verified_goal(
            plugin,
            "Keep an approved held artifact visible to operations",
            "Implemented the scoped change",
            "The scoped verification passed",
        )
        api = self._api_with_healthy_dependencies(
            plugin,
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
        )
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "A verified change should be reviewable",
                (verified.change_fact_id, verified.verification_fact_id),
                "Observed in the bounded test scenario",
                "Useful for future maintenance review",
            ),
        )
        assert candidate is not None
        staged = plugin.stage_artifact(
            verified.goal_id, "scratch", "held-health-artifact", BytesIO(b"held")
        )
        held = ArtifactRef(
            staged.path, staged.sha256, RetentionHoldKind.LEGAL,
            staged.device_id, staged.inode_id, staged.occurrence_id,
            ReacquisitionAction.RETAIN_UNDER_HOLD,
        )

        hold_review_packet = api.sde_review_packet(
            self.caller,
            "project-a",
            candidate.candidate_id,
            (held,),
        )
        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            SDEConfirmationRequest(
                candidate_id=candidate.candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(held,),
                artifact_inventory_complete=True,
                dependency_map_sha256=hold_review_packet.dependency_map_sha256,
                rationale="Keep the legal hold visible to operations",
            ),
        )

        self.assertEqual(receipt.purge_status.value, "purge_pending")
        health = api.project_health(self.caller, "project-a")
        self.assertEqual(health.status.value, "degraded")
        assert health.operational_counts is not None
        self.assertEqual(health.operational_counts.pending_purge_receipt_count, 1)
        self.assertEqual(health.operational_counts.pending_purge_artifact_count, 1)
        self.assertIn("purge_pending", health.gate_codes)
        self.assertIn("purge_artifacts_pending", health.gate_codes)
        self.assertIn("staged_artifacts_present", health.gate_codes)


    def test_project_health_reports_pending_expiry_receipt_and_targets(self) -> None:
        """A failed attended expiry purge must keep local health degraded."""

        artifact = ArtifactRef("expiry-goal/scratch/transient", "a" * 64)
        manifest = json.dumps(
            [(artifact.path, artifact.sha256, artifact.occurrence_id)],
            separators=(",", ":")
        )
        manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
        self.store.create_expiry_purge_receipt(
            "project-a",
            "hermes-user-1",
            manifest_sha256,
            (artifact,),
        )
        api = self._api_with_healthy_dependencies(self.plugin)

        health = api.project_health(self.caller, "project-a")
        metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        assert health.operational_counts is not None
        self.assertEqual(
            health.operational_counts.pending_expiry_purge_receipt_count, 1
        )
        self.assertEqual(
            health.operational_counts.pending_expiry_purge_artifact_count, 1
        )
        self.assertIn("expiry_purge_pending", health.gate_codes)
        self.assertIn("expiry_purge_artifacts_pending", health.gate_codes)
        self.assertIn('curatormd_expiry_purge_receipts_pending{project_id="project-a"} 1', metrics)
        self.assertIn('curatormd_expiry_purge_artifacts_pending{project_id="project-a"} 1', metrics)
