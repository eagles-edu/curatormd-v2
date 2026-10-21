"""Explicit backup and restore-to-new-path commands for Curator V2 SQLite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TextIO

from .backup import backup_database, restore_database


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-storage",
        description=(
            "Create an integrity-checked SQLite backup or restore it to a new path."
        ),
    )
    operations = parser.add_subparsers(dest="operation", required=True)
    backup = operations.add_parser("backup", help="create a non-overwriting snapshot")
    backup.add_argument("--database", required=True, type=Path)
    backup.add_argument("--destination", required=True, type=Path)
    restore = operations.add_parser(
        "restore", help="restore a verified snapshot to a new path"
    )
    restore.add_argument("--backup", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    restore.add_argument(
        "--restore-to-new-path",
        action="store_true",
        help="required confirmation; this command never replaces an existing database",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one verified backup/restore without exposing paths or DB errors."""

    arguments = _parser().parse_args(argv)
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    if arguments.operation == "restore" and not arguments.restore_to_new_path:
        print("Refusing restore without --restore-to-new-path.", file=errors)
        return 2

    source = (
        arguments.database
        if arguments.operation == "backup"
        else arguments.backup
    )
    if not source.is_absolute() or not arguments.destination.is_absolute():
        print(
            "Curator V2 storage failed (source and destination must be absolute paths).",
            file=errors,
        )
        return 2

    try:
        if arguments.operation == "backup":
            backup_database(source, arguments.destination)
        else:
            restore_database(source, arguments.destination)
        output.write(
            json.dumps(
                {"operation": arguments.operation, "status": "verified"},
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        return 0
    except Exception:  # pylint: disable=broad-exception-caught
        print(
            "Curator V2 storage failed (source, destination, or database error).",
            file=errors,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
