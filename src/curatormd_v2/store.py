"""SQLite persistence for goals, compact facts, SDEs, and purge receipts."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from types import TracebackType
from typing import Generator, Self, cast
import zlib

from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventDisposition,
    EventInboxStatus,
    EventQueueStatus,
)
from .content_safety import validate_safe_text
from .models import (
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    EventClassStorageUsage,
    EventFailureCategory,
    EventFailureCategoryUsage,
    Fact,
    FactArchiveReceipt,
    FactCapacity,
    FactCompactionProposal,
    FactKind,
    GoalCard,
    GoalCriteriaVersion,
    GoalStatus,
    GoalStatusStorageUsage,
    GlobalEventInboxUsage,
    MAX_CRITERIA_REVISIONS,
    MAX_FACTS_PER_GOAL,
    MAX_FACT_BYTES_PER_GOAL,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
    MAX_FACT_COMPACTION_BATCH_FACTS,
    MAX_FACT_COMPACTION_SOURCE_BYTES,
    MAX_GOAL_LIST_PAGE,
    MAX_EVENT_RECEIPTS_GLOBAL,
    MAX_EVENT_RECEIPT_BYTES_GLOBAL,
    EVENT_FAILURE_METADATA_RESERVE_BYTES,
    MAX_SDE_CORRECTIONS_PER_CANDIDATE,
    MAX_SDE_CORRECTIONS_PER_PROJECT,
    MAX_SDE_FEEDBACK_PER_PROJECT,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    MAX_SUCCESS_CRITERIA,
    Materiality,
    ProjectStorageUsage,
    ProjectActivitySnapshot,
    ProjectOperationalCounts,
    PurgeFailureCode,
    PurgeTargetRecord,
    PurgeStatus,
    ReviewDecision,
    RetentionHoldKind,
    SDECandidate,
    SDEStatus,
    SuccessCriterion,
    new_id,
    utc_now,
)
from .reporting import GoalReportContext
from .schema_migrations import (
    SQLITE_SCHEMA_VERSION,
    apply_schema_migrations,
    finish_unversioned_migrations,
)
from .validation import is_exact_int

EVENT_RETRY_BASE_SECONDS = 5
EVENT_RETRY_MAX_SECONDS = 900
PURGE_RETRY_BASE_SECONDS = 5
PURGE_RETRY_MAX_SECONDS = 900


class NotFoundError(LookupError):
    """A requested goal, fact, candidate, or receipt does not exist."""


class ConflictError(RuntimeError):
    """A requested transition conflicts with already-recorded state."""


class EventClaimError(ConflictError):
    """A worker no longer owns a live lease for the claimed event."""


class FactCapacityError(ConflictError):
    """A goal or project reached its immutable fact-history ceiling."""


class GoalListCapacityError(ConflictError):
    """An unpaged compatibility listing exceeds its safe result ceiling."""


class FactArchiveIntegrityError(RuntimeError):
    """A compressed fact archive failed its integrity or schema checks."""


class EventInboxCapacityError(ConflictError):
    """The global event-inbox count or retained-byte ceiling was reached."""


class EventOrderError(ConflictError):
    """An event sequence is repeated or arrives with a gap."""


@dataclass(frozen=True, slots=True)
class ProjectRegistrationRecord:
    """Current durable binding between an opaque project and host fingerprints."""

    project_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    status: str
    registered_by: str
    registered_at: str
    updated_by: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProjectRegistryAuditRecord:
    """Append-only evidence of a project registration or lifecycle change."""

    audit_id: str
    project_id: str
    actor_id: str
    action: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    rationale: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ProjectGrantRecord:
    """An exact project/action grant and optional immutable revocation event."""

    grant_id: str
    project_id: str
    subject_id: str
    action: str
    granted_by: str
    rationale: str
    granted_at: str
    revoked_by: str | None = None
    revoke_rationale: str | None = None
    revoked_at: str | None = None

    @property
    def active(self) -> bool:
        """Whether this grant has no recorded revocation."""

        return self.revoked_at is None


_ACCESS_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCESS_RATIONALE_LIMIT = 1000
_PROJECT_ACCESS_ACTIONS = frozenset(
    {"read", "write", "review", "purge_retry", "retention_hold_release", "event_retry"}
)


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_ERROR_CODE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")


def _evidence_to_dict(evidence: EvidenceRef) -> dict[str, str]:
    return {
        "evidence_kind": evidence.evidence_kind,
        "locator": evidence.locator,
        "sha256": evidence.sha256,
        "outcome": evidence.outcome.value,
    }


def _attestation_to_dict(attestation: EvidenceAttestation) -> dict[str, str]:
    """Serialize only the bounded provenance fields retained by the contract."""

    return {
        "evidence_kind": attestation.evidence_kind,
        "evidence_sha256": attestation.evidence_sha256,
        "project_id": attestation.project_id,
        "goal_id": attestation.goal_id,
        "criterion_id": attestation.criterion_id,
        "adapter_id": attestation.adapter_id,
        "authenticated_subject": attestation.authenticated_subject,
        "source_revision": attestation.source_revision,
        "observed_at": attestation.observed_at,
        "verified_at": attestation.verified_at,
        "valid_until": attestation.valid_until,
        "revocation_checked_at": attestation.revocation_checked_at,
    }


def _validate_retirement_request(
    goal_id: str,
    status: GoalStatus,
    reason: str,
    fact: Fact,
    replacement_goal_id: str | None,
) -> None:
    """Validate the immutable inputs for a cancellation or supersession."""

    if status not in {GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}:
        raise ValueError("retirement status must be cancelled or superseded")
    if not reason.strip() or len(reason) > 500 or "\n" in reason or "\r" in reason:
        raise ValueError("retirement requires a single-line reason of at most 500 characters")
    expected_kind = (
        FactKind.CANCELLED if status is GoalStatus.CANCELLED else FactKind.SUPERSEDED
    )
    if fact.goal_id != goal_id or fact.kind is not expected_kind:
        raise ConflictError("retirement transition requires its matching system fact")
    if (status is GoalStatus.SUPERSEDED) != (replacement_goal_id is not None):
        raise ValueError("only supersession has a replacement goal")
    if replacement_goal_id == goal_id:
        raise ValueError("a goal cannot supersede itself")


def _validate_replacement_goal(
    connection: sqlite3.Connection,
    goal_id: str,
    project_id: str,
    replacement_goal_id: str | None,
) -> None:
    """Require a same-project active replacement outside the retired subtree."""

    if replacement_goal_id is None:
        return
    replacement = connection.execute(
        "SELECT project_id, status, parent_goal_id FROM goals WHERE goal_id = ?",
        (replacement_goal_id,),
    ).fetchone()
    if replacement is None or replacement["project_id"] != project_id:
        raise ConflictError("replacement goal must exist in the same project")
    if GoalStatus(replacement["status"]) is not GoalStatus.ACTIVE:
        raise ConflictError("replacement goal must be active")
    ancestor_id = replacement["parent_goal_id"]
    while ancestor_id is not None:
        if ancestor_id == goal_id:
            raise ConflictError("a goal cannot be superseded by its descendant")
        ancestor = connection.execute(
            "SELECT parent_goal_id FROM goals WHERE goal_id = ? AND project_id = ?",
            (ancestor_id, project_id),
        ).fetchone()
        if ancestor is None:
            raise ConflictError("replacement goal has a broken parent chain")
        ancestor_id = ancestor["parent_goal_id"]


def _validate_retirement_relationships(
    connection: sqlite3.Connection, goal_id: str, project_id: str
) -> None:
    """Reject retirement while this goal has unresolved children or dependents."""

    active_children = connection.execute(
        "SELECT goal_id FROM goals WHERE parent_goal_id = ? AND status NOT IN (?, ?, ?)",
        (
            goal_id,
            GoalStatus.COMPLETE.value,
            GoalStatus.CANCELLED.value,
            GoalStatus.SUPERSEDED.value,
        ),
    ).fetchall()
    if active_children:
        raise ConflictError(
            "resolve child goals before cancelling or superseding their parent: "
            + ", ".join(child["goal_id"] for child in active_children)
        )
    dependent_rows = connection.execute(
        "SELECT goal_id, depends_on_json, status FROM goals "
        "WHERE project_id = ? AND goal_id != ?",
        (project_id, goal_id),
    ).fetchall()
    active_dependents = tuple(
        dependent["goal_id"]
        for dependent in dependent_rows
        if GoalStatus(dependent["status"])
        not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
        and goal_id in json.loads(dependent["depends_on_json"])
    )
    if active_dependents:
        raise ConflictError(
            "resolve dependent goals before retiring this dependency: "
            + ", ".join(active_dependents)
        )


class CuratorStore:
    """Thread-safe SQLite store using short, explicit write transactions."""

    def __init__(self, database: str | Path) -> None:
        requested_database = str(database)
        self.database = requested_database
        if requested_database != ":memory:":
            database_path = Path(requested_database).expanduser()
            if database_path.is_symlink():
                raise ValueError("database path must not be a symlink")
            database_path = database_path.resolve()
            database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not database_path.exists():
                try:
                    descriptor = os.open(
                        database_path,
                        os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
            metadata = database_path.stat(follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("database path must be a regular file")
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise PermissionError(
                    "Curator database must be private (mode 0600 or stricter)"
                )
            self.database = str(database_path)
        self._lock = RLock()
        self._transaction_depth = 0
        self._connection = sqlite3.connect(
            self.database, isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.database != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        try:
            self._create_schema()
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        """Close the SQLite connection after its owner has finished using it."""

        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        """Return this store for use in a resource-managed block."""

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the database connection when leaving a resource-managed block."""

        self.close()

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
            except Exception:
                self._transaction_depth -= 1
                if outermost:
                    self._connection.rollback()
                else:
                    self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            self._transaction_depth -= 1
            if outermost:
                self._connection.commit()
            else:
                self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")

    def transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        """Expose a transaction boundary for atomic multi-operation workflows."""

        return self._transaction()

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

    def register_project(
        self,
        project_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
        actor_id: str,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Register a host-verified project binding exactly once.

        The two SHA-256 values are supplied by the trusted host adapter. This
        store validates their shape but cannot authenticate or derive them.
        """

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
                project_id,
                actor_id,
                "registered",
                repository_fingerprint,
                config_sha256,
                backend_api_version,
                rationale,
                now,
            )
            row = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("project registration insert returned no row")
        return self._project_registration_from_row(row)

    @staticmethod
    def _append_project_registry_audit(
        connection: sqlite3.Connection,
        project_id: str,
        actor_id: str,
        action: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
        rationale: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO project_registry_audit
               (audit_id, project_id, actor_id, action, repository_fingerprint,
                config_sha256, backend_api_version, rationale, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id(),
                project_id,
                actor_id,
                action,
                repository_fingerprint,
                config_sha256,
                backend_api_version,
                rationale,
                created_at,
            ),
        )

    def update_project_registration(
        self,
        project_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
        actor_id: str,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Update host fingerprints with a separate attributable audit event."""

        self._validate_access_identity(project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        self._validate_access_digest(repository_fingerprint, "repository_fingerprint")
        self._validate_access_digest(config_sha256, "config_sha256")
        self._validate_backend_api_version(backend_api_version)
        self._validate_access_rationale(rationale)
        now = utc_now()
        with self._transaction() as connection:
            current = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if current is None:
                raise NotFoundError("project registration not found")
            replacement = (
                repository_fingerprint,
                config_sha256,
                backend_api_version,
            )
            previous = (
                current["repository_fingerprint"],
                current["config_sha256"],
                current["backend_api_version"],
            )
            if replacement == previous:
                raise ConflictError("project registration is unchanged")
            collision = connection.execute(
                "SELECT project_id FROM project_registry "
                "WHERE repository_fingerprint = ? AND project_id <> ?",
                (repository_fingerprint, project_id),
            ).fetchone()
            if collision is not None:
                raise ConflictError("repository fingerprint is already registered")
            connection.execute(
                """UPDATE project_registry SET repository_fingerprint = ?,
                   config_sha256 = ?, backend_api_version = ?, updated_by = ?,
                   updated_at = ? WHERE project_id = ?""",
                (
                    repository_fingerprint,
                    config_sha256,
                    backend_api_version,
                    actor_id,
                    now,
                    project_id,
                ),
            )
            self._append_project_registry_audit(
                connection,
                project_id,
                actor_id,
                "updated",
                repository_fingerprint,
                config_sha256,
                backend_api_version,
                rationale,
                now,
            )
            row = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("updated project registration returned no row")
        return self._project_registration_from_row(row)

    def set_project_status(
        self,
        project_id: str,
        status: str,
        actor_id: str,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Suspend or reactivate a registration, retaining every audit event."""

        self._validate_access_identity(project_id, "project_id")
        self._validate_access_identity(actor_id, "actor_id")
        status = self._validate_project_status(status)
        self._validate_access_rationale(rationale)
        now = utc_now()
        with self._transaction() as connection:
            current = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if current is None:
                raise NotFoundError("project registration not found")
            old_status = current["status"]
            if old_status == status:
                raise ConflictError("project registration already has that status")
            action = "suspended" if status == "suspended" else "reactivated"
            connection.execute(
                """UPDATE project_registry SET status = ?, updated_by = ?,
                   updated_at = ? WHERE project_id = ?""",
                (status, actor_id, now, project_id),
            )
            self._append_project_registry_audit(
                connection,
                project_id,
                actor_id,
                action,
                current["repository_fingerprint"],
                current["config_sha256"],
                current["backend_api_version"],
                rationale,
                now,
            )
            row = connection.execute(
                "SELECT * FROM project_registry WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("project status update returned no row")
        return self._project_registration_from_row(row)

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
                   JOIN project_grants AS grant_row
                     ON grant_row.project_id = project.project_id
                   LEFT JOIN project_grant_revocations AS revocation
                     ON revocation.grant_id = grant_row.grant_id
                   WHERE project.project_id = ? AND project.status = 'active'
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

            # Version 1 upgrades the previously unversioned schema in one
            # transaction. Keep every legacy column addition and data repair
            # below atomic with its user_version stamp.
            for statement in schema.split(";"):
                if statement.strip():
                    connection.execute(statement)
            archive_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(fact_archives)"
                ).fetchall()
            }
            if "schema_version" not in archive_columns:
                connection.execute(
                    "ALTER TABLE fact_archives ADD COLUMN schema_version "
                    "INTEGER NOT NULL DEFAULT 1"
                )
            goal_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(goals)").fetchall()
            }
            if "project_id" not in goal_columns:
                connection.execute(
                    "ALTER TABLE goals ADD COLUMN project_id TEXT NOT NULL DEFAULT 'default'"
                )
            if "checklist_version" not in goal_columns:
                connection.execute("ALTER TABLE goals ADD COLUMN checklist_version TEXT")
            if "checklist_source_text" not in goal_columns:
                connection.execute("ALTER TABLE goals ADD COLUMN checklist_source_text TEXT")
            if "parent_goal_id" not in goal_columns:
                connection.execute("ALTER TABLE goals ADD COLUMN parent_goal_id TEXT")
            if "depends_on_json" not in goal_columns:
                connection.execute(
                    "ALTER TABLE goals ADD COLUMN depends_on_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "criteria_revision" not in goal_columns:
                connection.execute(
                    "ALTER TABLE goals ADD COLUMN criteria_revision INTEGER NOT NULL DEFAULT 1"
                )
            if "superseded_by_goal_id" not in goal_columns:
                connection.execute(
                    "ALTER TABLE goals ADD COLUMN superseded_by_goal_id TEXT"
                )
            if "lifecycle_revision" not in goal_columns:
                connection.execute(
                    "ALTER TABLE goals ADD COLUMN lifecycle_revision INTEGER NOT NULL DEFAULT 1"
                )
                connection.execute(
                    "UPDATE goals SET lifecycle_revision = 2"
                )
            connection.execute(
                "INSERT OR IGNORE INTO goal_criteria_versions "
                "(goal_id, revision, criteria_json, reason, created_at) "
                "SELECT goal_id, criteria_revision, criteria_json, 'Initial criteria', created_at "
                "FROM goals"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS goals_parent "
                "ON goals(parent_goal_id, project_id, created_at, goal_id)"
            )
            receipt_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(audit_receipts)"
                ).fetchall()
            }
            receipt_migrations = (
                ("reviewer_id", "TEXT"),
                ("review_rationale", "TEXT"),
                ("canonical_persisted", "INTEGER NOT NULL DEFAULT 0"),
                ("canonical_target", "TEXT"),
                ("canonical_sha256", "TEXT"),
                ("canonical_persisted_at", "TEXT"),
            )
            receipt_schema_upgraded = any(
                column not in receipt_columns for column, _declaration in receipt_migrations
            )
            for column, declaration in receipt_migrations:
                if column not in receipt_columns:
                    connection.execute(
                        f"ALTER TABLE audit_receipts ADD COLUMN {column} {declaration}"
                    )
            if receipt_schema_upgraded:
                connection.execute(
                    "UPDATE audit_receipts SET purge_status = ? "
                    "WHERE canonical_persisted = 0",
                    (PurgeStatus.PURGE_PENDING.value,),
                )
            event_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(event_inbox)"
                ).fetchall()
            }
            if "event_type" not in event_columns:
                connection.execute(
                    "ALTER TABLE event_inbox ADD COLUMN event_type TEXT "
                    "NOT NULL DEFAULT 'legacy.unknown'"
                )
            if "payload_bytes" not in event_columns:
                connection.execute(
                    "ALTER TABLE event_inbox ADD COLUMN payload_bytes INTEGER "
                    "NOT NULL DEFAULT 0"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS event_inbox_usage "
                "ON event_inbox(project_id, event_type, status)"
            )
            connection.execute("PRAGMA user_version = 1")
            finish_unversioned_migrations(connection)

    def add_goal(
        self, goal: GoalCard, *, source_event_id: str | None = None
    ) -> None:
        """Persist a goal and its initial immutable criteria version."""

        if source_event_id is not None and (
            not source_event_id.strip() or len(source_event_id) > 128
        ):
            raise ValueError("source_event_id must be a bounded opaque identifier")
        if source_event_id is not None:
            validate_safe_text(source_event_id, "source_event_id")

        criteria = [
            {"criterion_id": item.criterion_id, "description": item.description}
            for item in goal.success_criteria
        ]
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO goals
                   (goal_id, project_id, problem, criteria_json, owner, checklist_id,
                    checklist_version, checklist_source_text, parent_goal_id,
                    depends_on_json, criteria_revision, lifecycle_revision,
                    superseded_by_goal_id, initial_status, source_event_id,
                    status, next_action, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    goal.goal_id,
                    goal.project_id,
                    goal.problem,
                    _json_dump(criteria),
                    goal.owner,
                    goal.checklist_id,
                    goal.checklist_version,
                    goal.checklist_source_text,
                    goal.parent_goal_id,
                    _json_dump(list(goal.depends_on_goal_ids)),
                    goal.criteria_revision,
                    goal.lifecycle_revision,
                    goal.superseded_by_goal_id,
                    goal.status.value,
                    source_event_id,
                    goal.status.value,
                    goal.next_action,
                    goal.created_at,
                    goal.updated_at,
                ),
            )
            connection.execute(
                "INSERT INTO goal_criteria_versions "
                "(goal_id, revision, criteria_json, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    goal.goal_id,
                    goal.criteria_revision,
                    _json_dump(criteria),
                    "Initial criteria",
                    goal.created_at,
                ),
            )

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

    def list_goals(
        self,
        statuses: tuple[GoalStatus, ...] = (),
        project_id: str | None = None,
    ) -> tuple[GoalCard, ...]:
        """List goals filtered by lifecycle state and optional project scope."""

        status_values = json.dumps([status.value for status in statuses])
        query = """SELECT goal_id, project_id FROM goals
                   WHERE (? IS NULL OR project_id = ?)
                     AND (json_array_length(?) = 0 OR status IN
                          (SELECT value FROM json_each(?)))
                   ORDER BY created_at, goal_id LIMIT ?"""
        with self._lock:
            rows = self._connection.execute(
                query,
                (
                    project_id,
                    project_id,
                    status_values,
                    status_values,
                    MAX_GOAL_LIST_PAGE + 1,
                ),
            ).fetchall()
        if len(rows) > MAX_GOAL_LIST_PAGE:
            raise GoalListCapacityError(
                "unpaged goal listing exceeds 100 records; use goal_list_page"
            )
        return tuple(
            self.get_goal(row["goal_id"], row["project_id"]) for row in rows
        )

    def list_goal_page(
        self,
        project_id: str,
        offset: int,
        limit: int,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> tuple[int, tuple[GoalCard, ...]]:
        """Return one bounded project-scoped goal page and its total count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        status_values = json.dumps([status.value for status in statuses])
        with self._lock:
            rows = self._connection.execute(
                """WITH project_goals AS (
                     SELECT goal_id, project_id, created_at FROM goals
                     WHERE project_id = ?
                       AND (json_array_length(?) = 0 OR status IN
                            (SELECT value FROM json_each(?)))
                   ), page AS (
                     SELECT goal_id, project_id FROM project_goals
                     ORDER BY created_at, goal_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM project_goals) AS total,
                          page.goal_id, page.project_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (project_id, status_values, status_values, limit, offset),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["goal_id"] is not None)
        return total, tuple(
            self.get_goal(row["goal_id"], project_id) for row in page_rows
        )

    def list_child_goals(
        self, parent_goal_id: str, project_id: str
    ) -> tuple[GoalCard, ...]:
        """List direct children without crossing the project boundary."""

        with self._lock:
            rows = self._connection.execute(
                "SELECT goal_id FROM goals WHERE parent_goal_id = ? AND project_id = ? "
                "ORDER BY created_at, goal_id",
                (parent_goal_id, project_id),
            ).fetchall()
        return tuple(
            self.get_goal(row["goal_id"], project_id) for row in rows
        )

    def list_child_goal_page(
        self,
        parent_goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> tuple[int, tuple[GoalCard, ...]]:
        """Return one bounded, project-scoped page of direct child cards."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        status_values = json.dumps([status.value for status in statuses])
        with self._lock:
            rows = self._connection.execute(
                """WITH project_children AS (
                     SELECT goal_id, created_at FROM goals
                     WHERE project_id = ? AND parent_goal_id = ?
                       AND (json_array_length(?) = 0 OR status IN
                            (SELECT value FROM json_each(?)))
                   ), page AS (
                     SELECT goal_id FROM project_children
                     ORDER BY created_at, goal_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM project_children) AS total,
                          page.goal_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    project_id,
                    parent_goal_id,
                    status_values,
                    status_values,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["goal_id"] is not None)
        return total, tuple(
            self.get_goal(row["goal_id"], project_id) for row in page_rows
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

    def _append_fact(
        self,
        connection: sqlite3.Connection,
        fact: Fact,
        project_id: str | None = None,
    ) -> tuple[Fact, bool]:
        evidence_json = _json_dump([_evidence_to_dict(item) for item in fact.evidence])
        attestations_json = _json_dump(
            [_attestation_to_dict(item) for item in fact.verification_attestations]
        )
        dedupe_key = self._fact_dedupe_key(fact)
        goal_row = connection.execute(
            "SELECT project_id, status FROM goals WHERE goal_id = ?", (fact.goal_id,)
        ).fetchone()
        if goal_row is None or (
            project_id is not None and goal_row["project_id"] != project_id
        ):
            raise NotFoundError(f"goal not found: {fact.goal_id}")
        existing = connection.execute(
            "SELECT * FROM facts WHERE dedupe_key = ?", (dedupe_key,)
        ).fetchone()
        if existing is not None:
            return self._fact_from_row(existing), False
        archived_duplicate = connection.execute(
            """SELECT fact_id FROM fact_archive_items WHERE dedupe_key = ?""",
            (dedupe_key,),
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
            fact, evidence_json, attestations_json, dedupe_key
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
                evidence_json,
                attestations_json,
                fact.source_event_id,
                dedupe_key,
                fact.created_at,
            )
        )
        row = connection.execute(
            "SELECT * FROM facts WHERE dedupe_key = ?", (dedupe_key,)
        ).fetchone()
        if row is None:
            raise RuntimeError("inserted fact row could not be read back")
        return self._fact_from_row(row), True

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
        goal_id: str,
        status: GoalStatus,
        next_action: str | None,
        facts: tuple[Fact, ...],
        expected_lifecycle_revision: int,
        project_id: str | None = None,
    ) -> GoalCard:
        """Atomically write a lifecycle transition and its compact facts."""

        if not is_exact_int(expected_lifecycle_revision) or expected_lifecycle_revision < 1:
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if status not in {
            GoalStatus.COMPLETE,
            GoalStatus.OPEN,
            GoalStatus.BLOCKED,
            GoalStatus.DEFERRED,
        }:
            raise ConflictError(
                "transition_goal may target only complete, open, blocked, or deferred"
            )
        if next_action is not None and len(next_action) > 1000:
            raise ValueError("next_action exceeds 1000 characters")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, lifecycle_revision FROM goals WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
            if row is None or (
                project_id is not None and row["project_id"] != project_id
            ):
                raise NotFoundError(f"goal not found: {goal_id}")
            current_status = GoalStatus(row["status"])
            if current_status in {
                GoalStatus.COMPLETE,
                GoalStatus.CANCELLED,
                GoalStatus.SUPERSEDED,
            }:
                raise ConflictError("terminal goals cannot transition again")
            if current_status is GoalStatus.PLANNED and status not in {
                GoalStatus.BLOCKED,
                GoalStatus.DEFERRED,
            }:
                raise ConflictError(
                    "planned goals must be activated before finish evaluation"
                )
            if row["lifecycle_revision"] != expected_lifecycle_revision:
                raise ConflictError("goal lifecycle revision changed; reload before updating")
            for fact in facts:
                if fact.goal_id != goal_id:
                    raise ConflictError("transition facts must belong to the goal")
                self._append_fact(connection, fact, project_id)
            connection.execute(
                "UPDATE goals SET status = ?, next_action = ?, lifecycle_revision = ?, "
                "updated_at = ? "
                "WHERE goal_id = ?",
                (
                    status.value,
                    next_action,
                    expected_lifecycle_revision + 1,
                    utc_now(),
                    goal_id,
                ),
            )
        return self.get_goal(goal_id, project_id)

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
        goal_id: str,
        status: GoalStatus,
        reason: str,
        fact: Fact,
        project_id: str | None = None,
        replacement_goal_id: str | None = None,
    ) -> GoalCard:
        """Atomically cancel or supersede a live goal with an immutable fact."""

        _validate_retirement_request(
            goal_id, status, reason, fact, replacement_goal_id
        )
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id FROM goals WHERE goal_id = ?", (goal_id,)
            ).fetchone()
            if row is None or (project_id is not None and row["project_id"] != project_id):
                raise NotFoundError(f"goal not found: {goal_id}")
            if GoalStatus(row["status"]) in {
                GoalStatus.COMPLETE,
                GoalStatus.CANCELLED,
                GoalStatus.SUPERSEDED,
            }:
                raise ConflictError("terminal goals cannot be cancelled or superseded")
            project = row["project_id"]
            _validate_replacement_goal(
                connection, goal_id, project, replacement_goal_id
            )
            _validate_retirement_relationships(connection, goal_id, project)
            self._append_fact(connection, fact, project_id)
            connection.execute(
                "UPDATE goals SET status = ?, next_action = NULL, "
                "superseded_by_goal_id = ?, lifecycle_revision = lifecycle_revision + 1, "
                "updated_at = ? WHERE goal_id = ?",
                (status.value, replacement_goal_id, utc_now(), goal_id),
            )
        return self.get_goal(goal_id, project_id)

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
            parent_goal_id = row["parent_goal_id"]
            if parent_goal_id is not None:
                parent = connection.execute(
                    "SELECT status FROM goals WHERE goal_id = ? AND project_id = ?",
                    (parent_goal_id, row["project_id"]),
                ).fetchone()
                if parent is None:
                    raise ConflictError("goal parent is missing from its project")
                if GoalStatus(parent["status"]) in {
                    GoalStatus.COMPLETE,
                    GoalStatus.CANCELLED,
                    GoalStatus.SUPERSEDED,
                }:
                    raise ConflictError("reopen or replace the terminal parent first")
            goal_row = connection.execute(
                "SELECT depends_on_json FROM goals WHERE goal_id = ?", (goal_id,)
            ).fetchone()
            for dependency_id in json.loads(goal_row["depends_on_json"]):
                dependency = connection.execute(
                    "SELECT status FROM goals WHERE goal_id = ? AND project_id = ?",
                    (dependency_id, row["project_id"]),
                ).fetchone()
                if dependency is None:
                    raise ConflictError("goal dependency is missing from its project")
                if GoalStatus(dependency["status"]) in {
                    GoalStatus.CANCELLED,
                    GoalStatus.SUPERSEDED,
                }:
                    raise ConflictError(
                        "replace the cancelled or superseded dependency before reopening"
                    )
            completed_goals = connection.execute(
                "SELECT goal_id, depends_on_json FROM goals "
                "WHERE project_id = ? AND status = ? AND goal_id != ?",
                (row["project_id"], GoalStatus.COMPLETE.value, goal_id),
            ).fetchall()
            completed_dependents = tuple(
                item["goal_id"]
                for item in completed_goals
                if goal_id in json.loads(item["depends_on_json"])
            )
            if completed_dependents:
                raise ConflictError(
                    "reopen completed dependent goals first: "
                    + ", ".join(completed_dependents)
                )
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

    def amend_goal_criteria(
        self,
        goal_id: str,
        expected_revision: int,
        criteria: tuple[SuccessCriterion, ...],
        reason: str,
        next_action: str,
        fact: Fact,
        project_id: str | None = None,
        expected_lifecycle_revision: int | None = None,
    ) -> GoalCard:
        """Replace the active contract while retaining every immutable version."""

        if expected_lifecycle_revision is not None and (
            not is_exact_int(expected_lifecycle_revision)
            or expected_lifecycle_revision < 1
        ):
            raise ValueError("expected_lifecycle_revision must be a positive integer")
        if fact.goal_id != goal_id or fact.kind is not FactKind.CRITERIA_AMENDED:
            raise ConflictError("criteria amendment requires its system amendment fact")
        if not is_exact_int(expected_revision) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if expected_revision >= MAX_CRITERIA_REVISIONS:
            raise ValueError(
                f"criteria history is limited to {MAX_CRITERIA_REVISIONS} revisions"
            )
        if not criteria or len(criteria) > MAX_SUCCESS_CRITERIA:
            raise ValueError(
                f"amended criteria must contain 1-{MAX_SUCCESS_CRITERIA} items"
            )
        criterion_ids = tuple(item.criterion_id for item in criteria)
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("amended criterion IDs must be unique")
        if not reason.strip() or not next_action.strip() or len(next_action) > 1000:
            raise ValueError("criteria amendment requires a bounded reason and next action")
        serialized = _json_dump([
            {"criterion_id": item.criterion_id, "description": item.description}
            for item in criteria
        ])
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, project_id, criteria_revision, criteria_json, lifecycle_revision "
                "FROM goals WHERE goal_id = ?",
                (goal_id,),
            ).fetchone()
            if row is None or (project_id is not None and row["project_id"] != project_id):
                raise NotFoundError(f"goal not found: {goal_id}")
            if GoalStatus(row["status"]) in {
                GoalStatus.COMPLETE,
                GoalStatus.CANCELLED,
                GoalStatus.SUPERSEDED,
            }:
                raise ConflictError("terminal goals cannot amend their criteria")
            if row["criteria_revision"] != expected_revision:
                raise ConflictError("criteria revision changed; reload before amending")
            expected_state_revision = (
                row["lifecycle_revision"]
                if expected_lifecycle_revision is None
                else expected_lifecycle_revision
            )
            if row["lifecycle_revision"] != expected_state_revision:
                raise ConflictError("goal lifecycle revision changed; reload before amending")
            if row["criteria_json"] == serialized:
                raise ConflictError("criteria amendment has no change")
            revision = expected_revision + 1
            created_at = utc_now()
            self._append_fact(connection, fact, project_id)
            connection.execute(
                "UPDATE goals SET criteria_json = ?, criteria_revision = ?, "
                "next_action = ?, lifecycle_revision = ?, updated_at = ? WHERE goal_id = ?",
                (
                    serialized,
                    revision,
                    next_action.strip(),
                    expected_state_revision + 1,
                    created_at,
                    goal_id,
                ),
            )
            connection.execute(
                "INSERT INTO goal_criteria_versions "
                "(goal_id, revision, criteria_json, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (goal_id, revision, serialized, reason.strip(), created_at),
            )
        return self.get_goal(goal_id, project_id)

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
    def _fact_from_archive_record(value: object) -> Fact:
        required = {
            "fact_id",
            "goal_id",
            "kind",
            "bullet",
            "criterion_id",
            "evidence",
            "created_at",
        }
        if not isinstance(value, dict):
            raise FactArchiveIntegrityError("fact archive record schema is invalid")
        record = cast(dict[str, object], value)
        optional = {"verification_attestations", "source_event_id"}
        if not required.issubset(record) or not set(record).issubset(required | optional):
            raise FactArchiveIntegrityError("fact archive record schema is invalid")
        if not isinstance(record["evidence"], list):
            raise FactArchiveIntegrityError("fact archive evidence schema is invalid")
        validation_failed = False
        fact: Fact | None = None
        try:
            evidence_items = cast(list[object], record["evidence"])
            evidence: list[EvidenceRef] = []
            for raw_item in evidence_items:
                if not isinstance(raw_item, dict):
                    raise FactArchiveIntegrityError(
                        "fact archive evidence item schema is invalid"
                    )
                item = cast(dict[str, object], raw_item)
                if set(item) != {"evidence_kind", "locator", "sha256", "outcome"}:
                    raise FactArchiveIntegrityError(
                        "fact archive evidence item fields are invalid"
                    )
                evidence_kind = item["evidence_kind"]
                locator = item["locator"]
                sha256 = item["sha256"]
                outcome_value = item["outcome"]
                if not all(
                    isinstance(value, str)
                    for value in (evidence_kind, locator, sha256, outcome_value)
                ):
                    raise FactArchiveIntegrityError(
                        "fact archive evidence values must be strings"
                    )
                evidence_kind = cast(str, evidence_kind)
                locator = cast(str, locator)
                sha256 = cast(str, sha256)
                outcome_value = cast(str, outcome_value)
                evidence.append(
                    EvidenceRef(
                        evidence_kind, locator, sha256, EvidenceOutcome(outcome_value)
                    )
                )
            raw_attestations = record.get("verification_attestations", [])
            if not isinstance(raw_attestations, list):
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
            for raw_attestation in cast(list[object], raw_attestations):
                if not isinstance(raw_attestation, dict):
                    raise FactArchiveIntegrityError(
                        "fact archive attestation item schema is invalid"
                    )
                attestation_data = cast(dict[str, object], raw_attestation)
                if set(attestation_data) != attestation_fields or any(
                    not isinstance(item, str) for item in attestation_data.values()
                ):
                    raise FactArchiveIntegrityError(
                        "fact archive attestation fields are invalid"
                    )
                attestations.append(
                    EvidenceAttestation(**cast(dict[str, str], attestation_data))
                )
            fact_id = record["fact_id"]
            goal_id = record["goal_id"]
            kind_value = record["kind"]
            bullet = record["bullet"]
            created_at = record["created_at"]
            if not all(
                isinstance(value, str)
                for value in (fact_id, goal_id, kind_value, bullet, created_at)
            ):
                raise FactArchiveIntegrityError("fact archive record strings are invalid")
            fact_id = cast(str, fact_id)
            goal_id = cast(str, goal_id)
            kind_value = cast(str, kind_value)
            bullet = cast(str, bullet)
            created_at = cast(str, created_at)
            for key in ("fact_id", "goal_id", "kind", "bullet", "created_at"):
                if not isinstance(record[key], str):
                    raise FactArchiveIntegrityError(
                        f"fact archive {key} must be a string"
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
            fact = Fact(
                goal_id=goal_id,
                kind=FactKind(kind_value),
                bullet=bullet,
                fact_id=fact_id,
                criterion_id=criterion_id,
                evidence=tuple(evidence),
                verification_attestations=tuple(attestations),
                source_event_id=source_event_id,
                created_at=created_at,
            )
        except (KeyError, TypeError, ValueError):
            # Enum and domain errors may retain caller-controlled archive values.
            validation_failed = True
        if validation_failed:
            raise FactArchiveIntegrityError(
                "fact archive record failed domain validation"
            )
        if fact is None:
            raise FactArchiveIntegrityError("fact archive record failed domain validation")
        return fact

    @classmethod
    def _decode_fact_archive(cls, row: sqlite3.Row) -> tuple[Fact, ...]:
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
        if not isinstance(parsed, list):
            raise FactArchiveIntegrityError("fact archive record count mismatch")
        records = cast(list[object], parsed)
        if len(records) != row["fact_count"]:
            raise FactArchiveIntegrityError("fact archive record count mismatch")
        facts = tuple(cls._fact_from_archive_record(item) for item in records)
        if len({fact.fact_id for fact in facts}) != len(facts):
            raise FactArchiveIntegrityError("fact archive contains duplicate IDs")
        if any(
            fact.goal_id != row["goal_id"]
            or fact.kind not in {FactKind.RESEARCH, FactKind.ADVICE}
            or fact.criterion_id is not None
            or fact.evidence
            for fact in facts
        ):
            raise FactArchiveIntegrityError("fact archive contains an ineligible fact")
        return facts

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

    def propose_fact_compaction(
        self, goal_id: str, project_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Preview the oldest eligible routine facts without mutating storage."""

        if not is_exact_int(max_facts) or not 1 <= max_facts <= MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError(
                f"max_facts must be between 1 and {MAX_FACT_COMPACTION_BATCH_FACTS}"
            )
        with self._lock:
            goal = self._connection.execute(
                "SELECT 1 FROM goals WHERE goal_id = ? AND project_id = ?",
                (goal_id, project_id),
            ).fetchone()
            if goal is None:
                raise NotFoundError(f"goal not found: {goal_id}")
            rows = self._connection.execute(
                """SELECT f.* FROM facts AS f JOIN goals AS g
                   ON g.goal_id = f.goal_id
                   WHERE f.goal_id = ? AND g.project_id = ?
                   ORDER BY f.created_at, f.fact_id""",
                (goal_id, project_id),
            ).fetchall()
            candidates = self._connection.execute(
                "SELECT fact_ids_json FROM sde_candidates WHERE goal_id = ?",
                (goal_id,),
            ).fetchall()
        protected_ids = {
            fact_id
            for candidate in candidates
            for fact_id in json.loads(candidate["fact_ids_json"])
        }
        eligible = tuple(
            fact
            for fact in (self._fact_from_row(row) for row in rows)
            if fact.kind in {FactKind.RESEARCH, FactKind.ADVICE}
            and fact.criterion_id is None
            and not fact.evidence
            and fact.fact_id not in protected_ids
        )[:max_facts]
        if not eligible:
            raise ConflictError("no eligible routine facts are available to archive")
        source = self._fact_archive_source(eligible)
        if len(source) > MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ConflictError("eligible facts exceed the bounded archive proposal size")
        compressed_size = len(zlib.compress(source, level=9))
        if compressed_size > MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ConflictError("compressed proposal exceeds the archive batch size")
        return FactCompactionProposal(
            compaction_id=new_id(),
            project_id=project_id,
            goal_id=goal_id,
            facts=eligible,
            source_sha256=hashlib.sha256(source).hexdigest(),
            source_bytes=len(source),
            estimated_compressed_bytes=compressed_size,
        )

    def approve_fact_compaction(
        self,
        compaction_id: str,
        goal_id: str,
        project_id: str,
        fact_ids: tuple[str, ...],
        source_sha256: str,
        reviewer_id: str,
        approval_reason: str,
    ) -> FactArchiveReceipt:
        """Atomically archive exact eligible facts and remove only their live rows."""

        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", compaction_id):
            raise ValueError("compaction_id must be a bounded opaque identifier")
        if not fact_ids or len(fact_ids) > MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError("fact_ids must contain 1-64 IDs")
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("fact_ids must be unique")
        if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA-256")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", reviewer_id):
            raise ValueError("reviewer_id must be a bounded opaque identifier")
        if not approval_reason.strip() or len(approval_reason) > 1000:
            raise ValueError("approval_reason must contain 1-1000 characters")
        if "\n" in approval_reason or "\r" in approval_reason:
            raise ValueError("approval_reason must be a single line")

        with self._transaction() as connection:
            existing_archive = connection.execute(
                "SELECT * FROM fact_archives WHERE compaction_id = ?",
                (compaction_id,),
            ).fetchone()
            if existing_archive is not None:
                receipt = self._fact_archive_receipt(existing_archive)
                if (
                    (
                        receipt.project_id,
                        receipt.goal_id,
                        receipt.fact_ids,
                        receipt.source_sha256,
                        receipt.reviewer_id,
                        receipt.approval_reason,
                    )
                    != (
                        project_id,
                        goal_id,
                        fact_ids,
                        source_sha256,
                        reviewer_id,
                        approval_reason,
                    )
                ):
                    raise ConflictError("compaction ID was reused for different approval")
                return receipt

            query = """SELECT f.* FROM facts AS f JOIN goals AS g
                       ON g.goal_id = f.goal_id
                       WHERE f.fact_id IN (SELECT value FROM json_each(?))
                         AND f.goal_id = ? AND g.project_id = ?"""
            rows = connection.execute(
                query,
                (json.dumps(fact_ids), goal_id, project_id),
            ).fetchall()
            fact_by_id = {row["fact_id"]: self._fact_from_row(row) for row in rows}
            if set(fact_by_id) != set(fact_ids):
                raise ConflictError("proposed facts changed or are no longer active")
            facts = tuple(
                sorted(fact_by_id.values(), key=lambda fact: (fact.created_at, fact.fact_id))
            )
            if tuple(fact.fact_id for fact in facts) != fact_ids:
                raise ConflictError("fact IDs do not match the canonical proposal order")
            if any(
                fact.kind not in {FactKind.RESEARCH, FactKind.ADVICE}
                or fact.criterion_id is not None
                or fact.evidence
                for fact in facts
            ):
                raise ConflictError("approval includes a non-routine or evidence-bearing fact")
            candidate_rows = connection.execute(
                "SELECT fact_ids_json FROM sde_candidates WHERE goal_id = ?",
                (goal_id,),
            ).fetchall()
            protected_ids = {
                item
                for candidate in candidate_rows
                for item in json.loads(candidate["fact_ids_json"])
            }
            if protected_ids.intersection(fact_ids):
                raise ConflictError("SDE-supported facts cannot be compacted")
            source = self._fact_archive_source(facts)
            actual_source_sha256 = hashlib.sha256(source).hexdigest()
            if actual_source_sha256 != source_sha256:
                raise ConflictError("fact source changed since the proposal was reviewed")
            if len(source) > MAX_FACT_COMPACTION_SOURCE_BYTES:
                raise ConflictError("fact archive exceeds its source size limit")
            compressed = zlib.compress(source, level=9)
            archive_sha256 = hashlib.sha256(compressed).hexdigest()
            created_at = utc_now()
            archive_usage = connection.execute(
                """SELECT COALESCE(SUM(
                         length(CAST(compaction_id AS BLOB)) +
                         length(CAST(schema_version AS TEXT)) +
                         length(CAST(goal_id AS BLOB)) +
                         length(CAST(source_sha256 AS BLOB)) +
                         length(CAST(archive_sha256 AS BLOB)) +
                         length(CAST(source_bytes AS TEXT)) +
                         length(CAST(compressed_bytes AS TEXT)) +
                         length(CAST(fact_count AS TEXT)) +
                         length(CAST(reviewer_id AS BLOB)) +
                         length(CAST(approval_reason AS BLOB)) +
                         length(CAST(created_at AS BLOB)) + compressed_bytes
                       ), 0) + COALESCE((
                         SELECT SUM(length(CAST(fact_id AS BLOB)) +
                                    length(CAST(compaction_id AS BLOB)) +
                                    length(CAST(project_id AS BLOB)) +
                                    length(CAST(goal_id AS BLOB)) +
                                    length(CAST(dedupe_key AS BLOB)) +
                                    length(CAST(created_at AS BLOB)))
                         FROM fact_archive_items WHERE project_id = ?
                       ), 0) AS bytes
                   FROM fact_archives WHERE project_id = ?""",
                (project_id, project_id),
            ).fetchone()
            new_archive_bytes = len(compressed) + sum(
                len(value.encode("utf-8"))
                for value in (
                    compaction_id,
                    project_id,
                    goal_id,
                    actual_source_sha256,
                    archive_sha256,
                    str(len(source)),
                    str(len(compressed)),
                    str(len(facts)),
                    "1",
                    reviewer_id,
                    approval_reason.strip(),
                    created_at,
                )
            )
            new_archive_bytes += sum(
                len(value.encode("utf-8"))
                for fact in facts
                for value in (
                    fact.fact_id,
                    compaction_id,
                    project_id,
                    goal_id,
                    self._fact_dedupe_key(fact),
                    fact.created_at,
                )
            )
            if archive_usage["bytes"] + new_archive_bytes > MAX_FACT_ARCHIVE_BYTES_PER_PROJECT:
                raise FactCapacityError("project fact archive capacity reached")
            connection.execute(
                """INSERT INTO fact_archives
                   (compaction_id, schema_version, project_id, goal_id, source_sha256,
                    archive_sha256,
                    source_bytes, compressed_bytes, fact_count, payload_zlib,
                    reviewer_id, approval_reason, created_at)
                   VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    compaction_id,
                    project_id,
                    goal_id,
                    actual_source_sha256,
                    archive_sha256,
                    len(source),
                    len(compressed),
                    len(facts),
                    compressed,
                    reviewer_id,
                    approval_reason.strip(),
                    created_at,
                ),
            )
            for fact in facts:
                connection.execute(
                    """INSERT INTO fact_archive_items
                       (fact_id, compaction_id, project_id, goal_id, dedupe_key, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        fact.fact_id,
                        compaction_id,
                        project_id,
                        goal_id,
                        self._fact_dedupe_key(fact),
                        fact.created_at,
                    ),
                )
            connection.executemany(
                "DELETE FROM facts WHERE fact_id = ?",
                ((fact_id,) for fact_id in fact_ids),
            )
            row = connection.execute(
                "SELECT * FROM fact_archives WHERE compaction_id = ?",
                (compaction_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("inserted fact archive could not be read back")
            return self._fact_archive_receipt(row)

    def list_fact_archive_receipts(
        self,
        goal_id: str,
        project_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read bounded archive receipts and verify every compressed payload."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if not is_exact_int(limit) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock:
            rows = self._connection.execute(
                """SELECT * FROM fact_archives
                   WHERE goal_id = ? AND project_id = ?
                   ORDER BY created_at, compaction_id LIMIT ? OFFSET ?""",
                (goal_id, project_id, limit, offset),
            ).fetchall()
        return tuple(self._fact_archive_receipt(row) for row in rows)

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

    @staticmethod
    def _candidate_dedupe_key(candidate: SDECandidate) -> str:
        """Hash the goal, materiality, and selected fact set for idempotency."""

        payload = {
            "goal_id": candidate.goal_id,
            "materiality": candidate.materiality.value,
            "fact_ids": sorted(candidate.fact_ids),
        }
        return hashlib.sha256(_json_dump(payload).encode("utf-8")).hexdigest()

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

    def list_sde_candidate_page(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
        status: SDEStatus | None = None,
    ) -> tuple[int, tuple[SDECandidate, ...]]:
        """Return one bounded page of a goal's SDE candidates and exact count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT s.candidate_id, s.created_at FROM sde_candidates AS s
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ?
                       AND (? IS NULL OR s.status = ?)
                   ), page AS (
                     SELECT candidate_id FROM selected
                     ORDER BY created_at, candidate_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.candidate_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    goal_id,
                    project_id,
                    status.value if status is not None else None,
                    status.value if status is not None else None,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["candidate_id"] is not None)
        return total, tuple(
            self.get_sde_candidate(row["candidate_id"], project_id)
            for row in page_rows
        )

    def pending_sde_candidates(
        self, project_id: str, limit: int = 100
    ) -> tuple[SDECandidate, ...]:
        """List a bounded, project-scoped review queue in creation order."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._lock:
            rows = self._connection.execute(
                """SELECT s.candidate_id FROM sde_candidates AS s
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ? AND s.status = ?
                   ORDER BY s.created_at, s.candidate_id LIMIT ?""",
                (project_id, SDEStatus.PENDING_REVIEW.value, limit),
            ).fetchall()
        return tuple(
            self.get_sde_candidate(row["candidate_id"], project_id) for row in rows
        )

    def project_operational_counts(self, project_id: str) -> ProjectOperationalCounts:
        """Count review and purge work exactly with bounded aggregate queries."""

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
                        AND p.status != ?) AS pending_artifacts""",
                (
                    project_id,
                    SDEStatus.PENDING_REVIEW.value,
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
        )

    def project_activity_status(self, project_id: str) -> ProjectActivitySnapshot:
        """Read bounded project activity totals without exposing event contents."""

        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("project activity snapshot cannot nest a transaction")
            self._connection.execute("BEGIN")
            try:
                event_rows = self._connection.execute(
                    "SELECT status, COUNT(*) AS count FROM event_inbox "
                    "WHERE project_id = ? GROUP BY status",
                    (project_id,),
                ).fetchall()
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
                fact_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM facts AS f JOIN goals AS g "
                        "ON g.goal_id = f.goal_id WHERE g.project_id = ?",
                        (project_id,),
                    ).fetchone()[0]
                )
                sde_rows = self._connection.execute(
                    "SELECT s.status, COUNT(*) AS count FROM sde_candidates AS s "
                    "JOIN goals AS g ON g.goal_id = s.goal_id "
                    "WHERE g.project_id = ? GROUP BY s.status",
                    (project_id,),
                ).fetchall()
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()

        event_counts = {row["status"]: int(row["count"]) for row in event_rows}
        sde_counts = {row["status"]: int(row["count"]) for row in sde_rows}
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
            fact_count=fact_count,
            sde_candidate_count=pending_sde + approved_sde + rejected_sde,
            pending_sde_count=pending_sde,
            approved_sde_count=approved_sde,
            rejected_sde_count=rejected_sde,
            events_observed=(processed + received + failed + quarantined) > 0,
        )

    def project_health_inputs(
        self, project_id: str
    ) -> tuple[EventQueueStatus, ProjectOperationalCounts, ProjectStorageUsage]:
        """Read health aggregates from one SQLite snapshot transaction."""

        with self._lock:
            if self._connection.in_transaction:
                raise RuntimeError("project health snapshot cannot nest a transaction")
            self._connection.execute("BEGIN")
            try:
                queue = self.event_queue_status(project_id)
                counts = self.project_operational_counts(project_id)
                usage = self.project_storage_usage(project_id)
            except BaseException:
                self._connection.rollback()
                raise
            self._connection.commit()
        return queue, counts, usage

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
                    "SELECT path, sha256, retention_hold FROM purge_targets WHERE receipt_id = ? "
                    "ORDER BY path",
                    (existing["receipt_id"],),
                ).fetchall()
                requested_targets = sorted(
                    (
                        item.path,
                        item.sha256,
                        item.retention_hold.value if item.retention_hold else None,
                    )
                    for item in receipt.artifacts
                )
                saved_target_values = [
                    (item["path"], item["sha256"], item["retention_hold"])
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
                            hold_created_at, hold_created_by)
                           VALUES (?, ?, ?, ?, 0, NULL, ?, NULL, NULL, ?, ?, ?)""",
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

    def get_receipt(
        self, receipt_id: str, project_id: str | None = None
    ) -> AuditReceipt:
        """Load one review and purge receipt, optionally project-scoped."""

        with self._lock:
            if project_id is None:
                row = self._connection.execute(
                    "SELECT * FROM audit_receipts WHERE receipt_id = ?",
                    (receipt_id,),
                ).fetchone()
            else:
                row = self._connection.execute(
                    """SELECT r.* FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.receipt_id = ? AND g.project_id = ?""",
                    (receipt_id, project_id),
                ).fetchone()
            if row is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            targets = self._connection.execute(
                "SELECT path, sha256, retention_hold FROM purge_targets WHERE receipt_id = ? "
                "ORDER BY path",
                (receipt_id,),
            ).fetchall()
        artifacts = tuple(
            ArtifactRef(
                item["path"],
                item["sha256"],
                RetentionHoldKind(item["retention_hold"]) if item["retention_hold"] else None,
            )
            for item in targets
        )
        return AuditReceipt(
            candidate_id=row["candidate_id"],
            decision=ReviewDecision(row["decision"]),
            facts_sha256=row["facts_sha256"],
            artifacts=artifacts,
            artifact_inventory_complete=bool(row["artifact_inventory_complete"]),
            reviewer_id=row["reviewer_id"],
            review_rationale=row["review_rationale"],
            canonical_persisted=bool(row["canonical_persisted"]),
            canonical_target=row["canonical_target"],
            canonical_sha256=row["canonical_sha256"],
            canonical_persisted_at=row["canonical_persisted_at"],
            receipt_id=row["receipt_id"],
            purge_status=PurgeStatus(row["purge_status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
        paths = [item.path for item in artifacts]
        if len(paths) != len(set(paths)):
            raise ConflictError("artifact inventory contains duplicate paths")
        requested = sorted(
            (
                item.path,
                item.sha256,
                item.retention_hold.value if item.retention_hold else None,
            )
            for item in artifacts
        )
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
                "hold_created_at, hold_created_by FROM purge_targets "
                "WHERE receipt_id = ? ORDER BY path",
                (receipt_id,),
            ).fetchall()
            existing_hold_audit = {
                (item["path"], item["sha256"], item["retention_hold"]): (
                    item["hold_created_at"],
                    item["hold_created_by"],
                )
                for item in existing_targets
                if item["retention_hold"] is not None
            }
            saved = [
                (item["path"], item["sha256"], item["retention_hold"])
                for item in existing_targets
            ]
            if bool(row["artifact_inventory_complete"]):
                if requested != saved:
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
                inventory_created_at = utc_now()
                for artifact in artifacts:
                    hold_kind = (
                        artifact.retention_hold.value
                        if artifact.retention_hold
                        else None
                    )
                    prior_hold_audit = existing_hold_audit.get(
                        (artifact.path, artifact.sha256, hold_kind)
                    )
                    hold_created_at = (
                        prior_hold_audit[0]
                        if prior_hold_audit is not None
                        else inventory_created_at if hold_kind else None
                    )
                    hold_actor = (
                        prior_hold_audit[1]
                        if prior_hold_audit is not None
                        else hold_created_by if hold_kind else None
                    )
                    connection.execute(
                        """INSERT INTO purge_targets
                           (receipt_id, path, sha256, status, attempts, error,
                            created_at, last_attempt_at, next_attempt_at, retention_hold,
                            hold_created_at, hold_created_by)
                           VALUES (?, ?, ?, ?, 0, NULL, ?, NULL, NULL, ?, ?, ?)""",
                        (
                            receipt_id,
                            artifact.path,
                            artifact.sha256,
                            (
                                ArtifactStatus.HELD
                                if artifact.retention_hold
                                else ArtifactStatus.PENDING
                            ).value,
                            inventory_created_at,
                            hold_kind,
                            hold_created_at,
                            hold_actor,
                        ),
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
                """SELECT p.status, p.retention_hold, p.attempts,
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
                """UPDATE purge_targets SET status = ?, error = NULL,
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

    def get_purge_targets(
        self,
        receipt_id: str,
        pending_only: bool = False,
        project_id: str | None = None,
        due_only: bool = False,
    ) -> tuple[tuple[ArtifactRef, ArtifactStatus, int, str | None], ...]:
        """Read the receipt's artifact states, optionally excluding completed purges."""

        if due_only and not pending_only:
            raise ValueError("due_only requires pending_only")
        with self._lock:
            if project_id is not None:
                scoped = self._connection.execute(
                    """SELECT 1 FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.receipt_id = ? AND g.project_id = ?""",
                    (receipt_id, project_id),
                ).fetchone()
                if scoped is None:
                    raise NotFoundError(f"audit receipt not found: {receipt_id}")
            if due_only:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? "
                    "AND status IN (?, ?) "
                    "AND (retention_hold IS NULL OR hold_released_at IS NOT NULL) "
                    "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
                    "ORDER BY path",
                    (
                        receipt_id,
                        ArtifactStatus.PENDING.value,
                        ArtifactStatus.FAILED.value,
                        utc_now(),
                    ),
                ).fetchall()
            elif pending_only:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? "
                    "AND status IN (?, ?) "
                    "AND (retention_hold IS NULL OR hold_released_at IS NOT NULL) "
                    "ORDER BY path",
                    (receipt_id, ArtifactStatus.PENDING.value, ArtifactStatus.FAILED.value),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM purge_targets WHERE receipt_id = ? ORDER BY path",
                    (receipt_id,),
                ).fetchall()
        return tuple(
            (
                ArtifactRef(
                    row["path"],
                    row["sha256"],
                    RetentionHoldKind(row["retention_hold"]) if row["retention_hold"] else None,
                ),
                ArtifactStatus(row["status"]),
                row["attempts"],
                row["error"],
            )
            for row in rows
        )

    def get_purge_target_records(
        self,
        receipt_id: str,
        project_id: str,
    ) -> tuple[PurgeTargetRecord, ...]:
        """Read timestamps and retry state for one scoped receipt's artifacts."""

        with self._lock:
            scoped = self._connection.execute(
                """SELECT 1 FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone()
            if scoped is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            rows = self._connection.execute(
                "SELECT * FROM purge_targets WHERE receipt_id = ? ORDER BY path",
                (receipt_id,),
            ).fetchall()
        return tuple(
            PurgeTargetRecord(
                artifact=ArtifactRef(
                    row["path"],
                    row["sha256"],
                    RetentionHoldKind(row["retention_hold"]) if row["retention_hold"] else None,
                ),
                status=ArtifactStatus(row["status"]),
                attempts=row["attempts"],
                error=row["error"],
                created_at=row["created_at"],
                last_attempt_at=row["last_attempt_at"],
                next_attempt_at=row["next_attempt_at"],
                hold_created_at=row["hold_created_at"],
                hold_created_by=row["hold_created_by"],
                hold_released_at=row["hold_released_at"],
                hold_released_by=row["hold_released_by"],
                hold_release_rationale=row["hold_release_rationale"],
            )
            for row in rows
        )

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
                   last_attempt_at = ?, next_attempt_at = NULL
                   WHERE receipt_id = ? AND path = ? AND status IN (?, ?)
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

    def record_purge_result(
        self,
        receipt_id: str,
        path: str,
        status: ArtifactStatus,
        error: str | None,
        project_id: str | None = None,
    ) -> AuditReceipt:
        """Persist one idempotent artifact purge result and refresh receipt state."""

        if status not in (ArtifactStatus.FAILED, ArtifactStatus.PURGED):
            raise ValueError("a purge result must be failed or purged")
        if status is ArtifactStatus.FAILED:
            allowed_errors = {
                code.value
                for code in PurgeFailureCode
                if code is not PurgeFailureCode.LEGACY_FAILURE_DETAIL_REDACTED
            }
            if error not in allowed_errors:
                raise ValueError("purge failure requires a known content-free error code")
        elif error is not None:
            raise ValueError("successful purge results cannot include an error")

        with self._transaction() as connection:
            if project_id is not None and connection.execute(
                """SELECT 1 FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.receipt_id = ? AND g.project_id = ?""",
                (receipt_id, project_id),
            ).fetchone() is None:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
            target = connection.execute(
                "SELECT attempts FROM purge_targets WHERE receipt_id = ? AND path = ?",
                (receipt_id, path),
            ).fetchone()
            if target is None:
                raise NotFoundError("purge target not found in receipt")
            held = connection.execute(
                "SELECT retention_hold, hold_released_at FROM purge_targets "
                "WHERE receipt_id = ? AND path = ?",
                (receipt_id, path),
            ).fetchone()
            if held is None or (
                held["retention_hold"] is not None
                and held["hold_released_at"] is None
            ):
                raise ConflictError("held artifacts cannot record a purge result")
            next_attempt_at = None
            if status is ArtifactStatus.FAILED:
                delay_seconds = min(
                    PURGE_RETRY_BASE_SECONDS
                    * (2 ** min(max(int(target["attempts"]) - 1, 0), 16)),
                    PURGE_RETRY_MAX_SECONDS,
                )
                next_attempt_at = (
                    datetime.now(UTC) + timedelta(seconds=delay_seconds)
                ).isoformat(timespec="microseconds")
            cursor = connection.execute(
                """UPDATE purge_targets SET status = ?, error = ?, next_attempt_at = ?
                   WHERE receipt_id = ? AND path = ?""",
                (status.value, error, next_attempt_at, receipt_id, path),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("purge target not found in receipt")
            attempted_at = utc_now()
            unfinished = connection.execute(
                "SELECT COUNT(*) FROM purge_targets WHERE receipt_id = ? AND status != ?",
                (receipt_id, ArtifactStatus.PURGED.value),
            ).fetchone()[0]
            receipt_status = (
                PurgeStatus.PURGE_PENDING if unfinished else PurgeStatus.COMPLETE
            )
            cursor = connection.execute(
                "UPDATE audit_receipts SET purge_status = ?, updated_at = ? "
                "WHERE receipt_id = ?",
                (receipt_status.value, attempted_at, receipt_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"audit receipt not found: {receipt_id}")
        return self.get_receipt(receipt_id, project_id)

    def pending_receipts(
        self, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List receipts whose artifact cleanup remains incomplete."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT receipt_id FROM audit_receipts WHERE purge_status = ? "
                    "ORDER BY created_at, receipt_id",
                    (PurgeStatus.PURGE_PENDING.value,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE r.purge_status = ? AND g.project_id = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (PurgeStatus.PURGE_PENDING.value, project_id),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def due_pending_purge_receipts(
        self, project_id: str, limit: int = 100
    ) -> tuple[AuditReceipt, ...]:
        """Return bounded, authorized-project receipts with at least one due target."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        with self._lock:
            rows = self._connection.execute(
                """SELECT r.receipt_id FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE r.purge_status = ? AND r.artifact_inventory_complete = 1
                     AND r.canonical_persisted = 1 AND g.project_id = ?
                     AND EXISTS (
                       SELECT 1 FROM purge_targets AS p
                       WHERE p.receipt_id = r.receipt_id
                         AND p.status IN (?, ?)
                         AND (p.retention_hold IS NULL OR p.hold_released_at IS NOT NULL)
                         AND (p.next_attempt_at IS NULL OR p.next_attempt_at <= ?)
                     )
                   ORDER BY r.created_at, r.receipt_id LIMIT ?""",
                (
                    PurgeStatus.PURGE_PENDING.value,
                    project_id,
                    ArtifactStatus.PENDING.value,
                    ArtifactStatus.FAILED.value,
                    now,
                    limit,
                ),
            ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def pending_receipts_for_goal(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List incomplete purge receipts for one goal and optional project."""

        with self._lock:
            if project_id is not None:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.goal_id = ? AND r.purge_status = ?
                       AND g.project_id = ? ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, PurgeStatus.PURGE_PENDING.value, project_id),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       WHERE s.goal_id = ? AND r.purge_status = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, PurgeStatus.PURGE_PENDING.value),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

    def receipt_purge_status_counts(
        self, goal_id: str, project_id: str
    ) -> dict[str, int]:
        """Count receipt purge states without loading the audit receipt bodies."""

        with self._lock:
            rows = self._connection.execute(
                """SELECT r.purge_status, COUNT(*) AS count FROM audit_receipts AS r
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE s.goal_id = ? AND g.project_id = ?
                   GROUP BY r.purge_status""",
                (goal_id, project_id),
            ).fetchall()
        return {str(row["purge_status"]): int(row["count"]) for row in rows}

    def receipt_page_for_goal(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, tuple[AuditReceipt, ...]]:
        """Return one bounded page of review receipts and exact total count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT r.receipt_id, r.created_at FROM audit_receipts AS r
                     JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ?
                   ), page AS (
                     SELECT receipt_id FROM selected
                     ORDER BY created_at, receipt_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.receipt_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (goal_id, project_id, limit, offset),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["receipt_id"] is not None)
        return total, tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in page_rows
        )

    def pending_receipt_page_for_goal(
        self,
        goal_id: str,
        project_id: str,
        offset: int,
        limit: int,
    ) -> tuple[int, tuple[AuditReceipt, ...]]:
        """Return one bounded page of purge-pending receipts and exact count."""

        if not is_exact_int(offset) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not is_exact_int(limit) or not 1 <= limit <= MAX_GOAL_LIST_PAGE:
            raise ValueError(f"limit must be between 1 and {MAX_GOAL_LIST_PAGE}")
        with self._lock:
            rows = self._connection.execute(
                """WITH selected AS (
                     SELECT r.receipt_id, r.created_at FROM audit_receipts AS r
                     JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                     JOIN goals AS g ON g.goal_id = s.goal_id
                     WHERE s.goal_id = ? AND g.project_id = ? AND r.purge_status = ?
                   ), page AS (
                     SELECT receipt_id FROM selected
                     ORDER BY created_at, receipt_id LIMIT ? OFFSET ?
                   )
                   SELECT (SELECT COUNT(*) FROM selected) AS total,
                          page.receipt_id
                   FROM (SELECT 1) AS singleton LEFT JOIN page ON 1 = 1""",
                (
                    goal_id,
                    project_id,
                    PurgeStatus.PURGE_PENDING.value,
                    limit,
                    offset,
                ),
            ).fetchall()
        total = int(rows[0]["total"])
        page_rows = tuple(row for row in rows if row["receipt_id"] is not None)
        return total, tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in page_rows
        )

    def receipts_for_goal(
        self, goal_id: str, project_id: str | None = None
    ) -> tuple[AuditReceipt, ...]:
        """List all review receipts for one goal in creation order."""

        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       WHERE s.goal_id = ? ORDER BY r.created_at, r.receipt_id""",
                    (goal_id,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT r.receipt_id FROM audit_receipts AS r
                       JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                       JOIN goals AS g ON g.goal_id = s.goal_id
                       WHERE s.goal_id = ? AND g.project_id = ?
                       ORDER BY r.created_at, r.receipt_id""",
                    (goal_id, project_id),
                ).fetchall()
        return tuple(
            self.get_receipt(row["receipt_id"], project_id) for row in rows
        )

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

    @staticmethod
    def _event_inbox_usage(connection: sqlite3.Connection) -> tuple[int, int]:
        """Measure retained event-row content across every project in the DB."""

        row = connection.execute(
            """SELECT COUNT(*) AS count, COALESCE(SUM(
                   length(CAST(project_id AS BLOB)) +
                   length(CAST(event_id AS BLOB)) +
                   length(CAST(event_type AS BLOB)) +
                   length(CAST(payload_sha256 AS BLOB)) +
                   COALESCE(length(CAST(idempotency_sha256 AS BLOB)), 0) +
                   length(CAST(payload_bytes AS TEXT)) +
                   COALESCE(length(CAST(payload_json AS BLOB)), 0) +
                   length(CAST(status AS BLOB)) +
                   length(CAST(received_at AS BLOB)) +
                   length(CAST(attempts AS TEXT)) +
                   length(CAST(source_id AS BLOB)) +
                   COALESCE(length(CAST(source_sequence AS TEXT)), 0) +
                   COALESCE(length(CAST(processed_at AS BLOB)), 0) +
                   COALESCE(length(CAST(last_error AS BLOB)), 0) +
                   COALESCE(length(CAST(next_attempt_at AS BLOB)), 0) +
                   COALESCE(length(CAST(lease_owner AS BLOB)), 0) +
                   COALESCE(length(CAST(lease_expires_at AS BLOB)), 0)
                 ), 0) AS bytes FROM event_inbox"""
        ).fetchone()
        audit = connection.execute(
            """SELECT COALESCE(SUM(
                   length(CAST(project_id AS BLOB)) +
                   length(CAST(event_id AS BLOB)) +
                   length(CAST(actor_id AS BLOB)) +
                   length(CAST(created_at AS BLOB))
                 ), 0) AS bytes FROM event_retry_audit"""
        ).fetchone()
        return int(row["count"]), int(row["bytes"]) + int(audit["bytes"])

    def global_event_inbox_usage(self) -> GlobalEventInboxUsage:
        """Return aggregate capacity only; never reveal other project IDs."""

        with self._lock:
            count, retained_bytes = self._event_inbox_usage(self._connection)
        return self._global_event_inbox_capacity(count, retained_bytes)

    @staticmethod
    def _global_event_inbox_capacity(
        count: int, retained_bytes: int
    ) -> GlobalEventInboxUsage:
        can_accept = (
            count < MAX_EVENT_RECEIPTS_GLOBAL
            and retained_bytes + EVENT_FAILURE_METADATA_RESERVE_BYTES
            <= MAX_EVENT_RECEIPT_BYTES_GLOBAL
        )
        gate = None if can_accept else (
            "Global event inbox capacity reached; new events are rejected without "
            "deleting receipts. An approved retention/recovery action is required."
        )
        return GlobalEventInboxUsage(
            receipt_count=count,
            retained_record_bytes=retained_bytes,
            receipt_count_limit=MAX_EVENT_RECEIPTS_GLOBAL,
            retained_record_bytes_limit=MAX_EVENT_RECEIPT_BYTES_GLOBAL,
            can_accept_new_event=can_accept,
            open_gate=gate,
        )

    def ingest_event(self, event: EventEnvelope) -> tuple[EventInboxReceipt, bool]:
        """Durably accept one event; repeated identical IDs are idempotent."""

        payload_json = event.to_json()
        payload_digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        payload_bytes = len(payload_json.encode("utf-8"))
        received_at = utc_now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (event.project_id, event.event_id),
            ).fetchone()
            if existing is not None:
                idempotency_digest = event.idempotency_sha256
                stored_idempotency_digest = existing["idempotency_sha256"]
                identity_changed = (
                    existing["payload_sha256"] != payload_digest
                    if stored_idempotency_digest is None
                    else stored_idempotency_digest != idempotency_digest
                )
                if identity_changed:
                    raise ConflictError(
                        "event ID was already used with a different payload"
                    )
                return self._event_receipt(existing), False
            retained_count, retained_bytes = self._event_inbox_usage(connection)
            new_row_bytes = sum(
                len(value.encode("utf-8"))
                for value in (
                    event.project_id,
                    event.event_id,
                    event.event_kind.value,
                    payload_digest,
                    event.idempotency_sha256,
                    str(payload_bytes),
                    payload_json,
                    EventInboxStatus.RECEIVED.value,
                    received_at,
                    event.source_id,
                    str(event.source_sequence) if event.source_sequence is not None else "",
                )
            )
            if (
                retained_count + 1 > MAX_EVENT_RECEIPTS_GLOBAL
                or retained_bytes
                + new_row_bytes
                + EVENT_FAILURE_METADATA_RESERVE_BYTES
                > MAX_EVENT_RECEIPT_BYTES_GLOBAL
            ):
                raise EventInboxCapacityError(
                    "global event inbox capacity reached; new events are rejected "
                    "without deleting receipts"
                )
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    idempotency_sha256, payload_json, status, received_at, processed_at,
                    last_error, source_id, source_sequence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
                (
                    event.project_id,
                    event.event_id,
                    event.event_kind.value,
                    payload_digest,
                    payload_bytes,
                    event.idempotency_sha256,
                    payload_json,
                    EventInboxStatus.RECEIVED.value,
                    received_at,
                    event.source_id,
                    event.source_sequence,
                ),
            )
            row = connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (event.project_id, event.event_id),
            ).fetchone()
        return self._event_receipt(row), True

    def advance_source_sequence(self, event: EventEnvelope) -> None:
        """Advance one project's source cursor in the caller's event transaction."""

        if event.source_sequence is None:
            return
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT last_sequence FROM event_cursors "
                "WHERE project_id = ? AND source_id = ?",
                (event.project_id, event.source_id),
            ).fetchone()
            previous = row["last_sequence"] if row is not None else 0
            expected = previous + 1
            if event.source_sequence != expected:
                raise EventOrderError(
                    f"expected source sequence {expected}, received {event.source_sequence}"
                )
            connection.execute(
                """INSERT INTO event_cursors
                   (project_id, source_id, last_sequence, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(project_id, source_id) DO UPDATE SET
                   last_sequence = excluded.last_sequence,
                   updated_at = excluded.updated_at""",
                (
                    event.project_id,
                    event.source_id,
                    event.source_sequence,
                    utc_now(),
                ),
            )

    @staticmethod
    def _event_receipt(row: sqlite3.Row) -> EventInboxReceipt:
        return EventInboxReceipt(
            project_id=row["project_id"],
            event_id=row["event_id"],
            payload_sha256=row["payload_sha256"],
            status=EventInboxStatus(row["status"]),
            received_at=row["received_at"],
            processed_at=row["processed_at"],
            last_error_code=row["last_error"],
            attempts=row["attempts"],
            next_attempt_at=row["next_attempt_at"],
            disposition=(
                EventDisposition(row["disposition"])
                if row["disposition"] is not None else None
            ),
        )

    def pending_events(
        self, *, project_id: str | None = None, limit: int = 100
    ) -> tuple[EventEnvelope, ...]:
        """Read bounded received/failed payloads for an in-process consumer."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        now = utc_now()
        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    """SELECT e.payload_json FROM event_inbox AS e
                       WHERE e.status IN (?, ?) AND e.payload_json IS NOT NULL
                         AND (e.status = ? OR e.next_attempt_at IS NULL
                              OR e.next_attempt_at <= ?)
                         AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                              OR e.lease_expires_at <= ?)
                         AND (e.source_sequence IS NULL OR e.source_sequence =
                           COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                     WHERE c.project_id = e.project_id
                                       AND c.source_id = e.source_id), 0) + 1)
                       ORDER BY e.received_at, e.event_id LIMIT ?""",
                    (
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        EventInboxStatus.RECEIVED.value,
                        now,
                        now,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """SELECT e.payload_json FROM event_inbox AS e
                       WHERE e.project_id = ? AND e.status IN (?, ?)
                         AND e.payload_json IS NOT NULL
                         AND (e.status = ? OR e.next_attempt_at IS NULL
                              OR e.next_attempt_at <= ?)
                         AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                              OR e.lease_expires_at <= ?)
                         AND (e.source_sequence IS NULL OR e.source_sequence =
                           COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                     WHERE c.project_id = e.project_id
                                       AND c.source_id = e.source_id), 0) + 1)
                       ORDER BY e.received_at, e.event_id LIMIT ?""",
                    (
                        project_id,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        EventInboxStatus.RECEIVED.value,
                        now,
                        now,
                        limit,
                    ),
                ).fetchall()
        return tuple(
            EventEnvelope.from_json(row["payload_json"])
            for row in rows
            if row["payload_json"] is not None
        )

    def claim_pending_events(
        self,
        lease_owner: str,
        *,
        limit: int = 100,
        lease_seconds: int = 300,
        project_ids: tuple[str, ...] | None = None,
    ) -> tuple[EventEnvelope, ...]:
        """Atomically lease due events, optionally within fixed project bindings."""

        if not _ERROR_CODE_RE.fullmatch(lease_owner) or len(lease_owner) > 128:
            raise ValueError("lease_owner must be a bounded safe identifier")
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if not is_exact_int(lease_seconds) or not 1 <= lease_seconds <= 86_400:
            raise ValueError("lease_seconds must be between 1 and 86400")
        if project_ids is not None:
            # Reject tuple subclasses so project bindings use an inert exact container.
            # pylint: disable-next=unidiomatic-typecheck
            if type(project_ids) is not tuple or len(project_ids) > 128:
                raise ValueError("project_ids must be a tuple of at most 128 bindings")
            for project_id in project_ids:
                self._validate_access_identity(project_id, "project_id")
            if len(set(project_ids)) != len(project_ids):
                raise ValueError("project_ids must not contain duplicates")
            if not project_ids:
                return ()
        now = datetime.now(UTC)
        now_text = now.isoformat(timespec="microseconds")
        expires_text = (now + timedelta(seconds=lease_seconds)).isoformat(
            timespec="microseconds"
        )
        with self._transaction() as connection:
            connection.execute(
                "CREATE TEMP TABLE IF NOT EXISTS router_project_bindings "
                "(project_id TEXT PRIMARY KEY) WITHOUT ROWID"
            )
            connection.execute("DELETE FROM temp.router_project_bindings")
            if project_ids is not None:
                connection.executemany(
                    "INSERT INTO temp.router_project_bindings(project_id) VALUES (?)",
                    ((project_id,) for project_id in project_ids),
                )
            rows = connection.execute(
                """SELECT e.project_id, e.event_id, e.payload_json
                   FROM event_inbox AS e
                   WHERE e.status IN (?, ?) AND e.payload_json IS NOT NULL
                     AND (e.status = ? OR e.next_attempt_at IS NULL
                          OR e.next_attempt_at <= ?)
                     AND (e.lease_owner IS NULL OR e.lease_expires_at IS NULL
                          OR e.lease_expires_at <= ?)
                     AND (e.source_sequence IS NULL OR e.source_sequence =
                       COALESCE((SELECT c.last_sequence FROM event_cursors AS c
                                 WHERE c.project_id = e.project_id
                                   AND c.source_id = e.source_id), 0) + 1)
                     AND (? = 1 OR e.project_id IN
                       (SELECT project_id FROM temp.router_project_bindings))
                   ORDER BY e.received_at, e.event_id LIMIT ?""",
                (
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                    EventInboxStatus.RECEIVED.value,
                    now_text,
                    now_text,
                    1 if project_ids is None else 0,
                    limit,
                ),
            ).fetchall()
            claimed_payloads: list[str] = []
            for row in rows:
                cursor = connection.execute(
                    """UPDATE event_inbox SET lease_owner = ?, lease_expires_at = ?
                       WHERE project_id = ? AND event_id = ?
                         AND (lease_owner IS NULL OR lease_expires_at IS NULL
                              OR lease_expires_at <= ?)""",
                    (
                        lease_owner,
                        expires_text,
                        row["project_id"],
                        row["event_id"],
                        now_text,
                    ),
                )
                if cursor.rowcount == 1 and row["payload_json"] is not None:
                    claimed_payloads.append(row["payload_json"])
            connection.execute("DELETE FROM temp.router_project_bindings")
        return tuple(EventEnvelope.from_json(payload) for payload in claimed_payloads)

    def assert_event_claim(
        self,
        project_id: str,
        event_id: str,
        lease_owner: str | None,
    ) -> None:
        """Require matching ownership when a live worker claim exists."""

        now = utc_now()
        with self._lock:
            row = self._connection.execute(
                "SELECT lease_owner, lease_expires_at FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"event not found: {project_id}/{event_id}")
        saved_owner = row["lease_owner"]
        expires_at = row["lease_expires_at"]
        is_live = saved_owner is not None and expires_at is not None and expires_at > now
        if lease_owner is not None:
            if saved_owner != lease_owner or not is_live:
                raise EventClaimError("event claim is missing, expired, or owned elsewhere")
        elif is_live:
            raise EventClaimError("event is currently claimed by another router worker")

    def release_event_claims(self, lease_owner: str) -> int:
        """Release unprocessed claims when a router invocation exits cleanly."""

        if not _ERROR_CODE_RE.fullmatch(lease_owner) or len(lease_owner) > 128:
            raise ValueError("lease_owner must be a bounded safe identifier")
        with self._transaction() as connection:
            cursor = connection.execute(
                """UPDATE event_inbox SET lease_owner = NULL, lease_expires_at = NULL
                   WHERE lease_owner = ? AND status IN (?, ?)""",
                (
                    lease_owner,
                    EventInboxStatus.RECEIVED.value,
                    EventInboxStatus.FAILED.value,
                ),
            )
        return cursor.rowcount

    def event_queue_status(
        self, project_id: str | None = None
    ) -> EventQueueStatus:
        """Return queue counts and oldest pending age without event identifiers."""

        now = utc_now()
        with self._lock:
            if project_id is None:
                rows = self._connection.execute(
                    "SELECT status, COUNT(*) AS count FROM event_inbox "
                    "GROUP BY status"
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT status, COUNT(*) AS count FROM event_inbox "
                    "WHERE project_id = ? GROUP BY status",
                    (project_id,),
                ).fetchall()
            oldest_query = (
                "SELECT MIN(received_at) AS received_at FROM event_inbox "
                "WHERE project_id = ? AND status IN (?, ?)"
                if project_id is not None
                else "SELECT MIN(received_at) AS received_at FROM event_inbox "
                "WHERE status IN (?, ?)"
            )
            oldest_params = (
                (project_id, EventInboxStatus.RECEIVED.value, EventInboxStatus.FAILED.value)
                if project_id is not None
                else (EventInboxStatus.RECEIVED.value, EventInboxStatus.FAILED.value)
            )
            oldest = self._connection.execute(
                oldest_query, oldest_params
            ).fetchone()["received_at"]
            if project_id is not None:
                claim_counts = self._connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN lease_expires_at > ? THEN 1 ELSE 0 END), 0)
                           AS claimed,
                         COALESCE(SUM(CASE WHEN lease_expires_at IS NULL
                                            OR lease_expires_at <= ? THEN 1 ELSE 0 END), 0)
                           AS expired
                       FROM event_inbox
                       WHERE status IN (?, ?) AND lease_owner IS NOT NULL
                         AND project_id = ?""",
                    (
                        now,
                        now,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                        project_id,
                    ),
                ).fetchone()
            else:
                claim_counts = self._connection.execute(
                    """SELECT
                         COALESCE(SUM(CASE WHEN lease_expires_at > ? THEN 1 ELSE 0 END), 0)
                           AS claimed,
                         COALESCE(SUM(CASE WHEN lease_expires_at IS NULL
                                            OR lease_expires_at <= ? THEN 1 ELSE 0 END), 0)
                           AS expired
                       FROM event_inbox
                       WHERE status IN (?, ?) AND lease_owner IS NOT NULL""",
                    (
                        now,
                        now,
                        EventInboxStatus.RECEIVED.value,
                        EventInboxStatus.FAILED.value,
                    ),
                ).fetchone()
        counts = {row["status"]: int(row["count"]) for row in rows}
        oldest_age = None
        if oldest is not None:
            try:
                timestamp = datetime.fromisoformat(oldest.replace("Z", "+00:00"))
                if timestamp.tzinfo is not None:
                    oldest_age = max(
                        0, int((datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds())
                    )
            except ValueError:
                oldest_age = None
        return EventQueueStatus(
            received_count=counts.get(EventInboxStatus.RECEIVED.value, 0),
            failed_count=counts.get(EventInboxStatus.FAILED.value, 0),
            quarantined_count=counts.get(EventInboxStatus.QUARANTINED.value, 0),
            oldest_pending_received_at=oldest,
            oldest_pending_age_seconds=oldest_age,
            claimed_count=int(claim_counts["claimed"]),
            expired_claim_count=int(claim_counts["expired"]),
        )

    def event_receipt(self, project_id: str, event_id: str) -> EventInboxReceipt:
        """Return the compact acceptance/processing receipt for an event."""

        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (project_id, event_id),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"event not found: {project_id}/{event_id}")
        return self._event_receipt(row)

    @staticmethod
    def _regular_file_size(path: Path) -> int | None:
        """Read one file's current size without following a symlink."""

        try:
            metadata = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return 0
        if not stat.S_ISREG(metadata.st_mode):
            return None
        return metadata.st_size

    def project_storage_usage(self, project_id: str) -> ProjectStorageUsage:
        """Report logical retained bytes per project and physical DB files globally.

        Logical byte totals count UTF-8 record content, not SQLite page/index
        overhead. Database and WAL sizes are intentionally reported separately
        because one SQLite file may contain several projects.
        """

        with self._lock:
            goal_usage = self._connection.execute(
                """SELECT COUNT(*) AS count, COALESCE(SUM(
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
                       length(CAST(v.criteria_json AS BLOB)) +
                       length(CAST(v.reason AS BLOB)) +
                       length(CAST(v.created_at AS BLOB)) +
                       length(CAST(v.revision AS TEXT))
                     ) FROM goal_criteria_versions AS v WHERE v.goal_id = g.goal_id), 0)
                   ), 0) AS bytes FROM goals AS g WHERE g.project_id = ?""",
                (project_id,),
            ).fetchone()
            goal_status_rows = self._connection.execute(
                "SELECT status, COUNT(*) AS count FROM goals "
                "WHERE project_id = ? GROUP BY status ORDER BY status",
                (project_id,),
            ).fetchall()
            fact_usage = self._connection.execute(
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
                            length(CAST(goal_id AS BLOB)) +
                            length(CAST(source_sha256 AS BLOB)) +
                            length(CAST(archive_sha256 AS BLOB)) +
                            length(CAST(source_bytes AS TEXT)) +
                            length(CAST(compressed_bytes AS TEXT)) +
                            length(CAST(fact_count AS TEXT)) +
                            length(CAST(reviewer_id AS BLOB)) +
                            length(CAST(approval_reason AS BLOB)) +
                            length(CAST(created_at AS BLOB)) +
                            compressed_bytes
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
                     COALESCE(length(CAST(r.reviewer_id AS BLOB)), 0) +
                     COALESCE(length(CAST(r.review_rationale AS BLOB)), 0) +
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
                     COALESCE(length(CAST(p.next_attempt_at AS BLOB)), 0)
                   ), 0) AS bytes
                   FROM purge_targets AS p
                   JOIN audit_receipts AS r ON r.receipt_id = p.receipt_id
                   JOIN sde_candidates AS s ON s.candidate_id = r.candidate_id
                   JOIN goals AS g ON g.goal_id = s.goal_id
                   WHERE g.project_id = ?""",
                (project_id,),
            ).fetchone()
            event_rows = self._connection.execute(
                """SELECT event_type, status, COUNT(*) AS count,
                          COALESCE(SUM(payload_bytes), 0) AS original_bytes,
                          COALESCE(SUM(COALESCE(
                              length(CAST(payload_json AS BLOB)), 0
                          )), 0) AS retained_bytes,
                          COALESCE(SUM(
                              length(CAST(event_id AS BLOB)) +
                              length(CAST(payload_sha256 AS BLOB)) +
                              COALESCE(length(CAST(idempotency_sha256 AS BLOB)), 0) +
                              length(CAST(event_type AS BLOB)) +
                              length(CAST(status AS BLOB)) +
                              length(CAST(received_at AS BLOB)) +
                              COALESCE(length(CAST(processed_at AS BLOB)), 0) +
                   COALESCE(length(CAST(last_error AS BLOB)), 0) +
                   COALESCE(length(CAST(next_attempt_at AS BLOB)), 0) +
                   COALESCE(length(CAST(lease_owner AS BLOB)), 0) +
                   COALESCE(length(CAST(lease_expires_at AS BLOB)), 0)
                          ), 0) AS metadata_bytes
                   FROM event_inbox WHERE project_id = ?
                   GROUP BY event_type, status ORDER BY event_type, status""",
                (project_id,),
            ).fetchall()
            event_failure_rows = self._connection.execute(
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
            global_event_count, global_event_bytes = self._event_inbox_usage(
                self._connection
            )
            global_event_inbox = self._global_event_inbox_capacity(
                global_event_count, global_event_bytes
            )

        event_classes = tuple(
            EventClassStorageUsage(
                event_type=row["event_type"],
                status=row["status"],
                count=row["count"],
                original_payload_bytes=row["original_bytes"],
                retained_payload_bytes=row["retained_bytes"],
            )
            for row in event_rows
        )
        failure_counts = {
            EventFailureCategory(row["category"]): int(row["count"])
            for row in event_failure_rows
        }
        event_failures = tuple(
            EventFailureCategoryUsage(category, failure_counts.get(category, 0))
            for category in EventFailureCategory
        )
        event_count = sum(item.count for item in event_classes)
        event_original_bytes = sum(
            item.original_payload_bytes for item in event_classes
        )
        event_retained_bytes = sum(
            item.retained_payload_bytes for item in event_classes
        )
        event_metadata_bytes = sum(row["metadata_bytes"] for row in event_rows)
        logical_bytes = sum(
            row["bytes"]
            for row in (
                goal_usage,
                fact_usage,
                candidate_usage,
                correction_usage,
                feedback_usage,
                receipt_usage,
                artifact_usage,
                archive_usage,
            )
        ) + event_metadata_bytes + event_retained_bytes

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
            goal_count=goal_usage["count"],
            goal_statuses=tuple(
                GoalStatusStorageUsage(GoalStatus(row["status"]), int(row["count"]))
                for row in goal_status_rows
            ),
            goal_record_bytes=goal_usage["bytes"],
            fact_count=fact_usage["count"],
            fact_record_bytes=fact_usage["bytes"],
            sde_candidate_count=candidate_usage["count"],
            sde_record_bytes=candidate_usage["bytes"],
            sde_correction_count=correction_usage["count"],
            sde_correction_record_bytes=correction_usage["bytes"],
            sde_quality_feedback_count=feedback_usage["count"],
            sde_quality_feedback_record_bytes=feedback_usage["bytes"],
            audit_receipt_count=receipt_usage["count"],
            audit_record_bytes=receipt_usage["bytes"],
            artifact_count=artifact_usage["count"],
            artifact_record_bytes=artifact_usage["bytes"],
            event_receipt_count=event_count,
            event_payload_bytes_received=event_original_bytes,
            event_payload_bytes_retained=event_retained_bytes,
            event_classes=event_classes,
            event_failures=event_failures,
            global_event_inbox=global_event_inbox,
            logical_record_bytes=logical_bytes,
            staging=None,
            global_database_bytes=database_bytes,
            global_wal_bytes=wal_bytes,
            fact_count_limit=MAX_FACTS_PER_PROJECT,
            fact_record_bytes_limit=MAX_FACT_BYTES_PER_PROJECT,
            fact_capacity_reached=(
                fact_usage["count"] >= MAX_FACTS_PER_PROJECT
                or fact_usage["bytes"] >= MAX_FACT_BYTES_PER_PROJECT
            ),
            fact_archive_batch_count=archive_usage["batches"],
            fact_archive_item_count=archive_usage["items"],
            fact_archive_compressed_bytes=archive_usage["compressed_bytes"],
            fact_archive_logical_bytes=archive_usage["bytes"],
            fact_archive_logical_bytes_limit=MAX_FACT_ARCHIVE_BYTES_PER_PROJECT,
            fact_archive_bytes_remaining=max(
                0,
                MAX_FACT_ARCHIVE_BYTES_PER_PROJECT
                - archive_usage["bytes"],
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
            next_attempt_at = None
            if not discard_payload:
                attempt_number = int(existing["attempts"]) + 1
                delay_seconds = min(
                    EVENT_RETRY_BASE_SECONDS * (2 ** min(attempt_number - 1, 16)),
                    EVENT_RETRY_MAX_SECONDS,
                )
                next_attempt_at = (
                    failed_at + timedelta(seconds=delay_seconds)
                ).isoformat(timespec="microseconds")
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
                current = connection.execute(
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
                claim_lost = (
                    lease_owner is None and has_live_claim
                ) or (
                    lease_owner is not None
                    and (
                        current["lease_owner"] != lease_owner
                        or not has_live_claim
                    )
                )
                if claim_lost:
                    raise EventClaimError(
                        "event claim is missing, expired, or owned elsewhere"
                    )
                raise ConflictError("event is missing or already processed")
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
