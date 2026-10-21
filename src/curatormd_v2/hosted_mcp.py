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
from .mcp_server import build_mcp_server
from .project_config import ProjectConfig
from .project_plugin import ProjectPlugin
from .project_access import FingerprintBoundSQLiteProjectGrantAuthorizer
from .rate_limiter import SQLiteTokenBucket
from .store import CuratorStore


_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


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


def build_local_profile_mcp(
    *,
    project_root: str | Path,
    database: str | Path,
    profile_id: str,
    source_id: str | None = None,
    allow_write: bool = False,
    allow_review: bool = False,
) -> LocalProfileMCP:
    """Bind one local profile to the project declared by its repo config.

    The profile ID and requested action ceiling must come from
    operator-controlled launcher configuration. Durable project registration
    and exact action grants must already exist; this project plugin never
    self-registers or grants access. No tool argument can choose a caller or
    project. The repository-owned config is validated by ``ProjectConfig.load``
    before any plugin is bound.
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
            project_id=config.project_id,
            repository_fingerprint=config.repository_fingerprint,
            config_sha256=config.config_sha256,
            backend_api_version=config.backend_api_version,
            allowed_actions=frozenset(actions),
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
            {config.project_id: ProjectPlugin.bind(config, store)},
            authorizer=authorizer,
            limiter=SQLiteTokenBucket(store),
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
