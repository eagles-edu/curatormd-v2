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
    Fact,
    FactArchiveIntegrityError,
    MAX_FACTS_PER_GOAL,
    MAX_SDE_CORRECTIONS_PER_CANDIDATE,
    MAX_SDE_CORRECTIONS_PER_PROJECT,
    MAX_SDE_FEEDBACK_PER_PROJECT,
    NotFoundError,
    PurgeOutcome,
    PurgeStatus,
    ReviewDecision,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEStatus,
    _insert_purge_targets_from_inventory,
    _json_dump,
    _requested_artifact_manifest,
    _stored_artifact_manifest,
    json,
    re,
    utc_now,
    validate_safe_text,
)
from .store_operations_07 import StoreOperations2

class StoreOperations3Part0(StoreOperations2):
    """Internal SQLite operation group ordered by method dependency."""


    def get_fact(self, fact_id: str, project_id: str | None = None) -> Fact:
        """Load an active or archived fact while honoring optional project scope."""

        with self._lock:
            if project_id is None:
                row = self._connection.execute(
                    "SELECT * FROM facts WHERE fact_id = ?", (fact_id,)
                ).fetchone()
            else:
                row = self._connection.execute(
                    """SELECT f.* FROM facts AS f JOIN goals AS g
                       ON g.goal_id = f.goal_id
                       WHERE f.fact_id = ? AND g.project_id = ?""",
                    (fact_id, project_id),
                ).fetchone()
            if row is not None:
                return self._fact_from_row(row)
            archive_query = """SELECT a.* FROM fact_archives AS a
                JOIN fact_archive_items AS i ON i.compaction_id = a.compaction_id
                WHERE i.fact_id = ?"""
            parameters: tuple[object, ...] = (fact_id,)
            if project_id is not None:
                archive_query += " AND i.project_id = ?"
                parameters += (project_id,)
            archive_row = self._connection.execute(
                archive_query, parameters
            ).fetchone()
            if archive_row is None:
                raise NotFoundError(f"fact not found: {fact_id}")
            facts = self._decode_fact_archive(archive_row)
        for fact in facts:
            if fact.fact_id == fact_id:
                return fact
        raise FactArchiveIntegrityError("archive index references a missing fact")

    def attach_fact_source_event(
        self,
        fact_ids: tuple[str, ...],
        source_event_id: str,
        project_id: str,
    ) -> None:
        """Attach the first processed event to new facts without rewriting origin."""

        if not fact_ids:
            return
        if len(fact_ids) > MAX_FACTS_PER_GOAL:
            raise ValueError("source event cannot be attached to an unbounded fact set")
        if not source_event_id.strip() or len(source_event_id) > 128:
            raise ValueError("source_event_id must be a bounded identifier")
        validate_safe_text(source_event_id, "source_event_id")
        with self._transaction() as connection:
            connection.execute(
                """UPDATE facts SET source_event_id = ?
                    WHERE fact_id IN (SELECT value FROM json_each(?))
                      AND source_event_id IS NULL
                      AND goal_id IN (
                        SELECT goal_id FROM goals WHERE project_id = ?
                      )""",
                (source_event_id, json.dumps(fact_ids), project_id),
            )

    def list_facts(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[Fact, ...]:
        """Return active and hash-verified archived facts in canonical order."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT * FROM facts WHERE goal_id = ? ORDER BY created_at, fact_id",
                    (goal_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT f.* FROM facts AS f JOIN goals AS g
                       ON g.goal_id = f.goal_id
                       WHERE f.goal_id = ? AND g.project_id = ?
                       ORDER BY f.created_at, f.fact_id""",
                    (goal_id, project_id),
                ).fetchall()
            if project_id is None:
                archives = self._connection.execute(
                    """SELECT DISTINCT a.* FROM fact_archives AS a
                       JOIN fact_archive_items AS i ON i.compaction_id = a.compaction_id
                       WHERE i.goal_id = ?""",
                    (goal_id,),
                ).fetchall()
                archive_item_rows = self._connection.execute(
                    "SELECT compaction_id, fact_id, goal_id, project_id "
                    "FROM fact_archive_items WHERE goal_id = ?",
                    (goal_id,),
                ).fetchall()
            else:
                archives = self._connection.execute(
                    """SELECT DISTINCT a.* FROM fact_archives AS a
                       JOIN fact_archive_items AS i ON i.compaction_id = a.compaction_id
                       WHERE i.goal_id = ? AND i.project_id = ?""",
                    (goal_id, project_id),
                ).fetchall()
                archive_item_rows = self._connection.execute(
                    "SELECT compaction_id, fact_id, goal_id, project_id "
                    "FROM fact_archive_items WHERE goal_id = ? AND project_id = ?",
                    (goal_id, project_id),
                ).fetchall()
            archive_items = {
                (row["compaction_id"], row["fact_id"]): row
                for row in archive_item_rows
            }
        active_facts = [self._fact_from_row(row) for row in rows]
        archived_facts: list[Fact] = []
        for archive in archives:
            decoded = self._decode_fact_archive(archive)
            indexed_ids = {
                item["fact_id"]
                for item in archive_items.values()
                if item["compaction_id"] == archive["compaction_id"]
            }
            if indexed_ids != {fact.fact_id for fact in decoded}:
                raise FactArchiveIntegrityError("archive index does not match its payload")
            archived_facts.extend(decoded)
        return tuple(
            sorted(active_facts + archived_facts, key=lambda fact: (fact.created_at, fact.fact_id))
        )

    def add_sde_candidate(
        self, candidate: SDECandidate, project_id: str | None = None
    ) -> tuple[SDECandidate, bool]:
        """Insert a project-owned candidate idempotently by its supporting facts."""

        dedupe_key = self._candidate_dedupe_key(candidate)
        with self._transaction() as connection:
            goal_row = connection.execute(
                "SELECT project_id FROM goals WHERE goal_id = ?",
                (candidate.goal_id,),
            ).fetchone()
            if goal_row is None or (
                project_id is not None and goal_row["project_id"] != project_id
            ):
                raise NotFoundError(f"goal not found: {candidate.goal_id}")
            query = """SELECT fact_id, goal_id FROM facts
                       WHERE fact_id IN (SELECT value FROM json_each(?))"""
            rows = connection.execute(
                query,
                (json.dumps(candidate.fact_ids),),
            ).fetchall()
            if len(rows) != len(candidate.fact_ids) or any(
                row["goal_id"] != candidate.goal_id for row in rows
            ):
                raise ConflictError("all SDE evidence facts must belong to the candidate goal")
            if candidate.impact is None or candidate.retrieval_value is None:
                raise ValueError(
                    "new SDE candidates require impact and retrieval value"
                )
            existing = connection.execute(
                "SELECT * FROM sde_candidates WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            if existing is not None:
                stored = self._candidate_from_row(existing)
                if (
                    stored.rationale != candidate.rationale.strip()
                    or stored.impact != candidate.impact.strip()
                    or stored.retrieval_value != candidate.retrieval_value.strip()
                ):
                    raise ConflictError(
                        "replayed SDE assessment changed its proposal context"
                    )
                return stored, False
            connection.execute(
                """INSERT INTO sde_candidates
                   (candidate_id, goal_id, materiality, rationale, impact,
                    retrieval_value, fact_ids_json, dedupe_key, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candidate.candidate_id,
                    candidate.goal_id,
                    candidate.materiality.value,
                    candidate.rationale.strip(),
                    candidate.impact.strip(),
                    candidate.retrieval_value.strip(),
                    _json_dump(candidate.fact_ids),
                    dedupe_key,
                    candidate.status.value,
                    candidate.created_at,
                ),
            )
        return candidate, True

    def get_sde_candidate(
        self, candidate_id: str, project_id: str | None = None
    ) -> SDECandidate:
        """Load one SDE candidate, optionally enforcing its project boundary."""

        with self._lock:
            if project_id is None:
                row = self._connection.execute(
                    "SELECT * FROM sde_candidates WHERE candidate_id = ?",
                    (candidate_id,),
                ).fetchone()
            else:
                row = self._connection.execute(
                    """SELECT s.* FROM sde_candidates AS s JOIN goals AS g
                       ON g.goal_id = s.goal_id
                       WHERE s.candidate_id = ? AND g.project_id = ?""",
                    (candidate_id, project_id),
                ).fetchone()
        if row is None:
            raise NotFoundError(f"SDE candidate not found: {candidate_id}")
        return self._candidate_from_row(row)

    def create_receipt(
        self, receipt: AuditReceipt, project_id: str | None = None
    ) -> AuditReceipt:
        """Durably record review and exact artifact hashes before any deletion."""

        if receipt.reviewer_id is None:
            raise ValueError("review receipt requires an authenticated reviewer identity")
        with self._transaction() as connection:
            if project_id is not None and connection.execute(
                """SELECT 1 FROM sde_candidates AS s JOIN goals AS g
                   ON g.goal_id = s.goal_id
                   WHERE s.candidate_id = ? AND g.project_id = ?""",
                (receipt.candidate_id, project_id),
            ).fetchone() is None:
                raise NotFoundError(
                    f"SDE candidate not found: {receipt.candidate_id}"
                )
            existing = connection.execute(
                "SELECT * FROM audit_receipts WHERE candidate_id = ?",
                (receipt.candidate_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["decision"] != receipt.decision.value
                    or existing["facts_sha256"] != receipt.facts_sha256
                    or existing["reviewer_id"] != receipt.reviewer_id
                    or existing["review_rationale"] != receipt.review_rationale
                    or bool(existing["artifact_inventory_complete"])
                    != receipt.artifact_inventory_complete
                ):
                    raise ConflictError("candidate already has a different audit receipt")
                saved_targets = connection.execute(
                    "SELECT path, sha256, retention_hold, device_id, inode_id, occurrence_id, "
                    "reacquisition_action "
                    "FROM purge_targets WHERE receipt_id = ? "
                    "ORDER BY path",
                    (existing["receipt_id"],),
                ).fetchall()
                requested_targets = sorted(
                    (
                        item.path,
                        item.sha256,
                        item.retention_hold.value if item.retention_hold else None,
                        item.device_id,
                        item.inode_id,
                        item.occurrence_id,
                        item.reacquisition_action.value,
                    )
                    for item in receipt.artifacts
                )
                saved_target_values = [
                    (
                        item["path"], item["sha256"], item["retention_hold"],
                        item["device_id"], item["inode_id"],
                        item["occurrence_id"],
                        item["reacquisition_action"],
                    )
                    for item in saved_targets
                ]
                if saved_target_values != requested_targets:
                    raise ConflictError("candidate receipt already contains different artifacts")
                receipt_id = existing["receipt_id"]
            else:
                candidate = connection.execute(
                    "SELECT status FROM sde_candidates WHERE candidate_id = ?",
                    (receipt.candidate_id,),
                ).fetchone()
                if candidate is None:
                    raise NotFoundError(f"SDE candidate not found: {receipt.candidate_id}")
                if candidate["status"] != SDEStatus.PENDING_REVIEW.value:
                    raise ConflictError("only pending SDE candidates can be reviewed")
                receipt_id = receipt.receipt_id
                initial_purge_status = (
                    PurgeStatus.PURGE_PENDING
                    if not receipt.canonical_persisted
                    or not receipt.artifact_inventory_complete
                    or receipt.artifacts
                    else PurgeStatus.COMPLETE
                )
                connection.execute(
                    """INSERT INTO audit_receipts
                       (receipt_id, candidate_id, decision, facts_sha256,
                        artifact_inventory_complete, reviewer_id, review_rationale,
                        canonical_persisted,
                        canonical_target, canonical_sha256, canonical_persisted_at,
                        purge_status, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        receipt_id,
                        receipt.candidate_id,
                        receipt.decision.value,
                        receipt.facts_sha256,
                        int(receipt.artifact_inventory_complete),
                        receipt.reviewer_id,
                        receipt.review_rationale,
                        int(receipt.canonical_persisted),
                        receipt.canonical_target,
                        receipt.canonical_sha256,
                        receipt.canonical_persisted_at,
                        initial_purge_status.value,
                        receipt.created_at,
                        receipt.updated_at,
                    ),
                )
                for artifact in receipt.artifacts:
                    connection.execute(
                        """INSERT INTO purge_targets
                           (receipt_id, path, sha256, status, attempts, error,
                            created_at, last_attempt_at, next_attempt_at, retention_hold,
                            hold_created_at, hold_created_by, device_id, inode_id,
                            occurrence_id, approval_stale, reacquisition_action, outcome)
                           VALUES (?, ?, ?, ?, 0, NULL, ?, NULL, NULL, ?, ?, ?, ?, ?,
                                   ?, ?, ?, ?)""",
                        (
                            receipt_id,
                            artifact.path,
                            artifact.sha256,
                            (
                                ArtifactStatus.HELD
                                if artifact.retention_hold
                                else ArtifactStatus.PENDING
                            ).value,
                            receipt.created_at,
                            artifact.retention_hold.value if artifact.retention_hold else None,
                            receipt.created_at if artifact.retention_hold else None,
                            receipt.reviewer_id if artifact.retention_hold else None,
                            artifact.device_id,
                            artifact.inode_id,
                            artifact.occurrence_id,
                            int(artifact.occurrence_id is None),
                            artifact.reacquisition_action.value,
                            PurgeOutcome.HELD.value if artifact.retention_hold else None,
                        ),
                    )
                status = (
                    SDEStatus.APPROVED
                    if receipt.decision is ReviewDecision.APPROVED
                    else SDEStatus.REJECTED
                )
                connection.execute(
                    "UPDATE sde_candidates SET status = ? WHERE candidate_id = ?",
                    (status.value, receipt.candidate_id),
                )
        return self.get_receipt(receipt_id, project_id)

    def add_sde_correction(
        self, correction: SDECorrection, project_id: str
    ) -> tuple[SDECorrection, bool]:
        """Append an immutable correction only after a durable review receipt."""

        with self._transaction() as connection:
            scoped = connection.execute(
                """SELECT g.project_id FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE s.candidate_id = ?""",
                (correction.candidate_id,),
            ).fetchone()
            if scoped is None or scoped["project_id"] != project_id:
                raise NotFoundError(
                    f"SDE candidate not found: {correction.candidate_id}"
                )
            if connection.execute(
                "SELECT 1 FROM audit_receipts WHERE candidate_id = ?",
                (correction.candidate_id,),
            ).fetchone() is None:
                raise ConflictError("SDE correction requires a durable review receipt")
            existing = connection.execute(
                "SELECT * FROM sde_corrections WHERE correction_id = ?",
                (correction.correction_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["candidate_id"] != correction.candidate_id
                    or existing["correction"] != correction.correction
                    or existing["rationale"] != correction.rationale
                    or existing["reviewer_id"] != correction.reviewer_id
                ):
                    raise ConflictError(
                        "correction ID already exists with different content"
                    )
                return self._sde_correction_from_row(existing), False
            candidate_count = connection.execute(
                "SELECT count(*) FROM sde_corrections WHERE candidate_id = ?",
                (correction.candidate_id,),
            ).fetchone()[0]
            project_count = connection.execute(
                """SELECT count(*) FROM sde_corrections AS c
                   JOIN sde_candidates AS s ON s.candidate_id = c.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ?""",
                (project_id,),
            ).fetchone()[0]
            if candidate_count >= MAX_SDE_CORRECTIONS_PER_CANDIDATE:
                raise ConflictError("SDE correction capacity reached for candidate")
            if project_count >= MAX_SDE_CORRECTIONS_PER_PROJECT:
                raise ConflictError("SDE correction capacity reached for project")
            connection.execute(
                """INSERT INTO sde_corrections
                   (correction_id, candidate_id, correction, rationale,
                    reviewer_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    correction.correction_id,
                    correction.candidate_id,
                    correction.correction,
                    correction.rationale,
                    correction.reviewer_id,
                    correction.created_at,
                ),
            )
            return correction, True

    def add_sde_quality_feedback(
        self, feedback: SDEQualityFeedback, project_id: str
    ) -> tuple[SDEQualityFeedback, bool]:
        """Append one reviewer label after a durable SDE decision."""

        with self._transaction() as connection:
            candidate = connection.execute(
                """SELECT g.project_id FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE s.candidate_id = ?""",
                (feedback.candidate_id,),
            ).fetchone()
            if candidate is None or candidate["project_id"] != project_id:
                raise NotFoundError(f"SDE candidate not found: {feedback.candidate_id}")
            if connection.execute(
                "SELECT 1 FROM audit_receipts WHERE candidate_id = ?",
                (feedback.candidate_id,),
            ).fetchone() is None:
                raise ConflictError("SDE feedback requires a durable review receipt")

            existing = connection.execute(
                "SELECT * FROM sde_quality_feedback WHERE feedback_id = ?",
                (feedback.feedback_id,),
            ).fetchone()
            if existing is not None:
                if not self._sde_feedback_matches(existing, feedback):
                    raise ConflictError(
                        "feedback ID already exists with different content"
                    )
                return self._sde_feedback_from_row(existing), False

            reviewer_feedback = connection.execute(
                """SELECT feedback_id FROM sde_quality_feedback
                   WHERE candidate_id = ? AND reviewer_id = ?""",
                (feedback.candidate_id, feedback.reviewer_id),
            ).fetchone()
            if reviewer_feedback is not None:
                raise ConflictError(
                    "reviewer already submitted feedback for this candidate"
                )
            project_count = connection.execute(
                """SELECT count(*) FROM sde_quality_feedback AS f
                   JOIN sde_candidates AS s ON s.candidate_id = f.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ?""",
                (project_id,),
            ).fetchone()[0]
            if project_count >= MAX_SDE_FEEDBACK_PER_PROJECT:
                raise ConflictError("SDE feedback capacity reached for project")
            connection.execute(
                """INSERT INTO sde_quality_feedback
                   (feedback_id, candidate_id, reviewer_id, label, rationale, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    feedback.feedback_id,
                    feedback.candidate_id,
                    feedback.reviewer_id,
                    feedback.label.value,
                    feedback.rationale,
                    feedback.created_at,
                ),
            )
            return feedback, True

    def complete_artifact_inventory(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        project_id: str | None = None,
        hold_created_by: str | None = None,
    ) -> AuditReceipt:
        """Finalize a manifest before any target in it can be purged."""

        if hold_created_by is not None and not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", hold_created_by
        ):
            raise ValueError("hold-placement actor must be a bounded opaque identifier")
        requested = _requested_artifact_manifest(artifacts)
        with self._transaction() as connection:
            if project_id is None:
                row = connection.execute(
                    "SELECT artifact_inventory_complete, canonical_persisted, purge_status "
                    "FROM audit_receipts "
                    "WHERE receipt_id = ?",
                    (receipt_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT r.artifact_inventory_complete, r.canonical_persisted,
                              r.purge_status
                       FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.receipt_id = ? AND g.project_id = ?""",
                    (receipt_id, project_id),
                ).fetchone()
            if row is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            existing_targets = connection.execute(
                "SELECT path, sha256, status, attempts, retention_hold, "
                "hold_created_at, hold_created_by, device_id, inode_id, occurrence_id, "
                "reacquisition_action "
                "FROM purge_targets "
                "WHERE receipt_id = ? ORDER BY path",
                (receipt_id,),
            ).fetchall()
            if bool(row["artifact_inventory_complete"]):
                if requested != _stored_artifact_manifest(existing_targets):
                    raise ConflictError("complete artifact inventory cannot be changed")
            else:
                if row["purge_status"] != PurgeStatus.PURGE_PENDING.value:
                    raise ConflictError(
                        "only pending receipts can complete an artifact inventory"
                    )
                if any(
                    item["attempts"]
                    or item["status"]
                    not in (ArtifactStatus.PENDING.value, ArtifactStatus.HELD.value)
                    for item in existing_targets
                ):
                    raise ConflictError(
                        "artifact inventory cannot change after purge attempts"
                    )
                connection.execute(
                    "DELETE FROM purge_targets WHERE receipt_id = ?", (receipt_id,)
                )
                _insert_purge_targets_from_inventory(
                    connection,
                    receipt_id,
                    artifacts,
                    existing_targets,
                    hold_created_by,
                )
                purge_status = (
                    PurgeStatus.PURGE_PENDING
                    if artifacts or not bool(row["canonical_persisted"])
                    else PurgeStatus.COMPLETE
                )
                connection.execute(
                    "UPDATE audit_receipts SET artifact_inventory_complete = 1, "
                    "purge_status = ?, updated_at = ? WHERE receipt_id = ?",
                    (purge_status.value, utc_now(), receipt_id),
                )
        return self.get_receipt(receipt_id, project_id)

    def mark_receipt_canonical_persisted(
        self,
        receipt_id: str,
        target: str,
        sha256: str,
        project_id: str,
    ) -> AuditReceipt:
        """Record immutable proof that facts and this receipt reached Markdown."""

        if not target.strip() or len(target) > 2000 or "\n" in target or "\r" in target:
            raise ValueError("canonical persistence target must be bounded and one line")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("canonical persistence hash must be SHA-256")
        persisted_at = utc_now()
        with self._transaction() as connection:
            row = connection.execute(
                """SELECT r.canonical_persisted, r.canonical_target,
                          r.canonical_sha256 FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
            if row is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            if bool(row["canonical_persisted"]):
                if row["canonical_target"] != target or row["canonical_sha256"] != sha256:
                    raise ConflictError("canonical persistence proof is immutable")
            else:
                connection.execute(
                    """UPDATE audit_receipts SET canonical_persisted = 1,
                              canonical_target = ?, canonical_sha256 = ?,
                              canonical_persisted_at = ?, updated_at = ?
                       WHERE receipt_id = ?""",
                    (target, sha256, persisted_at, persisted_at, receipt_id),
                )
                if bool(
                    connection.execute(
                        "SELECT artifact_inventory_complete FROM audit_receipts "
                        "WHERE receipt_id = ?",
                        (receipt_id,),
                    ).fetchone()["artifact_inventory_complete"]
                ):
                    unfinished = connection.execute(
                        "SELECT 1 FROM purge_targets WHERE receipt_id = ? "
                        "AND status != ? LIMIT 1",
                        (receipt_id, ArtifactStatus.PURGED.value),
                    ).fetchone()
                    if unfinished is None:
                        connection.execute(
                            "UPDATE audit_receipts SET purge_status = ?, updated_at = ? "
                            "WHERE receipt_id = ?",
                            (PurgeStatus.COMPLETE.value, persisted_at, receipt_id),
                        )
        return self.get_receipt(receipt_id, project_id)

    def release_artifact_hold(
        self,
        receipt_id: str,
        path: str,
        project_id: str,
        actor_id: str,
        rationale: str,
    ) -> AuditReceipt:
        """Release one held artifact with a durable actor and rationale."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", actor_id):
            raise ValueError("hold-release actor must be a bounded opaque identifier")
        validate_safe_text(rationale, "retention_hold.release_rationale")
        if not rationale.strip() or len(rationale) > 500 or "\n" in rationale or "\r" in rationale:
            raise ValueError("hold-release rationale must be a bounded single line")

        released_at = utc_now()
        with self._transaction() as connection:
            row = connection.execute(
                """SELECT p.status, p.retention_hold, p.attempts, p.approval_stale,
                          p.hold_released_at, p.hold_released_by,
                          p.hold_release_rationale, r.artifact_inventory_complete,
                          r.canonical_persisted
                   FROM purge_targets AS p
                   JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE p.receipt_id = ? AND p.path = ? AND g.project_id = ?""",
                (receipt_id, path, project_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("purge target not found in project receipt")
            if row["hold_released_at"] is not None:
                if (
                    row["hold_released_by"] == actor_id
                    and row["hold_release_rationale"] == rationale
                ):
                    return self.get_receipt(receipt_id, project_id)
                raise ConflictError("retention hold was already released differently")
            if (
                row["status"] != ArtifactStatus.HELD.value
                or row["retention_hold"] is None
                or row["attempts"] != 0
            ):
                raise ConflictError("artifact has no releasable retention hold")
            if not bool(row["artifact_inventory_complete"]) or not bool(
                row["canonical_persisted"]
            ):
                raise ConflictError("hold release is blocked by an open receipt gate")
            cursor = connection.execute(
                """UPDATE purge_targets SET status = ?, outcome = NULL,
                          error = CASE WHEN approval_stale = 1 THEN error ELSE NULL END,
                          next_attempt_at = NULL, hold_released_at = ?,
                          hold_released_by = ?, hold_release_rationale = ?
                   WHERE receipt_id = ? AND path = ? AND status = ?
                     AND hold_released_at IS NULL AND attempts = 0""",
                (
                    ArtifactStatus.PENDING.value,
                    released_at,
                    actor_id,
                    rationale,
                    receipt_id,
                    path,
                    ArtifactStatus.HELD.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("retention hold changed during release")
            connection.execute(
                "UPDATE audit_receipts SET updated_at = ? WHERE receipt_id = ?",
                (released_at, receipt_id),
            )
        return self.get_receipt(receipt_id, project_id)

    def begin_purge_attempt(
        self,
        receipt_id: str,
        path: str,
        project_id: str,
    ) -> None:
        """Durably count an eligible deletion attempt before touching a file."""

        attempted_at = utc_now()
        with self._transaction() as connection:
            receipt = connection.execute(
                """SELECT r.artifact_inventory_complete, r.canonical_persisted
                   FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
            if receipt is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            if not bool(receipt["artifact_inventory_complete"]) or not bool(
                receipt["canonical_persisted"]
            ):
                raise ConflictError("purge attempt is blocked by an open receipt gate")
            cursor = connection.execute(
                """UPDATE purge_targets SET attempts = attempts + 1,
                   last_attempt_at = ?, next_attempt_at = NULL, outcome = NULL
                   WHERE receipt_id = ? AND path = ? AND status IN (?, ?)
                     AND approval_stale = 0
                     AND (retention_hold IS NULL OR hold_released_at IS NOT NULL)""",
                (
                    attempted_at,
                    receipt_id,
                    path,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("purge target is missing or already complete")
            connection.execute(
                "UPDATE audit_receipts SET updated_at = ? WHERE receipt_id = ?",
                (attempted_at, receipt_id),
            )
