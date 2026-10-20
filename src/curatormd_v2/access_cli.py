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
import sys
from typing import TextIO

from .api import AuthenticatedCaller, ProjectAction
from .project_access import (
    ProjectAccessManager,
    ProjectAdministrationAction,
)
from .project_config import ProjectConfig
from .store import CuratorStore

_OPERATION_ACTIONS = {
    "register": ProjectAdministrationAction.REGISTER,
    "update": ProjectAdministrationAction.UPDATE,
    "suspend": ProjectAdministrationAction.SUSPEND,
    "reactivate": ProjectAdministrationAction.REACTIVATE,
    "grant": ProjectAdministrationAction.GRANT,
    "revoke": ProjectAdministrationAction.REVOKE,
    "view": ProjectAdministrationAction.VIEW,
}


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
        if name in {"register", "update", "suspend", "reactivate", "grant", "revoke"}:
            command.add_argument("--rationale", required=True)
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


def _confirmation_phrase(operation: str, project_id: str, arguments: argparse.Namespace) -> str:
    """Return the exact confirmation text for the selected operation."""

    if operation in {"grant", "revoke"}:
        return f"{operation.upper()} {arguments.action} {project_id} {arguments.subject_id}"
    if operation == "view":
        return f"VIEW {project_id} ACCESS"
    return f"{operation.upper()} {project_id}"


def _confirm(phrase: str, input_stream: TextIO, errors: TextIO) -> bool:
    if not input_stream.isatty():
        errors.write("Refusing project-access changes without an interactive TTY.\n")
        return False
    errors.write(f"Type exactly: {phrase}\n> ")
    errors.flush()
    try:
        return input_stream.readline(512).rstrip("\r\n") == phrase
    except (OSError, ValueError):
        return False


def _confirmed_caller(
    arguments: argparse.Namespace,
    config: ProjectConfig,
    input_stream: TextIO,
    errors: TextIO,
) -> AuthenticatedCaller | None:
    """Return the local actor only after the operation phrase is confirmed."""

    actor_id = _actor_id()
    phrase = _confirmation_phrase(arguments.operation, config.project_id, arguments)
    if not _confirm(phrase, input_stream, errors):
        return None
    return AuthenticatedCaller(actor_id)


def _perform(
    arguments: argparse.Namespace,
    config: ProjectConfig,
    manager: ProjectAccessManager,
    caller: AuthenticatedCaller,
) -> dict[str, object]:
    operation = arguments.operation
    rationale = getattr(arguments, "rationale", "")
    if not isinstance(rationale, str):
        raise ValueError("rationale must be text")
    if operation == "register":
        record = manager.register_project(
            caller,
            config.project_id,
            config.repository_fingerprint,
            config.config_sha256,
            config.backend_api_version,
            rationale,
        )
        return {"operation": operation, "registration": asdict(record)}
    if operation == "update":
        record = manager.update_project_registration(
            caller,
            config.project_id,
            config.repository_fingerprint,
            config.config_sha256,
            config.backend_api_version,
            rationale,
        )
        return {"operation": operation, "registration": asdict(record)}
    if operation in {"suspend", "reactivate"}:
        record = manager.set_project_status(
            caller,
            config.project_id,
            "suspended" if operation == "suspend" else "active",
            rationale,
        )
        return {"operation": operation, "registration": asdict(record)}
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
        registration = manager.get_registration(caller, config.project_id)
        return {
            "operation": operation,
            "registration": asdict(registration),
            "grants": [asdict(item) for item in manager.list_grants(caller, config.project_id)],
            "audit": [
                asdict(item)
                for item in manager.list_registration_audit(caller, config.project_id)
            ],
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
        result = _perform(arguments, config, manager, caller)
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
