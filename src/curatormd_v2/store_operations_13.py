"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    AuditReceipt,
    ConflictError,
    EVENT_FAILURE_METADATA_RESERVE_BYTES,
    EventClaimError,
    EventDisposition,
    EventInboxCapacityError,
    EventInboxReceipt,
    EventInboxStatus,
    Fact,
    FactKind,
    GoalCard,
    GoalRetirementRequest,
    GoalStatus,
    GoalStatusStorageUsage,
    GoalTransitionRequest,
    MAX_EVENT_RECEIPT_BYTES_GLOBAL,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    NotFoundError,
    Path,
    ProjectReactivationReviewPacket,
    ProjectStorageUsage,
    SDECorrection,
    SDEQualityFeedback,
    TerminalEventDispositionRecord,
    TerminalEventDispositionStoreRequest,
    UTC,
    _ERROR_CODE_RE,
    _REACTIVATION_STAGING_MAX_AGE_SECONDS,
    _SHA256_RE,
    _StagingInventorySummary,
    _attestation_to_dict,
    _evidence_to_dict,
    _json_dump,
    _summarize_project_event_usage,
    _validate_reopen_relationships,
    _validate_replacement_goal,
    _validate_retirement_relationships,
    _validate_retirement_request,
    datetime,
    hashlib,
    is_exact_int,
    json,
    parse_optional_aware_timestamp,
    sqlite3,
    utc_now,
)
from .store_operations_12 import StoreOperations4

