"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ConflictError,
    ConsumerBindingAuditRecord,
    ConsumerBindingRecord,
    ConsumerBindingTransitionRequest,
    ConsumerBindingTransitionResult,
    EVENT_RETRY_BASE_SECONDS,
    EVENT_RETRY_MAX_SECONDS,
    EventClaimError,
    Generator,
    NoReturn,
    NotFoundError,
    ProjectDrainEffectContext,
    ProjectRegistrationRecord,
    ProjectRegistrationRequest,
    ProjectRegistrationTransitionResult,
    ProjectRegistryAuditRecord,
    ProjectRetirementRecord,
    _ConsumerBindingTransitionPlan,
    _ProjectAuxiliaryUsageRows,
    _project_registration_is_unchanged,
    _project_registration_update_retry_matches,
    contextmanager,
    datetime,
    hashlib,
    is_exact_int,
    new_id,
    sqlite3,
    timedelta,
    utc_now,
)
from .store_operations_03 import StoreOperations1Part0

class StoreOperations1Part1(StoreOperations1Part0):
    """Continuation of StoreOperations1 operations."""


    def _project_auxiliary_usage_rows(
        self, project_id: str
    ) -> _ProjectAuxiliaryUsageRows:
        """Query project cursor, staging-age, and maintenance receipt usage."""

        event_cursor_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(source_id AS BLOB)) +
                 length(CAST(last_sequence AS TEXT)) +
                 length(CAST(updated_at AS BLOB))
               ), 0) AS bytes
               FROM event_cursors WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        staging_time_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(path AS BLOB)) +
                 length(CAST(sha256 AS BLOB)) +
                 length(CAST(staged_at AS BLOB)) +
                 COALESCE(length(CAST(device_id AS TEXT)), 0) +
                 COALESCE(length(CAST(inode_id AS TEXT)), 0) +
                 COALESCE(length(CAST(occurrence_id AS BLOB)), 0)
               ), 0) AS bytes
               FROM staging_artifact_times WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        staging_occurrence_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(path AS BLOB)) +
                 length(CAST(sha256 AS BLOB)) +
                 length(CAST(device_id AS TEXT)) +
                 length(CAST(inode_id AS TEXT)) +
                 length(CAST(occurrence_id AS BLOB)) +
                 length(CAST(observed_at AS BLOB))
               ), 0) AS bytes
               FROM staging_artifact_occurrences WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        expiry_receipt_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(receipt_id AS BLOB)) +
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(reviewer_id AS BLOB)) +
                 length(CAST(manifest_sha256 AS BLOB)) +
                 length(CAST(status AS BLOB)) +
                 length(CAST(created_at AS BLOB)) +
                 length(CAST(updated_at AS BLOB))
               ), 0) AS bytes
               FROM expiry_purge_receipts WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        expiry_target_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(t.receipt_id AS BLOB)) +
                 length(CAST(t.path AS BLOB)) +
                 length(CAST(t.sha256 AS BLOB)) +
                 length(CAST(t.status AS BLOB)) +
                 length(CAST(t.attempts AS TEXT)) +
                 COALESCE(length(CAST(t.error AS BLOB)), 0) +
                 length(CAST(t.created_at AS BLOB)) +
                 COALESCE(length(CAST(t.last_attempt_at AS BLOB)), 0) +
                 COALESCE(length(CAST(t.next_attempt_at AS BLOB)), 0) +
                 COALESCE(length(CAST(t.device_id AS TEXT)), 0) +
                 COALESCE(length(CAST(t.inode_id AS TEXT)), 0) +
                 COALESCE(length(CAST(t.occurrence_id AS BLOB)), 0) +
                 length(CAST(t.approval_stale AS TEXT))
               ), 0) AS bytes
               FROM expiry_purge_targets AS t
               JOIN expiry_purge_receipts AS r ON r.receipt_id = t.receipt_id
               WHERE r.project_id = ?""",
            (project_id,),
        ).fetchone()
        cleanup_authorization_usage = self._connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                 length(CAST(receipt_id AS BLOB)) +
                 length(CAST(project_id AS BLOB)) +
                 length(CAST(reviewer_id AS BLOB)) +
                 length(CAST(manifest_sha256 AS BLOB)) +
                 length(CAST(approved_at AS BLOB)) +
                 length(CAST(canonical_persisted AS TEXT)) +
                 COALESCE(length(CAST(canonical_target AS BLOB)), 0) +
                 COALESCE(length(CAST(canonical_sha256 AS BLOB)), 0) +
                 COALESCE(length(CAST(canonical_persisted_at AS BLOB)), 0) +
                 length(CAST(dependency_map_sha256 AS BLOB))
               ), 0) AS bytes
               FROM cleanup_authorizations WHERE project_id = ?""",
            (project_id,),
        ).fetchone()
        return _ProjectAuxiliaryUsageRows(
            event_cursors=event_cursor_usage,
            staging_artifact_times=staging_time_usage,
            staging_artifact_occurrences=staging_occurrence_usage,
            expiry_purge_receipts=expiry_receipt_usage,
            expiry_purge_targets=expiry_target_usage,
            cleanup_authorizations=cleanup_authorization_usage,
        )

    def _queue_event_payload_scrub(
        self, connection: sqlite3.Connection, project_id: str, event_id: str
    ) -> None:
        """Persist only a locator for a payload whose WAL remnants need scrubbing."""

        if self.database == ":memory:":
            return
        connection.execute(
            """INSERT INTO event_payload_scrub_queue
               (project_id, event_id, queued_at)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id, event_id) DO NOTHING""",
            (project_id, event_id, utc_now()),
        )

    @staticmethod
    def _event_failure_next_attempt_at(
        attempts: int, failed_at: datetime
    ) -> str | None:
        """Calculate the durable exponential retry time for a retained payload."""

        attempt_number = attempts + 1
        delay_seconds = min(
            EVENT_RETRY_BASE_SECONDS * (2 ** min(attempt_number - 1, 16)),
            EVENT_RETRY_MAX_SECONDS,
        )
        return (failed_at + timedelta(seconds=delay_seconds)).isoformat(
            timespec="microseconds"
        )

    def _raise_event_failure_transition_error(
        self, project_id: str, event_id: str, lease_owner: str | None
    ) -> NoReturn:
        """Classify a failed event update as lost lease or invalid transition."""

        current = self._connection.execute(
            "SELECT status, lease_owner, lease_expires_at FROM event_inbox "
            "WHERE project_id = ? AND event_id = ?",
            (project_id, event_id),
        ).fetchone()
        if current is None:
            raise NotFoundError(f"event not found: {project_id}/{event_id}")
        expires_at = current["lease_expires_at"]
        has_live_claim = (
            current["lease_owner"] is not None
            and expires_at is not None
            and expires_at > utc_now()
        )
        claim_lost = (lease_owner is None and has_live_claim) or (
            lease_owner is not None
            and (current["lease_owner"] != lease_owner or not has_live_claim)
        )
        if claim_lost:
            raise EventClaimError("event claim is missing, expired, or owned elsewhere")
        raise ConflictError("event is missing or already processed")

    @contextmanager
    def project_revision_fence(
        self, project_id: str, expected_revision: int,
        *, drain: ProjectDrainEffectContext | None = None,
        expected_binding_revision: int | None = None,
    ) -> Generator[sqlite3.Connection, None, None]:
        """Serialize one project effect against its reviewed lifecycle revision.

        The write transaction remains open through the caller's effect. A
        lifecycle transition on another connection either commits first and
        makes this fence stale, or waits until the admitted effect completes.
        """

        self._validate_access_identity(project_id, "project_id")
        if not is_exact_int(expected_revision) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        # Keep this transaction open across yield; contextlib exits it when
        # the caller leaves the fence context.
        with self._transaction() as connection:  # pylint: disable=contextmanager-generator-missing-cleanup
            registration = connection.execute(
                "SELECT status, revision, config_sha256 FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            binding = connection.execute(
                "SELECT status, revision, source_epoch FROM consumer_bindings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            drain_allowed = False
            if (
                binding is not None
                and binding["status"] == "deregistration_pending"
                and drain is not None
            ):
                drain_allowed = self._consumer_drain_allows_in_connection(
                    connection, drain,
                    binding["revision"], binding["source_epoch"],
                    registration["config_sha256"] if registration is not None else "",
                )
            if registration is None:
                raise NotFoundError("project registration not found")
            if (
                registration["status"] != "active"
                or registration["revision"] != expected_revision
                or not self._effect_binding_matches_revision(
                    binding, expected_binding_revision, drain_allowed
                )
            ):
                raise ConflictError("project or consumer lifecycle changed before the effect")
            yield connection

    def register_project(
        self, request: ProjectRegistrationRequest, actor_id: str
    ) -> ProjectRegistrationRecord:
        """Register a host-verified project binding exactly once.

        The two SHA-256 values are supplied by the trusted host adapter. This
        store validates their shape but cannot authenticate or derive them.
        """

        project_id = request.project_id
        repository_fingerprint = request.repository_fingerprint
        config_sha256 = request.config_sha256
        backend_api_version = request.backend_api_version
        rationale = request.rationale
        self._validate_access_identity(project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_digest(repository_fingerprint, "repository_fingerprint")
        self._validate_access_digest(config_sha256, "config_sha256")
        self._validate_backend_api_version(backend_api_version)
        self._validate_access_rationale(rationale)
        now = utc_now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT project_id FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if existing is not None:
                raise ConflictError("project is already registered")
            same_repository = connection.execute(
                "SELECT project_id FROM project_registry "
                "WHERE repository_fingerprint = ?",
                (repository_fingerprint,),
            ).fetchone()
            if same_repository is not None:
                raise ConflictError("repository fingerprint is already registered")
            connection.execute(
                """INSERT INTO project_registry
                   (project_id, repository_fingerprint, config_sha256,
                    backend_api_version, status, registered_by, registered_at,
                    updated_by, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                (
                    project_id,
                    repository_fingerprint,
                    config_sha256,
                    backend_api_version,
                    actor_id,
                    now,
                    actor_id,
                    now,
                ),
            )
            self._append_project_registry_audit(
                connection,
                ProjectRegistryAuditRecord(
                    audit_id=new_id(),
                    project_id=project_id,
                    actor_id=actor_id,
                    action="registered",
                    repository_fingerprint=repository_fingerprint,
                    config_sha256=config_sha256,
                    backend_api_version=backend_api_version,
                    rationale=rationale,
                    created_at=now,
                    revision=1,
                    transition_id=None,
                ),
            )
            connection.execute(
                """INSERT INTO consumer_bindings
                   (project_id, status, revision, source_epoch, updated_by, updated_at)
                   VALUES (?, 'active', 1, 1, ?, ?)""",
                (project_id, actor_id, now),
            )
            enrollment = ConsumerBindingAuditRecord(
                audit_id=new_id(),
                project_id=project_id,
                actor_id=actor_id,
                action="enrolled",
                from_status=None,
                to_status="active",
                source_epoch=1,
                revision=1,
                transition_id=new_id(),
                rationale=rationale,
                created_at=now,
            )
            self._append_consumer_binding_audit(connection, enrollment)
            row = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("project registration insert returned no row")
        return self._project_registration_from_row(row)

    def update_project_registration(
        self,
        request: ProjectRegistrationRequest,
        actor_id: str,
        transition_id: str,
    ) -> ProjectRegistrationTransitionResult:
        """Update fingerprints once; exact retries recover the original receipt."""

        self._validate_access_identity(request.project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_identity(transition_id, "transition_id")
        self._validate_access_digest(
            request.repository_fingerprint, "repository_fingerprint"
        )
        self._validate_access_digest(request.config_sha256, "config_sha256")
        self._validate_backend_api_version(request.backend_api_version)
        self._validate_access_rationale(request.rationale)
        expected_revision = request.expected_revision
        if not is_exact_int(expected_revision) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        now = utc_now()
        with self._transaction() as connection:
            previous_transition = connection.execute(
                """SELECT * FROM project_registry_audit
                   WHERE project_id = ? AND transition_id = ?""",
                (request.project_id, transition_id),
            ).fetchone()
            if previous_transition is not None:
                if not _project_registration_update_retry_matches(
                    previous_transition,
                    request,
                    actor_id,
                    expected_revision,
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
                raise ConflictError("retired project registrations cannot be changed")
            if current["revision"] != expected_revision:
                raise ConflictError("project registration revision is stale")
            binding = connection.execute(
                "SELECT status FROM consumer_bindings WHERE project_id = ?",
                (request.project_id,),
            ).fetchone()
            if binding is None or binding["status"] not in {"active", "deregistered"}:
                raise ConflictError("consumer binding is not active")
            if (
                current["repository_fingerprint"] != request.repository_fingerprint
                and binding["status"] == "active"
            ):
                raise ConflictError(
                    "repository fingerprint changes require deregistration "
                    "and fresh enrollment"
                )
            if _project_registration_is_unchanged(current, request):
                raise ConflictError("project registration is unchanged")
            collision = connection.execute(
                "SELECT project_id FROM project_registry "
                "WHERE repository_fingerprint = ? AND project_id <> ?",
                (request.repository_fingerprint, request.project_id),
            ).fetchone()
            if collision is not None:
                raise ConflictError("repository fingerprint is already registered")
            cursor = connection.execute(
                """UPDATE project_registry SET repository_fingerprint = ?,
                   config_sha256 = ?, backend_api_version = ?, updated_by = ?,
                   updated_at = ?, revision = revision + 1
                   WHERE project_id = ? AND revision = ?""",
                (
                    request.repository_fingerprint,
                    request.config_sha256,
                    request.backend_api_version,
                    actor_id,
                    now,
                    request.project_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise ConflictError("project registration revision is stale")
            transition_receipt = ProjectRegistryAuditRecord(
                audit_id=new_id(),
                project_id=request.project_id,
                actor_id=actor_id,
                action="updated",
                repository_fingerprint=request.repository_fingerprint,
                config_sha256=request.config_sha256,
                backend_api_version=request.backend_api_version,
                rationale=request.rationale,
                created_at=now,
                revision=expected_revision + 1,
                transition_id=transition_id,
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

    def _project_reactivation_purge_inventory(
        self, connection: sqlite3.Connection, project_id: str
    ) -> tuple[int, str]:
        """Count pending cleanup and hash the exact SDE and expiry inventories."""

        receipt_count, receipt_sha256 = self._digest_review_rows(
            connection,
            """SELECT receipt.receipt_id, receipt.decision, receipt.facts_sha256,
                      receipt.artifact_inventory_complete, receipt.canonical_persisted,
                      receipt.canonical_sha256, receipt.purge_status,
                      target.path, target.sha256, target.status, target.attempts,
                      target.retention_hold, target.approval_stale
               FROM audit_receipts AS receipt
               JOIN sde_candidates AS candidate
                 ON candidate.candidate_id = receipt.candidate_id
               JOIN goals AS goal ON goal.goal_id = candidate.goal_id
               LEFT JOIN purge_targets AS target
                 ON target.receipt_id = receipt.receipt_id
               WHERE goal.project_id = ?
               ORDER BY receipt.receipt_id, target.path""",
            project_id,
        )
        expiry_count, expiry_sha256 = self._digest_review_rows(
            connection,
            """SELECT receipt.receipt_id, receipt.manifest_sha256, receipt.status,
                      target.path, target.sha256, target.status, target.attempts,
                      target.approval_stale
               FROM expiry_purge_receipts AS receipt
               LEFT JOIN expiry_purge_targets AS target
                 ON target.receipt_id = receipt.receipt_id
               WHERE receipt.project_id = ?
               ORDER BY receipt.receipt_id, target.path""",
            project_id,
        )
        pending_purge_count = int(connection.execute(
            """SELECT
                 (SELECT COUNT(*) FROM purge_targets AS target
                   JOIN audit_receipts AS receipt
                     ON receipt.receipt_id = target.receipt_id
                   JOIN sde_candidates AS candidate
                     ON candidate.candidate_id = receipt.candidate_id
                   JOIN goals AS goal ON goal.goal_id = candidate.goal_id
                   WHERE goal.project_id = ? AND target.status != 'purged')
               + (SELECT COUNT(*) FROM expiry_purge_targets AS target
                   JOIN expiry_purge_receipts AS receipt
                     ON receipt.receipt_id = target.receipt_id
                   WHERE receipt.project_id = ? AND target.status != 'purged')""",
            (project_id, project_id),
        ).fetchone()[0])
        purge_digest = hashlib.sha256(
            (
                f"sde:{receipt_count}:{receipt_sha256}\n"
                f"expiry:{expiry_count}:{expiry_sha256}"
            ).encode("utf-8")
        ).hexdigest()
        return pending_purge_count, purge_digest

    def get_project_registration(
        self, project_id: str
    ) -> ProjectRegistrationRecord:
        """Return one registered project or fail without disclosing contents."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("project registration not found")
        return self._project_registration_from_row(row)

    def retire_project(
        self,
        project_id: str,
        actor_id: str,
        rationale: str,
        expected_revision: int,
        transition_id: str,
    ) -> ProjectRetirementRecord:
        """Permanently fence a project after its consumer binding is closed."""

        self._validate_access_identity(project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_identity(transition_id, "transition_id")
        self._validate_access_rationale(rationale)
        if not is_exact_int(expected_revision) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        now = utc_now()
        with self._transaction() as connection:
            prior = connection.execute(
                "SELECT * FROM project_retirement_tombstones WHERE transition_id = ?",
                (transition_id,),
            ).fetchone()
            if prior is not None:
                if (
                    prior["project_id"] != project_id
                    or prior["retired_by"] != actor_id
                    or prior["retired_revision"] != expected_revision + 1
                    or prior["rationale"] != rationale
                ):
                    raise ConflictError("retirement transition ID was reused")
                return self._project_retirement_from_row(prior)
            current = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            binding = connection.execute(
                "SELECT * FROM consumer_bindings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if current is None or binding is None:
                raise NotFoundError("project registration not found")
            if current["revision"] != expected_revision:
                raise ConflictError("project registration revision is stale")
            if binding["status"] not in {"deregistration_pending", "deregistered"}:
                raise ConflictError("consumer binding must be fenced before retirement")
            cursor = connection.execute(
                """UPDATE project_registry SET status = 'suspended',
                   updated_by = ?, updated_at = ?, revision = revision + 1
                   WHERE project_id = ? AND revision = ?""",
                (actor_id, now, project_id, expected_revision),
            )
            if cursor.rowcount != 1:
                raise ConflictError("project registration revision is stale")
            connection.execute(
                """INSERT INTO project_retirement_tombstones
                   (project_id, transition_id, retired_by, retired_revision,
                    source_epoch, rationale, retired_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, transition_id, actor_id, expected_revision + 1,
                 binding["source_epoch"], rationale, now),
            )
            row = connection.execute(
                "SELECT * FROM project_retirement_tombstones WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("retirement tombstone insert returned no row")
            return self._project_retirement_from_row(row)

    def get_project_retirement(
        self, project_id: str
    ) -> ProjectRetirementRecord | None:
        """Read a project's immutable retirement tombstone, if present."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM project_retirement_tombstones WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return self._project_retirement_from_row(row) if row is not None else None

    def get_consumer_binding(self, project_id: str) -> ConsumerBindingRecord:
        """Return the consumer's independent lifecycle state and source epoch."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM consumer_bindings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("consumer binding not found")
        return self._consumer_binding_from_row(row)

    def consumer_binding_audit(
        self, project_id: str
    ) -> tuple[ConsumerBindingAuditRecord, ...]:
        """Return immutable lifecycle receipts in revision order."""

        self._validate_access_identity(project_id, "project_id")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM consumer_binding_audit WHERE project_id = ?
                   ORDER BY revision, audit_id""",
                (project_id,),
            ).fetchall()
        return tuple(self._consumer_binding_audit_from_row(row) for row in rows)

    def _replay_consumer_binding_transition(
        self,
        connection: sqlite3.Connection,
        request: ConsumerBindingTransitionRequest,
        actor_id: str,
        action: str,
    ) -> ConsumerBindingTransitionResult | None:
        """Return the prior result for an exact idempotent transition replay."""

        prior = connection.execute(
            """SELECT * FROM consumer_binding_audit
               WHERE project_id = ? AND transition_id = ?""",
            (request.project_id, request.transition_id),
        ).fetchone()
        if prior is None:
            return None
        if (
            prior["actor_id"] != actor_id
            or prior["action"] != action
            or prior["revision"] != request.expected_revision + 1
            or prior["rationale"] != request.rationale
        ):
            raise ConflictError(
                "consumer transition ID was already used with different input"
            )
        current = connection.execute(
            "SELECT * FROM consumer_bindings WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        if current is None:
            raise NotFoundError("consumer binding not found")
        return ConsumerBindingTransitionResult(
            self._consumer_binding_from_row(current),
            self._consumer_binding_audit_from_row(prior),
            True,
        )

    def _validate_consumer_binding_transition_state(
        self,
        connection: sqlite3.Connection,
        request: ConsumerBindingTransitionRequest,
        action: str,
        expected_from: str,
    ) -> int:
        """Check the live binding, pending work, and re-enrollment proof."""

        current = connection.execute(
            "SELECT * FROM consumer_bindings WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        if current is None:
            raise NotFoundError("consumer binding not found")
        retired = connection.execute(
            "SELECT 1 FROM project_retirement_tombstones WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        if retired is not None:
            raise ConflictError("retired projects cannot change consumer bindings")
        if current["revision"] != request.expected_revision:
            raise ConflictError("consumer binding revision is stale")
        if current["status"] != expected_from:
            raise ConflictError("consumer binding is not in the required lifecycle state")
        if action in {"deregistered", "reenrolled"}:
            unresolved = connection.execute(
                """SELECT COUNT(*) FROM event_inbox
                   WHERE project_id = ? AND status <> 'processed'""",
                (request.project_id,),
            ).fetchone()[0]
            if unresolved:
                raise ConflictError("consumer binding has unresolved source events")
        next_epoch = int(current["source_epoch"])
        if action == "reenrolled":
            next_epoch = self._validate_consumer_reenrollment(
                connection, request, next_epoch
            )
        return next_epoch

    def _persist_consumer_binding_transition(
        self,
        connection: sqlite3.Connection,
        request: ConsumerBindingTransitionRequest,
        actor_id: str,
        plan: _ConsumerBindingTransitionPlan,
    ) -> ConsumerBindingTransitionResult:
        """Commit the state revision, revoked grants, and immutable audit row."""

        next_revision = request.expected_revision + 1
        cursor = connection.execute(
            """UPDATE consumer_bindings SET status = ?, revision = ?,
               source_epoch = ?, updated_by = ?, updated_at = ?
               WHERE project_id = ? AND revision = ? AND status = ?""",
            (
                request.status,
                next_revision,
                plan.next_source_epoch,
                actor_id,
                plan.now,
                request.project_id,
                request.expected_revision,
                plan.expected_from,
            ),
        )
        if cursor.rowcount != 1:
            raise ConflictError("consumer binding revision is stale")
        if plan.action == "deregistration_pending":
            connection.execute(
                """INSERT INTO project_grant_revocations
                       (grant_id, revoked_by, rationale, revoked_at)
                   SELECT grants.grant_id, ?, ?, ?
                   FROM project_grants AS grants
                   LEFT JOIN project_grant_revocations AS revocations
                     ON revocations.grant_id = grants.grant_id
                   WHERE grants.project_id = ? AND revocations.grant_id IS NULL""",
                (actor_id, request.rationale, plan.now, request.project_id),
            )
        receipt = ConsumerBindingAuditRecord(
            audit_id=new_id(),
            project_id=request.project_id,
            actor_id=actor_id,
            action=plan.action,
            from_status=plan.expected_from,
            to_status=request.status,
            source_epoch=plan.next_source_epoch,
            revision=next_revision,
            transition_id=request.transition_id,
            rationale=request.rationale,
            created_at=plan.now,
        )
        self._append_consumer_binding_audit(connection, receipt)
        updated = connection.execute(
            "SELECT * FROM consumer_bindings WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        if updated is None:
            raise RuntimeError("consumer binding transition returned no state")
        return ConsumerBindingTransitionResult(
            self._consumer_binding_from_row(updated), receipt, False
        )

    def consumer_drain_inventory(self, project_id: str) -> tuple[int, str]:
        """Return count and digest of the exact unprocessed event inventory."""

        digest = hashlib.sha256()
        count = 0
        with self._lock:
            rows = self._connection.execute(
                """SELECT event_id, payload_sha256, idempotency_sha256,
                          source_id, source_sequence, status
                   FROM event_inbox WHERE project_id = ? AND status <> 'processed'
                   ORDER BY event_id""",
                (project_id,),
            )
            for row in rows:
                encoded = self._consumer_drain_inventory_row_bytes(row)
                digest.update(len(encoded).to_bytes(4, "big"))
                digest.update(encoded)
                count += 1
        return count, digest.hexdigest()
