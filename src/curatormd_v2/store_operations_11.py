"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ConflictError,
    ConsumerBindingTransitionRequest,
    ConsumerBindingTransitionResult,
    EventInboxStatus,
    Fact,
    FactArchiveReceipt,
    FactCapacityError,
    FactCompactionApprovalRequest,
    FactKind,
    GoalCard,
    GoalListCapacityError,
    GoalStatus,
    MAX_FACTS_PER_GOAL,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_GOAL,
    MAX_FACT_BYTES_PER_PROJECT,
    MAX_GOAL_LIST_PAGE,
    NotFoundError,
    ProjectControlPlaneStorageUsage,
    ProjectLifecycleStatusSnapshot,
    SDECandidate,
    StorageClassUsage,
    _ConsumerBindingTransitionPlan,
    _PROJECT_EVENT_USAGE_SQL,
    _ProjectEventUsageRows,
    _ProjectReactivationInventory,
    _ProjectRecordUsageRows,
    is_exact_int,
    sqlite3,
    utc_now,
)
from .store_operations_10 import StoreOperations4Part0

class StoreOperations4Part1(StoreOperations4Part0):
    """Continuation of StoreOperations4 operations."""


    def _project_record_usage_rows(self, project_id: str) -> _ProjectRecordUsageRows:
        """Query logical non-event record usage for one project."""

        goal_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(g.project_id AS BLOB)) +
                 length(CAST(g.goal_id AS BLOB)) +
                 length(CAST(g.problem AS BLOB)) +
                 length(CAST(g.criteria_json AS BLOB)) +
                 COALESCE(length(CAST(g.owner AS BLOB)), 0) +
                 COALESCE(length(CAST(g.checklist_id AS BLOB)), 0) +
                 COALESCE(length(CAST(g.checklist_version AS BLOB)), 0) +
                 COALESCE(length(CAST(g.checklist_source_text AS BLOB)), 0) +
                 COALESCE(length(CAST(g.parent_goal_id AS BLOB)), 0) +
                 length(CAST(g.depends_on_json AS BLOB)) +
                 length(CAST(g.status AS BLOB)) +
                 COALESCE(length(CAST(g.next_action AS BLOB)), 0) +
                 length(CAST(g.criteria_revision AS TEXT)) +
                 length(CAST(g.lifecycle_revision AS TEXT)) +
                 COALESCE(length(CAST(g.superseded_by_goal_id AS BLOB)), 0) +
                 COALESCE(length(CAST(g.initial_status AS BLOB)), 0) +
                 COALESCE(length(CAST(g.source_event_id AS BLOB)), 0) +
                 length(CAST(g.created_at AS BLOB)) +
                 length(CAST(g.updated_at AS BLOB)) +
                 COALESCE((SELECT SUM(
                   length(CAST(v.goal_id AS BLOB)) +
                   length(CAST(v.criteria_json AS BLOB)) +
                   length(CAST(v.reason AS BLOB)) +
                   length(CAST(v.created_at AS BLOB)) +
                   length(CAST(v.revision AS TEXT))
                 ) FROM goal_criteria_versions AS v WHERE v.goal_id = g.goal_id), 0)
               ), 0) AS bytes FROM goals AS g WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        goal_statuses = self._connection.execute(
            "SELECT status, COUNT(*) AS count FROM goals "
            "WHERE project_id = ? GROUP BY status ORDER BY status",
            (project_id,),
        ).fetchall()
        fact_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(f.fact_id AS BLOB)) +
                 length(CAST(f.goal_id AS BLOB)) +
                 length(CAST(f.kind AS BLOB)) +
                 length(CAST(f.bullet AS BLOB)) +
                 COALESCE(length(CAST(f.criterion_id AS BLOB)), 0) +
                 length(CAST(f.evidence_json AS BLOB)) +
                 length(CAST(f.verification_attestations_json AS BLOB)) +
                 COALESCE(length(CAST(f.source_event_id AS BLOB)), 0) +
                 length(CAST(f.dedupe_key AS BLOB)) +
                 length(CAST(f.created_at AS BLOB))
               ), 0) AS bytes
               FROM facts AS f JOIN goals AS g ON g.goal_id = f.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        archive_usage = self._connection.execute(
            """SELECT COUNT(*) AS batches,
                      COALESCE(SUM(fact_count), 0) AS items,
                      COALESCE(SUM(compressed_bytes), 0) AS compressed_bytes,
                      COALESCE(SUM(
                        length(CAST(compaction_id AS BLOB)) +
                        length(CAST(schema_version AS TEXT)) +
                        length(CAST(project_id AS BLOB)) +
                        length(CAST(goal_id AS BLOB)) +
                        length(CAST(source_sha256 AS BLOB)) +
                        length(CAST(archive_sha256 AS BLOB)) +
                        length(CAST(source_bytes AS TEXT)) +
                        length(CAST(compressed_bytes AS TEXT)) +
                        length(CAST(fact_count AS TEXT)) +
                        length(CAST(reviewer_id AS BLOB)) +
                        length(CAST(approval_reason AS BLOB)) +
                        length(CAST(created_at AS BLOB)) +
                        length(CAST(payload_zlib AS BLOB))
                      ), 0) + COALESCE((
                        SELECT SUM(length(CAST(fact_id AS BLOB)) +
                                   length(CAST(compaction_id AS BLOB)) +
                                   length(CAST(project_id AS BLOB)) +
                                   length(CAST(goal_id AS BLOB)) +
                                   length(CAST(dedupe_key AS BLOB)) +
                                   length(CAST(created_at AS BLOB)) )
                        FROM fact_archive_items WHERE project_id = ?
                      ), 0) AS bytes
               FROM fact_archives WHERE project_id = ?""",
            (project_id, project_id),
        ).fetchone()
        candidate_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(s.candidate_id AS BLOB)) +
                 length(CAST(s.goal_id AS BLOB)) +
                 length(CAST(s.materiality AS BLOB)) +
                 length(CAST(s.rationale AS BLOB)) +
                 COALESCE(length(CAST(s.impact AS BLOB)), 0) +
                 COALESCE(length(CAST(s.retrieval_value AS BLOB)), 0) +
                 length(CAST(s.fact_ids_json AS BLOB)) +
                 length(CAST(s.dedupe_key AS BLOB)) +
                 length(CAST(s.status AS BLOB)) +
                 length(CAST(s.created_at AS BLOB))
               ), 0) AS bytes
               FROM sde_candidates AS s JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        correction_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(c.correction_id AS BLOB)) +
                 length(CAST(c.candidate_id AS BLOB)) +
                 length(CAST(c.correction AS BLOB)) +
                 length(CAST(c.rationale AS BLOB)) +
                 length(CAST(c.reviewer_id AS BLOB)) +
                 length(CAST(c.created_at AS BLOB))
               ), 0) AS bytes
               FROM sde_corrections AS c
               JOIN sde_candidates AS s ON s.candidate_id = c.candidate_id
               JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        feedback_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(f.feedback_id AS BLOB)) +
                 length(CAST(f.candidate_id AS BLOB)) +
                 length(CAST(f.reviewer_id AS BLOB)) +
                 length(CAST(f.label AS BLOB)) +
                 length(CAST(f.rationale AS BLOB)) +
                 length(CAST(f.created_at AS BLOB))
               ), 0) AS bytes
               FROM sde_quality_feedback AS f
               JOIN sde_candidates AS s ON s.candidate_id = f.candidate_id
               JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        receipt_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(r.receipt_id AS BLOB)) +
                 length(CAST(r.candidate_id AS BLOB)) +
                 length(CAST(r.decision AS BLOB)) +
                 length(CAST(r.facts_sha256 AS BLOB)) +
                 length(CAST(r.artifact_inventory_complete AS TEXT)) +
                 COALESCE(length(CAST(r.reviewer_id AS BLOB)), 0) +
                 COALESCE(length(CAST(r.review_rationale AS BLOB)), 0) +
                 length(CAST(r.canonical_persisted AS TEXT)) +
                 COALESCE(length(CAST(r.canonical_target AS BLOB)), 0) +
                 COALESCE(length(CAST(r.canonical_sha256 AS BLOB)), 0) +
                 COALESCE(length(CAST(r.canonical_persisted_at AS BLOB)), 0) +
                 length(CAST(r.purge_status AS BLOB)) +
                 length(CAST(r.created_at AS BLOB)) +
                 length(CAST(r.updated_at AS BLOB))
               ), 0) AS bytes
               FROM audit_receipts AS r
               JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
               JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        artifact_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(p.path AS BLOB)) +
                 length(CAST(p.sha256 AS BLOB)) +
                 length(CAST(p.status AS BLOB)) +
                 length(CAST(p.attempts AS TEXT)) +
                 COALESCE(length(CAST(p.error AS BLOB)), 0) +
                 length(CAST(p.created_at AS BLOB)) +
                 COALESCE(length(CAST(p.last_attempt_at AS BLOB)), 0) +
                 COALESCE(length(CAST(p.next_attempt_at AS BLOB)), 0) +
                 length(CAST(p.retention_hold AS TEXT)) +
                 COALESCE(length(CAST(p.hold_created_at AS BLOB)), 0) +
                 COALESCE(length(CAST(p.hold_created_by AS BLOB)), 0) +
                 COALESCE(length(CAST(p.hold_released_at AS BLOB)), 0) +
                 COALESCE(length(CAST(p.hold_released_by AS BLOB)), 0) +
                 COALESCE(length(CAST(p.hold_release_rationale AS BLOB)), 0) +
                 COALESCE(length(CAST(p.device_id AS TEXT)), 0) +
                 COALESCE(length(CAST(p.inode_id AS TEXT)), 0) +
                 COALESCE(length(CAST(p.occurrence_id AS BLOB)), 0) +
                 length(CAST(p.approval_stale AS TEXT)) +
                 COALESCE(length(CAST(p.reacquisition_action AS BLOB)), 0) +
                 COALESCE(length(CAST(p.outcome AS BLOB)), 0)
               ), 0) AS bytes
               FROM purge_targets AS p
               JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
               JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
               JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE g.project_id = ?""",
            (project_id,),
        ).fetchone()
        auxiliary_usage = self._project_auxiliary_usage_rows(project_id)
        return _ProjectRecordUsageRows(
            goals=goal_usage,
            goal_statuses=goal_statuses,
            facts=fact_usage,
            archives=archive_usage,
            candidates=candidate_usage,
            corrections=correction_usage,
            feedback=feedback_usage,
            receipts=receipt_usage,
            artifacts=artifact_usage,
            auxiliary=auxiliary_usage,
        )

    def _project_event_usage_rows(self, project_id: str) -> _ProjectEventUsageRows:
        """Query content-free event usage and global inbox capacity."""

        event_rows = self._connection.execute(
            _PROJECT_EVENT_USAGE_SQL, (project_id,)
        ).fetchall()
        failure_rows = self._connection.execute(
            """SELECT CASE last_error
                 WHEN 'EvidenceGateError' THEN 'evidence_rejected'
                 WHEN 'EvidenceAdapterError' THEN 'evidence_adapter_error'
                 ELSE 'other' END AS category,
                 COUNT(*) AS count
               FROM event_inbox
               WHERE project_id = ? AND status IN (?, ?)
               GROUP BY category""",
            (
                project_id,
                EventInboxStatus.FAILED.value,
                EventInboxStatus.QUARANTINED.value,
            ),
        ).fetchall()
        retry_audit_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(event_id AS BLOB)) +
                 length(CAST(actor_id AS BLOB)) +
                 length(CAST(created_at AS BLOB))
               ), 0) AS bytes
               FROM event_retry_audit WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        payload_scrub_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(scrub_id AS TEXT)) +
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(event_id AS BLOB)) +
                 length(CAST(queued_at AS BLOB)) +
                 length(CAST(attempts AS TEXT)) +
                 COALESCE(length(CAST(last_error_code AS BLOB)), 0)
               ), 0) AS bytes
               FROM event_payload_scrub_queue WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        global_event_count, global_event_bytes = self._event_inbox_usage(
            self._connection
        )
        global_scrub_usage = self._event_payload_scrub_usage(self._connection)
        global_capacity = self._global_event_inbox_capacity(
            global_event_count, global_event_bytes, global_scrub_usage
        )
        return _ProjectEventUsageRows(
            event_rows,
            failure_rows,
            retry_audit_usage,
            payload_scrub_usage,
            global_capacity,
        )

    def _project_reactivation_inventory(
        self, connection: sqlite3.Connection, project_id: str
    ) -> _ProjectReactivationInventory:
        """Collect the content-free ledger inventory bound into reactivation."""

        grant_history_count, grants_sha256 = self._digest_review_rows(
            connection,
            """SELECT grant_row.grant_id, grant_row.subject_id, grant_row.action,
                      grant_row.granted_at, revocation.revoked_at,
                      revocation.revoked_by
               FROM project_grants AS grant_row
               LEFT JOIN project_grant_revocations AS revocation
                 ON revocation.grant_id = grant_row.grant_id
               WHERE grant_row.project_id = ?
               ORDER BY grant_row.grant_id""",
            project_id,
        )
        cursor_count, cursors_sha256 = self._digest_review_rows(
            connection,
            """SELECT source_id, last_sequence, updated_at FROM event_cursors
               WHERE project_id = ? ORDER BY source_id""",
            project_id,
        )
        event_count, events_sha256 = self._digest_review_rows(
            connection,
            """SELECT event_id, event_type, payload_sha256, idempotency_sha256,
                      status, source_id, source_sequence, disposition,
                      lease_owner, lease_expires_at
               FROM event_inbox WHERE project_id = ? ORDER BY event_id""",
            project_id,
        )
        unresolved_count = int(connection.execute(
            "SELECT COUNT(*) FROM event_inbox WHERE project_id = ? "
            "AND status != 'processed'", (project_id,),
        ).fetchone()[0])
        pending_purge_count, purge_digest = self._project_reactivation_purge_inventory(
            connection, project_id
        )
        active_grant_count = int(connection.execute(
            """SELECT COUNT(*) FROM project_grants AS grant_row
               LEFT JOIN project_grant_revocations AS revocation
                 ON revocation.grant_id = grant_row.grant_id
               WHERE grant_row.project_id = ?
                 AND revocation.grant_id IS NULL""",
            (project_id,),
        ).fetchone()[0])
        return _ProjectReactivationInventory(
            grant_history_count, grants_sha256, cursor_count, cursors_sha256,
            event_count, events_sha256, unresolved_count, pending_purge_count,
            purge_digest, active_grant_count,
        )

    def transition_consumer_binding(
        self, request: ConsumerBindingTransitionRequest, actor_id: str
    ) -> ConsumerBindingTransitionResult:
        """Move active -> pending -> deregistered -> new source epoch.

        Finalization and re-enrollment are fail-closed while any source event
        lacks a processed receipt. Re-enrollment requires exact project and
        binding revisions/fingerprints and does not restore revoked grants.
        """

        self._validate_access_identity(request.project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_identity(request.transition_id, "transition_id")
        self._validate_access_rationale(request.rationale)
        action, expected_from = self._resolve_consumer_binding_transition(request)
        plan_time = utc_now()
        with self._transaction() as connection:
            replay = self._replay_consumer_binding_transition(
                connection, request, actor_id, action
            )
            if replay is not None:
                return replay
            next_epoch = self._validate_consumer_binding_transition_state(
                connection, request, action, expected_from
            )
            return self._persist_consumer_binding_transition(
                connection,
                request,
                actor_id,
                _ConsumerBindingTransitionPlan(
                    action, expected_from, next_epoch, plan_time
                ),
            )

    def project_lifecycle_status_snapshot(
        self,
        project_id: str,
        *,
        event_limit: int = 100,
        after_event_id: str | None = None,
    ) -> ProjectLifecycleStatusSnapshot:
        """Capture content-free lifecycle state from one SQLite read snapshot."""

        self._validate_access_identity(project_id, "project_id")
        if not is_exact_int(event_limit) or not 1 <= event_limit <= 100:
            raise ValueError("event_limit must be between 1 and 100")
        observed_at = utc_now()
        with self._lock:
            self._connection.execute("BEGIN")
            try:
                registration = self._connection.execute(
                    "SELECT status, revision FROM project_registry WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                binding_row = self._connection.execute(
                    "SELECT * FROM consumer_bindings WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                if registration is None or binding_row is None:
                    raise NotFoundError("project lifecycle registration not found")
                events = self._project_lifecycle_event_summary(
                    project_id, observed_at
                )
                retirement_row = self._connection.execute(
                    "SELECT * FROM project_retirement_tombstones WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
                terminal_inventory = self.terminal_event_inventory(
                    project_id, limit=event_limit, after_event_id=after_event_id
                )
                reasons = self._project_lifecycle_incomplete_reasons(
                    events.status_counts, terminal_inventory.complete
                )
                snapshot = ProjectLifecycleStatusSnapshot(
                    project_id=project_id,
                    observed_at=observed_at,
                    complete=not reasons,
                    incomplete_reasons=tuple(reasons),
                    project_status=str(registration["status"]),
                    project_revision=int(registration["revision"]),
                    consumer_binding=self._consumer_binding_from_row(binding_row),
                    retirement=(
                        self._project_retirement_from_row(retirement_row)
                        if retirement_row is not None else None
                    ),
                    event_status_counts=events.status_counts,
                    unprocessed_event_count=events.unprocessed_count,
                    unprocessed_event_sha256=events.unprocessed_sha256,
                    active_event_lease_count=events.active_lease_count,
                    terminal_event_inventory=terminal_inventory,
                )
                self._connection.commit()
                return snapshot
            except BaseException:
                self._connection.rollback()
                raise

    def project_control_plane_storage_usage(
        self, project_id: str
    ) -> ProjectControlPlaneStorageUsage:
        """Measure project-owned access-control and rate-limit rows.

        Bytes count UTF-8 text for stored fields, including decimal text for
        numeric values. SQLite indexes, pages, WAL, and shared overhead remain
        represented only by global database/WAL sizes in ProjectStorageUsage.
        """

        self._validate_access_identity(project_id, "project_id")
        queries = (
            (
                "consumer_bindings",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(status AS BLOB)) +
                     length(CAST(revision AS TEXT)) +
                     length(CAST(source_epoch AS TEXT)) +
                     length(CAST(updated_by AS BLOB)) +
                     length(CAST(updated_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM consumer_bindings WHERE project_id = ?""",
            ),
            (
                "consumer_binding_audit",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(audit_id AS BLOB)) +
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(actor_id AS BLOB)) +
                     length(CAST(action AS BLOB)) +
                     length(CAST(COALESCE(from_status, '') AS BLOB)) +
                     length(CAST(to_status AS BLOB)) +
                     length(CAST(source_epoch AS TEXT)) +
                     length(CAST(revision AS TEXT)) +
                     length(CAST(transition_id AS BLOB)) +
                     length(CAST(rationale AS BLOB)) +
                     length(CAST(created_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM consumer_binding_audit WHERE project_id = ?""",
            ),
            (
                "consumer_drain_sessions",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(transition_id AS BLOB)) +
                     length(CAST(actor_id AS BLOB)) +
                     length(CAST(caller_subject AS BLOB)) +
                     length(CAST(COALESCE(caller_profile, '') AS BLOB)) +
                     length(CAST(binding_revision AS TEXT)) +
                     length(CAST(source_epoch AS TEXT)) +
                     length(CAST(config_sha256 AS BLOB)) +
                     length(CAST(inventory_sha256 AS BLOB)) +
                     length(CAST(created_at AS BLOB)) +
                     length(CAST(expires_at AS BLOB)) +
                     length(CAST(COALESCE(revoked_at, '') AS BLOB))
                   ), 0) AS logical_bytes
                   FROM consumer_drain_sessions WHERE project_id = ?""",
            ),
            (
                "consumer_drain_events",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(transition_id AS BLOB)) +
                     length(CAST(event_id AS BLOB)) +
                     length(CAST(payload_sha256 AS BLOB)) +
                     length(CAST(COALESCE(idempotency_sha256, '') AS BLOB)) +
                     length(CAST(source_id AS BLOB)) +
                     COALESCE(length(CAST(source_sequence AS TEXT)), 0)
                   ), 0) AS logical_bytes
                   FROM consumer_drain_events WHERE project_id = ?""",
            ),
            (
                "project_retirement_tombstones",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(transition_id AS BLOB)) +
                     length(CAST(retired_by AS BLOB)) +
                     length(CAST(retired_revision AS TEXT)) +
                     length(CAST(source_epoch AS TEXT)) +
                     length(CAST(rationale AS BLOB)) +
                     length(CAST(retired_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM project_retirement_tombstones WHERE project_id = ?""",
            ),
            (
                "terminal_event_dispositions",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(event_id AS BLOB)) +
                     length(CAST(transition_id AS BLOB)) +
                     length(CAST(actor_id AS BLOB)) +
                     length(CAST(prior_status AS BLOB)) +
                     length(CAST(payload_sha256 AS BLOB)) +
                     length(CAST(rationale AS BLOB)) +
                     length(CAST(created_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM terminal_event_dispositions WHERE project_id = ?""",
            ),
            (
                "project_registry",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(repository_fingerprint AS BLOB)) +
                     length(CAST(config_sha256 AS BLOB)) +
                     length(CAST(backend_api_version AS TEXT)) +
                     length(CAST(status AS BLOB)) +
                     length(CAST(registered_by AS BLOB)) +
                     length(CAST(registered_at AS BLOB)) +
                     length(CAST(updated_by AS BLOB)) +
                     length(CAST(updated_at AS BLOB)) +
                     length(CAST(revision AS TEXT))
                   ), 0) AS logical_bytes
                   FROM project_registry WHERE project_id = ?""",
            ),
            (
                "project_registry_audit",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(audit_id AS BLOB)) +
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(actor_id AS BLOB)) +
                     length(CAST(action AS BLOB)) +
                     length(CAST(repository_fingerprint AS BLOB)) +
                     length(CAST(config_sha256 AS BLOB)) +
                     length(CAST(backend_api_version AS TEXT)) +
                     length(CAST(rationale AS BLOB)) +
                     length(CAST(created_at AS BLOB)) +
                     length(CAST(revision AS TEXT)) +
                     length(CAST(COALESCE(transition_id, '') AS BLOB))
                   ), 0) AS logical_bytes
                   FROM project_registry_audit WHERE project_id = ?""",
            ),
            (
                "project_grants",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(grant_id AS BLOB)) +
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(subject_id AS BLOB)) +
                     length(CAST(action AS BLOB)) +
                     length(CAST(granted_by AS BLOB)) +
                     length(CAST(rationale AS BLOB)) +
                     length(CAST(granted_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM project_grants WHERE project_id = ?""",
            ),
            (
                "project_grant_revocations",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(r.grant_id AS BLOB)) +
                     length(CAST(r.revoked_by AS BLOB)) +
                     length(CAST(r.rationale AS BLOB)) +
                     length(CAST(r.revoked_at AS BLOB))
                   ), 0) AS logical_bytes
                   FROM project_grant_revocations AS r
                   JOIN project_grants AS g ON g.grant_id = r.grant_id
                   WHERE g.project_id = ?""",
            ),
            (
                "request_rate_buckets",
                """SELECT COUNT(*) AS record_count, COALESCE(SUM(
                     length(CAST(subject_id AS BLOB)) +
                     length(CAST(project_id AS BLOB)) +
                     length(CAST(tokens AS TEXT)) +
                     length(CAST(updated_at AS TEXT)) +
                     length(CAST(touched_at AS TEXT))
                   ), 0) AS logical_bytes
                   FROM request_rate_buckets WHERE project_id = ?""",
            ),
        )
        with self._lock:
            classes = tuple(
                StorageClassUsage(
                    class_name=class_name,
                    record_count=int(row["record_count"]),
                    logical_bytes=int(row["logical_bytes"]),
                )
                for class_name, query in queries
                for row in (self._connection.execute(query, (project_id,)).fetchone(),)
            )
            scrub_usage = self._event_payload_scrub_usage(self._connection)
            sqlite_physical = self._sqlite_physical_storage_usage()
        global_classes = (
            StorageClassUsage(
                class_name="event_payload_scrub_queue_unassigned",
                record_count=scrub_usage.unassigned_record_count,
                logical_bytes=scrub_usage.unassigned_logical_bytes,
            ),
        )
        return ProjectControlPlaneStorageUsage(
            project_id=project_id,
            classes=classes,
            logical_record_bytes=sum(item.logical_bytes for item in classes),
            global_classes=global_classes,
            global_logical_bytes=sum(item.logical_bytes for item in global_classes),
            sqlite_physical=sqlite_physical,
        )

    def list_child_goals_compat(
        self, parent_goal_id: str, project_id: str
    ) -> tuple[GoalCard, ...]:
        """Keep the legacy full-snapshot path bounded to 100 child cards."""

        total, goals = self.list_child_goal_page(
            parent_goal_id, project_id, offset=0, limit=MAX_GOAL_LIST_PAGE
        )
        if total > MAX_GOAL_LIST_PAGE:
            raise GoalListCapacityError(
                "unpaged child-goal listing exceeds 100 records; "
                "use goal_children_page"
            )
        return goals

    def _append_fact(
        self,
        connection: sqlite3.Connection,
        fact: Fact,
        project_id: str | None = None,
    ) -> tuple[Fact, bool]:
        payload = self._fact_storage_payload(fact)
        goal_row = connection.execute(
            "SELECT project_id, status FROM goals WHERE goal_id = ?", (fact.goal_id,)
        ).fetchone()
        if goal_row is None or (
            project_id is not None and goal_row["project_id"] != project_id
        ):
            raise NotFoundError(f"goal not found: {fact.goal_id}")
        existing = connection.execute(
            "SELECT * FROM facts WHERE dedupe_key = ?", (payload.dedupe_key,)
        ).fetchone()
        if existing is not None:
            return self._fact_from_row(existing), False
        archived_duplicate = connection.execute(
            """SELECT fact_id FROM fact_archive_items WHERE dedupe_key = ?""",
            (payload.dedupe_key,),
        ).fetchone()
        if archived_duplicate is not None:
            return self.get_fact(archived_duplicate["fact_id"]), False
        stored_status = GoalStatus(goal_row["status"])
        if stored_status in {
            GoalStatus.COMPLETE,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        } and not (
            stored_status is GoalStatus.COMPLETE and fact.kind is FactKind.REOPENED
        ):
            raise ConflictError("terminal goals cannot accept new facts")
        if stored_status is GoalStatus.PLANNED and fact.kind in {
            FactKind.CHANGE,
            FactKind.VERIFICATION,
            FactKind.COMPLETION_CLAIM,
            FactKind.OUTCOME,
        }:
            raise ConflictError(
                "planned goals must be activated before implementation or verification facts"
            )
        reused_id = connection.execute(
            "SELECT dedupe_key FROM facts WHERE fact_id = ?", (fact.fact_id,)
        ).fetchone()
        archived_id = connection.execute(
            "SELECT dedupe_key FROM fact_archive_items WHERE fact_id = ?",
            (fact.fact_id,),
        ).fetchone()
        if reused_id is not None or archived_id is not None:
            raise ConflictError("fact ID was already used for different content")

        usage = connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(f.fact_id AS BLOB)) +
                 length(CAST(f.kind AS BLOB)) +
                 length(CAST(f.bullet AS BLOB)) +
                 COALESCE(length(CAST(f.criterion_id AS BLOB)), 0) +
                 length(CAST(f.evidence_json AS BLOB)) +
                 length(CAST(f.verification_attestations_json AS BLOB)) +
                 COALESCE(length(CAST(f.source_event_id AS BLOB)), 0) +
                 length(CAST(f.dedupe_key AS BLOB)) +
                 length(CAST(f.created_at AS BLOB))
               ), 0) AS bytes FROM facts AS f
               JOIN goals AS g ON g.goal_id = f.goal_id
               WHERE g.project_id = ?""",
            (goal_row["project_id"],),
        ).fetchone()
        goal_usage = connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(fact_id AS BLOB)) + length(CAST(kind AS BLOB)) +
                 length(CAST(bullet AS BLOB)) +
                 COALESCE(length(CAST(criterion_id AS BLOB)), 0) +
                 length(CAST(evidence_json AS BLOB)) +
                 length(CAST(verification_attestations_json AS BLOB)) +
                 COALESCE(length(CAST(source_event_id AS BLOB)), 0) +
                 length(CAST(dedupe_key AS BLOB)) +
                 length(CAST(created_at AS BLOB))
               ), 0) AS bytes FROM facts WHERE goal_id = ?""",
            (fact.goal_id,),
        ).fetchone()
        added_bytes = self._fact_record_bytes(
            fact,
            payload.evidence_json,
            payload.attestations_json,
            payload.dedupe_key,
        )
        if (
            goal_usage["count"] + 1 > MAX_FACTS_PER_GOAL
            or goal_usage["bytes"] + added_bytes > MAX_FACT_BYTES_PER_GOAL
            or usage["count"] + 1 > MAX_FACTS_PER_PROJECT
            or usage["bytes"] + added_bytes > MAX_FACT_BYTES_PER_PROJECT
        ):
            raise FactCapacityError(
                "fact history capacity reached; preserve existing facts and "
                "review an approved compaction/retention action before resuming"
            )

        connection.execute(
            """INSERT INTO facts
               (fact_id, goal_id, kind, bullet, criterion_id, evidence_json,
                verification_attestations_json, source_event_id, dedupe_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.fact_id,
                fact.goal_id,
                fact.kind.value,
                fact.bullet.strip(),
                fact.criterion_id,
                payload.evidence_json,
                payload.attestations_json,
                fact.source_event_id,
                payload.dedupe_key,
                fact.created_at,
            )
        )
        row = connection.execute(
            "SELECT * FROM facts WHERE dedupe_key = ?", (payload.dedupe_key,)
        ).fetchone()
        if row is None:
            raise RuntimeError("inserted fact row could not be read back")
        return self._fact_from_row(row), True

    def approve_fact_compaction(
        self, approval: FactCompactionApprovalRequest
    ) -> FactArchiveReceipt:
        """Atomically archive exact eligible facts and remove only their live rows."""

        self._validate_fact_compaction_approval(approval)
        with self._transaction() as connection:
            existing = self._read_existing_compaction_receipt(connection, approval)
            if existing is not None:
                return existing
            prepared = self._prepare_fact_archive(connection, approval)
            self._ensure_fact_archive_capacity(connection, approval, prepared)
            return self._persist_fact_archive(connection, approval, prepared)

    def list_sde_candidates(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[SDECandidate, ...]:
        """List a goal's candidates in creation order within the optional project."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT candidate_id FROM sde_candidates WHERE goal_id = ? "
                    "ORDER BY created_at, candidate_id",
                    (goal_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT s.candidate_id FROM sde_candidates AS s
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.goal_id = ? AND g.project_id = ?
                       ORDER BY s.created_at, s.candidate_id""",
                    (goal_id, project_id),
                ).fetchall()
        return tuple(
            self.get_sde_candidate(row["candidate_id"], project_id) for row in rows
        )
