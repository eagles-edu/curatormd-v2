"""Local, profile-bound stdio host for one Curator V2 project.

This entrypoint is intended for a trusted local orchestrator such as one
Hermes profile spawning one MCP subprocess. The operating system supplies the
authenticated local account; Hermes separately supplies the profile and
session for routing. Neither identity can be selected by tool arguments.
The profile receives only project read access by default and optional project
write and review access, each requiring an exact durable grant and an explicit
launcher ceiling. Review decisions are additionally bound to the current
non-setuid local UID. This is an attended single-user alpha identity; it does
not authenticate a remote Hermes user. Purge, retention-hold, and event-retry
actions remain separately scoped.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys

from mcp.server import MCPServer

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .cli_interaction import SafeArgumentParser, parse_safe_arguments
from .evidence import EvidenceVerifier
from .local_evidence_config import load_local_evidence_verifier
from .local_review_authorizer import LocalUIDReviewAuthorizer
from .mcp_server import HermesContextOptions, RequestHostReadiness, build_mcp_server
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectBindingStartupError,
    ProjectAuthorizationBinding,
    require_active_project_action,
    require_active_project_read,
)
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .process_privacy import protect_process_data
from .rate_limiter import SQLiteTokenBucket
from .store import CuratorStore


_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def _local_account_subject() -> str:
    """Return the kernel-reported local account used to launch this process."""

    get_effective_uid = getattr(os, "geteuid", None)
    get_real_uid = getattr(os, "getuid", None)
    if not callable(get_effective_uid) or not callable(get_real_uid):
        raise RuntimeError("the local host does not provide a trusted account ID")
    real_uid = get_real_uid()
    effective_uid = get_effective_uid()
    if real_uid != effective_uid:
        raise RuntimeError("set-user-ID execution cannot establish local identity")
    return f"local-uid:{effective_uid}"


def set_process_privacy_limits() -> None:
    """Restrict files and core dumps created by this local MCP process."""

    if not protect_process_data():
        raise RuntimeError("local MCP privacy limits are unavailable")


def validate_host_evidence_config_path(
    path: str | Path, project_root: Path
) -> Path:
    """Reject local evidence config paths that resolve inside a consumer repo."""

    selected = Path(path).expanduser()
    if not selected.is_absolute():
        raise ValueError("host evidence config must use an absolute path")
    try:
        resolved = selected.resolve(strict=False)
    except (OSError, RuntimeError):
        raise ValueError("host evidence config path is invalid") from None
    if resolved == project_root or project_root in resolved.parents:
        raise ValueError("host evidence config must be outside the consumer repository")
    return selected


@dataclass(slots=True)
class LocalProfileMCP:
    """Resources held for the lifetime of one local MCP process."""

    server: MCPServer
    store: CuratorStore
    api: AuthenticatedCuratorAPI
    caller: AuthenticatedCaller
    project_id: str

    def close(self) -> None:
        """Close the profile's SQLite connection."""

        self.store.close()


