"""MCP tool server bound to one trusted caller and configured project."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
import json
import re
from typing import Any, cast

from mcp.server import MCPServer
from mcp.server.context import ServerRequestContext
from mcp.types import CallToolResult, TextContent

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI
from .health_evaluation import REQUIRED_HEALTH_DEPENDENCIES
from .models import DependencyProbeObservation
from .mcp_tool_registration import register_mcp_tools
from .mcp_tool_support import ArtifactInput, safe_tool_handler
from .hermes_context import hermes_subject_grant_id

_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
host_readiness_context: ContextVar[Mapping[str, object]] = ContextVar(
    "curator_v2_host_readiness", default={}
)
hermes_subject_context: ContextVar[str | None] = ContextVar(
    "curator_v2_hermes_subject", default=None
)
__all__ = ["ArtifactInput", "build_mcp_server", "safe_tool_handler"]
SERVER_INSTRUCTIONS = """\
Curator V2 work protocol:
1. At intake, bind the exact user request or configured checklist item to this
   project. Before implementation, call goal_start with a concise problem and
   observable success criteria; use planned status until the work is accepted.
   Do not invent criteria or silently rewrite the source item. Once an existing
   goal is active, call hermes_goal_bind to validate an explicit current-session
   association; Hermes persists the host binding only after this succeeds.
2. At meaningful checkpoints, record deduplicated compact fact bullets with
   fact_record: distinguish research, advice, intent, change, verification,
   open gates, and outcomes. Verification needs evidence; claims, session end,
   and healthy readiness are not proof. Never store raw chats, transcripts,
   large command output, or source artifacts as canonical facts.
3. Reconcile with goal_report. Show verified criteria separately from open
   criteria, facts to date, TODOs, blocker/owner, and next action. Finish only
   when every criterion has passing evidence; otherwise leave the goal open,
   blocked, or deferred with the exact unmet work.
4. Keep SDE disposition, cleanup authorization, canonical persistence, and
   artifact deletion as ordered durable steps. One explicit review action may
   authorize deletion only for its complete exact inventory; expiry eligibility
   never authorizes deletion. Store a distinct cleanup receipt and project it
   before deleting. Keep unapproved or failed cleanup visibly pending; never equate a zero SDE
   count with failed capture or health.
"""




class _HermesRequestCaller(AuthenticatedCaller):  # pylint: disable=too-few-public-methods
    """Bind the captured local account to the authenticated subject per request."""

    __slots__ = ()

    def __getattribute__(self, name: str) -> Any:
        if name == "subject_id":
            subject_id = hermes_subject_context.get()
            if subject_id is not None:
                return subject_id
        return object.__getattribute__(self, name)


@dataclass(frozen=True, slots=True)
class HermesContextOptions:
    """Host-owned identity requirements for one profile-bound local server."""

    profile_id: str
    require_authenticated_subject: bool = False


def _hermes_identity_middleware(options: HermesContextOptions):
    """Require the local Hermes host context on every tool call.

    The profile is pinned by the local launcher and must match the identity
    Hermes injects into request metadata. This is a host-context binding for a
    private stdio process, not cryptographic authentication for remote clients.
    """

    async def enforce_profile(
        ctx: ServerRequestContext[Any, Any], call_next: Any
    ) -> Any:
        if ctx.method != "tools/call":
            return await call_next(ctx)

        metadata = ctx.meta
        profile_id = (
            metadata.get("hermes/profile_id")
            if isinstance(metadata, Mapping)
            else None
        )
        session_id = (
            metadata.get("hermes/session_id")
            if isinstance(metadata, Mapping)
            else None
        )
        valid_session = (
            isinstance(session_id, str)
            and 1 <= len(session_id) <= 256
            and "\n" not in session_id
            and "\r" not in session_id
        )
        if profile_id != options.profile_id or not valid_session:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "schema_version": 1,
                                "code": "unauthenticated",
                                "message": "Trusted Hermes profile context is required.",
                            },
                            sort_keys=True,
                        ),
                    )
                ],
                is_error=True,
            )
        raw_subject = (
            metadata.get("hermes/authenticated_subject")
            if isinstance(metadata, Mapping)
            else None
        )
        if raw_subject is None:
            if options.require_authenticated_subject:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "schema_version": 1,
                                    "code": "unauthenticated",
                                    "message": "An authenticated Hermes subject is required.",
                                },
                                sort_keys=True,
                            ),
                        )
                    ],
                    is_error=True,
                )
            subject_id = None
        else:
            subject_id = hermes_subject_grant_id(raw_subject)
            if subject_id is None:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "schema_version": 1,
                                    "code": "unauthenticated",
                                    "message": "The Hermes authenticated subject is invalid.",
                                },
                                sort_keys=True,
                            ),
                        )
                    ],
                    is_error=True,
                )
        readiness_token = host_readiness_context.set(
            validate_host_readiness(metadata)
        )
        subject_token = hermes_subject_context.set(subject_id)
        try:
            return await call_next(ctx)
        finally:
            hermes_subject_context.reset(subject_token)
            host_readiness_context.reset(readiness_token)

    return enforce_profile


def validate_host_readiness(metadata: object) -> dict[str, object]:
    """Convert only bounded, host-injected dependency observations."""

    if not isinstance(metadata, dict):
        return {}
    metadata_values = cast(dict[object, object], metadata)
    raw_value = metadata_values.get("hermes/readiness")
    if not isinstance(raw_value, dict):
        return {}
    raw = cast(dict[object, object], raw_value)
    if len(raw) > len(REQUIRED_HEALTH_DEPENDENCIES):
        return {}
    observations: dict[str, object] = {}
    for name_value, value_value in raw.items():
        if (
            not isinstance(name_value, str)
            or name_value not in REQUIRED_HEALTH_DEPENDENCIES
            or not isinstance(value_value, dict)
        ):
            continue
        value = cast(dict[object, object], value_value)
        ready = value.get("ready")
        observed_at = value.get("observed_at")
        if ready is not None and not isinstance(ready, bool):
            continue
        if not isinstance(observed_at, str) or not 1 <= len(observed_at) <= 64:
            continue
        observations[name_value] = DependencyProbeObservation(ready, observed_at)
    return observations


class RequestHostReadiness:
    """Request-local view of observations injected by trusted Hermes Core."""

    # pylint: disable=too-few-public-methods

    def readiness(self, project_id: str) -> Mapping[str, object]:
        """Return this request's trusted host probes for its pinned project."""

        del project_id  # this stdio process is pinned to one project at launch
        return host_readiness_context.get()




def build_mcp_server(
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    project_id: str,
    source_id: str,
    *,
    hermes_context: HermesContextOptions | None = None,
) -> MCPServer:
    """Build tools with trusted caller/project captured outside tool arguments.

    The host must authenticate the caller and authorize a configured project
    before calling this factory. MCP clients cannot switch projects or supply
    an identity through any registered tool parameter.
    """

    if not _SOURCE_ID_RE.fullmatch(source_id):
        raise ValueError("source_id must be a bounded opaque producer identifier")
    middleware = [_hermes_identity_middleware(hermes_context)] if hermes_context else None
    server = MCPServer(
        "CuratorMD V2",
        version="0.1.0",
        instructions=SERVER_INSTRUCTIONS,
        middleware=middleware,
    )

    registered_caller: AuthenticatedCaller = (
        _HermesRequestCaller(caller.subject_id, caller.profile_id)
        if hermes_context
        else caller
    )
    register_mcp_tools(server, api, registered_caller, project_id, source_id)
    return server
