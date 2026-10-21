"""Goal lifecycle, evidence gate, SDE review, and purge orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re

from .models import (
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    CriterionProgress,
    CriterionStatus,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    Fact,
    FactCapacity,
    FactArchiveReceipt,
    FactKind,
    PurgeFailureCode,
    FactCompactionProposal,
    GoalBullet,
    GoalBulletCategory,
    GoalBulletProjection,
    GoalCard,
    GoalListPage,
    GoalSnapshot,
    GoalStatus,
    MAX_CRITERIA_REVISIONS,
    MAX_GOAL_STATUS_CANDIDATES,
    MAX_GOAL_STATUS_PURGE_RECEIPTS,
    MAX_SDE_SUPPORTING_FACTS,
    MAX_SUCCESS_CRITERIA,
    Materiality,
    PurgeStatus,
    ReviewDecision,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    SDEStatus,
    SuccessCriterion,
    new_id,
)
from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    EventDisposition,
    EventPayload,
    FactRecorded,
    GoalActivityObserved,
    GoalActivated,
    GoalBlocked,
    GoalCancelled,
    GoalDeferred,
    GoalFinishRequested,
    GoalReopened,
    GoalCriteriaAmended,
    GoalSuperseded,
    GoalStarted,
)
from .evidence import (
    EvidenceAdapterError,
    EvidenceVerificationContext,
    EvidenceVerifier,
    RejectUnverifiedEvidence,
    evidence_has_current_attestations,
)
from .errors import safe_exception_label
from .purge import ArtifactPurger, PurgeError
from .reviews import (
    RejectUnauthenticatedReview,
    ReviewAuthorizer,
)
from .reporting import (
    MAX_GOAL_REPORT_CHILDREN,
    MAX_GOAL_REPORT_RECEIPTS,
    MAX_GOAL_REPORT_SDE_CANDIDATES,
    GoalReportSummary,
    render_goal_report,
)
from .store import (
    ConflictError,
    CuratorStore,
    EventClaimError,
    EventInboxCapacityError,
    FactCapacityError,
)
from .validation import is_exact_int


class EvidenceGateError(ValueError):
    """A proposed durable conclusion is not supported by direct evidence."""


@dataclass(frozen=True, slots=True)
class PurgeTargetStatus:
    """Current retry state for one artifact named by an audit receipt."""

    artifact: ArtifactRef
    status: ArtifactStatus
    attempts: int
    error: str | None
    created_at: str
    last_attempt_at: str | None
    next_attempt_at: str | None
    next_attempt_in_seconds: int | None
    age_seconds: int | None
    last_attempt_age_seconds: int | None
    safe_recovery_action: str
    hold_created_at: str | None
    hold_created_by: str | None
    hold_released_at: str | None
    hold_released_by: str | None
    hold_release_rationale: str | None


@dataclass(frozen=True, slots=True)
class _PreparedEvent:
    """Evidence and fact context gathered before the event commit transaction."""

    prior_fact_ids: frozenset[str]
    verified_goal_snapshot: GoalCard | None = None
    prepared_fact: Fact | None = None
    finish_snapshot: tuple[GoalCard, tuple[Fact, ...], set[str]] | None = None
    expected_finish_revision: int | None = None


def _timestamp_age_seconds(
    timestamp: str, now: datetime
) -> int | None:
    """Return nonnegative age for a valid timezone-aware durable timestamp."""

    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return max(0, int((now - parsed.astimezone(UTC)).total_seconds()))


def _timestamp_delay_seconds(
    timestamp: str | None, now: datetime
) -> int | None:
    """Return remaining delay for a valid timezone-aware retry deadline."""

    if timestamp is None:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return max(0, int((parsed.astimezone(UTC) - now).total_seconds()))


def _purge_recovery_action(receipt: AuditReceipt, status: ArtifactStatus) -> str:
    """Suggest only the next configured action that satisfies current gates."""

    if status is ArtifactStatus.PURGED:
        return "none"
    if status is ArtifactStatus.HELD:
        return "release_artifact_hold"
    if not receipt.artifact_inventory_complete:
        return "artifact_inventory_complete"
    if not receipt.canonical_persisted:
        return "goal_persist"
    return "retry_pending_purges"


class CuratorService:
    """Goal-ledger application service scoped to one configured project."""

    def __init__(
        self,
        store: CuratorStore,
        purger: ArtifactPurger,
        evidence_verifier: EvidenceVerifier | None = None,
        review_authorizer: ReviewAuthorizer | None = None,
        *,
        project_id: str = "default",
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        self.store = store
        self.purger = purger
        self.evidence_verifier = evidence_verifier or RejectUnverifiedEvidence()
        self.review_authorizer = review_authorizer or RejectUnauthenticatedReview()
        self.project_id = project_id

    def goal_start(
        self,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        *,
        owner: str | None = None,
        checklist_id: str | None = None,
        checklist_version: str | None = None,
        checklist_source_text: str | None = None,
        parent_goal_id: str | None = None,
        depends_on_goal_ids: tuple[str, ...] = (),
        goal_id: str | None = None,
        initial_status: GoalStatus = GoalStatus.ACTIVE,
        next_action: str | None = None,
        source_event_id: str | None = None,
    ) -> GoalCard:
        """Create a goal with an explicit problem and testable success criteria."""

        parse_failed = False
        normalized_status: GoalStatus | None = None
        try:
            normalized_status = GoalStatus(initial_status)
        except ValueError:
            parse_failed = True
        if parse_failed or normalized_status is None:
            raise ValueError("initial_status must be planned or active")
        initial_status = normalized_status
        if initial_status not in {GoalStatus.PLANNED, GoalStatus.ACTIVE}:
            raise ValueError("initial_status must be planned or active")
        with self.store.transaction():
            parent_ancestors: set[str] = set()
            if parent_goal_id is not None:
                parent = self.store.get_goal(parent_goal_id, self.project_id)
                if parent.status in {
                    GoalStatus.COMPLETE,
                    GoalStatus.CANCELLED,
                    GoalStatus.SUPERSEDED,
                }:
                    raise ConflictError("cannot add a child to a terminal goal")
                ancestor_id = parent.parent_goal_id
                while ancestor_id is not None:
                    if ancestor_id in parent_ancestors:
                        raise ConflictError("existing goal hierarchy contains a cycle")
                    parent_ancestors.add(ancestor_id)
                    ancestor_id = self.store.get_goal(
                        ancestor_id, self.project_id
                    ).parent_goal_id
            for dependency_id in depends_on_goal_ids:
                if dependency_id == goal_id:
                    raise ValueError("a goal cannot depend on itself")
                if dependency_id == parent_goal_id or dependency_id in parent_ancestors:
                    raise ValueError("a child cannot depend on its parent or ancestor")
                dependency = self.store.get_goal(dependency_id, self.project_id)
                if dependency.status in {GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}:
                    raise ConflictError(
                        "cannot depend on a cancelled or superseded goal; "
                        "reference its active replacement instead"
                    )
            goal = GoalCard(
                goal_id=goal_id or new_id(),
                problem=problem,
                success_criteria=success_criteria,
                owner=owner,
                checklist_id=checklist_id,
                checklist_version=checklist_version,
                checklist_source_text=checklist_source_text,
                parent_goal_id=parent_goal_id,
                depends_on_goal_ids=depends_on_goal_ids,
                project_id=self.project_id,
                status=initial_status,
                next_action=next_action,
            )
            self.store.add_goal(goal, source_event_id=source_event_id)
            return goal

    def goal_activate(
        self,
        goal_id: str,
        reason: str,
        expected_lifecycle_revision: int,
    ) -> GoalCard:
        """Activate planned work after explicit, revision-checked acceptance."""

        reason = reason.strip()
        if not reason or len(reason) > 500 or "\n" in reason or "\r" in reason:
            raise ValueError("activation requires a single-line reason of at most 500 characters")
        fact = Fact(goal_id=goal_id, kind=FactKind.INTENT, bullet=f"Activated: {reason}")
        return self.store.activate_goal(
            goal_id,
            fact,
            expected_lifecycle_revision,
            self.project_id,
        )

    def goal_fact(
        self,
        goal_id: str,
        kind: FactKind,
        bullet: str,
        *,
        criterion_id: str | None = None,
        evidence: tuple[EvidenceRef, ...] = (),
        fact_id: str | None = None,
    ) -> tuple[Fact, bool]:
        """Record a compact fact, independently verifying proof-bearing facts."""

        if kind in {
            FactKind.REOPENED,
            FactKind.CRITERIA_AMENDED,
            FactKind.CANCELLED,
            FactKind.SUPERSEDED,
        }:
            raise ValueError("lifecycle facts are generated by their goal transition")
        goal = self.store.get_goal(goal_id, self.project_id)
        if goal.status in {
            GoalStatus.COMPLETE,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        }:
            raise ConflictError("terminal goals cannot accept new facts")
        if criterion_id is not None and criterion_id not in {
            item.criterion_id for item in goal.success_criteria
        }:
            raise ValueError(f"unknown success criterion: {criterion_id}")
        attestations: tuple[EvidenceAttestation, ...] = ()
        if kind is FactKind.VERIFICATION:
            if not evidence or criterion_id is None:
                raise EvidenceGateError(
                    "verification requires independently verified passing evidence"
                )
            attestations = self._attest_evidence(goal, criterion_id, evidence)
            if len(attestations) != len(evidence):
                raise EvidenceGateError(
                    "verification requires independently verified passing evidence"
                )
        fact = Fact(
            goal_id=goal_id,
            kind=kind,
            bullet=bullet,
            fact_id=fact_id or new_id(),
            criterion_id=criterion_id,
            evidence=evidence,
            verification_attestations=attestations,
        )
        # Evidence adapters may be expensive, so verify before taking the SQLite
        # write lock. Re-read lifecycle state under the write transaction before
        # append: another process may have completed the goal during verification.
        with self.store.transaction():
            return self._append_preverified_fact(fact, goal)

    def _append_preverified_fact(
        self, fact: Fact, verified_goal_snapshot: GoalCard | None = None
    ) -> tuple[Fact, bool]:
        """Append under the current write lock after external proof ran outside it."""

        current_goal = self.store.get_goal(fact.goal_id, self.project_id)
        if current_goal.status in {
            GoalStatus.COMPLETE,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        }:
            raise ConflictError("terminal goals cannot accept new facts")
        if fact.criterion_id is not None and fact.criterion_id not in {
            item.criterion_id for item in current_goal.success_criteria
        }:
            raise ValueError(f"unknown success criterion: {fact.criterion_id}")
        if fact.kind is FactKind.VERIFICATION and verified_goal_snapshot is not None and (
            current_goal.criteria_revision != verified_goal_snapshot.criteria_revision
            or current_goal.lifecycle_revision
            != verified_goal_snapshot.lifecycle_revision
        ):
            raise ConflictError(
                "goal changed during evidence verification; reload and retry"
            )
        return self.store.append_fact(fact, self.project_id)

    def _attest_evidence(
        self,
        goal: GoalCard,
        criterion_id: str,
        evidence: tuple[EvidenceRef, ...],
    ) -> tuple[EvidenceAttestation, ...]:
        """Verify each reference through the host-bound adapter registry."""

        context = EvidenceVerificationContext(
            project_id=self.project_id,
            goal_id=goal.goal_id,
            criterion_id=criterion_id,
            now=datetime.now(UTC),
        )
        if any(item.outcome is not EvidenceOutcome.PASSED for item in evidence):
            return ()
        try:
            results = tuple(
                self.evidence_verifier.attest(item, context) for item in evidence
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Persist only a fixed operational category; never expose adapter text.
            raise EvidenceAdapterError() from None
        if any(
            not isinstance(result, EvidenceAttestation)
            or result.evidence_kind != item.evidence_kind
            or result.evidence_sha256 != item.sha256
            or result.project_id != context.project_id
            or result.goal_id != context.goal_id
            or result.criterion_id != context.criterion_id
            for item, result in zip(evidence, results, strict=True)
        ):
            return ()
        return tuple(result for result in results if result is not None)

    def _fact_is_currently_verified(self, goal: GoalCard, fact: Fact) -> bool:
        """Recheck a stored attestation and its exact source revision on each use."""

        if fact.kind is not FactKind.VERIFICATION or fact.criterion_id is None:
            return False
        if any(item.outcome is not EvidenceOutcome.PASSED for item in fact.evidence):
            return False
        return evidence_has_current_attestations(
            self.evidence_verifier,
            project_id=self.project_id,
            goal_id=goal.goal_id,
            criterion_id=fact.criterion_id,
            evidence=fact.evidence,
            stored=fact.verification_attestations,
        )

    def _verified_criterion_ids(
        self, goal: GoalCard, facts: tuple[Fact, ...]
    ) -> set[str]:
        cutoff = self._evidence_epoch_cutoff(facts)
        return {
            fact.criterion_id
            for fact in facts
            if fact.kind is FactKind.VERIFICATION
            and fact.criterion_id is not None
            and (cutoff is None or fact.created_at > cutoff)
            and self._fact_is_currently_verified(goal, fact)
        }

    def goal_finish(
        self,
        goal_id: str,
        completion_claim: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Request completion; missing proof or dependent work leaves the goal open."""
        if not completion_claim.strip():
            raise ValueError("completion claim must not be empty")
        if len(completion_claim.strip()) > 980:
            raise ValueError("completion claim exceeds 980 characters")
        initial_goal = self.store.get_goal(goal_id, self.project_id)
        expected_revision = (
            initial_goal.lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        if initial_goal.lifecycle_revision != expected_revision:
            raise ConflictError("goal lifecycle revision changed; reload before finishing")
        if initial_goal.status is GoalStatus.COMPLETE:
            return initial_goal
        facts_snapshot = self.store.list_facts(goal_id, self.project_id)
        for _attempt in range(3):
            verified = self._verified_criterion_ids(initial_goal, facts_snapshot)
            with self.store.transaction():
                current_goal = self.store.get_goal(goal_id, self.project_id)
                current_facts = self.store.list_facts(goal_id, self.project_id)
                if (
                    current_goal.lifecycle_revision != initial_goal.lifecycle_revision
                    or current_goal.criteria_revision != initial_goal.criteria_revision
                ):
                    raise ConflictError(
                        "goal changed during evidence verification; reload before finishing"
                    )
                if tuple(fact.fact_id for fact in current_facts) == tuple(
                    fact.fact_id for fact in facts_snapshot
                ):
                    return self._goal_finish_in_transaction(
                        goal_id,
                        completion_claim,
                        expected_revision,
                        verified,
                    )
            facts_snapshot = current_facts
        raise ConflictError(
            "facts kept changing during evidence verification; retry finish"
        )

    def _goal_finish_in_transaction(
        self,
        goal_id: str,
        completion_claim: str,
        expected_lifecycle_revision: int | None = None,
        verified_criterion_ids: set[str] | None = None,
    ) -> GoalCard:
        """Evaluate criteria, children, and dependencies under one write lock."""

        if not completion_claim.strip():
            raise ValueError("completion claim must not be empty")
        if len(completion_claim.strip()) > 980:
            raise ValueError("completion claim exceeds 980 characters")
        goal = self.store.get_goal(goal_id, self.project_id)
        expected_revision = (
            goal.lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        if goal.lifecycle_revision != expected_revision:
            raise ConflictError("goal lifecycle revision changed; reload before finishing")
        if goal.status is GoalStatus.PLANNED:
            raise ConflictError("planned goals must be explicitly activated before completion")
        if goal.status is GoalStatus.COMPLETE:
            return goal
        if goal.status in {GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}:
            raise ConflictError("terminal goals cannot be completed")
        facts = [
            Fact(
                goal_id=goal_id,
                kind=FactKind.COMPLETION_CLAIM,
                bullet=f"Completion claim: {completion_claim.strip()}",
            )
        ]
        verified = verified_criterion_ids or set()
        missing = tuple(
            criterion
            for criterion in goal.success_criteria
            if criterion.criterion_id not in verified
        )
        children = self.store.list_child_goals(goal_id, self.project_id)
        open_children = tuple(
            child
            for child in children
            if child.status
            not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
        )
        blocked_dependencies = tuple(
            dependency
            for dependency_id in goal.depends_on_goal_ids
            if (dependency := self.store.get_goal(dependency_id, self.project_id)).status
            is not GoalStatus.COMPLETE
        )
        if missing or open_children or blocked_dependencies:
            open_reasons: list[str] = []
            if missing:
                descriptions = "; ".join(item.description for item in missing)
                open_reasons.append(f"Verify unmet success criteria: {descriptions}")
            if open_children:
                child_ids = ", ".join(child.goal_id for child in open_children)
                open_reasons.append(f"Finish open child goals: {child_ids}")
            if blocked_dependencies:
                dependency_ids = ", ".join(
                    dependency.goal_id for dependency in blocked_dependencies
                )
                open_reasons.append(f"Complete dependencies first: {dependency_ids}")
            next_action = "; ".join(open_reasons)[:1000]
            for criterion in missing:
                facts.append(
                    Fact(
                        goal_id=goal_id,
                        kind=FactKind.OPEN_GATE,
                        bullet=(
                            f"Open: success criterion '{criterion.description}' "
                            "lacks passing evidence"
                        ),
                        criterion_id=criterion.criterion_id,
                    )
                )
            if open_children:
                for child in open_children:
                    facts.append(
                        Fact(
                            goal_id=goal_id,
                            kind=FactKind.OPEN_GATE,
                            bullet=(
                                f"Open: child goal '{child.goal_id}' remains "
                                f"{child.status.value}"
                            ),
                        )
                    )
            if blocked_dependencies:
                for dependency in blocked_dependencies:
                    facts.append(
                        Fact(
                            goal_id=goal_id,
                            kind=FactKind.OPEN_GATE,
                            bullet=(
                                f"Open: dependency '{dependency.goal_id}' remains "
                                f"{dependency.status.value}"
                            ),
                        ),
                    )
            facts.append(
                Fact(
                    goal_id=goal_id,
                    kind=FactKind.OUTCOME,
                    bullet="open",
                )
            )
            return self.store.transition_goal(
                goal_id,
                GoalStatus.OPEN,
                next_action,
                tuple(facts),
                expected_revision,
                self.project_id,
            )

        facts.append(
            Fact(
                goal_id=goal_id,
                kind=FactKind.OUTCOME,
                bullet=(
                    "completed — every success criterion has a passing evidence "
                    "reference and all child goals and dependencies are complete"
                ),
            )
        )
        return self.store.transition_goal(
            goal_id,
            GoalStatus.COMPLETE,
            None,
            tuple(facts),
            expected_revision,
            self.project_id,
        )

    def goal_defer(
        self,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Defer unfinished work with a concrete reason and resumption action."""

        if not reason.strip() or not next_action.strip():
            raise ValueError("defer requires both a reason and a concrete next action")
        if len(next_action.strip()) > 1000:
            raise ValueError("next_action exceeds 1000 characters")
        fact = Fact(
            goal_id=goal_id,
            kind=FactKind.OPEN_GATE,
            bullet=f"Deferred: {reason.strip()}; next: {next_action.strip()}",
        )
        expected_revision = (
            self.store.get_goal(goal_id, self.project_id).lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        return self.store.transition_goal(
            goal_id,
            GoalStatus.DEFERRED,
            next_action.strip(),
            (fact,),
            expected_revision,
            self.project_id,
        )

    def goal_block(
        self,
        goal_id: str,
        dependency: str,
        recovery: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Record an external dependency and recovery path for blocked work."""

        if not dependency.strip() or not recovery.strip():
            raise ValueError("blocked goal requires the dependency and recovery path")
        if len(recovery.strip()) > 1000:
            raise ValueError("recovery path exceeds 1000 characters")
        fact = Fact(
            goal_id=goal_id,
            kind=FactKind.OPEN_GATE,
            bullet=f"Blocked: {dependency.strip()}; recovery: {recovery.strip()}",
        )
        expected_revision = (
            self.store.get_goal(goal_id, self.project_id).lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        return self.store.transition_goal(
            goal_id,
            GoalStatus.BLOCKED,
            recovery.strip(),
            (fact,),
            expected_revision,
            self.project_id,
        )

    def goal_cancel(self, goal_id: str, reason: str) -> GoalCard:
        """Cancel unfinished work without treating it as successful."""

        reason = reason.strip()
        if not reason or len(reason) > 500 or "\n" in reason or "\r" in reason:
            raise ValueError(
                "cancellation requires a single-line reason of at most 500 characters"
            )
        fact = Fact(
            goal_id=goal_id,
            kind=FactKind.CANCELLED,
            bullet=f"Cancelled: {reason}",
        )
        return self.store.retire_goal(
            goal_id, GoalStatus.CANCELLED, reason, fact, self.project_id
        )

    def goal_supersede(
        self, goal_id: str, replacement_goal_id: str, reason: str
    ) -> GoalCard:
        """Replace unfinished work with an explicit same-project goal."""

        reason = reason.strip()
        if not reason or len(reason) > 500 or "\n" in reason or "\r" in reason:
            raise ValueError(
                "supersession requires a single-line reason of at most 500 characters"
            )
        if not replacement_goal_id.strip() or replacement_goal_id == goal_id:
            raise ValueError("supersession requires a different replacement goal")
        fact = Fact(
            goal_id=goal_id,
            kind=FactKind.SUPERSEDED,
            bullet=f"Superseded by goal '{replacement_goal_id}': {reason}",
        )
        return self.store.retire_goal(
            goal_id,
            GoalStatus.SUPERSEDED,
            reason,
            fact,
            self.project_id,
            replacement_goal_id,
        )

    def goal_reopen(
        self,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Reopen a completed goal and require fresh evidence for every criterion."""

        reason = reason.strip()
        next_action = next_action.strip()
        if not reason or not next_action:
            raise ValueError("reopen requires both a reason and a concrete next action")
        if len(reason) + len(next_action) + 18 > 1000:
            raise ValueError("reopen reason and next_action exceed the fact bullet limit")
        fact = Fact(
            goal_id=goal_id,
            kind=FactKind.REOPENED,
            bullet=f"Reopened: {reason}; next: {next_action}",
        )
        expected_revision = (
            self.store.get_goal(goal_id, self.project_id).lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        return self.store.reopen_goal(
            goal_id,
            next_action,
            fact,
            expected_revision,
            self.project_id,
        )

    def goal_amend_criteria(
        self,
        goal_id: str,
        expected_revision: int,
        success_criteria: tuple[SuccessCriterion, ...],
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Explicitly amend an open goal and require fresh proof afterward."""

        reason = reason.strip()
        next_action = next_action.strip()
        if not is_exact_int(expected_revision) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if expected_revision >= MAX_CRITERIA_REVISIONS:
            raise ValueError(
                f"criteria history is limited to {MAX_CRITERIA_REVISIONS} revisions"
            )
        if not success_criteria or len(success_criteria) > MAX_SUCCESS_CRITERIA:
            raise ValueError(
                f"amended criteria must contain 1-{MAX_SUCCESS_CRITERIA} items"
            )
        criterion_ids = tuple(item.criterion_id for item in success_criteria)
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("amended criterion IDs must be unique")
        if not reason or not next_action:
            raise ValueError("criteria amendment requires reason and next_action")
        bullet = f"Criteria amended: {reason}; next: {next_action}"
        if len(bullet) > 1000:
            raise ValueError("criteria amendment fact exceeds 1000 characters")
        fact = Fact(goal_id=goal_id, kind=FactKind.CRITERIA_AMENDED, bullet=bullet)
        expected_state_revision = (
            self.store.get_goal(goal_id, self.project_id).lifecycle_revision
            if expected_lifecycle_revision is None
            else expected_lifecycle_revision
        )
        return self.store.amend_goal_criteria(
            goal_id,
            expected_revision,
            success_criteria,
            reason,
            next_action,
            fact,
            self.project_id,
            expected_state_revision,
        )

    def goal_status(
        self,
        goal_id: str,
        *,
        sde_offset: int = 0,
        purge_offset: int = 0,
    ) -> GoalSnapshot:
        """Build a bounded goal view with exact SDE and purge-page totals."""

        goal = self.store.get_goal(goal_id, self.project_id)
        facts = self.store.list_facts(goal_id, self.project_id)
        criterion_progress = tuple(
            self._criterion_progress(goal, criterion, facts)
            for criterion in goal.success_criteria
        )
        sde_candidate_total, sde_candidates = self.store.list_sde_candidate_page(
            goal_id, self.project_id, sde_offset, MAX_GOAL_STATUS_CANDIDATES
        )
        pending_purge_total, pending_purges = self.store.pending_receipt_page_for_goal(
            goal_id, self.project_id, purge_offset, MAX_GOAL_STATUS_PURGE_RECEIPTS
        )
        sde_status_counts = self.store.sde_candidate_status_counts(
            goal_id, self.project_id
        )
        return GoalSnapshot(
            goal=goal,
            facts=facts,
            sde_candidates=sde_candidates,
            pending_purges=pending_purges,
            criteria=criterion_progress,
            criteria_history=self.store.list_goal_criteria_versions(
                goal_id, self.project_id
            ),
            fact_capacity=self.store.goal_fact_capacity(goal_id, self.project_id),
            sde_candidate_total=sde_candidate_total,
            sde_candidate_offset=sde_offset,
            sde_candidate_next_offset=(
                sde_offset + len(sde_candidates)
                if sde_offset + len(sde_candidates) < sde_candidate_total
                else None
            ),
            sde_candidate_status_counts=tuple(sorted(sde_status_counts.items())),
            pending_purge_total=pending_purge_total,
            pending_purge_offset=purge_offset,
            pending_purge_next_offset=(
                purge_offset + len(pending_purges)
                if purge_offset + len(pending_purges) < pending_purge_total
                else None
            ),
        )

    def goal_bullet_projection(self, goal_id: str) -> GoalBulletProjection:
        """Build compact bullets with evidence-derived truth labels and open gates."""

        return self._goal_bullet_projection(self.goal_status(goal_id))

    def goal_report(
        self,
        goal_id: str,
        *,
        fact_offset: int = 0,
        fact_limit: int = 16,
        child_offset: int = 0,
        sde_offset: int = 0,
        receipt_offset: int = 0,
    ) -> str:
        """Render one bounded read without holding a write lock during evidence checks."""

        goal = self.store.get_goal(goal_id, self.project_id)
        facts = self.store.list_facts(goal_id, self.project_id)
        criterion_progress = tuple(
            self._criterion_progress(goal, criterion, facts)
            for criterion in goal.success_criteria
        )
        pending_sde_total, pending_sdes = self.store.list_sde_candidate_page(
            goal_id,
            self.project_id,
            sde_offset,
            MAX_GOAL_REPORT_SDE_CANDIDATES,
            SDEStatus.PENDING_REVIEW,
        )
        pending_receipt_total, pending_receipts = self.store.pending_receipt_page_for_goal(
            goal_id, self.project_id, 0, MAX_GOAL_REPORT_RECEIPTS
        )
        snapshot = GoalSnapshot(
            goal=goal,
            facts=facts,
            sde_candidates=pending_sdes,
            pending_purges=pending_receipts,
            criteria=criterion_progress,
            criteria_history=self.store.list_goal_criteria_versions(
                goal_id, self.project_id
            ),
            fact_capacity=self.store.goal_fact_capacity(goal_id, self.project_id),
        )
        projection = self._goal_bullet_projection(snapshot)
        child_total, children = self.store.list_child_goal_page(
            goal_id,
            self.project_id,
            child_offset,
            MAX_GOAL_REPORT_CHILDREN,
        )
        child_status_counts = self.store.child_goal_status_counts(
            goal_id, self.project_id
        )
        open_child_total = sum(
            count
            for status, count in child_status_counts.items()
            if status
            not in {
                GoalStatus.COMPLETE.value,
                GoalStatus.CANCELLED.value,
                GoalStatus.SUPERSEDED.value,
            }
        )
        dependencies = tuple(
            self.store.get_goal(dependency_id, self.project_id)
            for dependency_id in goal.depends_on_goal_ids
        )
        receipt_total, receipts = self.store.receipt_page_for_goal(
            goal_id, self.project_id, receipt_offset, MAX_GOAL_REPORT_RECEIPTS
        )
        purge_status_counts = self.store.receipt_purge_status_counts(
            goal_id, self.project_id
        )
        summary = GoalReportSummary(
            child_total=child_total,
            open_child_total=open_child_total,
            sde_status_counts=tuple(
                sorted(self.store.sde_candidate_status_counts(goal_id, self.project_id).items())
            ),
            pending_sde_total=pending_sde_total,
            receipt_total=receipt_total,
            pending_receipt_total=purge_status_counts.get(
                PurgeStatus.PURGE_PENDING.value, pending_receipt_total
            ),
            purge_status_counts=tuple(sorted(purge_status_counts.items())),
        )
        intake = self.store.goal_report_context(goal_id, self.project_id)
        return render_goal_report(
            snapshot,
            projection,
            children,
            dependencies,
            receipts,
            intake=intake,
            summary=summary,
            fact_offset=fact_offset,
            fact_limit=fact_limit,
            child_offset=child_offset,
            sde_offset=sde_offset,
            receipt_offset=receipt_offset,
        )

    def fact_compaction_propose(
        self, goal_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Prepare a content-hashed preview; this never changes active facts."""

        return self.store.propose_fact_compaction(
            goal_id, self.project_id, max_facts
        )

    def fact_compaction_approve(
        self,
        compaction_id: str,
        goal_id: str,
        fact_ids: tuple[str, ...],
        source_sha256: str,
        reviewer_id: str,
        approval_reason: str,
    ) -> FactArchiveReceipt:
        """Archive only the exact preview approved by a scoped reviewer."""

        return self.store.approve_fact_compaction(
            compaction_id,
            goal_id,
            self.project_id,
            fact_ids,
            source_sha256,
            reviewer_id,
            approval_reason,
        )

    def fact_archive_receipts(
        self, goal_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read immutable archive audit receipts for a project-scoped goal."""

        return self.store.list_fact_archive_receipts(
            goal_id, self.project_id, offset=offset, limit=limit
        )

    def _goal_bullet_projection(
        self, snapshot: GoalSnapshot
    ) -> GoalBulletProjection:
        """Build the truth-labeled projection for an already read snapshot."""

        verified_fact_ids = {
            fact_id
            for criterion in snapshot.criteria
            if criterion.status is CriterionStatus.VERIFIED
            for fact_id in criterion.verification_fact_ids
        }
        bullets: list[GoalBullet] = [
            GoalBullet(GoalBulletCategory.PROBLEM, snapshot.goal.problem)
        ]
        bullets.extend(self._criterion_bullets(snapshot.criteria))
        bullets.extend(
            self._fact_bullet(fact, verified_fact_ids) for fact in snapshot.facts
        )
        bullets.extend(self._goal_state_bullets(snapshot.goal))
        bullets.extend(self._pending_review_bullets(snapshot))
        bullets.extend(self._pending_purge_bullets(snapshot))
        if snapshot.fact_capacity is not None:
            bullets.extend(self._fact_capacity_bullets(snapshot.fact_capacity))
        if snapshot.goal.next_action:
            bullets.append(
                GoalBullet(GoalBulletCategory.NEXT, snapshot.goal.next_action)
            )
        return GoalBulletProjection(
            goal_id=snapshot.goal.goal_id,
            problem=snapshot.goal.problem,
            status=snapshot.goal.status,
            criteria=snapshot.criteria,
            bullets=tuple(bullets),
            next_action=snapshot.goal.next_action,
        )

    @staticmethod
    def _criterion_bullets(
        criteria: tuple[CriterionProgress, ...],
    ) -> list[GoalBullet]:
        bullets: list[GoalBullet] = []
        for criterion in criteria:
            bullets.append(
                GoalBullet(
                    GoalBulletCategory.CRITERION,
                    f"{criterion.criterion_id}: {criterion.status.value} — "
                    f"{criterion.description}",
                    criterion_id=criterion.criterion_id,
                )
            )
            if criterion.status is CriterionStatus.OPEN:
                bullets.append(
                    GoalBullet(
                        GoalBulletCategory.OPEN,
                        "Required criterion remains unverified: "
                        f"{criterion.criterion_id} — {criterion.description}",
                        criterion_id=criterion.criterion_id,
                    )
                )
        return bullets

    @staticmethod
    def _fact_bullet(
        fact: Fact, verified_fact_ids: set[str]
    ) -> GoalBullet:
        text = f"{fact.kind.value.replace('_', ' ').capitalize()}: {fact.bullet}"
        if fact.kind is FactKind.OPEN_GATE:
            category = GoalBulletCategory.RECORDED
            text = f"Prior gate fact: {fact.bullet}"
        elif fact.kind is FactKind.OUTCOME:
            category = GoalBulletCategory.RECORDED
            text = f"Outcome: {fact.bullet}"
        elif fact.kind is FactKind.COMPLETION_CLAIM:
            category = GoalBulletCategory.UNVERIFIED
        elif fact.kind is FactKind.VERIFICATION:
            category = (
                GoalBulletCategory.VERIFIED
                if fact.fact_id in verified_fact_ids
                else GoalBulletCategory.UNVERIFIED
            )
        else:
            category = GoalBulletCategory.RECORDED
        return GoalBullet(
            category,
            text,
            fact_id=fact.fact_id,
            criterion_id=fact.criterion_id,
            evidence=fact.evidence,
        )

    @staticmethod
    def _goal_state_bullets(goal: GoalCard) -> list[GoalBullet]:
        if goal.status not in (
            GoalStatus.OPEN,
            GoalStatus.BLOCKED,
            GoalStatus.DEFERRED,
        ):
            return []
        status_gate = goal.status.value
        if goal.next_action:
            status_gate += f"; next action: {goal.next_action}"
        return [GoalBullet(GoalBulletCategory.OPEN, status_gate)]

    @staticmethod
    def _pending_review_bullets(snapshot: GoalSnapshot) -> list[GoalBullet]:
        bullets = [
            GoalBullet(
                GoalBulletCategory.OPEN,
                f"SDE candidate {candidate.candidate_id} awaits human review",
            )
            for candidate in snapshot.sde_candidates
            if candidate.status is SDEStatus.PENDING_REVIEW
        ]
        pending_total = sum(
            count
            for status, count in snapshot.sde_candidate_status_counts
            if status == SDEStatus.PENDING_REVIEW.value
        )
        visible_total = len(bullets)
        if pending_total > visible_total:
            continuation = (
                f"; next page: goal_status(sde_offset={snapshot.sde_candidate_next_offset})"
                if snapshot.sde_candidate_next_offset is not None
                else ""
            )
            bullets.append(
                GoalBullet(
                    GoalBulletCategory.OPEN,
                    f"{pending_total} SDE candidate(s) await review overall; "
                    f"this page shows {visible_total}{continuation}",
                )
            )
        return bullets

    @staticmethod
    def _pending_purge_bullets(snapshot: GoalSnapshot) -> list[GoalBullet]:
        bullets = [
            GoalBullet(
                GoalBulletCategory.OPEN,
                f"Purge receipt {receipt.receipt_id} remains pending",
            )
            for receipt in snapshot.pending_purges
        ]
        if (
            snapshot.pending_purge_total is not None
            and snapshot.pending_purge_total > len(snapshot.pending_purges)
        ):
            continuation = (
                f"; next page: goal_status(purge_offset={snapshot.pending_purge_next_offset})"
                if snapshot.pending_purge_next_offset is not None
                else ""
            )
            bullets.append(
                GoalBullet(
                    GoalBulletCategory.OPEN,
                    f"{snapshot.pending_purge_total} purge receipt(s) remain pending; "
                    f"this page shows {len(snapshot.pending_purges)}{continuation}",
                )
            )
        return bullets

    @staticmethod
    def _fact_capacity_bullets(capacity: FactCapacity) -> list[GoalBullet]:
        if capacity.append_available:
            return []
        return [
            GoalBullet(
                GoalBulletCategory.OPEN,
                capacity.open_gate
                or "Fact capacity reached; new facts are not being accepted",
            )
        ]

    @staticmethod
    def _evidence_epoch_cutoff(facts: tuple[Fact, ...]) -> str | None:
        """Return the newest explicit reopen/amendment boundary, if present."""

        return max(
            (
                fact.created_at
                for fact in facts
                if fact.kind in (FactKind.REOPENED, FactKind.CRITERIA_AMENDED)
            ),
            default=None,
        )

    def _criterion_progress(
        self,
        goal: GoalCard,
        criterion: SuccessCriterion,
        facts: tuple[Fact, ...],
    ) -> CriterionProgress:
        """Derive criterion state only from passing independently verified facts."""

        reopen_cutoff = self._evidence_epoch_cutoff(facts)
        proof_facts = tuple(
            fact
            for fact in facts
            if fact.kind is FactKind.VERIFICATION
            and fact.criterion_id == criterion.criterion_id
            and (reopen_cutoff is None or fact.created_at > reopen_cutoff)
            and self._fact_is_currently_verified(goal, fact)
        )
        return CriterionProgress(
            criterion_id=criterion.criterion_id,
            description=criterion.description,
            status=(CriterionStatus.VERIFIED if proof_facts else CriterionStatus.OPEN),
            verification_fact_ids=tuple(fact.fact_id for fact in proof_facts),
        )

    def goal_list(
        self, statuses: tuple[GoalStatus, ...] = ()
    ) -> tuple[GoalSnapshot, ...]:
        """Return a bounded compatibility listing; use goal_list_page for scale."""

        return tuple(
            self.goal_status(goal.goal_id)
            for goal in self.store.list_goals(statuses, self.project_id)
        )

    def goal_list_page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """Return bounded goal cards without loading per-goal facts or reviews."""

        total, goals = self.store.list_goal_page(
            self.project_id, offset, limit, statuses
        )
        next_offset = offset + len(goals) if offset + len(goals) < total else None
        return GoalListPage(
            project_id=self.project_id,
            total=total,
            offset=offset,
            limit=limit,
            goals=goals,
            next_offset=next_offset,
        )

    def goal_children(self, parent_goal_id: str) -> tuple[GoalSnapshot, ...]:
        """Return a bounded compatibility view of child snapshots."""

        self.store.get_goal(parent_goal_id, self.project_id)
        return tuple(
            self.goal_status(child.goal_id)
            for child in self.store.list_child_goals_compat(
                parent_goal_id, self.project_id
            )
        )

    def goal_children_page(
        self,
        parent_goal_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """Return compact direct-child cards without loading fact histories."""

        self.store.get_goal(parent_goal_id, self.project_id)
        total, goals = self.store.list_child_goal_page(
            parent_goal_id, self.project_id, offset, limit, statuses
        )
        next_offset = offset + len(goals) if offset + len(goals) < total else None
        return GoalListPage(
            project_id=self.project_id,
            total=total,
            offset=offset,
            limit=limit,
            goals=goals,
            next_offset=next_offset,
        )

    def sde_assess(
        self,
        goal_id: str,
        materiality: Materiality,
        rationale: str,
        fact_ids: tuple[str, ...],
    ) -> SDECandidate | None:
        """Return routine work directly or stage verified significant facts for review."""

        if materiality is Materiality.ROUTINE:
            return None
        if not fact_ids:
            raise EvidenceGateError("SDE assessment requires selected goal facts")
        if len(fact_ids) > MAX_SDE_SUPPORTING_FACTS:
            raise EvidenceGateError(
                "SDE assessment exceeds the supporting fact limit"
            )
        if len(fact_ids) != len(set(fact_ids)):
            raise EvidenceGateError("SDE assessment fact IDs must be unique")
        goal = self.store.get_goal(goal_id, self.project_id)
        selected = tuple(
            self.store.get_fact(fact_id, self.project_id) for fact_id in fact_ids
        )
        if any(fact.goal_id != goal_id for fact in selected):
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
            goal_id=goal_id,
            materiality=materiality,
            rationale=rationale,
            fact_ids=fact_ids,
        )
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
        stored, _inserted = self.store.add_sde_correction(record, self.project_id)
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
        stored, _inserted = self.store.add_sde_quality_feedback(
            feedback, self.project_id
        )
        return stored

    def sde_quality_feedback_summary(self) -> SDEQualityFeedbackSummary:
        """Return project-scoped aggregate reviewer label counts."""

        return self.store.sde_quality_feedback_summary(self.project_id)

    def sde_confirm(
        self,
        candidate_id: str,
        decision: ReviewDecision,
        artifacts: tuple[ArtifactRef, ...],
        *,
        artifact_inventory_complete: bool,
        rationale: str | None = None,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record an authorized human decision and begin receipt-gated cleanup."""

        reviewer_id = self.review_authorizer.authorize(
            self.project_id, candidate_id, decision, authenticated_subject
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        candidate = self.store.get_sde_candidate(candidate_id, self.project_id)
        receipt = AuditReceipt(
            candidate_id=candidate_id,
            decision=decision,
            facts_sha256=self.store.facts_digest(candidate.fact_ids, self.project_id),
            artifacts=artifacts,
            artifact_inventory_complete=artifact_inventory_complete,
            reviewer_id=reviewer_id,
            review_rationale=rationale,
        )
        # This commit is the deletion gate: no artifact is touched before it.
        durable_receipt = self.store.create_receipt(receipt, self.project_id)
        if (
            not durable_receipt.artifact_inventory_complete
            or not durable_receipt.canonical_persisted
        ):
            return durable_receipt
        return self._process_purge(durable_receipt.receipt_id)

    def artifact_inventory_complete(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Commit the complete staged-file manifest, then purge its exact files."""

        receipt = self.store.complete_artifact_inventory(
            receipt_id,
            artifacts,
            self.project_id,
            hold_created_by=authenticated_subject,
        )
        if not receipt.artifact_inventory_complete or not receipt.canonical_persisted:
            return receipt
        return self._process_purge(receipt_id)

    def release_artifact_hold(
        self,
        receipt_id: str,
        path: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Authorize and audit a hold release before retrying exact-file purge."""

        reviewer_id = self.review_authorizer.authorize_hold_release(
            self.project_id,
            receipt_id,
            path,
            rationale,
            authenticated_subject,
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        receipt = self.store.release_artifact_hold(
            receipt_id,
            path,
            self.project_id,
            reviewer_id,
            rationale,
        )
        if receipt.artifact_inventory_complete and receipt.canonical_persisted:
            return self._process_purge(receipt_id)
        return receipt

    def mark_canonical_persisted(
        self, receipt_id: str, target: str, sha256: str
    ) -> AuditReceipt:
        """Record the configured Markdown proof, then release the purge gate."""

        receipt = self.store.mark_receipt_canonical_persisted(
            receipt_id, target, sha256, self.project_id
        )
        if receipt.artifact_inventory_complete:
            return self._process_purge(receipt_id)
        return receipt

    def _process_purge(
        self, receipt_id: str, *, due_only: bool = False
    ) -> AuditReceipt:
        receipt = self.store.get_receipt(receipt_id, self.project_id)
        if not receipt.artifact_inventory_complete or not receipt.canonical_persisted:
            return receipt
        targets = self.store.get_purge_targets(
            receipt_id,
            pending_only=True,
            project_id=self.project_id,
            due_only=due_only,
        )
        for artifact, _, _, _ in targets:
            self.store.begin_purge_attempt(
                receipt_id, artifact.path, self.project_id
            )
            try:
                # The store's transactional selector permits only unheld or
                # explicitly released targets. Keep the immutable hold class
                # on the receipt, but pass a purgeable reference to the adapter.
                self.purger.purge(ArtifactRef(artifact.path, artifact.sha256))
            except (OSError, PurgeError, ValueError) as exc:
                if isinstance(exc, PurgeError):
                    error_code = exc.code.value
                elif isinstance(exc, OSError):
                    error_code = PurgeFailureCode.FILESYSTEM_ERROR.value
                else:
                    error_code = PurgeFailureCode.INVALID_ARTIFACT.value
                self.store.record_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.FAILED,
                    error_code,
                    self.project_id,
                )
            else:
                self.store.record_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.PURGED,
                    None,
                    self.project_id,
                )
        return self.store.get_receipt(receipt_id, self.project_id)

    def artifact_purge_status(
        self, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Report receipt and per-artifact purge state without masking failures."""

        receipt = self.store.get_receipt(receipt_id, self.project_id)
        now = datetime.now(UTC)
        targets = tuple(
            PurgeTargetStatus(
                artifact=item.artifact,
                status=item.status,
                attempts=item.attempts,
                error=item.error,
                created_at=item.created_at,
                last_attempt_at=item.last_attempt_at,
                next_attempt_at=item.next_attempt_at,
                next_attempt_in_seconds=_timestamp_delay_seconds(
                    item.next_attempt_at, now
                ),
                age_seconds=_timestamp_age_seconds(item.created_at, now),
                last_attempt_age_seconds=(
                    _timestamp_age_seconds(item.last_attempt_at, now)
                    if item.last_attempt_at is not None
                    else None
                ),
                safe_recovery_action=_purge_recovery_action(receipt, item.status),
                hold_created_at=item.hold_created_at,
                hold_created_by=item.hold_created_by,
                hold_released_at=item.hold_released_at,
                hold_released_by=item.hold_released_by,
                hold_release_rationale=item.hold_release_rationale,
            )
            for item in self.store.get_purge_target_records(
                receipt_id, project_id=self.project_id
            )
        )
        return receipt, targets

    def retry_pending_purges(self) -> tuple[AuditReceipt, ...]:
        """Explicitly retry all eligible manifests now, overriding backoff."""

        refreshed: list[AuditReceipt] = []
        for receipt in self.store.pending_receipts(self.project_id):
            if receipt.artifact_inventory_complete and receipt.canonical_persisted:
                refreshed.append(self._process_purge(receipt.receipt_id))
            else:
                refreshed.append(receipt)
        return tuple(refreshed)

    def retry_due_purges(self, limit: int = 100) -> tuple[AuditReceipt, ...]:
        """Process a bounded batch of reviewed purge targets whose backoff elapsed.

        This is an internal scheduler-facing operation. Human-authorized
        ``retry_pending_purges`` remains an immediate override.
        """

        if not is_exact_int(limit) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        refreshed: list[AuditReceipt] = []
        for receipt in self.store.due_pending_purge_receipts(
            self.project_id, limit
        ):
            refreshed.append(self._process_purge(receipt.receipt_id, due_only=True))
        return tuple(refreshed)

    def _claim_event(
        self, event: EventEnvelope, lease_owner: str | None
    ) -> EventInboxReceipt | None:
        """Claim an accepted event, returning its receipt when it needs no work."""

        # Keep this transaction short; evidence adapters may perform source I/O.
        with self.store.transaction():
            accepted, _inserted = self.store.ingest_event(event)
            if accepted.status is EventInboxStatus.PROCESSED:
                return accepted
            if accepted.status is EventInboxStatus.FAILED and accepted.next_attempt_at:
                if not self._event_retry_is_due(accepted.next_attempt_at):
                    return accepted
            self.store.assert_event_claim(self.project_id, event.event_id, lease_owner)
        return None

    @staticmethod
    def _event_retry_is_due(next_attempt_at: str) -> bool:
        """Fail closed when a failed event's retry timestamp is invalid or future."""

        try:
            retry_time = datetime.fromisoformat(next_attempt_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return retry_time.tzinfo is not None and retry_time <= datetime.now(UTC)

    def _prepare_event(self, event: EventEnvelope) -> _PreparedEvent:
        """Gather snapshots and independently attest evidence outside write locks."""

        payload = event.payload
        prior_fact_ids: frozenset[str] = (
            frozenset(
                fact.fact_id
                for fact in self.store.list_facts(payload.goal_id, self.project_id)
            )
            if not isinstance(payload, GoalStarted)
            else frozenset()
        )
        prepared = _PreparedEvent(prior_fact_ids=prior_fact_ids)
        if isinstance(payload, FactRecorded) and payload.kind is FactKind.VERIFICATION:
            return self._prepare_verified_fact(payload, prepared)
        if isinstance(payload, GoalFinishRequested):
            return self._prepare_goal_finish(payload, prepared)
        return prepared

    def _prepare_verified_fact(
        self, payload: FactRecorded, prepared: _PreparedEvent
    ) -> _PreparedEvent:
        goal = self.store.get_goal(payload.goal_id, self.project_id)
        criterion_ids = {item.criterion_id for item in goal.success_criteria}
        if payload.criterion_id is None or payload.criterion_id not in criterion_ids:
            raise ValueError("verification must reference a current criterion")
        attestations = self._attest_evidence(goal, payload.criterion_id, payload.evidence)
        if (
            not payload.evidence
            or any(item.outcome is not EvidenceOutcome.PASSED for item in payload.evidence)
            or len(attestations) != len(payload.evidence)
        ):
            raise EvidenceGateError(
                "verification requires independently verified passing evidence"
            )
        fact = Fact(
            goal_id=payload.goal_id,
            kind=payload.kind,
            bullet=payload.bullet,
            fact_id=payload.fact_id,
            criterion_id=payload.criterion_id,
            evidence=payload.evidence,
            verification_attestations=attestations,
        )
        return _PreparedEvent(
            prior_fact_ids=prepared.prior_fact_ids,
            verified_goal_snapshot=goal,
            prepared_fact=fact,
        )

    def _prepare_goal_finish(
        self, payload: GoalFinishRequested, prepared: _PreparedEvent
    ) -> _PreparedEvent:
        goal = self.store.get_goal(payload.goal_id, self.project_id)
        expected_revision = (
            goal.lifecycle_revision
            if payload.expected_lifecycle_revision is None
            else payload.expected_lifecycle_revision
        )
        if goal.lifecycle_revision != expected_revision:
            raise ConflictError("goal lifecycle revision changed; reload before finishing")
        facts = self.store.list_facts(payload.goal_id, self.project_id)
        verified_criteria = self._verified_criterion_ids(goal, facts)
        return _PreparedEvent(
            prior_fact_ids=prepared.prior_fact_ids,
            finish_snapshot=(goal, facts, verified_criteria),
            expected_finish_revision=expected_revision,
        )

    def _apply_event_payload(
        self, payload: EventPayload, prepared: _PreparedEvent, event_id: str
    ) -> EventDisposition:
        """Apply one typed event payload inside the caller's transaction."""

        if isinstance(payload, GoalStarted):
            self.goal_start(
                payload.problem,
                payload.success_criteria,
                owner=payload.owner,
                checklist_id=payload.checklist_id,
                checklist_version=payload.checklist_version,
                checklist_source_text=payload.checklist_source_text,
                parent_goal_id=payload.parent_goal_id,
                depends_on_goal_ids=payload.depends_on_goal_ids,
                goal_id=payload.goal_id,
                initial_status=payload.initial_status,
                next_action=payload.next_action,
                source_event_id=event_id,
            )
        elif isinstance(payload, GoalActivated):
            self.goal_activate(
                payload.goal_id, payload.reason, payload.expected_lifecycle_revision
            )
        elif isinstance(payload, FactRecorded):
            self._apply_fact_recorded(payload, prepared)
        elif isinstance(payload, GoalActivityObserved):
            return self._apply_activity_observed(payload)
        elif isinstance(payload, GoalFinishRequested):
            self._apply_goal_finish(payload, prepared)
        else:
            self._apply_goal_status_event(payload)
        return EventDisposition.APPLIED

    def _apply_fact_recorded(
        self, payload: FactRecorded, prepared: _PreparedEvent
    ) -> None:
        if prepared.prepared_fact is None:
            self.goal_fact(
                payload.goal_id,
                payload.kind,
                payload.bullet,
                criterion_id=payload.criterion_id,
                evidence=payload.evidence,
                fact_id=payload.fact_id,
            )
            return
        if prepared.verified_goal_snapshot is None:
            raise ConflictError("verified fact lost its goal snapshot before commit")
        self._append_preverified_fact(prepared.prepared_fact, prepared.verified_goal_snapshot)

    def _apply_activity_observed(
        self, payload: GoalActivityObserved
    ) -> EventDisposition:
        goal = self.store.get_goal(payload.goal_id, self.project_id)
        if goal.status is not GoalStatus.ACTIVE:
            return EventDisposition.SUPPRESSED_NONACTIVE_GOAL
        self._append_preverified_fact(
            Fact(
                goal_id=payload.goal_id,
                kind=payload.kind,
                bullet=payload.bullet,
                fact_id=payload.fact_id,
            )
        )
        return EventDisposition.APPLIED

    def _apply_goal_finish(
        self, payload: GoalFinishRequested, prepared: _PreparedEvent
    ) -> None:
        if prepared.finish_snapshot is None:
            raise ConflictError("finish evidence snapshot is unavailable before commit")
        goal, facts, verified_criteria = prepared.finish_snapshot
        current_goal = self.store.get_goal(payload.goal_id, self.project_id)
        current_facts = self.store.list_facts(payload.goal_id, self.project_id)
        if (
            current_goal.lifecycle_revision != goal.lifecycle_revision
            or current_goal.criteria_revision != goal.criteria_revision
            or tuple(fact.fact_id for fact in current_facts)
            != tuple(fact.fact_id for fact in facts)
        ):
            raise ConflictError("goal or facts changed during evidence verification; retry finish")
        self._goal_finish_in_transaction(
            payload.goal_id,
            payload.completion_claim,
            prepared.expected_finish_revision,
            verified_criteria,
        )

    def _apply_goal_status_event(self, payload: EventPayload) -> None:
        if isinstance(payload, GoalDeferred):
            self.goal_defer(
                payload.goal_id,
                payload.reason,
                payload.next_action,
                payload.expected_lifecycle_revision or 1,
            )
        elif isinstance(payload, GoalReopened):
            self.goal_reopen(
                payload.goal_id,
                payload.reason,
                payload.next_action,
                payload.expected_lifecycle_revision or 1,
            )
        elif isinstance(payload, GoalCriteriaAmended):
            self.goal_amend_criteria(
                payload.goal_id,
                payload.expected_revision,
                payload.success_criteria,
                payload.reason,
                payload.next_action,
                payload.expected_lifecycle_revision or 1,
            )
        elif isinstance(payload, GoalCancelled):
            self.goal_cancel(payload.goal_id, payload.reason)
        elif isinstance(payload, GoalSuperseded):
            self.goal_supersede(
                payload.goal_id, payload.replacement_goal_id, payload.reason
            )
        elif isinstance(payload, GoalBlocked):
            self.goal_block(
                payload.goal_id,
                payload.dependency,
                payload.recovery,
                payload.expected_lifecycle_revision or 1,
            )
        else:
            raise TypeError(f"unsupported event payload: {type(payload).__name__}")

    def _attach_event_facts(
        self,
        payload: EventPayload,
        prepared: _PreparedEvent,
        event_id: str,
        disposition: EventDisposition,
    ) -> None:
        new_fact_ids = tuple(
            fact.fact_id
            for fact in self.store.list_facts(payload.goal_id, self.project_id)
            if fact.fact_id not in prepared.prior_fact_ids
        )
        if isinstance(payload, (FactRecorded, GoalActivityObserved)) and (
            disposition is EventDisposition.APPLIED
        ):
            try:
                referenced_fact = self.store.get_fact(payload.fact_id, self.project_id)
            except LookupError:
                pass
            else:
                if referenced_fact.source_event_id is None:
                    new_fact_ids += (referenced_fact.fact_id,)
        self.store.attach_fact_source_event(
            tuple(dict.fromkeys(new_fact_ids)), event_id, self.project_id
        )

    def _commit_event(
        self, event: EventEnvelope, prepared: _PreparedEvent, lease_owner: str | None
    ) -> EventInboxReceipt:
        with self.store.transaction():
            current_receipt = self.store.event_receipt(self.project_id, event.event_id)
            if current_receipt.status is EventInboxStatus.PROCESSED:
                return current_receipt
            self.store.assert_event_claim(self.project_id, event.event_id, lease_owner)
            disposition = self._apply_event_payload(
                event.payload, prepared, event.event_id
            )
            self._attach_event_facts(event.payload, prepared, event.event_id, disposition)
            self.store.advance_source_sequence(event)
            return self.store.mark_event_processed(
                self.project_id,
                event.event_id,
                lease_owner=lease_owner,
                disposition=disposition,
            )

    def _mark_event_failure(
        self, event: EventEnvelope, exc: Exception, lease_owner: str | None
    ) -> EventInboxReceipt:
        if isinstance(exc, (EventClaimError, EventInboxCapacityError)):
            raise exc
        # Persist only a bounded exception type code; payload details can be private.
        error_code = safe_exception_label(exc)
        with self.store.transaction():
            accepted, _inserted = self.store.ingest_event(event)
            if accepted.status is EventInboxStatus.PROCESSED:
                return accepted
            return self.store.mark_event_failed(
                self.project_id,
                event.event_id,
                error_code,
                discard_payload=isinstance(exc, FactCapacityError),
                lease_owner=lease_owner,
            )

    def process_event(
        self, event: EventEnvelope, *, lease_owner: str | None = None
    ) -> EventInboxReceipt:
        """Apply one event and its inbox receipt atomically within this project.

        The service must be created from an independently authorized project
        binding. The envelope's project ID is routing context, not caller
        authentication.
        """

        if event.project_id != self.project_id:
            raise PermissionError("event project does not match authorized service scope")
        try:
            accepted = self._claim_event(event, lease_owner)
            if accepted is not None:
                return accepted
            return self._commit_event(event, self._prepare_event(event), lease_owner)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Failed mutations roll back with the processing receipt; retry state is
            # saved separately so transport retries remain idempotent.
            return self._mark_event_failure(event, exc, lease_owner)
