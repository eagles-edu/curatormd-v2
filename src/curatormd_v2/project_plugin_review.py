"""Human review and artifact disposition adapters for a Curator project."""

from __future__ import annotations

from dataclasses import replace
from .models import (
    ArtifactCleanupAuthorizationRequest,
    ArtifactRef,
    AuditReceipt,
    CleanupAuthorizationReceipt,
    FactArchiveReceipt,
    FactCompactionProposal,
    SDECandidate,
    SDEConfirmationRequest,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    SDEReviewPacket,
)
from .read_models import (
    artifact_dependency_map_sha256,
    build_artifact_review_dependencies,
)
from .service import (
    PurgeTargetStatus,
    SDEAssessmentRequest,
)
from .store import (
    FactCompactionApprovalRequest,
    ConflictError,
)
from .project_plugin_staging import (
    artifact_manifest_sha256,
)
from .project_plugin_views import ProjectRepositoryMixin


class ProjectReviewMixin(ProjectRepositoryMixin):  # pylint: disable=abstract-method
    """Review decisions, SDE feedback, and cleanup authorization methods."""

    def fact_compaction_propose(
        self, goal_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Preview routine facts eligible for project-scoped archival."""

        return self.service.fact_compaction_propose(goal_id, max_facts)

    def fact_compaction_approve(
        self,
        approval: FactCompactionApprovalRequest,
    ) -> FactArchiveReceipt:
        """Apply a hash-matched archive only after host review authorization."""

        with self._active_project_revision_fence():
            return self.service.fact_compaction_approve(
                replace(approval, project_id=self.config.project_id)
            )

    def fact_archive_receipts(
        self, goal_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read verified archive receipts inside this project's boundary."""

        return self.service.fact_archive_receipts(
            goal_id, offset=offset, limit=limit
        )

    def sde_review_queue(self, limit: int = 100) -> tuple[SDEReviewDetail, ...]:
        """List bounded pending SDE review packets in this project only."""

        return self.service.sde_review_queue(limit)

    def sde_assess(
        self,
        request: SDEAssessmentRequest,
    ) -> SDECandidate | None:
        """Create a review proposal only from verified facts in this project."""

        expected_revision = self._capture_active_project_revision()

        def effect_fence():
            """Fence candidate insertion after the external evidence check."""

            return self._project_revision_fence(expected_revision)

        return self.service.sde_assess_with_effect_fence(request, effect_fence)

    def sde_review_detail(self, candidate_id: str) -> SDEReviewDetail:
        """Read one candidate and its selected evidence within this project."""

        return self.service.sde_review_detail(candidate_id)

    def sde_review_packet(
        self,
        candidate_id: str,
        review_artifacts: tuple[ArtifactRef, ...] | None = None,
    ) -> SDEReviewPacket:
        """Compose selected evidence, full goal links, and current staging inventory."""

        detail = self.sde_review_detail(candidate_id)
        goal_snapshot = self.service.goal_status(detail.candidate.goal_id)
        with self._locked_staging_root() as root_fd:
            inventory = self._scan_staging_tree(
                discover_artifacts=True,
                scope_goal_id=detail.candidate.goal_id,
                staging_root_fd=root_fd,
            )
            approved_artifacts = (
                inventory.artifacts
                if review_artifacts is None
                else self._require_current_artifact_inventory(
                    detail.candidate.goal_id,
                    review_artifacts,
                    staging_root_fd=root_fd,
                )
            )
        dependencies = build_artifact_review_dependencies(
            goal_snapshot.facts, goal_snapshot.criteria, approved_artifacts
        )
        return SDEReviewPacket(
            detail=detail,
            artifact_inventory=inventory,
            review_artifacts=approved_artifacts,
            artifact_dependencies=dependencies,
            dependency_map_sha256=artifact_dependency_map_sha256(dependencies),
        )

    def sde_correction_record(
        self,
        correction_id: str,
        candidate_id: str,
        correction: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> SDECorrection:
        """Append a reviewer-authorized correction to a decided SDE."""

        with self._active_project_revision_fence():
            return self.service.sde_correction_record(
                correction_id,
                candidate_id,
                correction,
                rationale,
                authenticated_subject=authenticated_subject,
            )

    def sde_quality_feedback_record(
        self,
        feedback_id: str,
        candidate_id: str,
        label: SDEQualityFeedbackLabel,
        rationale: str = "",
        *,
        authenticated_subject: str | None = None,
    ) -> SDEQualityFeedback:
        """Record one authenticated feedback label after candidate disposition."""

        with self._active_project_revision_fence():
            return self.service.sde_quality_feedback_record(
                feedback_id,
                candidate_id,
                label,
                rationale,
                authenticated_subject=authenticated_subject,
            )

    def sde_quality_feedback_summary(self) -> SDEQualityFeedbackSummary:
        """Return only aggregate labels for this project's reviewed candidates."""

        return self.service.sde_quality_feedback_summary()

    def sde_confirm(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record disposition and exact cleanup authorization in one review action."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            validated_dependency_map_sha256: str | None = None
            artifacts = request.artifacts
            if request.artifact_inventory_complete:
                candidate = self.sde_review_detail(request.candidate_id).candidate
                artifacts = self._require_current_artifact_inventory(
                    candidate.goal_id, request.artifacts, staging_root_fd=root_fd
                )
                if request.dependency_map_sha256 is None:
                    raise ConflictError(
                        "cleanup review requires the displayed dependency map digest"
                    )
                self._require_current_dependency_map(
                    candidate.goal_id, artifacts, request.dependency_map_sha256
                )
                validated_dependency_map_sha256 = request.dependency_map_sha256
            validated_request = replace(request, artifacts=artifacts)
            with self._project_revision_fence(expected_revision):
                receipt = self.service.sde_confirm(
                    validated_request,
                    authenticated_subject=authenticated_subject,
                )
                if validated_request.artifact_inventory_complete:
                    if validated_dependency_map_sha256 is None:
                        raise ConflictError(
                            "cleanup review did not retain its validated dependency map digest"
                        )
                    self.service.authorize_artifact_cleanup(
                        receipt.receipt_id,
                        artifact_manifest_sha256(artifacts),
                        validated_dependency_map_sha256,
                        authenticated_subject=authenticated_subject,
                    )
                    receipt = self.service.store.get_receipt(
                        receipt.receipt_id, self.config.project_id
                    )
                return receipt

    def artifact_inventory_complete(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        dependency_map_sha256: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Finalize this project's exact artifact manifest before cleanup."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            receipt = self.service.store.get_receipt(
                receipt_id, self.config.project_id
            )
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, artifacts, staging_root_fd=root_fd
            )
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, dependency_map_sha256
            )
            with self._project_revision_fence(expected_revision):
                return self.service.artifact_inventory_complete(
                    receipt_id,
                    artifacts,
                    authenticated_subject=authenticated_subject,
                )

    def authorize_artifact_cleanup(
        self,
        request: ArtifactCleanupAuthorizationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> tuple[CleanupAuthorizationReceipt, AuditReceipt]:
        """Recheck a displayed manifest and record compatibility cleanup approval."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            receipt = self.service.store.get_receipt(
                request.receipt_id, self.config.project_id
            )
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, request.artifacts, staging_root_fd=root_fd
            )
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, request.dependency_map_sha256
            )
            current_manifest = artifact_manifest_sha256(artifacts)
            if current_manifest != request.manifest_sha256:
                raise ConflictError("cleanup manifest changed before approval")
            with self._project_revision_fence(expected_revision):
                authorization, _receipt = self.service.authorize_artifact_cleanup(
                    request.receipt_id,
                    request.manifest_sha256,
                    request.dependency_map_sha256,
                    authenticated_subject=authenticated_subject,
                )
        self.persist_goal(candidate.goal_id, request.target)
        receipt, _targets = self.service.artifact_purge_status(request.receipt_id)
        authorization = self.service.store.cleanup_authorization(
            request.receipt_id, self.config.project_id
        )
        if authorization is None:
            raise RuntimeError("cleanup authorization receipt was not persisted")
        return authorization, receipt

    def artifact_purge_status(
        self, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Read project-scoped receipt and per-artifact purge outcomes."""

        return self.service.artifact_purge_status(receipt_id)

    def release_artifact_hold(
        self,
        receipt_id: str,
        path: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Release one exact hold through the configured human reviewer."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.release_artifact_hold(
                    receipt_id,
                    path,
                    rationale,
                    authenticated_subject=authenticated_subject,
                )
