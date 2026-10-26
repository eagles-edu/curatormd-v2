"""Shared deterministic helpers for durable event regression tests."""

from __future__ import annotations

from curatormd_v2 import CuratorStore, EventEnvelope


def make_event_retry_due(store: CuratorStore, event: EventEnvelope) -> None:
    """Move one received event's retry deadline into the past without sleeping."""

    with store.transaction() as connection:
        connection.execute(
            "UPDATE event_inbox SET next_attempt_at = ? "
            "WHERE project_id = ? AND event_id = ?",
            ("2000-01-01T00:00:00+00:00", event.project_id, event.event_id),
        )
