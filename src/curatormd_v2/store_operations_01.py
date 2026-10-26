"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactRef,
    ArtifactStatus,
    CleanupAuthorizationReceipt,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    ExpiryPurgeReceipt,
    Fact,
    FactArchiveIntegrityError,
    FactCapacity,
    FactKind,
    GoalCard,
    GoalCriteriaVersion,
    GoalReportContext,
    GoalStatus,
    MAX_FACTS_PER_GOAL,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_GOAL,
    MAX_FACT_BYTES_PER_PROJECT,
    MAX_FACT_COMPACTION_SOURCE_BYTES,
    NotFoundError,
    PurgeStatus,
    SDEStatus,
    SuccessCriterion,
    _FactStoragePayload,
    _attestation_to_dict,
    _evidence_to_dict,
    _json_dump,
    cast,
    hashlib,
    json,
    re,
    sqlite3,
    utc_now,
    zlib,
)
from .store_operations_00 import StoreOperations0Part0

class StoreOperations0Part1(StoreOperations0Part0):
    """Continuation of StoreOperations0 operations."""


    def cleanup_authorization(
        self, receipt_id: str, project_id: str
    ) -> CleanupAuthorizationReceipt | None:
        """Read the separate exact-inventory approval for one project receipt."""

        with self._lock:
            row = self._connection.execute(
                """SELECT * FROM cleanup_authorizations
                   WHERE receipt_id = ? AND project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
        if row is None:
            return None
        return CleanupAuthorizationReceipt(
            row["receipt_id"], row["project_id"], row["reviewer_id"],
            row["manifest_sha256"], row["dependency_map_sha256"], row["approved_at"],
            bool(row["canonical_persisted"]), row["canonical_target"],
            row["canonical_sha256"], row["canonical_persisted_at"]
        )

    def expiry_purge_receipt(
        self, receipt_id: str, project_id: str
    ) -> ExpiryPurgeReceipt:
        """Read one durable expiry approval and its exact target inventory."""

        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM expiry_purge_receipts "
                "WHERE receipt_id = ? AND project_id = ?",
                (receipt_id, project_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("expiry purge receipt not found")
            targets = self._connection.execute(
                "SELECT path, sha256, device_id, inode_id, occurrence_id, approval_stale "
                "FROM expiry_purge_targets "
                "WHERE receipt_id = ? ORDER BY path",
                (receipt_id,),
            ).fetchall()
        return ExpiryPurgeReceipt(
            receipt_id=row["receipt_id"],
            project_id=row["project_id"],
            reviewer_id=row["reviewer_id"],
            manifest_sha256=row["manifest_sha256"],
            artifacts=tuple(
                ArtifactRef(
                    target["path"],
                    target["sha256"],
                    device_id=target["device_id"],
                    inode_id=target["inode_id"],
                    occurrence_id=target["occurrence_id"],
                )
                for target in targets
            ),
            status=PurgeStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approval_stale_artifacts=tuple(
                ArtifactRef(
                    target["path"],
                    target["sha256"],
                    device_id=target["device_id"],
                    inode_id=target["inode_id"],
                    occurrence_id=target["occurrence_id"],
                )
                for target in targets
                if bool(target["approval_stale"])
            ),
        )

    def due_expiry_purge_receipts(
        self, project_id: str, limit: int = 100
    ) -> tuple[str, ...]:
        """Select only previously approved expiry receipts with due targets."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        with self._lock:
            rows = self._connection.execute(
                """SELECT DISTINCT r.receipt_id FROM expiry_purge_receipts AS r
                   JOIN expiry_purge_targets AS t ON t.receipt_id = r.receipt_id
                   WHERE r.project_id = ? AND r.status = ?
                     AND t.status IN (?, ?)
                     AND t.approval_stale = 0
                     AND (t.next_attempt_at IS NULL OR t.next_attempt_at <= ?)
                   ORDER BY r.created_at, r.receipt_id LIMIT ?""",
                (
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                    now,
                    limit,
                ),
            ).fetchall()
        return tuple(row["receipt_id"] for row in rows)

    def expiry_purge_targets(
        self, receipt_id: str, project_id: str
    ) -> tuple[tuple[ArtifactRef, int], ...]:
        """Read due, unheld targets from one approved expiry receipt."""

        now = utc_now()
        with self._lock:
            rows = self._connection.execute(
                """SELECT t.path, t.sha256, t.attempts, t.device_id, t.inode_id,
                          t.occurrence_id
                   FROM expiry_purge_targets AS t
                   JOIN expiry_purge_receipts AS r ON r.receipt_id = t.receipt_id
                   WHERE r.receipt_id = ? AND r.project_id = ? AND t.status IN (?, ?)
                     AND t.approval_stale = 0
                     AND (t.next_attempt_at IS NULL OR t.next_attempt_at <= ?)
                     AND NOT EXISTS (
                       SELECT 1 FROM purge_targets AS p
                       JOIN audit_receipts AS ar ON ar.receipt_id = p.receipt_id
                       JOIN sde_candidates AS s ON s.candidate_id = ar.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE g.project_id = r.project_id AND p.path = t.path
                         AND p.sha256 = t.sha256 AND p.retention_hold IS NOT NULL
                         AND p.hold_released_at IS NULL
                     ) ORDER BY t.path""",
                (
                    receipt_id,
                    project_id,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                    now,
                ),
            ).fetchall()
        return tuple(
            (
                ArtifactRef(
                    row["path"], row["sha256"],
                    device_id=row["device_id"], inode_id=row["inode_id"],
                    occurrence_id=row["occurrence_id"],
                ),
                int(row["attempts"]),
            )
            for row in rows
        )

    def staging_artifact_times(
        self, project_id: str, artifacts: tuple[ArtifactRef, ...]
    ) -> dict[str, str]:
        """Return trusted timestamps only for exact project/path/hash matches."""

        if not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id
        ):
            raise ValueError("project_id must be a bounded opaque identifier")
        timestamps: dict[str, str] = {}
        with self._lock:
            for offset in range(0, len(artifacts), 400):
                page = artifacts[offset : offset + 400]
                if not page:
                    continue
                paths = tuple(item.path for item in page)
                paths_json = json.dumps(paths, separators=(",", ":"))
                rows = self._connection.execute(
                    "SELECT path, sha256, staged_at, device_id, inode_id, occurrence_id "
                    "FROM staging_artifact_times "
                    "WHERE project_id = ? AND path IN "
                    "(SELECT value FROM json_each(?))",
                    (project_id, paths_json),
                ).fetchall()
                known = {
                    row["path"]: (
                        row["sha256"], row["staged_at"],
                        row["device_id"], row["inode_id"],
                        row["occurrence_id"],
                    )
                    for row in rows
                }
                for artifact in page:
                    match = known.get(artifact.path)
                    if (
                        match is not None
                        and artifact.occurrence_id is not None
                        and match[0] == artifact.sha256
                        and match[2:] == (
                            artifact.device_id,
                            artifact.inode_id,
                            artifact.occurrence_id,
                        )
                    ):
                        timestamps[artifact.path] = str(match[1])
        return timestamps

    def staging_artifact_expiry_readiness(
        self,
        project_id: str,
        artifact_goal_times: dict[str, tuple[str, str]],
    ) -> dict[str, tuple[bool, bool, int]]:
        """Read post-publication fact/review evidence and pending SDE counts.

        The returned tuple is `(fact_after_stage, review_after_stage,
        pending_sde_count)`, keyed by the exact staged path. Only compact
        ledger timestamps and project/goal identifiers enter this query.
        """

        if not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id
        ):
            raise ValueError("project_id must be a bounded opaque identifier")
        requested_items: list[dict[str, str]] = []
        for path, (goal_id, staged_at) in artifact_goal_times.items():
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", goal_id):
                raise ValueError("goal_id must be a bounded opaque identifier")
            if not path or len(path) > 1024 or len(staged_at) > 64:
                raise ValueError("staged artifact readiness fields exceed their bounds")
            requested_items.append(
                {"path": path, "goal_id": goal_id, "staged_at": staged_at}
            )
        readiness: dict[str, tuple[bool, bool, int]] = {}
        for offset in range(0, len(requested_items), 400):
            page = requested_items[offset : offset + 400]
            if not page:
                continue
            requested = json.dumps(page, separators=(",", ":"))
            with self._lock:
                rows = self._connection.execute(
                    """WITH requested AS (
                           SELECT json_extract(value, '$.path') AS path,
                                  json_extract(value, '$.goal_id') AS goal_id,
                                  json_extract(value, '$.staged_at') AS staged_at
                           FROM json_each(?)
                       )
                       SELECT q.path,
                         EXISTS (
                           SELECT 1 FROM facts AS f
                           JOIN goals AS g ON g.goal_id = f.goal_id
                           WHERE f.goal_id = q.goal_id AND g.project_id = ?
                             AND f.created_at >= q.staged_at
                         ) AS fact_after_stage,
                         EXISTS (
                           SELECT 1 FROM audit_receipts AS r
                           JOIN sde_candidates AS s
                             ON s.candidate_id = r.candidate_id
                           JOIN goals AS g ON g.goal_id = s.goal_id
                           WHERE s.goal_id = q.goal_id AND g.project_id = ?
                             AND r.created_at >= q.staged_at
                         ) AS review_after_stage,
                         (SELECT COUNT(*) FROM sde_candidates AS s
                          JOIN goals AS g ON g.goal_id = s.goal_id
                          WHERE s.goal_id = q.goal_id AND g.project_id = ?
                            AND s.status = ?) AS pending_sde_count
                       FROM requested AS q""",
                    (
                        requested,
                        project_id,
                        project_id,
                        project_id,
                        SDEStatus.PENDING_REVIEW.value,
                    ),
                ).fetchall()
            for row in rows:
                readiness[str(row["path"])] = (
                    bool(row["fact_after_stage"]),
                    bool(row["review_after_stage"]),
                    int(row["pending_sde_count"]),
                )
        return readiness

    def goal_report_context(
        self, goal_id: str, project_id: str
    ) -> GoalReportContext:
        """Read compact immutable intake provenance for one scoped goal."""

        with self._lock:
            row = self._connection.execute(
                """SELECT project_id, owner, checklist_id, checklist_version,
                          initial_status, source_event_id
                   FROM goals WHERE goal_id = ? AND project_id = ?""",
                (goal_id, project_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"goal not found: {goal_id}")
        return GoalReportContext(
            project_id=row["project_id"],
            owner=row["owner"],
            checklist_id=row["checklist_id"],
            checklist_version=row["checklist_version"],
            initial_status=(
                GoalStatus(row["initial_status"])
                if row["initial_status"] is not None
                else None
            ),
            source_event_id=row["source_event_id"],
        )

    def get_goal(self, goal_id: str, project_id: str | None = None) -> GoalCard:
        """Load one goal, optionally enforcing its project boundary."""

        with self._lock:
            if project_id is None:
                row = self._connection.execute(
                    "SELECT * FROM goals WHERE goal_id = ?", (goal_id,)
                ).fetchone()
            else:
                row = self._connection.execute(
                    "SELECT * FROM goals WHERE goal_id = ? AND project_id = ?",
                    (goal_id, project_id),
                ).fetchone()
        if row is None:
            raise NotFoundError(f"goal not found: {goal_id}")
        criteria_data = json.loads(row["criteria_json"])
        criteria = tuple(
            SuccessCriterion(item["criterion_id"], item["description"])
            for item in criteria_data
        )
        return GoalCard(
            goal_id=row["goal_id"],
            problem=row["problem"],
            success_criteria=criteria,
            owner=row["owner"],
            checklist_id=row["checklist_id"],
            checklist_version=row["checklist_version"],
            checklist_source_text=row["checklist_source_text"],
            parent_goal_id=row["parent_goal_id"],
            depends_on_goal_ids=tuple(json.loads(row["depends_on_json"])),
            project_id=row["project_id"],
            status=GoalStatus(row["status"]),
            next_action=row["next_action"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            criteria_revision=row["criteria_revision"],
            lifecycle_revision=row["lifecycle_revision"],
            superseded_by_goal_id=row["superseded_by_goal_id"],
        )

    def list_goal_criteria_versions(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[GoalCriteriaVersion, ...]:
        """Return immutable original and amended criteria snapshots."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT v.* FROM goal_criteria_versions AS v "
                    "JOIN goals AS g ON g.goal_id = v.goal_id "
                    "WHERE v.goal_id = ? ORDER BY v.revision",
                    (goal_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT v.* FROM goal_criteria_versions AS v "
                    "JOIN goals AS g ON g.goal_id = v.goal_id "
                    "WHERE v.goal_id = ? AND g.project_id = ? ORDER BY v.revision",
                    (goal_id, project_id),
                ).fetchall()
        return tuple(
            GoalCriteriaVersion(
                revision=row["revision"],
                criteria=tuple(
                    SuccessCriterion(item["criterion_id"], item["description"])
                    for item in json.loads(row["criteria_json"])
                ),
                reason=row["reason"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def child_goal_status_counts(
        self, parent_goal_id: str, project_id: str
    ) -> dict[str, int]:
        """Count direct children by lifecycle state without loading goal cards."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT status, COUNT(*) AS count FROM goals "
                "WHERE parent_goal_id = ? AND project_id = ? GROUP BY status",
                (parent_goal_id, project_id),
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    @staticmethod
    def _fact_dedupe_key(fact: Fact) -> str:
        payload = {
            "goal_id": fact.goal_id,
            "kind": fact.kind.value,
            "bullet": fact.bullet.strip(),
            "criterion_id": fact.criterion_id,
            "evidence": [_evidence_to_dict(item) for item in fact.evidence],
        }
        return hashlib.sha256(_json_dump(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _fact_record_bytes(
        fact: Fact,
        evidence_json: str,
        attestations_json: str,
        dedupe_key: str,
    ) -> int:
        """Count retained UTF-8 fact fields using the usage-reporting contract."""

        return sum(
            len(value.encode("utf-8"))
            for value in (
                fact.fact_id,
                fact.kind.value,
                fact.bullet.strip(),
                fact.criterion_id or "",
                evidence_json,
                attestations_json,
                dedupe_key,
                fact.source_event_id or "",
                fact.created_at,
            )
        )

    @classmethod
    def _fact_storage_payload(cls, fact: Fact) -> _FactStoragePayload:
        """Serialize indexed fact fields once before transaction capacity checks."""

        return _FactStoragePayload(
            evidence_json=_json_dump(
                [_evidence_to_dict(item) for item in fact.evidence]
            ),
            attestations_json=_json_dump(
                [
                    _attestation_to_dict(item)
                    for item in fact.verification_attestations
                ]
            ),
            dedupe_key=cls._fact_dedupe_key(fact),
        )

    def goal_fact_capacity(self, goal_id: str, project_id: str) -> FactCapacity:
        """Return the goal and project fact-history budget without pruning."""

        with self._lock:
            goal = self._connection.execute(
                "SELECT project_id FROM goals WHERE goal_id = ? AND project_id = ?",
                (goal_id, project_id),
            ).fetchone()
            if goal is None:
                raise NotFoundError(f"goal not found: {goal_id}")
            per_goal = self._connection.execute(
                """SELECT COUNT(*) AS count, COALESCE(SUM(
                     length(CAST(fact_id AS BLOB)) + length(CAST(kind AS BLOB)) +
                     length(CAST(bullet AS BLOB)) +
                     COALESCE(length(CAST(criterion_id AS BLOB)), 0) +
                     length(CAST(evidence_json AS BLOB)) +
                     length(CAST(verification_attestations_json AS BLOB)) +
                     COALESCE(length(CAST(source_event_id AS BLOB)), 0) +
                     length(CAST(dedupe_key AS BLOB)) + length(CAST(created_at AS BLOB))
                   ), 0) AS bytes FROM facts WHERE goal_id = ?""",
                (goal_id,),
            ).fetchone()
            project = self._connection.execute(
                """SELECT COUNT(*) AS count, COALESCE(SUM(
                     length(CAST(f.fact_id AS BLOB)) + length(CAST(f.kind AS BLOB)) +
                     length(CAST(f.bullet AS BLOB)) +
                     COALESCE(length(CAST(f.criterion_id AS BLOB)), 0) +
                     length(CAST(f.evidence_json AS BLOB)) +
                     length(CAST(f.verification_attestations_json AS BLOB)) +
                     COALESCE(length(CAST(f.source_event_id AS BLOB)), 0) +
                     length(CAST(f.dedupe_key AS BLOB)) + length(CAST(f.created_at AS BLOB))
                   ), 0) AS bytes FROM facts AS f
                   JOIN goals AS g ON g.goal_id = f.goal_id WHERE g.project_id = ?""",
                (project_id,),
            ).fetchone()
        goal_full = (
            per_goal["count"] >= MAX_FACTS_PER_GOAL
            or per_goal["bytes"] >= MAX_FACT_BYTES_PER_GOAL
        )
        project_full = (
            project["count"] >= MAX_FACTS_PER_PROJECT
            or project["bytes"] >= MAX_FACT_BYTES_PER_PROJECT
        )
        reached = goal_full or project_full
        return FactCapacity(
            goal_fact_count=per_goal["count"],
            goal_fact_bytes=per_goal["bytes"],
            goal_fact_count_limit=MAX_FACTS_PER_GOAL,
            goal_fact_bytes_limit=MAX_FACT_BYTES_PER_GOAL,
            goal_fact_count_remaining=max(0, MAX_FACTS_PER_GOAL - per_goal["count"]),
            goal_fact_bytes_remaining=max(0, MAX_FACT_BYTES_PER_GOAL - per_goal["bytes"]),
            project_fact_count=project["count"],
            project_fact_bytes=project["bytes"],
            project_fact_count_limit=MAX_FACTS_PER_PROJECT,
            project_fact_bytes_limit=MAX_FACT_BYTES_PER_PROJECT,
            project_fact_count_remaining=max(
                0, MAX_FACTS_PER_PROJECT - project["count"]
            ),
            project_fact_bytes_remaining=max(
                0, MAX_FACT_BYTES_PER_PROJECT - project["bytes"]
            ),
            append_available=not reached,
            open_gate=(
                "Fact history capacity reached; request an explicit approved "
                "compaction/retention action before resuming capture."
                if reached
                else None
            ),
        )

    @staticmethod
    def _fact_from_row(row: sqlite3.Row) -> Fact:
        evidence_data = json.loads(row["evidence_json"])
        attestation_data: object = json.loads(
            row["verification_attestations_json"]
        )
        if not isinstance(attestation_data, list):
            raise ValueError("stored verification attestations must be an array")
        evidence = tuple(
            EvidenceRef(
                item["evidence_kind"],
                item["locator"],
                item["sha256"],
                EvidenceOutcome(item["outcome"]),
                item.get("occurrence_id"),
            )
            for item in evidence_data
        )
        attestations: list[EvidenceAttestation] = []
        for raw_attestation in cast(list[object], attestation_data):
            if not isinstance(raw_attestation, dict):
                raise ValueError("stored verification attestation is malformed")
            attestation_mapping = cast(dict[str, object], raw_attestation)
            if any(
                not isinstance(value, str)
                for value in attestation_mapping.values()
            ):
                raise ValueError("stored verification attestation is malformed")
            attestations.append(
                EvidenceAttestation(**cast(dict[str, str], attestation_mapping))
            )
        return Fact(
            goal_id=row["goal_id"],
            kind=FactKind(row["kind"]),
            bullet=row["bullet"],
            fact_id=row["fact_id"],
            criterion_id=row["criterion_id"],
            evidence=evidence,
            verification_attestations=tuple(attestations),
            source_event_id=row["source_event_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _fact_archive_record(fact: Fact) -> dict[str, object]:
        return {
            "fact_id": fact.fact_id,
            "goal_id": fact.goal_id,
            "kind": fact.kind.value,
            "bullet": fact.bullet,
            "criterion_id": fact.criterion_id,
            "evidence": [
                _evidence_to_dict(item) for item in fact.evidence
            ],
            "verification_attestations": [
                _attestation_to_dict(item)
                for item in fact.verification_attestations
            ],
            "source_event_id": fact.source_event_id,
            "created_at": fact.created_at,
        }

    @staticmethod
    def _fact_archive_evidence(value: object) -> tuple[EvidenceRef, ...]:
        if not isinstance(value, list):
            raise FactArchiveIntegrityError("fact archive evidence schema is invalid")
        evidence: list[EvidenceRef] = []
        for raw_item in cast(list[object], value):
            if not isinstance(raw_item, dict):
                raise FactArchiveIntegrityError(
                    "fact archive evidence item schema is invalid"
                )
            item = cast(dict[str, object], raw_item)
            required = {"evidence_kind", "locator", "sha256", "outcome"}
            if not required.issubset(item) or not set(item).issubset(
                required | {"occurrence_id"}
            ):
                raise FactArchiveIntegrityError(
                    "fact archive evidence item fields are invalid"
                )
            values = tuple(
                item[key]
                for key in ("evidence_kind", "locator", "sha256", "outcome")
            )
            occurrence_id = item.get("occurrence_id")
            if any(not isinstance(item_value, str) for item_value in values) or (
                occurrence_id is not None and not isinstance(occurrence_id, str)
            ):
                raise FactArchiveIntegrityError(
                    "fact archive evidence values must be strings"
                )
            evidence.append(
                EvidenceRef(
                    cast(str, values[0]),
                    cast(str, values[1]),
                    cast(str, values[2]),
                    EvidenceOutcome(cast(str, values[3])),
                    occurrence_id,
                )
            )
        return tuple(evidence)

    @staticmethod
    def _fact_archive_attestations(value: object) -> tuple[EvidenceAttestation, ...]:
        if not isinstance(value, list):
            raise FactArchiveIntegrityError(
                "fact archive attestation schema is invalid"
            )
        attestation_fields = {
            "evidence_kind",
            "evidence_sha256",
            "project_id",
            "goal_id",
            "criterion_id",
            "adapter_id",
            "authenticated_subject",
            "source_revision",
            "observed_at",
            "verified_at",
            "valid_until",
            "revocation_checked_at",
        }
        attestations: list[EvidenceAttestation] = []
        for raw_attestation in cast(list[object], value):
            if not isinstance(raw_attestation, dict):
                raise FactArchiveIntegrityError(
                    "fact archive attestation item schema is invalid"
                )
            attestation = cast(dict[str, object], raw_attestation)
            if not attestation_fields.issubset(attestation) or not set(attestation).issubset(
                attestation_fields | {"occurrence_id"}
            ) or any(
                not isinstance(item, str) for item in attestation.values()
            ):
                raise FactArchiveIntegrityError(
                    "fact archive attestation fields are invalid"
                )
            attestations.append(
                EvidenceAttestation(**cast(dict[str, str], attestation))
            )
        return tuple(attestations)

    @classmethod
    def _build_fact_from_archive_record(cls, record: dict[str, object]) -> Fact:
        required = {
            "fact_id",
            "goal_id",
            "kind",
            "bullet",
            "criterion_id",
            "evidence",
            "created_at",
        }
        optional = {"verification_attestations", "source_event_id"}
        if not required.issubset(record) or not set(record).issubset(
            required | optional
        ):
            raise FactArchiveIntegrityError("fact archive record schema is invalid")

        values = tuple(
            record[key]
            for key in ("fact_id", "goal_id", "kind", "bullet", "created_at")
        )
        if any(not isinstance(value, str) for value in values):
            raise FactArchiveIntegrityError("fact archive record strings are invalid")
        fact_id, goal_id, kind_value, bullet, created_at = cast(
            tuple[str, str, str, str, str], values
        )
        criterion_id = record["criterion_id"]
        if criterion_id is not None and not isinstance(criterion_id, str):
            raise FactArchiveIntegrityError(
                "fact archive criterion_id must be a string or null"
            )
        source_event_id = record.get("source_event_id")
        if source_event_id is not None and not isinstance(source_event_id, str):
            raise FactArchiveIntegrityError(
                "fact archive source_event_id must be a string or null"
            )

        return Fact(
            goal_id=goal_id,
            kind=FactKind(kind_value),
            bullet=bullet,
            fact_id=fact_id,
            criterion_id=criterion_id,
            evidence=cls._fact_archive_evidence(record["evidence"]),
            verification_attestations=cls._fact_archive_attestations(
                record.get("verification_attestations", [])
            ),
            source_event_id=source_event_id,
            created_at=created_at,
        )

    @classmethod
    def _fact_from_archive_record(cls, value: object) -> Fact:
        if not isinstance(value, dict):
            raise FactArchiveIntegrityError("fact archive record schema is invalid")
        validation_failed = False
        fact: Fact | None = None
        try:
            fact = cls._build_fact_from_archive_record(  # pylint: disable=protected-access
                cast(dict[str, object], value)
            )
        except (KeyError, TypeError, ValueError):
            # Enum and domain errors may retain caller-controlled archive values.
            validation_failed = True
        if validation_failed:
            raise FactArchiveIntegrityError(
                "fact archive record failed domain validation"
            )
        if fact is None:
            raise FactArchiveIntegrityError(
                "fact archive record failed domain validation"
            )
        return fact

    @staticmethod
    def _decode_fact_archive_source(row: sqlite3.Row) -> object:
        if row["schema_version"] != 1:
            raise FactArchiveIntegrityError("unsupported fact archive version")
        compressed = bytes(row["payload_zlib"])
        if len(compressed) != row["compressed_bytes"]:
            raise FactArchiveIntegrityError("fact archive compressed size mismatch")
        if hashlib.sha256(compressed).hexdigest() != row["archive_sha256"]:
            raise FactArchiveIntegrityError("fact archive compressed hash mismatch")
        decoder = zlib.decompressobj()
        decompression_failed = False
        source = b""
        try:
            source = decoder.decompress(compressed, MAX_FACT_COMPACTION_SOURCE_BYTES + 1)
        except zlib.error:
            decompression_failed = True
        if decompression_failed:
            raise FactArchiveIntegrityError("fact archive compression is invalid")
        if (
            len(source) > MAX_FACT_COMPACTION_SOURCE_BYTES
            or decoder.unconsumed_tail
            or decoder.unused_data
            or not decoder.eof
        ):
            raise FactArchiveIntegrityError("fact archive exceeds its bounds or is truncated")
        if len(source) != row["source_bytes"]:
            raise FactArchiveIntegrityError("fact archive source size mismatch")
        if hashlib.sha256(source).hexdigest() != row["source_sha256"]:
            raise FactArchiveIntegrityError("fact archive source hash mismatch")
        parse_failed = False
        parsed: object = None
        try:
            parsed = json.loads(source)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Decoder exceptions retain some or all of the decompressed archive.
            parse_failed = True
        if parse_failed:
            raise FactArchiveIntegrityError("fact archive JSON is invalid")
        return parsed

    @classmethod
    def _fact_archive_records(cls, row: sqlite3.Row) -> list[object]:
        parsed = cls._decode_fact_archive_source(row)
        if not isinstance(parsed, list):
            raise FactArchiveIntegrityError("fact archive record count mismatch")
        records = cast(list[object], parsed)
        if len(records) != row["fact_count"]:
            raise FactArchiveIntegrityError("fact archive record count mismatch")
        return records

    @staticmethod
    def _validate_fact_archive_facts(facts: tuple[Fact, ...], goal_id: str) -> None:
        if len({fact.fact_id for fact in facts}) != len(facts):
            raise FactArchiveIntegrityError("fact archive contains duplicate IDs")
        if any(
            fact.goal_id != goal_id
            or fact.kind not in {FactKind.RESEARCH, FactKind.ADVICE}
            or fact.criterion_id is not None
            or fact.evidence
            for fact in facts
        ):
            raise FactArchiveIntegrityError("fact archive contains an ineligible fact")

    @classmethod
    def _decode_fact_archive(cls, row: sqlite3.Row) -> tuple[Fact, ...]:
        records = cls._fact_archive_records(row)
        facts = tuple(cls._fact_from_archive_record(item) for item in records)
        cls._validate_fact_archive_facts(facts, row["goal_id"])
        return facts
