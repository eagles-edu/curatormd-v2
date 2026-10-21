"""Thin repository-bound plugin adapter over the Curator V2 global service."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import BinaryIO, Generator

from .evidence import EvidenceVerifier
from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    EventQueueStatus,
    GoalStarted,
)
from .markdown_persistence import (
    MarkdownPersistenceAdapter,
    MarkdownProjectReconciliation,
    MarkdownProjectionResult,
    MarkdownReconciliationResult,
)
from .models import (
    MAX_ARTIFACTS_PER_RECEIPT,
    ArtifactRef,
    AuditReceipt,
    FactArchiveReceipt,
    FactCompactionProposal,
    GoalCard,
    GoalListPage,
    GoalBulletProjection,
    GoalSnapshot,
    GoalStatus,
    ProjectActivitySnapshot,
    Materiality,
    ProjectStorageUsage,
    ProjectOperationalCounts,
    ReviewDecision,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    StagingArtifactClass,
    StagingArtifactInventory,
    StagingClassUsage,
    StagingUsage,
    SuccessCriterion,
)
from .project_config import ProjectConfig, ProjectConfigError
from .purge import ArtifactPurger
from .reviews import ReviewAuthorizer
from .service import CuratorService, PurgeTargetStatus
from .store import ConflictError, CuratorStore, NotFoundError

MAX_STAGING_SCAN_ENTRIES = 10_000
MAX_STAGING_HASH_BYTES = 8 * 1024**3
MAX_STAGED_ARTIFACT_BYTES = 64 * 1024**2
MAX_GOAL_STAGING_BYTES = 256 * 1024**2
MAX_GOAL_STAGING_FILES = MAX_ARTIFACTS_PER_RECEIPT
_STAGING_SCOPE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_STAGING_CLASS_RE = re.compile(r"^(raw-chat|cue|import|scratch|generated|duplicate)$")


class ProjectPlugin:
    """Expose only configured project paths and project-scoped goal operations."""

    def __init__(self, config: ProjectConfig, service: CuratorService) -> None:
        if service.project_id != config.project_id:
            raise ProjectConfigError("service project does not match repository config")
        self.config = config
        self.service = service

    @contextmanager
    def _locked_staging_root(self) -> Generator[int, None, None]:
        """Serialize supported plugin operations on this staging directory."""

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
            yield root_fd
        finally:
            try:
                fcntl.flock(root_fd, fcntl.LOCK_UN)
            finally:
                os.close(root_fd)

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
        return cls(config, service)

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
            adapter = MarkdownPersistenceAdapter(
                self.config,
                self.service.store,
                target,
                self.service.evidence_verifier,
            )
            projection = adapter.persist_goal(goal_id)
            unpersisted = tuple(
                receipt
                for receipt in self.service.store.receipts_for_goal(
                    goal_id, self.config.project_id
                )
                if not receipt.canonical_persisted
            )
            for receipt in unpersisted:
                adapter.verify_projection(projection)
                self.service.mark_canonical_persisted(
                    receipt.receipt_id,
                    projection.target.relative_to(self.config.project_root).as_posix(),
                    projection.sha256,
                )
            if unpersisted:
                projection = adapter.persist_goal(goal_id)
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

    def process_event(self, event: EventEnvelope) -> EventInboxReceipt:
        """Apply an event only inside this plugin's project binding.

        Checklist snapshots are revalidated at the repository boundary so a
        generic event/MCP caller cannot invent a checklist line or revision.
        Successfully processed retries remain idempotent after the source file
        later changes; the store still rejects changed payload reuse.
        """

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

        return self.service.process_event(event)

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
        parent_goal_id: str,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        *,
        owner: str | None = None,
        next_action: str | None = None,
        depends_on_goal_ids: tuple[str, ...] = (),
        source_event_id: str | None = None,
    ) -> GoalCard:
        """Start an explicitly accepted child task with its own criteria.

        This adapter does not turn a proposal into accepted work on its own:
        invocation is the caller's explicit acceptance, and the parent remains
        the provenance link. The service enforces same-project parent and
        dependency rules and rejects missing criteria.
        """

        return self.service.goal_start(
            problem,
            success_criteria,
            owner=owner,
            parent_goal_id=parent_goal_id,
            depends_on_goal_ids=depends_on_goal_ids,
            initial_status=GoalStatus.PLANNED,
            next_action=next_action,
            source_event_id=source_event_id,
        )

    def goal_start_from_checklist(
        self,
        checklist_id: str,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        *,
        exact_item_text: str,
        owner: str | None = None,
        next_action: str | None = None,
        parent_goal_id: str | None = None,
        depends_on_goal_ids: tuple[str, ...] = (),
        initial_status: GoalStatus = GoalStatus.PLANNED,
        source_event_id: str | None = None,
    ) -> GoalCard:
        """Start a goal with an exact checklist line and source-file revision."""

        source_version, source_text = self.config.checklist_snapshot(
            checklist_id, exact_item_text
        )
        return self.service.goal_start(
            problem,
            success_criteria,
            owner=owner,
            checklist_id=checklist_id,
            checklist_version=source_version,
            checklist_source_text=source_text,
            parent_goal_id=parent_goal_id,
            depends_on_goal_ids=depends_on_goal_ids,
            initial_status=initial_status,
            next_action=next_action,
            source_event_id=source_event_id,
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

        return self.service.goal_activate(goal_id, reason, expected_lifecycle_revision)

    def goal_bullet_projection(self, goal_id: str) -> GoalBulletProjection:
        """Return compact truth-labeled bullets inside this project boundary."""

        return self.service.goal_bullet_projection(goal_id)

    def goal_report(
        self,
        goal_id: str,
        fact_offset: int = 0,
        fact_limit: int = 16,
        child_offset: int = 0,
        sde_offset: int = 0,
        receipt_offset: int = 0,
    ) -> str:
        """Render a bounded, user-readable report inside this project scope."""

        return self.service.goal_report(
            goal_id,
            fact_offset=fact_offset,
            fact_limit=fact_limit,
            child_offset=child_offset,
            sde_offset=sde_offset,
            receipt_offset=receipt_offset,
        )

    def fact_compaction_propose(
        self, goal_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Preview routine facts eligible for project-scoped archival."""

        return self.service.fact_compaction_propose(goal_id, max_facts)

    def fact_compaction_approve(
        self,
        compaction_id: str,
        goal_id: str,
        fact_ids: tuple[str, ...],
        source_sha256: str,
        reviewer_id: str,
        approval_reason: str,
    ) -> FactArchiveReceipt:
        """Apply a hash-matched archive only after host review authorization."""

        return self.service.fact_compaction_approve(
            compaction_id,
            goal_id,
            fact_ids,
            source_sha256,
            reviewer_id,
            approval_reason,
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
    ) -> tuple[EventQueueStatus, ProjectOperationalCounts, ProjectStorageUsage]:
        """Read consistent SQLite health inputs and scan bounded staging state."""

        queue, counts, usage = self.service.store.project_health_inputs(
            self.config.project_id
        )
        try:
            with self._locked_staging_root() as root_fd:
                staging = self._scan_staging_tree(
                    discover_artifacts=False, staging_root_fd=root_fd
                ).usage
        except ProjectConfigError:
            staging = StagingUsage(
                0, 0, 0, 0, 0, 0, False, "staging_root_unavailable"
            )
        except OSError:
            staging = StagingUsage(
                0, 0, 0, 0, 0, 0, False, "staging_lock_unavailable"
            )
        return queue, counts, replace(
            usage,
            staging=staging,
            staging_project_byte_limit=self.config.staging_max_project_bytes,
            staging_project_file_limit=self.config.staging_max_project_files,
        )

    def discover_staging_artifacts(
        self, goal_id: str
    ) -> StagingArtifactInventory:
        """Discover only artifacts staged beneath this project goal's directory."""

        if not _STAGING_SCOPE_ID_RE.fullmatch(goal_id):
            raise ValueError("goal_id must be a bounded opaque identifier")
        self.service.store.get_goal(goal_id, self.config.project_id)
        with self._locked_staging_root() as root_fd:
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
        """

        if not _STAGING_SCOPE_ID_RE.fullmatch(goal_id):
            raise ValueError("goal_id must be a bounded opaque identifier")
        if not _STAGING_CLASS_RE.fullmatch(artifact_class):
            raise ValueError("artifact_class is not a supported temporary class")
        if not _STAGING_SCOPE_ID_RE.fullmatch(artifact_id):
            raise ValueError("artifact_id must be a bounded opaque identifier")
        self.service.store.get_goal(goal_id, self.config.project_id)
        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            raise ProjectConfigError("platform lacks safe staging write primitives")

        with self._locked_staging_root() as root_fd:
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

        inventory = self._scan_staging_tree(
            discover_artifacts=True,
            scope_goal_id=goal_id,
            staging_root_fd=root_fd,
        )
        if not inventory.usage.inventory_complete:
            raise ConflictError("cannot stage into an incompletely inventoried goal scope")
        if self.service.store.pending_receipts_for_goal(
            goal_id, self.config.project_id
        ):
            raise ConflictError("cannot stage while this goal has a pending purge receipt")
        if len(inventory.artifacts) >= MAX_GOAL_STAGING_FILES:
            raise ConflictError("goal staging file-count ceiling reached")
        existing_bytes = sum(self._artifact_size(item.path) for item in inventory.artifacts)
        if existing_bytes >= MAX_GOAL_STAGING_BYTES:
            raise ConflictError("goal staging byte ceiling reached")

        project_inventory = None
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

        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            raise ProjectConfigError("platform lacks safe staging write primitives")

        goal_fd = class_fd = temp_fd = -1
        temp_name = f".curator-v2-{secrets.token_hex(16)}.partial"
        final_name = f"{artifact_id}.bin"
        try:
            try:
                os.mkdir(goal_id, mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
            goal_fd = os.open(
                goal_id, os.O_RDONLY | directory_flag | no_follow, dir_fd=root_fd
            )
            try:
                os.mkdir(artifact_class, mode=0o700, dir_fd=goal_fd)
            except FileExistsError:
                pass
            class_fd = os.open(
                artifact_class,
                os.O_RDONLY | directory_flag | no_follow,
                dir_fd=goal_fd,
            )
            temp_fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow,
                0o600,
                dir_fd=class_fd,
            )
            digest = hashlib.sha256()
            total = 0
            with os.fdopen(temp_fd, "wb") as target:
                temp_fd = -1
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_STAGED_ARTIFACT_BYTES:
                        raise ConflictError("artifact exceeds the per-file byte ceiling")
                    if existing_bytes + total > MAX_GOAL_STAGING_BYTES:
                        raise ConflictError("goal staging byte ceiling reached")
                    if (
                        project_inventory is not None
                        and self.config.staging_max_project_bytes is not None
                        and project_inventory.usage.observed_file_bytes + total
                        > self.config.staging_max_project_bytes
                    ):
                        raise ConflictError("project staging byte budget reached")
                    target.write(chunk)
                    digest.update(chunk)
                target.flush()
                os.fsync(target.fileno())
            # link() is no-clobber: a producer retry cannot overwrite evidence.
            os.link(
                temp_name,
                final_name,
                src_dir_fd=class_fd,
                dst_dir_fd=class_fd,
                follow_symlinks=False,
            )
            os.unlink(temp_name, dir_fd=class_fd)
            os.fsync(class_fd)
            return ArtifactRef(
                str(
                    self.config.staging_root
                    / goal_id
                    / artifact_class
                    / final_name
                ),
                digest.hexdigest(),
            )
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            if class_fd >= 0:
                try:
                    os.unlink(temp_name, dir_fd=class_fd)
                except FileNotFoundError:
                    pass
                os.close(class_fd)
            if goal_fd >= 0:
                os.close(goal_fd)

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
    ) -> None:
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
        submitted_manifest = tuple(
            (item.path, item.sha256)
            for item in sorted(artifacts, key=lambda item: item.path)
        )
        discovered_manifest = tuple(
            (item.path, item.sha256)
            for item in sorted(inventory.artifacts, key=lambda item: item.path)
        )
        if submitted_manifest != discovered_manifest:
            raise ConflictError(
                "submitted artifact manifest does not match current staging inventory"
            )

    def _scan_staging_tree(
        self,
        *,
        discover_artifacts: bool,
        scope_goal_id: str | None = None,
        staging_root_fd: int | None = None,
    ) -> StagingArtifactInventory:
        """Traverse staging with no-follow descriptors and bounded work."""

        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            return self._incomplete_inventory("unsupported_platform", scope_goal_id)
        try:
            root = self.config.validated_staging_root()
        except ProjectConfigError:
            return self._incomplete_inventory("root_invalid", scope_goal_id)
        try:
            root_fd = (
                os.dup(staging_root_fd)
                if staging_root_fd is not None
                else os.open(root, os.O_RDONLY | directory_flag | no_follow)
            )
        except PermissionError:
            return self._incomplete_inventory("permission_denied", scope_goal_id)
        except OSError:
            return self._incomplete_inventory("root_unavailable", scope_goal_id)

        if scope_goal_id is not None:
            if not _STAGING_SCOPE_ID_RE.fullmatch(scope_goal_id):
                os.close(root_fd)
                return self._incomplete_inventory("scope_invalid", scope_goal_id)
            try:
                goal_fd = os.open(
                    scope_goal_id,
                    os.O_RDONLY | directory_flag | no_follow,
                    dir_fd=root_fd,
                )
            except FileNotFoundError:
                os.close(root_fd)
                return self._empty_goal_inventory(scope_goal_id)
            except PermissionError:
                os.close(root_fd)
                return self._incomplete_inventory("permission_denied", scope_goal_id)
            except OSError:
                os.close(root_fd)
                return self._incomplete_inventory("scope_unavailable", scope_goal_id)
            os.close(root_fd)
            root_fd = -1
            initial_directory_fd = goal_fd
            initial_relative_parts = (scope_goal_id,)
        else:
            initial_directory_fd = root_fd
            initial_relative_parts = ()

        entries_scanned = 0
        regular_file_count = 0
        observed_file_bytes = 0
        directory_count = 0
        symlink_count = 0
        special_file_count = 0
        class_totals: dict[StagingArtifactClass, list[int]] = {}
        complete = True
        error_code: str | None = None
        artifacts: list[ArtifactRef] = []
        hashed_bytes = 0
        hashing_enabled = discover_artifacts
        pending_directories: list[tuple[int, tuple[str, ...]]] = [
            (initial_directory_fd, initial_relative_parts)
        ]
        try:
            while pending_directories:
                directory_fd, relative_parts = pending_directories.pop()
                try:
                    with os.scandir(os.dup(directory_fd)) as entries:
                        for entry in entries:
                            if entries_scanned >= MAX_STAGING_SCAN_ENTRIES:
                                complete = False
                                error_code = error_code or "entry_limit"
                                break
                            entries_scanned += 1
                            try:
                                metadata = os.stat(
                                    entry.name,
                                    dir_fd=directory_fd,
                                    follow_symlinks=False,
                                )
                            except OSError as exc:
                                complete = False
                                if error_code is None:
                                    error_code = (
                                        "permission_denied"
                                        if isinstance(exc, PermissionError)
                                        else "scan_error"
                                    )
                                continue
                            if stat.S_ISREG(metadata.st_mode):
                                regular_file_count += 1
                                observed_file_bytes += metadata.st_size
                                class_name = (
                                    relative_parts[1]
                                    if len(relative_parts) > 1
                                    else StagingArtifactClass.OTHER.value
                                )
                                try:
                                    artifact_class = StagingArtifactClass(class_name)
                                except ValueError:
                                    artifact_class = StagingArtifactClass.OTHER
                                totals = class_totals.setdefault(artifact_class, [0, 0])
                                totals[0] += 1
                                totals[1] += metadata.st_size
                                if hashing_enabled:
                                    if len(artifacts) >= MAX_ARTIFACTS_PER_RECEIPT:
                                        complete = False
                                        error_code = error_code or "artifact_limit"
                                        hashing_enabled = False
                                    elif (
                                        hashed_bytes + metadata.st_size
                                        > MAX_STAGING_HASH_BYTES
                                    ):
                                        complete = False
                                        error_code = error_code or "hash_byte_limit"
                                        hashing_enabled = False
                                    else:
                                        try:
                                            artifact = self._hash_staged_file(
                                                directory_fd,
                                                entry.name,
                                                metadata,
                                                root.joinpath(*relative_parts, entry.name),
                                            )
                                        except (OSError, ValueError):
                                            complete = False
                                            error_code = error_code or "changed_during_scan"
                                            hashing_enabled = False
                                        else:
                                            artifacts.append(artifact)
                                            hashed_bytes += metadata.st_size
                            elif stat.S_ISDIR(metadata.st_mode):
                                directory_count += 1
                                try:
                                    child_fd = os.open(
                                        entry.name,
                                        os.O_RDONLY | directory_flag | no_follow,
                                        dir_fd=directory_fd,
                                    )
                                except OSError as exc:
                                    complete = False
                                    if error_code is None:
                                        error_code = (
                                            "permission_denied"
                                            if isinstance(exc, PermissionError)
                                            else "scan_error"
                                        )
                                else:
                                    pending_directories.append(
                                        (child_fd, relative_parts + (entry.name,))
                                    )
                            elif stat.S_ISLNK(metadata.st_mode):
                                symlink_count += 1
                                complete = False
                                error_code = error_code or "symlink_skipped"
                            else:
                                special_file_count += 1
                                complete = False
                                error_code = error_code or "special_file_skipped"
                        if not complete and error_code == "entry_limit":
                            break
                except OSError as exc:
                    complete = False
                    if error_code is None:
                        error_code = (
                            "permission_denied"
                            if isinstance(exc, PermissionError)
                            else "scan_error"
                        )
                finally:
                    os.close(directory_fd)
                if error_code == "entry_limit":
                    break
        finally:
            for directory_fd, _relative_parts in pending_directories:
                os.close(directory_fd)

        usage = StagingUsage(
            entries_scanned=entries_scanned,
            regular_file_count=regular_file_count,
            observed_file_bytes=observed_file_bytes,
            directory_count=directory_count,
            symlink_count=symlink_count,
            special_file_count=special_file_count,
            inventory_complete=complete,
            error_code=error_code,
            classes=tuple(
                StagingClassUsage(artifact_class, totals[0], totals[1])
                for artifact_class, totals in sorted(
                    class_totals.items(), key=lambda item: item[0].value
                )
            ),
        )
        sorted_artifacts = tuple(sorted(artifacts, key=lambda item: item.path))
        manifest_sha256 = None
        if complete:
            canonical_manifest = json.dumps(
                [(item.path, item.sha256) for item in sorted_artifacts],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            manifest_sha256 = hashlib.sha256(
                canonical_manifest.encode("utf-8")
            ).hexdigest()
        return StagingArtifactInventory(
            sorted_artifacts, usage, manifest_sha256, scope_goal_id
        )

    @staticmethod
    def _incomplete_inventory(
        error_code: str, scope_goal_id: str | None = None
    ) -> StagingArtifactInventory:
        return StagingArtifactInventory(
            (), StagingUsage(0, 0, 0, 0, 0, 0, False, error_code), None,
            scope_goal_id,
        )

    @staticmethod
    def _empty_goal_inventory(goal_id: str) -> StagingArtifactInventory:
        """Represent a missing per-goal directory as a complete empty manifest."""

        manifest_sha256 = hashlib.sha256(b"[]").hexdigest()
        return StagingArtifactInventory(
            (), StagingUsage(0, 0, 0, 0, 0, 0, True, None),
            manifest_sha256, goal_id,
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
            return ArtifactRef(str(absolute_path), digest.hexdigest())
        finally:
            os.close(file_fd)

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
        parent_goal_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """List compact, paginated child cards in this project's boundary."""

        return self.service.goal_children_page(
            parent_goal_id,
            offset=offset,
            limit=limit,
            statuses=statuses,
        )

    def goal_reopen(self, goal_id: str, reason: str, next_action: str) -> GoalCard:
        """Reopen one completed goal within this project's scope."""

        return self.service.goal_reopen(goal_id, reason, next_action)

    def goal_amend_criteria(
        self,
        goal_id: str,
        expected_revision: int,
        success_criteria: tuple[SuccessCriterion, ...],
        reason: str,
        next_action: str,
    ) -> GoalCard:
        """Amend criteria through this repository's project-bound service."""

        return self.service.goal_amend_criteria(
            goal_id, expected_revision, success_criteria, reason, next_action
        )

    def sde_review_queue(self, limit: int = 100) -> tuple[SDEReviewDetail, ...]:
        """List bounded pending SDE review packets in this project only."""

        return self.service.sde_review_queue(limit)

    def sde_assess(
        self,
        goal_id: str,
        materiality: Materiality,
        rationale: str,
        fact_ids: tuple[str, ...],
        impact: str | None = None,
        retrieval_value: str | None = None,
    ) -> SDECandidate | None:
        """Create a review proposal only from verified facts in this project."""

        return self.service.sde_assess(
            goal_id, materiality, rationale, fact_ids, impact, retrieval_value
        )

    def sde_review_detail(self, candidate_id: str) -> SDEReviewDetail:
        """Read one candidate and its selected evidence within this project."""

        return self.service.sde_review_detail(candidate_id)

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
        candidate_id: str,
        decision: ReviewDecision,
        artifacts: tuple[ArtifactRef, ...],
        *,
        artifact_inventory_complete: bool,
        rationale: str | None = None,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Record a host-authorized review; cleanup stays behind persistence."""

        with self._locked_staging_root() as root_fd:
            if artifact_inventory_complete:
                candidate = self.sde_review_detail(candidate_id).candidate
                self._require_current_artifact_inventory(
                    candidate.goal_id, artifacts, staging_root_fd=root_fd
                )
            return self.service.sde_confirm(
                candidate_id,
                decision,
                artifacts,
                artifact_inventory_complete=artifact_inventory_complete,
                rationale=rationale,
                authenticated_subject=authenticated_subject,
            )

    def artifact_inventory_complete(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Finalize this project's exact artifact manifest before cleanup."""

        with self._locked_staging_root() as root_fd:
            receipt = self.service.store.get_receipt(
                receipt_id, self.config.project_id
            )
            candidate = self.sde_review_detail(receipt.candidate_id).candidate
            self._require_current_artifact_inventory(
                candidate.goal_id, artifacts, staging_root_fd=root_fd
            )
            return self.service.artifact_inventory_complete(
                receipt_id,
                artifacts,
                authenticated_subject=authenticated_subject,
            )

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
            return self.service.release_artifact_hold(
                receipt_id,
                path,
                rationale,
                authenticated_subject=authenticated_subject,
            )

    def retry_due_purges(self, limit: int = 100) -> tuple[AuditReceipt, ...]:
        """Run one bounded scheduler pass for due, already-authorized purges."""

        with self._locked_staging_root():
            return self.service.retry_due_purges(limit)

    def retry_pending_purges(self) -> tuple[AuditReceipt, ...]:
        """Retry only reviewed, persisted, project-scoped pending manifests."""

        with self._locked_staging_root():
            return self.service.retry_pending_purges()
