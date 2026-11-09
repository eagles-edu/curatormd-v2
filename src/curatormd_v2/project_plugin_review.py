"""Human review and artifact disposition adapters for a Curator project."""

from __future__ import annotations

from dataclasses import replace
import hmac
import re
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
    ReviewDecision,
    SDEWithdrawal,
)
from .sde_review_draft import SDEReviewBinding, SDEReviewDraft
from .markdown_persistence import MarkdownPersistenceAdapter
from .read_models import (
    artifact_dependency_map_sha256,
    build_artifact_review_dependencies,
)
from .service import (
    PurgeTargetStatus,
    SDEAssessmentRequest,
)
from .store import (
    EventReceiptArchiveReceipt,
    EventReceiptArchiveRequest,
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

    def event_receipt_archive(
        self, request: EventReceiptArchiveRequest
    ) -> EventReceiptArchiveReceipt:
        """Archive only the exact event inventory page approved for this project."""

        with self._active_project_revision_fence():
            return self.service.store.archive_event_receipt_page(
                replace(request, project_id=self.config.project_id)
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

    def sde_review_documents(self) -> tuple[str, ...]:
        """Return configured project-relative Markdown destinations for draft editing."""

        return tuple(
            target.relative_to(self.config.project_root).as_posix()
            for target in self.config.persistence_targets
        )

    def sde_assess(
        self,
        request: SDEAssessmentRequest,
    ) -> SDECandidate:
        """Create a pending owner-review proposal from verified project facts."""

        expected_revision = self._capture_active_project_revision()

        def effect_fence():
            """Fence candidate insertion after the external evidence check."""

            return self._project_revision_fence(expected_revision)

        return self.service.sde_assess_with_effect_fence(request, effect_fence)

    def sde_review_detail(self, candidate_id: str) -> SDEReviewDetail:
        """Read one candidate and its selected evidence within this project."""

        return self.service.sde_review_detail(candidate_id)

    def sde_withdraw_candidates(
        self,
        candidate_ids: tuple[str, ...],
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> tuple[SDEWithdrawal, ...]:
        """Remove exact stale proposals from the queue and retain audit receipts."""

        if not candidate_ids or len(candidate_ids) > 100:
            raise ValueError("withdrawal requires 1-100 candidate IDs")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("withdrawal candidate IDs must be unique")
        reviewer_ids = tuple(
            self.service.review_authorizer.authorize_withdrawal(
                self.config.project_id,
                candidate_id,
                authenticated_subject,
            )
            for candidate_id in candidate_ids
        )
        if len(set(reviewer_ids)) != 1:
            raise PermissionError("one authenticated reviewer must authorize the batch")
        expected_revision = self._capture_active_project_revision()
        with self._project_revision_fence(expected_revision):
            return self.service.store.withdraw_sde_candidates(
                candidate_ids,
                self.config.project_id,
                reviewer_ids[0],
                rationale,
            )

    def sde_review_has_current_passing_evidence(self, candidate_id: str) -> bool:
        """Recheck selected evidence before presenting a successful-completion time."""

        return self.service.sde_review_has_current_passing_evidence(candidate_id)

    def sde_review_completion_claim(
        self, candidate_id: str
    ) -> dict[str, str] | None:
        """Read current single-check task proof for the owner review outline."""

        return self.service.sde_review_completion_claim(candidate_id)

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

    def prepare_sde_review_binding(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> SDEReviewBinding:
        """Observe the exact edited proposal and packet before human confirmation.

        This is not a decision or cleanup approval. The caller must repeat
        all checks when submitting the attended confirmation.
        """

        draft = request.review_draft
        if draft is None or request.rationale is None:
            raise ValueError("edited SDE review requires a draft and rationale")
        if request.decision is ReviewDecision.APPROVED and not draft.documents:
            raise ValueError("approval requires at least one configured document")
        if not request.artifact_inventory_complete or request.dependency_map_sha256 is None:
            raise ValueError("edited SDE review requires the complete displayed inventory")
        reviewer = self.service.review_authorizer.authorize(
            self.config.project_id, request.candidate_id, request.decision,
            authenticated_subject,
        )
        if authenticated_subject is not None and reviewer != authenticated_subject:
            raise PermissionError("reviewer does not match the authenticated subject")
        expected_revision = self._capture_active_project_revision()
        with self._locked_staging_root() as root_fd:
            candidate = self.sde_review_detail(request.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, request.artifacts, staging_root_fd=root_fd
            )
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, request.dependency_map_sha256
            )
            evidence_state = self.service.sde_review_evidence_state(
                request.candidate_id,
                require_passing=request.decision is ReviewDecision.APPROVED,
            )
            facts_sha256 = self.service.store.facts_digest(
                candidate.fact_ids, self.config.project_id
            )
            projection_state = draft.projection_state_sha256(self.config)
            if self.service.sde_review_evidence_state(
                request.candidate_id,
                require_passing=request.decision is ReviewDecision.APPROVED,
            ) != evidence_state:
                raise ConflictError("SDE evidence changed during review preparation")
            if self._capture_active_project_revision() != expected_revision:
                raise ConflictError("project changed during review preparation")
        return SDEReviewBinding(
            project_id=self.config.project_id,
            candidate_id=request.candidate_id,
            decision=request.decision.value,
            reviewer_id=reviewer,
            review_rationale=request.rationale,
            project_config_sha256=self.config.config_sha256,
            supporting_facts_sha256=facts_sha256,
            evidence_state_sha256=evidence_state,
            projection_state_sha256=projection_state,
            inventory_sha256=artifact_manifest_sha256(artifacts),
            dependency_map_sha256=request.dependency_map_sha256,
            draft_sha256=draft.sha256(),
        )

    def sde_confirm(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record disposition and exact cleanup authorization in one review action."""

        current_binding: SDEReviewBinding | None = None
        if request.review_draft is not None:
            expected_binding = request.expected_review_binding_sha256
            if not isinstance(expected_binding, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_binding):
                raise ValueError("edited SDE decision requires the displayed binding digest")
            if request.review_draft.significance == 5 and request.confirm_significance_five is not True:
                raise PermissionError("significance 5 requires explicit human confirmation")
            current_binding = self.prepare_sde_review_binding(
                request, authenticated_subject=authenticated_subject
            )
            if not hmac.compare_digest(current_binding.sha256(), expected_binding):
                raise ConflictError("SDE review changed after it was displayed")
        elif request.expected_review_binding_sha256 is not None or request.confirm_significance_five:
            raise ValueError("SDE binding options require an edited review draft")
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
            if current_binding is not None:
                draft = request.review_draft
                if draft is None or (
                    artifact_manifest_sha256(artifacts) != current_binding.inventory_sha256
                    or validated_dependency_map_sha256 != current_binding.dependency_map_sha256
                    or draft.projection_state_sha256(self.config) != current_binding.projection_state_sha256
                ):
                    raise ConflictError("SDE review state changed before confirmation")
            validated_request = replace(request, artifacts=artifacts)
            prepared_confirmation = self.service.prepare_sde_confirmation(
                validated_request,
                authenticated_subject=authenticated_subject,
                validated_binding=current_binding,
            )
            with self._project_revision_fence(expected_revision):
                receipt = self.service.commit_sde_confirmation(
                    prepared_confirmation
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

    def sde_review_projection_status(
        self, receipt_id: str, *, authenticated_subject: str | None = None,
    ) -> tuple[tuple[str, str | None, str | None], ...]:
        """Read the approved destination states for the original reviewer."""

        receipt = self.service.store.get_receipt(receipt_id, self.config.project_id)
        if receipt.review_draft_json is None or receipt.review_binding_json is None:
            raise ValueError("edited SDE receipt is required")
        reviewer = self.service.review_authorizer.authorize(
            self.config.project_id, receipt.candidate_id, receipt.decision,
            authenticated_subject,
        )
        if reviewer != receipt.reviewer_id or (
            authenticated_subject is not None and reviewer != authenticated_subject
        ):
            raise PermissionError("SDE projection requires the original reviewer")
        return self.service.store.sde_review_targets(receipt_id, self.config.project_id)

    def sde_project_review_target(
        self, receipt_id: str, target: str, *, prepare_only: bool,
        authenticated_subject: str | None = None,
    ) -> str:
        """Prepare or project one previously reviewed SDE destination.

        The API must reauthorize the project review grant for each call. This
        operation never marks the whole review complete or starts cleanup.
        """

        if type(prepare_only) is not bool:  # pylint: disable=unidiomatic-typecheck
            raise ValueError("projection phase must be explicit")
        receipt = self.service.store.get_receipt(receipt_id, self.config.project_id)
        if receipt.review_binding_json is None or receipt.review_draft_json is None:
            raise ValueError("edited SDE receipt is required")
        binding = SDEReviewBinding.from_json(receipt.review_binding_json)
        if receipt.decision is not ReviewDecision.APPROVED:
            raise ValueError("only approved SDE entries can be projected")
        reviewer = self.service.review_authorizer.authorize(
            self.config.project_id, receipt.candidate_id, receipt.decision,
            authenticated_subject,
        )
        if reviewer != receipt.reviewer_id or (
            authenticated_subject is not None and reviewer != authenticated_subject
        ):
            raise PermissionError("SDE projection requires the original reviewer")
        if self.service.sde_review_evidence_state(
            receipt.candidate_id, require_passing=True
        ) != binding.evidence_state_sha256:
            raise ConflictError("SDE evidence changed after approval")
        expected_revision = self._capture_active_project_revision()
        with self._locked_staging_root() as root_fd:
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, receipt.artifacts, staging_root_fd=root_fd
            )
            if artifact_manifest_sha256(artifacts) != binding.inventory_sha256:
                raise ConflictError("SDE inventory changed after approval")
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, binding.dependency_map_sha256
            )
            adapter = MarkdownPersistenceAdapter(
                self.config, self.service.store, target, self.service.evidence_verifier
            )

            def effect_fence():
                return self._project_revision_fence(expected_revision)

            if prepare_only:
                adapter.prepare_sde_review_projection(
                    receipt_id, binding, effect_fence=effect_fence
                )
                return "prepared"
            return adapter.persist_prepared_sde_review(
                receipt_id, binding, effect_fence=effect_fence
            )

    def sde_finalize_review_projection(
        self, receipt_id: str, *, authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Compare persisted SDE/artifact fingerprints before releasing cleanup.

        Each reviewed destination must match the exact SDE projection containing
        the artifact inventory and dependency-map digests. The current staged
        inventory and dependency map are rechecked against those same digests
        before cleanup can proceed; raw transient artifact content is not copied
        into canonical persistence.
        """

        receipt = self.service.store.get_receipt(receipt_id, self.config.project_id)
        if (
            receipt.decision not in {ReviewDecision.APPROVED, ReviewDecision.REJECTED}
            or receipt.review_draft_json is None
            or receipt.review_binding_json is None
        ):
            raise ValueError("edited SDE receipt is required")
        binding = SDEReviewBinding.from_json(receipt.review_binding_json)
        reviewer = self.service.review_authorizer.authorize(
            self.config.project_id, receipt.candidate_id, receipt.decision,
            authenticated_subject,
        )
        if reviewer != receipt.reviewer_id or (
            authenticated_subject is not None and reviewer != authenticated_subject
        ):
            raise PermissionError("SDE projection requires the original reviewer")
        if self.service.sde_review_evidence_state(
            receipt.candidate_id,
            require_passing=receipt.decision is ReviewDecision.APPROVED,
        ) != binding.evidence_state_sha256:
            raise ConflictError("SDE evidence changed after the decision")
        draft = SDEReviewDraft.from_json(receipt.review_draft_json)
        expected_revision = self._capture_active_project_revision()
        with self._locked_staging_root() as root_fd:
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, receipt.artifacts, staging_root_fd=root_fd
            )
            if artifact_manifest_sha256(artifacts) != binding.inventory_sha256:
                raise ConflictError("SDE inventory changed after approval")
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, binding.dependency_map_sha256
            )
            if receipt.decision is ReviewDecision.REJECTED:
                # A rejection is durable in the SQLite audit ledger and must
                # not be projected as a knowledge entry. Its typed confirmation
                # already bound the exact inventory and dependency map.
                canonical_target = f"sqlite://audit_receipts/{receipt.receipt_id}"
                canonical_digest = binding.sha256()
                with self._project_revision_fence(expected_revision):
                    self.service.mark_canonical_persisted(
                        receipt_id, canonical_target, canonical_digest
                    )
                    return self.service.mark_cleanup_authorization_canonical_persisted(
                        receipt_id, canonical_target, canonical_digest
                    )
            destinations = self.service.store.sde_review_targets(
                receipt_id, self.config.project_id
            )
            if tuple(path for path, _digest, _time in destinations) != tuple(
                sorted(draft.documents)
            ):
                raise ConflictError("SDE destination inventory changed after approval")
            for target in draft.documents:
                adapter = MarkdownPersistenceAdapter(
                    self.config, self.service.store,
                    self.config.validated_persistence_target(target),
                    self.service.evidence_verifier,
                )
                if adapter.inspect_sde_review_projection(receipt_id, binding) != "complete":
                    raise ConflictError("every SDE destination must match its recorded digest")
            if any(digest is None or projected_at is None for _path, digest, projected_at in destinations):
                raise ConflictError("every SDE destination must be fully recorded")
            canonical_target, canonical_sha256, _projected_at = destinations[0]
            if canonical_sha256 is None:
                raise ConflictError("canonical SDE destination digest is missing")
            with self._project_revision_fence(expected_revision):
                self.service.mark_canonical_persisted(
                    receipt_id, canonical_target, canonical_sha256
                )
                return self.service.mark_cleanup_authorization_canonical_persisted(
                    receipt_id, canonical_target, canonical_sha256
                )

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
