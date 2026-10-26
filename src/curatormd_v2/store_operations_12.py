"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    MAX_GOAL_LIST_PAGE,
    SDECandidate,
    SDEStatus,
    is_exact_int,
)
from .store_operations_11 import StoreOperations4Part1

class StoreOperations4(StoreOperations4Part1):
    """Continuation of StoreOperations4 operations."""


    def list_sde_candidate_page(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
        status: SDEStatus | None = None,
    ) -> tuple[int, tuple[SDECandidate, ...]]:
        """Return one bounded page of a goal's SDE candidates and exact count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT s.candidate_id, s.created_at FROM sde_candidates AS s
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ?
                       AND (? IS NULL OR s.status = ?)
                   ), page AS (
                     SELECT candidate_id FROM selected
                     ORDER BY created_at, candidate_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.candidate_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    goal_id,
                    project_id,
                    status.value if status is not None else None,
                    status.value if status is not None else None,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["candidate_id"] is not None)
        return total, tuple(
            self.get_sde_candidate(row["candidate_id"], project_id)
            for row in page_rows
        )

    def pending_sde_candidates(
        self, project_id: str, limit: int = 100
    ) -> tuple[SDECandidate, ...]:
        """List a bounded, project-scoped review queue in creation order."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """SELECT s.candidate_id FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ? AND s.status = ?
                   ORDER BY s.created_at, s.candidate_id LIMIT ?""",
                (project_id, SDEStatus.PENDING_REVIEW.value, limit),
            ).fetchall()
        return tuple(
            self.get_sde_candidate(row["candidate_id"], project_id) for row in rows
        )
