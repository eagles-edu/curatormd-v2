"""Require one Curator lifecycle pass when Codex ends on a task transition."""

from __future__ import annotations

import json
import sys
from typing import cast

from task_state import (
    has_stop_followup,
    has_unconfirmed_defer,
    has_unconfirmed_finish,
    has_unassessed_completion,
    has_sde_readback_pending,
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
                "Read `goal_status`; if it reports `complete`, prepare a pending "
                "SDE proposal from supported facts on that goal for owner review."
            )
        return (
            "Curator V2 accepted a hold request but its result is unconfirmed. "
            "Read `goal_status` and confirm `deferred` before ending this turn."
        )
    if stage == "sde":
        return (
            "Curator V2 confirmed this goal complete. Before ending the turn, "
            "use only supported facts from this completed goal to create a "
            "pending `sde_assess` proposal for owner review. Show the supporting "
            "facts and any category or importance suggestion as recommendations; "
            "never approve, reject, or codify it. If the tool rejects the facts, "
            "report the failure and leave the proposal gate open."
        )
    if stage == "sde_readback":
        return (
            "Curator accepted the completed task's pending SDE proposal. Before "
            "continuing, call `sde_review_detail` for the returned candidate ID "
            "and confirm its goal ID and `pending_review` status. Present its "
            "supporting facts and category/importance as recommendations only. "
            "Keep the proposal pending; then resume the exact previously paused "
            "plan item if the user asked to continue."
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
        f"{action}. For a single practical check, use its passing local test/lint "
        "result or explicit owner confirmation as proof; otherwise keep it open. "
        "After `goal_finish` succeeds and `goal_status` confirms complete, create "
        "a pending SDE proposal from supported facts on that goal. Keep it pending "
        "for owner review. After approval, transfer approved facts to the pertinent "
        "persistence document, read it back to verify, then perform only approved "
        "artifact cleanup. Never claim a Curator write unless its tool succeeds."
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
        needs_sde_proposal = has_unassessed_completion(event, project_id)
        needs_sde_readback = has_sde_readback_pending(event, project_id)
        assistant_cue = _transition_cue(event.get("last_assistant_message"))
        saved_cue = prompt_cue(event, project_id)
        cue = (
            assistant_cue
            if assistant_cue in {"hold", "next plan item", "end current task or item"}
            else saved_cue or assistant_cue
        )
        if needs_status_readback or needs_defer_readback:
            stage = "status"
        elif needs_sde_proposal:
            stage = "sde"
        elif needs_sde_readback:
            stage = "sde_readback"
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
