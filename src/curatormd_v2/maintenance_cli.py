"""Explicit one-shot runner for already-approved due artifact purges."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TextIO

from .cli_args import positive_integer_limit
from .models import PurgeStatus
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .store import CuratorStore


def _positive_limit(value: str) -> int:
    """Parse a bounded scheduler batch size."""

    return positive_integer_limit(value, 1000)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-maintenance",
        description=(
            "Process only due, previously reviewed and canonically persisted "
            "artifact purges for one configured project."
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
    """Run both bounded retry queues and emit their aggregate receipt counts."""

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

    arguments = _parser().parse_args(argv)
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
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
    except Exception:  # pylint: disable=broad-exception-caught
        # The boundary must sanitize any host adapter or filesystem exception.
        print(
            "Curator V2 maintenance failed (configuration or purge error).",
            file=errors,
        )
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
