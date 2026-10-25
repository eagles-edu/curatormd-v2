"""Capture content-free local evidence references from configured sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .hosted_mcp import validate_host_evidence_config_path
from .local_evidence_config import capture_local_browser_proof_reference
from .project_config import ProjectConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-evidence",
        description="Capture a content-free reference from one host-configured source.",
    )
    subparsers = parser.add_subparsers(dest="source", required=True)
    browser = subparsers.add_parser("browser", help="render one configured loopback route")
    browser.add_argument("--project-root", type=Path, required=True)
    browser.add_argument("--host-config", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Capture one explicit local browser proof without printing page content."""

    arguments = _parser().parse_args(argv)
    try:
        project = ProjectConfig.load(arguments.project_root)
        host_config = validate_host_evidence_config_path(
            arguments.host_config, project.project_root
        )
        evidence = capture_local_browser_proof_reference(
            host_config,
            project_id=project.project_id,
        )
    except (OSError, RuntimeError, ValueError):
        print("local evidence capture failed", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "evidence_kind": evidence.evidence_kind,
                "locator": evidence.locator,
                "sha256": evidence.sha256,
                "outcome": evidence.outcome.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
