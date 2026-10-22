"""Durable SQLite event consumer with bounded retries and quarantine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import uuid4

from .errors import safe_exception_label
from .events import EventEnvelope, EventInboxReceipt, EventQueueStatus, EventInboxStatus
from .service import CuratorService
from .store import CuratorStore, EventClaimError


DEFAULT_MAX_DELIVERY_ATTEMPTS = 5
MAX_ROUTER_BATCH = 1000
MAX_ROUTER_PROJECTS = 128


@dataclass(frozen=True, slots=True)
class EventRoutingResult:
    """Content-free result of one bounded durable queue pass."""

    attempted_count: int
    processed_count: int
    failed_count: int
    quarantined_count: int
    claim_lost_count: int
    queue: EventQueueStatus


@dataclass(frozen=True, slots=True)
class _EventRouteOutcome:
    """Content-free counters for one claimed event attempt."""

    processed_count: int = 0
    failed_count: int = 0
    quarantined_count: int = 0
    claim_lost_count: int = 0
    stop_batch: bool = False


class DurableEventRouter:
    """Consume stored events through trusted, project-bound service instances.

    The host must build the project-to-service map from authenticated profile
    bindings. Event project IDs are used only to select that fixed map entry;
    they never create or authorize a service.
    """

    # pylint: disable=too-few-public-methods  # The router exposes one bounded pass operation.

    def __init__(
        self,
        store: CuratorStore,
        project_services: Mapping[str, CuratorService],
        *,
        max_delivery_attempts: int = DEFAULT_MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        if not 1 <= max_delivery_attempts <= 100:
            raise ValueError("max_delivery_attempts must be between 1 and 100")
        if not project_services:
            raise ValueError("router requires at least one trusted project binding")
        if len(project_services) > MAX_ROUTER_PROJECTS:
            raise ValueError("router accepts at most 128 trusted project bindings")
        for project_id, service in project_services.items():
            if service.project_id != project_id:
                raise ValueError("router key must match the bound service project")
        self.store = store
        self.project_services = dict(project_services)
        self.max_delivery_attempts = max_delivery_attempts

    def route_once(self, limit: int = 100) -> EventRoutingResult:
        """Attempt a bounded set of eligible events, preserving failed payloads."""

        if not 1 <= limit <= MAX_ROUTER_BATCH:
            raise ValueError(f"limit must be between 1 and {MAX_ROUTER_BATCH}")
        lease_owner = f"router-{uuid4().hex}"
        events = self.store.claim_pending_events(
            lease_owner,
            limit=limit,
            project_ids=tuple(sorted(self.project_services)),
        )
        attempted = processed = failed = quarantined = claim_lost = 0
        for event in events:
            attempted += 1
            outcome = self._route_claimed_event(event, lease_owner)
            processed += outcome.processed_count
            failed += outcome.failed_count
            quarantined += outcome.quarantined_count
            claim_lost += outcome.claim_lost_count
            if outcome.stop_batch:
                break
        self.store.release_event_claims(lease_owner)
        self.store.retry_pending_event_payload_scrubs()
        return EventRoutingResult(
            attempted_count=attempted,
            processed_count=processed,
            failed_count=failed,
            quarantined_count=quarantined,
            claim_lost_count=claim_lost,
            queue=self.store.event_queue_status(),
        )

    def _route_claimed_event(
        self, event: EventEnvelope, lease_owner: str
    ) -> _EventRouteOutcome:
        """Dispatch one claimed event, then classify its durable receipt."""

        service = self.project_services.get(event.project_id)
        if service is None:
            receipt = self.store.mark_event_failed(
                event.project_id,
                event.event_id,
                "project_binding_missing",
                lease_owner=lease_owner,
            )
            return self._classify_receipt(receipt)
        try:
            receipt = service.process_event(event, lease_owner=lease_owner)
        except EventClaimError:
            return _EventRouteOutcome(claim_lost_count=1)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            receipt, stop_batch = self._recover_dispatch_failure(
                event, lease_owner, exc
            )
            if stop_batch or receipt is None:
                return _EventRouteOutcome(failed_count=1, stop_batch=True)
        return self._classify_receipt(receipt)

    def _recover_dispatch_failure(
        self, event: EventEnvelope, lease_owner: str, error: Exception
    ) -> tuple[EventInboxReceipt | None, bool]:
        """Recover or preserve a dispatch failure without exposing its details."""

        code = safe_exception_label(error)
        try:
            current = self.store.event_receipt(event.project_id, event.event_id)
        except Exception:  # pylint: disable=broad-exception-caught
            current = None
        if current is None:
            return None, True
        if current.status in {
            EventInboxStatus.PROCESSED,
            EventInboxStatus.QUARANTINED,
        }:
            return current, False
        try:
            failed = self.store.mark_event_failed(
                event.project_id,
                event.event_id,
                code or "router_error",
                lease_owner=lease_owner,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return None, True
        return failed, False

    def _classify_receipt(self, receipt: EventInboxReceipt) -> _EventRouteOutcome:
        """Count one persisted result and quarantine only at its retry ceiling."""

        if receipt.status is EventInboxStatus.FAILED:
            if receipt.attempts >= self.max_delivery_attempts:
                try:
                    receipt = self.store.quarantine_event(
                        receipt.project_id,
                        receipt.event_id,
                        self.max_delivery_attempts,
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    return _EventRouteOutcome(failed_count=1)
            if receipt.status is EventInboxStatus.QUARANTINED:
                return _EventRouteOutcome(quarantined_count=1)
            return _EventRouteOutcome(failed_count=1)
        if receipt.status is EventInboxStatus.PROCESSED:
            return _EventRouteOutcome(processed_count=1)
        return _EventRouteOutcome()
