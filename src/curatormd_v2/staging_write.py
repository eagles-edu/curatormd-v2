"""Bounded atomic writes for temporary project staging artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
import secrets
import sqlite3
import stat
from typing import BinaryIO, Callable

from .models import ArtifactRef, new_id
from .project_config import ProjectConfig, ProjectConfigError
from .staging_models import StagingUsage
from .store import ConflictError


@dataclass(frozen=True, slots=True)
class StagingArtifactWriteRequest:
    """Validated goal-scoped inputs and current usage for one staged file."""

    staging_root_fd: int
    goal_id: str
    artifact_class: str
    artifact_id: str
    source: BinaryIO
    existing_goal_bytes: int
    project_usage: StagingUsage | None
    existing_artifact: ArtifactRef | None


@dataclass(frozen=True, slots=True)
class StagingWriteLimits:
    """Hard per-artifact and per-goal ceilings for one artifact write."""

    max_artifact_bytes: int
    max_goal_bytes: int


@dataclass(frozen=True, slots=True)
class _StagedFile:
    temporary_name: str
    final_name: str
    artifact: ArtifactRef


@dataclass(frozen=True, slots=True)
class _StagingFileMetadata:
    """Stable identities collected for one temporary file before publication."""

    temporary_name: str
    final_name: str
    digest: str
    device_id: int
    inode_id: int
    occurrence_id: str


def write_staged_artifact(
    config: ProjectConfig,
    record_staged_time: Callable[[str, ArtifactRef], object],
    bind_existing_occurrences: Callable[
        [str, tuple[ArtifactRef, ...]], tuple[ArtifactRef, ...]
    ],
    request: StagingArtifactWriteRequest,
    limits: StagingWriteLimits,
) -> ArtifactRef:
    """Stream, hash, and publish one file without replacing existing evidence."""

    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory_flag = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory_flag is None:
        raise ProjectConfigError("platform lacks safe staging write primitives")
    temporary_name = f".curator-v2-{secrets.token_hex(16)}.partial"
    final_name = f"{request.artifact_id}.bin"
    goal_fd = class_fd = -1
    try:
        goal_fd, class_fd = _open_target_directories(
            request.staging_root_fd,
            request.goal_id,
            request.artifact_class,
            no_follow,
            directory_flag,
        )
        if request.existing_artifact is not None:
            return _verify_existing_retry(
                class_fd,
                config.project_id,
                request,
                limits,
                record_staged_time,
                bind_existing_occurrences,
            )
        digest, device_id, inode_id = _write_temporary_file(
            class_fd, temporary_name, request, limits, no_follow
        )
        occurrence_id = new_id()
        staged = _staged_file(
            config,
            request,
            _StagingFileMetadata(
                temporary_name,
                final_name,
                digest,
                device_id,
                inode_id,
                occurrence_id,
            ),
        )
        return _publish_staged_file(
            class_fd,
            config.project_id,
            staged,
            record_staged_time,
            bind_existing_occurrences,
            limits.max_artifact_bytes,
        )
    finally:
        _close_target_directories(class_fd, goal_fd, temporary_name)


def _open_target_directories(
    staging_root_fd: int,
    goal_id: str,
    artifact_class: str,
    no_follow: int,
    directory_flag: int,
) -> tuple[int, int]:
    """Create/open the goal and class directories through no-follow descriptors."""

    try:
        os.mkdir(goal_id, mode=0o700, dir_fd=staging_root_fd)
    except FileExistsError:
        pass
    goal_fd = os.open(
        goal_id, os.O_RDONLY | directory_flag | no_follow, dir_fd=staging_root_fd
    )
    try:
        try:
            os.mkdir(artifact_class, mode=0o700, dir_fd=goal_fd)
        except FileExistsError:
            pass
        class_fd = os.open(
            artifact_class,
            os.O_RDONLY | directory_flag | no_follow,
            dir_fd=goal_fd,
        )
    except BaseException:
        os.close(goal_fd)
        raise
    return goal_fd, class_fd


def _write_temporary_file(
    class_fd: int,
    temporary_name: str,
    request: StagingArtifactWriteRequest,
    limits: StagingWriteLimits,
    no_follow: int,
) -> tuple[str, int, int]:
    """Write bounded source chunks and return their stable content digest."""

    fd = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow,
        0o600,
        dir_fd=class_fd,
    )
    try:
        target_stream = os.fdopen(fd, "wb")
    except BaseException:
        os.close(fd)
        raise
    digest = hashlib.sha256()
    total = 0
    with target_stream as target:
        while True:
            chunk = request.source.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            _check_chunk_limits(total, request, limits)
            written = target.write(chunk)
            if written != len(chunk):
                raise OSError("short write while staging artifact")
            digest.update(chunk)
        target.flush()
        os.fsync(target.fileno())
        metadata = os.fstat(target.fileno())
    return digest.hexdigest(), metadata.st_dev, metadata.st_ino


def _check_chunk_limits(
    total_bytes: int,
    request: StagingArtifactWriteRequest,
    limits: StagingWriteLimits,
) -> None:
    """Reject an input chunk before it exceeds either hard byte ceiling."""

    if total_bytes > limits.max_artifact_bytes:
        raise ConflictError("artifact exceeds the per-file byte ceiling")
    if request.existing_goal_bytes + total_bytes > limits.max_goal_bytes:
        raise ConflictError("goal staging byte ceiling reached")


def _verify_existing_retry(
    class_fd: int,
    project_id: str,
    request: StagingArtifactWriteRequest,
    limits: StagingWriteLimits,
    record_staged_time: Callable[[str, ArtifactRef], object],
    bind_existing_occurrences: Callable[
        [str, tuple[ArtifactRef, ...]], tuple[ArtifactRef, ...]
    ],
) -> ArtifactRef:
    """Compare a retry to its inventoried file without consuming staging quota."""

    expected = request.existing_artifact
    if expected is None:
        raise ValueError("an existing retry requires its inventoried artifact")
    descriptor = os.open(
        f"{request.artifact_id}.bin",
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        dir_fd=class_fd,
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size > limits.max_artifact_bytes
            or (expected.device_id is not None and expected.device_id != before.st_dev)
            or (expected.inode_id is not None and expected.inode_id != before.st_ino)
        ):
            raise ConflictError("staged artifact changed before exact retry")
        digest = hashlib.sha256()
        total_bytes = 0
        while True:
            source_chunk = request.source.read(64 * 1024)
            if source_chunk:
                target_chunk = _read_exact(descriptor, len(source_chunk))
            else:
                target_chunk = os.read(descriptor, 1)
            if source_chunk != target_chunk:
                raise FileExistsError("staging artifact ID is already in use")
            if not source_chunk:
                break
            total_bytes += len(source_chunk)
            if total_bytes > limits.max_artifact_bytes:
                raise ConflictError("artifact exceeds the per-file byte ceiling")
            digest.update(source_chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    try:
        path_metadata = os.stat(
            f"{request.artifact_id}.bin",
            dir_fd=class_fd,
            follow_symlinks=False,
        )
    except OSError:
        raise ConflictError("staged artifact changed during exact retry") from None
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if (
        before_identity != after_identity
        or (path_metadata.st_dev, path_metadata.st_ino) != (after.st_dev, after.st_ino)
        or total_bytes != after.st_size
        or digest.hexdigest() != expected.sha256
    ):
        raise ConflictError("staged artifact changed during exact retry")
    current = replace(expected, device_id=after.st_dev, inode_id=after.st_ino)
    return _record_existing_occurrence(
        project_id,
        None,
        class_fd,
        current,
        bind_existing_occurrences,
        record_staged_time,
    )


def _read_exact(descriptor: int, byte_count: int) -> bytes:
    """Read one bounded target chunk, allowing short regular-file reads."""

    chunks: list[bytes] = []
    remaining = byte_count
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _staged_file(
    config: ProjectConfig,
    request: StagingArtifactWriteRequest,
    metadata: _StagingFileMetadata,
) -> _StagedFile:
    artifact = ArtifactRef(
        str(
            config.staging_root
            / request.goal_id
            / request.artifact_class
            / metadata.final_name
        ),
        metadata.digest,
        device_id=metadata.device_id,
        inode_id=metadata.inode_id,
        occurrence_id=metadata.occurrence_id,
    )
    return _StagedFile(metadata.temporary_name, metadata.final_name, artifact)


def _publish_staged_file(
    class_fd: int,
    project_id: str,
    staged: _StagedFile,
    record_staged_time: Callable[[str, ArtifactRef], object],
    bind_existing_occurrences: Callable[
        [str, tuple[ArtifactRef, ...]], tuple[ArtifactRef, ...]
    ],
    max_artifact_bytes: int,
) -> ArtifactRef:
    """Publish no-clobber content and roll it back if receipt persistence fails."""

    try:
        os.link(
            staged.temporary_name,
            staged.final_name,
            src_dir_fd=class_fd,
            dst_dir_fd=class_fd,
            follow_symlinks=False,
        )
    except FileExistsError:
        existing_artifact = _matching_existing_artifact(
            class_fd, staged, max_artifact_bytes
        )
        if existing_artifact is None:
            raise FileExistsError("staging artifact ID is already in use") from None
        return _record_existing_occurrence(
            project_id,
            staged.temporary_name,
            class_fd,
            existing_artifact,
            bind_existing_occurrences,
            record_staged_time,
        )

    os.unlink(staged.temporary_name, dir_fd=class_fd)
    os.fsync(class_fd)
    try:
        record_staged_time(project_id, staged.artifact)
    except (sqlite3.Error, ConflictError, ValueError):
        os.unlink(staged.final_name, dir_fd=class_fd)
        os.fsync(class_fd)
        raise
    return staged.artifact


def _record_existing_occurrence(
    project_id: str,
    temporary_name: str | None,
    class_fd: int,
    existing_artifact: ArtifactRef,
    bind_existing_occurrences: Callable[
        [str, tuple[ArtifactRef, ...]], tuple[ArtifactRef, ...]
    ],
    record_staged_time: Callable[[str, ArtifactRef], object],
) -> ArtifactRef:
    """Preserve the original occurrence and age for an exact retry."""

    bound_artifacts = bind_existing_occurrences(project_id, (existing_artifact,))
    if len(bound_artifacts) != 1:
        raise ValueError("staging occurrence binding returned an invalid result")
    existing_artifact = bound_artifacts[0]
    if temporary_name is not None:
        os.unlink(temporary_name, dir_fd=class_fd)
        os.fsync(class_fd)
    record_staged_time(project_id, existing_artifact)
    return existing_artifact


def _matching_existing_artifact(
    class_fd: int,
    staged: _StagedFile,
    max_artifact_bytes: int,
) -> ArtifactRef | None:
    """Adopt only an unchanged regular file with identical retry content."""

    no_follow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(
        staged.final_name,
        os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0),
        dir_fd=class_fd,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_artifact_bytes:
            return None
        digest = hashlib.sha256()
        total_bytes = 0
        while True:
            chunk = os.read(
                descriptor,
                min(64 * 1024, max_artifact_bytes - total_bytes + 1),
            )
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_artifact_bytes:
                return None
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    try:
        path_metadata = os.stat(
            staged.final_name,
            dir_fd=class_fd,
            follow_symlinks=False,
        )
    except OSError:
        return None
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if (
        identity_before != identity_after
        or (path_metadata.st_dev, path_metadata.st_ino)
        != (after.st_dev, after.st_ino)
        or total_bytes != after.st_size
        or digest.hexdigest() != staged.artifact.sha256
    ):
        return None
    return replace(
        staged.artifact,
        device_id=after.st_dev,
        inode_id=after.st_ino,
    )


def _close_target_directories(
    class_fd: int, goal_fd: int, temporary_name: str
) -> None:
    """Remove any unpublished temporary file and close owned directory fds."""

    if class_fd >= 0:
        try:
            os.unlink(temporary_name, dir_fd=class_fd)
        except FileNotFoundError:
            pass
        finally:
            os.close(class_fd)
    if goal_fd >= 0:
        os.close(goal_fd)
