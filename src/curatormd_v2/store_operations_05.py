"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ConflictError,
    ConsumerDrainStoreRequest,
    EventInboxStatus,
    TerminalEventCandidate,
    TerminalEventInventory,
    UTC,
    datetime,
    hashlib,
    is_exact_int,
    timedelta,
)
from .store_operations_04 import StoreOperations1Part1

class StoreOperations1(StoreOperations1Part1):
    """Continuation of StoreOperations1 operations."""


    def terminal_event_inventory(
        self,
        project_id: str,
        *,
        limit: int = 100,
        after_event_id: str | None = None,
    ) -> TerminalEventInventory:
        """Read a content-free page of failed events eligible for disposition."""

        self._validate_access_identity(project_id, "project_id")
        if not is_exact_int(limit) or not 1 <= limit <= 100:
            raise ValueError("terminal event inventory limit must be between 1 and 100")
        if after_event_id is not None:
            self._validate_access_identity(after_event_id, "after_event_id")
        with self._lock:
            count = int(self._connection.execute(
                """SELECT COUNT(*) FROM event_inbox
                   WHERE project_id = ? AND status IN (?, ?)
                     AND (? IS NULL OR event_id > ?)""",
                (project_id, EventInboxStatus.FAILED.value,
                 EventInboxStatus.QUARANTINED.value, after_event_id, after_event_id),
            ).fetchone()[0])
            rows = self._connection.execute(
                """SELECT event_id, status, payload_sha256, source_id, source_sequence
                   FROM event_inbox WHERE project_id = ? AND status IN (?, ?)
                     AND (? IS NULL OR event_id > ?)
                   ORDER BY event_id LIMIT ?""",
                (project_id, EventInboxStatus.FAILED.value,
                 EventInboxStatus.QUARANTINED.value, after_event_id, after_event_id,
                 limit + 1),
            ).fetchall()
        complete = len(rows) <= limit
        page = rows[:limit]
        events = tuple(
            TerminalEventCandidate(
                event_id=row["event_id"],
                status=EventInboxStatus(row["status"]),
                payload_sha256=row["payload_sha256"],
                source_id=row["source_id"],
                source_sequence=row["source_sequence"],
            )
            for row in page
        )
        return TerminalEventInventory(
            count_after_cursor=count,
            events=events,
            complete=complete,
            next_after_event_id=events[-1].event_id if not complete and events else None,
        )

    def authorize_consumer_drain(
        self, request: ConsumerDrainStoreRequest
    ) -> tuple[int, str]:
        """Authorize only the inventoried retries during a short attended drain."""

        self._validate_consumer_drain_request(request)
        now = datetime.now(UTC)
        created_at = now.isoformat()
        expires_at = (now + timedelta(seconds=request.lifetime_seconds)).isoformat()
        with self._transaction() as connection:
            binding, registration = self._require_consumer_drain_fence(
                connection, request
            )
            replay = self._consumer_drain_authorization_replay(
                connection, request, binding, registration
            )
            if replay is not None:
                return replay
            rows = connection.execute(
                """SELECT event_id, payload_sha256, idempotency_sha256,
                          source_id, source_sequence, status
                   FROM event_inbox WHERE project_id = ? AND status <> 'processed'
                   ORDER BY event_id""",
                (request.project_id,),
            ).fetchall()
            actual_digest = hashlib.sha256()
            for row in rows:
                encoded = self._consumer_drain_inventory_row_bytes(row)
                actual_digest.update(len(encoded).to_bytes(4, "big"))
                actual_digest.update(encoded)
            if actual_digest.hexdigest() != request.expected_inventory_sha256:
                raise ConflictError("event inventory changed; review it again")
            connection.execute(
                """INSERT INTO consumer_drain_sessions
                   (project_id, transition_id, actor_id, caller_subject,
                    caller_profile, binding_revision, source_epoch, config_sha256,
                    inventory_sha256, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    request.project_id, request.transition_id, request.actor_id,
                    request.caller_subject, request.caller_profile,
                    request.expected_revision, binding["source_epoch"],
                    registration["config_sha256"],
                    request.expected_inventory_sha256, created_at, expires_at,
                ),
            )
            connection.executemany(
                """INSERT INTO consumer_drain_events
                   (project_id, transition_id, event_id, payload_sha256,
                    idempotency_sha256, source_id, source_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        request.project_id, request.transition_id, row["event_id"],
                        row["payload_sha256"], row["idempotency_sha256"],
                        row["source_id"], row["source_sequence"],
                    )
                    for row in rows
                ],
            )
            return len(rows), expires_at
