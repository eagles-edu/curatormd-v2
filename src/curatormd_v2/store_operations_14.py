"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ConflictError,
    EventReceiptCompactionItem,
    EventReceiptCompactionProposal,
    EventQueueStatus,
    FactKind,
    GoalCard,
    GoalCriteriaAmendmentRequest,
    GoalStatus,
    MAX_CRITERIA_REVISIONS,
    MAX_EVENT_COMPACTION_PAGE,
    MAX_SUCCESS_CRITERIA,
    NotFoundError,
    ProjectOperationalCounts,
    ProjectReactivationReviewPacket,
    ProjectRegistrationTransitionResult,
    ProjectRegistryAuditRecord,
    ProjectStatusChangeRequest,
    ProjectStorageUsage,
    StagingArtifactInventory,
    _StagingInventorySummary,
    _json_dump,
    _validate_unique_amended_criteria_ids,
    asdict,
    hashlib,
    is_exact_int,
    json,
    new_id,
    utc_now,
)
from .store_operations_13 import StoreOperations5Part0

class StoreOperations5(StoreOperations5Part0):
    """Continuation of StoreOperations5 operations."""

    def propose_event_receipt_compaction(
        self, project_id: str, offset: int = 0, limit: int = 50
    ) -> EventReceiptCompactionProposal:
        """Return a paged, read-only manifest of processed payload-free events."""

        self._validate_access_identity(project_id, "project_id")
        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_EVENT_COMPACTION_PAGE:
            raise ValueError("limit is outside the bounded event compaction page size")

        query = """SELECT e.project_id, e.event_id, e.event_type,
                   e.payload_sha256, e.idempotency_sha256, e.received_at,
                   e.processed_at, e.source_id, e.source_sequence, e.attempts,
                   (SELECT COUNT(*) FROM event_retry_audit AS r
                    WHERE r.project_id = e.project_id AND r.event_id = e.event_id)
                       AS retry_audit_count,
                   (SELECT COUNT(*) FROM terminal_event_dispositions AS d
                    WHERE d.project_id = e.project_id AND d.event_id = e.event_id)
                       AS terminal_disposition_count,
                   (SELECT COUNT(*) FROM consumer_drain_events AS c
                    WHERE c.project_id = e.project_id AND c.event_id = e.event_id)
                       AS consumer_drain_reference_count
               FROM event_inbox AS e
               WHERE e.project_id = ? AND e.status = 'processed'
                 AND e.payload_json IS NULL AND e.processed_at IS NOT NULL
                 AND e.lease_owner IS NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM event_payload_scrub_queue AS q
                     WHERE q.project_id = e.project_id AND q.event_id = e.event_id
                 )
               ORDER BY e.event_id"""
        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("event compaction inventory cannot nest a transaction")
            self._connection.execute("BEGIN")
            try:
                digest = hashlib.sha256()
                eligible_count = 0
                page: list[EventReceiptCompactionItem] = []
                cursor = self._connection.execute(query, (project_id,))
                for row in cursor:
                    canonical = {key: row[key] for key in row.keys()}
                    digest.update(
                        json.dumps(
                            canonical, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8")
                    )
                    digest.update(b"\n")
                    if offset <= eligible_count < offset + limit:
                        page.append(EventReceiptCompactionItem(**canonical))
                    eligible_count += 1
                manifest_sha256 = digest.hexdigest()
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
        return EventReceiptCompactionProposal(
            project_id=project_id,
            eligible_count=eligible_count,
            offset=offset,
            limit=limit,
            manifest_sha256=manifest_sha256,
            items=tuple(page),
        )


    def amend_goal_criteria(
        self,
        request: GoalCriteriaAmendmentRequest,
    ) -> GoalCard:
        """Replace the active contract while retaining every immutable version."""

        if request.expected_revisions.lifecycle_revision is not None and (
            not is_exact_int(request.expected_revisions.lifecycle_revision)
            or request.expected_revisions.lifecycle_revision < 1
        ):
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if (
            request.fact.goal_id != request.goal_id
            or request.fact.kind is not FactKind.CRITERIA_AMENDED
        ):
            raise ConflictError("criteria amendment requires its system amendment fact")
        if (
            not is_exact_int(request.expected_revisions.criteria_revision)
            or request.expected_revisions.criteria_revision < 1
        ):
            raise ValueError("expected_revision must be a positive integer")
        if request.expected_revisions.criteria_revision >= MAX_CRITERIA_REVISIONS:
            raise ValueError(
                f"criteria history is limited to {MAX_CRITERIA_REVISIONS} revisions"
            )
        if not request.criteria or len(request.criteria) > MAX_SUCCESS_CRITERIA:
            raise ValueError(
                f"amended criteria must contain 1-{MAX_SUCCESS_CRITERIA} items"
            )
        _validate_unique_amended_criteria_ids(request.criteria)
        if (
            not request.reason.strip()
            or not request.next_action.strip()
            or len(request.next_action) > 1000
        ):
            raise ValueError("criteria amendment requires a bounded reason and next action")
        serialized = _json_dump([
            {"criterion_id": item.criterion_id, "description": item.description}
            for item in request.criteria
        ])
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, criteria_revision, criteria_json, lifecycle_revision "
                "FROM goals WHERE goal_id = ?",
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
                raise ConflictError("terminal goals cannot amend their criteria")
            if row["criteria_revision"] != request.expected_revisions.criteria_revision:
                raise ConflictError("criteria revision changed; reload before amending")
            expected_state_revision = (
                row["lifecycle_revision"]
                if request.expected_revisions.lifecycle_revision is None
                else request.expected_revisions.lifecycle_revision
            )
            if row["lifecycle_revision"] != expected_state_revision:
                raise ConflictError("goal lifecycle revision changed; reload before amending")
            if row["criteria_json"] == serialized:
                raise ConflictError("criteria amendment has no change")
            revision = request.expected_revisions.criteria_revision + 1
            created_at = utc_now()
            self._append_fact(connection, request.fact, request.project_id)
            connection.execute(
                "UPDATE goals SET criteria_json = ?, criteria_revision = ?, "
                "next_action = ?, lifecycle_revision = ?, updated_at = ? WHERE goal_id = ?",
                (
                    serialized,
                    revision,
                    request.next_action.strip(),
                    expected_state_revision + 1,
                    created_at,
                    request.goal_id,
                ),
            )
            connection.execute(
                "INSERT INTO goal_criteria_versions "
                "(goal_id, revision, criteria_json, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    request.goal_id,
                    revision,
                    serialized,
                    request.reason.strip(),
                    created_at,
                ),
            )
        return self.get_goal(request.goal_id, request.project_id)

    def project_health_inputs(
        self, project_id: str
    ) -> tuple[
        EventQueueStatus, ProjectOperationalCounts, ProjectStorageUsage, int, str
    ]:
        """Read queue/review/purge/storage/scrub health and time in one snapshot."""

        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("project health snapshot cannot nest a transaction")
            self._connection.execute("BEGIN")
            try:
                queue = self.event_queue_status(project_id)
                counts = self.project_operational_counts(project_id)
                usage = self.project_storage_usage(project_id)
                scrub_count = self.event_payload_scrub_pending_count(project_id)
                observed_at = utc_now()
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
        return queue, counts, usage, scrub_count, observed_at

    def project_reactivation_review_packet(
        self,
        project_id: str,
        staging_inventory: StagingArtifactInventory,
    ) -> ProjectReactivationReviewPacket:
        """Build one bounded-state review packet from DB and staging snapshots."""

        self._validate_access_identity(project_id, "project_id")
        with self._transaction() as connection:
            return self._project_reactivation_review_packet(
                connection,
                project_id,
                _StagingInventorySummary(
                    staging_inventory.manifest_sha256,
                    staging_inventory.usage.regular_file_count,
                    staging_inventory.usage.observed_file_bytes,
                    staging_inventory.usage.observed_at,
                ),
            )

    def set_project_status(
        self,
        request: ProjectStatusChangeRequest,
        actor_id: str,
    ) -> ProjectRegistrationTransitionResult:
        """Change project status once and recover the receipt on exact retry."""

        self._validate_access_identity(request.project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_identity(request.transition_id, "transition_id")
        status = self._validate_project_status(request.status)
        self._validate_access_rationale(request.rationale)
        if (
            not is_exact_int(request.expected_revision)
            or request.expected_revision < 1
        ):
            raise ValueError("expected_revision must be a positive integer")
        self._validate_project_status_request_fields(request, status)

        now = utc_now()
        with self._transaction() as connection:
            action = "suspended" if status == "suspended" else "reactivated"
            previous_transition = connection.execute(
                """SELECT * FROM project_registry_audit
                   WHERE project_id = ? AND transition_id = ?""",
                (request.project_id, request.transition_id),
            ).fetchone()
            if previous_transition is not None:
                if (
                    (
                        previous_transition["action"],
                        previous_transition["actor_id"],
                        previous_transition["revision"],
                        previous_transition["rationale"],
                        previous_transition["review_packet_sha256"],
                        previous_transition["suspension_transition_id"],
                    )
                    != (
                        action,
                        actor_id,
                        request.expected_revision + 1,
                        request.rationale,
                        request.review_packet_sha256,
                        request.suspension_transition_id,
                    )
                ):
                    raise ConflictError(
                        "project transition ID was already used with different input"
                    )
                return self._project_registration_transition_result(
                    connection, previous_transition, replayed=True
                )
            current = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (request.project_id,),
            ).fetchone()
            if current is None:
                raise NotFoundError("project registration not found")
            if connection.execute(
                "SELECT 1 FROM project_retirement_tombstones WHERE project_id = ?",
                (request.project_id,),
            ).fetchone() is not None:
                raise ConflictError("retired projects cannot be reactivated or changed")
            if current["revision"] != request.expected_revision:
                raise ConflictError("project registration revision is stale")
            old_status = current["status"]
            if old_status == status:
                raise ConflictError("project registration already has that status")
            review_packet: ProjectReactivationReviewPacket | None = None
            if status == "active":
                self._validate_reactivation_review_input(request)
                review_packet = self._project_reactivation_review_packet(
                    connection,
                    request.project_id,
                    _StagingInventorySummary(
                        request.staging_inventory_sha256,
                        request.staging_inventory_count,
                        request.staging_inventory_bytes,
                        request.staging_inventory_observed_at,
                    ),
                )
                if (
                    not review_packet.complete
                    or review_packet.packet_sha256 != request.review_packet_sha256
                    or review_packet.suspension_transition_id
                    != request.suspension_transition_id
                ):
                    raise ConflictError(
                        "reactivation review packet is incomplete or stale"
                    )
            cursor = connection.execute(
                """UPDATE project_registry SET status = ?, updated_by = ?,
                   updated_at = ?, revision = revision + 1
                   WHERE project_id = ? AND revision = ?""",
                (
                    status,
                    actor_id,
                    now,
                    request.project_id,
                    request.expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("project registration revision is stale")
            transition_receipt = ProjectRegistryAuditRecord(
                audit_id=new_id(),
                project_id=request.project_id,
                actor_id=actor_id,
                action=action,
                repository_fingerprint=current["repository_fingerprint"],
                config_sha256=current["config_sha256"],
                backend_api_version=current["backend_api_version"],
                rationale=request.rationale,
                created_at=now,
                revision=request.expected_revision + 1,
                transition_id=request.transition_id,
                review_packet_sha256=request.review_packet_sha256,
                review_packet_json=(
                    json.dumps(
                        asdict(review_packet),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if review_packet is not None
                    else None
                ),
                suspension_transition_id=request.suspension_transition_id,
            )
            self._append_project_registry_audit(
                connection,
                transition_receipt,
            )
            receipt_row = connection.execute(
                "SELECT * FROM project_registry_audit WHERE audit_id = ?",
                (transition_receipt.audit_id,),
            ).fetchone()
            if receipt_row is None:
                raise RuntimeError("project transition receipt insert returned no row")
            return self._project_registration_transition_result(
                connection, receipt_row, replayed=False
            )
