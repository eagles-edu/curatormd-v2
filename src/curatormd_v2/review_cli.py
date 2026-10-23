"""Attended local-UID workflow for reviewing Curator V2 SDE proposals.

This host adapter is for one local account and one configured project at a
time. It is not a Hermes identity provider or a remote review endpoint. The
review confirmation binds the decision to the exact inventory displayed; the
plugin re-scans that inventory before committing the receipt. Canonical facts
are persisted before any eligible purge runs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import stat
import sys
from typing import TextIO

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .cli_interaction import confirm_exact_phrase
from .models import ArtifactRef, ReacquisitionAction, ReviewDecision, SDEReviewPacket
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAuthorizationBinding,
)
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

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Bind cleanup authorization to the invoking local UID."""

        del project_id, receipt_id, manifest_sha256
        return self._subject(authenticated_subject)

    def authorize_database(
        self, database: Path, authenticated_subject: str | None = None
    ) -> str:
        """Require the current local reviewer to own the pilot ledger file."""

        subject = self._subject(authenticated_subject)
        metadata = database.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise ReviewAuthorizationError(
                "database must be a regular file owned by the current local account"
            )
        return subject

    @staticmethod
    def _subject(authenticated_subject: str | None) -> str:
        """Reject absent, substituted, or setuid caller identity."""
        subject = _local_subject()
        if authenticated_subject != subject:
            raise ReviewAuthorizationError(
                "local reviewer identity does not match the current OS account"
            )
        return subject


@dataclass(frozen=True, slots=True)
class _CliStreams:
    """Explicit streams for attended CLI operations and their tests."""

    input: TextIO
    output: TextIO
    errors: TextIO


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
    config: ProjectConfig,
    store: CuratorStore,
    review_authorizer: LocalUIDReviewAuthorizer,
) -> AuthenticatedCuratorAPI:
    """Build a project-fingerprint-bound API with a local UID review host."""

    plugin = ProjectPlugin.bind(config, store, review_authorizer=review_authorizer)
    authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
        store,
        ProjectAuthorizationBinding.from_project_config(
            config, frozenset({ProjectAction.READ, ProjectAction.REVIEW})
        ),
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
    decision: ReviewDecision,
    candidate_id: str,
    manifest_sha256: str,
    dependency_map_sha256: str,
) -> str:
    """Bind one human action to disposition, dependency map, and inventory."""

    action = "APPROVE" if decision is ReviewDecision.APPROVED else "REJECT"
    return (
        f"{action} SDE {candidate_id} WITH DEPENDENCY MAP "
        f"{dependency_map_sha256} AND PURGE INVENTORY {manifest_sha256}"
    )


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


def _select_review_artifacts(
    packet: SDEReviewPacket,
    streams: _CliStreams,
) -> tuple[ArtifactRef, ...] | None:
    """Collect only retention actions allowed by the displayed dependencies."""

    selected: list[ArtifactRef] = []
    for artifact in packet.artifact_inventory.artifacts:
        dependency = next(
            (
                item
                for item in getattr(packet, "artifact_dependencies", ())
                if item.artifact.path == artifact.path
            ),
            None,
        )
        if artifact.retention_hold is not None:
            allowed_actions = {ReacquisitionAction.RETAIN_UNDER_HOLD}
        elif any(
            item.criterion_status == "open"
            for item in (
                dependency.evidence_dependencies if dependency is not None else ()
            )
        ):
            allowed_actions = {ReacquisitionAction.REACQUIRE_FROM_SOURCE}
        else:
            allowed_actions = {
                ReacquisitionAction.NOT_REQUIRED,
                ReacquisitionAction.REACQUIRE_FROM_SOURCE,
            }
        choices = "/".join(sorted(item.value for item in allowed_actions))
        streams.errors.write(
            f"Retention or reacquisition action for {artifact.path} ({choices}): "
        )
        streams.errors.flush()
        try:
            action = ReacquisitionAction(streams.input.readline(64).strip())
        except ValueError:
            streams.errors.write("SDE review cancelled; action was invalid.\n")
            return None
        if action not in allowed_actions:
            streams.errors.write(
                "SDE review cancelled; action does not match the packet.\n"
            )
            return None
        selected.append(replace(artifact, reacquisition_action=action))
    return tuple(selected)


def _read_review_decision(streams: _CliStreams) -> ReviewDecision | None:
    """Read the attended SDE decision without consuming action input on error."""

    streams.errors.write("Decision (approve/reject; also purge this exact inventory): ")
    streams.errors.flush()
    decision = {
        "approve": ReviewDecision.APPROVED,
        "reject": ReviewDecision.REJECTED,
    }.get(streams.input.readline(16).strip().lower())
    if decision is None:
        streams.errors.write("SDE review cancelled; no decision was recorded.\n")
    return decision


