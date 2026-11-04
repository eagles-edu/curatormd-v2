"""Owner-audited alpha recovery operations for pending SDE proposals."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib

from .store_support_01 import (
    ConflictError,
    NotFoundError,
    SDEStatus,
    SDEWithdrawal,
    _json_dump,
    new_id,
    utc_now,
    validate_safe_text,
)
from .store_operations_14 import StoreOperations5


class StoreOperations6(StoreOperations5):
    """Append-only withdrawal receipts and queue removal for alpha recovery."""

    def withdraw_sde_candidates(
        self,
        candidate_ids: tuple[str, ...],
        project_id: str,
        reviewer_id: str,
        rationale: str,
    ) -> tuple[SDEWithdrawal, ...]:
        """Withdraw an exact bounded candidate set without deleting its source facts."""

        if not candidate_ids or len(candidate_ids) > 100:
            raise ValueError("withdrawal requires 1-100 candidate IDs")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("withdrawal candidate IDs must be unique")
        validate_safe_text(rationale, "sde_withdrawal.rationale")
        if not rationale.strip() or len(rationale) > 1000:
            raise ValueError("withdrawal rationale must contain 1-1000 characters")
        if "\n" in rationale or "\r" in rationale:
            raise ValueError("withdrawal rationale must be a single line")
        validate_safe_text(reviewer_id, "sde_withdrawal.reviewer_id")
        if not reviewer_id.strip() or len(reviewer_id) > 128:
            raise ValueError("withdrawal reviewer ID must contain 1-128 characters")

        receipts: list[SDEWithdrawal] = []
        with self._transaction() as connection:
            for candidate_id in candidate_ids:
                row = connection.execute(
                    """SELECT s.* FROM sde_candidates AS s
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.candidate_id = ? AND g.project_id = ?""",
                    (candidate_id, project_id),
                ).fetchone()
                if row is None:
                    raise NotFoundError(f"SDE candidate not found: {candidate_id}")
                existing = connection.execute(
                    """SELECT * FROM sde_candidate_withdrawals
                       WHERE candidate_id = ?""",
                    (candidate_id,),
                ).fetchone()
                if row["status"] == SDEStatus.WITHDRAWN.value and existing is not None:
                    if (
                        existing["reviewer_id"] != reviewer_id
                        or existing["rationale"] != rationale.strip()
                    ):
                        raise ConflictError(
                            "withdrawal retry does not match its saved owner receipt"
                        )
                    receipts.append(SDEWithdrawal(**dict(existing)))
                    continue
                if row["status"] != SDEStatus.PENDING_REVIEW.value or existing is not None:
                    raise ConflictError("only pending SDE candidates can be withdrawn")

                candidate_snapshot = {
                    key: row[key]
                    for key in (
                        "candidate_id", "goal_id", "materiality", "rationale",
                        "impact", "retrieval_value", "fact_ids_json", "dedupe_key",
                        "created_at",
                    )
                }
                receipt = SDEWithdrawal(
                    withdrawal_id=new_id(),
                    project_id=project_id,
                    candidate_id=candidate_id,
                    reviewer_id=reviewer_id,
                    rationale=rationale.strip(),
                    candidate_sha256=hashlib.sha256(
                        _json_dump(candidate_snapshot).encode("utf-8")
                    ).hexdigest(),
                    created_at=utc_now(),
                )
                connection.execute(
                    """INSERT INTO sde_candidate_withdrawals
                       (withdrawal_id, project_id, candidate_id, reviewer_id,
                        rationale, candidate_sha256, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        receipt.withdrawal_id,
                        receipt.project_id,
                        receipt.candidate_id,
                        receipt.reviewer_id,
                        receipt.rationale,
                        receipt.candidate_sha256,
                        receipt.created_at,
                    ),
                )
                cursor = connection.execute(
                    """UPDATE sde_candidates SET status = ?
                       WHERE candidate_id = ? AND status = ?""",
                    (
                        SDEStatus.WITHDRAWN.value,
                        candidate_id,
                        SDEStatus.PENDING_REVIEW.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ConflictError("SDE candidate changed during withdrawal")
                receipts.append(receipt)
        return tuple(receipts)
