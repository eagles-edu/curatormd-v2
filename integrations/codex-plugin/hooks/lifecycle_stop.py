"""Require one Curator lifecycle pass when Codex ends on a task transition."""

from __future__ import annotations

import json
import sys
from typing import cast

from task_state import (
    active_goal_ids,
    has_summary_fact,
    has_summary_ready,
    has_stop_followup,
    has_unconfirmed_defer,
    has_unconfirmed_finish,
    has_unconfirmed_report,
    prompt_cue,
    record_stop_followup,
)
from user_prompt_submit import (
    MAX_INPUT_BYTES,
    _configured_project_root,
    _protect_prompt_process,
    _transition_cue,
)


_ENDPOINT_CUES = {
    "begin task",
    "hold",
    "resume",
    "next plan item",
    "end current task or item",
}


def _continuation_reason(
    cue: str,
    stage: str,
    needs_status_readback: bool,
    needs_defer_readback: bool,
) -> str:
    """Give Codex one bounded continuation for the next missing lifecycle step."""

    if stage == "status":
        if needs_status_readback and needs_defer_readback:
            return "Curator V2 accepted finish/hold requests. Read `goal_status` for both and follow the returned states before ending this turn."
        if needs_status_readback:
            return (
                "Curator V2 accepted a finish request but its result is unconfirmed. "
                "Read `goal_status`; if it reports `complete`, report task completion "
                "and end the development workflow without starting SDE curation."
            )
        return (
            "Curator V2 accepted a hold request but its result is unconfirmed. "
            "Read `goal_status` and confirm `deferred` before ending this turn."
        )
    if stage == "summary":
        return (
            "You reached the task endpoint, but it cannot be finished until its "
            "history has been summarized. Read "
            "every page of this goal's `goal_report`; for a plan, also page the "
            "children and each child's report. Record one concise `change` fact "
            "whose bullet begins `Task summary:` and cites the outcome plus the "
            "supporting goal/fact IDs. Read the report page containing that saved "
            "summary before calling `goal_finish`. After the user's SDE "
            "decision, show the exact temporary-file cleanup inventory and purge "
            "only what the user approves; preserve the summary and audit receipts."
        )
    if stage == "report":
        return (
            "Curator accepted a task write, but its readback is missing. Before "
            "ending this turn, call `goal_status` or `goal_report` for the "
            "same goal and confirm its saved criteria and facts. If this is the "
            "completion summary, confirm the report page contains `Task summary:`."
        )

    action = {
        "begin task": (
            "read goals and create or activate the matching task before work"
        ),
        "hold": "save a checkpoint and defer the matching task",
        "resume": "read the checkpoint and activate the matching task if needed",
        "next plan item": (
            "verify and record the current item, finish it only if its checks pass, "
            "then activate the next item"
        ),
        "end current task or item": (
            "verify and record the matching task endpoint, then finish it only "
            "if its checks pass"
        ),
    }[cue]
    return (
        "Curator V2 transition detected. Before ending this turn, "
        f"{action}. If checks remain open or lack current passing evidence, "
        "keep the goal active and continue development. After `goal_finish` "
        "succeeds and `goal_status` confirms complete, report task completion "
        "and end the development workflow. Historical SDE curation is separate "
        "and only happens when requested for a completed goal; approval still "
        "requires current passing evidence. Use `evidence_capture` for "
        "its returned fields unchanged to `fact_record`. The owner decides "
        "what is recorded as "
        "lasting knowledge, its importance, and its disposition. Do not claim a "
        "Curator write unless its tool succeeds; if a required task check or evidence "
        "is missing, report that clearly and leave the affected check open."
    )


def main() -> int:
    """Inspect only bounded hook input; never read or store the transcript."""

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
        configured = _configured_project_root(event.get("cwd"))
        if configured is None:
            return 0
        _, project_id = configured
        needs_status_readback = has_unconfirmed_finish(event, project_id)
        needs_defer_readback = has_unconfirmed_defer(event, project_id)
        needs_report_readback = has_unconfirmed_report(event, project_id)
        assistant_cue = _transition_cue(event.get("last_assistant_message"))
        saved_cue = prompt_cue(event, project_id)
        cue = (
            assistant_cue
            if assistant_cue in {"hold", "next plan item", "end current task or item"}
            else saved_cue or assistant_cue
        )
        if needs_status_readback or needs_defer_readback:
            stage = "status"
        elif any(
            has_summary_fact(event, project_id, goal_id)
            for goal_id in active_goal_ids(event, project_id)
        ) and needs_report_readback:
            stage = "report"
        elif cue == "end current task or item" and any(
            not has_summary_ready(event, project_id, goal_id)
            for goal_id in active_goal_ids(event, project_id)
        ):
            stage = "summary"
        elif needs_report_readback:
            stage = "report"
        elif cue in _ENDPOINT_CUES:
            stage = "lifecycle"
        else:
            return 0
        if has_stop_followup(event, project_id, stage):
            return 0
        if not record_stop_followup(event, project_id, stage):
            return 0
        if stage == "status":
            # A lifecycle transition has already reached its accepted response;
            # subsequent continuations should ask only for the missing next step.
            record_stop_followup(event, project_id, "lifecycle")
        sys.stdout.write(
            json.dumps(
                {
                    "decision": "block",
                    "reason": _continuation_reason(
                        cue if cue in _ENDPOINT_CUES else "end current task or item",
                        stage,
                        needs_status_readback,
                        needs_defer_readback,
                    ),
                },
                separators=(",", ":"),
            )
        )
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
