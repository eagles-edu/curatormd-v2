"""Explicit bounded runner for already-persisted project events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TextIO

from .cli_args import positive_integer_limit
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .router import DurableEventRouter, MAX_ROUTER_BATCH, MAX_ROUTER_PROJECTS
from .store import CuratorStore


def _positive_limit(value: str) -> int:
    """Parse a bounded event batch size without echoing rejected input."""

    return positive_integer_limit(value, MAX_ROUTER_BATCH)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-router",
        description=(
            "Process one bounded batch of durable events for explicitly bound projects."
        ),
    )
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--project-root",
        required=True,
        action="append",
        type=Path,
        help="consumer repository root; repeat once per trusted project binding",
    )
    parser.add_argument("--batch-limit", type=_positive_limit, default=100)
    parser.add_argument(
        "--route-events",
        action="store_true",
        help="required opt-in; process pending events for the configured projects",
    )
    return parser


def _queue_counts(
    store: CuratorStore, project_ids: tuple[str, ...]
) -> dict[str, int]:
    """Aggregate queue counts for only the explicitly bound projects."""

    queues = tuple(store.event_queue_status(project_id) for project_id in project_ids)
    return {
        "pending": sum(queue.received_count + queue.failed_count for queue in queues),
        "quarantined": sum(queue.quarantined_count for queue in queues),
        "claimed": sum(queue.claimed_count for queue in queues),
        "expired_claims": sum(queue.expired_claim_count for queue in queues),
    }


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one explicitly authorized local router pass and emit safe counters."""

    arguments = _parser().parse_args(argv)
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    if not arguments.route_events:
        print("Refusing event processing without --route-events.", file=errors)
        return 2
    if not arguments.database.is_absolute():
        print("Curator V2 router failed (invalid database path).", file=errors)
        return 2
    if not 1 <= len(arguments.project_root) <= MAX_ROUTER_PROJECTS:
        print("Curator V2 router failed (invalid project binding count).", file=errors)
        return 2

    try:
        configs = tuple(ProjectConfig.load(root) for root in arguments.project_root)
        project_ids = tuple(config.project_id for config in configs)
        if len(set(project_ids)) != len(project_ids):
            raise ValueError("duplicate configured project binding")
        with CuratorStore(arguments.database) as store:
            services = {
                config.project_id: ProjectPlugin.bind(config, store).service
                for config in configs
            }
            result = DurableEventRouter(store, services).route_once(
                arguments.batch_limit
            )
            queue_counts = _queue_counts(store, project_ids)
            output.write(
                json.dumps(
                    {
                        "attempted": result.attempted_count,
                        "claim_lost": result.claim_lost_count,
                        "failed": result.failed_count,
                        "processed": result.processed_count,
                        "project_count": len(project_ids),
                        **queue_counts,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
            return int(
                bool(
                    queue_counts["pending"]
                    or queue_counts["quarantined"]
                    or result.claim_lost_count
                )
            )
    except Exception:  # pylint: disable=broad-exception-caught
        print(
            "Curator V2 router failed (configuration or routing error).",
            file=errors,
        )
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
