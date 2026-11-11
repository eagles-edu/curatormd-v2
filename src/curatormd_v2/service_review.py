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
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from .domain_enums import EvidenceOutcome, GoalStatus, Materiality
from .models import (
    AuditReceipt,
    Fact,
    FactKind,
    GoalCard,
    MAX_SDE_SUPPORTING_FACTS,
    ReviewDecision,
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
from .sde_review_draft import SDEReviewBinding
from .store import ConflictError

_SDE_FACT_KINDS = frozenset(
    {FactKind.USER_REPORT, FactKind.RESEARCH, FactKind.CHANGE, FactKind.VERIFICATION}
)


@dataclass(frozen=True, slots=True)
class _PreparedSDEConfirmation:
    """A reviewed decision verified outside the SQLite write transaction."""

    receipt: AuditReceipt
    expected_effect_revision: int | None


class _ReviewMixin(_GoalReadMixin):
    """Assess, review, and disposition significant decisions."""

    def sde_assess(
        self,
        request: SDEAssessmentRequest,
    ) -> SDECandidate:
        """Stage supported assessments, including routine ones, for owner review."""

        expected_effect_revision = self._capture_effect_revision()
        return self._sde_assess(
            request, lambda: self._effect_fence(expected_effect_revision)
        )

    def sde_record_user_report(
        self, goal_id: str, report: str, event_id: str
    ) -> SDECandidate:
        """Create a pending SDE from an authenticated user's concise report."""

        report = report.strip()
        if (
            not report
            or len(report) > 1000
            or "\n" in report
            or "\r" in report
        ):
            raise ValueError(
                "user report must be a compact single line of at most 1000 characters"
            )
        if (
            not event_id.strip()
            or len(event_id) > 128
            or "\n" in event_id
            or "\r" in event_id
        ):
            raise ValueError("user report event_id must be a bounded single line")
        goal = self.store.get_goal(goal_id, self.project_id)
        if goal.status not in {GoalStatus.ACTIVE, GoalStatus.OPEN}:
            raise ValueError("user reports require an active or open goal")
        fact_id = str(
            uuid5(
                NAMESPACE_URL,
                f"curator-user-report:{self.project_id}:{goal_id}:{event_id}",
            )
        )
        fact, _inserted = self.goal_fact(
            goal_id,
            FactKind.USER_REPORT,
            report,
            fact_id=fact_id,
        )
        candidate = SDECandidate(
            goal_id=goal_id,
            materiality=Materiality.DECISION,
            rationale=report,
            fact_ids=(fact.fact_id,),
            impact="Owner-reported decision captured for owner review.",
            retrieval_value="Retrieve the concise user-reported decision from Curator review.",
            candidate_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"curator-user-report-sde:{self.project_id}:{goal_id}:{event_id}",
                )
            ),
        )
        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            stored, _created = self.store.add_sde_candidate(candidate, self.project_id)
        return stored

    def sde_assess_with_effect_fence(
        self,
        request: SDEAssessmentRequest,
        effect_fence: Callable[[], AbstractContextManager[object]],
    ) -> SDECandidate:
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
    ) -> SDECandidate:
        """Store a candidate for human review, including during active work."""

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
        self.store.get_goal(request.goal_id, self.project_id)
        selected = tuple(
            self.store.get_fact(fact_id, self.project_id)
            for fact_id in request.fact_ids
        )
        if any(fact.kind not in _SDE_FACT_KINDS for fact in selected):
            raise EvidenceGateError(
                "SDE candidates may include only research, change, or verification facts"
            )
        if any(fact.goal_id != request.goal_id for fact in selected):
            raise EvidenceGateError("SDE facts must belong to the assessed goal")
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

    def _selected_verifications_were_passing(
        self,
        goal: GoalCard,
        facts: tuple[Fact, ...],
        reopen_cutoff: str | None,
        *,
        require_verification: bool = False,
    ) -> bool:
        """Validate recorded proof at completion without expiring historical work."""

        verification_facts = tuple(
            fact for fact in facts if fact.kind is FactKind.VERIFICATION
        )
        return (bool(verification_facts) or not require_verification) and all(
            (reopen_cutoff is None or fact.created_at > reopen_cutoff)
            and self._fact_passed_at_completion(goal, fact)
            for fact in verification_facts
        )

    def _fact_passed_at_completion(self, goal: GoalCard, fact: Fact) -> bool:
        """Check the saved host attestation and its original completion window."""

        if not goal.completed_at or not fact.criterion_id or not fact.evidence:
            return False
        if len(fact.evidence) != len(fact.verification_attestations):
            return False
        try:
            completed = datetime.fromisoformat(goal.completed_at)
            if completed.tzinfo is None:
                return False
            return all(
                ref.outcome is EvidenceOutcome.PASSED
                and att.evidence_kind == ref.evidence_kind
                and att.evidence_sha256 == ref.sha256
                and att.occurrence_id == ref.occurrence_id
                and att.project_id == self.project_id
                and att.goal_id == goal.goal_id
                and att.criterion_id == fact.criterion_id
                and datetime.fromisoformat(att.verified_at) <= completed
                < datetime.fromisoformat(att.valid_until)
                for ref, att in zip(fact.evidence, fact.verification_attestations, strict=True)
            )
        except (TypeError, ValueError):
            return False

    def _current_single_check_completion_claim(
        self, goal: GoalCard, reopen_cutoff: str | None
    ) -> Fact | None:
        """Return a recorded claim for context, never as verification evidence."""

        if goal.status is not GoalStatus.COMPLETE or len(goal.success_criteria) != 1:
            return None
        criterion_id = goal.success_criteria[0].criterion_id
        for fact in reversed(self.store.list_facts(goal.goal_id, self.project_id)):
            if (
                fact.kind is FactKind.COMPLETION_CLAIM
                and fact.criterion_id == criterion_id
                and (reopen_cutoff is None or fact.created_at > reopen_cutoff)
                and fact.bullet.startswith((
                    "Completion claim: Checks passed:",
                    "Completion claim: Owner confirmed:",
                ))
            ):
                return fact
        return None

    def sde_review_completion_claim(
        self, candidate_id: str
    ) -> dict[str, str] | None:
        """Expose the recorded completion claim as context, separate from proof."""

        candidate = self.store.get_sde_candidate(candidate_id, self.project_id)
        goal = self.store.get_goal(candidate.goal_id, self.project_id)
        reopen_cutoff = self._evidence_epoch_cutoff(
            self.store.list_facts(goal.goal_id, self.project_id)
        )
        fact = self._current_single_check_completion_claim(goal, reopen_cutoff)
        if fact is None or fact.criterion_id is None:
            return None
        return {
            "fact_id": fact.fact_id,
            "criterion_id": fact.criterion_id,
            "bullet": fact.bullet,
        }

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

    def sde_review_evidence_state(
        self, candidate_id: str, *, require_passing: bool
    ) -> str:
        """Check recorded completion evidence and fingerprint the goal epoch.

        The digest is an observation, not an approval or a reservation. The
        caller must repeat the check before committing the human decision.
        """

        candidate = self.store.get_sde_candidate(candidate_id, self.project_id)
        goal = self.store.get_goal(candidate.goal_id, self.project_id)
        before = self.store.facts_digest(candidate.fact_ids, self.project_id)
        facts = tuple(self.store.get_fact(fact_id, self.project_id) for fact_id in candidate.fact_ids)
        cutoff = self._evidence_epoch_cutoff(
            self.store.list_facts(candidate.goal_id, self.project_id)
        )
        current = (
            goal.status is GoalStatus.COMPLETE
            and self._selected_verifications_were_passing(
                goal, facts, cutoff, require_verification=True
            )
        )
        after_goal = self.store.get_goal(candidate.goal_id, self.project_id)
        after_candidate = self.store.get_sde_candidate(candidate_id, self.project_id)
        after = self.store.facts_digest(candidate.fact_ids, self.project_id)
        if (
            before != after
            or after_candidate != candidate
            or after_goal != goal
            or self._evidence_epoch_cutoff(
                self.store.list_facts(candidate.goal_id, self.project_id)
            ) != cutoff
        ):
            raise ConflictError("SDE evidence changed while preparing review")
        if require_passing and not current:
            raise EvidenceGateError(
                "approval requires a completed goal and passing task proof"
            )
        canonical = json.dumps(
            {
                "project_id": self.project_id,
                "candidate_id": candidate_id,
                "candidate_materiality": candidate.materiality.value,
                "candidate_rationale": candidate.rationale,
                "candidate_impact": candidate.impact,
                "candidate_retrieval_value": candidate.retrieval_value,
                "candidate_fact_ids": candidate.fact_ids,
                "candidate_created_at": candidate.created_at,
                "goal_id": goal.goal_id,
                "goal_problem": goal.problem,
                "goal_status": goal.status.value,
                "goal_started_at": goal.started_at,
                "goal_completed_at": goal.completed_at,
                "success_criteria": [
                    (criterion.criterion_id, criterion.description)
                    for criterion in goal.success_criteria
                ],
                "lifecycle_revision": goal.lifecycle_revision,
                "criteria_revision": goal.criteria_revision,
                "epoch_cutoff": cutoff,
                "facts_sha256": before,
                "passing": current,
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sde_review_has_current_passing_evidence(self, candidate_id: str) -> bool:
        """Report whether selected verification passed at task completion."""

        try:
            self.sde_review_evidence_state(candidate_id, require_passing=True)
        except EvidenceGateError:
            return False
        return True

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

        return self.commit_sde_confirmation(
            self.prepare_sde_confirmation(
                request, authenticated_subject=authenticated_subject
            )
        )

    def prepare_sde_confirmation(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
        validated_binding: SDEReviewBinding | None = None,
    ) -> _PreparedSDEConfirmation:
        """Authorize and recheck proof before any project write fence is opened."""

        if request.review_draft is not None and validated_binding is None:
            raise EvidenceGateError(
                "editable SDE decisions require receipt and multi-document binding"
            )
        if request.review_draft is None and validated_binding is not None:
            raise ValueError("a review binding requires an edited SDE draft")
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
        override = bool(request.evidence_override_reason)
        if override and (validated_binding is None or request.decision is not ReviewDecision.APPROVED):
            raise EvidenceGateError("evidence override requires an edited owner review")
        if request.decision is ReviewDecision.APPROVED:
            facts = tuple(
                self.store.get_fact(fact_id, self.project_id)
                for fact_id in candidate.fact_ids
            )
            if any(fact.kind not in _SDE_FACT_KINDS for fact in facts):
                raise EvidenceGateError(
                    "approval cannot retain advice, proposals, or lifecycle facts"
                )
        facts_sha256 = self.store.facts_digest(candidate.fact_ids, self.project_id)
        if validated_binding is not None:
            draft = request.review_draft
            if draft is None or (
                validated_binding.project_id != self.project_id
                or validated_binding.candidate_id != request.candidate_id
                or validated_binding.decision != request.decision.value
                or validated_binding.reviewer_id != reviewer_id
                or validated_binding.review_rationale != request.rationale
                or validated_binding.evidence_override_reason != (request.evidence_override_reason or "")
                or validated_binding.supporting_facts_sha256 != facts_sha256
                or validated_binding.draft_sha256 != draft.sha256()
                or validated_binding.sha256() != request.expected_review_binding_sha256
            ):
                raise ConflictError("edited SDE decision does not match its reviewed binding")
            evidence_state = self.sde_review_evidence_state(
                request.candidate_id,
                require_passing=False,
            )
            if evidence_state != validated_binding.evidence_state_sha256:
                raise ConflictError("SDE evidence changed after the review was displayed")
        receipt = AuditReceipt(
            candidate_id=request.candidate_id,
            decision=request.decision,
            facts_sha256=facts_sha256,
            artifacts=request.artifacts,
            artifact_inventory_complete=request.artifact_inventory_complete,
            reviewer_id=reviewer_id,
            review_rationale=request.rationale,
            review_draft_json=(
                request.review_draft.canonical_bytes().decode("utf-8")
                if request.review_draft is not None else None
            ),
            review_binding_sha256=(validated_binding.sha256() if validated_binding else None),
            review_binding_json=(
                validated_binding.canonical_bytes().decode("utf-8")
                if validated_binding else None
            ),
        )
        return _PreparedSDEConfirmation(receipt, expected_effect_revision)

    def commit_sde_confirmation(
        self, prepared: _PreparedSDEConfirmation
    ) -> AuditReceipt:
        """Commit only if the reviewed supporting facts have not changed."""

        receipt = prepared.receipt
        with self._effect_fence(prepared.expected_effect_revision):
            if self.store.facts_digest(
                self.store.get_sde_candidate(
                    receipt.candidate_id, self.project_id
                ).fact_ids,
                self.project_id,
            ) != receipt.facts_sha256:
                raise ConflictError("reviewed facts changed before disposition")
            return self.store.create_receipt(receipt, self.project_id)
