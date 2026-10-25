"""Thin repository-bound plugin adapter over the Curator V2 global service."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from threading import RLock, local
from typing import BinaryIO, Generator, Mapping

from .evidence import EvidenceVerifier
from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    EventQueueStatus,
    GoalCriteriaAmended,
    GoalStarted,
)
from .markdown_persistence import (
    MarkdownPersistenceAdapter,
    MarkdownProjectReconciliation,
    MarkdownProjectionResult,
    MarkdownReconciliationResult,
)
from .models import (
    ArtifactCleanupAuthorizationRequest,
    MAX_ARTIFACTS_PER_RECEIPT,
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    ChecklistGoalStartRequest,
    CleanupAuthorizationReceipt,
    ExpiryPurgeReceipt,
    FactArchiveReceipt,
    FactCompactionProposal,
    GoalChildrenPageRequest,
    GoalCard,
    GoalListPage,
    GoalBulletProjection,
    GoalSnapshot,
    GoalSubtaskStartRequest,
    GoalStatus,
    ProjectActivitySnapshot,
    ProjectStorageUsage,
    ProjectOperationalCounts,
    PurgeFailureCode,
    ReacquisitionAction,
    SDECandidate,
    SDEConfirmationRequest,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    SDEReviewPacket,
    StagingArtifactInventory,
    StagingExpirySnapshot,
    SuccessCriterion,
    utc_now,
)
from .staging_models import (
    MAX_STAGING_SCAN_ENTRIES,
    StagingUsage,
)
from .read_models import (
    artifact_dependency_map_sha256,
    build_artifact_review_dependencies,
)
from .staging_scan import StagingTreeScanner
from .staging_write import (
    StagingArtifactWriteRequest,
    StagingWriteLimits,
    write_staged_artifact,
)
from .project_config import ProjectConfig, ProjectConfigError
from .purge import ArtifactPurger, PurgeError
from .reporting import GoalReportPage
from .reviews import ReviewAuthorizer
from .service import (
    CuratorService,
    PurgeTargetStatus,
    SDEAssessmentRequest,
)
from .store import FactCompactionApprovalRequest
from .store import ConflictError, CuratorStore, NotFoundError
from .store_requests import ProjectDrainEffectContext

MAX_STAGING_HASH_BYTES = 8 * 1024**3
MAX_STAGED_ARTIFACT_BYTES = 64 * 1024**2
MAX_GOAL_STAGING_BYTES = 256 * 1024**2
MAX_GOAL_STAGING_FILES = MAX_ARTIFACTS_PER_RECEIPT
_STAGING_SCOPE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_DRAIN_EFFECT_CONTEXT: ContextVar[
    tuple[str, str | None, EventEnvelope] | None
] = ContextVar("curator_v2_drain_effect_context", default=None)
_STAGING_CLASS_RE = re.compile(r"^(raw-chat|cue|import|scratch|generated|duplicate)$")
STAGING_MAX_AGE = timedelta(hours=72)


def _aware_utc_now(value: datetime | None = None) -> datetime:
    """Normalize one injectable, timezone-aware clock reading to UTC."""

    observed = value or datetime.now(UTC)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return observed.astimezone(UTC)


def _staged_artifact_goal_times(
    config: ProjectConfig,
    artifacts: tuple[ArtifactRef, ...],
    timestamps: Mapping[str, str],
) -> dict[str, tuple[str, str]]:
    """Select exact staged files that can be joined to goal review evidence."""

    staging_root = config.validated_staging_root()
    result: dict[str, tuple[str, str]] = {}
    for artifact in artifacts:
        staged_at = timestamps.get(artifact.path)
        try:
            path_parts = Path(artifact.path).relative_to(staging_root).parts
        except ValueError:
            path_parts = ()
        if (
            staged_at is not None
            and len(path_parts) == 3
            and _STAGING_SCOPE_ID_RE.fullmatch(path_parts[0])
        ):
            result[artifact.path] = (path_parts[0], staged_at)
    return result


def _select_expiry_eligible_artifacts(
    artifacts: tuple[ArtifactRef, ...],
    timestamps: Mapping[str, str],
    readiness: Mapping[str, tuple[bool, bool, int]],
    cutoff: datetime,
) -> tuple[tuple[ArtifactRef, ...], int, int]:
    """Apply exact-age and post-stage record rules without mutating storage."""

    eligible: list[ArtifactRef] = []
    unknown_age_count = 0
    pending_sde_artifact_count = 0
    for artifact in artifacts:
        expiry_state = _artifact_expiry_state(
            artifact.path, timestamps, readiness, cutoff
        )
        if expiry_state is None:
            unknown_age_count += 1
            continue
        age_eligible, review_ready, pending_sde_count = expiry_state
        if pending_sde_count:
            if age_eligible or review_ready:
                pending_sde_artifact_count += 1
            # Pending review delays prompt post-record expiry, but it must not
            # extend transient-source retention beyond the approved 72 hours.
            if not age_eligible:
                continue
        if age_eligible or review_ready:
            eligible.append(artifact)
    return tuple(eligible), unknown_age_count, pending_sde_artifact_count


def _artifact_expiry_state(
    path: str,
    timestamps: Mapping[str, str],
    readiness: Mapping[str, tuple[bool, bool, int]],
    cutoff: datetime,
) -> tuple[bool, bool, int] | None:
    """Return age, post-stage readiness, and pending-SDE state for one file."""

    staged_at = timestamps.get(path)
    state = readiness.get(path)
    if staged_at is None or state is None:
        return None
    try:
        parsed = datetime.fromisoformat(staged_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    fact_after_stage, review_after_stage, pending_sde_count = state
    return (
        parsed.astimezone(UTC) <= cutoff,
        fact_after_stage or review_after_stage,
        pending_sde_count,
    )


def _expiry_manifest_sha256(artifacts: tuple[ArtifactRef, ...]) -> str:
    """Hash the exact eligible path/digest/occurrence triples in order."""

    manifest = json.dumps(
        [(item.path, item.sha256, item.occurrence_id) for item in artifacts],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


class ProjectPlugin:
    """Expose only configured project paths and project-scoped goal operations."""

    def __init__(self, config: ProjectConfig, service: CuratorService) -> None:
        if service.project_id != config.project_id:
            raise ProjectConfigError("service project does not match repository config")
        self.config = config
        self.service = service
        try:
            binding = service.store.get_consumer_binding(config.project_id)
        except NotFoundError:
            self._consumer_binding_revision: int | None = None
        else:
            self._consumer_binding_revision = binding.revision
        self._staging_thread_lock = RLock()
        self._staging_lock_state = local()

    @contextmanager
    def _locked_staging_root(self) -> Generator[int, None, None]:
        """Serialize supported plugin operations on this staging directory."""

        with self._staging_thread_lock:
            existing_fd = getattr(self._staging_lock_state, "root_fd", None)
            if existing_fd is not None:
                self._staging_lock_state.depth += 1
                try:
                    yield existing_fd
                finally:
                    self._staging_lock_state.depth -= 1
                return

            no_follow = getattr(os, "O_NOFOLLOW", None)
            directory_flag = getattr(os, "O_DIRECTORY", None)
            if no_follow is None or directory_flag is None:
                raise ProjectConfigError("platform lacks safe staging lock primitives")
            root = self.config.validated_staging_root()
            root_open_failed = False
            root_fd = -1
            try:
                root_fd = os.open(root, os.O_RDONLY | directory_flag | no_follow)
            except OSError:
                root_open_failed = True
            if root_open_failed:
                raise ProjectConfigError("staging root cannot be opened safely")
            try:
                fcntl.flock(root_fd, fcntl.LOCK_EX)
                self._staging_lock_state.root_fd = root_fd
                self._staging_lock_state.depth = 1
                try:
                    yield root_fd
                finally:
                    del self._staging_lock_state.root_fd
                    del self._staging_lock_state.depth
            finally:
                try:
                    fcntl.flock(root_fd, fcntl.LOCK_UN)
                finally:
                    os.close(root_fd)

    @contextmanager
    def project_effect_lock(self) -> Generator[None, None, None]:
        """Acquire the repository staging lock before an API revision fence."""

        with self._locked_staging_root():
            yield

    @contextmanager
    def _active_project_revision_fence(self) -> Generator[None, None, None]:
        """Fence an effect to this config's currently active revision."""

        revision = self._capture_active_project_revision()
        with self._project_revision_fence(revision):
            yield

    def _capture_active_project_revision(self) -> int:
        """Capture the active revision before an external verification phase."""

        registration = self.service.store.get_project_registration(
            self.config.project_id
        )
        if (
            registration.repository_fingerprint,
            registration.config_sha256,
            registration.backend_api_version,
        ) != (
            self.config.repository_fingerprint,
            self.config.config_sha256,
            self.config.backend_api_version,
        ):
            raise ConflictError("maintenance project binding changed")
        if self._consumer_binding_revision is None:
            raise ConflictError("consumer binding was not active when plugin bound")
        if registration.status != "active":
            raise ConflictError("project lifecycle changed before the effect")
        return registration.revision

    def refresh_consumer_binding_revision(self, expected_revision: int) -> None:
        """Refresh a re-enrolled binding after the API authorizes its writer."""

        binding = self.service.store.get_consumer_binding(self.config.project_id)
        if binding.status != "active" or binding.revision != expected_revision:
            raise ConflictError("consumer binding changed before the effect")
        self._consumer_binding_revision = binding.revision

    @contextmanager
    def _project_revision_fence(
        self,
        expected_revision: int,
        *,
        drain_event: EventEnvelope | None = None,
        caller_subject: str | None = None,
        caller_profile: str | None = None,
        expected_binding_revision: int | None = None,
    ) -> Generator[None, None, None]:
        """Fence an effect to a previously captured project revision."""

        inherited_drain = _DRAIN_EFFECT_CONTEXT.get()
        if drain_event is None and inherited_drain is not None:
            caller_subject, caller_profile, drain_event = inherited_drain

        with self.service.store.project_revision_fence(
            self.config.project_id,
            expected_revision,
            drain=(
                ProjectDrainEffectContext(
                    drain_event, caller_subject, caller_profile
                )
                if drain_event is not None and caller_subject is not None
                else None
            ),
            expected_binding_revision=(
                self._consumer_binding_revision
                if expected_binding_revision is None
                else expected_binding_revision
            ),
        ):
            yield

    @classmethod
    def bind(
        cls,
        config: ProjectConfig,
        store: CuratorStore,
        evidence_verifier: EvidenceVerifier | None = None,
        review_authorizer: ReviewAuthorizer | None = None,
    ) -> ProjectPlugin:
        """Bind config to the global store without mixing project state."""

        staging_root = config.validated_staging_root()
        service = CuratorService(
            store,
            ArtifactPurger(staging_root),
            evidence_verifier,
            review_authorizer,
            project_id=config.project_id,
        )
        plugin = cls(config, service)
        service.bind_project_effect_boundary(
            plugin._capture_active_project_revision,
            plugin._project_revision_fence,
        )
        return plugin

    @property
    def repository_root(self) -> Path:
        """Return this plugin's validated consumer repository root."""

        return self.config.project_root

    @property
    def persistence_targets(self) -> tuple[Path, ...]:
        """Return the explicitly configured canonical Markdown targets."""

        return self.config.persistence_targets

    def persist_goal(self, goal_id: str, target: str | Path) -> MarkdownProjectionResult:
        """Project one scoped goal to an explicitly selected configured target.

        Projection is deliberately explicit and never approves an SDE. For an
        already reviewed receipt, a successful Markdown write records its
        target/hash in SQLite and releases the purge gate; purge errors remain
        visible on the receipt and are reflected by the follow-up projection.
        """

        with self._locked_staging_root():
            expected_revision = self._capture_active_project_revision()

            def effect_fence():
                """Fence each durable projection effect to the captured revision."""

                return self._project_revision_fence(expected_revision)

            adapter = MarkdownPersistenceAdapter(
                self.config,
                self.service.store,
                target,
                self.service.evidence_verifier,
            )
            projection = adapter.persist_goal(goal_id, effect_fence=effect_fence)
            unpersisted = tuple(
                receipt
                for receipt in self.service.store.receipts_for_goal(
                    goal_id, self.config.project_id
                )
                if not receipt.canonical_persisted
            )
            for receipt in unpersisted:
                adapter.verify_projection(projection)
                with effect_fence():
                    self.service.mark_canonical_persisted(
                        receipt.receipt_id,
                        projection.target.relative_to(
                            self.config.project_root
                        ).as_posix(),
                        projection.sha256,
                    )
            cleanup_unpersisted = tuple(
                receipt
                for receipt in self.service.store.receipts_for_goal(
                    goal_id, self.config.project_id
                )
                if receipt.cleanup_authorized
                and not receipt.cleanup_canonical_persisted
            )
            for receipt in cleanup_unpersisted:
                adapter.verify_projection(projection)
                with effect_fence():
                    self.service.mark_cleanup_authorization_canonical_persisted(
                        receipt.receipt_id,
                        projection.target.relative_to(
                            self.config.project_root
                        ).as_posix(),
                        projection.sha256,
                    )
            if unpersisted or cleanup_unpersisted:
                projection = adapter.persist_goal(
                    goal_id, effect_fence=effect_fence
                )
            return projection

    def reconcile_goal(
        self, goal_id: str, target: str | Path
    ) -> MarkdownReconciliationResult:
        """Compare configured Markdown with the structured record read-only."""

        adapter = MarkdownPersistenceAdapter(
            self.config,
            self.service.store,
            target,
            self.service.evidence_verifier,
        )
        return adapter.reconcile_goal(goal_id)

    def reconcile_project(
        self,
        target: str | Path,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MarkdownProjectReconciliation:
        """Return a bounded per-goal and orphan-marker reconciliation page."""

        adapter = MarkdownPersistenceAdapter(
            self.config,
            self.service.store,
            target,
            self.service.evidence_verifier,
        )
        return adapter.reconcile_project(offset=offset, limit=limit)

    def checklist_path(self, checklist_id: str) -> Path:
        """Resolve a checklist only when its ID is bound in repository config."""

        return self.config.checklist_path(checklist_id)

    def resolve_read_path(self, relative_path: str) -> Path:
        """Return a path inside the config's read-only repository allowlist."""

        return self.config.resolve_read_path(relative_path)

    def process_event(
        self,
        event: EventEnvelope,
        *,
        drain_caller: tuple[str, str | None] | None = None,
        expected_binding_revision: int | None = None,
    ) -> EventInboxReceipt:
        """Apply an event only inside this plugin's project binding.

        Checklist snapshots are revalidated at the repository boundary so a
        generic event/MCP caller cannot invent a checklist line or revision.
        Successfully processed retries remain idempotent after the source file
        later changes; the store still rejects changed payload reuse.
        """

        if event.project_id != self.config.project_id:
            raise PermissionError("event project does not match this plugin")
        with self._locked_staging_root():
            expected_revision = self._capture_active_project_revision()
            token = (
                _DRAIN_EFFECT_CONTEXT.set(
                    (drain_caller[0], drain_caller[1], event)
                )
                if drain_caller is not None
                else None
            )
            try:
                return self._process_event_locked(
                    event,
                    expected_revision,
                    drain_caller,
                    expected_binding_revision,
                )
            finally:
                if token is not None:
                    _DRAIN_EFFECT_CONTEXT.reset(token)

    def _process_event_locked(
        self,
        event: EventEnvelope,
        expected_revision: int,
        drain_caller: tuple[str, str | None] | None = None,
        expected_binding_revision: int | None = None,
    ) -> EventInboxReceipt:
        """Validate repository-bound fields, then fence durable event effects."""

        payload = event.payload
        if isinstance(payload, GoalStarted) and payload.checklist_id is not None:
            try:
                prior_receipt = self.service.store.event_receipt(
                    self.config.project_id, event.event_id
                )
            except NotFoundError:
                prior_receipt = None
            if (
                prior_receipt is None
                or prior_receipt.status is not EventInboxStatus.PROCESSED
            ):
                version, source_text = self.config.checklist_snapshot(
                    payload.checklist_id, payload.checklist_source_text or ""
                )
                if (
                    version != payload.checklist_version
                    or source_text != payload.checklist_source_text
                ):
                    raise ProjectConfigError(
                        "checklist snapshot does not match the configured source revision"
                    )

        def effect_fence():
            return self._project_revision_fence(
                expected_revision,
                drain_event=event if drain_caller is not None else None,
                caller_subject=drain_caller[0] if drain_caller is not None else None,
                caller_profile=drain_caller[1] if drain_caller is not None else None,
                expected_binding_revision=expected_binding_revision,
            )

        return self.service.process_event(
            event,
            effect_fence=effect_fence,
            override_project_fence=drain_caller is not None,
        )

    def event_queue_status(self) -> EventQueueStatus:
        """Return event backlog metrics for this project's authorized binding."""

        return self.service.store.event_queue_status(self.config.project_id)

    def activity_status(self) -> ProjectActivitySnapshot:
        """Return retained event, goal, fact, and SDE totals for this project."""

        return self.service.store.project_activity_status(self.config.project_id)

    def retry_quarantined_event(
        self, event_id: str, actor_id: str
    ) -> EventInboxReceipt:
        """Audit and retry one quarantined event within this project only."""

        with self._active_project_revision_fence():
            return self.service.store.retry_quarantined_event(
                self.config.project_id, event_id, actor_id
            )

    def goal_start_from_request(
        self,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        *,
        owner: str | None = None,
        next_action: str | None = None,
        source_event_id: str | None = None,
    ) -> GoalCard:
        """Start a user-request goal without deriving or rewriting criteria.

        Callers must pass the agreed problem and observable success criteria.
        The model validates and stores those values unchanged; an empty criteria
        set is rejected rather than synthesized from the problem statement.
        """

        with self._active_project_revision_fence():
            return self.service.goal_start(
                problem,
                success_criteria,
                owner=owner,
                initial_status=GoalStatus.PLANNED,
                next_action=next_action,
                source_event_id=source_event_id,
            )

    def goal_start_subtask(
        self,
        request: GoalSubtaskStartRequest,
    ) -> GoalCard:
        """Start an explicitly accepted child task with its own criteria.

        This adapter does not turn a proposal into accepted work on its own:
        invocation is the caller's explicit acceptance, and the parent remains
        the provenance link. The service enforces same-project parent and
        dependency rules and rejects missing criteria.
        """

        with self._active_project_revision_fence():
            return self.service.goal_start(
                request.problem,
                request.success_criteria,
                owner=request.owner,
                parent_goal_id=request.parent_goal_id,
                depends_on_goal_ids=request.depends_on_goal_ids,
                initial_status=GoalStatus.PLANNED,
                next_action=request.next_action,
                source_event_id=request.source_event_id,
            )

    def goal_start_from_checklist(
        self,
        request: ChecklistGoalStartRequest,
    ) -> GoalCard:
        """Start a goal with an exact checklist line and source-file revision."""

        with self._active_project_revision_fence():
            source_version, source_text = self.config.checklist_snapshot(
                request.checklist_id, request.exact_item_text
            )
            return self.service.goal_start(
                request.problem,
                request.success_criteria,
                owner=request.options.owner,
                checklist_id=request.checklist_id,
                checklist_version=source_version,
                checklist_source_text=source_text,
                parent_goal_id=request.options.parent_goal_id,
                depends_on_goal_ids=request.options.depends_on_goal_ids,
                initial_status=request.options.initial_status,
                next_action=request.options.next_action,
                source_event_id=request.options.source_event_id,
            )

    def goal_status(
        self, goal_id: str, sde_offset: int = 0, purge_offset: int = 0
    ) -> GoalSnapshot:
        """Read one bounded status page from this plugin's project scope."""

        return self.service.goal_status(
            goal_id, sde_offset=sde_offset, purge_offset=purge_offset
        )

    def goal_activate(
        self, goal_id: str, reason: str, expected_lifecycle_revision: int
    ) -> GoalCard:
        """Activate one planned goal under this plugin's project binding."""

        with self._active_project_revision_fence():
            return self.service.goal_activate(
                goal_id, reason, expected_lifecycle_revision
            )

    def goal_bullet_projection(self, goal_id: str) -> GoalBulletProjection:
        """Return compact truth-labeled bullets inside this project boundary."""

        return self.service.goal_bullet_projection(goal_id)

    def goal_report(
        self,
        goal_id: str,
        page: GoalReportPage | None = None,
    ) -> str:
        """Render a bounded, user-readable report inside this project scope."""

        return self.service.goal_report(goal_id, page)

    def fact_compaction_propose(
        self, goal_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Preview routine facts eligible for project-scoped archival."""

        return self.service.fact_compaction_propose(goal_id, max_facts)

    def fact_compaction_approve(
        self,
        approval: FactCompactionApprovalRequest,
    ) -> FactArchiveReceipt:
        """Apply a hash-matched archive only after host review authorization."""

        with self._active_project_revision_fence():
            return self.service.fact_compaction_approve(
                replace(approval, project_id=self.config.project_id)
            )

    def fact_archive_receipts(
        self, goal_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read verified archive receipts inside this project's boundary."""

        return self.service.fact_archive_receipts(
            goal_id, offset=offset, limit=limit
        )

    def storage_usage(self) -> ProjectStorageUsage:
        """Return project records, staging scan, and separate global DB sizes."""

        usage = self.service.store.project_storage_usage(self.config.project_id)
        with self._locked_staging_root() as root_fd:
            staging = self._scan_staging_tree(
                discover_artifacts=False, staging_root_fd=root_fd
            ).usage
        return replace(
            usage,
            staging=staging,
            staging_project_byte_limit=self.config.staging_max_project_bytes,
            staging_project_file_limit=self.config.staging_max_project_files,
        )

    def operational_health_inputs(
        self,
    ) -> tuple[EventQueueStatus, ProjectOperationalCounts, ProjectStorageUsage, int, str]:
        """Read consistent SQLite health inputs and scan bounded staging state."""

        (
            queue,
            counts,
            usage,
            scrub_count,
            database_observed_at,
        ) = self.service.store.project_health_inputs(self.config.project_id)
        try:
            with self._locked_staging_root() as root_fd:
                staging = self._scan_staging_tree(
                    discover_artifacts=False, staging_root_fd=root_fd
                ).usage
        except ProjectConfigError:
            staging = StagingUsage(
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                "staging_root_unavailable",
                observed_at=utc_now(),
            )
        except OSError:
            staging = StagingUsage(
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                "staging_lock_unavailable",
                observed_at=utc_now(),
            )
        return queue, counts, replace(
            usage,
            staging=staging,
            staging_project_byte_limit=self.config.staging_max_project_bytes,
            staging_project_file_limit=self.config.staging_max_project_files,
        ), scrub_count, database_observed_at

    def discover_staging_artifacts(
        self, goal_id: str
    ) -> StagingArtifactInventory:
        """Discover only artifacts staged beneath this project goal's directory."""

        if not _STAGING_SCOPE_ID_RE.fullmatch(goal_id):
            raise ValueError("goal_id must be a bounded opaque identifier")
        with self._locked_staging_root() as root_fd:
            self.service.store.get_goal(goal_id, self.config.project_id)
            return self._scan_staging_tree(
                discover_artifacts=True,
                scope_goal_id=goal_id,
                staging_root_fd=root_fd,
            )

    def discover_project_staging_artifacts(self) -> StagingArtifactInventory:
        """Inventory every staged file in this project without authorizing purge.

        The project-wide snapshot includes files under unrecognized or orphaned
        goal directories so they cannot disappear from inventory merely because
        they are not attached to a current goal. Incomplete or over-limit scans
        remain explicitly incomplete; callers must not use this method as
        approval to delete anything.
        """

        with self._locked_staging_root() as root_fd:
            return self._scan_staging_tree(
                discover_artifacts=True, staging_root_fd=root_fd
            )

    def review_staging_inventory(self) -> StagingArtifactInventory:
        """Hash a complete staging snapshot without updating inventory metadata."""

        with self._locked_staging_root() as root_fd:
            scanner = StagingTreeScanner(
                self.config,
                self._hash_staged_file,
                max_entries=MAX_STAGING_SCAN_ENTRIES,
                max_hash_bytes=MAX_STAGING_HASH_BYTES,
            )
            return scanner.discover(staging_root_fd=root_fd)

    def discover_expired_staging_artifacts(
        self, now: datetime | None = None
    ) -> StagingExpirySnapshot:
        """Find over-age artifacts from complete scans and exact durable age data.

        This is eligibility discovery only. It neither approves deletion nor
        creates a purge receipt. Any file without matching V2 age metadata makes
        the snapshot incomplete and therefore unusable for a purge decision.
        """

        observed_at = _aware_utc_now(now)
        with self._locked_staging_root() as root_fd:
            return self._expiry_snapshot_locked(root_fd, observed_at)

    def _expiry_snapshot_locked(
        self, root_fd: int, observed_at: datetime
    ) -> StagingExpirySnapshot:
        """Build a complete age and active-hold view under the staging lock."""

        cutoff = observed_at - STAGING_MAX_AGE
        inventory = self._scan_staging_tree(
            discover_artifacts=True, staging_root_fd=root_fd
        )
        timestamps = self.service.store.staging_artifact_times(
            self.config.project_id, inventory.artifacts
        )
        artifact_goal_times = _staged_artifact_goal_times(
            self.config, inventory.artifacts, timestamps
        )
        readiness = self.service.store.staging_artifact_expiry_readiness(
            self.config.project_id, artifact_goal_times
        )
        expired, unknown_age_count, pending_sde_artifact_count = (
            _select_expiry_eligible_artifacts(
                inventory.artifacts, timestamps, readiness, cutoff
            )
        )
        complete = inventory.usage.inventory_complete and unknown_age_count == 0
        if not complete:
            expired = ()
        eligible, held = self._partition_expiry_holds(expired)
        manifest_sha256 = (
            _expiry_manifest_sha256(eligible) if complete else None
        )
        return StagingExpirySnapshot(
            eligible,
            held,
            complete,
            unknown_age_count,
            cutoff.isoformat(timespec="microseconds"),
            manifest_sha256,
            pending_sde_artifact_count,
        )

    def _partition_expiry_holds(
        self, expired: tuple[ArtifactRef, ...]
    ) -> tuple[tuple[ArtifactRef, ...], tuple[ArtifactRef, ...]]:
        """Separate held targets from purge-eligible targets in path order."""

        active_holds = self.service.store.active_staging_artifact_holds(
            self.config.project_id, expired
        )
        held = tuple(
            ArtifactRef(
                item.path,
                item.sha256,
                active_holds[item.path],
                item.device_id,
                item.inode_id,
                item.occurrence_id,
            )
            for item in sorted(expired, key=lambda item: item.path)
            if item.path in active_holds
        )
        eligible = tuple(
            item
            for item in sorted(expired, key=lambda item: item.path)
            if item.path not in active_holds
        )
        return eligible, held

    def approve_expired_staging_inventory(
        self,
        artifacts: tuple[ArtifactRef, ...],
        manifest_sha256: str,
        *,
        authenticated_subject: str | None = None,
        now: datetime | None = None,
    ) -> ExpiryPurgeReceipt:
        """Authorize, receipt, then purge one exact current expiry inventory."""

        observed_at = _aware_utc_now(now)
        with self._locked_staging_root() as root_fd:
            with self._active_project_revision_fence():
                snapshot = self._expiry_snapshot_locked(root_fd, observed_at)
                if not snapshot.inventory_complete or snapshot.manifest_sha256 is None:
                    raise ConflictError("expiry inventory is incomplete")
                submitted = tuple(
                    (
                        item.path, item.sha256, item.device_id, item.inode_id,
                        item.occurrence_id,
                    )
                    for item in artifacts
                )
                current = tuple(
                    (
                        item.path, item.sha256, item.device_id, item.inode_id,
                        item.occurrence_id,
                    )
                    for item in snapshot.eligible_artifacts
                )
                if not artifacts or len(submitted) != len(current) or any(
                    supplied[:2] != observed[:2]
                    or (
                        supplied[2] is not None
                        and (supplied[2], supplied[3]) != (observed[2], observed[3])
                    )
                    or (
                        supplied[4] is not None and supplied[4] != observed[4]
                    )
                    for supplied, observed in zip(submitted, current)
                ):
                    raise ConflictError(
                        "expiry inventory does not match current eligibility"
                    )
                artifacts = snapshot.eligible_artifacts
                if manifest_sha256 != snapshot.manifest_sha256:
                    raise ConflictError("expiry manifest changed before approval")
                reviewer_id = self.service.review_authorizer.authorize_expiry_purge(
                    self.config.project_id,
                    manifest_sha256,
                    authenticated_subject,
                )
                receipt = self.service.store.create_expiry_purge_receipt(
                    self.config.project_id,
                    reviewer_id,
                    manifest_sha256,
                    artifacts,
                )
                return self._process_expiry_purge(receipt.receipt_id)

    def expiry_purge_receipt(self, receipt_id: str) -> ExpiryPurgeReceipt:
        """Read the durable project-scoped result of an expiry approval."""

        return self.service.store.expiry_purge_receipt(
            receipt_id, self.config.project_id
        )

    def retry_due_expiry_purges(self, limit: int = 100) -> tuple[ExpiryPurgeReceipt, ...]:
        """Retry only due targets from durable attended expiry approvals."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self._retry_due_expiry_purges_locked(limit)

    def retry_due_purge_pass(
        self, limit: int = 100
    ) -> tuple[tuple[AuditReceipt, ...], tuple[ExpiryPurgeReceipt, ...]]:
        """Run both approved retry queues under one active project fence.

        Acquire the staging lock before the SQLite revision fence. File-producing
        plugin operations use the same order when persisting their receipts.
        """

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._locked_staging_root():
            with self._active_project_revision_fence():
                receipts = self.service.retry_due_purges(limit)
                expiry_receipts = self._retry_due_expiry_purges_locked(limit)
        return receipts, expiry_receipts

    def _retry_due_expiry_purges_locked(
        self, limit: int
    ) -> tuple[ExpiryPurgeReceipt, ...]:
        receipts = self.service.store.due_expiry_purge_receipts(
            self.config.project_id, limit
        )
        return tuple(self._process_expiry_purge(item) for item in receipts)

    def retry_expiry_purge(self, receipt_id: str) -> ExpiryPurgeReceipt:
        """Retry due targets from one exact, previously approved receipt."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                self.service.store.expiry_purge_receipt(
                    receipt_id, self.config.project_id
                )
                return self._process_expiry_purge(receipt_id)

    def _process_expiry_purge(self, receipt_id: str) -> ExpiryPurgeReceipt:
        """Attempt due exact targets from an already approved expiry receipt."""

        targets = self.service.store.expiry_purge_targets(
            receipt_id, self.config.project_id
        )
        staging_root = self.config.validated_staging_root()
        for artifact, _attempts in targets:
            try:
                path_parts = Path(artifact.path).relative_to(staging_root).parts
            except ValueError:
                continue
            if len(path_parts) != 3:
                continue
            if not self.service.store.begin_expiry_purge_attempt(
                receipt_id, artifact.path, self.config.project_id, path_parts[0]
            ):
                continue
            try:
                self.service.purger.purge(artifact)
            except PurgeError as exc:
                error_code = exc.code.value
                self.service.store.record_expiry_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.FAILED,
                    error_code,
                    self.config.project_id,
                )
            except OSError:
                error_code = PurgeFailureCode.FILESYSTEM_ERROR.value
                self.service.store.record_expiry_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.FAILED,
                    error_code,
                    self.config.project_id,
                )
            except ValueError:
                error_code = PurgeFailureCode.INVALID_ARTIFACT.value
                self.service.store.record_expiry_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.FAILED,
                    error_code,
                    self.config.project_id,
                )
            else:
                self.service.store.record_expiry_purge_result(
                    receipt_id,
                    artifact.path,
                    ArtifactStatus.PURGED,
                    None,
                    self.config.project_id,
                )
        return self.service.store.expiry_purge_receipt(
            receipt_id, self.config.project_id
        )

    def stage_artifact(
        self,
        goal_id: str,
        artifact_class: str,
        artifact_id: str,
        source: BinaryIO,
    ) -> ArtifactRef:
        """Atomically stream one bounded, temporary artifact into goal scope.

        Producer adapters should call this instead of writing into the staging
        tree directly. The API deliberately accepts a binary stream and never
        returns artifact contents. It enforces hard technical ceilings; it does
        not implement an age-based retention policy or delete older artifacts.
        Artifact IDs are immutable within a project/goal/class path: after a
        prior occurrence has been observed, reusing its ID fails closed so a
        replay cannot reset retention age. A genuinely new artifact needs a new
        ID.
        """

        if not _STAGING_SCOPE_ID_RE.fullmatch(goal_id):
            raise ValueError("goal_id must be a bounded opaque identifier")
        if not _STAGING_CLASS_RE.fullmatch(artifact_class):
            raise ValueError("artifact_class is not a supported temporary class")
        if not _STAGING_SCOPE_ID_RE.fullmatch(artifact_id):
            raise ValueError("artifact_id must be a bounded opaque identifier")
        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            raise ProjectConfigError("platform lacks safe staging write primitives")

        with self._locked_staging_root() as root_fd:
            self.service.store.get_goal(goal_id, self.config.project_id)
            with self._active_project_revision_fence():
                return self._stage_artifact_locked(
                    root_fd, goal_id, artifact_class, artifact_id, source
                )

    def _stage_artifact_locked(
        self,
        root_fd: int,
        goal_id: str,
        artifact_class: str,
        artifact_id: str,
        source: BinaryIO,
    ) -> ArtifactRef:
        """Publish a producer artifact while the project staging lock is held."""

        existing_bytes, project_usage = self._staging_budget_snapshot(
            root_fd, goal_id
        )
        return write_staged_artifact(
            self.config,
            self.service.store.record_staging_artifact_time,
            StagingArtifactWriteRequest(
                root_fd,
                goal_id,
                artifact_class,
                artifact_id,
                source,
                existing_bytes,
                project_usage,
            ),
            StagingWriteLimits(
                MAX_STAGED_ARTIFACT_BYTES,
                MAX_GOAL_STAGING_BYTES,
                self.config.staging_max_project_bytes,
            ),
        )

    def _staging_budget_snapshot(
        self, root_fd: int, goal_id: str
    ) -> tuple[int, StagingUsage | None]:
        """Verify goal and optional project budgets before starting a write."""

        inventory = self._scan_staging_tree(
            discover_artifacts=True,
            scope_goal_id=goal_id,
            staging_root_fd=root_fd,
        )
        if not inventory.usage.inventory_complete:
            raise ConflictError(
                "cannot stage into an incompletely inventoried goal scope"
            )
        if self.service.store.pending_receipts_for_goal(
            goal_id, self.config.project_id
        ):
            raise ConflictError("cannot stage while this goal has a pending purge receipt")
        if len(inventory.artifacts) >= MAX_GOAL_STAGING_FILES:
            raise ConflictError("goal staging file-count ceiling reached")
        existing_bytes = sum(
            self._artifact_size(item.path) for item in inventory.artifacts
        )
        if existing_bytes >= MAX_GOAL_STAGING_BYTES:
            raise ConflictError("goal staging byte ceiling reached")

        project_usage = None
        if (
            self.config.staging_max_project_bytes is not None
            or self.config.staging_max_project_files is not None
        ):
            project_inventory = self._scan_staging_tree(
                discover_artifacts=False, staging_root_fd=root_fd
            )
            if not project_inventory.usage.inventory_complete:
                raise ConflictError(
                    "cannot enforce project staging budget with incomplete inventory"
                )
            if (
                self.config.staging_max_project_files is not None
                and project_inventory.usage.regular_file_count
                >= self.config.staging_max_project_files
            ):
                raise ConflictError("project staging file-count budget reached")
            if (
                self.config.staging_max_project_bytes is not None
                and project_inventory.usage.observed_file_bytes
                >= self.config.staging_max_project_bytes
            ):
                raise ConflictError("project staging byte budget reached")
            project_usage = project_inventory.usage
        return existing_bytes, project_usage

    @staticmethod
    def _artifact_size(path: str) -> int:
        """Read a no-follow regular-file size from a discovered manifest path."""

        metadata = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise ConflictError("staged artifact changed after inventory discovery")
        return metadata.st_size

    def _require_current_artifact_inventory(
        self,
        goal_id: str,
        artifacts: tuple[ArtifactRef, ...],
        *,
        staging_root_fd: int | None = None,
    ) -> tuple[ArtifactRef, ...]:
        if staging_root_fd is None:
            inventory = self.discover_staging_artifacts(goal_id)
        else:
            inventory = self._scan_staging_tree(
                discover_artifacts=True,
                scope_goal_id=goal_id,
                staging_root_fd=staging_root_fd,
            )
        if not inventory.usage.inventory_complete:
            raise ConflictError(
                "staging inventory is incomplete: "
                f"{inventory.usage.error_code or 'unknown'}"
            )
        submitted = tuple(sorted(artifacts, key=lambda item: item.path))
        discovered = tuple(sorted(inventory.artifacts, key=lambda item: item.path))
        if len(submitted) != len(discovered) or any(
            requested.path != observed.path
            or requested.sha256 != observed.sha256
            or (
                observed.retention_hold is not None
                and requested.retention_hold != observed.retention_hold
            )
            or (
                requested.device_id is not None
                and (requested.device_id, requested.inode_id)
                != (observed.device_id, observed.inode_id)
            )
            or (
                requested.occurrence_id is not None
                and requested.occurrence_id != observed.occurrence_id
            )
            for requested, observed in zip(submitted, discovered)
        ):
            raise ConflictError(
                "submitted artifact manifest or hold state does not match current inventory"
            )
        holds = {item.path: item.retention_hold for item in submitted}
        actions = {item.path: item.reacquisition_action for item in submitted}
        return tuple(
            replace(
                item,
                retention_hold=holds[item.path],
                reacquisition_action=actions[item.path],
            )
            for item in discovered
        )

    def _require_current_dependency_map(
        self,
        goal_id: str,
        artifacts: tuple[ArtifactRef, ...],
        expected_sha256: str,
    ) -> None:
        """Reject a review action if evidence or criterion links changed after display."""

        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ConflictError("cleanup review requires the displayed dependency map digest")
        snapshot = self.service.goal_status(goal_id)
        dependencies = build_artifact_review_dependencies(
            snapshot.facts, snapshot.criteria, artifacts
        )
        if artifact_dependency_map_sha256(dependencies) != expected_sha256:
            raise ConflictError(
                "artifact dependency map changed before the review decision"
            )
        for dependency in dependencies:
            artifact = dependency.artifact
            action = dependency.reacquisition_action
            if action is ReacquisitionAction.NOT_RECORDED:
                raise ConflictError(
                    "cleanup review requires an explicit retention or "
                    "reacquisition action for every artifact"
                )
            if artifact.retention_hold is not None:
                if action is not ReacquisitionAction.RETAIN_UNDER_HOLD:
                    raise ConflictError(
                        "held artifacts require the retain_under_hold review action"
                    )
            elif action is ReacquisitionAction.RETAIN_UNDER_HOLD:
                raise ConflictError(
                    "retain_under_hold requires an active artifact retention hold"
                )
            elif (
                any(
                    item.criterion_status == "open"
                    for item in dependency.evidence_dependencies
                )
                and action is not ReacquisitionAction.REACQUIRE_FROM_SOURCE
            ):
                raise ConflictError(
                    "artifacts linked to open criteria require "
                    "reacquire_from_source or a retention hold"
                )

    def _scan_staging_tree(
        self,
        *,
        discover_artifacts: bool,
        scope_goal_id: str | None = None,
        staging_root_fd: int | None = None,
    ) -> StagingArtifactInventory:
        """Traverse staging with no-follow descriptors and bounded work."""

        scanner = StagingTreeScanner(
            self.config,
            self._hash_staged_file,
            max_entries=MAX_STAGING_SCAN_ENTRIES,
            max_hash_bytes=MAX_STAGING_HASH_BYTES,
        )
        if discover_artifacts:
            inventory = scanner.discover(
                scope_goal_id=scope_goal_id,
                staging_root_fd=staging_root_fd,
            )
            artifacts = self.service.store.bind_staging_artifact_occurrences(
                self.config.project_id, inventory.artifacts
            )
            active_holds = self.service.store.active_staging_artifact_holds(
                self.config.project_id, artifacts
            )
            artifacts = tuple(
                replace(item, retention_hold=active_holds.get(item.path))
                for item in artifacts
            )
            manifest_sha256 = (
                _artifact_manifest_sha256(artifacts)
                if inventory.usage.inventory_complete
                else None
            )
            return replace(
                inventory,
                artifacts=artifacts,
                manifest_sha256=manifest_sha256,
            )
        return scanner.measure(
            scope_goal_id=scope_goal_id,
            staging_root_fd=staging_root_fd,
        )

    @staticmethod
    def _hash_staged_file(
        directory_fd: int,
        filename: str,
        observed: os.stat_result,
        absolute_path: Path,
    ) -> ArtifactRef:
        """Hash one stable regular file through a no-follow descriptor."""

        no_follow = getattr(os, "O_NOFOLLOW", None)
        if no_follow is None or os.open not in os.supports_dir_fd:
            raise OSError("platform lacks safe descriptor-relative reads")
        file_fd = os.open(
            filename,
            os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0),
            dir_fd=directory_fd,
        )
        try:
            return ProjectPlugin._hash_open_staged_file(
                file_fd, observed, absolute_path
            )
        finally:
            os.close(file_fd)

    @staticmethod
    def _hash_open_staged_file(
        file_fd: int,
        observed: os.stat_result,
        absolute_path: Path,
    ) -> ArtifactRef:
        """Hash an opened file only while its identity and content stay stable."""

        before = os.fstat(file_fd)
        observed_identity = (observed.st_dev, observed.st_ino, observed.st_size)
        opened_identity = (before.st_dev, before.st_ino, before.st_size)
        if not stat.S_ISREG(before.st_mode) or opened_identity != observed_identity:
            raise ValueError("artifact changed during inventory discovery")
        digest = hashlib.sha256()
        bytes_read = 0
        with os.fdopen(os.dup(file_fd), "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                bytes_read += len(chunk)
                digest.update(chunk)
        after = os.fstat(file_fd)
        before_state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_state = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if before_state != after_state or bytes_read != before.st_size:
            raise ValueError("artifact changed during inventory discovery")
        return ArtifactRef(
            str(absolute_path),
            digest.hexdigest(),
            device_id=before.st_dev,
            inode_id=before.st_ino,
        )

    def goal_list(
        self, statuses: tuple[GoalStatus, ...] = ()
    ) -> tuple[GoalSnapshot, ...]:
        """List only goals belonging to this plugin's bound project."""

        return self.service.goal_list(statuses)

    def goal_list_page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """List compact project goal cards with bounded pagination."""

        return self.service.goal_list_page(
            offset=offset, limit=limit, statuses=statuses
        )

    def goal_children(self, parent_goal_id: str) -> tuple[GoalSnapshot, ...]:
        """List only direct child tasks of a goal in this project."""

        return self.service.goal_children(parent_goal_id)

    def goal_children_page(
        self,
        request: GoalChildrenPageRequest,
    ) -> GoalListPage:
        """List compact, paginated child cards in this project's boundary."""

        return self.service.goal_children_page(request)

    def goal_reopen(self, goal_id: str, reason: str, next_action: str) -> GoalCard:
        """Reopen one completed goal within this project's scope."""

        with self._active_project_revision_fence():
            return self.service.goal_reopen(goal_id, reason, next_action)

    def goal_amend_criteria(
        self,
        request: GoalCriteriaAmended,
    ) -> GoalCard:
        """Amend criteria through this repository's project-bound service."""

        with self._active_project_revision_fence():
            return self.service.goal_amend_criteria(request)

    def sde_review_queue(self, limit: int = 100) -> tuple[SDEReviewDetail, ...]:
        """List bounded pending SDE review packets in this project only."""

        return self.service.sde_review_queue(limit)

    def sde_assess(
        self,
        request: SDEAssessmentRequest,
    ) -> SDECandidate | None:
        """Create a review proposal only from verified facts in this project."""

        expected_revision = self._capture_active_project_revision()

        def effect_fence():
            """Fence candidate insertion after the external evidence check."""

            return self._project_revision_fence(expected_revision)

        return self.service.sde_assess_with_effect_fence(request, effect_fence)

    def sde_review_detail(self, candidate_id: str) -> SDEReviewDetail:
        """Read one candidate and its selected evidence within this project."""

        return self.service.sde_review_detail(candidate_id)

    def sde_review_packet(
        self,
        candidate_id: str,
        review_artifacts: tuple[ArtifactRef, ...] | None = None,
    ) -> SDEReviewPacket:
        """Compose selected evidence, full goal links, and current staging inventory."""

        detail = self.sde_review_detail(candidate_id)
        goal_snapshot = self.service.goal_status(detail.candidate.goal_id)
        with self._locked_staging_root() as root_fd:
            inventory = self._scan_staging_tree(
                discover_artifacts=True,
                scope_goal_id=detail.candidate.goal_id,
                staging_root_fd=root_fd,
            )
            approved_artifacts = (
                inventory.artifacts
                if review_artifacts is None
                else self._require_current_artifact_inventory(
                    detail.candidate.goal_id,
                    review_artifacts,
                    staging_root_fd=root_fd,
                )
            )
        dependencies = build_artifact_review_dependencies(
            goal_snapshot.facts, goal_snapshot.criteria, approved_artifacts
        )
        return SDEReviewPacket(
            detail=detail,
            artifact_inventory=inventory,
            review_artifacts=approved_artifacts,
            artifact_dependencies=dependencies,
            dependency_map_sha256=artifact_dependency_map_sha256(dependencies),
        )

    def sde_correction_record(
        self,
        correction_id: str,
        candidate_id: str,
        correction: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> SDECorrection:
        """Append a reviewer-authorized correction to a decided SDE."""

        with self._active_project_revision_fence():
            return self.service.sde_correction_record(
                correction_id,
                candidate_id,
                correction,
                rationale,
                authenticated_subject=authenticated_subject,
            )

    def sde_quality_feedback_record(
        self,
        feedback_id: str,
        candidate_id: str,
        label: SDEQualityFeedbackLabel,
        rationale: str = "",
        *,
        authenticated_subject: str | None = None,
    ) -> SDEQualityFeedback:
        """Record one authenticated feedback label after candidate disposition."""

        with self._active_project_revision_fence():
            return self.service.sde_quality_feedback_record(
                feedback_id,
                candidate_id,
                label,
                rationale,
                authenticated_subject=authenticated_subject,
            )

    def sde_quality_feedback_summary(self) -> SDEQualityFeedbackSummary:
        """Return only aggregate labels for this project's reviewed candidates."""

        return self.service.sde_quality_feedback_summary()

    def sde_confirm(
        self,
        request: SDEConfirmationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record disposition and exact cleanup authorization in one review action."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            validated_dependency_map_sha256: str | None = None
            artifacts = request.artifacts
            if request.artifact_inventory_complete:
                candidate = self.sde_review_detail(request.candidate_id).candidate
                artifacts = self._require_current_artifact_inventory(
                    candidate.goal_id, request.artifacts, staging_root_fd=root_fd
                )
                if request.dependency_map_sha256 is None:
                    raise ConflictError(
                        "cleanup review requires the displayed dependency map digest"
                    )
                self._require_current_dependency_map(
                    candidate.goal_id, artifacts, request.dependency_map_sha256
                )
                validated_dependency_map_sha256 = request.dependency_map_sha256
            validated_request = replace(request, artifacts=artifacts)
            with self._project_revision_fence(expected_revision):
                receipt = self.service.sde_confirm(
                    validated_request,
                    authenticated_subject=authenticated_subject,
                )
                if validated_request.artifact_inventory_complete:
                    if validated_dependency_map_sha256 is None:
                        raise ConflictError(
                            "cleanup review did not retain its validated dependency map digest"
                        )
                    self.service.authorize_artifact_cleanup(
                        receipt.receipt_id,
                        _artifact_manifest_sha256(artifacts),
                        validated_dependency_map_sha256,
                        authenticated_subject=authenticated_subject,
                    )
                    receipt = self.service.store.get_receipt(
                        receipt.receipt_id, self.config.project_id
                    )
                return receipt

    def artifact_inventory_complete(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        dependency_map_sha256: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Finalize this project's exact artifact manifest before cleanup."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            receipt = self.service.store.get_receipt(
                receipt_id, self.config.project_id
            )
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, artifacts, staging_root_fd=root_fd
            )
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, dependency_map_sha256
            )
            with self._project_revision_fence(expected_revision):
                return self.service.artifact_inventory_complete(
                    receipt_id,
                    artifacts,
                    authenticated_subject=authenticated_subject,
                )

    def authorize_artifact_cleanup(
        self,
        request: ArtifactCleanupAuthorizationRequest,
        *,
        authenticated_subject: str | None = None,
    ) -> tuple[CleanupAuthorizationReceipt, AuditReceipt]:
        """Recheck a displayed manifest and record compatibility cleanup approval."""

        with self._locked_staging_root() as root_fd:
            expected_revision = self._capture_active_project_revision()
            receipt = self.service.store.get_receipt(
                request.receipt_id, self.config.project_id
            )
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            artifacts = self._require_current_artifact_inventory(
                candidate.goal_id, request.artifacts, staging_root_fd=root_fd
            )
            self._require_current_dependency_map(
                candidate.goal_id, artifacts, request.dependency_map_sha256
            )
            current_manifest = _artifact_manifest_sha256(artifacts)
            if current_manifest != request.manifest_sha256:
                raise ConflictError("cleanup manifest changed before approval")
            with self._project_revision_fence(expected_revision):
                authorization, _receipt = self.service.authorize_artifact_cleanup(
                    request.receipt_id,
                    request.manifest_sha256,
                    request.dependency_map_sha256,
                    authenticated_subject=authenticated_subject,
                )
        self.persist_goal(candidate.goal_id, request.target)
        receipt, _targets = self.service.artifact_purge_status(request.receipt_id)
        authorization = self.service.store.cleanup_authorization(
            request.receipt_id, self.config.project_id
        )
        if authorization is None:
            raise RuntimeError("cleanup authorization receipt was not persisted")
        return authorization, receipt

    def artifact_purge_status(
        self, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Read project-scoped receipt and per-artifact purge outcomes."""

        return self.service.artifact_purge_status(receipt_id)

    def release_artifact_hold(
        self,
        receipt_id: str,
        path: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Release one exact hold through the configured human reviewer."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.release_artifact_hold(
                    receipt_id,
                    path,
                    rationale,
                    authenticated_subject=authenticated_subject,
                )

    def retry_due_purges(self, limit: int = 100) -> tuple[AuditReceipt, ...]:
        """Run one bounded scheduler pass for due, already-authorized purges."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.retry_due_purges(limit)

    def retry_pending_purges(self) -> tuple[AuditReceipt, ...]:
        """Retry only reviewed, persisted, project-scoped pending manifests."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.retry_pending_purges()


def _artifact_manifest_sha256(artifacts: tuple[ArtifactRef, ...]) -> str:
    """Hash the sorted exact path/hash/occurrence inventory for approval."""

    manifest = json.dumps(
        [
            (item.path, item.sha256, item.occurrence_id)
            for item in sorted(artifacts, key=lambda item: item.path)
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()
