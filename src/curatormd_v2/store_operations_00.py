"""Ordered SQLite operation segment extracted from store.py."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

# Continuation bases preserve the original method override order.
# The old single module hid cross-version duplicate-code diagnostics.
# pylint: disable=too-many-ancestors,duplicate-code
from .store_support_01 import (
    ArtifactRef,
    ConflictError,
    ConsumerBindingAuditRecord,
    ConsumerBindingRecord,
    ConsumerBindingTransitionRequest,
    ConsumerDrainStoreRequest,
    EventEnvelope,
    EventInboxStatus,
    Generator,
    NotFoundError,
    ProjectDrainEffectContext,
    ProjectGrantRecord,
    ProjectRegistrationRecord,
    ProjectRegistrationTransitionResult,
    ProjectRegistryAuditRecord,
    ProjectRetirementRecord,
    ProjectStatusChangeRequest,
    RLockType,
    ReacquisitionAction,
    RetentionHoldKind,
    UTC,
    _ACCESS_ID_RE,
    _ACCESS_RATIONALE_LIMIT,
    _ProjectLifecycleEventSummary,
    _SHA256_RE,
    contextmanager,
    datetime,
    hashlib,
    is_exact_int,
    json,
    parse_optional_aware_timestamp,
    re,
    sqlite3,
    utc_now,
    validate_safe_text,
)

class StoreOperations0Part0:
    """Internal SQLite operation group ordered by method dependency."""

    database: str
    _lock: RLockType
    _transaction_depth: int = 0
    _connection: sqlite3.Connection


    @contextmanager
    def _transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            outermost = not self._connection.in_transaction
            savepoint = f"curatormd_nested_{self._transaction_depth}"
            if outermost:
                self._connection.execute("BEGIN IMMEDIATE")
            else:
                self._connection.execute(f"SAVEPOINT {savepoint}")
            self._transaction_depth += 1
            try:
                yield self._connection
            except BaseException:
                self._transaction_depth -= 1
                if outermost:
                    self._connection.rollback()
                elif self._connection.in_transaction:
                    self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            self._transaction_depth -= 1
            if outermost:
                try:
                    self._connection.commit()
                except BaseException as commit_error:
                    try:
                        self._connection.rollback()
                    except sqlite3.Error as rollback_error:
                        try:
                            self._connection.close()
                        except sqlite3.Error as close_error:
                            commit_error.add_note(
                                "transaction rollback and connection close failed "
                                f"({type(rollback_error).__name__}, "
                                f"{type(close_error).__name__})"
                            )
                        else:
                            commit_error.add_note(
                                "transaction rollback failed; connection closed "
                                f"({type(rollback_error).__name__})"
                            )
                    raise
            else:
                self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")

    @contextmanager
    def read_snapshot(self) -> Generator[sqlite3.Connection, None, None]:
        """Run a group of reads against one SQLite snapshot without write access."""

        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("read snapshot cannot nest a transaction")
            self._connection.execute("PRAGMA query_only = ON")
            try:
                self._connection.execute("BEGIN")
                yield self._connection
                self._connection.commit()
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.rollback()
                raise
            finally:
                if self._connection.in_transaction:
                    self._connection.rollback()
                self._connection.execute("PRAGMA query_only = OFF")

    @staticmethod
    def _effect_binding_matches_revision(
        binding: sqlite3.Row | None,
        expected_binding_revision: int | None,
        drain_allowed: bool,
    ) -> bool:
        """Require the active binding revision unless this exact event is draining."""

        if binding is None:
            return False
        if binding["status"] != "active" and not drain_allowed:
            return False
        return (
            expected_binding_revision is None
            or binding["revision"] == expected_binding_revision
            or drain_allowed
        )

    @staticmethod
    def _consumer_drain_allows_in_connection(
        connection: sqlite3.Connection,
        drain: ProjectDrainEffectContext,
        binding_revision: int,
        source_epoch: int,
        config_sha256: str,
    ) -> bool:
        """Recheck the exact live drain token inside the effect transaction."""

        now = datetime.now(UTC).isoformat()
        row = connection.execute(
            """SELECT item.payload_sha256, item.idempotency_sha256,
                      item.source_id, item.source_sequence
               FROM consumer_drain_sessions AS session
               JOIN consumer_drain_events AS item
                 ON item.project_id = session.project_id
                AND item.transition_id = session.transition_id
               WHERE session.project_id = ? AND item.event_id = ?
                 AND session.caller_subject = ? AND session.caller_profile IS ?
                 AND session.expires_at > ? AND session.revoked_at IS NULL
                 AND session.binding_revision = ? AND session.source_epoch = ?
                 AND session.config_sha256 = ?
               ORDER BY session.created_at DESC LIMIT 1""",
            (
             drain.event.project_id, drain.event.event_id,
             drain.caller_subject, drain.caller_profile,
             now, binding_revision, source_epoch, config_sha256),
        ).fetchone()
        if row is None:
            return False
        serialized = drain.event.to_json()
        identity_matches = (
            row["idempotency_sha256"] == drain.event.idempotency_sha256
            if row["idempotency_sha256"] is not None
            else row["payload_sha256"]
            == hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        )
        result = (
            identity_matches
            and row["source_id"] == drain.event.source_id
            and row["source_sequence"] == drain.event.source_sequence
        )
        return result

    @property
    def transaction_active(self) -> bool:
        """Report whether this connection currently holds a transaction."""

        return self._connection.in_transaction

    @staticmethod
    def _validate_access_identity(value: object, field_name: str) -> None:
        if not isinstance(value, str) or not _ACCESS_ID_RE.fullmatch(value):
            raise ValueError(f"{field_name} must be a bounded opaque identifier")

    @staticmethod
    def _validate_access_rationale(value: object) -> None:
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > _ACCESS_RATIONALE_LIMIT
            or "\n" in value
            or "\r" in value
        ):
            raise ValueError(
                "access rationale must be a non-empty, bounded single line"
            )
        validate_safe_text(value, "access rationale")

    @staticmethod
    def _validate_access_digest(value: object, field_name: str) -> None:
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise ValueError(f"{field_name} must be a lowercase SHA-256")

    @staticmethod
    def _validate_backend_api_version(value: object) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError("backend_api_version must be a positive integer")

    @staticmethod
    def _validate_project_status(value: object) -> str:
        if not isinstance(value, str) or value not in {"active", "suspended"}:
            raise ValueError("project status must be active or suspended")
        return value

    @staticmethod
    def _project_registration_from_row(
        row: sqlite3.Row,
    ) -> ProjectRegistrationRecord:
        return ProjectRegistrationRecord(
            project_id=row["project_id"],
            repository_fingerprint=row["repository_fingerprint"],
            config_sha256=row["config_sha256"],
            backend_api_version=row["backend_api_version"],
            status=row["status"],
            registered_by=row["registered_by"],
            registered_at=row["registered_at"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
            revision=row["revision"],
        )

    @staticmethod
    def _project_registry_audit_from_row(
        row: sqlite3.Row,
    ) -> ProjectRegistryAuditRecord:
        """Hydrate one append-only registry transition receipt."""

        return ProjectRegistryAuditRecord(
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

    @classmethod
    def _project_registration_transition_result(
        cls, connection: sqlite3.Connection, receipt_row: sqlite3.Row, *, replayed: bool
    ) -> ProjectRegistrationTransitionResult:
        """Return current state with the same durable receipt on exact retries."""

        current = connection.execute(
            "SELECT * FROM project_registry WHERE project_id = ?",
            (receipt_row["project_id"],),
        ).fetchone()
        if current is None:
            raise NotFoundError("project registration not found")
        return ProjectRegistrationTransitionResult(
            registration=cls._project_registration_from_row(current),
            receipt=cls._project_registry_audit_from_row(receipt_row),
            replayed=replayed,
        )

    @staticmethod
    def _project_grant_from_row(row: sqlite3.Row) -> ProjectGrantRecord:
        return ProjectGrantRecord(
            grant_id=row["grant_id"],
            project_id=row["project_id"],
            subject_id=row["subject_id"],
            action=row["action"],
            granted_by=row["granted_by"],
            rationale=row["rationale"],
            granted_at=row["granted_at"],
            revoked_by=row["revoked_by"],
            revoke_rationale=row["revoke_rationale"],
            revoked_at=row["revoked_at"],
        )

    @staticmethod
    def _append_project_registry_audit(
        connection: sqlite3.Connection,
        record: ProjectRegistryAuditRecord,
    ) -> None:
        connection.execute(
            """INSERT INTO project_registry_audit
               (audit_id, project_id, actor_id, action, repository_fingerprint,
                config_sha256, backend_api_version, rationale, created_at,
                revision, transition_id, review_packet_sha256, review_packet_json,
                suspension_transition_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.audit_id,
                record.project_id,
                record.actor_id,
                record.action,
                record.repository_fingerprint,
                record.config_sha256,
                record.backend_api_version,
                record.rationale,
                record.created_at,
                record.revision,
                record.transition_id,
                record.review_packet_sha256,
                record.review_packet_json,
                record.suspension_transition_id,
            ),
        )

    @staticmethod
    def _digest_review_rows(
        connection: sqlite3.Connection,
        query: str,
        project_id: str,
    ) -> tuple[int, str]:
        """Hash ordered content-free review rows with bounded memory."""

        digest = hashlib.sha256()
        count = 0
        cursor = connection.execute(query, (project_id,))
        while rows := cursor.fetchmany(128):
            for row in rows:
                canonical = json.dumps(
                    tuple(row), ensure_ascii=False, separators=(",", ":")
                )
                digest.update(canonical.encode("utf-8"))
                digest.update(b"\n")
                count += 1
        return count, digest.hexdigest()

    @classmethod
    def _validate_reactivation_review_input(
        cls, request: ProjectStatusChangeRequest
    ) -> None:
        """Validate the review digest and fresh staging observation fields."""

        cls._validate_access_digest(  # pylint: disable=protected-access
            request.review_packet_sha256, "review_packet_sha256"
        )
        cls._validate_access_identity(  # pylint: disable=protected-access
            request.suspension_transition_id, "suspension_transition_id"
        )
        cls._validate_access_digest(  # pylint: disable=protected-access
            request.staging_inventory_sha256, "staging_inventory_sha256"
        )
        if (
            not is_exact_int(request.staging_inventory_count)
            or request.staging_inventory_count < 0
            or not is_exact_int(request.staging_inventory_bytes)
            or request.staging_inventory_bytes < 0
            or parse_optional_aware_timestamp(request.staging_inventory_observed_at)
            is None
        ):
            raise ValueError("reactivation requires a complete staging observation")

    @classmethod
    def _validate_project_status_request_fields(
        cls, request: ProjectStatusChangeRequest, status: str
    ) -> None:
        """Validate fields exclusive to suspension or reactivation requests."""

        if status == "suspended" and any(
            value is not None
            for value in (
                request.review_packet_sha256,
                request.suspension_transition_id,
                request.staging_inventory_sha256,
            )
        ):
            raise ValueError("suspension does not accept a reactivation review packet")
        if status == "active":
            cls._validate_access_digest(  # pylint: disable=protected-access
                request.review_packet_sha256, "review_packet_sha256"
            )
            cls._validate_access_identity(  # pylint: disable=protected-access
                request.suspension_transition_id, "suspension_transition_id"
            )

    @staticmethod
    def _project_retirement_from_row(row: sqlite3.Row) -> ProjectRetirementRecord:
        return ProjectRetirementRecord(
            project_id=row["project_id"],
            transition_id=row["transition_id"],
            retired_by=row["retired_by"],
            retired_revision=row["retired_revision"],
            source_epoch=row["source_epoch"],
            rationale=row["rationale"],
            retired_at=row["retired_at"],
        )

    @staticmethod
    def _consumer_binding_from_row(row: sqlite3.Row) -> ConsumerBindingRecord:
        return ConsumerBindingRecord(
            project_id=row["project_id"],
            status=row["status"],
            revision=row["revision"],
            source_epoch=row["source_epoch"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _consumer_binding_audit_from_row(
        row: sqlite3.Row,
    ) -> ConsumerBindingAuditRecord:
        return ConsumerBindingAuditRecord(
            audit_id=row["audit_id"],
            project_id=row["project_id"],
            actor_id=row["actor_id"],
            action=row["action"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            source_epoch=row["source_epoch"],
            revision=row["revision"],
            transition_id=row["transition_id"],
            rationale=row["rationale"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _append_consumer_binding_audit(
        connection: sqlite3.Connection, record: ConsumerBindingAuditRecord
    ) -> None:
        connection.execute(
            """INSERT INTO consumer_binding_audit
               (audit_id, project_id, actor_id, action, from_status, to_status,
                source_epoch, revision, transition_id, rationale, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.audit_id,
                record.project_id,
                record.actor_id,
                record.action,
                record.from_status,
                record.to_status,
                record.source_epoch,
                record.revision,
                record.transition_id,
                record.rationale,
                record.created_at,
            ),
        )

    @staticmethod
    def _resolve_consumer_binding_transition(
        request: ConsumerBindingTransitionRequest,
    ) -> tuple[str, str]:
        """Map the requested next state to its audited action and prior state."""

        transitions = {
            "deregistration_pending": ("deregistration_pending", "active"),
            "deregistered": ("deregistered", "deregistration_pending"),
            "active": ("reenrolled", "deregistered"),
        }
        transition = transitions.get(request.status)
        if transition is None:
            raise ValueError(
                "consumer binding status must be an explicit supported transition"
            )
        if not is_exact_int(request.expected_revision) or request.expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        return transition

    @staticmethod
    def _validate_consumer_reenrollment(
        connection: sqlite3.Connection,
        request: ConsumerBindingTransitionRequest,
        current_epoch: int,
    ) -> int:
        """Require current project identity before opening a new source epoch."""

        if (
            not is_exact_int(request.expected_source_epoch)
            or request.expected_source_epoch != current_epoch
        ):
            raise ConflictError("consumer source epoch is stale")
        if (
            not is_exact_int(request.expected_project_revision)
            or request.repository_fingerprint is None
            or request.config_sha256 is None
            or not is_exact_int(request.backend_api_version)
        ):
            raise ValueError(
                "re-enrollment requires the reviewed project revision and fingerprints"
            )
        registration = connection.execute(
            "SELECT * FROM project_registry WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        if registration is None or registration["status"] != "active":
            raise ConflictError("project registration is not active")
        if registration["revision"] != request.expected_project_revision:
            raise ConflictError("project registration revision is stale")
        if (
            registration["repository_fingerprint"] != request.repository_fingerprint
            or registration["config_sha256"] != request.config_sha256
            or registration["backend_api_version"] != request.backend_api_version
        ):
            raise ConflictError("project config changed before re-enrollment")
        return current_epoch + 1

    @staticmethod
    def _consumer_drain_inventory_row_bytes(row: sqlite3.Row) -> bytes:
        """Encode the exact fixed event identity fields covered by drain review."""

        return json.dumps(
            [row[key] for key in (
                "event_id", "payload_sha256", "idempotency_sha256",
                "source_id", "source_sequence", "status",
            )],
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")

    def _project_lifecycle_event_summary(
        self, project_id: str, observed_at: str
    ) -> _ProjectLifecycleEventSummary:
        """Read event counts, unresolved digest, and leases in the active snapshot."""

        event_counts = tuple(
            (str(row["status"]), int(row["count"]))
            for row in self._connection.execute(
                "SELECT status, COUNT(*) AS count FROM event_inbox "
                "WHERE project_id = ? GROUP BY status ORDER BY status",
                (project_id,),
            ).fetchall()
        )
        unprocessed_rows = self._connection.execute(
            """SELECT event_id, payload_sha256, idempotency_sha256,
                      source_id, source_sequence, status FROM event_inbox
               WHERE project_id = ? AND status <> 'processed'
               ORDER BY event_id""",
            (project_id,),
        ).fetchall()
        digest = hashlib.sha256()
        for row in unprocessed_rows:
            encoded = json.dumps(
                [row[key] for key in (
                    "event_id", "payload_sha256", "idempotency_sha256",
                    "source_id", "source_sequence", "status",
                )],
                separators=(",", ":"), ensure_ascii=True,
            ).encode("ascii")
            digest.update(len(encoded).to_bytes(4, "big"))
            digest.update(encoded)
        active_leases = int(self._connection.execute(
            """SELECT COUNT(*) FROM event_inbox WHERE project_id = ?
               AND lease_owner IS NOT NULL AND lease_expires_at > ?""",
            (project_id, observed_at),
        ).fetchone()[0])
        return _ProjectLifecycleEventSummary(
            event_counts, len(unprocessed_rows), digest.hexdigest(), active_leases
        )

    @staticmethod
    def _project_lifecycle_incomplete_reasons(
        event_counts: tuple[tuple[str, int], ...],
        terminal_inventory_complete: bool,
    ) -> list[str]:
        """Describe fixed conditions that make a lifecycle view incomplete."""

        known_statuses = {status.value for status in EventInboxStatus}
        reasons: list[str] = []
        if any(status not in known_statuses for status, _count in event_counts):
            reasons.append("unknown_event_status")
        if not terminal_inventory_complete:
            reasons.append("terminal_event_page_truncated")
        return reasons

    @classmethod
    def _validate_consumer_drain_request(
        cls, request: ConsumerDrainStoreRequest
    ) -> None:
        """Validate the short lifetime and stable caller/inventory fields."""

        if not 1 <= request.lifetime_seconds <= 900:
            raise ValueError("drain lifetime must be between 1 and 900 seconds")
        for name, value in (
            ("project_id", request.project_id),
            ("transition_id", request.transition_id),
            ("actor_id", request.actor_id),
            ("caller_subject", request.caller_subject),
        ):
            cls._validate_access_identity(value, name)
        if request.caller_profile is not None:
            cls._validate_access_identity(request.caller_profile, "caller_profile")
        if not re.fullmatch(r"[0-9a-f]{64}", request.expected_inventory_sha256):
            raise ValueError("inventory digest must be lowercase SHA-256")

    @staticmethod
    def _require_consumer_drain_fence(
        connection: sqlite3.Connection,
        request: ConsumerDrainStoreRequest,
    ) -> tuple[sqlite3.Row, sqlite3.Row]:
        """Require the active project at the exact reviewed drain transition."""

        binding = connection.execute(
            "SELECT * FROM consumer_bindings WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        registration = connection.execute(
            "SELECT * FROM project_registry WHERE project_id = ?",
            (request.project_id,),
        ).fetchone()
        transition = connection.execute(
            """SELECT 1 FROM consumer_binding_audit
               WHERE project_id = ? AND transition_id = ?
                 AND action = 'deregistration_pending'""",
            (request.project_id, request.transition_id),
        ).fetchone()
        message = "consumer is not at the reviewed drain transition"
        if binding is None:
            raise ConflictError(message)
        if (binding["status"], binding["revision"]) != (
            "deregistration_pending", request.expected_revision
        ):
            raise ConflictError(message)
        if (
            registration is None
            or registration["status"] != "active"
            or transition is None
        ):
            raise ConflictError(message)
        return binding, registration

    @staticmethod
    def _consumer_drain_authorization_replay(
        connection: sqlite3.Connection,
        request: ConsumerDrainStoreRequest,
        binding: sqlite3.Row,
        registration: sqlite3.Row,
    ) -> tuple[int, str] | None:
        """Return an identical drain receipt or reject transition-ID reuse."""

        prior = connection.execute(
            """SELECT * FROM consumer_drain_sessions
               WHERE project_id = ? AND transition_id = ?""",
            (request.project_id, request.transition_id),
        ).fetchone()
        if prior is None:
            return None
        existing = tuple(prior[key] for key in (
            "actor_id", "caller_subject", "caller_profile",
            "binding_revision", "source_epoch", "config_sha256",
            "inventory_sha256",
        ))
        expected = (
            request.actor_id, request.caller_subject, request.caller_profile,
            request.expected_revision, binding["source_epoch"],
            registration["config_sha256"], request.expected_inventory_sha256,
        )
        if existing != expected:
            raise ConflictError("drain transition ID was reused with changed input")
        event_count = connection.execute(
            """SELECT COUNT(*) FROM consumer_drain_events
               WHERE project_id = ? AND transition_id = ?""",
            (request.project_id, request.transition_id),
        ).fetchone()[0]
        return int(event_count), prior["expires_at"]

    def consumer_drain_allows(
        self,
        caller_subject: str,
        caller_profile: str | None,
        event: EventEnvelope,
    ) -> bool:
        """Check an exact inventoried envelope against a live drain capability."""

        now = datetime.now(UTC).isoformat()
        with self._lock:
            row = self._connection.execute(
                """SELECT session.*, item.payload_sha256, item.idempotency_sha256,
                          item.source_id, item.source_sequence, inbox.status
                   FROM consumer_drain_sessions AS session
                   JOIN consumer_drain_events AS item
                     ON item.project_id = session.project_id
                    AND item.transition_id = session.transition_id
                   JOIN event_inbox AS inbox
                     ON inbox.project_id = item.project_id
                    AND inbox.event_id = item.event_id
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = session.project_id
                   JOIN project_registry AS registration
                     ON registration.project_id = session.project_id
                   WHERE session.project_id = ? AND item.event_id = ?
                     AND session.caller_subject = ?
                     AND session.caller_profile IS ?
                     AND session.expires_at > ? AND session.revoked_at IS NULL
                     AND binding.status = 'deregistration_pending'
                     AND binding.revision = session.binding_revision
                     AND binding.source_epoch = session.source_epoch
                     AND registration.status = 'active'
                     AND registration.config_sha256 = session.config_sha256
                   ORDER BY session.created_at DESC LIMIT 1""",
                (event.project_id, event.event_id, caller_subject, caller_profile, now),
            ).fetchone()
        if row is None:
            return False
        serialized = event.to_json()
        payload_matches = (
            row["idempotency_sha256"] == event.idempotency_sha256
            if row["idempotency_sha256"] is not None
            else row["payload_sha256"]
            == hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        )
        return (
            payload_matches
            and row["source_id"] == event.source_id
            and row["source_sequence"] == event.source_sequence
        )

    def consumer_drain_epoch(
        self, project_id: str, caller_subject: str, caller_profile: str | None,
        event_id: str,
    ) -> int | None:
        """Return the old epoch only for an event in a live reviewed drain."""

        now = datetime.now(UTC).isoformat()
        with self._lock:
            row = self._connection.execute(
                """SELECT session.source_epoch FROM consumer_drain_sessions AS session
                   JOIN consumer_drain_events AS item
                     ON item.project_id = session.project_id
                    AND item.transition_id = session.transition_id
                   JOIN consumer_bindings AS binding
                     ON binding.project_id = session.project_id
                   JOIN project_registry AS registration
                     ON registration.project_id = session.project_id
                   WHERE session.project_id = ? AND item.event_id = ?
                     AND session.caller_subject = ? AND session.caller_profile IS ?
                     AND session.expires_at > ? AND session.revoked_at IS NULL
                     AND binding.status = 'deregistration_pending'
                     AND binding.revision = session.binding_revision
                     AND binding.source_epoch = session.source_epoch
                     AND registration.status = 'active'
                     AND registration.config_sha256 = session.config_sha256
                   ORDER BY session.created_at DESC LIMIT 1""",
                (project_id, event_id, caller_subject, caller_profile, now),
            ).fetchone()
        return int(row["source_epoch"]) if row is not None else None

    @staticmethod
    def _record_staging_occurrence(
        connection: sqlite3.Connection, project_id: str, artifact: ArtifactRef
    ) -> None:
        """Remember the exact filesystem occurrence without granting expiry age."""

        if (
            artifact.device_id is None
            or artifact.inode_id is None
            or artifact.occurrence_id is None
        ):
            return
        connection.execute(
            """INSERT INTO staging_artifact_occurrences
               (project_id, path, sha256, device_id, inode_id, occurrence_id, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(project_id, path) DO UPDATE SET
                 sha256 = excluded.sha256,
                 device_id = excluded.device_id,
                 inode_id = excluded.inode_id,
                 occurrence_id = excluded.occurrence_id,
                 observed_at = excluded.observed_at""",
            (
                project_id,
                artifact.path,
                artifact.sha256,
                artifact.device_id,
                artifact.inode_id,
                artifact.occurrence_id,
                utc_now(),
            ),
        )

    def active_staging_artifact_holds(
        self, project_id: str, artifacts: tuple[ArtifactRef, ...]
    ) -> dict[str, RetentionHoldKind]:
        """Read project-scoped unreleased holds for exact path/hash pairs."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", project_id):
            raise ValueError("project_id must be a bounded opaque identifier")
        held: dict[str, RetentionHoldKind] = {}
        for offset in range(0, len(artifacts), 400):
            page = artifacts[offset : offset + 400]
            if not page:
                continue
            requested = json.dumps(
                [{"path": item.path, "sha256": item.sha256} for item in page],
                separators=(",", ":"),
            )
            with self._lock:
                rows = self._connection.execute(
                    """WITH requested AS (
                           SELECT json_extract(value, '$.path') AS path,
                                  json_extract(value, '$.sha256') AS sha256
                           FROM json_each(?)
                       )
                       SELECT p.path, p.retention_hold FROM purge_targets AS p
                       JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       JOIN requested AS q ON q.path = p.path AND q.sha256 = p.sha256
                       WHERE g.project_id = ? AND p.retention_hold IS NOT NULL
                         AND p.hold_released_at IS NULL""",
                    (requested, project_id),
                ).fetchall()
            for row in rows:
                held[row["path"]] = RetentionHoldKind(row["retention_hold"])
        return held

    @staticmethod
    def _validate_cleanup_authorization_inventory(
        connection: sqlite3.Connection,
        receipt_id: str,
        project_id: str,
        manifest_sha256: str,
    ) -> None:
        """Require a complete, action-bound inventory with the exact manifest."""

        receipt = connection.execute(
            """SELECT r.artifact_inventory_complete
               FROM audit_receipts AS r
               JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
               JOIN goals AS g ON g.goal_id = s.goal_id
               WHERE r.receipt_id = ? AND g.project_id = ?""",
            (receipt_id, project_id),
        ).fetchone()
        if receipt is None:
            raise NotFoundError("audit receipt not found")
        if not bool(receipt["artifact_inventory_complete"]):
            raise ConflictError("cleanup requires a complete artifact inventory")
        rows = connection.execute(
            "SELECT path, sha256, occurrence_id, retention_hold, "
            "reacquisition_action FROM purge_targets "
            "WHERE receipt_id = ? ORDER BY path",
            (receipt_id,),
        ).fetchall()
        for row in rows:
            action = ReacquisitionAction(row["reacquisition_action"])
            is_held = row["retention_hold"] is not None
            if action is ReacquisitionAction.NOT_RECORDED:
                raise ConflictError(
                    "cleanup authorization requires a per-artifact retention "
                    "or reacquisition action"
                )
            if is_held != (action is ReacquisitionAction.RETAIN_UNDER_HOLD):
                raise ConflictError(
                    "artifact hold state and reacquisition action do not agree"
                )
        canonical = json.dumps(
            [(row["path"], row["sha256"], row["occurrence_id"]) for row in rows],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        observed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if observed != manifest_sha256:
            raise ConflictError("cleanup manifest does not match the exact inventory")
