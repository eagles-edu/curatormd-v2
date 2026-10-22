"""Bounded atomic writes for temporary project staging artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import secrets
import sqlite3
from typing import BinaryIO, Callable

from .models import ArtifactRef
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


@dataclass(frozen=True, slots=True)
class StagingWriteLimits:
    """Host-configured ceilings for one artifact write."""

    max_artifact_bytes: int
    max_goal_bytes: int
    max_project_bytes: int | None


@dataclass(frozen=True, slots=True)
class _StagedFile:
    temporary_name: str
    final_name: str
    artifact: ArtifactRef


def write_staged_artifact(
    config: ProjectConfig,
    record_staged_time: Callable[[str, ArtifactRef], object],
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
        digest = _write_temporary_file(
            class_fd, temporary_name, request, limits, no_follow
        )
        staged = _staged_file(config, request, temporary_name, final_name, digest)
        _publish_staged_file(class_fd, config.project_id, staged, record_staged_time)
        return staged.artifact
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
) -> str:
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
    project_bytes = (
        request.project_usage.observed_file_bytes
        if request.project_usage is not None
        else None
    )
    with target_stream as target:
        while True:
            chunk = request.source.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            _check_chunk_limits(total, request, limits, project_bytes)
            target.write(chunk)
            digest.update(chunk)
        target.flush()
        os.fsync(target.fileno())
    return digest.hexdigest()


def _check_chunk_limits(
    total_bytes: int,
    request: StagingArtifactWriteRequest,
    limits: StagingWriteLimits,
    project_bytes: int | None,
) -> None:
    """Reject an input chunk before it exceeds any configured byte ceiling."""

    if total_bytes > limits.max_artifact_bytes:
        raise ConflictError("artifact exceeds the per-file byte ceiling")
    if request.existing_goal_bytes + total_bytes > limits.max_goal_bytes:
        raise ConflictError("goal staging byte ceiling reached")
    if (
        project_bytes is not None
        and limits.max_project_bytes is not None
        and project_bytes + total_bytes > limits.max_project_bytes
    ):
        raise ConflictError("project staging byte budget reached")


def _staged_file(
    config: ProjectConfig,
    request: StagingArtifactWriteRequest,
    temporary_name: str,
    final_name: str,
    digest: str,
) -> _StagedFile:
    artifact = ArtifactRef(
        str(
            config.staging_root
            / request.goal_id
            / request.artifact_class
            / final_name
        ),
        digest,
    )
    return _StagedFile(temporary_name, final_name, artifact)


def _publish_staged_file(
    class_fd: int,
    project_id: str,
    staged: _StagedFile,
    record_staged_time: Callable[[str, ArtifactRef], object],
) -> None:
    """Publish no-clobber content and roll it back if receipt persistence fails."""

    os.link(
        staged.temporary_name,
        staged.final_name,
        src_dir_fd=class_fd,
        dst_dir_fd=class_fd,
        follow_symlinks=False,
    )
    os.unlink(staged.temporary_name, dir_fd=class_fd)
    os.fsync(class_fd)
    try:
        record_staged_time(project_id, staged.artifact)
    except (sqlite3.Error, ConflictError, ValueError):
        os.unlink(staged.final_name, dir_fd=class_fd)
        os.fsync(class_fd)
        raise


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
