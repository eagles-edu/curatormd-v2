"""Local, profile-bound stdio host for one Curator V2 project.

This entrypoint is intended for a trusted local orchestrator such as one
Hermes profile spawning one MCP subprocess. Its command-line identity is an
operator assertion, not authentication; every tool call must also carry
matching host-injected Hermes profile and session metadata. This is a local
stdio host-context binding, not cryptographic authentication; do not expose
this process remotely or share its launcher configuration across principals.
The profile receives only project read access by default and optional project
write access, each requiring an exact durable grant. Review, purge,
retention-hold, and event-retry actions remain denied.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

from mcp.server import MCPServer

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI, ProjectAction
from .evidence import EvidenceVerifier
from .local_evidence_config import load_local_service_probe_verifier
from .mcp_server import RequestHostReadiness, build_mcp_server
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .project_access import (
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAuthorizationBinding,
)
from .rate_limiter import SQLiteTokenBucket
from .store import CuratorStore


_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


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
        selected_evidence_verifier = load_local_service_probe_verifier(
            host_evidence_path,
            project_id=config.project_id,
        )
    store = CuratorStore(database_path)
    try:
        caller = AuthenticatedCaller(profile_id)
        actions = {ProjectAction.READ}
        if allow_write:
            actions.add(ProjectAction.WRITE)
        if allow_review:
            actions.add(ProjectAction.REVIEW)
        authorizer = FingerprintBoundSQLiteProjectGrantAuthorizer(
            store,
            ProjectAuthorizationBinding.from_project_config(
                config, frozenset(actions)
            ),
        )
        if not authorizer.authorize(caller, config.project_id, ProjectAction.READ):
            raise ValueError(
                "project registration fingerprint or read grant is not active"
            )
        if allow_write and not authorizer.authorize(
            caller, config.project_id, ProjectAction.WRITE
        ):
            raise ValueError("requested project write grant is not active")
        if allow_review and not authorizer.authorize(
            caller, config.project_id, ProjectAction.REVIEW
        ):
            raise ValueError("requested project review grant is not active")
        api = AuthenticatedCuratorAPI(
            {
                config.project_id: ProjectPlugin.bind(
                    config, store, evidence_verifier=selected_evidence_verifier
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
            require_hermes_context=True,
        )
    except BaseException:
        store.close()
        raise
    return LocalProfileMCP(server, store, api, caller, config.project_id)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the pinned local MCP server; diagnostics go to stderr only."""

    args = _parser().parse_args(argv)
    try:
        runtime = build_local_profile_mcp(
            project_root=args.project_root,
            database=args.database,
            profile_id=args.profile_id,
            source_id=args.source_id,
            allow_write=args.allow_write,
            allow_review=args.allow_review,
            evidence_config=args.evidence_config,
        )
    except Exception:  # pylint: disable=broad-exception-caught  # Keep startup errors private.
        print(
            "Curator V2 MCP startup failed (configuration or runtime error).",
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
