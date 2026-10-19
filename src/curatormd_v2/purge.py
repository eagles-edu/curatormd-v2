"""Hash-verified, root-confined purge adapter for explicitly listed files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

from .models import ArtifactRef


class PurgeError(RuntimeError):
    """An artifact was not removed because its safety checks failed."""


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
            raise PurgeError("artifact retention hold prevents purge")

        supplied = Path(artifact.path)
        if not supplied.is_absolute():
            raise PurgeError("artifact path must be absolute")
        target = Path(os.path.abspath(supplied))
        try:
            relative = target.relative_to(self.staging_root)
        except ValueError as exc:
            raise PurgeError("artifact is outside the configured staging root") from exc
        if not relative.parts:
            raise PurgeError("staging root itself cannot be purged")

        no_follow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        if no_follow is None or directory is None or os.open not in os.supports_dir_fd:
            raise PurgeError("platform lacks safe descriptor-relative purge support")

        root_fd = -1
        opened_directories: list[int] = []
        file_fd = -1
        try:
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
                        return True
                    opened_directories.append(child_fd)
                    parent_fd = child_fd
                filename = relative.parts[-1]
                try:
                    file_fd = os.open(
                        filename,
                        os.O_RDONLY | no_follow | getattr(os, "O_NONBLOCK", 0),
                        dir_fd=parent_fd,
                    )
                except FileNotFoundError:
                    return True
                before = os.fstat(file_fd)
                if not stat.S_ISREG(before.st_mode):
                    raise PurgeError("only regular files are eligible for purge")
                digest = hashlib.sha256()
                with os.fdopen(os.dup(file_fd), "rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                after = os.fstat(file_fd)
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise PurgeError("artifact changed while its hash was being verified")
                if digest.hexdigest() != artifact.sha256:
                    raise PurgeError("artifact hash does not match the approved reference")
                os.unlink(filename, dir_fd=parent_fd)
            except OSError as exc:
                raise PurgeError(f"cannot safely inspect or remove artifact: {exc}") from exc
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            for directory_fd in reversed(opened_directories):
                os.close(directory_fd)
            if root_fd >= 0:
                os.close(root_fd)
        return True
