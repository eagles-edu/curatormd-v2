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

from task_state import record_prompt_cue


CONFIG_NAME = ".curatormd-v2.toml"
MAX_INPUT_BYTES = 64 * 1024
_PR_SET_DUMPABLE = 4

_HOLD_CUES = re.compile(
    r"\b(?:pause|paused|pausing|hold|holding|held|defer|deferred|shelve|shelved|park|parking|"
    r"suspend|suspended|postpone|postponed)\b"
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
) -> str:
    transition = {
        "hold": "TURN=HOLD: save checkpoint; read status; call goal_defer.",
        "resume": "TURN=RESUME: page all goals; match saved problem/checks; read goal_status. If already active, do NOT call goal_start or goal_activate: save intent/progress with fact_record, then continue. Activate only a planned/deferred/blocked goal using its current revision. Say `Resuming problem/task: <saved problem/title> [plan item X]. Open checks: <saved checks>.` Append facts to that goal ID.",
        "next plan item": "TURN=NEXT: verify/finish; activate next child only if continuing.",
        "end current task or item": "TURN=END: summarize all goal/child pages before finish; then SDE and approved cleanup. One-off ends here.",
        "begin task": "TURN=BEGIN: Problem/Success; read goals and match saved checks. For an already-active match, read goal_status then save intent with fact_record; never goal_start/goal_activate it. Activate a planned/deferred/blocked match with current revision; call goal_start only if no match exists. Plan=parent+child; reuse retry.",
        "ordinary work": "",
        "ordinary work or progress": "",
    }[cue]
    return f"""Curator V2; `goal_start.event_id`={source_event_id or 'unavailable'} (retry).
{transition}
Interpret full request; cues are hints. “Finish the plugin” means work. Before creating a goal, page through all goals and match saved problem plus checks; reuse one clear match, ask if ambiguous, create only if none. For immediate work, create a new goal with `initial_status="active"`. For an already-active match, read `goal_status`, record intent with `fact_record`, and continue; never call `goal_start` or `goal_activate` for it. Activate a planned/deferred/blocked match with its current revision. Do not attach unrelated work to the latest goal. Track nontrivial work before edits; save intent. Plans=parent+child; follow each item/one-off; advance only if continuing. Say `Problem: <problem>. Success: <observable checks>.` Retry/resume reuse same goal and wording; separated records for one task stay under the same goal ID across pauses/threads; child IDs link to parent.
At a completed endpoint, say “Item complete; preparing its SDE proposal for your review”. Before `goal_finish`, read status; aggregate every page for the goal and linked children, save one `Task summary:` fact, and read it back. Finish only with passing checks. At every endpoint propose supported facts, verified or not. The user decides disposition; approval needs current passing evidence. Then show exact cleanup inventory; delete only approved temporary artifacts, and keep the summary and audit receipts. Fact compaction needs its own exact approval. Never approve/reject/codify.
Current revisions; compact facts, no prompts. Use exact `evidence_capture` references; never invent. Without capture, record `open_gate`/`research`. Claim writes only after success."""


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
        response = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": _context(project_id, source_event_id, cue),
            }
        }
        sys.stdout.write(json.dumps(response, separators=(",", ":")))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
