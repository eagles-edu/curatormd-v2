"""Manage goal lifecycle and current evidence."""

from __future__ import annotations

__all__ = (
    "_GoalLifecycleMixin",
)

from datetime import (
    UTC,
    datetime,
)
from typing import Unpack
from .models import (
    CriterionProgress,
    CriterionStatus,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    Fact,
    FactKind,
    GoalCard,
    GoalSnapshot,
    GoalStatus,
    MAX_CRITERIA_REVISIONS,
    MAX_GOAL_STATUS_CANDIDATES,
    MAX_GOAL_STATUS_PURGE_RECEIPTS,
    MAX_SUCCESS_CRITERIA,
    SuccessCriterion,
    new_id,
)
from .events import GoalCriteriaAmended
from .evidence import (
    EvidenceAdapterError,
    EvidenceVerificationContext,
    evidence_current_attestations,
)
from .record_validation import parse_optional_aware_timestamp
from .reporting import open_child_goals
from .store import ConflictError
from .store_requests import (
    GoalCriteriaAmendmentRequest,
    GoalCriteriaRevisionExpectation,
    GoalRetirementRequest,
    GoalTransitionRequest,
)
from .validation import is_exact_int

from .service_types import (
    EvidenceGateError,
    _GoalFactOptions,
    _GoalStartOptions,
    _attestation_lease_end,
)
from .service_state import _CuratorServiceState


