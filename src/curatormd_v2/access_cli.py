"""Attended local-terminal administration for project registrations/grants.

This is deliberately separate from MCP. The local OS UID is the audit subject;
the command is not a substitute for a deployed identity provider or role system.
Every operation requires a TTY and an exact confirmation phrase.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys
from typing import TextIO

from .api import AuthenticatedCaller, ProjectAction
from .cli_interaction import confirm_exact_phrase
from .project_access import (
    ProjectAccessManager,
    ProjectAdministrationAction,
)
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .store import (
    ConsumerBindingTransitionRequest,
    CuratorStore,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
)

_OPERATION_ACTIONS = {
    "register": ProjectAdministrationAction.REGISTER,
    "update": ProjectAdministrationAction.UPDATE,
    "suspend": ProjectAdministrationAction.SUSPEND,
    "reactivate": ProjectAdministrationAction.REACTIVATE,
    "deregister": ProjectAdministrationAction.DEREGISTER,
    "deregister_finalize": ProjectAdministrationAction.DEREGISTER_FINALIZE,
    "reenroll": ProjectAdministrationAction.REENROLL,
    "drain": ProjectAdministrationAction.DRAIN,
    "dispose_event": ProjectAdministrationAction.DISPOSE_EVENT,
    "retire": ProjectAdministrationAction.RETIRE,
    "grant": ProjectAdministrationAction.GRANT,
    "revoke": ProjectAdministrationAction.REVOKE,
    "view": ProjectAdministrationAction.VIEW,
}
_TRANSITION_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def _transition_id(value: str) -> str:
    """Reject control characters before an identifier enters a TTY prompt."""

    if not _TRANSITION_ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "transition ID must be a bounded opaque identifier"
        )
    return value


def _positive_revision(value: str) -> int:
    """Parse a positive reviewed revision before displaying confirmation."""

    try:
        revision = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("revision must be a positive integer") from exc
    if revision < 1:
        raise argparse.ArgumentTypeError("revision must be a positive integer")
    return revision


def _sha256(value: str) -> str:
    """Parse one lowercase SHA-256 from the reviewed status packet."""

    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("value must be a lowercase SHA-256")
    return value


class _SingleOperationPolicy:
    """Allow one confirmed operation for one local-UID administrator."""

    # This class implements exactly one authorization protocol method.
    # pylint: disable=too-few-public-methods

    def __init__(
        self,
        actor_id: str,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> None:
        self.actor_id = actor_id
        self.project_id = project_id
        self.action = action

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow only the confirmed actor, project, and action tuple."""
        return (
            caller.subject_id == self.actor_id
            and project_id == self.project_id
            and action is self.action
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curatormd-v2-access",
        description=(
            "Attend one local project-access operation. This command is not "
            "exposed through MCP and requires an interactive terminal."
        ),
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in _OPERATION_ACTIONS:
        command = commands.add_parser(name)
        command.add_argument("--project-root", required=True, type=Path)
        command.add_argument("--database", required=True, type=Path)
        if name in {
            "register", "update", "suspend", "reactivate", "deregister",
            "deregister_finalize", "reenroll", "grant", "revoke",
            "drain", "dispose_event", "retire",
        }:
            command.add_argument("--rationale", required=True)
        if name in {
            "update", "suspend", "reactivate", "deregister",
            "deregister_finalize", "reenroll",
            "drain", "dispose_event", "retire",
        }:
            command.add_argument(
                "--expected-revision", required=True, type=_positive_revision
            )
            command.add_argument("--transition-id", required=True, type=_transition_id)
        if name == "reenroll":
            command.add_argument(
                "--expected-source-epoch", required=True, type=_positive_revision
            )
            command.add_argument(
                "--expected-project-revision", required=True, type=_positive_revision
            )
        if name == "reactivate":
            command.add_argument("--review-packet-sha256", required=True, type=_sha256)
            command.add_argument(
                "--suspension-transition-id", required=True, type=_transition_id
            )
        if name == "drain":
            command.add_argument("--inventory-sha256", required=True)
            command.add_argument("--lifetime-seconds", required=True, type=int)
            command.add_argument("--consumer-profile", required=True)
        if name == "dispose_event":
            command.add_argument("--event-id", required=True)
            command.add_argument("--payload-sha256", required=True)
            command.add_argument("--expected-source-epoch", required=True, type=_positive_revision)
        if name == "view":
            command.add_argument("--event-limit", type=int, default=100)
            command.add_argument("--event-after")
        if name in {"grant", "revoke"}:
            command.add_argument("--subject-id", required=True)
            command.add_argument(
                "--action",
                required=True,
                choices=[action.value for action in ProjectAction],
            )
    return parser


def _actor_id() -> str:
    """Name the effective local OS account without accepting an ID argument."""

    if not hasattr(os, "getuid") or not hasattr(os, "geteuid"):
        raise OSError("local UID identity is unavailable")
    if os.getuid() != os.geteuid():
        raise PermissionError("set-user-ID execution is not supported")
    return f"local-uid:{os.geteuid()}"


def _confirmation_phrase(
    operation: str, config: ProjectConfig, arguments: argparse.Namespace
) -> str:
    """Return the exact confirmation text for the selected operation."""

    if operation in {"grant", "revoke"}:
        return (
            f"{operation.upper()} {arguments.action} {config.project_id} "
            f"{arguments.subject_id}"
        )
    if operation == "view":
        return f"VIEW {config.project_id} ACCESS"
    if operation == "update":
        return (
            f"UPDATE {config.project_id} TRANSITION {arguments.transition_id} "
            f"AT REVISION {arguments.expected_revision} "
            f"TO REPOSITORY {config.repository_fingerprint} CONFIG "
            f"{config.config_sha256} API {config.backend_api_version}"
        )
    if operation == "suspend":
        return (
            f"{operation.upper()} {config.project_id} "
            f"AT REVISION {arguments.expected_revision} "
            f"TRANSITION {arguments.transition_id}"
        )
    if operation == "reactivate":
        return (
            f"REACTIVATE {config.project_id} AT REVISION "
            f"{arguments.expected_revision} AFTER SUSPENSION "
            f"{arguments.suspension_transition_id} REVIEW "
            f"{arguments.review_packet_sha256} TRANSITION "
            f"{arguments.transition_id}"
        )
    if operation in {"deregister", "deregister_finalize"}:
        return (
            f"{operation.upper()} {config.project_id} "
            f"AT BINDING REVISION {arguments.expected_revision} "
            f"TRANSITION {arguments.transition_id}"
        )
    if operation == "reenroll":
        return (
            f"REENROLL {config.project_id} FROM SOURCE EPOCH "
            f"{arguments.expected_source_epoch} AT BINDING REVISION "
            f"{arguments.expected_revision} PROJECT REVISION "
            f"{arguments.expected_project_revision} TRANSITION "
            f"{arguments.transition_id} REPOSITORY "
            f"{config.repository_fingerprint} CONFIG {config.config_sha256} "
            f"API {config.backend_api_version}"
        )
    if operation == "drain":
        return (
            f"DRAIN {config.project_id} TRANSITION {arguments.transition_id} "
            f"AT BINDING REVISION {arguments.expected_revision} "
            f"INVENTORY {arguments.inventory_sha256} FOR "
            f"{arguments.lifetime_seconds} SECONDS PROFILE "
            f"{arguments.consumer_profile}"
        )
    if operation == "dispose_event":
        return (
            f"DISPOSE EVENT {config.project_id} {arguments.event_id} AT BINDING "
            f"REVISION {arguments.expected_revision} SOURCE EPOCH "
            f"{arguments.expected_source_epoch} TRANSITION "
            f"{arguments.transition_id} PAYLOAD {arguments.payload_sha256}"
        )
    if operation == "retire":
        return (
            f"RETIRE PROJECT {config.project_id} AT REVISION "
            f"{arguments.expected_revision} TRANSITION {arguments.transition_id}"
        )
    return f"{operation.upper()} {config.project_id}"


def _confirmed_caller(
    arguments: argparse.Namespace,
    config: ProjectConfig,
    input_stream: TextIO,
    errors: TextIO,
) -> AuthenticatedCaller | None:
    """Return the local actor only after the operation phrase is confirmed."""

    actor_id = _actor_id()
    phrase = _confirmation_phrase(arguments.operation, config, arguments)
    if not confirm_exact_phrase(
        phrase,
        input_stream,
        errors,
        "Refusing project-access changes without an interactive TTY.\n",
    ):
        return None
    return AuthenticatedCaller(actor_id)


def _perform(
    arguments: argparse.Namespace,
    config: ProjectConfig,
    manager: ProjectAccessManager,
    caller: AuthenticatedCaller,
    plugin: ProjectPlugin | None = None,
) -> dict[str, object]:
    operation = arguments.operation
    rationale = getattr(arguments, "rationale", "")
    if not isinstance(rationale, str):
        raise ValueError("rationale must be text")
    if operation == "register":
        record = manager.register_project(
            caller,
            ProjectRegistrationRequest.from_project_config(config, rationale),
        )
        return {"operation": operation, "registration": asdict(record)}
    if operation == "update":
        result = manager.update_project_registration(
            caller,
            ProjectRegistrationRequest.from_project_config(
                config, rationale, arguments.expected_revision
            ),
            arguments.transition_id,
        )
        return {
            "operation": operation,
            "registration": asdict(result.registration),
            "transition_receipt": asdict(result.receipt),
            "replayed": result.replayed,
        }
    if operation in {"suspend", "reactivate"}:
        review_packet_sha256: str | None = None
        suspension_transition_id: str | None = None
        staging_inventory_sha256: str | None = None
        staging_inventory_count: int | None = None
        staging_inventory_bytes: int | None = None
        staging_inventory_observed_at: str | None = None
        if operation == "reactivate":
            if plugin is None:
                raise ValueError("reactivation requires a repository staging scan")
            with plugin.project_effect_lock():
                inventory = plugin.review_staging_inventory()
                packet = manager.project_reactivation_review_packet(
                    caller,
                    config.project_id,
                    inventory,
                    for_reactivation=True,
                )
                if packet.complete and (
                    packet.packet_sha256 != arguments.review_packet_sha256
                    or packet.suspension_transition_id
                    != arguments.suspension_transition_id
                    or packet.repository_fingerprint
                    != config.repository_fingerprint
                    or packet.config_sha256 != config.config_sha256
                    or packet.backend_api_version != config.backend_api_version
                ):
                    raise ValueError(
                        "reactivation review changed; obtain a fresh view"
                    )
                review_packet_sha256 = arguments.review_packet_sha256
                suspension_transition_id = arguments.suspension_transition_id
                if packet.complete:
                    staging_inventory_sha256 = packet.staging_inventory_sha256
                    staging_inventory_count = packet.staging_inventory_count
                    staging_inventory_bytes = packet.staging_inventory_bytes
                    staging_inventory_observed_at = (
                        packet.staging_inventory_observed_at
                    )
                request = ProjectStatusChangeRequest(
                    project_id=config.project_id,
                    status="active",
                    rationale=rationale,
                    expected_revision=arguments.expected_revision,
                    transition_id=arguments.transition_id,
                    review_packet_sha256=review_packet_sha256,
                    suspension_transition_id=suspension_transition_id,
                    staging_inventory_sha256=staging_inventory_sha256,
                    staging_inventory_count=staging_inventory_count,
                    staging_inventory_bytes=staging_inventory_bytes,
                    staging_inventory_observed_at=staging_inventory_observed_at,
                )
                result = manager.set_project_status(caller, request)
        else:
            result = manager.set_project_status(
                caller,
                ProjectStatusChangeRequest(
                    project_id=config.project_id,
                    status="suspended",
                    rationale=rationale,
                    expected_revision=arguments.expected_revision,
                    transition_id=arguments.transition_id,
                ),
            )
        return {
            "operation": operation,
            "registration": asdict(result.registration),
            "transition_receipt": asdict(result.receipt),
            "replayed": result.replayed,
        }
    if operation in {"deregister", "deregister_finalize", "reenroll"}:
        is_reenroll = operation == "reenroll"
        result = manager.transition_consumer_binding(
            caller,
            ConsumerBindingTransitionRequest(
                project_id=config.project_id,
                status=(
                    "deregistration_pending"
                    if operation == "deregister"
                    else "deregistered"
                    if operation == "deregister_finalize"
                    else "active"
                ),
                rationale=rationale,
                expected_revision=arguments.expected_revision,
                transition_id=arguments.transition_id,
                expected_source_epoch=(
                    arguments.expected_source_epoch if is_reenroll else None
                ),
                expected_project_revision=(
                    arguments.expected_project_revision if is_reenroll else None
                ),
                repository_fingerprint=(
                    config.repository_fingerprint if is_reenroll else None
                ),
                config_sha256=config.config_sha256 if is_reenroll else None,
                backend_api_version=(
                    config.backend_api_version if is_reenroll else None
                ),
            ),
        )
        return {
            "operation": operation,
            "binding": asdict(result.binding),
            "transition_receipt": asdict(result.receipt),
            "replayed": result.replayed,
        }
    if operation == "drain":
        count, expires_at = manager.authorize_consumer_drain(
            caller,
            config.project_id,
            arguments.transition_id,
            arguments.expected_revision,
            arguments.inventory_sha256,
            arguments.lifetime_seconds,
            arguments.consumer_profile,
        )
        return {
            "operation": operation,
            "authorized_event_count": count,
            "expires_at": expires_at,
        }
    if operation == "dispose_event":
        receipt, disposition = manager.terminally_dispose_event(
            caller,
            project_id=config.project_id,
            event_id=arguments.event_id,
            transition_id=arguments.transition_id,
            rationale=rationale,
            expected_binding_revision=arguments.expected_revision,
            expected_source_epoch=arguments.expected_source_epoch,
            expected_payload_sha256=arguments.payload_sha256,
        )
        return {
            "operation": operation,
            "receipt": asdict(receipt),
            "terminal_disposition": asdict(disposition),
        }
    if operation == "retire":
        receipt = manager.retire_project(
            caller,
            config.project_id,
            rationale,
            arguments.expected_revision,
            arguments.transition_id,
        )
        return {"operation": operation, "retirement": asdict(receipt)}
    if operation in {"grant", "revoke"}:
        action = ProjectAction(arguments.action)
        method = manager.grant if operation == "grant" else manager.revoke
        record = method(
            caller,
            config.project_id,
            arguments.subject_id,
            action,
            rationale,
        )
        return {"operation": operation, "grant": asdict(record)}
    if operation == "view":
        lifecycle_status = manager.lifecycle_status_snapshot(
            caller,
            config.project_id,
            event_limit=arguments.event_limit,
            after_event_id=arguments.event_after,
        )
        registration = manager.get_registration(caller, config.project_id)
        reactivation_review: dict[str, object] | None = None
        if registration.status == "suspended" and plugin is not None:
            inventory = plugin.review_staging_inventory()
            packet = manager.project_reactivation_review_packet(
                caller, config.project_id, inventory
            )
            reactivation_review = asdict(packet)
        return {
            "operation": operation,
            "registration": asdict(registration),
            "reactivation_review": reactivation_review,
            "consumer_binding": asdict(lifecycle_status.consumer_binding),
            "grants": [asdict(item) for item in manager.list_grants(caller, config.project_id)],
            "audit": [
                asdict(item)
                for item in manager.list_registration_audit(caller, config.project_id)
            ],
            "consumer_binding_audit": [
                asdict(item)
                for item in manager.list_consumer_binding_audit(caller, config.project_id)
            ],
            "retirement": (
                asdict(lifecycle_status.retirement)
                if lifecycle_status.retirement is not None
                else None
            ),
            "unprocessed_event_inventory": {
                "count": lifecycle_status.unprocessed_event_count,
                "sha256": lifecycle_status.unprocessed_event_sha256,
            },
            "terminal_event_inventory": asdict(
                lifecycle_status.terminal_event_inventory
            ),
            "lifecycle_status": asdict(lifecycle_status),
            "control_plane_storage_usage": asdict(
                manager.storage_usage(caller, config.project_id)
            ),
        }
    raise ValueError("unsupported operation")


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Perform one attended, audited local project-access operation."""

    arguments = _parser().parse_args(argv)
    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    database = arguments.database.expanduser()
    if not database.is_absolute():
        errors.write("Curator access operation failed (invalid configuration).\n")
        return 2

    store: CuratorStore | None = None
    try:
        config = ProjectConfig.load(arguments.project_root)
        caller = _confirmed_caller(arguments, config, input_stream, errors)
        if caller is None:
            return 2
        store = CuratorStore(database)
        manager = ProjectAccessManager(
            store,
            _SingleOperationPolicy(
                caller.subject_id,
                config.project_id,
                _OPERATION_ACTIONS[arguments.operation],
            ),
        )
        plugin = (
            ProjectPlugin.bind(config, store)
            if arguments.operation in {"view", "reactivate"}
            else None
        )
        result = _perform(arguments, config, manager, caller, plugin)
        output.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except Exception:  # pylint: disable=broad-exception-caught
        errors.write("Curator access operation failed (policy or runtime error).\n")
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