class StoreOperations5Part0(StoreOperations4):
    """Internal SQLite operation group ordered by method dependency."""


    def receipt_for_candidate(
        self, candidate_id: str, project_id: str
    ) -> AuditReceipt | None:
        """Return a candidate's immutable decision receipt within project scope."""

        with self._lock:
            row = self._connection.execute(
                """SELECT r.receipt_id FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.candidate_id = ? AND g.project_id = ?""",
                (candidate_id, project_id),
            ).fetchone()
        if row is None:
            # Validate the candidate scope even when it has no receipt.
            self.get_sde_candidate(candidate_id, project_id)
            return None
        return self.get_receipt(row["receipt_id"], project_id)

    def list_sde_corrections(
        self, candidate_id: str, project_id: str
    ) -> tuple[SDECorrection, ...]:
        """List linked corrections in a project-scoped stable order."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT c.* FROM sde_corrections AS c
                   JOIN sde_candidates AS s ON s.candidate_id = c.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE c.candidate_id = ? AND g.project_id = ?
                   ORDER BY c.created_at, c.correction_id""",
                (candidate_id, project_id),
            ).fetchall()
        if not rows:
            # Preserve not-found behavior for a foreign/unknown candidate.
            self.get_sde_candidate(candidate_id, project_id)
        return tuple(self._sde_correction_from_row(row) for row in rows)

    def list_sde_quality_feedback(
        self, candidate_id: str, project_id: str
    ) -> tuple[SDEQualityFeedback, ...]:
        """List reviewer feedback in deterministic project-scoped order."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT f.* FROM sde_quality_feedback AS f
                   JOIN sde_candidates AS s ON s.candidate_id = f.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE f.candidate_id = ? AND g.project_id = ?
                   ORDER BY f.created_at, f.feedback_id""",
                (candidate_id, project_id),
            ).fetchall()
        if not rows:
            self.get_sde_candidate(candidate_id, project_id)
        return tuple(self._sde_feedback_from_row(row) for row in rows)

    def facts_digest(
        self, fact_ids: tuple[str, ...], project_id: str | None = None
    ) -> str:
        """Hash canonical selected-fact content for review and receipt binding."""

        facts = [self.get_fact(fact_id, project_id) for fact_id in fact_ids]
        canonical = [
            {
                "fact_id": fact.fact_id,
                "goal_id": fact.goal_id,
                "kind": fact.kind.value,
                "bullet": fact.bullet,
                "criterion_id": fact.criterion_id,
                "evidence": [_evidence_to_dict(item) for item in fact.evidence],
                "verification_attestations": [
                    _attestation_to_dict(item)
                    for item in fact.verification_attestations
                ],
            }
            for fact in sorted(facts, key=lambda item: item.fact_id)
        ]
        return hashlib.sha256(_json_dump(canonical).encode("utf-8")).hexdigest()

    def terminally_dispose_event(
        self,
        request: TerminalEventDispositionStoreRequest,
    ) -> tuple[EventInboxReceipt, TerminalEventDispositionRecord]:
        """Resolve one failed event by exact human-approved terminal disposition."""

        self._validate_terminal_event_disposition_request(request)
        now = utc_now()
        with self._transaction() as connection:
            replay = self._terminal_event_disposition_replay(connection, request)
            if replay is None:
                self._require_terminal_disposition_binding(connection, request)
                row = self._require_terminal_disposition_event(
                    connection, request, now
                )
                self._advance_terminal_disposition_cursor(
                    connection, request, row, now
                )
                record = self._persist_terminal_event_disposition(
                    connection, request, row, now
                )
            else:
                record = replay[1]
        self.retry_pending_event_payload_scrubs()
        return self.event_receipt(request.project_id, request.event_id), record

    def project_storage_usage(self, project_id: str) -> ProjectStorageUsage:
        """Report logical retained bytes per project and physical DB files globally.

        Logical byte totals count UTF-8 record content, not SQLite page/index
        overhead. Database and WAL sizes are intentionally reported separately
        because one SQLite file may contain several projects.
        """

        with self._lock:
            record_rows = self._project_record_usage_rows(project_id)
            event_usage_rows = self._project_event_usage_rows(project_id)
        event_summary = _summarize_project_event_usage(event_usage_rows)
        logical_bytes = sum(
            row["bytes"]
            for row in (
                record_rows.goals,
                record_rows.facts,
                record_rows.candidates,
                record_rows.corrections,
                record_rows.feedback,
                record_rows.receipts,
                record_rows.artifacts,
                record_rows.auxiliary.event_cursors,
                record_rows.auxiliary.staging_artifact_times,
                record_rows.auxiliary.staging_artifact_occurrences,
                record_rows.auxiliary.expiry_purge_receipts,
                record_rows.auxiliary.expiry_purge_targets,
                record_rows.auxiliary.cleanup_authorizations,
                record_rows.archives,
            )
        ) + (
            event_summary.metadata_bytes
            + event_summary.retained_bytes
            + event_summary.retry_audit_bytes
            + event_summary.payload_scrub_bytes
        )

        database_path = Path(self.database) if self.database != ":memory:" else None
        database_bytes = (
            self._regular_file_size(database_path) if database_path is not None else None
        )
        wal_bytes = (
            self._regular_file_size(Path(f"{self.database}-wal"))
            if self.database != ":memory:"
            else None
        )
        return ProjectStorageUsage(
            project_id=project_id,
            goal_count=record_rows.goals["count"],
            goal_statuses=tuple(
                GoalStatusStorageUsage(GoalStatus(row["status"]), int(row["count"]))
                for row in record_rows.goal_statuses
            ),
            goal_record_bytes=record_rows.goals["bytes"],
            fact_count=record_rows.facts["count"],
            fact_record_bytes=record_rows.facts["bytes"],
            sde_candidate_count=record_rows.candidates["count"],
            sde_record_bytes=record_rows.candidates["bytes"],
            sde_correction_count=record_rows.corrections["count"],
            sde_correction_record_bytes=record_rows.corrections["bytes"],
            sde_quality_feedback_count=record_rows.feedback["count"],
            sde_quality_feedback_record_bytes=record_rows.feedback["bytes"],
            audit_receipt_count=record_rows.receipts["count"],
            audit_record_bytes=record_rows.receipts["bytes"],
            artifact_count=record_rows.artifacts["count"],
            artifact_record_bytes=record_rows.artifacts["bytes"],
            event_receipt_count=event_summary.event_count,
            event_payload_bytes_received=event_summary.original_bytes,
            event_payload_bytes_retained=event_summary.retained_bytes,
            event_cursor_count=record_rows.auxiliary.event_cursors["count"],
            event_cursor_record_bytes=record_rows.auxiliary.event_cursors["bytes"],
            event_retry_audit_count=event_summary.retry_audit_count,
            event_retry_audit_record_bytes=event_summary.retry_audit_bytes,
            staging_artifact_time_count=record_rows.auxiliary.staging_artifact_times["count"],
            staging_artifact_time_record_bytes=record_rows.auxiliary.staging_artifact_times[
                "bytes"
            ],
            staging_artifact_occurrence_count=record_rows.auxiliary.staging_artifact_occurrences[
                "count"
            ],
            staging_artifact_occurrence_record_bytes=(
                record_rows.auxiliary.staging_artifact_occurrences["bytes"]
            ),
            expiry_purge_receipt_count=record_rows.auxiliary.expiry_purge_receipts["count"],
            expiry_purge_receipt_record_bytes=record_rows.auxiliary.expiry_purge_receipts[
                "bytes"
            ],
            expiry_purge_target_count=record_rows.auxiliary.expiry_purge_targets["count"],
            expiry_purge_target_record_bytes=record_rows.auxiliary.expiry_purge_targets[
                "bytes"
            ],
            cleanup_authorization_count=record_rows.auxiliary.cleanup_authorizations["count"],
            cleanup_authorization_record_bytes=record_rows.auxiliary.cleanup_authorizations[
                "bytes"
            ],
            event_payload_scrub_count=event_summary.payload_scrub_count,
            event_payload_scrub_record_bytes=event_summary.payload_scrub_bytes,
            event_classes=event_summary.event_classes,
            event_failures=event_summary.failures,
            global_event_inbox=event_usage_rows.global_capacity,
            logical_record_bytes=logical_bytes,
            staging=None,
            global_database_bytes=database_bytes,
            global_wal_bytes=wal_bytes,
            fact_count_limit=MAX_FACTS_PER_PROJECT,
            fact_record_bytes_limit=MAX_FACT_BYTES_PER_PROJECT,
            fact_capacity_reached=(
                record_rows.facts["count"] >= MAX_FACTS_PER_PROJECT
                or record_rows.facts["bytes"] >= MAX_FACT_BYTES_PER_PROJECT
            ),
            fact_archive_batch_count=record_rows.archives["batches"],
            fact_archive_item_count=record_rows.archives["items"],
            fact_archive_compressed_bytes=record_rows.archives["compressed_bytes"],
            fact_archive_logical_bytes=record_rows.archives["bytes"],
            fact_archive_logical_bytes_limit=MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
            fact_archive_bytes_remaining=max(
                0,
                MAX_FACT_ARCHIVE_BYTES_PER_PROJECT
                - record_rows.archives["bytes"],
            ),
        )

    def mark_event_failed(
        self,
        project_id: str,
        event_id: str,
        error_code: str,
        *,
        discard_payload: bool = False,
        lease_owner: str | None = None,
    ) -> EventInboxReceipt:
        """Retain retry payloads except permanent storage-capacity failures."""

        if not _ERROR_CODE_RE.fullmatch(error_code):
            raise ValueError("error_code must be 1-128 safe identifier characters")
        failed_at = datetime.now(UTC)
        with self._transaction() as connection:
            payload_row = connection.execute(
                "SELECT payload_json FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
            if (
                discard_payload
                and payload_row is not None
                and payload_row["payload_json"] is not None
            ):
                self._queue_event_payload_scrub(connection, project_id, event_id)
            existing = connection.execute(
                "SELECT attempts FROM event_inbox WHERE project_id = ? AND event_id = ? "
                "AND status IN (?, ?)",
                (
                    project_id,
                    event_id,
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                ),
            ).fetchone()
            if existing is None:
                raise ConflictError("event is missing or already processed")
            next_attempt_at = self._event_failure_next_attempt_at(
                int(existing["attempts"]), failed_at, discard_payload
            )
            cursor = connection.execute(
                """UPDATE event_inbox SET status = ?, last_error = ?,
                   attempts = attempts + 1,
                   next_attempt_at = ?,
                   lease_owner = NULL, lease_expires_at = NULL,
                   payload_json = CASE WHEN ? THEN NULL ELSE payload_json END
                   WHERE project_id = ? AND event_id = ? AND status IN (?, ?)
                     AND ((? IS NULL AND (lease_owner IS NULL OR lease_expires_at IS NULL
                                          OR lease_expires_at <= ?))
                       OR (? IS NOT NULL AND lease_owner = ? AND lease_expires_at > ?))""",
                (
                    EventInboxStatus.FAILED.value,
                    error_code,
                    next_attempt_at,
                    int(discard_payload),
                    project_id,
                    event_id,
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                    lease_owner,
                    utc_now(),
                    lease_owner,
                    lease_owner,
                    utc_now(),
                ),
            )
            if cursor.rowcount != 1:
                self._raise_event_failure_transition_error(
                    project_id, event_id, lease_owner
                )
        if discard_payload:
            self.retry_pending_event_payload_scrubs()
        return self.event_receipt(project_id, event_id)

    def mark_event_processed(
        self,
        project_id: str,
        event_id: str,
        *,
        lease_owner: str | None = None,
        disposition: EventDisposition = EventDisposition.APPLIED,
    ) -> EventInboxReceipt:
        """Finalize an event and discard its payload, retaining its digest receipt."""

        with self._transaction() as connection:
            payload_row = connection.execute(
                "SELECT payload_json FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
            if payload_row is not None and payload_row["payload_json"] is not None:
                self._queue_event_payload_scrub(connection, project_id, event_id)
            cursor = connection.execute(
                """UPDATE event_inbox SET status = ?, payload_json = NULL,
                   processed_at = ?, last_error = NULL, next_attempt_at = NULL,
                   disposition = ?,
                   attempts = attempts + 1,
                   lease_owner = NULL, lease_expires_at = NULL
                   WHERE project_id = ? AND event_id = ? AND status IN (?, ?)
                     AND ((? IS NULL AND (lease_owner IS NULL OR lease_expires_at IS NULL
                                          OR lease_expires_at <= ?))
                       OR (? IS NOT NULL AND lease_owner = ? AND lease_expires_at > ?))""",
                (
                    EventInboxStatus.PROCESSED.value,
                    utc_now(),
                    disposition.value,
                    project_id,
                    event_id,
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                    lease_owner,
                    utc_now(),
                    lease_owner,
                    lease_owner,
                    utc_now(),
                ),
            )
            if cursor.rowcount != 1:
                current = connection.execute(
                    "SELECT status FROM event_inbox WHERE project_id = ? AND event_id = ?",
                    (project_id, event_id),
                ).fetchone()
                if current is None:
                    raise NotFoundError(f"event not found: {project_id}/{event_id}")
                if current["status"] != EventInboxStatus.PROCESSED.value:
                    claim = connection.execute(
                        "SELECT lease_owner, lease_expires_at FROM event_inbox "
                        "WHERE project_id = ? AND event_id = ?",
                        (project_id, event_id),
                    ).fetchone()
                    expires_at = claim["lease_expires_at"]
                    has_live_claim = (
                        claim["lease_owner"] is not None
                        and expires_at is not None
                        and expires_at > utc_now()
                    )
                    claim_lost = (
                        lease_owner is None and has_live_claim
                    ) or (
                        lease_owner is not None
                        and (
                            claim["lease_owner"] != lease_owner
                            or not has_live_claim
                        )
                    )
                    if claim_lost:
                        raise EventClaimError(
                            "event claim is missing, expired, or owned elsewhere"
                        )
                    raise ConflictError("event cannot transition to processed")
        self.retry_pending_event_payload_scrubs()
        return self.event_receipt(project_id, event_id)

    def quarantine_event(
        self, project_id: str, event_id: str, max_attempts: int
    ) -> EventInboxReceipt:
        """Move an exhausted failed event aside while preserving its payload."""

        if not is_exact_int(max_attempts) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        with self._transaction() as connection:
            cursor = connection.execute(
                """UPDATE event_inbox SET status = ?, next_attempt_at = NULL,
                   lease_owner = NULL, lease_expires_at = NULL
                   WHERE project_id = ? AND event_id = ? AND status = ?
                     AND attempts >= ? AND payload_json IS NOT NULL""",
                (
                    EventInboxStatus.QUARANTINED.value,
                    project_id,
                    event_id,
                    EventInboxStatus.FAILED.value,
                    max_attempts,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("event is not eligible for quarantine")
        return self.event_receipt(project_id, event_id)

    def retry_quarantined_event(
        self, project_id: str, event_id: str, actor_id: str
    ) -> EventInboxReceipt:
        """Audit an authorized retry request and return a quarantined event to queue."""

        if not _ERROR_CODE_RE.fullmatch(actor_id):
            raise ValueError("actor_id must be a bounded opaque identifier")
        with self._transaction() as connection:
            _receipt_count, retained_bytes = self._event_inbox_usage(connection)
            audit_bytes = sum(
                len(value.encode("utf-8"))
                for value in (project_id, event_id, actor_id, utc_now())
            )
            if (
                retained_bytes
                + audit_bytes
                + EVENT_FAILURE_METADATA_RESERVE_BYTES
                > MAX_EVENT_RECEIPT_BYTES_GLOBAL
            ):
                raise EventInboxCapacityError(
                    "global event inbox audit capacity reached; retry was not recorded"
                )
            cursor = connection.execute(
                """UPDATE event_inbox SET status = ?, attempts = 0, last_error = NULL,
                   next_attempt_at = NULL, lease_owner = NULL, lease_expires_at = NULL
                   WHERE project_id = ? AND event_id = ? AND status = ?
                     AND payload_json IS NOT NULL""",
                (
                    EventInboxStatus.FAILED.value,
                    project_id,
                    event_id,
                    EventInboxStatus.QUARANTINED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("event is not eligible for operator retry")
            connection.execute(
                """INSERT INTO event_retry_audit
                   (project_id, event_id, actor_id, created_at) VALUES (?, ?, ?, ?)""",
                (project_id, event_id, actor_id, utc_now()),
            )
        return self.event_receipt(project_id, event_id)

    def _project_reactivation_review_packet(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        staging: _StagingInventorySummary,
    ) -> ProjectReactivationReviewPacket:
        """Build the packet inside the caller's SQLite read/write snapshot."""

        registration = connection.execute(
            "SELECT * FROM project_registry WHERE project_id = ?", (project_id,)
        ).fetchone()
        binding = connection.execute(
            "SELECT * FROM consumer_bindings WHERE project_id = ?", (project_id,)
        ).fetchone()
        suspension = connection.execute(
            """SELECT transition_id, revision FROM project_registry_audit
               WHERE project_id = ? AND action = 'suspended'
               ORDER BY revision DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
        if registration is None:
            raise NotFoundError("project registration not found")
        staging_observed = parse_optional_aware_timestamp(
            staging.observed_at
        )
        complete = (
            registration["status"] == "suspended"
            and binding is not None
            and binding["status"] == "active"
            and suspension is not None
            and isinstance(staging.sha256, str)
            and _SHA256_RE.fullmatch(staging.sha256) is not None
            and is_exact_int(staging.file_count)
            and staging.file_count >= 0
            and is_exact_int(staging.observed_bytes)
            and staging.observed_bytes >= 0
            and staging_observed is not None
            and abs((datetime.now(UTC) - staging_observed).total_seconds())
            <= _REACTIVATION_STAGING_MAX_AGE_SECONDS
        )
        inventory = self._project_reactivation_inventory(connection, project_id)
        payload: dict[str, object] = {
            "project_id": project_id,
            "project_revision": registration["revision"],
            "suspension_transition_id": (
                suspension["transition_id"] if suspension is not None else ""
            ),
            "repository_fingerprint": registration["repository_fingerprint"],
            "config_sha256": registration["config_sha256"],
            "backend_api_version": registration["backend_api_version"],
            "binding_revision": binding["revision"] if binding is not None else 0,
            "source_epoch": binding["source_epoch"] if binding is not None else 0,
            "active_grant_count": inventory.active_grant_count,
            "grant_history_count": inventory.grant_history_count,
            "grants_sha256": inventory.grants_sha256,
            "source_cursor_count": inventory.cursor_count,
            "source_cursors_sha256": inventory.cursors_sha256,
            "event_count": inventory.event_count,
            "unresolved_event_count": inventory.unresolved_count,
            "events_sha256": inventory.events_sha256,
            "pending_purge_work_count": inventory.pending_purge_count,
            "purge_inventory_sha256": inventory.purge_digest,
            "staging_inventory_sha256": staging.sha256,
            "staging_inventory_count": staging.file_count or 0,
            "staging_inventory_bytes": staging.observed_bytes or 0,
        }
        packet_sha256 = None
        if complete:
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            packet_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return ProjectReactivationReviewPacket(
            project_id=project_id,
            project_revision=int(registration["revision"]),
            suspension_transition_id=(
                suspension["transition_id"] if suspension is not None else ""
            ),
            repository_fingerprint=registration["repository_fingerprint"],
            config_sha256=registration["config_sha256"],
            backend_api_version=int(registration["backend_api_version"]),
            binding_revision=int(binding["revision"]) if binding is not None else 0,
            source_epoch=int(binding["source_epoch"]) if binding is not None else 0,
            active_grant_count=inventory.active_grant_count,
            grant_history_count=inventory.grant_history_count,
            grants_sha256=inventory.grants_sha256,
            source_cursor_count=inventory.cursor_count,
            source_cursors_sha256=inventory.cursors_sha256,
            event_count=inventory.event_count,
            unresolved_event_count=inventory.unresolved_count,
            events_sha256=inventory.events_sha256,
            pending_purge_work_count=inventory.pending_purge_count,
            purge_inventory_sha256=inventory.purge_digest,
            staging_inventory_sha256=staging.sha256,
            staging_inventory_count=staging.file_count or 0,
            staging_inventory_bytes=staging.observed_bytes or 0,
            staging_inventory_observed_at=staging.observed_at or "",
            complete=complete,
            packet_sha256=packet_sha256,
        )

    def append_fact(
        self, fact: Fact, project_id: str | None = None
    ) -> tuple[Fact, bool]:
        """Append a non-lifecycle fact, returning the stored row and insert flag."""

        if fact.kind in {
            FactKind.REOPENED,
            FactKind.CRITERIA_AMENDED,
            FactKind.CANCELLED,
            FactKind.SUPERSEDED,
        }:
            raise ConflictError("lifecycle facts must use their atomic goal transition")
        with self._transaction() as connection:
            return self._append_fact(connection, fact, project_id)

    def transition_goal(
        self,
        request: GoalTransitionRequest,
    ) -> GoalCard:
        """Atomically write a lifecycle transition and its compact facts."""

        if (
            not is_exact_int(request.expected_lifecycle_revision)
            or request.expected_lifecycle_revision < 1
        ):
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if request.status not in {
            GoalStatus.COMPLETE,
            GoalStatus.OPEN,
            GoalStatus.BLOCKED,
            GoalStatus.DEFERRED,
        }:
            raise ConflictError(
                "transition_goal may target only complete, open, blocked, or deferred"
            )
        if request.next_action is not None and len(request.next_action) > 1000:
            raise ValueError("next_action exceeds 1000 characters")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, lifecycle_revision FROM goals WHERE goal_id = ?",
                (request.goal_id,),
            ).fetchone()
            if row is None or (
                request.project_id is not None
                and row["project_id"] != request.project_id
            ):
                raise NotFoundError(f"goal not found: {request.goal_id}")
            current_status = GoalStatus(row["status"])
            if current_status in {
                GoalStatus.COMPLETE,
                GoalStatus.CANCELLED,
                GoalStatus.SUPERSEDED,
            }:
                raise ConflictError("terminal goals cannot transition again")
            if current_status is GoalStatus.PLANNED and request.status not in {
                GoalStatus.BLOCKED,
                GoalStatus.DEFERRED,
            }:
                raise ConflictError(
                    "planned goals must be activated before finish evaluation"
                )
            if row["lifecycle_revision"] != request.expected_lifecycle_revision:
                raise ConflictError("goal lifecycle revision changed; reload before updating")
            for fact in request.facts:
                if fact.goal_id != request.goal_id:
                    raise ConflictError("transition facts must belong to the goal")
                self._append_fact(connection, fact, request.project_id)
            connection.execute(
                "UPDATE goals SET status = ?, next_action = ?, lifecycle_revision = ?, "
                "updated_at = ? "
                "WHERE goal_id = ?",
                (
                    request.status.value,
                    request.next_action,
                    request.expected_lifecycle_revision + 1,
                    utc_now(),
                    request.goal_id,
                ),
            )
        return self.get_goal(request.goal_id, request.project_id)

    def activate_goal(
        self,
        goal_id: str,
        fact: Fact,
        expected_lifecycle_revision: int,
        project_id: str | None = None,
    ) -> GoalCard:
        """Atomically activate a planned goal and record its acceptance fact."""

        if not is_exact_int(expected_lifecycle_revision) or expected_lifecycle_revision < 1:
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if fact.goal_id != goal_id or fact.kind is not FactKind.INTENT:
            raise ConflictError("activation requires its goal's intent fact")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, lifecycle_revision FROM goals WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
            if row is None or (
                project_id is not None and row["project_id"] != project_id
            ):
                raise NotFoundError(f"goal not found: {goal_id}")
            if row["status"] != GoalStatus.PLANNED.value:
                raise ConflictError("only planned goals can be activated")
            if row["lifecycle_revision"] != expected_lifecycle_revision:
                raise ConflictError(
                    "goal lifecycle revision changed; reload before activation"
                )
            self._append_fact(connection, fact, project_id)
            connection.execute(
                "UPDATE goals SET status = ?, lifecycle_revision = ?, "
                "updated_at = ? "
                "WHERE goal_id = ?",
                (
                    GoalStatus.ACTIVE.value,
                    expected_lifecycle_revision + 1,
                    utc_now(),
                    goal_id,
                ),
            )
        return self.get_goal(goal_id, project_id)

    def retire_goal(
        self,
        request: GoalRetirementRequest,
    ) -> GoalCard:
        """Atomically cancel or supersede a live goal with an immutable fact."""

        _validate_retirement_request(
            request.goal_id,
            request.status,
            request.reason,
            request.fact,
            request.replacement_goal_id,
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id FROM goals WHERE goal_id = ?",
                (request.goal_id,),
            ).fetchone()
            if row is None or (
                request.project_id is not None
                and row["project_id"] != request.project_id
            ):
                raise NotFoundError(f"goal not found: {request.goal_id}")
            if GoalStatus(row["status"]) in {
                GoalStatus.COMPLETE,
                GoalStatus.CANCELLED,
                GoalStatus.SUPERSEDED,
            }:
                raise ConflictError("terminal goals cannot be cancelled or superseded")
            project = row["project_id"]
            _validate_replacement_goal(
                connection, request.goal_id, project, request.replacement_goal_id
            )
            _validate_retirement_relationships(connection, request.goal_id, project)
            self._append_fact(connection, request.fact, request.project_id)
            connection.execute(
                "UPDATE goals SET status = ?, next_action = NULL, "
                "superseded_by_goal_id = ?, lifecycle_revision = lifecycle_revision + 1, "
                "updated_at = ? WHERE goal_id = ?",
                (
                    request.status.value,
                    request.replacement_goal_id,
                    utc_now(),
                    request.goal_id,
                ),
            )
        return self.get_goal(request.goal_id, request.project_id)

    def reopen_goal(
        self,
        goal_id: str,
        next_action: str,
        fact: Fact,
        expected_lifecycle_revision: int,
        project_id: str | None = None,
    ) -> GoalCard:
        """Start a new evidence epoch without invalidating completed relatives."""

        if not is_exact_int(expected_lifecycle_revision) or expected_lifecycle_revision < 1:
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if fact.goal_id != goal_id or fact.kind is not FactKind.REOPENED:
            raise ConflictError("reopen transition requires its system reopen fact")
        if not next_action.strip() or len(next_action) > 1000:
            raise ValueError("reopen requires a bounded concrete next action")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, parent_goal_id, lifecycle_revision "
                "FROM goals WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
            if row is None or (
                project_id is not None and row["project_id"] != project_id
            ):
                raise NotFoundError(f"goal not found: {goal_id}")
            if row["status"] != GoalStatus.COMPLETE.value:
                raise ConflictError("only completed goals can be reopened")
            if row["lifecycle_revision"] != expected_lifecycle_revision:
                raise ConflictError("goal lifecycle revision changed; reload before reopening")
            _validate_reopen_relationships(connection, goal_id, row)
            self._append_fact(connection, fact, project_id)
            connection.execute(
                "UPDATE goals SET status = ?, next_action = ?, lifecycle_revision = ?, "
                "updated_at = ? "
                "WHERE goal_id = ?",
                (
                    GoalStatus.ACTIVE.value,
                    next_action.strip(),
                    expected_lifecycle_revision + 1,
                    utc_now(),
                    goal_id,
                ),
            )
        return self.get_goal(goal_id, project_id)
