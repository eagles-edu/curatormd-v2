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
import re
import stat
import sys
from typing import TextIO

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .cli_interaction import (
    SafeArgumentParser,
    confirm_exact_phrase,
    parse_safe_arguments,
)
from .evidence import EvidenceVerifier
from .hosted_mcp import validate_host_evidence_config_path
from .local_evidence_config import load_local_evidence_verifier
from .models import (
    ArtifactRef,
    ReacquisitionAction,
    ReviewDecision,
    SDEConfirmationRequest,
    SDEReviewPacket,
)
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAuthorizationBinding,
)
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .process_privacy import protect_process_data
from .rate_limiter import SQLiteTokenBucket
from .local_review_authorizer import LocalUIDReviewAuthorizer as _LocalUIDReviewAuthorizer
from .reviews import ReviewAuthorizationError
from .service_types import EvidenceGateError
from .store import CuratorStore
from .sde_review_draft import SDEReviewDraft


class LocalUIDReviewAuthorizer(_LocalUIDReviewAuthorizer):
    """Keep CLI identity sourced from its attended process boundary."""

    # pylint: disable=too-few-public-methods

    @staticmethod
    def _subject(authenticated_subject: str | None) -> str:
        """Require the OS identity selected by the local review CLI."""

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
    parser = SafeArgumentParser(
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
    parser.add_argument(
        "--evidence-config",
        type=Path,
        help="owner-only host evidence config path; never stored in the project",
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("queue", help="show pending SDE candidates")
    review = commands.add_parser("review", help="review and disposition one candidate")
    review.add_argument("candidate_id")
    review.add_argument(
        "--decision-hint", choices=("approve", "reject"),
        help=(
            "review action selected in the editor; the final binding phrase "
            "confirms it in the terminal"
        ),
    )
    review.add_argument(
        "--edited-draft", action="store_true",
        help="review the saved candidate-specific decision in the project review document",
    )
    resume_review = commands.add_parser(
        "resume-review", help="resume exact approved SDE destination writes from a receipt"
    )
    resume_review.add_argument("receipt_id")
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
    evidence_verifier: EvidenceVerifier | None = None,
) -> AuthenticatedCuratorAPI:
    """Build a project-fingerprint-bound API with a local UID review host."""

    plugin = ProjectPlugin.bind(
        config,
        store,
        evidence_verifier=evidence_verifier,
        review_authorizer=review_authorizer,
    )
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
    output.flush()


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


def _read_review_decision(
    streams: _CliStreams, decision_hint: str | None = None
) -> ReviewDecision | None:
    """Read the attended SDE decision, using an editor choice when supplied."""

    if decision_hint:
        streams.errors.write(
            f"Editor selection: {decision_hint}. Review the packet; "
            "the final binding phrase confirms this choice.\n"
        )
        return {
            "approve": ReviewDecision.APPROVED,
            "reject": ReviewDecision.REJECTED,
        }.get(decision_hint)
    streams.errors.write("Decision (approve/reject; also purge this exact inventory): ")
    streams.errors.flush()
    return {
        "approve": ReviewDecision.APPROVED,
        "reject": ReviewDecision.REJECTED,
    }.get(streams.input.readline(16).strip().lower())


def _saved_review_draft(config: ProjectConfig, candidate_id: str) -> SDEReviewDraft:
    """Read one bounded saved draft from this project's fixed review document."""

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", candidate_id):
        raise ValueError("invalid SDE candidate ID")
    state_root = config.project_root / ".curatormd-v2"
    review_dir = state_root / "sde-proposals"
    for directory in (state_root, review_dir):
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("invalid review document directory")
    path = review_dir / "pending-review.md"
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("safe review document reads are unavailable")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid() or before.st_size > 1024 * 1024:
            raise ValueError("review document is invalid or too large")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            content = source.read(1024 * 1024 + 1)
        after = os.fstat(descriptor)
        current = path.lstat()
        if (
            len(content) > 1024 * 1024
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
            or not stat.S_ISREG(current.st_mode)
        ):
            raise ValueError("review document changed during reading")
    finally:
        os.close(descriptor)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("review document must be UTF-8") from None
    start = f"<!-- curator-v2-decision:{candidate_id}:start -->"
    end = f"<!-- curator-v2-decision:{candidate_id}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("review decision block is missing or ambiguous")
    prefix, remaining = text.split(start, 1)
    del prefix
    block, _suffix = remaining.split(end, 1)
    match = re.fullmatch(r"\s*(`{3,})json\s*\n(.*?)\n\1\s*", block, re.DOTALL)
    if match is None:
        raise ValueError("review decision block must contain one JSON object")
    draft = SDEReviewDraft.from_json(match.group(2))
    draft.validated_targets(config)
    return draft


def _review_edited(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> bool:
    """Review the saved edited copy and journal each selected projection."""

    draft = _saved_review_draft(config, arguments.candidate_id)
    packet = api.sde_review_packet(caller, config.project_id, arguments.candidate_id)
    if not packet.artifact_inventory.usage.inventory_complete or packet.artifact_inventory.manifest_sha256 is None:
        streams.errors.write("Refusing SDE review because the artifact inventory is incomplete.\n")
        return False
    _write_json(streams.output, {"review_packet": asdict(packet), "edited_entry": asdict(draft)})
    decision = _read_review_decision(streams, getattr(arguments, "decision_hint", None))
    if decision is None:
        return False
    selected_artifacts = _select_review_artifacts(packet, streams)
    if selected_artifacts is None:
        return False
    selected_packet = api.sde_review_packet(
        caller, config.project_id, arguments.candidate_id, selected_artifacts
    )
    streams.errors.write("Review rationale (one line): ")
    streams.errors.flush()
    rationale = streams.input.readline(1002).rstrip("\r\n")
    if not rationale.strip() or len(rationale) > 1000 or "\n" in rationale or "\r" in rationale:
        streams.errors.write("SDE review cancelled; rationale must be 1-1000 characters.\n")
        return False
    request = SDEConfirmationRequest(
        candidate_id=arguments.candidate_id,
        decision=decision,
        artifacts=selected_artifacts,
        artifact_inventory_complete=True,
        dependency_map_sha256=selected_packet.dependency_map_sha256,
        rationale=rationale,
        review_draft=draft,
    )
    binding = api.prepare_sde_review_binding(caller, config.project_id, request)
    phrase = _confirmation_phrase(
        decision, arguments.candidate_id,
        packet.artifact_inventory.manifest_sha256,
        selected_packet.dependency_map_sha256,
    ) + f" BINDING {binding.sha256()}"
    _write_json(streams.output, {
        "decision_packet": asdict(selected_packet),
        "edited_entry": asdict(draft),
        "binding": asdict(binding),
        "confirmation_phrase": phrase,
    })
    if draft.significance == 5 and not confirm_exact_phrase(
        "CONFIRM SIGNIFICANCE 5", streams.input, streams.errors,
        "Refusing significance confirmation without an interactive TTY.\n",
    ):
        streams.errors.write("SDE review cancelled; no decision was recorded.\n")
        return False
    if not confirm_exact_phrase(
        phrase, streams.input, streams.errors,
        "Refusing human approval without an interactive TTY.\n",
    ):
        streams.errors.write("SDE review cancelled; no decision was recorded.\n")
        return False
    receipt = api.sde_confirm(
        caller, config.project_id,
        replace(request, expected_review_binding_sha256=binding.sha256(),
                confirm_significance_five=draft.significance == 5),
    )
    _write_json(streams.output, {
        "decision": decision.value, "receipt_id": receipt.receipt_id,
        "projection_status": "pending", "cleanup_status": "pending",
    })
    if decision is ReviewDecision.APPROVED:
        for target in draft.documents:
            api.sde_project_review_target(
                caller, config.project_id, receipt.receipt_id, target, prepare_only=True
            )
        for target in draft.documents:
            api.sde_project_review_target(
                caller, config.project_id, receipt.receipt_id, target, prepare_only=False
            )
        projected = api.sde_review_projection_status(
            caller, config.project_id, receipt.receipt_id
        )
        if len(projected) != len(draft.documents) or any(
            digest is None or projected_at is None
            for _path, digest, projected_at in projected
        ):
            _write_json(streams.output, {
                "receipt_id": receipt.receipt_id,
                "projection_status": "pending",
                "destinations": [
                    {"path": path, "projection_sha256": digest, "projected_at": projected_at}
                    for path, digest, projected_at in projected
                ],
                "cleanup_status": "pending",
            })
            return False
        final_receipt = api.sde_finalize_review_projection(
            caller, config.project_id, receipt.receipt_id
        )
        final_receipt, purge_targets = api.artifact_purge_status(
            caller, config.project_id, receipt.receipt_id
        )
        _write_json(streams.output, {
            "receipt_id": final_receipt.receipt_id,
            "projection_status": "complete",
            "purge_status": final_receipt.purge_status.value,
            "cleanup_status": final_receipt.purge_status.value,
            "artifact_status": [asdict(item) for item in purge_targets],
        })
        return final_receipt.purge_status.value == "complete"
    final_receipt = api.sde_finalize_review_projection(
        caller, config.project_id, receipt.receipt_id
    )
    final_receipt, purge_targets = api.artifact_purge_status(
        caller, config.project_id, receipt.receipt_id
    )
    _write_json(streams.output, {
        "receipt_id": final_receipt.receipt_id,
        "projection_status": "not_applicable",
        "canonical_receipt": final_receipt.canonical_target,
        "purge_status": final_receipt.purge_status.value,
        "cleanup_status": final_receipt.purge_status.value,
        "artifact_status": [asdict(item) for item in purge_targets],
    })
    return final_receipt.purge_status.value == "complete"


def _review(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> bool:
    """Show facts and inventory, then commit one attended review/purge action."""

    if getattr(arguments, "edited_draft", False):
        return _review_edited(arguments, api, caller, config, streams)

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
    decision = _read_review_decision(streams, getattr(arguments, "decision_hint", None))
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
        SDEConfirmationRequest(
            candidate_id=arguments.candidate_id,
            decision=decision,
            artifacts=selected_artifacts,
            artifact_inventory_complete=True,
            dependency_map_sha256=selected_packet.dependency_map_sha256,
            rationale=rationale,
        ),
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


def _resume_review_projection(
    arguments: argparse.Namespace,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    config: ProjectConfig,
    streams: _CliStreams,
) -> bool:
    """Resume only the destinations already bound to an approved receipt."""

    receipt, artifacts = api.artifact_purge_status(
        caller, config.project_id, arguments.receipt_id
    )
    if (
        receipt.decision is not ReviewDecision.APPROVED
        or receipt.review_draft_json is None
        or receipt.review_binding_json is None
        or receipt.review_binding_sha256 is None
    ):
        raise ValueError("receipt is not an approved edited SDE review")
    draft = SDEReviewDraft.from_json(receipt.review_draft_json)
    if receipt.canonical_persisted and receipt.cleanup_canonical_persisted:
        destinations = api.sde_review_projection_status(
            caller, config.project_id, receipt.receipt_id
        )
        _write_json(streams.output, {
            "receipt_id": receipt.receipt_id,
            "projection_status": "complete",
            "destinations": [
                {"path": path, "projection_sha256": digest, "projected_at": projected_at}
                for path, digest, projected_at in destinations
            ],
            "purge_status": receipt.purge_status.value,
            "cleanup_status": receipt.purge_status.value,
            "artifact_status": [asdict(item) for item in artifacts],
        })
        if receipt.purge_status.value != "complete":
            streams.errors.write(
                "Projection is canonical; use the authorized pending-purge retry to reconcile cleanup.\n"
            )
        return receipt.purge_status.value == "complete"
    destinations = api.sde_review_projection_status(
        caller, config.project_id, receipt.receipt_id
    )
    phrase = f"RESUME SDE {receipt.receipt_id} BINDING {receipt.review_binding_sha256}"
    _write_json(streams.output, {
        "receipt_id": receipt.receipt_id,
        "candidate_id": receipt.candidate_id,
        "destinations": [
            {"path": path, "projection_sha256": digest, "projected_at": projected_at}
            for path, digest, projected_at in destinations
        ],
        "artifact_status": [asdict(item) for item in artifacts],
        "cleanup_status": "pending",
        "confirmation_phrase": phrase,
    })
    if not confirm_exact_phrase(
        phrase, streams.input, streams.errors,
        "Refusing SDE recovery without an interactive TTY.\n",
    ):
        streams.errors.write("SDE projection recovery cancelled.\n")
        return False
    for target in draft.documents:
        api.sde_project_review_target(
            caller, config.project_id, receipt.receipt_id, target, prepare_only=True
        )
    for target in draft.documents:
        api.sde_project_review_target(
            caller, config.project_id, receipt.receipt_id, target, prepare_only=False
        )
    projected = api.sde_review_projection_status(
        caller, config.project_id, receipt.receipt_id
    )
    complete = len(projected) == len(draft.documents) and all(
        digest is not None and projected_at is not None
        for _path, digest, projected_at in projected
    )
    final_receipt = receipt
    purge_targets = artifacts
    if complete:
        final_receipt = api.sde_finalize_review_projection(
            caller, config.project_id, receipt.receipt_id
        )
        final_receipt, purge_targets = api.artifact_purge_status(
            caller, config.project_id, receipt.receipt_id
        )
    _write_json(streams.output, {
        "receipt_id": final_receipt.receipt_id,
        "projection_status": "complete" if complete else "pending",
        "destinations": [
            {"path": path, "projection_sha256": digest, "projected_at": projected_at}
            for path, digest, projected_at in projected
        ],
        "purge_status": final_receipt.purge_status.value,
        "cleanup_status": final_receipt.purge_status.value,
        "artifact_status": [asdict(item) for item in purge_targets],
    })
    return complete and final_receipt.purge_status.value == "complete"


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
    if arguments.operation == "resume-review":
        return 0 if _resume_review_projection(arguments, api, caller, config, streams) else 2
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

    streams = _CliStreams(stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr)
    if not protect_process_data():
        streams.errors.write("Curator review failed (privacy limits unavailable).\n")
        return 2
    arguments = parse_safe_arguments(
        _parser(), argv, streams.errors,
        "Curator review failed (invalid command arguments).\n",
    )
    if arguments is None:
        return 2
    try:
        subject = _local_subject()
        if arguments.operation in {"review", "resume-review", "expire"} and not streams.input.isatty():
            streams.errors.write("Refusing attended review without an interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "resume-review", "expire"} and not streams.output.isatty():
            streams.errors.write("Refusing attended review without a visible interactive TTY.\n")
            return 2
        if arguments.operation in {"review", "resume-review", "expire"} and not streams.errors.isatty():
            streams.errors.write("Refusing attended review without a visible prompt TTY.\n")
            return 2
        database = arguments.database.expanduser()
        if not database.is_absolute():
            raise ValueError("database must be an existing absolute regular file")
        review_authorizer = LocalUIDReviewAuthorizer()
        subject = review_authorizer.authorize_database(database, subject)
        config = ProjectConfig.load(arguments.project_root)
        evidence_verifier = None
        if arguments.evidence_config is not None:
            evidence_path = validate_host_evidence_config_path(
                arguments.evidence_config, config.project_root
            )
            evidence_verifier = load_local_evidence_verifier(
                evidence_path, project_id=config.project_id
            )
        store = CuratorStore(database)
    except Exception:  # pylint: disable=broad-exception-caught
        streams.errors.write("Curator review failed (identity or configuration error).\n")
        return 2
    try:
        caller = AuthenticatedCaller(subject)
        api = _build_api(
            config, store, review_authorizer, evidence_verifier=evidence_verifier
        )
        return _dispatch_operation(arguments, api, caller, config, streams)
    except EvidenceGateError:
        streams.errors.write(
            "Curator did not record approval because current verification evidence is missing or stale.\n"
        )
        return 2
    except Exception:  # pylint: disable=broad-exception-caught
        streams.errors.write(
            "Curator review failed (authorization, inventory, or persistence error).\n"
        )
        return 2
    finally:
        store.close()
