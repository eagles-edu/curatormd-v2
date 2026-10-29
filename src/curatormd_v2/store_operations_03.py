"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    ConflictError,
    EVENT_FAILURE_METADATA_RESERVE_BYTES,
    EventClaimError,
    EventDisposition,
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    EventPayloadScrubUsage,
    EventQueueStatus,
    GlobalEventInboxUsage,
    MAX_EVENT_RECEIPTS_GLOBAL,
    MAX_EVENT_RECEIPT_BYTES_GLOBAL,
    NotFoundError,
    PURGE_RETRY_BASE_SECONDS,
    PURGE_RETRY_MAX_SECONDS,
    Path,
    PurgeFailureCode,
    PurgeOutcome,
    PurgeStatus,
    PurgeTargetRecord,
    ReacquisitionAction,
    RetentionHoldKind,
    ReviewDecision,
    SuspendedProcessedEventEpochRequest,
    TerminalEventDispositionRecord,
    TerminalEventDispositionStoreRequest,
    UTC,
    _EVENT_INBOX_USAGE_SQL,
    _PURGE_APPROVAL_INVALIDATING_ERRORS,
    datetime,
    is_exact_int,
    re,
    sqlite3,
    stat,
    timedelta,
    utc_now,
)
from .store_operations_02 import StoreOperations0

