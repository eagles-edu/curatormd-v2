"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ConflictError,
    EVENT_FAILURE_METADATA_RESERVE_BYTES,
    EventDisposition,
    EventEnvelope,
    EventInboxCapacityError,
    EventInboxReceipt,
    EventInboxStatus,
    EventOrderError,
    GlobalEventInboxUsage,
    MAX_EVENT_RECEIPTS_GLOBAL,
    MAX_EVENT_RECEIPT_BYTES_GLOBAL,
    NotFoundError,
    Path,
    SQLiteDatabaseFileUsage,
    SQLiteDatabasePageUsage,
    SQLitePhysicalStorageUsage,
    StoragePhysicalClassUsage,
    TerminalEventDispositionRecord,
    TerminalEventDispositionStoreRequest,
    UTC,
    _ERROR_CODE_RE,
    datetime,
    hashlib,
    is_exact_int,
    re,
    sqlite3,
    timedelta,
    utc_now,
)
from .read_models import SQLITE_DATABASE_WARNING_THRESHOLD_BYTES
from .store_operations_09 import StoreOperations3

class StoreOperations4Part0(StoreOperations3):
    """Internal SQLite operation group ordered by method dependency."""


    def global_event_inbox_usage(self) -> GlobalEventInboxUsage:
        """Return aggregate capacity only; never reveal other project IDs."""

        with self._lock:
            count, retained_bytes = self._event_inbox_usage(self._connection)
            scrub_usage = self._event_payload_scrub_usage(self._connection)
        return self._global_event_inbox_capacity(count, retained_bytes, scrub_usage)

    def ingest_event(self, event: EventEnvelope) -> tuple[EventInboxReceipt, bool]:
        """Durably accept one event; repeated identical IDs are idempotent."""

        payload_json = event.to_json()
        payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        payload_bytes = len(payload_json.encode("utf-8"))
        received_at = utc_now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (event.project_id, event.event_id),
            ).fetchone()
            if existing is not None:
                if not self._event_replay_payload_matches(
                    existing, event, payload_digest
                ):
                    raise ConflictError(
                        "event ID was already used with a different payload"
                    )
                return self._event_receipt(existing), False
            lifecycle = connection.execute(
                """SELECT registration.status AS project_status,
                          binding.status AS binding_status,
                          tombstone.project_id AS retired_project_id
                   FROM project_registry AS registration
                   LEFT JOIN consumer_bindings AS binding
                     ON binding.project_id = registration.project_id
                   LEFT JOIN project_retirement_tombstones AS tombstone
                     ON tombstone.project_id = registration.project_id
                   WHERE registration.project_id = ?""",
                (event.project_id,),
            ).fetchone()
            if lifecycle is not None and (
                lifecycle["project_status"] != "active"
                or lifecycle["binding_status"] != "active"
                or lifecycle["retired_project_id"] is not None
            ):
                raise ConflictError(
                    "project or consumer lifecycle does not accept new events"
                )
            retained_count, retained_bytes = self._event_inbox_usage(connection)
            new_row_bytes = sum(
                len(value.encode("utf-8"))
                for value in (
                    event.project_id,
                    event.event_id,
                    event.event_kind.value,
                    payload_digest,
                    event.idempotency_sha256,
                    str(payload_bytes),
                    payload_json,
                    EventInboxStatus.RECEIVED.value,
                    received_at,
                    event.source_id,
                    str(event.source_sequence) if event.source_sequence is not None else "",
                )
            )
            if (
                retained_count + 1 > MAX_EVENT_RECEIPTS_GLOBAL
                or retained_bytes
                + new_row_bytes
                + EVENT_FAILURE_METADATA_RESERVE_BYTES
                > MAX_EVENT_RECEIPT_BYTES_GLOBAL
            ):
                raise EventInboxCapacityError(
                    "global event inbox capacity reached; new events are rejected "
                    "without deleting receipts"
                )
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    idempotency_sha256, payload_json, status, received_at, processed_at,
                    last_error, source_id, source_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
                (
                    event.project_id,
                    event.event_id,
                    event.event_kind.value,
                    payload_digest,
                    payload_bytes,
                    event.idempotency_sha256,
                    payload_json,
                    EventInboxStatus.RECEIVED.value,
                    received_at,
                    event.source_id,
                    event.source_sequence,
                ),
            )
            row = connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (event.project_id, event.event_id),
            ).fetchone()
        return self._event_receipt(row), True

    def advance_source_sequence(self, event: EventEnvelope) -> None:
        """Advance one project's source cursor in the caller's event transaction."""

        if event.source_sequence is None:
            return
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT last_sequence FROM event_cursors "
                "WHERE project_id = ? AND source_id = ?",
                (event.project_id, event.source_id),
            ).fetchone()
            previous = row["last_sequence"] if row is not None else 0
            expected = previous + 1
            if event.source_sequence != expected:
                raise EventOrderError(
                    f"expected source sequence {expected}, received {event.source_sequence}"
                )
            connection.execute(
                """INSERT INTO event_cursors
                   (project_id, source_id, last_sequence, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(project_id, source_id) DO UPDATE SET
                   last_sequence = excluded.last_sequence,
                   updated_at = excluded.updated_at""",
                (
                    event.project_id,
                    event.source_id,
                    event.source_sequence,
                    utc_now(),
                ),
            )

    def claim_pending_events(
        self,
        lease_owner: str,
        *,
        limit: int = 100,
        lease_seconds: int = 300,
        project_ids: tuple[str, ...] | None = None,
    ) -> tuple[EventEnvelope, ...]:
        """Atomically lease due events, optionally within fixed project bindings."""

        if not _ERROR_CODE_RE.fullmatch(lease_owner) or len(lease_owner) > 128:
            raise ValueError("lease_owner must be a bounded safe identifier")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not is_exact_int(lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_seconds must be between 1 and 86400")
        if project_ids is not None:
            # Reject tuple subclasses so project bindings use an inert exact container.
            # pylint: disable-next=unidiomatic-typecheck
            if type(project_ids) is not tuple or len(project_ids) > 128:
                raise ValueError("project_ids must be a tuple of at most 128 bindings")
            for project_id in project_ids:
                self._validate_access_identity(project_id, "project_id")
            if len(set(project_ids)) != len(project_ids):
                raise ValueError("project_ids must not contain duplicates")
            if not project_ids:
                return ()
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="microseconds")
        expires_text = (now + timedelta(seconds=lease_seconds)).isoformat(
            timespec="microseconds"
        )
        with self._transaction() as connection:
            connection.execute(
                "CREATE TEMP TABLE IF NOT EXISTS router_project_bindings "
                "(project_id TEXT PRIMARY KEY) WITHOUT ROWID"
            )
            connection.execute("DELETE FROM temp.router_project_bindings")
            if project_ids is not None:
                connection.executemany(
                    "INSERT INTO temp.router_project_bindings(project_id) VALUES (?)",
                    ((project_id,) for project_id in project_ids),
                )
            rows = connection.execute(
                """SELECT e.project_id, e.event_id, e.payload_json
                   FROM event_inbox AS e
                   WHERE e.status IN (?, ?) AND e.payload_json IS NOT NULL
                     AND (e.status = ? OR e.next_attempt_at IS NULL
                          OR e.next_attempt_at <= ?)
                     AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                          OR e.lease_expires_at <= ?)
                     AND (e.source_sequence IS NULL OR e.source_sequence =
                       COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                 WHERE c.project_id = e.project_id
                                   AND c.source_id = e.source_id), 0) + 1)
                     AND (? = 1 OR e.project_id IN
                       (SELECT project_id FROM temp.router_project_bindings))
                   ORDER BY e.received_at, e.event_id LIMIT ?""",
                (
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                    EventInboxStatus.RECEIVED.value,
                    now_text,
                    now_text,
                    1 if project_ids is None else 0,
                    limit,
                ),
            ).fetchall()
            claimed_payloads: list[str] = []
            for row in rows:
                cursor = connection.execute(
                    """UPDATE event_inbox SET lease_owner = ?, lease_expires_at = ?
                       WHERE project_id = ? AND event_id = ?
                         AND (lease_owner IS NULL OR lease_expires_at IS NULL
                              OR lease_expires_at <= ?)""",
                    (
                        lease_owner,
                        expires_text,
                        row["project_id"],
                        row["event_id"],
                        now_text,
                    ),
                )
                if cursor.rowcount == 1 and row["payload_json"] is not None:
                    claimed_payloads.append(row["payload_json"])
            connection.execute("DELETE FROM temp.router_project_bindings")
        return tuple(EventEnvelope.from_json(payload) for payload in claimed_payloads)

    def release_event_claims(self, lease_owner: str) -> int:
        """Release unprocessed claims when a router invocation exits cleanly."""

        if not _ERROR_CODE_RE.fullmatch(lease_owner) or len(lease_owner) > 128:
            raise ValueError("lease_owner must be a bounded safe identifier")
        with self._transaction() as connection:
            cursor = connection.execute(
                """UPDATE event_inbox SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE lease_owner = ? AND status IN (?, ?)""",
                (
                    lease_owner,
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                ),
            )
        return cursor.rowcount

    def event_payload_scrub_pending_count(self, project_id: str) -> int:
        """Count content-free WAL scrub receipts visible to one project."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            row = self._connection.execute(
                """SELECT COUNT(*) AS count FROM event_payload_scrub_queue
                   WHERE project_id = ? OR project_id IS NULL""",
                (project_id,),
            ).fetchone()
        return int(row["count"])

    def retry_pending_event_payload_scrubs(self, limit: int = 1000) -> int:
        """Truncate payload remnants from WAL, retaining pending receipts on busy."""

        if not is_exact_int(limit) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.database == ":memory:":
            return 0
        with self._lock:
            if self._connection.in_transaction:
                return 0
            rows = self._connection.execute(
                """SELECT scrub_id FROM event_payload_scrub_queue
                   ORDER BY scrub_id LIMIT ?""",
                (limit,),
            ).fetchall()
            scrub_ids = tuple(int(row["scrub_id"]) for row in rows)
            if not scrub_ids:
                return 0
            busy_timeout = int(
                self._connection.execute("PRAGMA busy_timeout").fetchone()[0]
            )
            try:
                self._connection.execute("PRAGMA busy_timeout = 0")
                checkpoint = self._connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
            except sqlite3.Error:
                checkpoint = None
            finally:
                self._connection.execute(
                    f"PRAGMA busy_timeout = {busy_timeout}"
                )
            checkpoint_complete = checkpoint is not None and (
                int(checkpoint[0]) == 0
                and (
                    int(checkpoint[1]) == -1
                    or (int(checkpoint[1]) == 0 and int(checkpoint[2]) == 0)
                )
            )
            if not checkpoint_complete:
                try:
                    with self._transaction() as connection:
                        connection.executemany(
                            """UPDATE event_payload_scrub_queue
                               SET attempts = attempts + 1,
                                   last_error_code = 'wal_checkpoint_busy'
                               WHERE scrub_id = ?""",
                            ((scrub_id,) for scrub_id in scrub_ids),
                        )
                except sqlite3.Error:
                    pass
                return 0
            try:
                with self._transaction() as connection:
                    cursor = connection.executemany(
                        "DELETE FROM event_payload_scrub_queue WHERE scrub_id = ?",
                        ((scrub_id,) for scrub_id in scrub_ids),
                    )
            except sqlite3.Error:
                return 0
        return cursor.rowcount

    def _terminal_event_disposition_replay(
        self,
        connection: sqlite3.Connection,
        request: TerminalEventDispositionStoreRequest,
    ) -> tuple[EventInboxReceipt, TerminalEventDispositionRecord] | None:
        """Return an exact prior decision or reject a reused decision ID."""

        prior = connection.execute(
            "SELECT * FROM terminal_event_dispositions "
            "WHERE project_id = ? AND (event_id = ? OR transition_id = ?)",
            (request.project_id, request.event_id, request.transition_id),
        ).fetchone()
        if prior is None:
            return None
        compared = tuple(prior[key] for key in (
            "event_id", "transition_id", "actor_id", "payload_sha256", "rationale"
        ))
        expected = (
            request.event_id, request.transition_id, request.actor_id,
            request.expected_payload_sha256, request.rationale,
        )
        if compared != expected:
            raise ConflictError("terminal disposition ID was reused with changed input")
        receipt_row = connection.execute(
            "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
            (request.project_id, request.event_id),
        ).fetchone()
        if receipt_row is None:
            raise RuntimeError("terminal disposition lost its inbox receipt")
        return (
            self._event_receipt(receipt_row),
            self._terminal_event_disposition_from_row(prior),
        )

    def _persist_terminal_event_disposition(
        self,
        connection: sqlite3.Connection,
        request: TerminalEventDispositionStoreRequest,
        row: sqlite3.Row,
        now: str,
    ) -> TerminalEventDispositionRecord:
        """Persist the decision, queue payload erasure, and close its receipt."""

        record = TerminalEventDispositionRecord(
            request.project_id, request.event_id, request.transition_id,
            request.actor_id, EventInboxStatus(row["status"]),
            request.expected_payload_sha256, request.rationale, now,
        )
        connection.execute(
            """INSERT INTO terminal_event_dispositions
               (project_id, event_id, transition_id, actor_id, prior_status,
                payload_sha256, rationale, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (request.project_id, request.event_id, request.transition_id,
             request.actor_id, record.prior_status.value,
             request.expected_payload_sha256, request.rationale, now),
        )
        if row["payload_json"] is not None:
            self._queue_event_payload_scrub(
                connection, request.project_id, request.event_id
            )
        connection.execute(
            """UPDATE event_inbox SET status = ?, payload_json = NULL,
               processed_at = ?, last_error = NULL, next_attempt_at = NULL,
               disposition = ?, lease_owner = NULL, lease_expires_at = NULL
               WHERE project_id = ? AND event_id = ?""",
            (EventInboxStatus.PROCESSED.value, now,
             EventDisposition.TERMINAL_AUTHORIZED.value,
             request.project_id, request.event_id),
        )
        receipt = connection.execute(
            "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
            (request.project_id, request.event_id),
        ).fetchone()
        if receipt is None:
            raise RuntimeError("terminal disposition lost its inbox receipt")
        return record

    def event_receipt(self, project_id: str, event_id: str) -> EventInboxReceipt:
        """Return the compact acceptance/processing receipt for an event."""

        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"event not found: {project_id}/{event_id}")
        return self._event_receipt(row)

    def reconcile_suspended_processed_event(
        self,
        event: EventEnvelope,
        subject_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
    ) -> EventInboxReceipt | None:
        """Permit only an exact processed-event ack retry after suspension."""

        payload_digest = hashlib.sha256(event.to_json().encode("utf-8")).hexdigest()
        with self._lock:
            row = self._connection.execute(
                """SELECT item.* FROM event_inbox AS item
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
                     AND project.status = 'suspended'
                     AND project.repository_fingerprint = ?
                     AND project.config_sha256 = ?
                     AND project.backend_api_version = ?
                     AND binding.status = 'active'
                     AND revocation.grant_id IS NULL
                   ORDER BY grant_row.granted_at DESC LIMIT 1""",
                (
                    subject_id,
                    event.project_id,
                    event.event_id,
                    repository_fingerprint,
                    config_sha256,
                    backend_api_version,
                ),
            ).fetchone()
        if (
            row is None
            or row["status"] != EventInboxStatus.PROCESSED.value
            or row["payload_sha256"] != payload_digest
            or row["source_id"] != event.source_id
            or row["source_sequence"] != event.source_sequence
        ):
            return None
        return self._event_receipt(row)

    def reconcile_deregistered_processed_event(
        self,
        event: EventEnvelope,
    ) -> EventInboxReceipt | None:
        """Return an exact processed drain receipt after binding cutover.

        This read-only path lets a trusted source clear its durable outbox after
        the original response was lost. It cannot admit or process an event.
        """

        payload_digest = hashlib.sha256(event.to_json().encode("utf-8")).hexdigest()
        with self._lock:
            row = self._connection.execute(
                """SELECT inbox.* FROM event_inbox AS inbox
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = inbox.project_id
                   JOIN project_registry AS project
                     ON project.project_id = inbox.project_id
                   JOIN consumer_binding_audit AS cutover
                     ON cutover.project_id = binding.project_id
                    AND cutover.revision = binding.revision
                   LEFT JOIN project_retirement_tombstones AS retirement
                     ON retirement.project_id = inbox.project_id
                   WHERE inbox.project_id = ? AND inbox.event_id = ?
                     AND inbox.status = 'processed'
                     AND project.status = 'active'
                     AND retirement.project_id IS NULL
                     AND binding.status IN ('deregistered', 'active')
                     AND cutover.action IN ('deregistered', 'reenrolled')
                     AND inbox.received_at <= cutover.created_at
                   LIMIT 1""",
                (event.project_id, event.event_id),
            ).fetchone()
        if row is None or row["source_id"] != event.source_id or row[
            "source_sequence"
        ] != event.source_sequence:
            return None
        identity_matches = (
            row["idempotency_sha256"] == event.idempotency_sha256
            if row["idempotency_sha256"] is not None
            else row["payload_sha256"] == payload_digest
        )
        return self._event_receipt(row) if identity_matches else None

    def reconcile_retired_processed_event(
        self,
        event: EventEnvelope,
        expected_source_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
    ) -> EventInboxReceipt | None:
        """Return only an exact pre-retirement receipt for outbox recovery.

        Retirement permanently blocks new writes. A trusted source may still
        need the original acknowledgement when Curator committed an event but
        its response was lost immediately before retirement. This read-only
        path is bound to the tombstoned source epoch and current project config.
        """

        self._validate_access_identity(event.project_id, "project_id")
        self._validate_access_identity(event.event_id, "event_id")
        self._validate_access_identity(expected_source_id, "expected_source_id")
        if not re.fullmatch(r"[0-9a-f]{64}", repository_fingerprint):
            raise ValueError("repository_fingerprint must be lowercase SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", config_sha256):
            raise ValueError("config_sha256 must be lowercase SHA-256")
        if not is_exact_int(backend_api_version) or backend_api_version < 1:
            raise ValueError("backend_api_version must be a positive integer")
        payload_digest = hashlib.sha256(event.to_json().encode("utf-8")).hexdigest()
        with self._lock:
            row = self._connection.execute(
                """SELECT inbox.* FROM event_inbox AS inbox
                   JOIN project_registry AS project
                     ON project.project_id = inbox.project_id
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = inbox.project_id
                   JOIN project_retirement_tombstones AS retirement
                     ON retirement.project_id = inbox.project_id
                   JOIN consumer_binding_audit AS cutover
                     ON cutover.project_id = binding.project_id
                    AND cutover.revision = binding.revision
                   WHERE inbox.project_id = ? AND inbox.event_id = ?
                     AND inbox.status = 'processed'
                     AND inbox.source_id = ?
                     AND inbox.received_at <= retirement.retired_at
                     AND project.status = 'suspended'
                     AND project.repository_fingerprint = ?
                     AND project.config_sha256 = ?
                     AND project.backend_api_version = ?
                     AND binding.status IN ('deregistration_pending', 'deregistered')
                     AND binding.source_epoch = retirement.source_epoch
                     AND cutover.action IN ('deregistration_pending', 'deregistered')
                     AND cutover.source_epoch = retirement.source_epoch
                   LIMIT 1""",
                (
                    event.project_id,
                    event.event_id,
                    expected_source_id,
                    repository_fingerprint,
                    config_sha256,
                    backend_api_version,
                ),
            ).fetchone()
        if (
            row is None
            or row["source_id"] != event.source_id
            or row["source_sequence"] != event.source_sequence
        ):
            return None
        identity_matches = (
            row["idempotency_sha256"] == event.idempotency_sha256
            if row["idempotency_sha256"] is not None
            else row["payload_sha256"] == payload_digest
        )
        return self._event_receipt(row) if identity_matches else None

    def _sqlite_physical_storage_usage(self) -> SQLitePhysicalStorageUsage:
        """Attribute main-database table/index pages without exposing rows."""

        page_size = int(self._connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(self._connection.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(
            self._connection.execute("PRAGMA freelist_count").fetchone()[0]
        )
        database_bytes = page_size * page_count
        database_path = Path(self.database) if self.database != ":memory:" else None
        database_file_bytes = (
            self._regular_file_size(database_path) if database_path is not None else None
        )
        wal_file_bytes = (
            self._regular_file_size(Path(f"{self.database}-wal"))
            if self.database != ":memory:"
            else None
        )
        combined_file_bytes = (
            database_file_bytes + wal_file_bytes
            if database_file_bytes is not None and wal_file_bytes is not None
            else None
        )
        warning_status = (
            "unknown"
            if combined_file_bytes is None
            else (
                "warning"
                if combined_file_bytes > SQLITE_DATABASE_WARNING_THRESHOLD_BYTES
                else "below_threshold"
            )
        )
        file_usage = SQLiteDatabaseFileUsage(
            database_bytes=database_file_bytes,
            wal_file_bytes=wal_file_bytes,
            combined_bytes=combined_file_bytes,
            warning_status=warning_status,
        )
        try:
            rows = self._connection.execute(
                """SELECT m.tbl_name AS class_name,
                          COUNT(*) AS page_count,
                          SUM(d.pgsize) AS allocated_bytes,
                          SUM(d.payload) AS payload_bytes,
                          SUM(d.unused) AS unused_bytes
                   FROM dbstat('main') AS d
                   JOIN sqlite_master AS m ON m.name = d.name
                   WHERE m.type IN ('table', 'index')
                     AND m.tbl_name NOT LIKE 'sqlite_%'
                   GROUP BY m.tbl_name
                   ORDER BY m.tbl_name"""
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: dbstat" not in str(exc).lower() and (
                "no such module: dbstat" not in str(exc).lower()
            ):
                raise
            return SQLitePhysicalStorageUsage(
                status="unsupported",
                classes=(),
                pages=SQLiteDatabasePageUsage(
                    page_size=page_size,
                    page_count=page_count,
                    freelist_page_count=freelist_count,
                    allocated_bytes=database_bytes,
                    attributed_btree_bytes=None,
                    unattributed_database_bytes=None,
                ),
                files=file_usage,
            )
        classes = tuple(
            StoragePhysicalClassUsage(
                class_name=row["class_name"],
                page_count=int(row["page_count"]),
                allocated_bytes=int(row["allocated_bytes"]),
                payload_bytes=int(row["payload_bytes"]),
                unused_bytes=int(row["unused_bytes"]),
            )
            for row in rows
        )
        attributed_bytes = sum(item.allocated_bytes for item in classes)
        if attributed_bytes > database_bytes:
            raise sqlite3.DatabaseError("dbstat page attribution exceeds database pages")
        return SQLitePhysicalStorageUsage(
            status="available",
            classes=classes,
            pages=SQLiteDatabasePageUsage(
                page_size=page_size,
                page_count=page_count,
                freelist_page_count=freelist_count,
                allocated_bytes=database_bytes,
                attributed_btree_bytes=attributed_bytes,
                unattributed_database_bytes=database_bytes - attributed_bytes,
            ),
            files=file_usage,
        )
