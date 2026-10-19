"""Durable SQLite event consumer with bounded retries and quarantine."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping
from uuid import uuid4

from .events import EventQueueStatus, EventInboxStatus
from .service import CuratorService
from .store import CuratorStore, EventClaimError


DEFAULT_MAX_DELIVERY_ATTEMPTS = 5
MAX_ROUTER_BATCH = 1000
_ERROR_CODE_RE = re.compile(r"[^a-zA-Z0-9_.:-]")


@dataclass(frozen=True, slots=True)
class EventRoutingResult:
    """Content-free result of one bounded durable queue pass."""

    attempted_count: int
    processed_count: int
    failed_count: int
    quarantined_count: int
    claim_lost_count: int
    queue: EventQueueStatus


class DurableEventRouter:
    """Consume stored events through trusted, project-bound service instances.

    The host must build the project-to-service map from authenticated profile
    bindings. Event project IDs are used only to select that fixed map entry;
    they never create or authorize a service.
    """

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
        events = self.store.claim_pending_events(lease_owner, limit=limit)
        attempted = 0
        processed = 0
        failed = 0
        quarantined = 0
        claim_lost = 0
        for event in events:
            attempted += 1
            service = self.project_services.get(event.project_id)
            if service is None:
                receipt = self.store.mark_event_failed(
                    event.project_id,
                    event.event_id,
                    "project_binding_missing",
                    lease_owner=lease_owner,
                )
            else:
                try:
                    receipt = service.process_event(event, lease_owner=lease_owner)
                except EventClaimError:
                    claim_lost += 1
                    continue
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    code = _ERROR_CODE_RE.sub("_", type(exc).__name__)[:128]
                    try:
                        current = self.store.event_receipt(
                            event.project_id, event.event_id
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        current = None
                    if current is None:
                        # Preserve the durable receipt and stop this pass if
                        # storage cannot report the failed dispatch state.
                        failed += 1
                        break
                    if current.status is EventInboxStatus.PROCESSED:
                        receipt = current
                    elif current.status is EventInboxStatus.QUARANTINED:
                        receipt = current
                    else:
                        try:
                            receipt = self.store.mark_event_failed(
                                event.project_id,
                                event.event_id,
                                code or "router_error",
                                lease_owner=lease_owner,
                            )
                        except Exception:  # pylint: disable=broad-exception-caught
                            # A later pass can recover once SQLite is healthy.
                            failed += 1
                            break
            if receipt.status is EventInboxStatus.FAILED:
                if receipt.attempts >= self.max_delivery_attempts:
                    try:
                        receipt = self.store.quarantine_event(
                            event.project_id,
                            event.event_id,
                            self.max_delivery_attempts,
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        failed += 1
                        continue
                if receipt.status is EventInboxStatus.QUARANTINED:
                    quarantined += 1
                else:
                    failed += 1
            elif receipt.status is EventInboxStatus.PROCESSED:
                processed += 1
        self.store.release_event_claims(lease_owner)
        return EventRoutingResult(
            attempted_count=attempted,
            processed_count=processed,
            failed_count=failed,
            quarantined_count=quarantined,
            claim_lost_count=claim_lost,
            queue=self.store.event_queue_status(),
        )
