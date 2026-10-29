"""Non-overwriting, integrity-checked SQLite backup and restore helpers."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
from zoneinfo import ZoneInfo

from .read_models import BACKUP_TREE_WARNING_THRESHOLD_BYTES, BackupDirectoryUsage

_MAX_BACKUP_DIRECTORY_ENTRIES = 256
_MAX_BACKUP_DIRECTORY_DEPTH = 8


def measure_backup_directory(directory: str | Path | None) -> BackupDirectoryUsage:
    """Measure daily snapshots and bounded file totals without reading contents."""

    if directory is None:
        return BackupDirectoryUsage(
            "unavailable", None, None, None, None, None, None, None, None
        )
    backup_directory = Path(directory).expanduser()
    if any(
        ancestor.is_symlink()
        for ancestor in (backup_directory, *backup_directory.parents)
    ):
        return BackupDirectoryUsage(
            "unavailable", None, None, None, None, None, None, None, None
        )
    try:
        metadata = backup_directory.stat(follow_symlinks=False)
    except FileNotFoundError:
        return BackupDirectoryUsage(
            "available", 0, 0, 0, 0, 0, 0, 0, 0,
            warning_threshold_bytes=BACKUP_TREE_WARNING_THRESHOLD_BYTES,
            warning_status="below_threshold",
        )
    except OSError:
        return BackupDirectoryUsage(
            "unavailable", None, None, None, None, None, None, None, None
        )
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        return BackupDirectoryUsage(
            "unavailable", None, None, None, None, None, None, None, None
        )

    backup_count = file_bytes = allocated_bytes = unclassified = 0
    observed_entries = observed_files = observed_file_bytes = observed_allocated = 0
    inspected = 0
    inventory_incomplete = False
    measurement_complete = True
    allocation_supported = True
    pending: list[tuple[int, int]] = []
    try:
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        root_fd = os.open(backup_directory, directory_flags)
        pending.append((root_fd, 0))
        root_stat = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.getuid()
            or stat.S_IMODE(root_stat.st_mode) & 0o077
        ):
            raise PermissionError("backup directory ownership or mode changed")
        observed_allocated = (
            root_stat.st_blocks * 512 if hasattr(root_stat, "st_blocks") else 0
        )
        if not hasattr(root_stat, "st_blocks"):
            allocation_supported = False
            measurement_complete = False
        while pending:
            current_fd, depth = pending.pop()
            try:
                try:
                    entries_context = os.scandir(current_fd)
                except OSError:
                    inventory_incomplete = True
                    measurement_complete = False
                    continue
                with entries_context as entries:
                    for entry in entries:
                        inspected += 1
                        if inspected > _MAX_BACKUP_DIRECTORY_ENTRIES:
                            inventory_incomplete = True
                            measurement_complete = False
                            break
                        observed_entries += 1
                        try:
                            entry_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            unclassified += 1
                            inventory_incomplete = True
                            measurement_complete = False
                            continue
                        if hasattr(entry_stat, "st_blocks"):
                            observed_allocated += entry_stat.st_blocks * 512
                        else:
                            measurement_complete = False
                            allocation_supported = False

                        is_top_level = depth == 0
                        match = (
                            _DAILY_BACKUP_NAME.fullmatch(entry.name)
                            if is_top_level else None
                        )
                        if match is None:
                            unclassified += 1
                            inventory_incomplete = True
                        elif not stat.S_ISREG(entry_stat.st_mode):
                            unclassified += 1
                            inventory_incomplete = True
                        else:
                            try:
                                date.fromisoformat(match.group(1))
                            except ValueError:
                                unclassified += 1
                                inventory_incomplete = True
                            else:
                                backup_count += 1
                                file_bytes += entry_stat.st_size
                                allocated_bytes += (
                                    entry_stat.st_blocks * 512
                                    if hasattr(entry_stat, "st_blocks") else 0
                                )
                                if (
                                    entry_stat.st_uid != os.getuid()
                                    or stat.S_IMODE(entry_stat.st_mode) & 0o077
                                ):
                                    unclassified += 1
                                    inventory_incomplete = True

                        if stat.S_ISREG(entry_stat.st_mode):
                            observed_files += 1
                            observed_file_bytes += entry_stat.st_size
                        if (
                            entry_stat.st_uid != os.getuid()
                            or stat.S_IMODE(entry_stat.st_mode) & 0o077
                        ):
                            inventory_incomplete = True
                        if stat.S_ISDIR(entry_stat.st_mode):
                            if depth >= _MAX_BACKUP_DIRECTORY_DEPTH:
                                inventory_incomplete = True
                                measurement_complete = False
                            else:
                                try:
                                    child_fd = os.open(
                                        entry.name,
                                        directory_flags,
                                        dir_fd=current_fd,
                                    )
                                except OSError:
                                    inventory_incomplete = True
                                    measurement_complete = False
                                else:
                                    try:
                                        child_stat = os.fstat(child_fd)
                                    except OSError:
                                        os.close(child_fd)
                                        raise
                                    if (
                                        child_stat.st_dev != root_stat.st_dev
                                        or child_stat.st_ino != entry_stat.st_ino
                                    ):
                                        os.close(child_fd)
                                        inventory_incomplete = True
                                        measurement_complete = False
                                    else:
                                        pending.append((child_fd, depth + 1))
                        elif not stat.S_ISREG(entry_stat.st_mode):
                            # A symlink's own allocation is counted, but its
                            # target and special-file contents stay outside.
                            inventory_incomplete = True
            finally:
                os.close(current_fd)
            if inspected > _MAX_BACKUP_DIRECTORY_ENTRIES:
                break
    except OSError:
        return BackupDirectoryUsage(
            "unavailable", None, None, None, None, None, None, None, None
        )
    finally:
        for pending_fd, _depth in pending:
            os.close(pending_fd)

    if observed_allocated >= BACKUP_TREE_WARNING_THRESHOLD_BYTES:
        warning_status = "warning"
    elif not measurement_complete or not allocation_supported:
        warning_status = "unknown"
    else:
        warning_status = "below_threshold"
    return BackupDirectoryUsage(
        "incomplete" if inventory_incomplete else "available",
        backup_count,
        file_bytes,
        allocated_bytes if allocation_supported and not inventory_incomplete else None,
        unclassified,
        observed_entries,
        observed_files,
        observed_file_bytes,
        observed_allocated if allocation_supported else None,
        warning_threshold_bytes=BACKUP_TREE_WARNING_THRESHOLD_BYTES,
        warning_status=warning_status,
    )


def _database_path(path: str | Path, *, must_exist: bool) -> Path:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("database path must not be a symlink")
    if must_exist:
        resolved = requested.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("database path must be a regular file")
        return resolved

    if requested.exists():
        raise FileExistsError("destination already exists; refusing to overwrite")
    parent = requested.parent.resolve(strict=False)
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = parent / requested.name
    if os.path.lexists(destination):
        raise FileExistsError("destination already exists; refusing to overwrite")
    return destination


def _verify_database(connection: sqlite3.Connection) -> None:
    integrity = tuple(row[0] for row in connection.execute("PRAGMA integrity_check"))
    if integrity != ("ok",):
        raise sqlite3.DatabaseError("SQLite integrity_check did not return ok")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise sqlite3.DatabaseError("SQLite foreign_key_check found violations")


def _copy_verified(source: Path, destination: Path) -> None:
    temporary_path: Path | None = None
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)

        source_uri = f"{source.as_uri()}?mode=ro"
        source_connection = sqlite3.connect(source_uri, uri=True, timeout=30)
        destination_connection = sqlite3.connect(temporary_path, timeout=30)
        source_connection.backup(destination_connection, pages=256, sleep=0.01)
        _verify_database(destination_connection)
        destination_connection.close()
        destination_connection = None
        source_connection.close()
        source_connection = None

        # A same-directory hard link installs the verified bytes atomically and
        # fails if another process created the requested destination meanwhile.
        os.link(temporary_path, destination)
        temporary_path.unlink()
        temporary_path = None
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def backup_database(source: str | Path, destination: str | Path) -> Path:
    """Take a consistent private SQLite snapshot without overwriting a backup."""

    source_path = _database_path(source, must_exist=True)
    destination_path = _database_path(destination, must_exist=False)
    _copy_verified(source_path, destination_path)
    return destination_path


def restore_database(backup: str | Path, destination: str | Path) -> Path:
    """Restore a verified snapshot to a new path; never replace an existing DB."""

    backup_path = _database_path(backup, must_exist=True)
    destination_path = _database_path(destination, must_exist=False)
    _copy_verified(backup_path, destination_path)
    return destination_path


_DAILY_BACKUP_NAME = re.compile(r"^curator-v2-(\d{4}-\d{2}-\d{2})\.sqlite3$")


def _verify_existing_backup(path: Path) -> None:
    """Verify an existing dated backup before reusing or pruning beside it."""

    if path.is_symlink() or not path.is_file():
        raise ValueError("daily backup entry is not a regular file")
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("daily backup file is not private and owner-owned")
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro", uri=True, timeout=30
    )
    try:
        _verify_database(connection)
    finally:
        connection.close()


def backup_daily(
    source: str | Path,
    directory: str | Path,
    *,
    today: date | None = None,
    keep: int = 7,
) -> Path:
    """Create today's verified snapshot and retain the newest seven daily files."""

    if keep != 7:
        raise ValueError("local alpha policy retains exactly seven daily backups")
    backup_directory = Path(directory).expanduser()
    if backup_directory.is_symlink():
        raise ValueError("backup directory must not be a symlink")
    backup_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = backup_directory.stat(follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("backup destination must be a directory")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("backup directory must be private and owner-owned")

    backup_day = today or datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    destination = backup_directory / f"curator-v2-{backup_day.isoformat()}.sqlite3"
    try:
        backup_database(source, destination)
    except FileExistsError:
        # A concurrent scheduled run may have installed today's backup first.
        _verify_existing_backup(destination)

    dated: list[tuple[date, Path]] = []
    for candidate in backup_directory.iterdir():
        match = _DAILY_BACKUP_NAME.fullmatch(candidate.name)
        if match is None:
            continue
        try:
            candidate_day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        _verify_existing_backup(candidate)
        dated.append((candidate_day, candidate))

    dated.sort(key=lambda item: item[0], reverse=True)
    for _, expired in dated[keep:]:
        expired.unlink()
    return destination