# pylint: disable=too-many-arguments,too-many-locals
def build_local_profile_mcp(
    *,
    project_root: str | Path,
    database: str | Path,
    profile_id: str,
    source_id: str | None = None,
    allow_write: bool = False,
    allow_review: bool = False,
    allow_event_retry: bool = False,
    allow_retention_hold_release: bool = False,
    allow_purge_retry: bool = False,
    require_authenticated_subject: bool = False,
    evidence_verifier: EvidenceVerifier | None = None,
    evidence_config: str | Path | None = None,
) -> LocalProfileMCP:
    """Bind one local profile to the project declared by its repo config.

    The profile ID and requested action ceiling must come from
    operator-controlled launcher configuration. Durable project registration
    and exact action grants must already exist; this project plugin never
    self-registers or grants access. No tool argument can choose a caller or
    project. The repository-owned config is validated by ``ProjectConfig.load``
    before any plugin is bound. A supplied verifier must be built from
    host-owned trust configuration, never the consumer repository config.
    ``evidence_config`` loads one owner-only local service probe from a
    separate host file. Supplying both forms is rejected. Omitting both
    preserves the reject-all evidence default.
    """

    if not _PROFILE_ID_RE.fullmatch(profile_id):
        raise ValueError("profile_id must be a bounded opaque identifier")
    selected_source_id = source_id or f"hermes-profile:{profile_id}"
    if not _SOURCE_ID_RE.fullmatch(selected_source_id):
        raise ValueError("source_id must be a bounded opaque identifier")
    database_path = Path(database).expanduser()
    if not database_path.is_absolute():
        raise ValueError("database must be an absolute path")

    config = ProjectConfig.load(project_root)
    if evidence_verifier is not None and evidence_config is not None:
        raise ValueError("supply either a host verifier or host evidence config")
    selected_evidence_verifier = evidence_verifier
    if evidence_config is not None:
        host_evidence_path = validate_host_evidence_config_path(
            evidence_config, config.project_root
        )
        selected_evidence_verifier = load_local_evidence_verifier(
            host_evidence_path,
            project_id=config.project_id,
        )
    store = CuratorStore(database_path)
    try:
        caller = AuthenticatedCaller(_local_account_subject(), profile_id=profile_id)
        require_active_project_read(store, config, caller)
        actions = {ProjectAction.READ}
        if allow_write:
            actions.add(ProjectAction.WRITE)
        if allow_review:
            actions.add(ProjectAction.REVIEW)
        if allow_event_retry:
            actions.add(ProjectAction.EVENT_RETRY)
        if allow_retention_hold_release:
            actions.add(ProjectAction.RETENTION_HOLD_RELEASE)
        if allow_purge_retry:
            actions.add(ProjectAction.PURGE_RETRY)
        authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
            store,
            ProjectAuthorizationBinding.from_project_config(
                config, frozenset(actions)
            ),
        )
        if not authorizer.authorize(caller, config.project_id, ProjectAction.READ):
            require_active_project_read(store, config, caller)
            raise ProjectBindingStartupError("project-binding-changed")
        for allowed, action, error_code in (
            (allow_write, ProjectAction.WRITE, "project-write-grant-missing"),
            (allow_review, ProjectAction.REVIEW, "project-review-grant-missing"),
        ):
            if not allowed:
                continue
            require_active_project_action(store, config, caller, action, error_code)
            if not authorizer.authorize(caller, config.project_id, action):
                require_active_project_action(
                    store, config, caller, action, error_code
                )
                raise ProjectBindingStartupError("project-binding-changed")
        for allowed, action, error_code in (
            (
                allow_event_retry,
                ProjectAction.EVENT_RETRY,
                "project-event-retry-grant-missing",
            ),
            (
                allow_retention_hold_release,
                ProjectAction.RETENTION_HOLD_RELEASE,
                "project-retention-hold-grant-missing",
            ),
            (
                allow_purge_retry,
                ProjectAction.PURGE_RETRY,
                "project-purge-retry-grant-missing",
            ),
        ):
            if not allowed:
                continue
            require_active_project_action(store, config, caller, action, error_code)
            if not authorizer.authorize(caller, config.project_id, action):
                require_active_project_action(
                    store, config, caller, action, error_code
                )
                raise ProjectBindingStartupError("project-binding-changed")
        api = AuthenticatedCuratorAPI(
            {
                config.project_id: ProjectPlugin.bind(
                    config,
                    store,
                    evidence_verifier=selected_evidence_verifier,
                    review_authorizer=LocalUIDReviewAuthorizer(),
                )
            },
            authorizer=authorizer,
            limiter=SQLiteTokenBucket(store),
            dependency_readiness=RequestHostReadiness(),
        )
        server = build_mcp_server(
            api,
            caller,
            config.project_id,
            selected_source_id,
            hermes_context=HermesContextOptions(
                profile_id=profile_id,
                require_authenticated_subject=require_authenticated_subject,
            ),
        )
    except BaseException:
        store.close()
        raise
    return LocalProfileMCP(server, store, api, caller, config.project_id)


def _parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="curatormd-v2-mcp",
        description="Run one local, profile-bound Curator V2 stdio server.",
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument(
        "--profile-id",
        required=True,
        help="operator-configured Hermes profile identity; not an auth credential",
    )
    parser.add_argument("--source-id")
    parser.add_argument(
        "--evidence-config",
        type=Path,
        help="owner-only host evidence config; never read from consumer repository",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="allow writes only when this profile has an exact durable write grant",
    )
    parser.add_argument(
        "--allow-review",
        action="store_true",
        help="allow review tools only when this profile has an exact durable review grant",
    )
    parser.add_argument(
        "--allow-event-retry",
        action="store_true",
        help="allow quarantined-event retry only with its exact durable action grant",
    )
    parser.add_argument(
        "--allow-retention-hold-release",
        action="store_true",
        help="allow retention-hold release only with its exact durable action grant",
    )
    parser.add_argument(
        "--allow-purge-retry",
        action="store_true",
        help="allow reviewed cleanup retry only with its exact durable action grant",
    )
    parser.add_argument(
        "--require-authenticated-subject",
        action="store_true",
        help="deny every Hermes MCP call without a host-authenticated human subject",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pinned local MCP server; diagnostics go to stderr only."""

    try:
        set_process_privacy_limits()
    except Exception:  # pylint: disable=broad-exception-caught
        print(
            "Curator V2 MCP startup failed (privacy limits unavailable).",
            file=sys.stderr,
        )
        return 2
    args = parse_safe_arguments(
        _parser(), argv, sys.stderr,
        "Curator V2 MCP startup failed (invalid command arguments).\n",
    )
    if args is None:
        return 2
    try:
        runtime = build_local_profile_mcp(
            project_root=args.project_root,
            database=args.database,
            profile_id=args.profile_id,
            source_id=args.source_id,
            allow_write=args.allow_write,
            allow_review=args.allow_review,
            allow_event_retry=args.allow_event_retry,
            allow_retention_hold_release=args.allow_retention_hold_release,
            allow_purge_retry=args.allow_purge_retry,
            require_authenticated_subject=args.require_authenticated_subject,
            evidence_config=args.evidence_config,
        )
    except ProjectBindingStartupError as exc:
        print(f"CURATOR_STARTUP_ERROR={exc.code}", file=sys.stderr)
        return 2
    except Exception:  # pylint: disable=broad-exception-caught  # Keep startup errors private.
        print(
            "CURATOR_STARTUP_ERROR=runtime",
            file=sys.stderr,
        )
        return 2
    try:
        runtime.server.run()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
