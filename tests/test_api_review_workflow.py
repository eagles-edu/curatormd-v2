"""SDE review lifecycle API regression tests."""

from __future__ import annotations

from test_api import (
    AllowProject,
    ArtifactRef,
    AuthenticatedCuratorAPI,
    BytesIO,
    EvidenceGateError,
    Materiality,
    ProjectAction,
    ProjectConfig,
    ProjectPlugin,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewDecision,
    ReviewHost,
    SDEAssessmentRequest,
    SDEConfirmationRequest,
    TestVerifier,
    _ApiTestSupport,
    hashlib,
    json,
)


class ApiReviewWorkflowTests(_ApiTestSupport):
    """Exercise apireviewworkflow behavior."""

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
        self.assertEqual(review_health.status.value, "degraded")
        self.assertIn("review_backlog", review_health.gate_codes)
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

        self.assertIsNone(
            api.sde_assess(
                self.caller,
                "project-a",
                SDEAssessmentRequest(
                    verified.goal_id,
                    Materiality.ROUTINE,
                    "Ordinary progress is not an SDE",
                    (),
                    "Observed in the bounded test scenario",
                    "Useful for future maintenance review",
                ),
            )
        )


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
