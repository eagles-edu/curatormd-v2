"""Remember only successful Curator goal IDs for the current Codex turn."""

from __future__ import annotations

import json
import re
import sys
from typing import cast

from task_state import (
    accepted_event_result,
    accepted_sde_result,
    has_summary_fact,
    record_evidence_capture_state,
    goal_status_result,
    goal_report_matches,
    goal_id_from_input,
    record_fact_state,
    record_summary_fact,
    record_defer_request,
    record_completed_goal,
    record_finish_request,
    record_goal_state,
    record_ootask_goal,
    record_report_pending,
    record_scoped_goal_status,
    record_sde_proposal_state,
    retire_ootask_goal,
    resolve_defer_request,
    resolve_ootask_resume,
    resolve_finish_request,
    resolve_report_pending,
    resolve_sde_candidate_readback,
    resolve_task_summary_readback,
    task_scope_cue,
)
from user_prompt_submit import (
    MAX_INPUT_BYTES,
    _configured_project_root,
    _protect_prompt_process,
)


_TOOL_NAME = re.compile(
    r"^mcp__codex[-_]intake__(goal_start|goal_activate|goal_status|goal_report|goal_finish|goal_defer|fact_record|sde_assess|sde_record_user_report|sde_review_detail|evidence_capture)$"
)


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
        if not isinstance(tool_name, str):
            return 0
        match = _TOOL_NAME.fullmatch(tool_name)
        if match is None:
            return 0
        configured = _configured_project_root(event.get("cwd"))
        if configured is None:
            return 0
        _, project_id = configured
        tool = match.group(1)
        if tool == "sde_review_detail":
            resolve_sde_candidate_readback(event, project_id)
            return 0
        goal_id = goal_id_from_input(event)
        if goal_id is None:
            return 0

        if tool == "evidence_capture":
            record_evidence_capture_state(event, project_id, goal_id)
            return 0

        if tool in {"goal_start", "goal_activate"}:
            if not accepted_event_result(event):
                return 0
            if tool == "goal_start":
                tool_input = event.get("tool_input")
                status = tool_input.get("initial_status") if isinstance(tool_input, dict) else None
                if status != "active":
                    return 0
            record_goal_state(event, project_id, goal_id, True)
            if tool == "goal_start" and task_scope_cue(event, project_id) == "ootask":
                record_ootask_goal(event, project_id, goal_id)
            if tool == "goal_activate":
                resolve_ootask_resume(event, project_id, goal_id)
            record_report_pending(event, project_id, goal_id)
        elif tool == "goal_status":
            status = goal_status_result(event, goal_id)
            if status is not None:
                record_goal_state(
                    event, project_id, goal_id, status in {"active", "open"}
                )
                record_scoped_goal_status(event, project_id, goal_id)
                if status == "complete":
                    record_completed_goal(event, project_id, goal_id)
                    retire_ootask_goal(project_id, goal_id)
                resolve_report_pending(event, project_id, goal_id)
                if status == "complete":
                    resolve_finish_request(event, project_id, goal_id, True)
                else:
                    resolve_finish_request(event, project_id, goal_id, False)
                resolve_defer_request(
                    event, project_id, goal_id, status == "deferred"
                )
        elif tool == "goal_report" and goal_report_matches(event, goal_id):
            summary_read_back = resolve_task_summary_readback(
                event, project_id, goal_id
            )
            if summary_read_back or not has_summary_fact(event, project_id, goal_id):
                resolve_report_pending(event, project_id, goal_id)
        elif tool == "fact_record" and accepted_event_result(event):
            record_fact_state(event, project_id, goal_id)
            record_summary_fact(event, project_id, goal_id)
            record_report_pending(event, project_id, goal_id)
        elif tool == "goal_finish" and accepted_event_result(event):
            record_finish_request(event, project_id, goal_id)
            record_report_pending(event, project_id, goal_id)
        elif tool == "goal_defer" and accepted_event_result(event):
            record_defer_request(event, project_id, goal_id)
            record_report_pending(event, project_id, goal_id)
        elif tool in {"sde_assess", "sde_record_user_report"} and accepted_sde_result(event, goal_id):
            record_sde_proposal_state(
                event,
                project_id,
                goal_id,
                allow_active=tool == "sde_record_user_report",
            )
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
