"""Reusable assertions for Curator V2 project-plugin contract tests.

Consumer repositories can import this module from the installed backend and
run the same producer/backend contract against their plugin adapter. It does
not create fixtures, access a database directly, or perform deployment work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    GoalStarted,
)
from .models import GoalSnapshot, ProjectStorageUsage


class ProjectPluginContractAdapter(Protocol):
    """Public operations required by the producer/backend contract check."""

    def process_event(self, event: EventEnvelope) -> EventInboxReceipt:
        """Submit one typed, project-scoped producer event."""
        ...

    def goal_status(self, goal_id: str) -> GoalSnapshot:
        """Read the persisted goal through the project plugin boundary."""
        ...

    def storage_usage(self) -> ProjectStorageUsage:
        """Read content-free project storage totals."""
        ...


class PluginContractViolation(AssertionError):
    """Raised when a plugin adapter fails an observable contract assertion."""


@dataclass(frozen=True, slots=True)
class ProducerBackendContractEvidence:
    """Bounded result of one producer event and exact retry contract check."""

    project_id: str
    event_id: str
    payload_sha256: str
    event_payload_bytes: int
    event_payload_bytes_received: int
    event_payload_bytes_retained: int


def assert_goal_started_event_contract(
    adapter: ProjectPluginContractAdapter,
    event: EventEnvelope,
    *,
    expected_project_id: str,
) -> ProducerBackendContractEvidence:
    """Assert serialization, acceptance, retry idempotency, and payload disposal.

    This reusable check intentionally covers only behavior visible through the
    plugin surface. Consumer suites must separately test their repository
    routing and any real producer or runtime delivery path.
    """

    if not isinstance(event.payload, GoalStarted):
        raise PluginContractViolation("contract event must contain goal.started")
    if event.project_id != expected_project_id:
        raise PluginContractViolation("event project does not match expected project")

    serialized = event.to_json()
    decoded = EventEnvelope.from_json(serialized)
    if decoded != event:
        raise PluginContractViolation("event JSON round-trip changed producer fields")

    first_receipt = adapter.process_event(decoded)
    retry_receipt = adapter.process_event(decoded)
    if first_receipt.status is not EventInboxStatus.PROCESSED:
        raise PluginContractViolation("goal.started event was not processed")
    if first_receipt != retry_receipt:
        raise PluginContractViolation("exact event retry changed its durable receipt")
    if (
        first_receipt.project_id != expected_project_id
        or first_receipt.event_id != event.event_id
    ):
        raise PluginContractViolation("receipt identity differs from producer event")

    snapshot = adapter.goal_status(event.payload.goal_id)
    goal = snapshot.goal
    if goal.project_id != expected_project_id:
        raise PluginContractViolation("persisted goal escaped the expected project")
    if (
        goal.goal_id != event.payload.goal_id
        or goal.problem != event.payload.problem
        or goal.owner != event.payload.owner
        or goal.success_criteria != event.payload.success_criteria
        or goal.status != event.payload.initial_status
        or goal.checklist_id != event.payload.checklist_id
        or goal.checklist_version != event.payload.checklist_version
        or goal.checklist_source_text != event.payload.checklist_source_text
        or goal.parent_goal_id != event.payload.parent_goal_id
        or goal.depends_on_goal_ids != event.payload.depends_on_goal_ids
        or goal.next_action != event.payload.next_action
    ):
        raise PluginContractViolation("persisted goal differs from producer contract")

    usage = adapter.storage_usage()
    event_payload_bytes = len(serialized.encode("utf-8"))
    if usage.project_id != expected_project_id:
        raise PluginContractViolation("storage usage escaped the expected project")
    if usage.event_payload_bytes_received < event_payload_bytes:
        raise PluginContractViolation("backend did not account for received event bytes")
    if usage.event_payload_bytes_retained != 0:
        raise PluginContractViolation("backend retained transient event payload bytes")

    return ProducerBackendContractEvidence(
        project_id=expected_project_id,
        event_id=event.event_id,
        payload_sha256=first_receipt.payload_sha256,
        event_payload_bytes=event_payload_bytes,
        event_payload_bytes_received=usage.event_payload_bytes_received,
        event_payload_bytes_retained=usage.event_payload_bytes_retained,
    )
