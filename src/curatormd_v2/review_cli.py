"""Attended local-UID workflow for reviewing Curator V2 SDE proposals.

This host adapter is for one local account and one configured project at a
time. It is not a Hermes identity provider or a remote review endpoint. The
review confirmation binds the decision to the exact inventory displayed; the
plugin re-scans that inventory before committing the receipt. Canonical facts
are persisted before any eligible purge runs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import TextIO

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .models import ReviewDecision
from .project_access import FingerprintBoundSQLiteProjectGrantAuthorizer
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .rate_limiter import SQLiteTokenBucket
from .reviews import ReviewAuthorizationError
from .store import CuratorStore


class LocalUIDReviewAuthorizer:
    """Bind local review methods to the invoking, non-setuid OS account."""

    # This is a deliberately small implementation of the host review protocol.
    # pylint: disable=too-few-public-methods

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Authorize only the process's exact local UID subject."""
        del project_id, candidate_id, decision
        return self._subject(authenticated_subject)

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Bind a correction to the invoking local UID."""
        del project_id, candidate_id
        return self._subject(authenticated_subject)

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Bind reviewer feedback to the invoking local UID."""
        del project_id, candidate_id
        return self._subject(authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Bind an exact hold release to the invoking local UID."""
        del project_id, receipt_id, path, rationale
        return self._subject(authenticated_subject)

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Bind expiry approval to the invoking local UID."""

        del project_id, manifest_sha256
        return self._subject(authenticated_subject)

    @staticmethod
    def _subject(authenticated_subject: str | None) -> str:
        """Reject absent, substituted, or setuid caller identity."""
        subject = _local_subject()
        if authenticated_subject != subject:
            raise ReviewAuthorizationError(
                "local reviewer identity does not match the current OS account"
            )
        return subject


def _local_subject() -> str:
    """Return the effective local UID only when real and effective IDs agree."""

    if not hasattr(os, "getuid") or not hasattr(os, "geteuid"):
        raise OSError("local UID identity is unavailable")
    if os.getuid() != os.geteuid():
        raise PermissionError("set-user-ID review is not supported")
    return f"local-uid:{os.geteuid()}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-review",
        description=(
            "Review one Curator V2 SDE interactively as the current local OS account."
        ),
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--target",
        help="configured canonical Markdown target; required when multiple targets exist",
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("queue", help="show pending SDE candidates")
    review = commands.add_parser("review", help="review and disposition one candidate")
    review.add_argument("candidate_id")
    commands.add_parser(
        "expire", help="approve and purge the current complete expiry inventory"
    )
    retry_expiry = commands.add_parser(
        "expiry-retry", help="retry due targets from one approved expiry receipt"
    )
    retry_expiry.add_argument("receipt_id")
    return parser


def _build_api(
    config: ProjectConfig, store: CuratorStore
) -> AuthenticatedCuratorAPI:
    """Build a project-fingerprint-bound API with a local UID review host."""

    plugin = ProjectPlugin.bind(
        config, store, review_authorizer=LocalUIDReviewAuthorizer()
    )
    authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
        store,
        project_id=config.project_id,
        repository_fingerprint=config.repository_fingerprint,
        config_sha256=config.config_sha256,
        backend_api_version=config.backend_api_version,
        allowed_actions=frozenset({ProjectAction.READ, ProjectAction.REVIEW}),
    )
    return AuthenticatedCuratorAPI(
        {config.project_id: plugin},
        authorizer=authorizer,
        limiter=SQLiteTokenBucket(store),
    )


def _target(config: ProjectConfig, requested: str | None) -> Path:
    """Select only one of the project's explicitly configured targets."""

    if requested is not None:
        return config.validated_persistence_target(requested)
    if len(config.persistence_targets) != 1:
        raise ValueError("--target is required when the project has multiple targets")
    return config.persistence_targets[0]


def _confirmation_phrase(
    decision: ReviewDecision, candidate_id: str, manifest_sha256: str
) -> str:
    """Bind the human confirmation to both disposition and exact file manifest."""

    action = "APPROVE" if decision is ReviewDecision.APPROVED else "REJECT"
    return f"{action} {candidate_id} AND PURGE INVENTORY {manifest_sha256}"


def _confirm(
    phrase: str, input_stream: TextIO, errors: TextIO
) -> bool:
    """Require the exact displayed phrase on an interactive terminal."""

    if not input_stream.isatty():
        errors.write("Refusing SDE review without an interactive TTY.\n")
        return False
    errors.write(f"Type exactly: {phrase}\n> ")
    errors.flush()
    try:
        return input_stream.readline(512).rstrip("\r\n") == phrase
    except (OSError, ValueError):
        return False


def _write_json(output: TextIO, value: object) -> None:
    output.write(json.dumps(value, default=str, sort_keys=True) + "\n")


def _queue(
    api: AuthenticatedCuratorAPI, caller: AuthenticatedCaller, project_id: str
) -> list[dict[str, object]]:
    """Return a bounded, content-free summary of pending candidates."""

    details = api.sde_review_queue(caller, project_id, limit=100)
    return [
        {
            "candidate_id": item.candidate.candidate_id,
            "goal_id": item.goal.goal_id,
            "materiality": item.candidate.materiality.value,
            "rationale": item.candidate.rationale,
            "impact": item.candidate.impact,
            "retrieval_value": item.candidate.retrieval_value,
        }
        for item in details
    ]


