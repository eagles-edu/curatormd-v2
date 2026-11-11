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
1. Intake happens from the user's normal Codex request; do not ask the user to
   launch a VS Code palette command. By default, treat a direct request to do
   work as one task. If the user asks for a plan, create one parent goal and
   bounded child tasks for its steps. First reply briefly with the problem and
   observable success checks you will save; keep the user's scope and limits as
   guardrails. Do not invent checks or silently rewrite the request. State
   them briefly to the user, then save before implementation; do not add a
   confirmation round when the request already authorizes the work. First read
   the project's goals and reuse only an exact problem-and-criteria match for
   the same task; repository or topic similarity alone is not a match.
   Otherwise start a distinct goal. If a new bounded task clearly belongs
   within an active broader goal, link it with `parent_goal_id` while keeping its checks, facts,
   and lifecycle on the child. If unrelated to the active item, create a
   top-level one-off. Never append a distinct task's facts to its parent merely
   because both touch the same repository. Use active status when the user asks
   you to do the work and planned status only when they ask for a plan. Owner
   UX approval is not a prerequisite for coding, local checks, or closing
   passed engineering criteria. Ask about material product or scope decisions;
   resolve routine reversible engineering choices and continue independent
   work. Track UX review separately after the behavior is usable and repeatable.
   Respect `ootask:` as a distinct one-off with its own
   lifecycle; set its parent only when it is a bounded task within that scope.
   `aotask:` (add-on to current item) adds a sub-item under, or corrects or
   changes, the current goal/plan item under the same ID and lifecycle. Do not
   ask the owner for a goal ID or switch to another item.
   For a plan, keep its parent and child tasks planned until execution is
   requested. Once a goal is active, call hermes_goal_bind to
   validate the current-session association; Hermes persists the host binding
   only after this succeeds. If goal creation or binding fails, say so plainly
   and do not claim the task is tracked or bound.
2. Record compact facts at task start, after changes/checks, and at the
   outcome. Use one practical success check per task unless it has independent
   outcomes. A passing relevant test/lint check or the owner's explicit
   confirmation is task evidence only when recorded as current verification
   evidence. Never store raw chats,
   transcripts, large command output, or source artifacts as canonical facts.
3. Treat the user's ordinary words as lifecycle controls for both plan children
   and one-off tasks. On hold/pause, record facts, reason, and next action and
   call goal_defer. On resume/continue, read the checkpoint and call
   goal_activate. On next/check-off/done, record the endpoint facts, reconcile
   record current verification facts for every success criterion using
   evidence returned by evidence_capture and passed unchanged to fact_record,
   then call goal_finish. Its completion_claim is an outcome note only; no
   claim prefix satisfies a criterion. If current evidence is unavailable,
   leave the goal open and report the gap and next action. For a plan, activate the next child only after the
   current child finishes. Read goal_status before each lifecycle call and pass
   its current lifecycle revision. Show verified checks separately from open checks,
   TODOs, blocker/owner, and next action. Never claim a task was closed when
   goal_finish leaves it open.
   At each completed child or one-off task, prepare a pending proposal from
   that task's supported facts, with a concise summary, category, and importance
   recommendation. A passing relevant local test/lint result or explicit owner
   confirmation is the task proof; the owner decides the SDE disposition. Show
   the proposal and supporting facts for review. After approval, transfer only
   approved facts to the pertinent persistence document, read it back to verify
   the saved content, then automatically clear eligible candidate-scoped
   transient artifacts after an internal comparison confirms that the saved
   entry contains the same artifact-inventory and dependency-map fingerprints
   as the rechecked transient set. The SDE decision is the single owner
   approval; do not ask for separate deletion approval. Build and recheck the
   complete exact inventory internally, verify its receipt, and leave held, changed,
   incomplete, out-of-scope, or failed artifacts pending.
   Use evidence_capture for configured host sources and pass its returned
   evidence fields unchanged to fact_record; it cannot accept arbitrary
   commands or paths.
4. Keep SDE disposition, canonical persistence, readback, and artifact deletion
   as ordered durable steps. The explicit SDE approval authorizes automatic
   deletion only after successful canonical readback confirms the approved
   entry's artifact-inventory and dependency-map fingerprints match the
   complete, rechecked candidate-scoped transient inventory; expiry eligibility never
   authorizes deletion. Store a distinct cleanup receipt and project it before
   deleting. Keep held, changed, incomplete, out-of-scope, or failed cleanup
   visibly pending; never equate a zero SDE count with failed capture or health.
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
    hermes_binding_enabled: bool | None = None,
    instructions: str = SERVER_INSTRUCTIONS,
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
        instructions=instructions,
        middleware=middleware,
    )

    registered_caller: AuthenticatedCaller = (
        _HermesRequestCaller(caller.subject_id, caller.profile_id)
        if hermes_context
        else caller
    )
    register_mcp_tools(
        server, api, registered_caller, project_id, source_id,
        hermes_binding_enabled=(hermes_context is not None if hermes_binding_enabled is None
                                else hermes_binding_enabled),
    )
    return server
