"""Assess, review, and disposition significant decisions."""

from __future__ import annotations

__all__ = (
    "_ReviewMixin",
)

from collections.abc import Callable
from contextlib import (
    AbstractContextManager,
    nullcontext,
)
from .models import (
    AuditReceipt,
    MAX_SDE_SUPPORTING_FACTS,
    Materiality,
    SDEConfirmationRequest,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
)

from .service_types import (
    EvidenceGateError,
    SDEAssessmentRequest,
)
from .service_goal_read import _GoalReadMixin


class _ReviewMixin(_GoalReadMixin):
    """Assess, review, and disposition significant decisions."""

    def sde_assess(
        self,
        request: SDEAssessmentRequest,
    ) -> SDECandidate | None:
        """Return routine work directly or stage verified significant facts for review."""

        expected_effect_revision = self._capture_effect_revision()
        return self._sde_assess(
            request, lambda: self._effect_fence(expected_effect_revision)
        )

    def sde_assess_with_effect_fence(
        self,
        request: SDEAssessmentRequest,
        effect_fence: Callable[[], AbstractContextManager[object]],
    ) -> SDECandidate | None:
        """Verify evidence before fencing the durable proposal write."""

        expected_effect_revision = self._capture_effect_revision()
        return self._sde_assess(
            request,
            lambda: self._effect_guard(expected_effect_revision, effect_fence),
        )

    def _sde_assess(
        self,
        request: SDEAssessmentRequest,
        effect_fence: Callable[[], AbstractContextManager[object]] | None,
    ) -> SDECandidate | None:
        """Validate current supporting evidence, then store one candidate."""

        if request.materiality is Materiality.ROUTINE:
            return None
        if request.impact is None or request.retrieval_value is None:
            raise EvidenceGateError(
                "SDE assessment requires impact and retrieval value"
            )
        if not request.fact_ids:
            raise EvidenceGateError("SDE assessment requires selected goal facts")
        if len(request.fact_ids) > MAX_SDE_SUPPORTING_FACTS:
            raise EvidenceGateError(
                "SDE assessment exceeds the supporting fact limit"
            )
        if len(request.fact_ids) != len(set(request.fact_ids)):
            raise EvidenceGateError("SDE assessment fact IDs must be unique")
        goal = self.store.get_goal(request.goal_id, self.project_id)
        selected = tuple(
            self.store.get_fact(fact_id, self.project_id)
            for fact_id in request.fact_ids
        )
        if any(fact.goal_id != request.goal_id for fact in selected):
            raise EvidenceGateError("SDE facts must belong to the assessed goal")
        has_direct_passing_evidence = any(
            self._fact_is_currently_verified(goal, fact)
            for fact in selected
        )
        if not has_direct_passing_evidence:
            raise EvidenceGateError(
                "candidate requires a selected verification fact with passing evidence"
            )
        candidate = SDECandidate(
            goal_id=request.goal_id,
            materiality=request.materiality,
            rationale=request.rationale,
            fact_ids=request.fact_ids,
            impact=request.impact,
            retrieval_value=request.retrieval_value,
        )
        guard = effect_fence if effect_fence is not None else nullcontext
        with guard():
            stored_candidate, _inserted = self.store.add_sde_candidate(
                candidate, self.project_id
            )
        return stored_candidate

    def sde_review_queue(self, limit: int = 100) -> tuple[SDEReviewDetail, ...]:
        """Return pending review packets without exposing other projects."""

        candidates = self.store.pending_sde_candidates(self.project_id, limit)
        return tuple(self.sde_review_detail(item.candidate_id) for item in candidates)

    def sde_review_detail(self, candidate_id: str) -> SDEReviewDetail:
        """Read a candidate, its selected facts, goal context, and decision receipt."""

        candidate = self.store.get_sde_candidate(candidate_id, self.project_id)
        goal = self.store.get_goal(candidate.goal_id, self.project_id)
        facts = tuple(
            self.store.get_fact(fact_id, self.project_id) for fact_id in candidate.fact_ids
        )
        receipt = self.store.receipt_for_candidate(candidate_id, self.project_id)
        corrections = self.store.list_sde_corrections(candidate_id, self.project_id)
        return SDEReviewDetail(candidate, goal, facts, receipt, corrections)

    def sde_correction_record(
        self,
        correction_id: str,
        candidate_id: str,
        correction: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> SDECorrection:
        """Append an attributable correction without mutating candidate/receipt."""

        expected_effect_revision = self._capture_effect_revision()
        reviewer_id = self.review_authorizer.authorize_correction(
            self.project_id, candidate_id, authenticated_subject
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        record = SDECorrection(
            correction_id=correction_id,
            candidate_id=candidate_id,
            correction=correction,
            rationale=rationale,
            reviewer_id=reviewer_id,
        )
        with self._effect_fence(expected_effect_revision):
            stored, _inserted = self.store.add_sde_correction(
                record, self.project_id
            )
        return stored

    def sde_quality_feedback_record(
        self,
        feedback_id: str,
        candidate_id: str,
        label: SDEQualityFeedbackLabel,
        rationale: str = "",
        *,
        authenticated_subject: str | None = None,
    ) -> SDEQualityFeedback:
        """Append one trusted reviewer's explicit post-decision quality label."""

        expected_effect_revision = self._capture_effect_revision()
        reviewer_id = self.review_authorizer.authorize_feedback(
            self.project_id, candidate_id, authenticated_subject
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        feedback = SDEQualityFeedback(
            feedback_id=feedback_id,
            candidate_id=candidate_id,
            reviewer_id=reviewer_id,
            label=label,
            rationale=rationale,
        )
        with self._effect_fence(expected_effect_revision):
            stored, _inserted = self.store.add_sde_quality_feedback(
                feedback, self.project_id
            )
        return stored

    def sde_quality_feedback_summary(self) -> SDEQualityFeedbackSummary:
        """Return project-scoped aggregate reviewer label counts."""

        return self.store.sde_quality_feedback_summary(self.project_id)

    def sde_confirm(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record the SDE disposition before the plugin binds this action to cleanup."""

        expected_effect_revision = self._capture_effect_revision()
        reviewer_id = self.review_authorizer.authorize(
            self.project_id,
            request.candidate_id,
            request.decision,
            authenticated_subject,
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        candidate = self.store.get_sde_candidate(request.candidate_id, self.project_id)
        receipt = AuditReceipt(
            candidate_id=request.candidate_id,
            decision=request.decision,
            facts_sha256=self.store.facts_digest(candidate.fact_ids, self.project_id),
            artifacts=request.artifacts,
            artifact_inventory_complete=request.artifact_inventory_complete,
            reviewer_id=reviewer_id,
            review_rationale=request.rationale,
        )
        # This commit is the deletion gate: no artifact is touched before it.
        with self._effect_fence(expected_effect_revision):
            durable_receipt = self.store.create_receipt(receipt, self.project_id)
        return durable_receipt