class StoreOperations1Part0(StoreOperations0):
    """Internal SQLite operation group ordered by method dependency."""


    def get_receipt(
        self, receipt_id: str, project_id: str | None = None
    ) -> AuditReceipt:
        """Load one review and purge receipt, optionally project-scoped."""

        with self._lock:
            if project_id is None:
                row = self._connection.execute(
                    """SELECT r.*, c.reviewer_id AS cleanup_reviewer_id,
                              c.manifest_sha256 AS cleanup_manifest_sha256,
                              c.dependency_map_sha256 AS cleanup_dependency_map_sha256,
                              c.approved_at AS cleanup_approved_at,
                              c.canonical_persisted AS cleanup_canonical_persisted
                       FROM audit_receipts AS r
                       LEFT JOIN cleanup_authorizations AS c
                         ON c.receipt_id = r.receipt_id
                       WHERE r.receipt_id = ?""",
                    (receipt_id,),
                ).fetchone()
            else:
                row = self._connection.execute(
                    """SELECT r.*, c.reviewer_id AS cleanup_reviewer_id,
                              c.manifest_sha256 AS cleanup_manifest_sha256,
                              c.dependency_map_sha256 AS cleanup_dependency_map_sha256,
                              c.approved_at AS cleanup_approved_at,
                              c.canonical_persisted AS cleanup_canonical_persisted
                       FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       LEFT JOIN cleanup_authorizations AS c
                         ON c.receipt_id = r.receipt_id
                       WHERE r.receipt_id = ? AND g.project_id = ?""",
                    (receipt_id, project_id),
                ).fetchone()
            if row is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            targets = self._connection.execute(
                "SELECT path, sha256, retention_hold, device_id, inode_id, occurrence_id, "
                "reacquisition_action "
                "FROM purge_targets WHERE receipt_id = ? "
                "ORDER BY path",
                (receipt_id,),
            ).fetchall()
        artifacts = tuple(
            ArtifactRef(
                item["path"],
                item["sha256"],
                RetentionHoldKind(item["retention_hold"]) if item["retention_hold"] else None,
                item["device_id"],
                item["inode_id"],
                item["occurrence_id"],
                ReacquisitionAction(item["reacquisition_action"]),
            )
            for item in targets
        )
        return AuditReceipt(
            candidate_id=row["candidate_id"],
            decision=ReviewDecision(row["decision"]),
            facts_sha256=row["facts_sha256"],
            artifacts=artifacts,
            artifact_inventory_complete=bool(row["artifact_inventory_complete"]),
            reviewer_id=row["reviewer_id"],
            review_rationale=row["review_rationale"],
            canonical_persisted=bool(row["canonical_persisted"]),
            canonical_target=row["canonical_target"],
            canonical_sha256=row["canonical_sha256"],
            canonical_persisted_at=row["canonical_persisted_at"],
            receipt_id=row["receipt_id"],
            purge_status=PurgeStatus(row["purge_status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            cleanup_authorized=row["cleanup_reviewer_id"] is not None,
            cleanup_reviewer_id=row["cleanup_reviewer_id"],
            cleanup_manifest_sha256=row["cleanup_manifest_sha256"],
            cleanup_dependency_map_sha256=row["cleanup_dependency_map_sha256"],
            cleanup_approved_at=row["cleanup_approved_at"],
            cleanup_canonical_persisted=bool(row["cleanup_canonical_persisted"]),
        )

    def get_purge_targets(
        self,
        receipt_id: str,
        pending_only: bool = False,
        project_id: str | None = None,
        due_only: bool = False,
    ) -> tuple[tuple[ArtifactRef, ArtifactStatus, int, str | None], ...]:
        """Read the receipt's artifact states, optionally excluding completed purges."""

        if due_only and not pending_only:
            raise ValueError("due_only requires pending_only")
        with self._lock:
            if project_id is not None:
                scoped = self._connection.execute(
                    """SELECT 1 FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.receipt_id = ? AND g.project_id = ?""",
                    (receipt_id, project_id),
                ).fetchone()
                if scoped is None:
                    raise NotFoundError(f"audit receipt not found: {receipt_id}")
            if due_only:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? "
                    "AND status IN (?, ?) "
                    "AND approval_stale = 0 "
                    "AND (retention_hold IS NULL OR hold_released_at IS NOT NULL) "
                    "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
                    "ORDER BY path",
                    (
                        receipt_id,
                        ArtifactStatus.PENDING.value,
                        ArtifactStatus.FAILED.value,
                        utc_now(),
                    ),
                ).fetchall()
            elif pending_only:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? "
                    "AND status IN (?, ?) "
                    "AND approval_stale = 0 "
                    "AND (retention_hold IS NULL OR hold_released_at IS NOT NULL) "
                    "ORDER BY path",
                    (receipt_id, ArtifactStatus.PENDING.value, ArtifactStatus.FAILED.value),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? ORDER BY path",
                    (receipt_id,),
                ).fetchall()
        return tuple(
            (
                ArtifactRef(
                    row["path"],
                    row["sha256"],
                    RetentionHoldKind(row["retention_hold"]) if row["retention_hold"] else None,
                    row["device_id"],
                    row["inode_id"],
                    row["occurrence_id"],
                    ReacquisitionAction(row["reacquisition_action"]),
                ),
                ArtifactStatus(row["status"]),
                row["attempts"],
                row["error"],
            )
            for row in rows
        )

    def get_purge_target_records(
        self,
        receipt_id: str,
        project_id: str,
    ) -> tuple[PurgeTargetRecord, ...]:
        """Read timestamps and retry state for one scoped receipt's artifacts."""

        with self._lock:
            scoped = self._connection.execute(
                """SELECT 1 FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
            if scoped is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            rows = self._connection.execute(
                "SELECT * FROM purge_targets WHERE receipt_id = ? ORDER BY path",
                (receipt_id,),
            ).fetchall()
        return tuple(
            PurgeTargetRecord(
                artifact=ArtifactRef(
                    row["path"],
                    row["sha256"],
                    RetentionHoldKind(row["retention_hold"]) if row["retention_hold"] else None,
                    row["device_id"],
                    row["inode_id"],
                    row["occurrence_id"],
                    ReacquisitionAction(row["reacquisition_action"]),
                ),
                status=ArtifactStatus(row["status"]),
                attempts=row["attempts"],
                error=row["error"],
                created_at=row["created_at"],
                last_attempt_at=row["last_attempt_at"],
                next_attempt_at=row["next_attempt_at"],
                hold_created_at=row["hold_created_at"],
                hold_created_by=row["hold_created_by"],
                hold_released_at=row["hold_released_at"],
                hold_released_by=row["hold_released_by"],
                hold_release_rationale=row["hold_release_rationale"],
                approval_stale=bool(row["approval_stale"]),
                outcome=PurgeOutcome(row["outcome"]) if row["outcome"] else None,
            )
            for row in rows
        )

    @staticmethod
    def _validate_purge_result(
        status: ArtifactStatus, error: str | None, outcome: PurgeOutcome | None
    ) -> None:
        """Accept only terminal purge states and fixed content-free failures."""

        if status not in (ArtifactStatus.FAILED, ArtifactStatus.PURGED):
            raise ValueError("a purge result must be failed or purged")
        if status is ArtifactStatus.FAILED:
            allowed_errors = {
                code.value
                for code in PurgeFailureCode
                if code is not PurgeFailureCode.LEGACY_FAILURE_DETAIL_REDACTED
            }
            if error not in allowed_errors:
                raise ValueError("purge failure requires a known content-free error code")
            expected_outcome = (
                PurgeOutcome.CHANGED
                if error in _PURGE_APPROVAL_INVALIDATING_ERRORS
                else PurgeOutcome.FAILED
            )
            if outcome is not expected_outcome:
                raise ValueError("purge failure outcome does not match its error code")
        elif error is not None or outcome not in (
            None,
            PurgeOutcome.DELETED,
            PurgeOutcome.ALREADY_ABSENT,
        ):
            raise ValueError("successful purge needs a successful outcome and no error")

    @staticmethod
    def _purge_retry_at(status: ArtifactStatus, attempts: int) -> str | None:
        """Schedule bounded retry backoff only for failed purge attempts."""

        if status is not ArtifactStatus.FAILED:
            return None
        delay_seconds = min(
            PURGE_RETRY_BASE_SECONDS * (2 ** min(max(attempts - 1, 0), 16)),
            PURGE_RETRY_MAX_SECONDS,
        )
        return (datetime.now(UTC) + timedelta(seconds=delay_seconds)).isoformat(
            timespec="microseconds"
        )

    @staticmethod
    def _refresh_purge_receipt_status(
        connection: sqlite3.Connection, receipt_id: str
    ) -> None:
        """Keep the receipt pending until every inventoried artifact is purged."""

        updated_at = utc_now()
        unfinished = connection.execute(
            "SELECT COUNT(*) FROM purge_targets WHERE receipt_id = ? AND status != ?",
            (receipt_id, ArtifactStatus.PURGED.value),
        ).fetchone()[0]
        receipt_status = (
            PurgeStatus.PURGE_PENDING if unfinished else PurgeStatus.COMPLETE
        )
        cursor = connection.execute(
            "UPDATE audit_receipts SET purge_status = ?, updated_at = ? "
            "WHERE receipt_id = ?",
            (receipt_status.value, updated_at, receipt_id),
        )
        if cursor.rowcount != 1:
            raise NotFoundError(f"audit receipt not found: {receipt_id}")

    def receipt_purge_status_counts(
        self, goal_id: str, project_id: str
    ) -> dict[str, int]:
        """Count receipt purge states without loading the audit receipt bodies."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT r.purge_status, COUNT(*) AS count FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE s.goal_id = ? AND g.project_id = ?
                   GROUP BY r.purge_status""",
                (goal_id, project_id),
            ).fetchall()
        return {str(row["purge_status"]): int(row["count"]) for row in rows}

    @staticmethod
    def _event_inbox_usage(connection: sqlite3.Connection) -> tuple[int, int]:
        """Measure active inbox rows and retry metadata against the live cap."""

        row = connection.execute(_EVENT_INBOX_USAGE_SQL).fetchone()
        audit = connection.execute(
            """SELECT COALESCE(SUM(
                   length(CAST(retry.project_id AS BLOB)) +
                   length(CAST(retry.event_id AS BLOB)) +
                   length(CAST(retry.actor_id AS BLOB)) +
                   length(CAST(retry.created_at AS BLOB))
                 ), 0) AS bytes FROM event_retry_audit AS retry
               JOIN event_inbox AS inbox
                 ON inbox.project_id = retry.project_id
                AND inbox.event_id = retry.event_id
               WHERE inbox.archive_id IS NULL"""
        ).fetchone()
        return int(row["count"]), int(row["bytes"]) + int(audit["bytes"])

    @staticmethod
    def _event_payload_scrub_usage(
        connection: sqlite3.Connection,
    ) -> EventPayloadScrubUsage:
        """Measure all scrub rows and their unassigned subset as logical bytes."""

        row = connection.execute(
            """WITH measured AS (
                   SELECT project_id,
                          length(CAST(scrub_id AS TEXT)) +
                          COALESCE(length(CAST(project_id AS BLOB)), 0) +
                          COALESCE(length(CAST(event_id AS BLOB)), 0) +
                          length(CAST(queued_at AS BLOB)) +
                          length(CAST(attempts AS TEXT)) +
                          COALESCE(length(CAST(last_error_code AS BLOB)), 0)
                            AS record_bytes
                   FROM event_payload_scrub_queue
                 )
                 SELECT COUNT(*) AS record_count,
                        COALESCE(SUM(record_bytes), 0) AS record_bytes,
                        COALESCE(SUM(CASE WHEN project_id IS NULL THEN 1 ELSE 0 END), 0)
                          AS unassigned_count,
                        COALESCE(SUM(CASE WHEN project_id IS NULL THEN record_bytes
                                          ELSE 0 END), 0) AS unassigned_bytes
                 FROM measured"""
        ).fetchone()
        return EventPayloadScrubUsage(
            record_count=int(row["record_count"]),
            logical_bytes=int(row["record_bytes"]),
            unassigned_record_count=int(row["unassigned_count"]),
            unassigned_logical_bytes=int(row["unassigned_bytes"]),
        )

    @staticmethod
    def _global_event_inbox_capacity(
        count: int,
        retained_bytes: int,
        scrub_usage: EventPayloadScrubUsage,
    ) -> GlobalEventInboxUsage:
        can_accept = (
            count < MAX_EVENT_RECEIPTS_GLOBAL
            and retained_bytes + EVENT_FAILURE_METADATA_RESERVE_BYTES
            <= MAX_EVENT_RECEIPT_BYTES_GLOBAL
        )
        gate = None if can_accept else (
            "Global event inbox capacity reached; new events are rejected without "
            "deleting receipts. An approved retention/recovery action is required."
        )
        return GlobalEventInboxUsage(
            receipt_count=count,
            retained_record_bytes=retained_bytes,
            receipt_count_limit=MAX_EVENT_RECEIPTS_GLOBAL,
            retained_record_bytes_limit=MAX_EVENT_RECEIPT_BYTES_GLOBAL,
            can_accept_new_event=can_accept,
            payload_scrub_queue=scrub_usage,
            open_gate=gate,
        )

    @staticmethod
    def _event_replay_payload_matches(
        existing: sqlite3.Row,
        event: EventEnvelope,
        payload_digest: str,
    ) -> bool:
        """Match a replay to the stored canonical or idempotency digest."""

        stored_idempotency_digest = existing["idempotency_sha256"]
        if stored_idempotency_digest is None:
            return existing["payload_sha256"] == payload_digest
        return stored_idempotency_digest == event.idempotency_sha256

    @staticmethod
    def _event_receipt(row: sqlite3.Row) -> EventInboxReceipt:
        return EventInboxReceipt(
            project_id=row["project_id"],
            event_id=row["event_id"],
            payload_sha256=row["payload_sha256"],
            status=EventInboxStatus(row["status"]),
            received_at=row["received_at"],
            processed_at=row["processed_at"],
            last_error_code=row["last_error"],
            attempts=row["attempts"],
            next_attempt_at=row["next_attempt_at"],
            disposition=(
                EventDisposition(row["disposition"])
                if row["disposition"] is not None else None
            ),
        )

    def pending_events(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> tuple[EventEnvelope, ...]:
        """Read bounded received/failed payloads for an in-process consumer."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    """SELECT e.payload_json FROM event_inbox AS e
                       WHERE e.status IN (?, ?) AND e.payload_json IS NOT NULL
                         AND (e.status = ? OR e.next_attempt_at IS NULL
                              OR e.next_attempt_at <= ?)
                         AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                              OR e.lease_expires_at <= ?)
                         AND (e.source_sequence IS NULL OR e.source_sequence =
                           COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                     WHERE c.project_id = e.project_id
                                       AND c.source_id = e.source_id), 0) + 1)
                       ORDER BY e.received_at, e.event_id LIMIT ?""",
                    (
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        EventInboxStatus.RECEIVED.value,
                        now,
                        now,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT e.payload_json FROM event_inbox AS e
                       WHERE e.project_id = ? AND e.status IN (?, ?)
                         AND e.payload_json IS NOT NULL
                         AND (e.status = ? OR e.next_attempt_at IS NULL
                              OR e.next_attempt_at <= ?)
                         AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                              OR e.lease_expires_at <= ?)
                         AND (e.source_sequence IS NULL OR e.source_sequence =
                           COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                     WHERE c.project_id = e.project_id
                                       AND c.source_id = e.source_id), 0) + 1)
                       ORDER BY e.received_at, e.event_id LIMIT ?""",
                    (
                        project_id,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        EventInboxStatus.RECEIVED.value,
                        now,
                        now,
                        limit,
                    ),
                ).fetchall()
        return tuple(
            EventEnvelope.from_json(row["payload_json"])
            for row in rows
            if row["payload_json"] is not None
        )

    def assert_event_claim(
        self,
        project_id: str,
        event_id: str,
        lease_owner: str | None,
    ) -> None:
        """Require matching ownership when a live worker claim exists."""

        now = utc_now()
        with self._lock:
            row = self._connection.execute(
                "SELECT lease_owner, lease_expires_at FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"event not found: {project_id}/{event_id}")
        saved_owner = row["lease_owner"]
        expires_at = row["lease_expires_at"]
        is_live = saved_owner is not None and expires_at is not None and expires_at > now
        if lease_owner is not None:
            if saved_owner != lease_owner or not is_live:
                raise EventClaimError("event claim is missing, expired, or owned elsewhere")
        elif is_live:
            raise EventClaimError("event is currently claimed by another router worker")

    def event_queue_status(
        self, project_id: str | None = None
    ) -> EventQueueStatus:
        """Return queue counts and oldest pending age without event identifiers."""

        now = utc_now()
        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT status, COUNT(*) AS count FROM event_inbox "
                    "GROUP BY status"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT status, COUNT(*) AS count FROM event_inbox "
                    "WHERE project_id = ? GROUP BY status",
                    (project_id,),
                ).fetchall()
            oldest_query = (
                "SELECT MIN(received_at) AS received_at FROM event_inbox "
                "WHERE project_id = ? AND status IN (?, ?)"
                if project_id is not None
                else "SELECT MIN(received_at) AS received_at FROM event_inbox "
                "WHERE status IN (?, ?)"
            )
            oldest_params = (
                (project_id, EventInboxStatus.RECEIVED.value, EventInboxStatus.FAILED.value)
                if project_id is not None
                else (EventInboxStatus.RECEIVED.value, EventInboxStatus.FAILED.value)
            )
            oldest = self._connection.execute(
                oldest_query, oldest_params
            ).fetchone()["received_at"]
            if project_id is not None:
                claim_counts = self._connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN lease_expires_at > ? THEN 1 ELSE 0 END), 0)
                           AS claimed,
                         COALESCE(SUM(CASE WHEN lease_expires_at IS NULL
                                            OR lease_expires_at <= ? THEN 1 ELSE 0 END), 0)
                           AS expired
                       FROM event_inbox
                       WHERE status IN (?, ?) AND lease_owner IS NOT NULL
                         AND project_id = ?""",
                    (
                        now,
                        now,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        project_id,
                    ),
                ).fetchone()
            else:
                claim_counts = self._connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN lease_expires_at > ? THEN 1 ELSE 0 END), 0)
                           AS claimed,
                         COALESCE(SUM(CASE WHEN lease_expires_at IS NULL
                                            OR lease_expires_at <= ? THEN 1 ELSE 0 END), 0)
                           AS expired
                       FROM event_inbox
                       WHERE status IN (?, ?) AND lease_owner IS NOT NULL""",
                    (
                        now,
                        now,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                    ),
                ).fetchone()
        counts = {row["status"]: int(row["count"]) for row in rows}
        oldest_age = None
        if oldest is not None:
            try:
                timestamp = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
                if timestamp.tzinfo is not None:
                    oldest_age = max(
                        0, int((datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds())
                    )
            except ValueError:
                oldest_age = None
        return EventQueueStatus(
            received_count=counts.get(EventInboxStatus.RECEIVED.value, 0),
            failed_count=counts.get(EventInboxStatus.FAILED.value, 0),
            quarantined_count=counts.get(EventInboxStatus.QUARANTINED.value, 0),
            oldest_pending_received_at=oldest,
            oldest_pending_age_seconds=oldest_age,
            claimed_count=int(claim_counts["claimed"]),
            expired_claim_count=int(claim_counts["expired"]),
        )

    @classmethod
    def _validate_terminal_event_disposition_request(
        cls, request: TerminalEventDispositionStoreRequest
    ) -> None:
        """Validate bounded identity, rationale, fence, and digest fields."""

        for name, value in (
            ("project_id", request.project_id),
            ("event_id", request.event_id),
            ("transition_id", request.transition_id),
            ("actor_id", request.actor_id),
        ):
            cls._validate_access_identity(value, name)
        cls._validate_access_rationale(request.rationale)
        if (
            not is_exact_int(request.expected_binding_revision)
            or request.expected_binding_revision < 1
            or not is_exact_int(request.expected_source_epoch)
            or request.expected_source_epoch < 1
        ):
            raise ValueError("binding revision and source epoch must be positive integers")
        if not re.fullmatch(r"[0-9a-f]{64}", request.expected_payload_sha256):
            raise ValueError("payload digest must be lowercase SHA-256")

    @staticmethod
    def _require_terminal_disposition_binding(
        connection: sqlite3.Connection,
        request: TerminalEventDispositionStoreRequest,
    ) -> None:
        """Require the same fenced consumer-binding revision and epoch."""

        binding = connection.execute(
            "SELECT status, revision, source_epoch FROM consumer_bindings "
            "WHERE project_id = ?", (request.project_id,),
        ).fetchone()
        if (
            binding is None
            or binding["status"] not in {"deregistration_pending", "deregistered"}
            or binding["revision"] != request.expected_binding_revision
            or binding["source_epoch"] != request.expected_source_epoch
        ):
            raise ConflictError("consumer binding changed or is not fenced")

    @staticmethod
    def _require_terminal_disposition_event(
        connection: sqlite3.Connection,
        request: TerminalEventDispositionStoreRequest,
        now: str,
    ) -> sqlite3.Row:
        """Require the exact unresolved payload without an active lease."""

        row = connection.execute(
            "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
            (request.project_id, request.event_id),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"event not found: {request.project_id}/{request.event_id}")
        if row["status"] not in {"failed", "quarantined"} or row[
            "payload_sha256"
        ] != request.expected_payload_sha256:
            raise ConflictError("event is not the reviewed unresolved payload")
        if (
            row["lease_owner"] is not None
            and row["lease_expires_at"] is not None
            and row["lease_expires_at"] > now
        ):
            raise ConflictError("event has an active processing lease")
        return row

    @staticmethod
    def _advance_terminal_disposition_cursor(
        connection: sqlite3.Connection,
        request: TerminalEventDispositionStoreRequest,
        row: sqlite3.Row,
        now: str,
    ) -> None:
        """Advance the source cursor only when this is the next event."""

        if row["source_sequence"] is None:
            return
        cursor = connection.execute(
            "SELECT last_sequence FROM event_cursors "
            "WHERE project_id = ? AND source_id = ?",
            (request.project_id, row["source_id"]),
        ).fetchone()
        previous = int(cursor["last_sequence"]) if cursor is not None else 0
        if row["source_sequence"] != previous + 1:
            raise ConflictError("earlier source events must be resolved first")
        connection.execute(
            """INSERT INTO event_cursors
               (project_id, source_id, last_sequence, updated_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(project_id, source_id)
               DO UPDATE SET last_sequence = excluded.last_sequence,
               updated_at = excluded.updated_at""",
            (request.project_id, row["source_id"], row["source_sequence"], now),
        )

    @staticmethod
    def _terminal_event_disposition_from_row(
        row: sqlite3.Row,
    ) -> TerminalEventDispositionRecord:
        return TerminalEventDispositionRecord(
            row["project_id"], row["event_id"], row["transition_id"],
            row["actor_id"], EventInboxStatus(row["prior_status"]),
            row["payload_sha256"], row["rationale"], row["created_at"],
        )

    def suspended_processed_event_source_epoch(
        self, request: SuspendedProcessedEventEpochRequest
    ) -> int | None:
        """Return the epoch only for a processed receipt under suspended state."""

        with self._lock:
            row = self._connection.execute(
                """SELECT binding.source_epoch FROM event_inbox AS item
                   JOIN project_registry AS project
                     ON project.project_id = item.project_id
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = item.project_id
                   JOIN project_grants AS grant_row
                     ON grant_row.project_id = item.project_id
                    AND grant_row.subject_id = ? AND grant_row.action = 'write'
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE item.project_id = ? AND item.event_id = ?
                     AND item.status = 'processed'
                     AND project.status = 'suspended'
                     AND project.repository_fingerprint = ?
                     AND project.config_sha256 = ?
                     AND project.backend_api_version = ?
                     AND binding.status = 'active'
                     AND revocation.grant_id IS NULL
                   ORDER BY grant_row.granted_at DESC LIMIT 1""",
                (
                    request.subject_id,
                    request.project_id,
                    request.event_id,
                    request.repository_fingerprint,
                    request.config_sha256,
                    request.backend_api_version,
                ),
            ).fetchone()
        return int(row["source_epoch"]) if row is not None else None

    @staticmethod
    def _regular_file_size(path: Path) -> int | None:
        """Read one file's current size without following a symlink."""

        try:
            metadata = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return 0
        if not stat.S_ISREG(metadata.st_mode):
            return None
        return metadata.st_size
