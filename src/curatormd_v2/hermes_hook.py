"""Project-scoped adapter from Hermes' durable hook outbox to Curator MCP."""

from __future__ import annotations

import inspect
import importlib
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
HermesHook = Callable[
    [str, Mapping[str, Any]], Coroutine[Any, Any, bool | None]
]


def build_hermes_hook_handler(
    project_root: str | Path,
    server_name: str,
    *,
    timeout_seconds: float = 30.0,
    call_tool: ToolCall | None = None,
) -> HermesHook:
    """Create a trusted local hook handler bound to one repository's plugin config.

    ``None`` means the event belongs to another configured project hook;
    literal ``True`` acknowledges a durable Curator receipt; ``False`` asks the
    Hermes outbox to retain and retry the event. The normal implementation
    calls the already-connected, operator-configured local MCP server.
    """
    config = ProjectConfig.load(project_root)
    if not server_name.strip() or len(server_name) > 128:
        raise ValueError("server_name must be a bounded configured MCP name")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("timeout_seconds must be between 0 and 300")

    tool_call = call_tool
    if tool_call is None:
        # This adapter is imported by Hermes' in-process gateway hook loader.
        # Keep the Hermes dependency lazy so Curator's backend remains usable
        # from ordinary CLI/MCP deployments.
        handlers = importlib.import_module("tools.mcp_tool_handlers")
        make_tool_handler = cast(
            Callable[[str, str, float], Callable[..., str]],
            getattr(handlers, "_make_tool_handler"),
        )
        tool_call = make_tool_handler(server_name, "hermes_codex_event", timeout_seconds)

    async def handle(event_type: str, hook_context: Mapping[str, Any]) -> bool | None:
        if event_type not in _SUPPORTED_EVENTS:
            return None
        if hook_context.get("project_id") != config.project_id:
            return None
        try:
            context = {
                key: hook_context[key]
                for key in _EVENT_CONTEXT_FIELDS
                if key in hook_context
            }
            payload = {
                "event_type": event_type,
                "goal_id": hook_context["goal_id"],
                "event_id": hook_context["event_id"],
                "source_sequence": hook_context["source_sequence"],
                "occurred_at": hook_context["occurred_at"],
                "context": context,
            }
            if context.get("session_id") != hook_context.get("session_id"):
                return False
            raw_response = tool_call(
                payload,
                session_id=context["session_id"],
                hermes_durable_event=True,
            )
            if inspect.isawaitable(raw_response):
                response = await raw_response
            else:
                response = raw_response
            decoded: object = json.loads(response)
            if not isinstance(decoded, dict) or "error" in decoded:
                return False
            envelope = cast(dict[str, Any], decoded)
            result: object = envelope.get("result")
            if isinstance(result, str):
                result = json.loads(result)
            if not isinstance(result, dict):
                return False
            receipt: object = cast(dict[str, Any], result).get("receipt", result)
            if not isinstance(receipt, dict):
                return False
            receipt_payload = cast(dict[str, Any], receipt)
            return receipt_payload.get("status") in {
                "processed",
                "duplicate",
            }
        except Exception:
            # Hook exceptions must not expose source details or cause an ack.
            return False

    return handle
