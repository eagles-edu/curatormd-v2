"""Owner-audited alpha recovery operations for pending SDE proposals."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json

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

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    def record_hermes_codex_turn_event(
        self,
        project_id: str,
        profile_id: str,
        session_id: str,
        turn_id: str,
        event_id: str,
        event_type: str,
        occurred_at: str,
        outcome: str | None = None,
    ) -> dict[str, object]:
        """Persist one bounded turn boundary with a replay-stable receipt."""

        values = (project_id, profile_id, session_id, turn_id, event_id)
        for value, name in zip(
            values, ("project_id", "profile_id", "session_id", "turn_id", "event_id")
        ):
            self._validate_access_identity(value, name)
        if event_type not in {"start", "end"}:
            raise ValueError("event_type must be start or end")
        if not 1 <= len(occurred_at) <= 64:
            raise ValueError("occurred_at must be a bounded timestamp")
        if "\n" in occurred_at or "\r" in occurred_at:
            raise ValueError("occurred_at must be a single line")
        validate_safe_text(occurred_at, "codex_turn.occurred_at")
        if event_type == "end" and outcome not in {
            "completed", "interrupted", "failed", "unknown"
        }:
            raise ValueError("end outcome is unsupported")
        if event_type == "start" and outcome is not None:
            raise ValueError("start events cannot include an outcome")
        payload = {
            "project_id": project_id, "profile_id": profile_id,
            "session_id": session_id, "turn_id": turn_id,
            "event_type": event_type, "occurred_at": occurred_at,
            "outcome": outcome,
        }
        payload_sha = hashlib.sha256(_json_dump(payload).encode("utf-8")).hexdigest()
        with self._transaction() as connection:
            existing = connection.execute(
                """SELECT payload_sha256, receipt_json
                   FROM hermes_codex_telemetry_receipts
                   WHERE project_id = ? AND event_id = ?""",
                (project_id, event_id),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != payload_sha:
                    raise ConflictError("Codex telemetry event ID was reused with changed data")
                return json.loads(existing["receipt_json"])
            if event_type == "start":
                row = connection.execute(
                    """SELECT started_at FROM hermes_codex_turns
                       WHERE project_id = ? AND profile_id = ? AND session_id = ?
                         AND turn_id = ?""",
                    (project_id, profile_id, session_id, turn_id),
                ).fetchone()
                if row is not None and row["started_at"] != occurred_at:
                    raise ConflictError("Codex turn start conflicts with its saved observation")
                connection.execute(
                    """INSERT INTO hermes_codex_turns
                       (project_id, profile_id, session_id, turn_id, started_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(project_id, profile_id, session_id, turn_id)
                       DO NOTHING""",
                    (project_id, profile_id, session_id, turn_id, occurred_at),
                )
            else:
                cursor = connection.execute(
                    """UPDATE hermes_codex_turns SET ended_at = ?, outcome = ?
                       WHERE project_id = ? AND profile_id = ? AND session_id = ?
                         AND turn_id = ? AND ended_at IS NULL""",
                    (occurred_at, outcome, project_id, profile_id, session_id, turn_id),
                )
                row = connection.execute(
                    """SELECT ended_at, outcome FROM hermes_codex_turns
                       WHERE project_id = ? AND profile_id = ? AND session_id = ?
                         AND turn_id = ?""",
                    (project_id, profile_id, session_id, turn_id),
                ).fetchone()
                if row is None:
                    raise NotFoundError("Codex turn start has not been observed")
                if cursor.rowcount == 0 and (
                    row["ended_at"] != occurred_at or row["outcome"] != outcome
                ):
                    raise ConflictError("Codex turn end conflicts with its saved observation")
            receipt: dict[str, object] = {
                "project_id": project_id, "event_id": event_id,
                "status": "processed", "profile_id": profile_id,
                "session_id": session_id, "turn_id": turn_id,
                "event_type": event_type,
            }
            connection.execute(
                """INSERT INTO hermes_codex_telemetry_receipts
                   (project_id, event_id, payload_sha256, receipt_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, event_id, payload_sha, _json_dump(receipt), utc_now()),
            )
        return receipt

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    def link_hermes_codex_turn_goal(
        self,
        project_id: str,
        profile_id: str,
        session_id: str,
        turn_id: str,
        goal_id: str,
        event_id: str,
        source_tool: str,
    ) -> dict[str, object]:
        """Link a goal only after the caller observed its successful task call."""

        for value, name in (
            (project_id, "project_id"), (profile_id, "profile_id"),
            (session_id, "session_id"), (turn_id, "turn_id"),
            (goal_id, "goal_id"), (event_id, "event_id"),
        ):
            self._validate_access_identity(value, name)
        if source_tool not in {
            "goal_start", "goal_activate", "goal_finish", "goal_defer",
            "goal_block", "fact_record", "goal_reopen", "goal_cancel",
            "goal_supersede", "goal_amend_criteria",
        }:
            raise ValueError("source_tool is not a Curator task lifecycle or fact call")
        payload = {
            "project_id": project_id, "profile_id": profile_id,
            "session_id": session_id, "turn_id": turn_id,
            "goal_id": goal_id, "source_tool": source_tool,
        }
        payload_sha = hashlib.sha256(_json_dump(payload).encode("utf-8")).hexdigest()
        with self._transaction() as connection:
            existing = connection.execute(
                """SELECT payload_sha256, receipt_json
                   FROM hermes_codex_telemetry_receipts
                   WHERE project_id = ? AND event_id = ?""",
                (project_id, event_id),
            ).fetchone()
            if existing is not None:
                if existing["payload_sha256"] != payload_sha:
                    raise ConflictError("Codex telemetry event ID was reused with changed data")
                return json.loads(existing["receipt_json"])
            turn = connection.execute(
                """SELECT 1 FROM hermes_codex_turns
                   WHERE project_id = ? AND profile_id = ? AND session_id = ?
                     AND turn_id = ?""",
                (project_id, profile_id, session_id, turn_id),
            ).fetchone()
            goal = connection.execute(
                "SELECT 1 FROM goals WHERE project_id = ? AND goal_id = ?",
                (project_id, goal_id),
            ).fetchone()
            if turn is None or goal is None:
                raise NotFoundError("Codex turn or project goal is unavailable")
            connection.execute(
                """INSERT INTO hermes_codex_turn_links
                   (project_id, profile_id, session_id, turn_id, goal_id,
                    source_tool, linked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, profile_id, session_id, turn_id, goal_id)
                   DO NOTHING""",
                (project_id, profile_id, session_id, turn_id, goal_id,
                 source_tool, utc_now()),
            )
            receipt: dict[str, object] = {
                "project_id": project_id, "event_id": event_id,
                "status": "processed", "profile_id": profile_id,
                "session_id": session_id, "turn_id": turn_id,
                "goal_id": goal_id,
            }
            connection.execute(
                """INSERT INTO hermes_codex_telemetry_receipts
                   (project_id, event_id, payload_sha256, receipt_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_id, event_id, payload_sha, _json_dump(receipt), utc_now()),
            )
        return receipt

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
