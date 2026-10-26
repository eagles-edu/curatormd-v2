"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactStatus,
    AuditReceipt,
    ConflictError,
    MAX_GOAL_LIST_PAGE,
    NotFoundError,
    PurgeOutcome,
    PurgeStatus,
    PurgeTargetResult,
    _PURGE_APPROVAL_INVALIDATING_ERRORS,
    is_exact_int,
    utc_now,
)
from .store_operations_08 import StoreOperations3Part0

class StoreOperations3(StoreOperations3Part0):
    """Continuation of StoreOperations3 operations."""


    def record_purge_result(
        self,
        receipt_id: str,
        path: str,
        result: PurgeTargetResult,
        project_id: str | None = None,
    ) -> AuditReceipt:
        """Persist one idempotent artifact purge result and refresh receipt state."""

        status = result.status
        error = result.error
        outcome = result.outcome
        if outcome is None:
            if status is ArtifactStatus.FAILED and error in _PURGE_APPROVAL_INVALIDATING_ERRORS:
                outcome = PurgeOutcome.CHANGED
            elif status is ArtifactStatus.FAILED:
                outcome = PurgeOutcome.FAILED
        self._validate_purge_result(status, error, outcome)

        with self._transaction() as connection:
            if project_id is not None and connection.execute(
                """SELECT 1 FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone() is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            target = connection.execute(
                """SELECT p.attempts, p.sha256, p.occurrence_id, p.approval_stale,
                          g.project_id
                   FROM purge_targets AS p
                   JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE p.receipt_id = ? AND p.path = ?""",
                (receipt_id, path),
            ).fetchone()
            if target is None:
                raise NotFoundError("purge target not found in receipt")
            if bool(target["approval_stale"]):
                raise ConflictError("legacy purge approval requires fresh inventory review")
            held = connection.execute(
                "SELECT retention_hold, hold_released_at FROM purge_targets "
                "WHERE receipt_id = ? AND path = ?",
                (receipt_id, path),
            ).fetchone()
            if held is None or (
                held["retention_hold"] is not None
                and held["hold_released_at"] is None
            ):
                raise ConflictError("held artifacts cannot record a purge result")
            approval_stale = int(
                status is ArtifactStatus.FAILED
                and error in _PURGE_APPROVAL_INVALIDATING_ERRORS
            )
            next_attempt_at = (
                None
                if approval_stale
                else self._purge_retry_at(status, int(target["attempts"]))
            )
            cursor = connection.execute(
                """UPDATE purge_targets SET status = ?, error = ?, next_attempt_at = ?,
                          approval_stale = MAX(approval_stale, ?), outcome = ?
                   WHERE receipt_id = ? AND path = ?""",
                (
                    status.value, error, next_attempt_at, approval_stale,
                    outcome.value if outcome is not None else None,
                    receipt_id, path,
                ),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("purge target not found in receipt")
            if status is ArtifactStatus.PURGED:
                connection.execute(
                    "DELETE FROM staging_artifact_times "
                    "WHERE project_id = ? AND path = ? AND sha256 = ? "
                    "AND occurrence_id = ?",
                    (
                        target["project_id"], path, target["sha256"],
                        target["occurrence_id"],
                    ),
                )
            self._refresh_purge_receipt_status(connection, receipt_id)
        return self.get_receipt(receipt_id, project_id)

    def pending_receipts(
        self, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List receipts whose artifact cleanup remains incomplete."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT receipt_id FROM audit_receipts WHERE purge_status = ? "
                    "ORDER BY created_at, receipt_id",
                    (PurgeStatus.PURGE_PENDING.value,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.purge_status = ? AND g.project_id = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (PurgeStatus.PURGE_PENDING.value, project_id),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def due_pending_purge_receipts(
        self, project_id: str, limit: int = 100
    ) -> tuple[AuditReceipt, ...]:
        """Return bounded, authorized-project receipts with at least one due target."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        with self._lock:
            rows = self._connection.execute(
                """SELECT r.receipt_id FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.purge_status = ? AND r.artifact_inventory_complete = 1
                     AND r.canonical_persisted = 1 AND g.project_id = ?
                     AND EXISTS (
                       SELECT 1 FROM cleanup_authorizations AS c
                       WHERE c.receipt_id = r.receipt_id
                         AND c.project_id = g.project_id
                         AND c.canonical_persisted = 1
                     )
                     AND EXISTS (
                       SELECT 1 FROM purge_targets AS p
                       WHERE p.receipt_id = r.receipt_id
                         AND p.status IN (?, ?)
                         AND p.approval_stale = 0
                         AND (p.retention_hold IS NULL OR p.hold_released_at IS NOT NULL)
                         AND (p.next_attempt_at IS NULL OR p.next_attempt_at <= ?)
                     )
                   ORDER BY r.created_at, r.receipt_id LIMIT ?""",
                (
                    PurgeStatus.PURGE_PENDING.value,
                    project_id,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                    now,
                    limit,
                ),
            ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def pending_receipts_for_goal(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List incomplete purge receipts for one goal and optional project."""

        with self._lock:
            if project_id is not None:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.goal_id = ? AND r.purge_status = ?
                       AND g.project_id = ? ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, PurgeStatus.PURGE_PENDING.value, project_id),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       WHERE s.goal_id = ? AND r.purge_status = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, PurgeStatus.PURGE_PENDING.value),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def receipt_page_for_goal(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, tuple[AuditReceipt, ...]]:
        """Return one bounded page of review receipts and exact total count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT r.receipt_id, r.created_at FROM audit_receipts AS r
                     JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ?
                   ), page AS (
                     SELECT receipt_id FROM selected
                     ORDER BY created_at, receipt_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.receipt_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (goal_id, project_id, limit, offset),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["receipt_id"] is not None)
        return total, tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in page_rows
        )

    def pending_receipt_page_for_goal(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, tuple[AuditReceipt, ...]]:
        """Return one bounded page of purge-pending receipts and exact count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT r.receipt_id, r.created_at FROM audit_receipts AS r
                     JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ? AND r.purge_status = ?
                   ), page AS (
                     SELECT receipt_id FROM selected
                     ORDER BY created_at, receipt_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.receipt_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    goal_id,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["receipt_id"] is not None)
        return total, tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in page_rows
        )

    def receipts_for_goal(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List all review receipts for one goal in creation order."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       WHERE s.goal_id = ? ORDER BY r.created_at, r.receipt_id""",
                    (goal_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.goal_id = ? AND g.project_id = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, project_id),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )
