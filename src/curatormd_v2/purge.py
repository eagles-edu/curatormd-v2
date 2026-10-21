"""Hash-verified, root-confined purge adapter for explicitly listed files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

from .models import ArtifactRef, PurgeFailureCode


class PurgeError(RuntimeError):
    """An artifact was not removed because its safety checks failed."""

    def __init__(self, code: PurgeFailureCode, message: str) -> None:
        """Keep an internal diagnostic while exposing a stable safe code."""

        super().__init__(message)
        self.code = code


class ArtifactPurger:
    """Delete only exact, hash-matching regular files beneath one staging root."""

    def __init__(self, staging_root: str | Path) -> None:
        root = Path(staging_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("staging_root must be an existing directory")
        self.staging_root = root

    def purge(self, artifact: ArtifactRef) -> bool:
        """Remove an artifact; return True if removed or already absent.

        A missing file is treated as success to make retries idempotent after a
        process crash between unlink and recording the result in SQLite.
        """

        if artifact.retention_hold is not None:
            raise PurgeError(
                PurgeFailureCode.RETENTION_HOLD,
                "artifact retention hold prevents purge",
            )

        supplied = Path(artifact.path)
        if not supplied.is_absolute():
            raise PurgeError(PurgeFailureCode.INVALID_PATH, "artifact path must be absolute")
        target = Path(os.path.abspath(supplied))
        outside_staging_root = False
        relative = target
        try:
            relative = target.relative_to(self.staging_root)
        except ValueError:
            outside_staging_root = True
        if outside_staging_root:
            raise PurgeError(
                PurgeFailureCode.OUTSIDE_STAGING_ROOT,
                "artifact is outside the configured staging root",
            )
        if not relative.parts:
            raise PurgeError(
                PurgeFailureCode.STAGING_ROOT,
                "staging root itself cannot be purged",
            )

        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        if (
            no_follow is None
            or directory is None
            or os.open not in os.supports_dir_fd
            or os.stat not in os.supports_dir_fd
            or os.stat not in os.supports_follow_symlinks
        ):
            raise PurgeError(
                PurgeFailureCode.UNSUPPORTED_PLATFORM,
                "platform lacks safe descriptor-relative purge support",
            )

        filesystem_failed = False
        try:
            self._remove_target(relative, no_follow, directory, artifact)
        except OSError:
            filesystem_failed = True
        if filesystem_failed:
            raise PurgeError(
                PurgeFailureCode.FILESYSTEM_ERROR,
                "cannot safely inspect or remove artifact",
            )
        return True

    def _remove_target(
        self,
        relative: Path,
        no_follow: int,
        directory: int,
        artifact: ArtifactRef,
    ) -> None:
        """Open, verify, and unlink one exact staged file with pinned parents."""

        root_fd = -1
        directory_fds: list[int] = []
        file_fd = -1
        try:
            root_fd = os.open(
                self.staging_root,
                os.O_RDONLY | directory | no_follow,
            )
            parent_fd = root_fd
            for part in relative.parts[:-1]:
                try:
                    child_fd = os.open(
                        part,
                        os.O_RDONLY | directory | no_follow,
                        dir_fd=parent_fd,
                    )
                except FileNotFoundError:
                    return
                directory_fds.append(child_fd)
                parent_fd = child_fd
            filename = relative.parts[-1]
            try:
                file_fd = os.open(
                    filename,
                    os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0),
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                return
            self._verify_target(file_fd, parent_fd, filename, artifact)
            os.unlink(filename, dir_fd=parent_fd)
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            for directory_fd in reversed(directory_fds):
                os.close(directory_fd)
            if root_fd >= 0:
                os.close(root_fd)

    @staticmethod
    def _verify_target(
        file_fd: int,
        parent_fd: int,
        filename: str,
        artifact: ArtifactRef,
    ) -> None:
        """Verify the opened file and its directory entry before unlink."""

        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise PurgeError(
                PurgeFailureCode.NOT_REGULAR_FILE,
                "only regular files are eligible for purge",
            )
        digest = hashlib.sha256()
        with os.fdopen(os.dup(file_fd), "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        after = os.fstat(file_fd)
        before_identity = before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        after_identity = after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        if before_identity != after_identity:
            raise PurgeError(
                PurgeFailureCode.ARTIFACT_CHANGED,
                "artifact changed while its hash was being verified",
            )
        if digest.hexdigest() != artifact.sha256:
            raise PurgeError(
                PurgeFailureCode.HASH_MISMATCH,
                "artifact hash does not match the approved reference",
            )
        named = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino):
            raise PurgeError(
                PurgeFailureCode.PATH_CHANGED,
                "artifact path changed while its hash was being verified",
            )
