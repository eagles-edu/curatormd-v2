"""Require a Curator-active task before local shell commands or code edits."""

from __future__ import annotations

import json
import sys
from typing import cast

from task_state import (
    has_active_goal,
    has_active_goal_with_fact,
    has_unconfirmed_defer,
    has_unconfirmed_finish,
    has_recorded_fact,
    has_summary_ready,
    goal_id_from_input,
)
from user_prompt_submit import (
    MAX_INPUT_BYTES,
    _configured_project_root,
    _protect_prompt_process,
)


_WORK_TOOLS = {"Bash", "apply_patch", "Edit", "Write"}
_ENDPOINT_TOOLS = {
    "mcp__codex-intake__goal_finish",
    "mcp__codex_intake__goal_finish",
    "mcp__codex-intake__goal_defer",
    "mcp__codex_intake__goal_defer",
}


def main() -> int:
    try:
        if not _protect_prompt_process():
            return 0
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            return 0
        decoded: object = json.loads(raw)
        if not isinstance(decoded, dict):
            return 0
        event = cast(dict[str, object], decoded)
        tool_name = event.get("tool_name")
        if tool_name not in _WORK_TOOLS and tool_name not in _ENDPOINT_TOOLS:
            return 0
        configured = _configured_project_root(event.get("cwd"))
        if configured is None:
            return 0
        _, project_id = configured
        goal_id = goal_id_from_input(event) if tool_name in _ENDPOINT_TOOLS else None
        if tool_name in _WORK_TOOLS and not has_active_goal(event, project_id):
            reason = (
                "Curator V2 needs the matching task confirmed for this turn before local work. "
                "Page the project goals and read goal_status. For an active match, record "
                "intent with fact_record; do not call goal_start or goal_activate. Activate "
                "a planned, deferred, or unblocked task at its current revision. Create a "
                "goal only when no matching task exists, then retry. If Curator tools "
                "are missing from this session, disable the Curator PreToolUse hook "
                "in /hooks and reload after fixing its MCP connection."
            )
        elif tool_name in _WORK_TOOLS and has_active_goal(event, project_id):
            if has_unconfirmed_finish(event, project_id) or has_unconfirmed_defer(
                event, project_id
            ):
                reason = (
                    "Curator V2 needs a goal status readback before more local work. "
                    "Read goal_status and follow the result."
                )
            elif has_active_goal_with_fact(event, project_id):
                return 0
            else:
                reason = (
                    "Curator V2 needs an accepted task fact before local work. "
                    "Record the task intent or current progress, then retry."
                )
        elif (
            tool_name in {"mcp__codex-intake__goal_finish", "mcp__codex_intake__goal_finish"}
            and goal_id is not None
            and has_active_goal(event, project_id)
            and not has_summary_ready(event, project_id, goal_id)
        ):
            reason = (
                "Curator V2 needs the complete task history summarized before finish. "
                "Read every goal report page and linked plan-child report, save a "
                "`change` fact beginning `Task summary:`, read that summary back, "
                "then retry goal_finish."
            )
        elif (
            goal_id is not None
            and has_active_goal(event, project_id)
            and has_recorded_fact(event, project_id, goal_id)
            and not has_unconfirmed_finish(event, project_id)
            and not has_unconfirmed_defer(event, project_id)
        ):
            return 0
        else:
            reason = (
                "Curator V2 needs an accepted checkpoint fact before this task can be "
                "finished or put on hold. Record the result or checkpoint, then retry."
            )
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }, separators=(",", ":")))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
