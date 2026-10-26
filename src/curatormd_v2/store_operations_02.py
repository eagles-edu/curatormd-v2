"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactStatus,
    ConflictError,
    EventInboxStatus,
    Fact,
    FactArchiveReceipt,
    FactCompactionApprovalRequest,
    GoalStatus,
    GoalStatusStorageUsage,
    MAX_FACT_COMPACTION_BATCH_FACTS,
    Materiality,
    ProjectActivitySnapshot,
    ProjectOperationalCounts,
    PurgeStatus,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEStatus,
    _json_dump,
    hashlib,
    json,
    re,
    sqlite3,
    utc_now,
)
from .store_operations_01 import StoreOperations0Part1

class StoreOperations0(StoreOperations0Part1):
    """Continuation of StoreOperations0 operations."""


    @classmethod
    def _fact_archive_receipt(cls, row: sqlite3.Row) -> FactArchiveReceipt:
        facts = cls._decode_fact_archive(row)
        return FactArchiveReceipt(
            compaction_id=row["compaction_id"],
            archive_version=row["schema_version"],
            project_id=row["project_id"],
            goal_id=row["goal_id"],
            fact_ids=tuple(fact.fact_id for fact in facts),
            source_sha256=row["source_sha256"],
            archive_sha256=row["archive_sha256"],
            source_bytes=row["source_bytes"],
            compressed_bytes=row["compressed_bytes"],
            reviewer_id=row["reviewer_id"],
            approval_reason=row["approval_reason"],
            created_at=row["created_at"],
        )

    @classmethod
    def _fact_archive_source(cls, facts: tuple[Fact, ...]) -> bytes:
        return _json_dump([cls._fact_archive_record(fact) for fact in facts]).encode(
            "utf-8"
        )

    @staticmethod
    def _validate_fact_compaction_approval(
        approval: FactCompactionApprovalRequest,
    ) -> None:
        """Reject malformed approval identifiers before opening a transaction."""

        if not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", approval.compaction_id
        ):
            raise ValueError("compaction_id must be a bounded opaque identifier")
        if not approval.fact_ids or len(approval.fact_ids) > MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError("fact_ids must contain 1-64 IDs")
        if len(set(approval.fact_ids)) != len(approval.fact_ids):
            raise ValueError("fact_ids must be unique")
        if not re.fullmatch(r"[0-9a-f]{64}", approval.source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA-256")
        if not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", approval.reviewer_id
        ):
            raise ValueError("reviewer_id must be a bounded opaque identifier")
        if not approval.approval_reason.strip() or len(approval.approval_reason) > 1000:
            raise ValueError("approval_reason must contain 1-1000 characters")
        if "\n" in approval.approval_reason or "\r" in approval.approval_reason:
            raise ValueError("approval_reason must be a single line")

    @staticmethod
    def _reject_sde_protected_facts(
        connection: sqlite3.Connection,
        approval: FactCompactionApprovalRequest,
    ) -> None:
        """Keep facts supporting any SDE candidate out of compaction."""

        rows = connection.execute(
            "SELECT fact_ids_json FROM sde_candidates WHERE goal_id = ?",
            (approval.goal_id,),
        ).fetchall()
        protected_ids = {
            fact_id
            for candidate in rows
            for fact_id in json.loads(candidate["fact_ids_json"])
        }
        if protected_ids.intersection(approval.fact_ids):
            raise ConflictError("SDE-supported facts cannot be compacted")

    @staticmethod
    def _candidate_dedupe_key(candidate: SDECandidate) -> str:
        """Hash the goal, materiality, and selected fact set for idempotency."""

        payload = {
            "goal_id": candidate.goal_id,
            "materiality": candidate.materiality.value,
            "fact_ids": sorted(candidate.fact_ids),
        }
        return hashlib.sha256(_json_dump(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _candidate_from_row(row: sqlite3.Row) -> SDECandidate:
        return SDECandidate(
            goal_id=row["goal_id"],
            materiality=Materiality(row["materiality"]),
            rationale=row["rationale"],
            fact_ids=tuple(json.loads(row["fact_ids_json"])),
            impact=row["impact"],
            retrieval_value=row["retrieval_value"],
            candidate_id=row["candidate_id"],
            status=SDEStatus(row["status"]),
            created_at=row["created_at"],
        )

    def sde_candidate_status_counts(
        self, goal_id: str, project_id: str
    ) -> dict[str, int]:
        """Count one goal's candidate states without hydrating candidate payloads."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT s.status, COUNT(*) AS count FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE s.goal_id = ? AND g.project_id = ? GROUP BY s.status""",
                (goal_id, project_id),
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def project_operational_counts(self, project_id: str) -> ProjectOperationalCounts:
        """Count SDE, expiry, and purge work with bounded aggregate queries."""

        with self._lock:
            row = self._connection.execute(
                """SELECT
                     (SELECT COUNT(*) FROM sde_candidates AS s
                      JOIN goals AS g ON g.goal_id = s.goal_id
                      WHERE g.project_id = ? AND s.status = ?) AS pending_reviews,
                     (SELECT COUNT(*) FROM audit_receipts AS r
                      JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                      JOIN goals AS g ON g.goal_id = s.goal_id
                      WHERE g.project_id = ? AND r.purge_status = ?) AS pending_receipts,
                     (SELECT COUNT(*) FROM purge_targets AS p
                      JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
                      JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                      JOIN goals AS g ON g.goal_id = s.goal_id
                      WHERE g.project_id = ? AND r.purge_status = ?
                        AND p.status != ?) AS pending_artifacts,
                     (SELECT COUNT(*) FROM expiry_purge_receipts AS r
                      WHERE r.project_id = ? AND r.status = ?) AS pending_expiry_receipts,
                     (SELECT COUNT(*) FROM expiry_purge_targets AS t
                      JOIN expiry_purge_receipts AS r ON r.receipt_id = t.receipt_id
                      WHERE r.project_id = ? AND r.status = ?
                        AND t.status != ?) AS pending_expiry_artifacts""",
                (
                    project_id,
                    SDEStatus.PENDING_REVIEW.value,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    ArtifactStatus.PURGED.value,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    ArtifactStatus.PURGED.value,
                ),
            ).fetchone()
        return ProjectOperationalCounts(
            pending_review_count=int(row["pending_reviews"]),
            pending_purge_receipt_count=int(row["pending_receipts"]),
            pending_purge_artifact_count=int(row["pending_artifacts"]),
            pending_expiry_purge_receipt_count=int(row["pending_expiry_receipts"]),
            pending_expiry_purge_artifact_count=int(row["pending_expiry_artifacts"]),
        )

    def project_activity_status(self, project_id: str) -> ProjectActivitySnapshot:
        """Read bounded project activity totals without exposing event contents."""

        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("project activity snapshot cannot nest a transaction")
            self._connection.execute("BEGIN")
            try:
                event_counts = {
                    row["status"]: int(row["count"])
                    for row in self._connection.execute(
                        "SELECT status, COUNT(*) AS count FROM event_inbox "
                        "WHERE project_id = ? GROUP BY status",
                        (project_id,),
                    ).fetchall()
                }
                event_times = self._connection.execute(
                    "SELECT MAX(received_at) AS last_received, "
                    "MAX(processed_at) AS last_processed FROM event_inbox "
                    "WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                goal_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM goals WHERE project_id = ?",
                        (project_id,),
                    ).fetchone()[0]
                )
                goal_status_counts = {
                    row["status"]: int(row["count"])
                    for row in self._connection.execute(
                        "SELECT status, COUNT(*) AS count FROM goals "
                        "WHERE project_id = ? GROUP BY status",
                        (project_id,),
                    ).fetchall()
                }
                fact_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM facts AS f JOIN goals AS g "
                        "ON g.goal_id = f.goal_id WHERE g.project_id = ?",
                        (project_id,),
                    ).fetchone()[0]
                )
                sde_counts = {
                    row["status"]: int(row["count"])
                    for row in self._connection.execute(
                        "SELECT s.status, COUNT(*) AS count FROM sde_candidates AS s "
                        "JOIN goals AS g ON g.goal_id = s.goal_id "
                        "WHERE g.project_id = ? GROUP BY s.status",
                        (project_id,),
                    ).fetchall()
                }
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()

        received = event_counts.get(EventInboxStatus.RECEIVED.value, 0)
        failed = event_counts.get(EventInboxStatus.FAILED.value, 0)
        quarantined = event_counts.get(EventInboxStatus.QUARANTINED.value, 0)
        processed = event_counts.get(EventInboxStatus.PROCESSED.value, 0)
        pending_sde = sde_counts.get(SDEStatus.PENDING_REVIEW.value, 0)
        approved_sde = sde_counts.get(SDEStatus.APPROVED.value, 0)
        rejected_sde = sde_counts.get(SDEStatus.REJECTED.value, 0)
        return ProjectActivitySnapshot(
            project_id=project_id,
            observed_at=utc_now(),
            event_receipt_count=processed + received + failed + quarantined,
            processed_event_count=processed,
            received_event_count=received,
            failed_event_count=failed,
            quarantined_event_count=quarantined,
            last_event_received_at=event_times["last_received"],
            last_event_processed_at=event_times["last_processed"],
            goal_count=goal_count,
            goal_status_counts=tuple(
                GoalStatusStorageUsage(
                    status=status, count=goal_status_counts.get(status.value, 0)
                )
                for status in GoalStatus
            ),
            fact_count=fact_count,
            sde_candidate_count=pending_sde + approved_sde + rejected_sde,
            pending_sde_count=pending_sde,
            approved_sde_count=approved_sde,
            rejected_sde_count=rejected_sde,
            events_observed=(processed + received + failed + quarantined) > 0,
        )

    @staticmethod
    def _sde_correction_from_row(row: sqlite3.Row) -> SDECorrection:
        return SDECorrection(
            correction_id=row["correction_id"],
            candidate_id=row["candidate_id"],
            correction=row["correction"],
            rationale=row["rationale"],
            reviewer_id=row["reviewer_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _sde_feedback_matches(
        row: sqlite3.Row, feedback: SDEQualityFeedback
    ) -> bool:
        return all(
            row[key] == value
            for key, value in (
                ("candidate_id", feedback.candidate_id),
                ("reviewer_id", feedback.reviewer_id),
                ("label", feedback.label.value),
                ("rationale", feedback.rationale),
            )
        )

    @staticmethod
    def _sde_feedback_from_row(row: sqlite3.Row) -> SDEQualityFeedback:
        return SDEQualityFeedback(
            feedback_id=row["feedback_id"],
            candidate_id=row["candidate_id"],
            reviewer_id=row["reviewer_id"],
            label=SDEQualityFeedbackLabel(row["label"]),
            rationale=row["rationale"],
            created_at=row["created_at"],
        )

    def sde_quality_feedback_summary(
        self, project_id: str
    ) -> SDEQualityFeedbackSummary:
        """Count explicit feedback labels without returning any reviewer IDs."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT f.label, COUNT(*) AS count
                   FROM sde_quality_feedback AS f
                   JOIN sde_candidates AS s ON s.candidate_id = f.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ? GROUP BY f.label""",
                (project_id,),
            ).fetchall()
        count_by_label = {row["label"]: int(row["count"]) for row in rows}
        counts = tuple(
                (label, count_by_label.get(label.value, 0))
                for label in SDEQualityFeedbackLabel
        )
        return SDEQualityFeedbackSummary(
            project_id=project_id,
            counts=counts,
            total=sum(count for _label, count in counts),
        )
