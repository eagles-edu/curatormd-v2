"""Project-scoped adapter from Hermes' durable hook outbox to Curator MCP."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from typing import Any, cast

from .project_config import ProjectConfig


_EVENT_CONTEXT_FIELDS = frozenset(
    {"attempt_id", "session_id", "turn_id", "outcome", "failure_kind"}
)
_SUPPORTED_EVENTS = frozenset({"codex:turn:start", "codex:turn:end"})
ToolCall = Callable[..., str | Awaitable[str]]
MCPCall = Callable[..., object]
HermesHook = Callable[
    [str, Mapping[str, Any]], Coroutine[Any, Any, bool | None]
]


def _build_payload(
    event_type: str, hook_context: Mapping[str, Any]
) -> dict[str, Any]:
    """Keep only the bounded event fields understood by Curator V2."""

    context = {
        key: hook_context[key]
        for key in _EVENT_CONTEXT_FIELDS
        if key in hook_context
    }
    if context.get("session_id") != hook_context.get("session_id"):
        raise ValueError("event session binding is inconsistent")
    return {
        "event_type": event_type,
        "goal_id": hook_context["goal_id"],
        "event_id": hook_context["event_id"],
        "source_sequence": hook_context["source_sequence"],
        "occurred_at": hook_context["occurred_at"],
        "context": context,
    }


async def _call_curator(
    payload: Mapping[str, Any],
    *,
    server_name: str,
    timeout_seconds: float,
    call_mcp: MCPCall | None,
    call_tool: ToolCall | None,
) -> object:
    """Call the public Hermes MCP capability or the adapter's test seam."""

    if call_mcp is not None:
        raw_context = payload["context"]
        if not isinstance(raw_context, Mapping):
            raise ValueError("event context must be a mapping")
        context = cast(Mapping[str, Any], raw_context)
        session_id = context.get("session_id")
        if not isinstance(session_id, str):
            raise ValueError("event session ID must be a string")
        response = await asyncio.to_thread(
            call_mcp,
            server_name,
            "hermes_codex_event",
            dict(payload),
            timeout=timeout_seconds,
            session_id=session_id,
            hermes_durable_event=True,
        )
        if not isinstance(response, Mapping):
            raise ValueError("MCP response must be an envelope")
        response_envelope = cast(Mapping[str, Any], response)
        if (
            response_envelope.get("ok") is not True
            or response_envelope.get("truncated") is True
        ):
            raise ValueError("MCP response did not complete")
        return response_envelope.get("result")

    if call_tool is None:
        raise ValueError("a Curator MCP adapter is required")
    raw_event_context = payload["context"]
    if not isinstance(raw_event_context, Mapping):
        raise ValueError("event context must be a mapping")
    event_context = cast(Mapping[str, Any], raw_event_context)
    session_id = event_context.get("session_id")
    if not isinstance(session_id, str):
        raise ValueError("event session ID must be a string")
    raw_response = call_tool(
        dict(payload),
        session_id=session_id,
        hermes_durable_event=True,
    )
    if inspect.isawaitable(raw_response):
        raw_response = await raw_response
    decoded: object = json.loads(raw_response)
    if not isinstance(decoded, dict) or "error" in decoded:
        raise ValueError("Curator response did not complete")
    return cast(dict[str, Any], decoded).get("result")


def _has_durable_receipt(
    result: object, *, project_id: str, event_id: str
) -> bool:
    """Acknowledge only a processed receipt for this exact project event."""

    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict):
        return False
    receipt = cast(dict[str, Any], result).get("receipt", result)
    if not isinstance(receipt, dict):
        return False
    value = cast(dict[str, Any], receipt)
    return (
        value.get("project_id") == project_id
        and value.get("event_id") == event_id
        and value.get("status") in {"processed", "duplicate"}
    )


def build_hermes_hook_handler(
    project_root: str | Path,
    server_name: str,
    *,
    timeout_seconds: float = 30.0,
    call_mcp: MCPCall | None = None,
    call_tool: ToolCall | None = None,
) -> HermesHook:
    """Create a trusted local hook handler bound to one repository's plugin config.

    ``None`` means the event belongs to another configured project hook;
    literal ``True`` acknowledges a durable Curator receipt; ``False`` asks the
    Hermes outbox to retain and retry the event. A Hermes gateway hook passes
    its public ``ctx.call_mcp`` capability. ``call_tool`` is retained only as
    an in-process test seam for the adapter's asynchronous fixtures.
    """
    config = ProjectConfig.load(project_root)
    if not server_name.strip() or len(server_name) > 128:
        raise ValueError("server_name must be a bounded configured MCP name")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("timeout_seconds must be between 0 and 300")

    if call_mcp is not None and call_tool is not None:
        raise ValueError("provide only one MCP call adapter")
    if call_mcp is None and call_tool is None:
        raise ValueError("a Hermes hook context call_mcp capability is required")

    async def handle(event_type: str, hook_context: Mapping[str, Any]) -> bool | None:
        if event_type not in _SUPPORTED_EVENTS:
            return None
        if hook_context.get("project_id") != config.project_id:
            return None
        try:
            payload = _build_payload(event_type, hook_context)
            result = await _call_curator(
                payload,
                server_name=server_name,
                timeout_seconds=timeout_seconds,
                call_mcp=call_mcp,
                call_tool=call_tool,
            )
            return _has_durable_receipt(
                result,
                project_id=config.project_id,
                event_id=str(payload["event_id"]),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # This is the untrusted host/MCP boundary: unknown adapter failures
            # must not expose source details or acknowledge durable delivery.
            return False

    return handle
