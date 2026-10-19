"""Non-overwriting, integrity-checked SQLite backup and restore helpers."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile


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
