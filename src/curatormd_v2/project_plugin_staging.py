"""Project staging, inventory, and expiry operations for the repository adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import BinaryIO, ContextManager, Mapping

from .events import EventQueueStatus
from .models import (
    MAX_ARTIFACTS_PER_RECEIPT,
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    ExpiryPurgeReceipt,
    ProjectOperationalCounts,
    ProjectStorageUsage,
    PurgeFailureCode,
    ReacquisitionAction,
    StagingArtifactInventory,
    StagingExpirySnapshot,
    utc_now,
)
from .project_config import ProjectConfig, ProjectConfigError
from .purge import PurgeError
from .read_models import artifact_dependency_map_sha256, build_artifact_review_dependencies
from .service import CuratorService
from .staging_models import MAX_STAGING_SCAN_ENTRIES, StagingUsage
from .staging_scan import StagingTreeScanner
from .staging_write import StagingArtifactWriteRequest, StagingWriteLimits, write_staged_artifact
from .store import ConflictError

MAX_STAGING_HASH_BYTES = 8 * 1024**3
MAX_STAGED_ARTIFACT_BYTES = 64 * 1024**2
MAX_GOAL_STAGING_BYTES = 256 * 1024**2
MAX_GOAL_STAGING_FILES = MAX_ARTIFACTS_PER_RECEIPT
_STAGING_SCOPE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
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

    eligible: list[tuple[datetime, ArtifactRef]] = []
    unknown_age_count = 0
    pending_sde_artifact_count = 0
    for artifact in artifacts:
        expiry_state = _artifact_expiry_state(
            artifact.path, timestamps, readiness, cutoff
        )
        if expiry_state is None:
            unknown_age_count += 1
            continue
        age_eligible, review_ready, pending_sde_count, staged_at = expiry_state
        if pending_sde_count:
            if age_eligible or review_ready:
                pending_sde_artifact_count += 1
            # Pending review delays prompt post-record expiry, but it must not
            # extend transient-source retention beyond the approved 72 hours.
            if not age_eligible:
                continue
        if age_eligible or review_ready:
            eligible.append((staged_at, artifact))
    eligible.sort(key=lambda item: (item[0], item[1].path))
    return (
        tuple(artifact for _, artifact in eligible),
        unknown_age_count,
        pending_sde_artifact_count,
    )

def _artifact_expiry_state(
    path: str,
    timestamps: Mapping[str, str],
    readiness: Mapping[str, tuple[bool, bool, int]],
    cutoff: datetime,
) -> tuple[bool, bool, int, datetime] | None:
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
    staged_at_utc = parsed.astimezone(UTC)
    return (
        staged_at_utc <= cutoff,
        fact_after_stage or review_after_stage,
        pending_sde_count,
        staged_at_utc,
    )

def _expiry_manifest_sha256(artifacts: tuple[ArtifactRef, ...]) -> str:
    """Hash the exact eligible path/digest/occurrence triples in order."""

    manifest = json.dumps(
        [(item.path, item.sha256, item.occurrence_id) for item in artifacts],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()

def artifact_manifest_sha256(artifacts: tuple[ArtifactRef, ...]) -> str:
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

class ProjectStagingMixin(ABC):
    """Project plugin methods for staging and expiry operations."""

    config: ProjectConfig
    service: CuratorService

    @abstractmethod
    def _locked_staging_root(self) -> ContextManager[int]:
        raise NotImplementedError

    @abstractmethod
    def _active_project_revision_fence(self) -> ContextManager[None]:
        raise NotImplementedError

    @abstractmethod
    def _capture_active_project_revision(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def _project_revision_fence(
        self, _expected_revision: int
    ) -> ContextManager[None]:
        raise NotImplementedError

    def storage_usage(self: ProjectStagingMixin) -> ProjectStorageUsage:
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
        self: ProjectStagingMixin,
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
        self: ProjectStagingMixin, goal_id: str
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

    def discover_project_staging_artifacts(self: ProjectStagingMixin) -> StagingArtifactInventory:
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

    def review_staging_inventory(self: ProjectStagingMixin) -> StagingArtifactInventory:
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
        self: ProjectStagingMixin, now: datetime | None = None
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
        self: ProjectStagingMixin, root_fd: int, observed_at: datetime
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
        self: ProjectStagingMixin, expired: tuple[ArtifactRef, ...]
    ) -> tuple[tuple[ArtifactRef, ...], tuple[ArtifactRef, ...]]:
        """Separate holds while preserving oldest-first proposal order."""

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
            for item in expired
            if item.path in active_holds
        )
        eligible = tuple(
            item
            for item in expired
            if item.path not in active_holds
        )
        return eligible, held

    def approve_expired_staging_inventory(
        self: ProjectStagingMixin,
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

    def expiry_purge_receipt(self: ProjectStagingMixin, receipt_id: str) -> ExpiryPurgeReceipt:
        """Read the durable project-scoped result of an expiry approval."""

        return self.service.store.expiry_purge_receipt(
            receipt_id, self.config.project_id
        )

    def retry_due_expiry_purges(
        self: ProjectStagingMixin, limit: int = 100
    ) -> tuple[ExpiryPurgeReceipt, ...]:
        """Retry only due targets from durable attended expiry approvals."""

        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self._retry_due_expiry_purges_locked(limit)

    def retry_due_purge_pass(
        self: ProjectStagingMixin, limit: int = 100
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
        self: ProjectStagingMixin, limit: int
    ) -> tuple[ExpiryPurgeReceipt, ...]:
        receipts = self.service.store.due_expiry_purge_receipts(
            self.config.project_id, limit
        )
        return tuple(self._process_expiry_purge(item) for item in receipts)

    def retry_expiry_purge(self: ProjectStagingMixin, receipt_id: str) -> ExpiryPurgeReceipt:
        """Retry due targets from one exact, previously approved receipt."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                self.service.store.expiry_purge_receipt(
                    receipt_id, self.config.project_id
                )
                return self._process_expiry_purge(receipt_id)

    def _process_expiry_purge(self: ProjectStagingMixin, receipt_id: str) -> ExpiryPurgeReceipt:
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
        self: ProjectStagingMixin,
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
        self: ProjectStagingMixin,
        root_fd: int,
        goal_id: str,
        artifact_class: str,
        artifact_id: str,
        source: BinaryIO,
    ) -> ArtifactRef:
        """Publish a producer artifact while the project staging lock is held."""

        existing_bytes, project_usage, existing_artifact = self._staging_budget_snapshot(
            root_fd, goal_id, artifact_class, artifact_id
        )
        return write_staged_artifact(
            self.config,
            self.service.store.record_staging_artifact_time,
            self.service.store.bind_staging_artifact_occurrences,
            StagingArtifactWriteRequest(
                root_fd,
                goal_id,
                artifact_class,
                artifact_id,
                source,
                existing_bytes,
                project_usage,
                existing_artifact,
            ),
            StagingWriteLimits(
                MAX_STAGED_ARTIFACT_BYTES,
                MAX_GOAL_STAGING_BYTES,
            ),
        )

    def _staging_budget_snapshot(
        self: ProjectStagingMixin,
        root_fd: int,
        goal_id: str,
        artifact_class: str,
        artifact_id: str,
    ) -> tuple[int, StagingUsage | None, ArtifactRef | None]:
        """Check complete inventories and read optional project thresholds."""

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
        existing_bytes = sum(
            self._artifact_size(item.path) for item in inventory.artifacts
        )
        existing_files = len(inventory.artifacts)
        target_path = str(
            self.config.staging_root
            / goal_id
            / artifact_class
            / f"{artifact_id}.bin"
        )
        existing_artifact = next(
            (item for item in inventory.artifacts if item.path == target_path), None
        )
        if existing_artifact is None:
            if existing_files >= MAX_GOAL_STAGING_FILES:
                raise ConflictError("goal staging file-count ceiling reached")
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
            project_usage = project_inventory.usage
        return existing_bytes, project_usage, existing_artifact

    @staticmethod
    def _artifact_size(path: str) -> int:
        """Read a no-follow regular-file size from a discovered manifest path."""

        metadata = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode):
            raise ConflictError("staged artifact changed after inventory discovery")
        return metadata.st_size

    def _require_current_artifact_inventory(
        self: ProjectStagingMixin,
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
        self: ProjectStagingMixin,
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
        self: ProjectStagingMixin,
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
                artifact_manifest_sha256(artifacts)
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
            return ProjectStagingMixin._hash_open_staged_file(
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
