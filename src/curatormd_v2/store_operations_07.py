"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactStatus,
    ConflictError,
    ExpiryPurgeReceipt,
    FactArchiveReceipt,
    FactCapacityError,
    FactCompactionApprovalRequest,
    FactCompactionProposal,
    FactKind,
    GoalCard,
    GoalListCapacityError,
    GoalStatus,
    MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
    MAX_FACT_COMPACTION_BATCH_FACTS,
    MAX_FACT_COMPACTION_SOURCE_BYTES,
    MAX_GOAL_LIST_PAGE,
    NotFoundError,
    PURGE_RETRY_BASE_SECONDS,
    PURGE_RETRY_MAX_SECONDS,
    PurgeFailureCode,
    PurgeStatus,
    UTC,
    _PURGE_APPROVAL_INVALIDATING_ERRORS,
    _PreparedFactArchive,
    _json_dump,
    datetime,
    hashlib,
    is_exact_int,
    json,
    new_id,
    sqlite3,
    timedelta,
    utc_now,
    validate_safe_text,
    zlib,
)
from .store_operations_06 import StoreOperations2Part0

class StoreOperations2(StoreOperations2Part0):
    """Continuation of StoreOperations2 operations."""


    def record_expiry_purge_result(
        self,
        receipt_id: str,
        path: str,
        status: ArtifactStatus,
        error: str | None,
        project_id: str,
    ) -> ExpiryPurgeReceipt:
        """Persist retry-safe deletion outcome and clear age after success."""

        if status not in {ArtifactStatus.FAILED, ArtifactStatus.PURGED}:
            raise ValueError("expiry purge result must be failed or purged")
        allowed_errors = {
            code.value
            for code in PurgeFailureCode
            if code is not PurgeFailureCode.LEGACY_FAILURE_DETAIL_REDACTED
        }
        if (status is ArtifactStatus.FAILED and error not in allowed_errors) or (
            status is ArtifactStatus.PURGED and error is not None
        ):
            raise ValueError("expiry purge result has an invalid content-free error")
        with self._transaction() as connection:
            target = connection.execute(
                """SELECT t.sha256, t.occurrence_id, t.approval_stale FROM expiry_purge_targets AS t
                   JOIN expiry_purge_receipts AS r ON r.receipt_id = t.receipt_id
                   WHERE t.receipt_id = ? AND t.path = ? AND r.project_id = ?""",
                (receipt_id, path, project_id),
            ).fetchone()
            if target is None:
                raise NotFoundError("expiry purge target not found")
            if bool(target["approval_stale"]):
                raise ConflictError("legacy expiry approval requires fresh inventory review")
            next_attempt_at = None
            if status is ArtifactStatus.FAILED:
                attempts = int(
                    connection.execute(
                        "SELECT attempts FROM expiry_purge_targets "
                        "WHERE receipt_id = ? AND path = ?",
                        (receipt_id, path),
                    ).fetchone()["attempts"]
                )
                delay = min(
                    PURGE_RETRY_BASE_SECONDS * (2 ** min(max(attempts - 1, 0), 16)),
                    PURGE_RETRY_MAX_SECONDS,
                )
                next_attempt_at = (
                    datetime.now(UTC) + timedelta(seconds=delay)
                ).isoformat(timespec="microseconds")
            approval_stale = int(
                status is ArtifactStatus.FAILED
                and error in _PURGE_APPROVAL_INVALIDATING_ERRORS
            )
            if approval_stale:
                next_attempt_at = None
            connection.execute(
                """UPDATE expiry_purge_targets SET status = ?, error = ?,
                   next_attempt_at = ?, approval_stale = MAX(approval_stale, ?)
                   WHERE receipt_id = ? AND path = ?""",
                (
                    status.value, error, next_attempt_at, approval_stale,
                    receipt_id, path,
                ),
            )
            if status is ArtifactStatus.PURGED:
                connection.execute(
                    "DELETE FROM staging_artifact_times "
                    "WHERE project_id = ? AND path = ? AND sha256 = ? "
                    "AND occurrence_id = ?",
                    (project_id, path, target["sha256"], target["occurrence_id"]),
                )
            pending = int(
                connection.execute(
                    "SELECT COUNT(*) FROM expiry_purge_targets "
                    "WHERE receipt_id = ? AND status != ?",
                    (receipt_id, ArtifactStatus.PURGED.value),
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE expiry_purge_receipts SET status = ?, updated_at = ? "
                "WHERE receipt_id = ? AND project_id = ?",
                (
                    PurgeStatus.PURGE_PENDING.value if pending else PurgeStatus.COMPLETE.value,
                    utc_now(),
                    receipt_id,
                    project_id,
                ),
            )
        return self.expiry_purge_receipt(receipt_id, project_id)

    def add_goal(
        self, goal: GoalCard, *, source_event_id: str | None = None
    ) -> None:
        """Persist a goal and its initial immutable criteria version."""

        if source_event_id is not None and (
            not source_event_id.strip() or len(source_event_id) > 128
        ):
            raise ValueError("source_event_id must be a bounded opaque identifier")
        if source_event_id is not None:
            validate_safe_text(source_event_id, "source_event_id")

        criteria = [
            {"criterion_id": item.criterion_id, "description": item.description}
            for item in goal.success_criteria
        ]
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO goals
                   (goal_id, project_id, problem, criteria_json, owner, checklist_id,
                    checklist_version, checklist_source_text, parent_goal_id,
                    depends_on_json, criteria_revision, lifecycle_revision,
                    superseded_by_goal_id, initial_status, source_event_id,
                    status, next_action, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    goal.goal_id,
                    goal.project_id,
                    goal.problem,
                    _json_dump(criteria),
                    goal.owner,
                    goal.checklist_id,
                    goal.checklist_version,
                    goal.checklist_source_text,
                    goal.parent_goal_id,
                    _json_dump(list(goal.depends_on_goal_ids)),
                    goal.criteria_revision,
                    goal.lifecycle_revision,
                    goal.superseded_by_goal_id,
                    goal.status.value,
                    source_event_id,
                    goal.status.value,
                    goal.next_action,
                    goal.created_at,
                    goal.updated_at,
                ),
            )
            connection.execute(
                "INSERT INTO goal_criteria_versions "
                "(goal_id, revision, criteria_json, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    goal.goal_id,
                    goal.criteria_revision,
                    _json_dump(criteria),
                    "Initial criteria",
                    goal.created_at,
                ),
            )

    def list_goals(
        self,
        statuses: tuple[GoalStatus, ...] = (),
        project_id: str | None = None,
    ) -> tuple[GoalCard, ...]:
        """List goals filtered by lifecycle state and optional project scope."""

        status_values = json.dumps([status.value for status in statuses])
        query = """SELECT goal_id, project_id FROM goals
                   WHERE (? IS NULL OR project_id = ?)
                     AND (json_array_length(?) = 0 OR status IN
                          (SELECT value FROM json_each(?)))
                   ORDER BY created_at, goal_id LIMIT ?"""
        with self._lock:
            rows = self._connection.execute(
                query,
                (
                    project_id,
                    project_id,
                    status_values,
                    status_values,
                    MAX_GOAL_LIST_PAGE + 1,
                ),
            ).fetchall()
        if len(rows) > MAX_GOAL_LIST_PAGE:
            raise GoalListCapacityError(
                "unpaged goal listing exceeds 100 records; use goal_list_page"
            )
        return tuple(
            self.get_goal(row["goal_id"], row["project_id"]) for row in rows
        )

    def list_goal_page(
        self,
        project_id: str,
        offset: int,
        limit: int,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> tuple[int, tuple[GoalCard, ...]]:
        """Return one bounded project-scoped goal page and its total count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        status_values = json.dumps([status.value for status in statuses])
        with self._lock:
            rows = self._connection.execute(
                """WITH project_goals AS (
                     SELECT goal_id, project_id, created_at FROM goals
                     WHERE project_id = ?
                       AND (json_array_length(?) = 0 OR status IN
                            (SELECT value FROM json_each(?)))
                   ), page AS (
                     SELECT goal_id, project_id FROM project_goals
                     ORDER BY created_at, goal_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM project_goals) AS total,
                          page.goal_id, page.project_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (project_id, status_values, status_values, limit, offset),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["goal_id"] is not None)
        return total, tuple(
            self.get_goal(row["goal_id"], project_id) for row in page_rows
        )

    def list_child_goals(
        self, parent_goal_id: str, project_id: str
    ) -> tuple[GoalCard, ...]:
        """List direct children without crossing the project boundary."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT goal_id FROM goals WHERE parent_goal_id = ? AND project_id = ? "
                "ORDER BY created_at, goal_id",
                (parent_goal_id, project_id),
            ).fetchall()
        return tuple(
            self.get_goal(row["goal_id"], project_id) for row in rows
        )

    def list_child_goal_page(
        self,
        parent_goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> tuple[int, tuple[GoalCard, ...]]:
        """Return one bounded, project-scoped page of direct child cards."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        status_values = json.dumps([status.value for status in statuses])
        with self._lock:
            rows = self._connection.execute(
                """WITH project_children AS (
                     SELECT goal_id, created_at FROM goals
                     WHERE project_id = ? AND parent_goal_id = ?
                       AND (json_array_length(?) = 0 OR status IN
                            (SELECT value FROM json_each(?)))
                   ), page AS (
                     SELECT goal_id FROM project_children
                     ORDER BY created_at, goal_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM project_children) AS total,
                          page.goal_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    project_id,
                    parent_goal_id,
                    status_values,
                    status_values,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["goal_id"] is not None)
        return total, tuple(
            self.get_goal(row["goal_id"], project_id) for row in page_rows
        )

    def propose_fact_compaction(
        self, goal_id: str, project_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Preview the oldest eligible routine facts without mutating storage."""

        if not is_exact_int(max_facts) or not 1 <= max_facts <= MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError(
                f"max_facts must be between 1 and {MAX_FACT_COMPACTION_BATCH_FACTS}"
            )
        with self._lock:
            goal = self._connection.execute(
                "SELECT 1 FROM goals WHERE goal_id = ? AND project_id = ?",
                (goal_id, project_id),
            ).fetchone()
            if goal is None:
                raise NotFoundError(f"goal not found: {goal_id}")
            rows = self._connection.execute(
                """SELECT f.* FROM facts AS f JOIN goals AS g
                   ON g.goal_id = f.goal_id
                   WHERE f.goal_id = ? AND g.project_id = ?
                   ORDER BY f.created_at, f.fact_id""",
                (goal_id, project_id),
            ).fetchall()
            candidates = self._connection.execute(
                "SELECT fact_ids_json FROM sde_candidates WHERE goal_id = ?",
                (goal_id,),
            ).fetchall()
        protected_ids = {
            fact_id
            for candidate in candidates
            for fact_id in json.loads(candidate["fact_ids_json"])
        }
        eligible = tuple(
            fact
            for fact in (self._fact_from_row(row) for row in rows)
            if fact.kind in {FactKind.RESEARCH, FactKind.ADVICE}
            and fact.criterion_id is None
            and not fact.evidence
            and fact.fact_id not in protected_ids
        )[:max_facts]
        if not eligible:
            raise ConflictError("no eligible routine facts are available to archive")
        source = self._fact_archive_source(eligible)
        if len(source) > MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ConflictError("eligible facts exceed the bounded archive proposal size")
        compressed_size = len(zlib.compress(source, level=9))
        if compressed_size > MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ConflictError("compressed proposal exceeds the archive batch size")
        return FactCompactionProposal(
            compaction_id=new_id(),
            project_id=project_id,
            goal_id=goal_id,
            facts=eligible,
            source_sha256=hashlib.sha256(source).hexdigest(),
            source_bytes=len(source),
            estimated_compressed_bytes=compressed_size,
        )

    def _read_existing_compaction_receipt(
        self,
        connection: sqlite3.Connection,
        approval: FactCompactionApprovalRequest,
    ) -> FactArchiveReceipt | None:
        """Return an exact idempotent replay or reject a reused compaction ID."""

        row = connection.execute(
            "SELECT * FROM fact_archives WHERE compaction_id = ?",
            (approval.compaction_id,),
        ).fetchone()
        if row is None:
            return None
        receipt = self._fact_archive_receipt(row)
        original = (
            receipt.project_id,
            receipt.goal_id,
            receipt.fact_ids,
            receipt.source_sha256,
            receipt.reviewer_id,
            receipt.approval_reason,
        )
        requested = (
            approval.project_id,
            approval.goal_id,
            approval.fact_ids,
            approval.source_sha256,
            approval.reviewer_id,
            approval.approval_reason,
        )
        if original != requested:
            raise ConflictError("compaction ID was reused for different approval")
        return receipt

    def _prepare_fact_archive(
        self,
        connection: sqlite3.Connection,
        approval: FactCompactionApprovalRequest,
    ) -> _PreparedFactArchive:
        """Load, revalidate, and hash exactly the facts named by the approval."""

        rows = connection.execute(
            """SELECT f.* FROM facts AS f JOIN goals AS g
               ON g.goal_id = f.goal_id
               WHERE f.fact_id IN (SELECT value FROM json_each(?))
                 AND f.goal_id = ? AND g.project_id = ?""",
            (json.dumps(approval.fact_ids), approval.goal_id, approval.project_id),
        ).fetchall()
        fact_by_id = {row["fact_id"]: self._fact_from_row(row) for row in rows}
        if set(fact_by_id) != set(approval.fact_ids):
            raise ConflictError("proposed facts changed or are no longer active")
        facts = tuple(
            sorted(fact_by_id.values(), key=lambda fact: (fact.created_at, fact.fact_id))
        )
        if tuple(fact.fact_id for fact in facts) != approval.fact_ids:
            raise ConflictError("fact IDs do not match the canonical proposal order")
        if any(
            fact.kind not in {FactKind.RESEARCH, FactKind.ADVICE}
            or fact.criterion_id is not None
            or fact.evidence
            for fact in facts
        ):
            raise ConflictError("approval includes a non-routine or evidence-bearing fact")
        self._reject_sde_protected_facts(connection, approval)

        source = self._fact_archive_source(facts)
        if hashlib.sha256(source).hexdigest() != approval.source_sha256:
            raise ConflictError("fact source changed since the proposal was reviewed")
        if len(source) > MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ConflictError("fact archive exceeds its source size limit")
        compressed = zlib.compress(source, level=9)
        return _PreparedFactArchive(
            facts=facts,
            source=source,
            compressed=compressed,
            archive_sha256=hashlib.sha256(compressed).hexdigest(),
            created_at=utc_now(),
        )

    def _ensure_fact_archive_capacity(
        self,
        connection: sqlite3.Connection,
        approval: FactCompactionApprovalRequest,
        prepared: _PreparedFactArchive,
    ) -> None:
        """Enforce the project archive budget before deleting active facts."""

        usage = connection.execute(
            """SELECT COALESCE(SUM(
                     length(CAST(compaction_id AS BLOB)) +
                     length(CAST(schema_version AS TEXT)) +
                     length(CAST(goal_id AS BLOB)) +
                     length(CAST(source_sha256 AS BLOB)) +
                     length(CAST(archive_sha256 AS BLOB)) +
                     length(CAST(source_bytes AS TEXT)) +
                     length(CAST(compressed_bytes AS TEXT)) +
                     length(CAST(fact_count AS TEXT)) +
                     length(CAST(reviewer_id AS BLOB)) +
                     length(CAST(approval_reason AS BLOB)) +
                     length(CAST(created_at AS BLOB)) + compressed_bytes
                   ), 0) + COALESCE((
                     SELECT SUM(length(CAST(fact_id AS BLOB)) +
                                length(CAST(compaction_id AS BLOB)) +
                                length(CAST(project_id AS BLOB)) +
                                length(CAST(goal_id AS BLOB)) +
                                length(CAST(dedupe_key AS BLOB)) +
                                length(CAST(created_at AS BLOB)))
                     FROM fact_archive_items WHERE project_id = ?
                   ), 0) AS bytes
               FROM fact_archives WHERE project_id = ?""",
            (approval.project_id, approval.project_id),
        ).fetchone()
        new_bytes = len(prepared.compressed) + sum(
            len(value.encode("utf-8"))
            for value in (
                approval.compaction_id,
                approval.project_id,
                approval.goal_id,
                approval.source_sha256,
                prepared.archive_sha256,
                str(len(prepared.source)),
                str(len(prepared.compressed)),
                str(len(prepared.facts)),
                "1",
                approval.reviewer_id,
                approval.approval_reason.strip(),
                prepared.created_at,
            )
        )
        new_bytes += sum(
            len(value.encode("utf-8"))
            for fact in prepared.facts
            for value in (
                fact.fact_id,
                approval.compaction_id,
                approval.project_id,
                approval.goal_id,
                self._fact_dedupe_key(fact),
                fact.created_at,
            )
        )
        if usage["bytes"] + new_bytes > MAX_FACT_ARCHIVE_BYTES_PER_PROJECT:
            raise FactCapacityError("project fact archive capacity reached")

    def _persist_fact_archive(
        self,
        connection: sqlite3.Connection,
        approval: FactCompactionApprovalRequest,
        prepared: _PreparedFactArchive,
    ) -> FactArchiveReceipt:
        """Write archive, item receipts, and active-row deletion atomically."""

        connection.execute(
            """INSERT INTO fact_archives
               (compaction_id, schema_version, project_id, goal_id, source_sha256,
                archive_sha256, source_bytes, compressed_bytes, fact_count, payload_zlib,
                reviewer_id, approval_reason, created_at)
               VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                approval.compaction_id,
                approval.project_id,
                approval.goal_id,
                approval.source_sha256,
                prepared.archive_sha256,
                len(prepared.source),
                len(prepared.compressed),
                len(prepared.facts),
                prepared.compressed,
                approval.reviewer_id,
                approval.approval_reason.strip(),
                prepared.created_at,
            ),
        )
        for fact in prepared.facts:
            connection.execute(
                """INSERT INTO fact_archive_items
                   (fact_id, compaction_id, project_id, goal_id, dedupe_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    fact.fact_id,
                    approval.compaction_id,
                    approval.project_id,
                    approval.goal_id,
                    self._fact_dedupe_key(fact),
                    fact.created_at,
                ),
            )
        connection.executemany(
            "DELETE FROM facts WHERE fact_id = ?",
            ((fact_id,) for fact_id in approval.fact_ids),
        )
        row = connection.execute(
            "SELECT * FROM fact_archives WHERE compaction_id = ?",
            (approval.compaction_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("inserted fact archive could not be read back")
        return self._fact_archive_receipt(row)

    def list_fact_archive_receipts(
        self,
        goal_id: str,
        project_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read bounded archive receipts and verify every compressed payload."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if not is_exact_int(limit) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM fact_archives
                   WHERE goal_id = ? AND project_id = ?
                   ORDER BY created_at, compaction_id LIMIT ? OFFSET ?""",
                (goal_id, project_id, limit, offset),
            ).fetchall()
        return tuple(self._fact_archive_receipt(row) for row in rows)
