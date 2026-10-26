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
    ConflictError,
    ExpiryPurgeReceipt,
    MAX_ARTIFACTS_PER_RECEIPT,
    NotFoundError,
    ProjectGrantRecord,
    ProjectRegistryAuditRecord,
    PurgeStatus,
    SDEStatus,
    SQLITE_SCHEMA_VERSION,
    UTC,
    _PROJECT_ACCESS_ACTIONS,
    _initialize_unversioned_schema,
    apply_schema_migrations,
    datetime,
    hashlib,
    json,
    new_id,
    re,
    timedelta,
    utc_now,
)
from .store_operations_05 import StoreOperations1

class StoreOperations2Part0(StoreOperations1):
    """Internal SQLite operation group ordered by method dependency."""


    def project_registry_audit(
        self, project_id: str
    ) -> tuple[ProjectRegistryAuditRecord, ...]:
        """Return ordered, append-only project registration audit records."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM project_registry_audit WHERE project_id = ?
                   ORDER BY created_at, audit_id""",
                (project_id,),
            ).fetchall()
        return tuple(
            ProjectRegistryAuditRecord(
                audit_id=row["audit_id"],
                project_id=row["project_id"],
                actor_id=row["actor_id"],
                action=row["action"],
                repository_fingerprint=row["repository_fingerprint"],
                config_sha256=row["config_sha256"],
                backend_api_version=row["backend_api_version"],
                rationale=row["rationale"],
                created_at=row["created_at"],
                revision=row["revision"],
                transition_id=row["transition_id"],
                review_packet_sha256=row["review_packet_sha256"],
                review_packet_json=row["review_packet_json"],
                suspension_transition_id=row["suspension_transition_id"],
            )
            for row in rows
        )

    def add_project_grant(
        self,
        project_id: str,
        subject_id: str,
        action: str,
        granted_by: str,
        rationale: str,
    ) -> ProjectGrantRecord:
        """Persist one exact active project/action grant."""

        for value, field_name in (
            (project_id, "project_id"),
            (subject_id, "subject_id"),
            (granted_by, "granted_by"),
            (action, "action"),
        ):
            self._validate_access_identity(value, field_name)
        if action not in _PROJECT_ACCESS_ACTIONS:
            raise ValueError("action must be a known project authorization scope")
        self._validate_access_rationale(rationale)
        now = utc_now()
        grant_id = new_id()
        with self._transaction() as connection:
            project = connection.execute(
                "SELECT status FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                raise NotFoundError("project registration not found")
            if project["status"] != "active":
                raise ConflictError("project registration is not active")
            binding = connection.execute(
                "SELECT status FROM consumer_bindings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if binding is None or binding["status"] != "active":
                raise ConflictError("consumer binding is not active")
            active = connection.execute(
                """SELECT 1 FROM project_grants AS grant_row
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE grant_row.project_id = ? AND grant_row.subject_id = ?
                     AND grant_row.action = ? AND revocation.grant_id IS NULL
                   LIMIT 1""",
                (project_id, subject_id, action),
            ).fetchone()
            if active is not None:
                raise ConflictError("exact project grant is already active")
            connection.execute(
                """INSERT INTO project_grants
                   (grant_id, project_id, subject_id, action, granted_by,
                    rationale, granted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (grant_id, project_id, subject_id, action, granted_by, rationale, now),
            )
            row = connection.execute(
                """SELECT grant_row.*, NULL AS revoked_by,
                          NULL AS revoke_rationale, NULL AS revoked_at
                   FROM project_grants AS grant_row WHERE grant_id = ?""",
                (grant_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("project grant insert returned no row")
        return self._project_grant_from_row(row)

    def revoke_project_grant(
        self,
        project_id: str,
        subject_id: str,
        action: str,
        revoked_by: str,
        rationale: str,
    ) -> ProjectGrantRecord:
        """Append a revocation for the newest active exact grant."""

        for value, field_name in (
            (project_id, "project_id"),
            (subject_id, "subject_id"),
            (revoked_by, "revoked_by"),
            (action, "action"),
        ):
            self._validate_access_identity(value, field_name)
        if action not in _PROJECT_ACCESS_ACTIONS:
            raise ValueError("action must be a known project authorization scope")
        self._validate_access_rationale(rationale)
        now = utc_now()
        with self._transaction() as connection:
            row = connection.execute(
                """SELECT grant_row.* FROM project_grants AS grant_row
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE grant_row.project_id = ? AND grant_row.subject_id = ?
                     AND grant_row.action = ? AND revocation.grant_id IS NULL
                   ORDER BY grant_row.granted_at DESC, grant_row.grant_id DESC
                   LIMIT 1""",
                (project_id, subject_id, action),
            ).fetchone()
            if row is None:
                raise NotFoundError("active project grant not found")
            connection.execute(
                """INSERT INTO project_grant_revocations
                   (grant_id, revoked_by, rationale, revoked_at)
                   VALUES (?, ?, ?, ?)""",
                (row["grant_id"], revoked_by, rationale, now),
            )
            revoked = connection.execute(
                """SELECT grant_row.*, revocation.revoked_by,
                          revocation.rationale AS revoke_rationale,
                          revocation.revoked_at
                   FROM project_grants AS grant_row
                   JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE grant_row.grant_id = ?""",
                (row["grant_id"],),
            ).fetchone()
        if revoked is None:
            raise RuntimeError("project grant revocation returned no row")
        return self._project_grant_from_row(revoked)

    def has_project_grant(
        self, subject_id: str, project_id: str, action: str
    ) -> bool:
        """Check an exact active grant and active project registration."""

        for value, field_name in (
            (subject_id, "subject_id"),
            (project_id, "project_id"),
            (action, "action"),
        ):
            self._validate_access_identity(value, field_name)
        if action not in _PROJECT_ACCESS_ACTIONS:
            return False
        with self._lock:
            row = self._connection.execute(
                """SELECT 1 FROM project_registry AS project
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = project.project_id
                   JOIN project_grants AS grant_row
                     ON grant_row.project_id = project.project_id
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE project.project_id = ? AND project.status = 'active'
                     AND binding.status = 'active'
                     AND grant_row.subject_id = ? AND grant_row.action = ?
                     AND revocation.grant_id IS NULL LIMIT 1""",
                (project_id, subject_id, action),
            ).fetchone()
        return row is not None

    def project_grants(
        self, project_id: str
    ) -> tuple[ProjectGrantRecord, ...]:
        """Return the full grant and revocation history for one project."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            registered = self._connection.execute(
                "SELECT 1 FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if registered is None:
                raise NotFoundError("project registration not found")
            rows = self._connection.execute(
                """SELECT grant_row.*, revocation.revoked_by,
                          revocation.rationale AS revoke_rationale,
                          revocation.revoked_at
                   FROM project_grants AS grant_row
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE grant_row.project_id = ?
                   ORDER BY grant_row.granted_at, grant_row.grant_id""",
                (project_id,),
            ).fetchall()
        return tuple(self._project_grant_from_row(row) for row in rows)

    def _create_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS goals (
            goal_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL DEFAULT 'default',
            problem TEXT NOT NULL,
            criteria_json TEXT NOT NULL,
            owner TEXT,
            checklist_id TEXT,
            checklist_version TEXT,
            checklist_source_text TEXT,
            parent_goal_id TEXT,
            depends_on_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            next_action TEXT,
            superseded_by_goal_id TEXT,
            criteria_revision INTEGER NOT NULL DEFAULT 1,
            lifecycle_revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS goal_criteria_versions (
            goal_id TEXT NOT NULL REFERENCES goals(goal_id),
            revision INTEGER NOT NULL,
            criteria_json TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(goal_id, revision)
        );
        CREATE TABLE IF NOT EXISTS facts (
            fact_id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL REFERENCES goals(goal_id),
            kind TEXT NOT NULL,
            bullet TEXT NOT NULL,
            criterion_id TEXT,
            evidence_json TEXT NOT NULL,
            verification_attestations_json TEXT NOT NULL DEFAULT '[]',
            source_event_id TEXT,
            dedupe_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS facts_goal_created
            ON facts(goal_id, created_at, fact_id);
        CREATE TABLE IF NOT EXISTS fact_archives (
            compaction_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL DEFAULT 1,
            project_id TEXT NOT NULL,
            goal_id TEXT NOT NULL REFERENCES goals(goal_id),
            source_sha256 TEXT NOT NULL,
            archive_sha256 TEXT NOT NULL,
            source_bytes INTEGER NOT NULL,
            compressed_bytes INTEGER NOT NULL,
            fact_count INTEGER NOT NULL,
            payload_zlib BLOB NOT NULL,
            reviewer_id TEXT NOT NULL,
            approval_reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS fact_archives_project_created
            ON fact_archives(project_id, created_at, compaction_id);
        CREATE TABLE IF NOT EXISTS fact_archive_items (
            fact_id TEXT PRIMARY KEY,
            compaction_id TEXT NOT NULL REFERENCES fact_archives(compaction_id),
            project_id TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            dedupe_key TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS fact_archive_items_goal_created
            ON fact_archive_items(goal_id, created_at, fact_id);
        CREATE TABLE IF NOT EXISTS sde_candidates (
            candidate_id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL REFERENCES goals(goal_id),
            materiality TEXT NOT NULL,
            rationale TEXT NOT NULL,
            fact_ids_json TEXT NOT NULL,
            dedupe_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_receipts (
            receipt_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL UNIQUE REFERENCES sde_candidates(candidate_id),
            decision TEXT NOT NULL,
            facts_sha256 TEXT NOT NULL,
            artifact_inventory_complete INTEGER NOT NULL,
            reviewer_id TEXT,
            review_rationale TEXT,
            canonical_persisted INTEGER NOT NULL DEFAULT 0,
            canonical_target TEXT,
            canonical_sha256 TEXT,
            canonical_persisted_at TEXT,
            purge_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sde_corrections (
            correction_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL REFERENCES sde_candidates(candidate_id),
            correction TEXT NOT NULL,
            rationale TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sde_corrections_candidate_created
            ON sde_corrections(candidate_id, created_at, correction_id);
        CREATE TABLE IF NOT EXISTS purge_targets (
            receipt_id TEXT NOT NULL REFERENCES audit_receipts(receipt_id),
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL,
            last_attempt_at TEXT,
            next_attempt_at TEXT,
            retention_hold TEXT,
            hold_created_at TEXT,
            hold_created_by TEXT,
            hold_released_at TEXT,
            hold_released_by TEXT,
            hold_release_rationale TEXT,
            device_id INTEGER,
            inode_id INTEGER,
            outcome TEXT CHECK (outcome IN (
                'deleted', 'already_absent', 'held', 'changed', 'failed'
            )),
            PRIMARY KEY(receipt_id, path)
        );
        CREATE TABLE IF NOT EXISTS event_inbox (
            project_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'legacy.unknown',
            payload_sha256 TEXT NOT NULL,
            payload_bytes INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT,
            status TEXT NOT NULL,
            received_at TEXT NOT NULL,
            processed_at TEXT,
            last_error TEXT,
            next_attempt_at TEXT,
            lease_owner TEXT,
            lease_expires_at TEXT,
            disposition TEXT,
            PRIMARY KEY(project_id, event_id)
        );
        CREATE INDEX IF NOT EXISTS event_inbox_pending
            ON event_inbox(project_id, status, received_at, event_id);
        CREATE TABLE IF NOT EXISTS event_cursors (
            project_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            last_sequence INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(project_id, source_id)
        );
        """
        with self._transaction() as connection:
            schema_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if schema_version == SQLITE_SCHEMA_VERSION:
                return
            if schema_version != 0:
                apply_schema_migrations(connection, schema_version)
                return
            _initialize_unversioned_schema(connection, schema)

    def record_staging_artifact_time(
        self, project_id: str, artifact: ArtifactRef
    ) -> str:
        """Persist immutable V2 publication time without retaining file content."""

        if not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id
        ):
            raise ValueError("project_id must be a bounded opaque identifier")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT sha256, staged_at, device_id, inode_id, occurrence_id "
                "FROM staging_artifact_times "
                "WHERE project_id = ? AND path = ?",
                (project_id, artifact.path),
            ).fetchone()
            if row is not None:
                if row["sha256"] != artifact.sha256:
                    raise ConflictError("staging path already has different age metadata")
                if (
                    artifact.occurrence_id is not None
                    and row["occurrence_id"] == artifact.occurrence_id
                ):
                    self._record_staging_occurrence(connection, project_id, artifact)
                    return str(row["staged_at"])
                if artifact.device_id is None or artifact.inode_id is None:
                    return str(row["staged_at"])
                if (row["device_id"], row["inode_id"]) == (
                    artifact.device_id,
                    artifact.inode_id,
                ):
                    if artifact.occurrence_id is not None:
                        connection.execute(
                            "UPDATE staging_artifact_times SET occurrence_id = ? "
                            "WHERE project_id = ? AND path = ?",
                            (artifact.occurrence_id, project_id, artifact.path),
                        )
                    self._record_staging_occurrence(connection, project_id, artifact)
                    return str(row["staged_at"])
                staged_at = utc_now()
                connection.execute(
                    "UPDATE staging_artifact_times SET device_id = ?, inode_id = ?, "
                    "occurrence_id = ?, staged_at = ? WHERE project_id = ? AND path = ?",
                    (
                        artifact.device_id,
                        artifact.inode_id,
                        artifact.occurrence_id,
                        staged_at,
                        project_id,
                        artifact.path,
                    ),
                )
                self._record_staging_occurrence(connection, project_id, artifact)
                return staged_at
            prior_occurrence = connection.execute(
                "SELECT sha256, device_id, inode_id, occurrence_id "
                "FROM staging_artifact_occurrences "
                "WHERE project_id = ? AND path = ?",
                (project_id, artifact.path),
            ).fetchone()
            if prior_occurrence is not None:
                if (
                    prior_occurrence["sha256"] == artifact.sha256
                    and (prior_occurrence["device_id"], prior_occurrence["inode_id"])
                    == (artifact.device_id, artifact.inode_id)
                    and prior_occurrence["occurrence_id"] == artifact.occurrence_id
                    and artifact.device_id is not None
                    and artifact.inode_id is not None
                ):
                    occurrence_id = str(prior_occurrence["occurrence_id"])
                    staged_at = utc_now()
                    connection.execute(
                        "INSERT INTO staging_artifact_times "
                        "(project_id, path, sha256, staged_at, device_id, inode_id, occurrence_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            project_id,
                            artifact.path,
                            artifact.sha256,
                            staged_at,
                            artifact.device_id,
                            artifact.inode_id,
                            occurrence_id,
                        ),
                    )
                    self._record_staging_occurrence(
                        connection,
                        project_id,
                        ArtifactRef(
                            artifact.path,
                            artifact.sha256,
                            artifact.retention_hold,
                            artifact.device_id,
                            artifact.inode_id,
                            occurrence_id,
                        ),
                    )
                    return staged_at
                raise ConflictError(
                    "staging artifact path has prior history; use a new artifact ID"
                )
            staged_at = utc_now()
            connection.execute(
                "INSERT INTO staging_artifact_times "
                "(project_id, path, sha256, staged_at, device_id, inode_id, occurrence_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    artifact.path,
                    artifact.sha256,
                    staged_at,
                    artifact.device_id,
                    artifact.inode_id,
                    artifact.occurrence_id,
                ),
            )
            self._record_staging_occurrence(connection, project_id, artifact)
            return staged_at

    def bind_staging_artifact_occurrences(
        self, project_id: str, artifacts: tuple[ArtifactRef, ...]
    ) -> tuple[ArtifactRef, ...]:
        """Attach durable generation IDs to exact path/hash/file identities."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        bound: list[ArtifactRef] = []
        with self._transaction() as connection:
            for artifact in artifacts:
                occurrence_id: str | None = None
                if artifact.device_id is not None and artifact.inode_id is not None:
                    row = connection.execute(
                        """SELECT occurrence_id FROM staging_artifact_occurrences
                           WHERE project_id = ? AND path = ? AND sha256 = ?
                             AND device_id = ? AND inode_id = ?""",
                        (
                            project_id,
                            artifact.path,
                            artifact.sha256,
                            artifact.device_id,
                            artifact.inode_id,
                        ),
                    ).fetchone()
                    if row is not None:
                        occurrence_id = row["occurrence_id"]
                    else:
                        occurrence_id = artifact.occurrence_id or new_id()
                        self._record_staging_occurrence(
                            connection,
                            project_id,
                            ArtifactRef(
                                artifact.path,
                                artifact.sha256,
                                artifact.retention_hold,
                                artifact.device_id,
                                artifact.inode_id,
                                occurrence_id,
                            ),
                        )
                bound.append(
                    ArtifactRef(
                        artifact.path,
                        artifact.sha256,
                        artifact.retention_hold,
                        artifact.device_id,
                        artifact.inode_id,
                        occurrence_id,
                    )
                )
        return tuple(bound)

    def create_cleanup_authorization(
        self,
        receipt_id: str,
        project_id: str,
        reviewer_id: str,
        manifest_sha256: str,
        dependency_map_sha256: str,
    ) -> CleanupAuthorizationReceipt:
        """Durably authorize an exact complete SDE inventory before projection."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", reviewer_id):
            raise ValueError("cleanup reviewer must be a bounded opaque identifier")
        if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
            raise ValueError("cleanup manifest must be a lowercase SHA-256")
        if not re.fullmatch(r"[0-9a-f]{64}", dependency_map_sha256):
            raise ValueError("cleanup dependency map must be a lowercase SHA-256")
        approved_at = utc_now()
        with self._transaction() as connection:
            self._validate_cleanup_authorization_inventory(
                connection,
                receipt_id,
                project_id,
                manifest_sha256,
            )
            existing = connection.execute(
                "SELECT * FROM cleanup_authorizations WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["project_id"] != project_id
                    or existing["manifest_sha256"] != manifest_sha256
                    or existing["dependency_map_sha256"] != dependency_map_sha256
                ):
                    raise ConflictError(
                        "cleanup authorization is bound to another inventory or dependency map"
                    )
                if existing["reviewer_id"] != reviewer_id:
                    raise ConflictError("cleanup authorization reviewer is immutable")
                return CleanupAuthorizationReceipt(
                    receipt_id=receipt_id,
                    project_id=project_id,
                    reviewer_id=existing["reviewer_id"],
                    manifest_sha256=manifest_sha256,
                    dependency_map_sha256=existing["dependency_map_sha256"],
                    approved_at=existing["approved_at"],
                    canonical_persisted=bool(existing["canonical_persisted"]),
                    canonical_target=existing["canonical_target"],
                    canonical_sha256=existing["canonical_sha256"],
                    canonical_persisted_at=existing["canonical_persisted_at"],
                )
            connection.execute(
                """INSERT INTO cleanup_authorizations
                   (receipt_id, project_id, reviewer_id, manifest_sha256,
                    dependency_map_sha256, approved_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    receipt_id,
                    project_id,
                    reviewer_id,
                    manifest_sha256,
                    dependency_map_sha256,
                    approved_at,
                ),
            )
        return CleanupAuthorizationReceipt(
            receipt_id,
            project_id,
            reviewer_id,
            manifest_sha256,
            dependency_map_sha256,
            approved_at,
        )

    def mark_cleanup_authorization_canonical_persisted(
        self,
        receipt_id: str,
        project_id: str,
        target: str,
        sha256: str,
    ) -> CleanupAuthorizationReceipt:
        """Record the projection containing the cleanup authorization receipt."""

        if not target.strip() or len(target) > 2000 or "\n" in target or "\r" in target:
            raise ValueError("cleanup canonical target must be bounded and one line")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("cleanup canonical hash must be lowercase SHA-256")
        persisted_at = utc_now()
        with self._transaction() as connection:
            row = connection.execute(
                """SELECT canonical_persisted, canonical_target, canonical_sha256
                   FROM cleanup_authorizations
                   WHERE receipt_id = ? AND project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("cleanup authorization receipt not found")
            if bool(row["canonical_persisted"]):
                if row["canonical_target"] != target or row["canonical_sha256"] != sha256:
                    raise ConflictError("cleanup canonical proof is immutable")
            else:
                connection.execute(
                    """UPDATE cleanup_authorizations SET canonical_persisted = 1,
                       canonical_target = ?, canonical_sha256 = ?,
                       canonical_persisted_at = ? WHERE receipt_id = ?""",
                    (target, sha256, persisted_at, receipt_id),
                )
        authorization = self.cleanup_authorization(receipt_id, project_id)
        if authorization is None:
            raise NotFoundError("cleanup authorization receipt not found")
        return authorization

    def create_expiry_purge_receipt(
        self,
        project_id: str,
        reviewer_id: str,
        manifest_sha256: str,
        artifacts: tuple[ArtifactRef, ...],
    ) -> ExpiryPurgeReceipt:
        """Record exact attended expiry approval before the first unlink."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", reviewer_id):
            raise ValueError("reviewer_id must be a bounded opaque identifier")
        if not 1 <= len(artifacts) <= MAX_ARTIFACTS_PER_RECEIPT:
            raise ValueError("expiry inventory must contain 1-500 artifacts")
        if len({item.path for item in artifacts}) != len(artifacts):
            raise ValueError("expiry inventory paths must be unique")
        canonical = json.dumps(
            [
                (item.path, item.sha256, item.occurrence_id)
                for item in sorted(artifacts, key=lambda item: item.path)
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        observed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if manifest_sha256 != observed_hash:
            raise ConflictError("expiry manifest hash does not match the exact inventory")
        if self.active_staging_artifact_holds(project_id, artifacts):
            raise ConflictError("held artifacts must be separately released before expiry")
        receipt_id = new_id()
        created_at = utc_now()
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO expiry_purge_receipts
                   (receipt_id, project_id, reviewer_id, manifest_sha256,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    receipt_id,
                    project_id,
                    reviewer_id,
                    manifest_sha256,
                    PurgeStatus.PURGE_PENDING.value,
                    created_at,
                    created_at,
                ),
            )
            connection.executemany(
                """INSERT INTO expiry_purge_targets
                   (receipt_id, path, sha256, status, created_at, device_id, inode_id,
                    occurrence_id, approval_stale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        receipt_id,
                        item.path,
                        item.sha256,
                        ArtifactStatus.PENDING.value,
                        created_at,
                        item.device_id,
                        item.inode_id,
                        item.occurrence_id,
                        int(item.occurrence_id is None),
                    )
                    for item in artifacts
                ),
            )
        return self.expiry_purge_receipt(receipt_id, project_id)

    def begin_expiry_purge_attempt(
        self, receipt_id: str, path: str, project_id: str, goal_id: str
    ) -> bool:
        """Claim one approved target only when due and not under an active hold."""

        now = utc_now()
        with self._transaction() as connection:
            target = connection.execute(
                """SELECT t.sha256, t.occurrence_id, t.approval_stale FROM expiry_purge_targets AS t
                   JOIN expiry_purge_receipts AS r ON r.receipt_id = t.receipt_id
                   WHERE t.receipt_id = ? AND t.path = ? AND r.project_id = ?
                     AND t.status IN (?, ?)
                     AND t.approval_stale = 0
                     AND (t.next_attempt_at IS NULL OR t.next_attempt_at <= ?)""",
                (
                    receipt_id,
                    path,
                    project_id,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                    now,
                ),
            ).fetchone()
            if target is None:
                return False
            held = connection.execute(
                """SELECT 1 FROM purge_targets AS p
                   JOIN audit_receipts AS ar ON ar.receipt_id = p.receipt_id
                   JOIN sde_candidates AS s ON s.candidate_id = ar.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ? AND p.path = ? AND p.sha256 = ?
                     AND p.retention_hold IS NOT NULL AND p.hold_released_at IS NULL
                   LIMIT 1""",
                (project_id, path, target["sha256"]),
            ).fetchone()
            if held is not None:
                return False
            pending_sde = connection.execute(
                """SELECT 1 FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ? AND s.goal_id = ? AND s.status = ?
                   LIMIT 1""",
                (project_id, goal_id, SDEStatus.PENDING_REVIEW.value),
            ).fetchone()
            if pending_sde is not None:
                age = connection.execute(
                    """SELECT staged_at FROM staging_artifact_times
                       WHERE project_id = ? AND path = ? AND sha256 = ?""",
                    (project_id, path, target["sha256"]),
                ).fetchone()
                if age is None:
                    return False
                try:
                    staged_at = datetime.fromisoformat(
                        str(age["staged_at"]).replace("Z", "+00:00")
                    )
                    observed_at = datetime.fromisoformat(now.replace("Z", "+00:00"))
                except ValueError:
                    return False
                if (
                    staged_at.tzinfo is None
                    or staged_at.utcoffset() is None
                    or observed_at.tzinfo is None
                    or observed_at.utcoffset() is None
                    or staged_at.astimezone(UTC)
                    > observed_at.astimezone(UTC) - timedelta(hours=72)
                ):
                    return False
            cursor = connection.execute(
                """UPDATE expiry_purge_targets
                   SET attempts = attempts + 1, last_attempt_at = ?
                   WHERE receipt_id = ? AND path = ? AND status IN (?, ?)
                     AND approval_stale = 0""",
                (
                    now,
                    receipt_id,
                    path,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                ),
            )
            return cursor.rowcount == 1