def _review(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> bool:
    """Show facts and inventory, then commit one attended review/purge action."""

    packet = api.sde_review_packet(
        caller, config.project_id, arguments.candidate_id
    )
    if (
        not packet.artifact_inventory.usage.inventory_complete
        or packet.artifact_inventory.manifest_sha256 is None
    ):
        streams.errors.write("Refusing SDE review because the artifact inventory is incomplete.\n")
        return False
    target = _target(config, arguments.target)
    _write_json(
        streams.output,
        {
            "review_packet": asdict(packet),
            "canonical_target": str(target),
            "review_action": (
                "The exact phrase below approves this SDE disposition and the "
                "displayed complete inventory for purge after canonical persistence."
            ),
        },
    )
    decision = _read_review_decision(streams)
    if decision is None:
        return False
    selected_artifacts = _select_review_artifacts(packet, streams)
    if selected_artifacts is None:
        return False
    selected_packet = api.sde_review_packet(
        caller,
        config.project_id,
        arguments.candidate_id,
        selected_artifacts,
    )
    _write_json(
        streams.output,
        {
            "decision_packet": asdict(selected_packet),
            "canonical_target": str(target),
            "confirmation_phrase": _confirmation_phrase(
                decision,
                arguments.candidate_id,
                packet.artifact_inventory.manifest_sha256,
                selected_packet.dependency_map_sha256,
            ),
        },
    )
    if not confirm_exact_phrase(
        _confirmation_phrase(
            decision,
            arguments.candidate_id,
            packet.artifact_inventory.manifest_sha256,
            selected_packet.dependency_map_sha256,
        ),
        streams.input,
        streams.errors,
        "Refusing human approval without an interactive TTY.\n",
    ):
        streams.errors.write("SDE review cancelled; no decision was recorded.\n")
        return False
    streams.errors.write("Review rationale (one line): ")
    streams.errors.flush()
    rationale = streams.input.readline(1002).rstrip("\r\n")
    if not rationale.strip() or len(rationale) > 1000 or "\n" in rationale:
        streams.errors.write("SDE review cancelled; rationale must be 1-1000 characters.\n")
        return False

    receipt = api.sde_confirm(
        caller,
        config.project_id,
        arguments.candidate_id,
        decision,
        selected_artifacts,
        artifact_inventory_complete=True,
        dependency_map_sha256=selected_packet.dependency_map_sha256,
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
        streams.output,
        {
            "decision": decision.value,
            "receipt_id": receipt.receipt_id,
            "canonical_target": str(projection.target),
            "canonical_sha256": projection.sha256,
            "purge_status": final_receipt.purge_status.value,
            "cleanup_authorization": final_receipt.cleanup_authorized,
            "artifacts": [asdict(item) for item in purge_targets],
        },
    )
    return True


def _expire(
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> int:
    """Display then approve only the complete, exact 72-hour inventory."""

    snapshot = api.discover_project_expiry_inventory(caller, config.project_id)
    _write_json(streams.output, {"expiry_snapshot": asdict(snapshot)})
    if not snapshot.inventory_complete or snapshot.manifest_sha256 is None:
        streams.errors.write(
            "Refusing expiry approval because staging age inventory is incomplete.\n"
        )
        return 2
    if not snapshot.eligible_artifacts:
        streams.errors.write("No unheld artifacts are ready for expiry.\n")
        return 0
    if len(snapshot.eligible_artifacts) > 500:
        streams.errors.write("Expiry inventory exceeds the 500-artifact receipt limit.\n")
        return 2
    phrase = f"PURGE EXPIRED INVENTORY {snapshot.manifest_sha256}"
    if not confirm_exact_phrase(
        phrase,
        streams.input,
        streams.errors,
        "Refusing human approval without an interactive TTY.\n",
    ):
        streams.errors.write("Expiry cleanup cancelled; no approval receipt was recorded.\n")
        return 2
    receipt = api.approve_project_expiry_inventory(
        caller,
        config.project_id,
        snapshot.eligible_artifacts,
        snapshot.manifest_sha256,
    )
    _write_json(streams.output, {"expiry_purge_receipt": asdict(receipt)})
    return 0 if receipt.status.value == "complete" else 1


def _dispatch_operation(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> int:
    """Run one operation after identity, project, and store validation."""

    if arguments.operation == "queue":
        _write_json(
            streams.output,
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
        _write_json(streams.output, {"expiry_purge_receipt": asdict(receipt)})
        return 0 if receipt.status.value == "complete" else 1
    if arguments.operation == "expire":
        return _expire(api, caller, config, streams)
    return 0 if _review(arguments, api, caller, config, streams) else 2


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the attended local review workflow without accepting identity input."""

    arguments = _parser().parse_args(argv)
    streams = _CliStreams(stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr)
    try:
        subject = _local_subject()
        if arguments.operation in {"review", "expire"} and not streams.input.isatty():
            streams.errors.write("Refusing attended review without an interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "expire"} and not streams.output.isatty():
            streams.errors.write("Refusing attended review without a visible interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "expire"} and not streams.errors.isatty():
            streams.errors.write("Refusing attended review without a visible prompt TTY.\n")
            return 2
        database = arguments.database.expanduser()
        if not database.is_absolute():
            raise ValueError("database must be an existing absolute regular file")
        review_authorizer = LocalUIDReviewAuthorizer()
        subject = review_authorizer.authorize_database(database, subject)
        config = ProjectConfig.load(arguments.project_root)
        store = CuratorStore(database)
    except Exception:  # pylint: disable=broad-exception-caught
        streams.errors.write("Curator review failed (identity or configuration error).\n")
        return 2
    try:
        caller = AuthenticatedCaller(subject)
        api = _build_api(config, store, review_authorizer)
        return _dispatch_operation(arguments, api, caller, config, streams)
    except Exception:  # pylint: disable=broad-exception-caught
        streams.errors.write(
            "Curator review failed (authorization, inventory, or persistence error).\n"
        )
        return 2
    finally:
        store.close()
