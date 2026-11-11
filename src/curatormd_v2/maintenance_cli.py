"""Explicit one-shot runner for already-approved due artifact purges."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import TextIO

from .backup import backup_daily
from .cli_args import positive_integer_limit
from .cli_interaction import SafeArgumentParser, parse_safe_arguments
from .errors import safe_exception_label
from .models import PurgeStatus
from .project_config import ProjectConfig
from .process_privacy import protect_process_data
from .project_plugin import ProjectPlugin
from .store import CuratorStore


_SQLITE_ERROR_NAME = re.compile(r"SQLITE_[A-Z0-9_]{1,64}\Z")


def _safe_failure_detail(error: Exception) -> str:
    """Describe an operational failure without logging paths or exception text."""

    details = [f"cause={safe_exception_label(error)}"]
    if isinstance(error, OSError) and type(error.errno) is int:
        details.append(f"errno={error.errno}")
    if isinstance(error, sqlite3.Error):
        error_name = getattr(error, "sqlite_errorname", None)
        if isinstance(error_name, str) and _SQLITE_ERROR_NAME.fullmatch(error_name):
            details.append(f"sqlite_code={error_name}")
    return " ".join(details)


def _positive_limit(value: str) -> int:
    """Parse a bounded scheduler batch size."""

    return positive_integer_limit(value, 1000)


def _parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="curatormd-v2-maintenance",
        description=(
            "Create the daily local database backup and process only due, "
            "previously reviewed artifact purges for one configured project."
        ),
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--batch-limit", type=_positive_limit, default=100)
    parser.add_argument(
        "--execute-due-purges",
        action="store_true",
        help="required opt-in; never creates review decisions or bypasses backoff",
    )
    return parser


def _execute_retry_pass(
    config: ProjectConfig,
    database: Path,
    batch_limit: int,
    output: TextIO,
) -> int:
    """Back up the ledger, retry bounded purge queues, and report safe counts."""

    backup_daily(database, database.parent / "backups")
    with CuratorStore(database) as store:
        plugin = ProjectPlugin.bind(config, store)
        receipts, expiry_receipts = plugin.retry_due_purge_pass(batch_limit)
        completed = sum(
            receipt.purge_status is PurgeStatus.COMPLETE for receipt in receipts
        )
        pending = len(receipts) - completed
        expiry_complete = sum(
            receipt.status is PurgeStatus.COMPLETE for receipt in expiry_receipts
        )
        expiry_pending = len(expiry_receipts) - expiry_complete
        output.write(
            json.dumps(
                {
                    "backup_status": "verified",
                    "project_id": config.project_id,
                    "processed": len(receipts),
                    "complete": completed,
                    "pending": pending,
                    "expiry_processed": len(expiry_receipts),
                    "expiry_complete": expiry_complete,
                    "expiry_pending": expiry_pending,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        return 1 if pending or expiry_pending else 0


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute a bounded purge-retry pass and emit content-free counters."""

    errors = stderr or sys.stderr
    if not protect_process_data():
        print("Curator V2 maintenance failed (privacy limits unavailable).", file=errors)
        return 2
    arguments = parse_safe_arguments(
        _parser(), argv, errors,
        "Curator V2 maintenance failed (invalid command arguments).\n",
    )
    if arguments is None:
        return 2
    output = stdout or sys.stdout
    if not arguments.execute_due_purges:
        print(
            "Refusing purge retries without --execute-due-purges.", file=errors
        )
        return 2
    database = arguments.database.expanduser()
    if not database.is_absolute():
        print("Curator V2 maintenance failed (invalid configuration).", file=errors)
        return 2

    try:
        config = ProjectConfig.load(arguments.project_root)
        return _execute_retry_pass(
            config, database, arguments.batch_limit, output
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # The boundary must sanitize any host adapter or filesystem exception.
        print(
            "Curator V2 maintenance failed (configuration or purge error; "
            f"{_safe_failure_detail(exc)}).",
            file=errors,
        )
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
