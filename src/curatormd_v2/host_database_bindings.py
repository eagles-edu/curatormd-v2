"""Owner-managed per-project database routing for local Codex MCP."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
from typing import cast

from .project_access import ProjectBindingStartupError


DEFAULT_DATABASE_BINDINGS_PATH = (
    Path.home() / ".config" / "curatormd-v2" / "database-bindings.json"
)
MAX_DATABASE_BINDINGS_BYTES = 16 * 1024
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys rather than accepting the last value."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate database binding key")
        result[key] = value
    return result


def _read_owner_file(path: Path) -> bytes:
    """Read a bounded private host file without following symlinks."""

    if (
        not path.is_absolute()
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "geteuid")
    ):
        raise ProjectBindingStartupError("project-database-bindings-unavailable")
    try:
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
        )
    except OSError:
        raise ProjectBindingStartupError(
            "project-database-bindings-unavailable"
        ) from None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_DATABASE_BINDINGS_BYTES
        ):
            raise ProjectBindingStartupError(
                "project-database-bindings-unavailable"
            )
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(
            descriptor, min(4096, MAX_DATABASE_BINDINGS_BYTES + 1 - total)
        ):
            total += len(chunk)
            if total > MAX_DATABASE_BINDINGS_BYTES:
                raise ProjectBindingStartupError(
                    "project-database-bindings-unavailable"
                )
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def load_project_database_bindings(bindings_path: Path | None = None) -> dict[str, object]:
    """Read the bounded owner-managed project map without selecting a ledger."""
    selected_path = (bindings_path or DEFAULT_DATABASE_BINDINGS_PATH).expanduser()
    try:
        document: object = json.loads(
            _read_owner_file(selected_path).decode("utf-8"),
            object_pairs_hook=_unique_object,
        )
    except ProjectBindingStartupError:
        raise
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise ProjectBindingStartupError(
            "project-database-bindings-unavailable"
        ) from None
    if not isinstance(document, dict):
        raise ProjectBindingStartupError("project-database-bindings-unavailable")
    mapping = cast(dict[str, object], document)
    version = mapping.get("schema_version")
    project_values = mapping.get("projects")
    if (
        set(mapping) != {"schema_version", "projects"}
        or type(version) is not int
        or version != 1
        or not isinstance(project_values, dict)
    ):
        raise ProjectBindingStartupError("project-database-bindings-unavailable")
    projects = cast(dict[str, object], project_values)
    if any(not _PROJECT_ID_RE.fullmatch(key) for key in projects):
        raise ProjectBindingStartupError("project-database-bindings-unavailable")
    return projects


def resolve_project_database(
    project_id: str, bindings_path: Path | None = None
) -> Path:
    """Select one exact project database; never fall back to another ledger."""

    projects = load_project_database_bindings(bindings_path)
    if project_id not in projects:
        raise ProjectBindingStartupError("project-database-binding-missing")
    return validate_project_database_path(projects[project_id])


def validate_project_database_path(raw_database: object) -> Path:
    """Validate one selected database path without reloading the project map."""

    if not isinstance(raw_database, str):
        raise ProjectBindingStartupError("project-database-bindings-unavailable")
    database = Path(raw_database)
    if not database.is_absolute():
        raise ProjectBindingStartupError("project-database-file-invalid")
    try:
        metadata = database.lstat()
    except OSError:
        raise ProjectBindingStartupError("project-database-file-invalid") from None
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or metadata.st_nlink != 1
    ):
        raise ProjectBindingStartupError("project-database-file-invalid")
    return database
