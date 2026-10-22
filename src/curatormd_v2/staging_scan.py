"""Bounded, descriptor-relative traversal for project staging inventories."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable

from .models import (
    MAX_ARTIFACTS_PER_RECEIPT,
    ArtifactRef,
    StagingArtifactInventory,
)
from .project_config import ProjectConfig, ProjectConfigError
from .staging_models import (
    MAX_STAGING_SCAN_ENTRIES,
    StagingArtifactClass,
    StagingClassUsage,
    StagingUsage,
)

_STAGING_SCOPE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def _new_artifacts() -> list[ArtifactRef]:
    return []


def _new_class_totals() -> dict[StagingArtifactClass, list[int]]:
    return {}


@dataclass(slots=True)
class _ScanOptions:
    """Immutable operating limits and root descriptors for one scan."""

    root: Path
    no_follow: int
    directory_flag: int
    max_entries: int
    max_hash_bytes: int


@dataclass(slots=True)
class _ScanStatus:
    """Mutable fail-closed completion state for one scan."""

    complete: bool = True
    error_code: str | None = None


@dataclass(slots=True)
class _ScanTotals:
    """Content-free entry and byte counters."""

    entries_scanned: int = 0
    regular_file_count: int = 0
    observed_file_bytes: int = 0
    directory_count: int = 0
    symlink_count: int = 0
    special_file_count: int = 0


@dataclass(slots=True)
class _ArtifactDiscovery:
    """Bounded hash inventory and per-class counters."""

    artifacts: list[ArtifactRef] = field(default_factory=_new_artifacts)
    class_totals: dict[StagingArtifactClass, list[int]] = field(
        default_factory=_new_class_totals
    )
    hashed_bytes: int = 0
    hashing_enabled: bool = False


@dataclass(frozen=True, slots=True)
class _ScannedEntry:
    """One name and its no-follow metadata under an open parent directory."""

    directory_fd: int
    relative_parts: tuple[str, ...]
    name: str
    metadata: os.stat_result


@dataclass(slots=True)
class _ScanState:
    """Working state grouped so traversal helpers keep explicit interfaces."""

    options: _ScanOptions
    scope_goal_id: str | None
    status: _ScanStatus
    totals: _ScanTotals
    discovery: _ArtifactDiscovery
    pending_directories: list[tuple[int, tuple[str, ...]]]


class StagingTreeScanner:
    """Scan one configured staging root without following links or unbounded work."""

    def __init__(
        self,
        config: ProjectConfig,
        hash_staged_file: Callable[
            [int, str, os.stat_result, Path], ArtifactRef
        ],
        *,
        max_entries: int = MAX_STAGING_SCAN_ENTRIES,
        max_hash_bytes: int = 8 * 1024**3,
    ) -> None:
        self._config = config
        self._hash_staged_file = hash_staged_file
        self._max_entries = max_entries
        self._max_hash_bytes = max_hash_bytes

    def measure(
        self,
        *,
        scope_goal_id: str | None = None,
        staging_root_fd: int | None = None,
    ) -> StagingArtifactInventory:
        """Return bounded usage totals without reading artifact contents."""

        return self._scan(
            discover_artifacts=False,
            scope_goal_id=scope_goal_id,
            staging_root_fd=staging_root_fd,
        )

    def discover(
        self,
        *,
        scope_goal_id: str | None = None,
        staging_root_fd: int | None = None,
    ) -> StagingArtifactInventory:
        """Return bounded usage totals and stable artifact hashes."""

        return self._scan(
            discover_artifacts=True,
            scope_goal_id=scope_goal_id,
            staging_root_fd=staging_root_fd,
        )

    def _scan(
        self,
        *,
        discover_artifacts: bool,
        scope_goal_id: str | None,
        staging_root_fd: int | None,
    ) -> StagingArtifactInventory:
        """Share traversal while keeping measurement and discovery explicit."""

        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory_flag = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory_flag is None:
            return _incomplete_inventory("unsupported_platform", scope_goal_id)
        try:
            root = self._config.validated_staging_root()
        except ProjectConfigError:
            return _incomplete_inventory("root_invalid", scope_goal_id)
        initial = self._open_scan_root(
            root, scope_goal_id, staging_root_fd, no_follow, directory_flag
        )
        if isinstance(initial, StagingArtifactInventory):
            return initial
        initial_directory_fd, relative_parts = initial
        state = _ScanState(
            options=_ScanOptions(
                root,
                no_follow,
                directory_flag,
                self._max_entries,
                self._max_hash_bytes,
            ),
            scope_goal_id=scope_goal_id,
            status=_ScanStatus(),
            totals=_ScanTotals(),
            discovery=_ArtifactDiscovery(hashing_enabled=discover_artifacts),
            pending_directories=[(initial_directory_fd, relative_parts)],
        )
        _walk_staging_directories(state, self._hash_staged_file)
        return _build_inventory(state)

    @staticmethod
    def _open_scan_root(
        root: Path,
        scope_goal_id: str | None,
        staging_root_fd: int | None,
        no_follow: int,
        directory_flag: int,
    ) -> tuple[int, tuple[str, ...]] | StagingArtifactInventory:
        """Open the root and optional goal directory without following links."""

        try:
            root_fd = (
                os.dup(staging_root_fd)
                if staging_root_fd is not None
                else os.open(root, os.O_RDONLY | directory_flag | no_follow)
            )
        except PermissionError:
            return _incomplete_inventory("permission_denied", scope_goal_id)
        except OSError:
            return _incomplete_inventory("root_unavailable", scope_goal_id)
        if scope_goal_id is None:
            return root_fd, ()
        if _STAGING_SCOPE_ID_RE.fullmatch(scope_goal_id) is None:
            os.close(root_fd)
            return _incomplete_inventory("scope_invalid", scope_goal_id)
        return _open_goal_directory(root_fd, scope_goal_id, directory_flag, no_follow)


def _walk_staging_directories(
    state: _ScanState,
    hash_staged_file: Callable[[int, str, os.stat_result, Path], ArtifactRef],
) -> None:
    """Traverse the pending directory stack and close every owned descriptor."""

    try:
        while state.pending_directories:
            directory_fd, relative_parts = state.pending_directories.pop()
            _scan_directory(state, directory_fd, relative_parts, hash_staged_file)
            if state.status.error_code == "entry_limit":
                break
    finally:
        for directory_fd, _relative_parts in state.pending_directories:
            os.close(directory_fd)


def _scan_directory(
    state: _ScanState,
    directory_fd: int,
    relative_parts: tuple[str, ...],
    hash_staged_file: Callable[[int, str, os.stat_result, Path], ArtifactRef],
) -> None:
    """Classify all bounded entries in one already-open directory."""

    try:
        with os.scandir(os.dup(directory_fd)) as entries:
            for entry in entries:
                if state.totals.entries_scanned >= state.options.max_entries:
                    _mark_incomplete(state, "entry_limit")
                    break
                state.totals.entries_scanned += 1
                try:
                    metadata = os.stat(
                        entry.name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    _mark_scan_error(state, exc)
                    continue
                _process_staging_entry(
                    state,
                    _ScannedEntry(directory_fd, relative_parts, entry.name, metadata),
                    hash_staged_file,
                )
                if state.status.error_code == "entry_limit":
                    break
    except OSError as exc:
        _mark_scan_error(state, exc)
    finally:
        os.close(directory_fd)


def _process_staging_entry(
    state: _ScanState,
    entry: _ScannedEntry,
    hash_staged_file: Callable[[int, str, os.stat_result, Path], ArtifactRef],
) -> None:
    """Dispatch one no-follow metadata result by filesystem entry type."""

    metadata = entry.metadata
    if stat.S_ISREG(metadata.st_mode):
        _scan_regular_file(state, entry, hash_staged_file)
    elif stat.S_ISDIR(metadata.st_mode):
        state.totals.directory_count += 1
        _queue_staging_directory(state, entry)
    elif stat.S_ISLNK(metadata.st_mode):
        state.totals.symlink_count += 1
        _mark_incomplete(state, "symlink_skipped")
    else:
        state.totals.special_file_count += 1
        _mark_incomplete(state, "special_file_skipped")


def _scan_regular_file(
    state: _ScanState,
    entry: _ScannedEntry,
    hash_staged_file: Callable[[int, str, os.stat_result, Path], ArtifactRef],
) -> None:
    """Count a regular file and optionally hash it within the discovery limits."""

    metadata = entry.metadata
    state.totals.regular_file_count += 1
    state.totals.observed_file_bytes += metadata.st_size
    class_name = (
        entry.relative_parts[1]
        if len(entry.relative_parts) > 1
        else StagingArtifactClass.OTHER.value
    )
    try:
        artifact_class = StagingArtifactClass(class_name)
    except ValueError:
        artifact_class = StagingArtifactClass.OTHER
    class_totals = state.discovery.class_totals.setdefault(artifact_class, [0, 0])
    class_totals[0] += 1
    class_totals[1] += metadata.st_size
    if not state.discovery.hashing_enabled:
        return
    if len(state.discovery.artifacts) >= MAX_ARTIFACTS_PER_RECEIPT:
        state.discovery.hashing_enabled = False
        _mark_incomplete(state, "artifact_limit")
        return
    if state.discovery.hashed_bytes + metadata.st_size > state.options.max_hash_bytes:
        state.discovery.hashing_enabled = False
        _mark_incomplete(state, "hash_byte_limit")
        return
    try:
        artifact = hash_staged_file(
            entry.directory_fd,
            entry.name,
            metadata,
            state.options.root.joinpath(*entry.relative_parts, entry.name),
        )
    except (OSError, ValueError):
        state.discovery.hashing_enabled = False
        _mark_incomplete(state, "changed_during_scan")
        return
    state.discovery.artifacts.append(artifact)
    state.discovery.hashed_bytes += metadata.st_size


def _queue_staging_directory(
    state: _ScanState,
    entry: _ScannedEntry,
) -> None:
    """Open and queue one child directory using a no-follow descriptor."""

    try:
        child_fd = os.open(
            entry.name,
            os.O_RDONLY | state.options.directory_flag | state.options.no_follow,
            dir_fd=entry.directory_fd,
        )
    except OSError as exc:
        _mark_scan_error(state, exc)
        return
    state.pending_directories.append(
        (child_fd, entry.relative_parts + (entry.name,))
    )


def _mark_scan_error(state: _ScanState, error: OSError) -> None:
    """Keep filesystem failures content-free and fail the inventory closed."""

    code = "permission_denied" if isinstance(error, PermissionError) else "scan_error"
    _mark_incomplete(state, code)


def _mark_incomplete(state: _ScanState, error_code: str) -> None:
    state.status.complete = False
    state.status.error_code = state.status.error_code or error_code


def _build_inventory(state: _ScanState) -> StagingArtifactInventory:
    """Freeze scan counters and a canonical artifact manifest."""

    totals = state.totals
    usage = StagingUsage(
        entries_scanned=totals.entries_scanned,
        regular_file_count=totals.regular_file_count,
        observed_file_bytes=totals.observed_file_bytes,
        directory_count=totals.directory_count,
        symlink_count=totals.symlink_count,
        special_file_count=totals.special_file_count,
        inventory_complete=state.status.complete,
        error_code=state.status.error_code,
        classes=tuple(
            StagingClassUsage(artifact_class, class_totals[0], class_totals[1])
            for artifact_class, class_totals in sorted(
                state.discovery.class_totals.items(), key=lambda item: item[0].value
            )
        ),
    )
    artifacts = tuple(sorted(state.discovery.artifacts, key=lambda item: item.path))
    manifest_sha256 = _manifest_hash(artifacts) if state.status.complete else None
    return StagingArtifactInventory(
        artifacts, usage, manifest_sha256, state.scope_goal_id
    )


def _manifest_hash(artifacts: tuple[ArtifactRef, ...]) -> str:
    """Hash the sorted exact path/digest pairs using the canonical JSON form."""

    canonical = json.dumps(
        [(item.path, item.sha256) for item in artifacts],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _incomplete_inventory(
    error_code: str, scope_goal_id: str | None = None
) -> StagingArtifactInventory:
    return StagingArtifactInventory(
        (), StagingUsage(0, 0, 0, 0, 0, 0, False, error_code), None,
        scope_goal_id,
    )


def _empty_goal_inventory(goal_id: str) -> StagingArtifactInventory:
    """Represent a missing per-goal directory as a complete empty manifest."""

    return StagingArtifactInventory(
        (), StagingUsage(0, 0, 0, 0, 0, 0, True, None),
        hashlib.sha256(b"[]").hexdigest(), goal_id,
    )


def _open_goal_directory(
    root_fd: int,
    goal_id: str,
    directory_flag: int,
    no_follow: int,
) -> tuple[int, tuple[str, ...]] | StagingArtifactInventory:
    """Open one scope after the root has been established."""

    try:
        goal_fd = os.open(
            goal_id,
            os.O_RDONLY | directory_flag | no_follow,
            dir_fd=root_fd,
        )
    except FileNotFoundError:
        os.close(root_fd)
        return _empty_goal_inventory(goal_id)
    except PermissionError:
        os.close(root_fd)
        return _incomplete_inventory("permission_denied", goal_id)
    except OSError:
        os.close(root_fd)
        return _incomplete_inventory("scope_unavailable", goal_id)
    os.close(root_fd)
    return goal_fd, (goal_id,)
