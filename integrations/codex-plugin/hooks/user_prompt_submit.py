"""Add workspace-scoped Curator intake guidance without retaining the prompt."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import resource
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

from task_state import record_prompt_cue, record_task_scope


CONFIG_NAME = ".curatormd-v2.toml"
MAX_INPUT_BYTES = 64 * 1024
_PR_SET_DUMPABLE = 4
_GOAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_TASK_SCOPE_CUE_PREFIX = re.compile(r"\s*(ootask|aotask|aatask)\b", re.IGNORECASE)
_AOTASK_TARGET_PREFIX = re.compile(
    r"\s*aotask(?:\s+([A-Za-z0-9][A-Za-z0-9._:-]{0,127}))?\s*:",
    re.IGNORECASE,
)

_HOLD_CUES = re.compile(
    r"\b(?:pause|pausing|hold|holding|defer|shelve|park|parking|"
    r"suspend|postpone)\b"
    r"|\b(?:put|set)\b.{0,32}\b(?:aside|on hold)\b"
    r"|\b(?:leave|leaving|park|parking)\b.{0,32}\b(?:for now|here|aside)\b"
    r"|\b(?:come back to|return to|pick up)\b.{0,32}\b(?:later|tomorrow|next time)\b"
    r"|\b(?:leave|keep)\b.{0,32}\b(?:for later|until later|until next time)\b"
    r"|\b(?:stop|stopping)\s+(?:work|working)\b.{0,32}\b(?:for now|on this|here)\b"
    r"|\b(?:put|set|leave|keep)\b.{0,32}\b(?:on ice|on pause|for now)\b"
    r"|\b(?:leave|let)\b.{0,24}\b(?:this|that|it|the task|the item)\b.{0,24}\b(?:there|for now|until later)\b"
    r"|\b(?:skip|stop|drop)\b.{0,24}\b(?:this|that|it|the task|the item)\b.{0,24}\b(?:for now|until later)\b"
    r"|\btable\b.{0,24}\b(?:this|that|it|the task|the item)\b"
    r"|\bhold off\b.{0,32}\b(?:for now|on this|until)\b"
    r"|\b(?:leave|leaving)\b.{0,32}\b(?:open|unfinished|pending)\b"
    r"|\bback burner\b"
    r"|\bnot now\b",
    re.IGNORECASE,
)
_RESUME_CUES = re.compile(
    r"\b(?:resume|resumed|resuming|continue|continued|continuing|pick back up|"
    r"pick this back up|return to|back to|carry on with|carry on|"
    r"get back to|take this back up|pick up again|pick this up again|start again|"
    r"we're back|we are back|back at it)\b",
    re.IGNORECASE,
)
_NEXT_CUES = re.compile(
    r"\bnext\s+(?:(?:\d+|few|several|remaining)\s+)?(?:(?:plan|list|checklist)\s+)?(?:unfinished\s+|open\s+)?items?\b"
    r"|\b(?:next|following)\s+(?:plan\s+)?(?:step|task|checklist item)\b"
    r"|\b(?:move|moving|go|going|advance|advancing)\b.{0,36}\bnext\b"
    r"|\b(?:close|finish|complete|clear)\b.{0,48}\b(?:so|then|and|to)\b.{0,24}\b(?:move|go|work)\b.{0,24}\b(?:ahead|forward|next)\b"
    r"|\b(?:move|moving|go|going)\s+on\b.{0,24}\b(?:now|after this|from here)\b"
    r"|\b(?:move|moving|go|going)\s+on\b"
    r"|\b(?:on to|onto)\s+(?:the\s+)?next\b"
    r"|\bnext up\b"
    r"|\b(?:check|mark)\b.{0,48}\b(?:complete|completed|done|finished)\b.{0,32}\b(?:and )?(?:move|go|advance)\b",
    # Keep common conversational transitions alongside explicit checklist terms.
    re.IGNORECASE,
)
_END_CUES = re.compile(
    r"\b(?:finish|finished|complete|completed|close|closed|done)\b"
    r".{0,48}\b(?:task|item|goal|plugin|work|it|this)\b"
    r"|\b(?:task|item|goal|plugin|work)\b.{0,48}\b(?:is\s+|has\s+been\s+)?"
    r"(?:finished|completed|complete|done)\b"
    r"|\b(?:that|this|it|the\s+(?:task|item))\s+(?:is|was|has\s+been)\s+"
    r"(?:done|complete|completed|finished)\b"
    r"|\b(?:task|item|work)\b.{0,32}\b(?:wrapped up|closed out)\b"
    r"|\b(?:that'?s|it'?s)\s+(?:done|complete|completed|finished)\b"
    r"|\b(?:we'?ve|we have|i'?ve|i have)\s+(?:now\s+)?(?:finished|completed|wrapped up)\b"
    r"|\b(?:finished|completed|wrapped up)\s+(?:with\s+)?(?:this|that|the current)\s+(?:task|item|work)\b"
    r"|\bwrap(?:ping)?\s+up\b"
    r"|\bcall\b.{0,32}\b(?:done|complete|finished)\b"
    r"|\b(?:that's|that is|we're|we are)\s+(?:all\s+)?done\b"
    r"|\b(?:i|we)\s+(?:have\s+|just\s+)?(?:finished|completed|closed out)\b"
    r"|\b(?:this|that|it|the current task|the current item)\s+(?:is|was|has been)\s+(?:complete|completed|finished|closed)\b"
    r"|\b(?:close|finish|complete)\b.{0,32}\b(?:this|that|it|the task|the item|the current item)\b"
    r"|\bclose\s+(?:it|this|that|everything|all)\b"
    r"|\bget\b.{0,24}\b(?:this|that|it|things|everything|the task|the item)\b.{0,24}\b(?:done|closed|finished|completed)\b"
    r"|\b(?:check|mark)\b.{0,48}\b(?:this|that|it|the task|the item)\b.{0,24}\b(?:complete|completed|done|finished|closed)\b"
    r"|\b(?:this|that|it|the task|the item)\b.{0,32}\b(?:is|was|has been)\s+(?:done|complete|completed|finished|closed)\b"
    r"|\b(?:done|finished|completed|complete|closed)\s*[.!]?\s*$"
    r"|\b(?:done|finished|completed|complete|closed)\s+with\s+(?:this|that|it|the task|the item)\b"
    r"|\bcheck(?:ed)?\s+(?:this|that|it|the task|the item)?\s*off\b"
    r"|^\s*(?:done|finished|completed|finish|close)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_BEGIN_CUES = re.compile(
    r"\b(?:start|starts|started|starting|begin|begins|begun|began|beginning|"
    r"work on|fix|implement|build|investigate|debug|review|add|update|change|"
    r"create|remove|rewrite|finish|complete|close|tackle|take on|handle|address|work through|"
    r"get started|pick up|look into|sort out|take care of|get it working)\b"
    r"|\b(?:get|make)\b.{0,24}\b(?:this|that|it|the task|the item)\b.{0,24}\bworking\b"
    r"|\b(?:let'?s|let us|we need to|please|could you|can you)\s+"
    r"(?:now\s+)?(?:start|begin|work on|fix|implement|build|investigate|debug|"
    r"review|add|update|change|create|remove|rewrite|tackle|handle|address|"
    r"get started on|work through)\b",
    re.IGNORECASE,
)
_NEGATED_CUE_SUFFIX = re.compile(
    r"\b(?:do\s+not|does\s+not|did\s+not|has\s+not|have\s+not|had\s+not|"
    r"don't|dont|doesn't|didn't|hasn't|haven't|hadn't|won't|wouldn't|cannot|can't|"
    r"shouldn't|should\s+not|isn't|aren't|not|never|without)\b"
    r"(?:\W+\w+){0,4}\W*$",
    re.IGNORECASE,
)
_STATUS_QUESTION = re.compile(
    r"^\s*(?:is|are|was|were|has|have)\b.{0,256}\?\s*$",
    re.IGNORECASE,
)
_WORKFLOW_DISCUSSION = re.compile(
    r"\b(?:when|if)\s+(?:codex|the\s+plugin|the\s+hook|i|you)\b"
    r".{0,80}\b(?:say|says|said|use|uses|hear|hears|recognize|recognizes|detect|detects)\b"
    r"|\b(?:plugin|curator|hook|assistant|codex)\b.{0,100}\b"
    r"(?:learn|recognize|detect|interpret|support|handle|understand|"
    r"cue|cues|phrase|phrases|wording|vernacular|language|trigger)\b"
    r"|\b(?:learn|recognize|detect|interpret|support|handle|understand)\b"
    r".{0,100}\b(?:cue|cues|phrase|phrases|wording|vernacular|language)\b",
    re.IGNORECASE,
)


def _has_unnegated_cue(pattern: re.Pattern[str], text: str) -> bool:
    """Ignore a cue when its current sentence explicitly negates it."""

    for match in pattern.finditer(text):
        sentence_start = max(
            text.rfind(delimiter, 0, match.start())
            for delimiter in ("\n", ".", "!", "?")
        ) + 1
        if not _NEGATED_CUE_SUFFIX.search(text[sentence_start:match.start()]):
            return True
    return False


def _transition_cue(prompt: object) -> str:
    """Classify lifecycle wording without retaining or returning the prompt."""

    if not isinstance(prompt, str) or not prompt:
        return "ordinary work"
    bounded = prompt[:MAX_INPUT_BYTES].casefold()
    # Talking about how the integration should interpret lifecycle language is
    # not itself a request to hold, finish, or advance the current task.
    if _WORKFLOW_DISCUSSION.search(bounded):
        return "ordinary work or progress"
    if _STATUS_QUESTION.search(bounded):
        return "ordinary work or progress"
    if _has_unnegated_cue(_HOLD_CUES, bounded):
        return "hold"
    if _has_unnegated_cue(_RESUME_CUES, bounded):
        return "resume"
    if _has_unnegated_cue(_NEXT_CUES, bounded):
        return "next plan item"
    # Imperative "finish/complete/close the plugin/task" asks Codex to do work.
    # Treat an endpoint as a transition only when the user marks a state or
    # explicitly checks an item off; otherwise the default task intake handles
    # it as beginning or ongoing work.
    if _has_unnegated_cue(_END_CUES, bounded) and not re.search(
        r"\b(?:finish|complete|close)\s+"
        r"(?:(?:the|this|that|current|remaining)\s+)?"
        r"(?:plugin|implementation|feature|work|task|item|goal)\b",
        bounded,
        re.IGNORECASE,
    ):
        return "end current task or item"
    if _has_unnegated_cue(_BEGIN_CUES, bounded):
        return "begin task"
    return "ordinary work or progress"


def _task_scope_cue(prompt: object) -> str | None:
    """Recognize explicit task-scope prefixes without retaining their text."""

    if not isinstance(prompt, str):
        return None
    match = _TASK_SCOPE_CUE_PREFIX.match(prompt[:MAX_INPUT_BYTES])
    return match.group(1).casefold() if match else None


def _task_scope_goal_id(prompt: object) -> str | None:
    """Return only the explicitly named opaque goal ID for an AOTASK."""

    if not isinstance(prompt, str):
        return None
    match = _AOTASK_TARGET_PREFIX.match(prompt[:MAX_INPUT_BYTES])
    if match is None:
        return None
    goal_id = match.group(1)
    return goal_id if goal_id is not None and _GOAL_ID.fullmatch(goal_id) else None


def _protect_prompt_process() -> bool:
    """Disable core dumps and restrict files before reading prompt input."""

    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if sys.platform.startswith("linux"):
            prctl = ctypes.CDLL(None, use_errno=True).prctl
            prctl.argtypes = [
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
            ]
            prctl.restype = ctypes.c_int
            if prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
                return False
        os.umask(0o077)
    except (AttributeError, OSError, ValueError):
        return False
    return True


def _configured_project_root(cwd: object) -> tuple[Path, str] | None:
    if not isinstance(cwd, str) or not cwd:
        return None
    try:
        current = Path(cwd).resolve(strict=True)
        for candidate in (current, *current.parents):
            config_path = candidate / CONFIG_NAME
            if not config_path.is_file():
                continue
            with config_path.open("rb") as config_file:
                config: Any = tomllib.load(config_file)
            project_id = config.get("project_id")
            if isinstance(project_id, str) and project_id:
                return candidate, project_id
    except (OSError, RuntimeError, ValueError, tomllib.TOMLDecodeError):
        return None
    return None


def _source_event_id(turn_id: object) -> str | None:
    """Return a stable, content-free source reference for one Codex turn."""

    if not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 256:
        return None
    digest = hashlib.sha256(
        b"curator-v2-codex-prompt-turn-v1\0" + turn_id.encode("utf-8")
    ).hexdigest()[:32]
    return f"codex-turn-{digest}"


def _context(
    _project_id: str,
    source_event_id: str | None,
    cue: str = "ordinary work or progress",
    scope_cue: str | None = None,
    scope_goal_id: str | None = None,
) -> str:
    if scope_cue == "aatask":
        return ("SCOPE=AATASK: Handle this aside as work unrelated to the current "
                "repository. Do not create or update a Curator project goal, "
                "facts, lifecycle, or SDE for it. Preserve the current task and "
                "resume it only when the user asks. Do not retain the prompt.")
    transition = {
        "hold": "TURN=HOLD: save checkpoint; read status; call goal_defer.",
        "resume": "TURN=RESUME: page all goals; match saved problem/checks; read goal_status. If already active, do NOT call goal_start or goal_activate: save intent/progress with fact_record, then continue. Activate only a planned/deferred/blocked goal using its current revision. Say `Resuming problem/task: <saved problem/title> [plan item X]. Open checks: <saved checks>.` Append facts to that goal ID.",
        "next plan item": "TURN=NEXT: verify and finish the current task; after complete, prepare its own pending SDE proposal and confirm its goal/status with sde_review_detail; only then activate the next child if the user is continuing.",
        "end current task or item": "TURN=END: record the task result and passing test/lint check (or the owner's confirmation), finish the goal, then create its pending SDE proposal. For an interrupting OOTASK, resume the exact previously paused plan item only if the user says continue.",
        "begin task": "TURN=BEGIN: Problem/Success; read goals and match saved checks. For an already-active match, read goal_status then save intent with fact_record; never goal_start/goal_activate it. Activate a planned/deferred/blocked match with current revision; call goal_start only if no match exists. Plan=parent+child; reuse retry.",
        "ordinary work": "",
        "ordinary work or progress": "",
    }[cue]
    scope = {
        "ootask": "SCOPE=OOTASK: create or resume a distinct one-off with its own criteria, facts, checks, and lifecycle. Reuse only an exact matching goal previously started as an OOTASK; never attach this work to the broader goal itself. If it interrupts an active plan item, first checkpoint and defer that exact item; keep the one-off's facts and pending SDE proposal separate. After Curator confirms the pending candidate's goal ID and status with sde_review_detail, reactivate the previously paused item only when the user says to continue. Use parent_goal_id only when this distinct one-off is explicitly within a broader goal.",
        "aotask": (
            f"SCOPE=AOTASK goal_id={scope_goal_id}: add a sub-item to, or "
            "correct/change, that current goal or plan item; keep its same ID. "
            "Do not create another goal or activate another plan item."
            if scope_goal_id
            else "SCOPE=AOTASK (add-on to current item): add a sub-item under, or "
            "correct/change, the current goal or plan item under the same goal ID. "
            "Use current task context; do not create another goal, switch items, "
            "or ask the owner for an ID. Read and update that same goal only. Do not require "
            "`aotask <goal-id>:`."
        ),
    }.get(scope_cue, "")
    return f"""Curator V2; `goal_start.event_id`={source_event_id or 'unavailable'} (retry).
{transition}
{scope}
Interpret the full request and conversation; cues are hints. Route by workspace scope and active plan. Continue through the active plan's current item; the plan workflow advances through its items. `aotask:` (add-on to current item) adds a sub-item under, or corrects/changes, the current goal or plan item under the same implicit goal ID. Do not create another goal or switch plan items. With no plan match, normal-language work starts or resumes a top-level one-off; `ootask:` forces a distinct one-off. If the request clearly targets another repository, treat it as `aatask` even without the prefix: do not change this project's goals, facts, lifecycle, or SDEs, and preserve unrelated work in progress. Do not interrupt unrelated work unless the request is germane or the owner asks to change scope. Ask only when repository scope is genuinely ambiguous; if AOTASK has no current goal context, ask for the task by problem or title, never ID. Repository or topic similarity alone is not a plan match. “Finish the plugin” means work. Track nontrivial project work before edits; save intent. Before work, page all goals and match saved problem/checks; reuse one clear same-task goal. For new task use `initial_status="active"`; same-task active: read status and record intent, no start/activate. Plans=parent+child; follow each item/one-off; advance only if continuing. Say `Problem: <problem>. Success: <observable checks>.` Retry/resume reuse same goal and wording; separated records for one task stay under the same goal ID across pauses/threads; child IDs link to parent.
At task end, save the observed result and finish without waiting for separate proof or another instruction; moving on after seeing the result can indicate completion. Record available evidence honestly, never invent it, and ask the owner for guidance when unsure. Propose potentially useful facts for owner review, including during active work; do not approve or codify on the owner's behalf. For an interrupting OOTASK, resume the exact previously paused plan item only if the user says continue. Never attach one-off facts to another task. Never retain prompts. Claim writes only after success."""


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
        configured = _configured_project_root(event.get("cwd"))
        if configured is None:
            return 0
        _, project_id = configured
        source_event_id = _source_event_id(event.get("turn_id"))
        cue = _transition_cue(event.get("prompt"))
        record_prompt_cue(event, project_id, cue)
        scope_cue = _task_scope_cue(event.get("prompt"))
        scope_goal_id = _task_scope_goal_id(event.get("prompt"))
        record_task_scope(event, project_id, scope_cue, scope_goal_id)
        response = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": _context(
                    project_id, source_event_id, cue, scope_cue, scope_goal_id
                ),
            }
        }
        sys.stdout.write(json.dumps(response, separators=(",", ":")))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
