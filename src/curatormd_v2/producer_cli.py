"""Bounded stdin adapter for repository-local Curator V2 artifact staging."""

from __future__ import annotations

import argparse
from contextlib import closing
from pathlib import Path
import sys
from typing import BinaryIO, TextIO

from .cli_output import write_json_line
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .store import CuratorStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-stage",
        description=(
            "Stream one temporary artifact from stdin into the configured "
            "project and goal staging scope."
        ),
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--goal-id", required=True)
    parser.add_argument(
        "--artifact-class",
        required=True,
        choices=("raw-chat", "cue", "import", "scratch", "generated", "duplicate"),
    )
    parser.add_argument("--artifact-id", required=True)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Stage only bytes piped to stdin; never read arbitrary source paths."""

    arguments = _parser().parse_args(argv)
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    database = arguments.database.expanduser()
    if not database.is_absolute():
        print("Curator V2 staging failed (invalid request or producer error).", file=errors)
        return 2

    try:
        config = ProjectConfig.load(arguments.project_root)
        with closing(CuratorStore(database)) as store:
            plugin = ProjectPlugin.bind(config, store)
            artifact = plugin.stage_artifact(
                arguments.goal_id,
                arguments.artifact_class,
                arguments.artifact_id,
                stdin or sys.stdin.buffer,
            )
            write_json_line(output, {"path": artifact.path, "sha256": artifact.sha256})
            return 0
    # The producer boundary must sanitize arbitrary adapter and input failures.
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        print("Curator V2 staging failed (invalid request or producer error).", file=errors)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
