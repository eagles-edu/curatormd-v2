"""MCP tool server bound to one trusted caller and configured project."""

from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any

from mcp.server import MCPServer
from mcp.server.context import ServerRequestContext
from mcp.types import CallToolResult, TextContent

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI
from .mcp_tool_registration import register_mcp_tools
from .mcp_tool_support import ArtifactInput, safe_tool_handler

_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
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




def _hermes_identity_middleware(expected_profile_id: str):
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
        if profile_id != expected_profile_id or not valid_session:
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
        return await call_next(ctx)

    return enforce_profile




def build_mcp_server(
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    project_id: str,
    source_id: str,
    *,
    require_hermes_context: bool = False,
) -> MCPServer:
    """Build tools with trusted caller/project captured outside tool arguments.

    The host must authenticate the caller and authorize a configured project
    before calling this factory. MCP clients cannot switch projects or supply
    an identity through any registered tool parameter.
    """

    if not _SOURCE_ID_RE.fullmatch(source_id):
        raise ValueError("source_id must be a bounded opaque producer identifier")
    middleware = (
        [_hermes_identity_middleware(caller.subject_id)]
        if require_hermes_context
        else None
    )
    server = MCPServer(
        "CuratorMD V2",
        version="0.1.0",
        instructions=SERVER_INSTRUCTIONS,
        middleware=middleware,
    )

    register_mcp_tools(server, api, caller, project_id, source_id)
    return server