def _review(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    input_stream: TextIO,
    output: TextIO,
    errors: TextIO,
) -> bool:
    """Show facts and exact inventory, then commit one attended disposition."""

    packet = api.sde_review_packet(
        caller, config.project_id, arguments.candidate_id
    )
    inventory = packet.artifact_inventory
    if not inventory.usage.inventory_complete or inventory.manifest_sha256 is None:
        errors.write("Refusing SDE review because the artifact inventory is incomplete.\n")
        return False
    target = _target(config, arguments.target)
    _write_json(
        output,
        {
            "review_packet": asdict(packet),
            "canonical_target": str(target),
            "cleanup_authorization": (
                "The exact listed inventory may be purged after canonical persistence; "
                "held artifacts remain held."
            ),
        },
    )
    errors.write("Decision (approve/reject): ")
    errors.flush()
    decision_text = input_stream.readline(16).strip().lower()
    decisions = {"approve": ReviewDecision.APPROVED, "reject": ReviewDecision.REJECTED}
    decision = decisions.get(decision_text)
    if decision is None:
        errors.write("SDE review cancelled; no decision was recorded.\n")
        return False
    phrase = _confirmation_phrase(
        decision, arguments.candidate_id, inventory.manifest_sha256
    )
    if not _confirm(phrase, input_stream, errors):
        errors.write("SDE review cancelled; no decision was recorded.\n")
        return False
    errors.write("Review rationale (one line): ")
    errors.flush()
    rationale = input_stream.readline(1002).rstrip("\r\n")
    if not rationale.strip() or len(rationale) > 1000 or "\n" in rationale:
        errors.write("SDE review cancelled; rationale must be 1-1000 characters.\n")
        return False

    receipt = api.sde_confirm(
        caller,
        config.project_id,
        arguments.candidate_id,
        decision,
        inventory.artifacts,
        artifact_inventory_complete=True,
        rationale=rationale,
    )
    projection = api.persist_goal(
        caller,
        config.project_id,
        packet.detail.goal.goal_id,
        str(target),
    )
    final_receipt, purge_targets = api.artifact_purge_status(
        caller, config.project_id, receipt.receipt_id
    )
    _write_json(
        output,
        {
            "decision": decision.value,
            "receipt_id": receipt.receipt_id,
            "canonical_target": str(projection.target),
            "canonical_sha256": projection.sha256,
            "purge_status": final_receipt.purge_status.value,
            "artifacts": [asdict(item) for item in purge_targets],
        },
    )
    return True


def _expire(
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    input_stream: TextIO,
    output: TextIO,
    errors: TextIO,
) -> int:
    """Display then approve only the complete, exact 72-hour inventory."""

    snapshot = api.discover_project_expiry_inventory(caller, config.project_id)
    _write_json(output, {"expiry_snapshot": asdict(snapshot)})
    if not snapshot.inventory_complete or snapshot.manifest_sha256 is None:
        errors.write("Refusing expiry approval because staging age inventory is incomplete.\n")
        return 2
    if not snapshot.eligible_artifacts:
        errors.write("No unheld artifacts are ready for expiry.\n")
        return 0
    if len(snapshot.eligible_artifacts) > 500:
        errors.write("Expiry inventory exceeds the 500-artifact receipt limit.\n")
        return 2
    phrase = f"PURGE EXPIRED INVENTORY {snapshot.manifest_sha256}"
    if not _confirm(phrase, input_stream, errors):
        errors.write("Expiry cleanup cancelled; no approval receipt was recorded.\n")
        return 2
    receipt = api.approve_project_expiry_inventory(
        caller,
        config.project_id,
        snapshot.eligible_artifacts,
        snapshot.manifest_sha256,
    )
    _write_json(output, {"expiry_purge_receipt": asdict(receipt)})
    return 0 if receipt.status.value == "complete" else 1


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the attended local review workflow without accepting identity input."""

    arguments = _parser().parse_args(argv)
    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    try:
        subject = _local_subject()
        if arguments.operation in {"review", "expire"} and not input_stream.isatty():
            errors.write("Refusing attended review without an interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "expire"} and not output.isatty():
            errors.write("Refusing attended review without a visible interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "expire"} and not errors.isatty():
            errors.write("Refusing attended review without a visible prompt TTY.\n")
            return 2
        database = arguments.database.expanduser()
        if not database.is_absolute() or not database.is_file() or database.is_symlink():
            raise ValueError("database must be an existing absolute regular file")
        config = ProjectConfig.load(arguments.project_root)
        store = CuratorStore(database)
    except Exception:  # pylint: disable=broad-exception-caught
        errors.write("Curator review failed (identity or configuration error).\n")
        return 2
    try:
        caller = AuthenticatedCaller(subject)
        api = _build_api(config, store)
        if arguments.operation == "queue":
            _write_json(
                output,
                {
                    "project_id": config.project_id,
                    "pending": _queue(api, caller, config.project_id),
                },
            )
            return 0
        if arguments.operation == "expiry-retry":
            receipt = api.retry_expiry_purge(
                caller, config.project_id, arguments.receipt_id
            )
            _write_json(output, {"expiry_purge_receipt": asdict(receipt)})
            return 0 if receipt.status.value == "complete" else 1
        if arguments.operation == "expire":
            return _expire(api, caller, config, input_stream, output, errors)
        if _review(arguments, api, caller, config, input_stream, output, errors):
            return 0
        return 2
    except Exception:  # pylint: disable=broad-exception-caught
        errors.write("Curator review failed (authorization, inventory, or persistence error).\n")
        return 2
    finally:
        store.close()