class _GoalLifecycleMixin(_CuratorServiceState):
    """Manage goal lifecycle and current evidence."""

    def _validate_goal_start_relations(
        self,
        parent_goal_id: str | None,
        depends_on_goal_ids: tuple[str, ...],
        goal_id: str | None,
    ) -> None:
        """Reject invalid parent/dependency links inside the intake transaction."""

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

    @staticmethod
    def _normalize_goal_start_status(initial_status: GoalStatus) -> GoalStatus:
        """Accept only the two valid states for a newly captured goal."""

        parse_failed = False
        normalized_status: GoalStatus | None = None
        try:
            normalized_status = GoalStatus(initial_status)
        except ValueError:
            parse_failed = True
        if parse_failed or normalized_status is None:
            raise ValueError("initial_status must be planned or active")
        if normalized_status not in {GoalStatus.PLANNED, GoalStatus.ACTIVE}:
            raise ValueError("initial_status must be planned or active")
        return normalized_status

    def goal_start(
        self,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        **options: Unpack[_GoalStartOptions],
    ) -> GoalCard:
        """Create a goal with an explicit problem and testable success criteria."""

        if options.keys() - _GoalStartOptions.__annotations__.keys():
            raise TypeError("goal_start received an unsupported option")
        expected_effect_revision = self._capture_effect_revision()
        initial_status = self._normalize_goal_start_status(
            options.get("initial_status", GoalStatus.ACTIVE)
        )
        with self._effect_fence(expected_effect_revision):
            with self.store.transaction():
                self._validate_goal_start_relations(
                    options.get("parent_goal_id"),
                    options.get("depends_on_goal_ids", ()),
                    options.get("goal_id"),
                )
                goal = GoalCard(
                    goal_id=options.get("goal_id") or new_id(),
                    problem=problem,
                    success_criteria=success_criteria,
                    owner=options.get("owner"),
                    checklist_id=options.get("checklist_id"),
                    checklist_version=options.get("checklist_version"),
                    checklist_source_text=options.get("checklist_source_text"),
                    parent_goal_id=options.get("parent_goal_id"),
                    depends_on_goal_ids=options.get("depends_on_goal_ids", ()),
                    project_id=self.project_id,
                    status=initial_status,
                    next_action=options.get("next_action"),
                )
                self.store.add_goal(goal, source_event_id=options.get("source_event_id"))
                return goal

    def goal_activate(
        self,
        goal_id: str,
        reason: str,
        expected_lifecycle_revision: int,
    ) -> GoalCard:
        """Activate planned work after explicit, revision-checked acceptance."""

        expected_effect_revision = self._capture_effect_revision()
        reason = reason.strip()
        if not reason or len(reason) > 500 or "\n" in reason or "\r" in reason:
            raise ValueError("activation requires a single-line reason of at most 500 characters")
        fact = Fact(goal_id=goal_id, kind=FactKind.INTENT, bullet=f"Activated: {reason}")
        with self._effect_fence(expected_effect_revision):
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
        **options: Unpack[_GoalFactOptions],
    ) -> tuple[Fact, bool]:
        """Record a compact fact, independently verifying proof-bearing facts."""

        if options.keys() - _GoalFactOptions.__annotations__.keys():
            raise TypeError("goal_fact received an unsupported option")
        criterion_id = options.get("criterion_id")
        evidence = options.get("evidence", ())
        fact_id = options.get("fact_id")
        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
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

        return self._current_fact_attestations(goal, fact) is not None

    def _current_fact_attestations(
        self, goal: GoalCard, fact: Fact
    ) -> tuple[EvidenceAttestation, ...] | None:
        """Return matching current attestations without discarding their lease."""

        if fact.kind is not FactKind.VERIFICATION or fact.criterion_id is None:
            return None
        if any(item.outcome is not EvidenceOutcome.PASSED for item in fact.evidence):
            return None
        return evidence_current_attestations(
            self.evidence_verifier,
            EvidenceVerificationContext(
                project_id=self.project_id,
                goal_id=goal.goal_id,
                criterion_id=fact.criterion_id,
                now=datetime.now(UTC),
            ),
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

    def _verified_criterion_attestations(
        self, goal: GoalCard, facts: tuple[Fact, ...]
    ) -> dict[str, tuple[EvidenceAttestation, ...]]:
        """Keep the freshest external source lease for each verified criterion."""

        cutoff = self._evidence_epoch_cutoff(facts)
        verified: dict[str, tuple[EvidenceAttestation, ...]] = {}
        for fact in facts:
            criterion_id = fact.criterion_id
            if (
                fact.kind is not FactKind.VERIFICATION
                or criterion_id is None
                or (cutoff is not None and fact.created_at <= cutoff)
            ):
                continue
            current = self._current_fact_attestations(goal, fact)
            if current is None:
                continue
            previous = verified.get(criterion_id)
            if previous is None or _attestation_lease_end(current) > _attestation_lease_end(
                previous
            ):
                verified[criterion_id] = current
        return verified

    @staticmethod
    def _criteria_with_unexpired_attestations(
        verified_attestations: dict[str, tuple[EvidenceAttestation, ...]],
        now: datetime,
    ) -> set[str]:
        """Drop pre-verified criteria whose receipts expired before commit."""

        now_utc = now.astimezone(UTC)
        return {
            criterion_id
            for criterion_id, attestations in verified_attestations.items()
            if attestations
            and all(
                (valid_until := parse_optional_aware_timestamp(item.valid_until))
                is not None
                and valid_until > now_utc
                for item in attestations
            )
        }

    def goal_finish(
        self,
        goal_id: str,
        completion_claim: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Request completion; missing proof or dependent work leaves the goal open."""
        expected_effect_revision = self._capture_effect_revision()
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
            verified = self._verified_criterion_attestations(initial_goal, facts_snapshot)
            with self._effect_fence(expected_effect_revision):
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

    @staticmethod
    def _goal_finish_open_gate_payload(
        goal_id: str,
        missing: tuple[SuccessCriterion, ...],
        open_children: tuple[GoalCard, ...],
        blocked_dependencies: tuple[GoalCard, ...],
    ) -> tuple[str, tuple[Fact, ...]]:
        """Build the bounded next action and exact facts for an open outcome."""

        reasons: list[str] = []
        facts: list[Fact] = []
        if missing:
            descriptions = "; ".join(item.description for item in missing)
            reasons.append(f"Verify unmet success criteria: {descriptions}")
            facts.extend(
                Fact(
                    goal_id=goal_id,
                    kind=FactKind.OPEN_GATE,
                    bullet=(
                        f"Open: success criterion '{criterion.description}' "
                        "lacks passing evidence"
                    ),
                    criterion_id=criterion.criterion_id,
                )
                for criterion in missing
            )
        if open_children:
            child_ids = ", ".join(child.goal_id for child in open_children)
            reasons.append(f"Finish open child goals: {child_ids}")
            facts.extend(
                Fact(
                    goal_id=goal_id,
                    kind=FactKind.OPEN_GATE,
                    bullet=(
                        f"Open: child goal '{child.goal_id}' remains "
                        f"{child.status.value}"
                    ),
                )
                for child in open_children
            )
        if blocked_dependencies:
            dependency_ids = ", ".join(
                dependency.goal_id for dependency in blocked_dependencies
            )
            reasons.append(f"Complete dependencies first: {dependency_ids}")
            facts.extend(
                Fact(
                    goal_id=goal_id,
                    kind=FactKind.OPEN_GATE,
                    bullet=(
                        f"Open: dependency '{dependency.goal_id}' remains "
                        f"{dependency.status.value}"
                    ),
                )
                for dependency in blocked_dependencies
            )
        return "; ".join(reasons)[:1000], tuple(facts)

    def _goal_finish_in_transaction(
        self,
        goal_id: str,
        completion_claim: str,
        expected_lifecycle_revision: int | None = None,
        verified_criterion_attestations: (
            dict[str, tuple[EvidenceAttestation, ...]] | None
        ) = None,
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
        open_children = open_child_goals(
            self.store.list_child_goals(goal_id, self.project_id)
        )
        blocked_dependencies = tuple(
            dependency
            for dependency_id in goal.depends_on_goal_ids
            if (dependency := self.store.get_goal(dependency_id, self.project_id)).status
            is not GoalStatus.COMPLETE
        )
        # External verification is performed before the write transaction. Recheck
        # its bounded local lease after transaction reads, immediately before the
        # completion decision and transition.
        verified = self._criteria_with_unexpired_attestations(
            verified_criterion_attestations or {},
            datetime.now(UTC),
        )
        missing = tuple(
            criterion
            for criterion in goal.success_criteria
            if criterion.criterion_id not in verified
        )
        if missing or open_children or blocked_dependencies:
            next_action, open_gate_facts = self._goal_finish_open_gate_payload(
                goal_id, missing, open_children, blocked_dependencies
            )
            facts.extend(open_gate_facts)
            facts.append(
                Fact(
                    goal_id=goal_id,
                    kind=FactKind.OUTCOME,
                    bullet="open",
                )
            )
            return self.store.transition_goal(
                GoalTransitionRequest(
                    goal_id=goal_id,
                    status=GoalStatus.OPEN,
                    next_action=next_action,
                    facts=tuple(facts),
                    expected_lifecycle_revision=expected_revision,
                    project_id=self.project_id,
                )
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
            GoalTransitionRequest(
                goal_id=goal_id,
                status=GoalStatus.COMPLETE,
                next_action=None,
                facts=tuple(facts),
                expected_lifecycle_revision=expected_revision,
                project_id=self.project_id,
            )
        )

    def goal_defer(
        self,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Defer unfinished work with a concrete reason and resumption action."""

        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
            return self.store.transition_goal(
                GoalTransitionRequest(
                    goal_id=goal_id,
                    status=GoalStatus.DEFERRED,
                    next_action=next_action.strip(),
                    facts=(fact,),
                    expected_lifecycle_revision=expected_revision,
                    project_id=self.project_id,
                )
            )

    def goal_block(
        self,
        goal_id: str,
        dependency: str,
        recovery: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Record an external dependency and recovery path for blocked work."""

        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
            return self.store.transition_goal(
                GoalTransitionRequest(
                    goal_id=goal_id,
                    status=GoalStatus.BLOCKED,
                    next_action=recovery.strip(),
                    facts=(fact,),
                    expected_lifecycle_revision=expected_revision,
                    project_id=self.project_id,
                )
            )

    def goal_cancel(self, goal_id: str, reason: str) -> GoalCard:
        """Cancel unfinished work without treating it as successful."""

        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
            return self.store.retire_goal(
                GoalRetirementRequest(
                    goal_id=goal_id,
                    status=GoalStatus.CANCELLED,
                    reason=reason,
                    fact=fact,
                    project_id=self.project_id,
                )
            )

    def goal_supersede(
        self, goal_id: str, replacement_goal_id: str, reason: str
    ) -> GoalCard:
        """Replace unfinished work with an explicit same-project goal."""

        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
            return self.store.retire_goal(
                GoalRetirementRequest(
                    goal_id=goal_id,
                    status=GoalStatus.SUPERSEDED,
                    reason=reason,
                    fact=fact,
                    project_id=self.project_id,
                    replacement_goal_id=replacement_goal_id,
                )
            )

    def goal_reopen(
        self,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Reopen a completed goal and require fresh evidence for every criterion."""

        expected_effect_revision = self._capture_effect_revision()
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
        with self._effect_fence(expected_effect_revision):
            return self.store.reopen_goal(
                goal_id,
                next_action,
                fact,
                expected_revision,
                self.project_id,
            )

    def goal_amend_criteria(
        self,
        request: GoalCriteriaAmended,
    ) -> GoalCard:
        """Explicitly amend an open goal and require fresh proof afterward."""

        expected_effect_revision = self._capture_effect_revision()
        goal_id = request.goal_id
        expected_revision = request.expected_revision
        success_criteria = request.success_criteria
        reason = request.reason.strip()
        next_action = request.next_action.strip()
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
            if request.expected_lifecycle_revision is None
            else request.expected_lifecycle_revision
        )
        with self._effect_fence(expected_effect_revision):
            return self.store.amend_goal_criteria(
                GoalCriteriaAmendmentRequest(
                    goal_id=goal_id,
                    expected_revisions=GoalCriteriaRevisionExpectation(
                        criteria_revision=expected_revision,
                        lifecycle_revision=expected_state_revision,
                    ),
                    criteria=success_criteria,
                    reason=reason,
                    next_action=next_action,
                    fact=fact,
                    project_id=self.project_id,
                ),
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
