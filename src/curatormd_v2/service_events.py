"""Process versioned event envelopes and durable retries."""

from __future__ import annotations

__all__ = (
    "_EventMixin",
)

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import (
    UTC,
    datetime,
)
from .models import (
    EvidenceOutcome,
    Fact,
    FactKind,
    GoalStatus,
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
from .errors import safe_exception_label
from .store import (
    ConflictError,
    EventClaimError,
    EventInboxCapacityError,
)

from .service_types import (
    EvidenceGateError,
    _PreparedEvent,
)
from .service_purge import _PurgeMixin


class _EventMixin(_PurgeMixin):  # pylint: disable=too-few-public-methods  # Internal mixin boundary.
    """Process versioned event envelopes and durable retries."""

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
        verified_criteria = self._verified_criterion_attestations(goal, facts)
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
                replace(
                    payload,
                    expected_lifecycle_revision=(
                        payload.expected_lifecycle_revision or 1
                    ),
                )
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
                lease_owner=lease_owner,
            )

    def process_event(
        self,
        event: EventEnvelope,
        *,
        lease_owner: str | None = None,
        effect_fence: Callable[[], AbstractContextManager[object]] | None = None,
        override_project_fence: bool = False,
    ) -> EventInboxReceipt:
        """Apply one event and its inbox receipt atomically within this project.

        The service must be created from an independently authorized project
        binding. The envelope's project ID is routing context, not caller
        authentication.
        """

        if event.project_id != self.project_id:
            raise PermissionError("event project does not match authorized service scope")
        expected_effect_revision = (
            None if override_project_fence else self._capture_effect_revision()
        )

        def guard() -> AbstractContextManager[object]:
            return self._effect_guard(expected_effect_revision, effect_fence)

        try:
            with guard():
                accepted = self._claim_event(event, lease_owner)
            if accepted is not None:
                return accepted
            prepared = self._prepare_event(event)
            with guard():
                return self._commit_event(event, prepared, lease_owner)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Failed mutations roll back with the processing receipt; retry state is
            # saved separately so transport retries remain idempotent.
            with guard():
                return self._mark_event_failure(event, exc, lease_owner)
