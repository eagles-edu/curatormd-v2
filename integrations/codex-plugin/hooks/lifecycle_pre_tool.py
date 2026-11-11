"""Require a Curator-active task before local shell commands or code edits."""

from __future__ import annotations

import json
import sys
from typing import cast

from task_state import (
    has_active_goal,
    has_active_goal_id,
    has_captured_verification_evidence,
    has_active_goal_with_fact,
    has_completed_goal,
    has_sde_readback_pending,
    has_unassessed_completion,
    has_unconfirmed_defer,
    has_unconfirmed_finish,
    has_recorded_fact,
    has_scoped_goal_status,
    goal_id_from_input,
    ootask_resume_state,
    prompt_cue,
    task_scope_cue,
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
_GOAL_START_TOOLS = {
    "mcp__codex-intake__goal_start",
    "mcp__codex_intake__goal_start",
}
_GOAL_ACTIVATE_TOOLS = {
    "mcp__codex-intake__goal_activate",
    "mcp__codex_intake__goal_activate",
}
_FACT_RECORD_TOOLS = {
    "mcp__codex-intake__fact_record",
    "mcp__codex_intake__fact_record",
}
_ASIDE_WRITE_TOOLS = {
    f"mcp__{server}__{tool}"
    for server in ("codex-intake", "codex_intake")
    for tool in ("sde_assess", "sde_record_user_report")
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
        if (
            tool_name not in _WORK_TOOLS
            and tool_name not in _ENDPOINT_TOOLS
            and tool_name not in _GOAL_START_TOOLS
            and tool_name not in _GOAL_ACTIVATE_TOOLS
            and tool_name not in _FACT_RECORD_TOOLS
            and tool_name not in _ASIDE_WRITE_TOOLS
        ):
            return 0
        configured = _configured_project_root(event.get("cwd"))
        if configured is None:
            return 0
        _, project_id = configured
        if task_scope_cue(event, project_id) == "aatask":
            if tool_name in _WORK_TOOLS:
                return 0
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "An aatask is unrelated to this project and does not change its Curator task records.",
                }
            }, separators=(",", ":")))
            return 0
        if tool_name in _ASIDE_WRITE_TOOLS:
            return 0
        if tool_name in _GOAL_ACTIVATE_TOOLS:
            activating_goal_id = goal_id_from_input(event)
            paused_goal_ids, ootask_sde_read_back = ootask_resume_state(
                event, project_id
            )
            if has_unassessed_completion(event, project_id):
                reason = (
                    "Curator V2 requires the completed task's pending SDE proposal "
                    "before activating the next plan child. Use supported facts from "
                    "that completed goal only; keep the proposal separate from the "
                    "next child and leave disposition to the owner."
                )
            elif has_sde_readback_pending(event, project_id):
                reason = (
                    "Curator V2 requires confirmation that the completed task's "
                    "pending SDE candidate is attached to its goal before activating "
                    "another plan item. Call `sde_review_detail` for the returned "
                    "candidate ID; then resume "
                    "the exact previously paused item if the user is continuing."
                )
            elif paused_goal_ids:
                if not ootask_sde_read_back:
                    reason = (
                        "This OOTASK interrupted a plan item. First prepare its "
                        "pending SDE proposal from the one-off's supported facts, "
                        "then read back that exact pending candidate."
                    )
                elif prompt_cue(event, project_id) not in {
                    "resume", "next plan item",
                }:
                    reason = (
                        "The one-off and its pending SDE are complete. Wait for the "
                        "user to say continue before resuming the paused plan item."
                    )
                elif goal_id_from_input(event) not in paused_goal_ids:
                    reason = (
                        "This OOTASK interrupted a plan item. Resume the exact item "
                        "that was deferred before the one-off; do not activate a later "
                        "or unrelated child."
                    )
                else:
                    return 0
            else:
                scope = task_scope_cue(event, project_id)
                if scope == "aotask":
                    reason = (
                        "AOTASK adds a sub-item to, or corrects/changes, the current "
                        "goal or plan item. Do not activate another goal or item."
                    )
                elif scope is not None and (
                    activating_goal_id is None
                    or not has_scoped_goal_status(
                        event, project_id, activating_goal_id
                    )
                ):
                    reason = (
                        "Read `goal_status` for the matching task first. The status "
                        "must confirm the requested one-off or current AOTASK goal "
                        "before activation."
                    )
                else:
                    return 0
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, separators=(",", ":")))
            return 0
        if tool_name in _GOAL_START_TOOLS:
            scope = task_scope_cue(event, project_id)
            if scope != "aotask":
                return 0
            reason = (
                "AOTASK adds a sub-item to, or corrects/changes, the current parent "
                "or child goal. Reuse its ID; do not create another goal."
            )
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, separators=(",", ":")))
            return 0
        if tool_name in _FACT_RECORD_TOOLS:
            fact_goal_id = goal_id_from_input(event)
            if fact_goal_id is None:
                return 0
            if has_completed_goal(event, project_id, fact_goal_id):
                reason = (
                    "Curator V2 confirmed this goal complete. Do not append facts to a "
                    "terminal goal; use its supported facts for the pending SDE review "
                    "or start/continue a matching active task."
                )
            elif not has_active_goal_id(event, project_id, fact_goal_id):
                reason = (
                    "Read `goal_status` and confirm this exact goal is active before "
                    "recording a fact; terminal and unresolved goals cannot accept "
                    "new task facts."
                )
            elif not has_captured_verification_evidence(
                event, project_id, fact_goal_id
            ):
                reason = (
                    "A verification fact must use a passing reference returned by "
                    "`evidence_capture` for this exact goal and criterion. Pass the "
                    "captured fields unchanged; if no configured source is available, "
                    "record the check as a change fact instead of inventing evidence."
                )
            else:
                return 0
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, separators=(",", ":")))
            return 0
        goal_id = goal_id_from_input(event) if tool_name in _ENDPOINT_TOOLS else None
        if (
            tool_name in _ENDPOINT_TOOLS
            and task_scope_cue(event, project_id) is not None
            and (
                goal_id is None
                or not has_scoped_goal_status(event, project_id, goal_id)
            )
        ):
            reason = (
                "This scoped task can write lifecycle changes only to the goal "
                "whose status readback matches its OOTASK or current AOTASK goal."
            )
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }, separators=(",", ":")))
            return 0
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
            elif task_scope_cue(event, project_id) is not None:
                scope = task_scope_cue(event, project_id)
                relation = "top-level with no parent" if scope == "ootask" else "a child of the specified parent or child"
                reason = (
                    f"The `{scope}` task scope is not confirmed for an active goal. "
                    f"Read goal_status and select a task that is {relation}; then "
                    "record its intent and read it back before local work."
                )
            else:
                reason = (
                    "Curator V2 needs an accepted task fact before local work. "
                    "Record the task intent or current progress, then retry."
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
