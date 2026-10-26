"""Capture content-free local evidence references from configured sources."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

from .hosted_mcp import validate_host_evidence_config_path
from .evidence import EvidenceVerificationContext
from .local_evidence_config import (
    capture_local_browser_proof_reference,
    capture_local_human_observation_reference,
    capture_local_repository_diff_reference,
    capture_local_repository_test_reference,
    capture_local_service_probe_reference,
)
from .human_observation import new_human_confirmation_challenge
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
    service_probe = subparsers.add_parser(
        "service-probe", help="run one configured service probe and hash its output"
    )
    service_probe.add_argument("--project-root", type=Path, required=True)
    service_probe.add_argument("--host-config", type=Path, required=True)
    repository_diff = subparsers.add_parser(
        "repository-diff", help="hash one exact configured Git commit range"
    )
    repository_diff.add_argument("--project-root", type=Path, required=True)
    repository_diff.add_argument("--host-config", type=Path, required=True)
    repository_diff.add_argument("--base", required=True)
    repository_diff.add_argument("--head", required=True)
    repository_test = subparsers.add_parser(
        "repository-test", help="run one configured test command at an exact commit"
    )
    repository_test.add_argument("--project-root", type=Path, required=True)
    repository_test.add_argument("--host-config", type=Path, required=True)
    repository_test.add_argument("--runner", required=True)
    repository_test.add_argument("--commit", required=True)
    human_observation = subparsers.add_parser(
        "human-observation",
        help="record one attended local confirmation for a goal criterion",
    )
    human_observation.add_argument("--project-root", type=Path, required=True)
    human_observation.add_argument("--host-config", type=Path, required=True)
    human_observation.add_argument("--goal-id", required=True)
    human_observation.add_argument("--criterion-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Capture one local evidence reference without printing source content."""

    arguments = _parser().parse_args(argv)
    try:
        project = ProjectConfig.load(arguments.project_root)
        host_config = validate_host_evidence_config_path(
            arguments.host_config, project.project_root
        )
        if arguments.source == "browser":
            evidence = capture_local_browser_proof_reference(
                host_config,
                project_id=project.project_id,
            )
        elif arguments.source == "service-probe":
            evidence = capture_local_service_probe_reference(
                host_config,
                project_id=project.project_id,
            )
        elif arguments.source == "repository-diff":
            evidence = capture_local_repository_diff_reference(
                host_config,
                project_id=project.project_id,
                base_revision=arguments.base,
                head_revision=arguments.head,
            )
        elif arguments.source == "repository-test":
            evidence = capture_local_repository_test_reference(
                host_config,
                project_id=project.project_id,
                runner_id=arguments.runner,
                commit_id=arguments.commit,
            )
        else:
            if not sys.stdin.isatty() or not sys.stderr.isatty():
                raise ValueError("human confirmation requires an attended terminal")
            challenge = new_human_confirmation_challenge()
            print(
                "Confirm that you personally observed the criterion pass in the "
                "target workflow. This records no observation text and does not "
                "approve an SDE or artifact purge.\n"
                f"Project: {project.project_id}\n"
                f"Goal: {arguments.goal_id}\n"
                f"Criterion: {arguments.criterion_id}\n"
                f"Type exactly: {challenge}",
                file=sys.stderr,
            )
            confirmation = sys.stdin.readline().rstrip("\r\n")
            evidence = capture_local_human_observation_reference(
                host_config,
                context=EvidenceVerificationContext(
                    project_id=project.project_id,
                    goal_id=arguments.goal_id,
                    criterion_id=arguments.criterion_id,
                    now=datetime.now(UTC),
                ),
                challenge=challenge,
                confirmation=confirmation,
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
