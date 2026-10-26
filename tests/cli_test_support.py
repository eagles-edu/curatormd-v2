"""Shared argv construction for local Curator CLI regressions."""

from __future__ import annotations

from pathlib import Path


def access_cli_args(
    operation: str,
    project_root: Path,
    database: Path,
    *extra: str,
) -> list[str]:
    """Build the common attended-access command prefix and exact options."""

    return [
        operation,
        "--project-root",
        str(project_root),
        "--database",
        str(database),
        *extra,
    ]
