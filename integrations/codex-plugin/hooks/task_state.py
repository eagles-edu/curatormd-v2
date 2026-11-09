"""Keep a private, turn-scoped marker that Curator accepted an active goal."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, cast


_GOAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_STATE_BYTES = 4096
_MAX_TOOL_RESPONSE_BYTES = 64 * 1024
_PROMPT_CUES = frozenset({
    "begin task",
    "hold",
    "resume",
    "next plan item",
    "end current task or item",
})
_TASK_SCOPE_CUES = frozenset({"ootask", "aotask"})


def _state_directory() -> Path | None:
    value = os.environ.get("PLUGIN_DATA")
    if not value:
        return None
    root = Path(value)
    if not root.is_absolute():
        return None
    try:
        directory = root / "task-state"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            return None
        return directory
    except (OSError, RuntimeError):
        return None


def _state_path(event: dict[str, object]) -> Path | None:
    session_id = event.get("session_id")
    turn_id = event.get("turn_id")
    if (
        not isinstance(session_id, str)
        or not 1 <= len(session_id) <= 256
        or not isinstance(turn_id, str)
        or not 1 <= len(turn_id) <= 256
    ):
        return None
    directory = _state_directory()
    if directory is None:
        return None
    digest = hashlib.sha256(
        b"curator-v2-task-state-v1\0"
        + session_id.encode("utf-8")
        + b"\0"
        + turn_id.encode("utf-8")
    ).hexdigest()
    return directory / f"turn-{digest}.json"


def _ootask_handoff_path(
    event: dict[str, object], project_id: str
) -> Path | None:
    """Return session-scoped state for an OOTASK-to-plan-item handoff."""

    session_id = event.get("session_id")
    if (
        not isinstance(session_id, str)
        or not 1 <= len(session_id) <= 256
        or not _GOAL_ID.fullmatch(project_id)
    ):
        return None
    directory = _state_directory()
    if directory is None:
        return None
    digest = hashlib.sha256(
        b"curator-v2-ootask-handoff-v1\0"
        + project_id.encode("utf-8")
        + b"\0"
        + session_id.encode("utf-8")
    ).hexdigest()
    return directory / f"handoff-{digest}.json"


def _ootask_registry_path(
    project_id: str,
) -> Path | None:
    """Return private project state for unfinished OOTASK goal IDs."""

    if not _GOAL_ID.fullmatch(project_id):
        return None
    directory = _state_directory()
    if directory is None:
        return None
    digest = hashlib.sha256(
        b"curator-v2-ootask-registry-v1\0" + project_id.encode("utf-8")
    ).hexdigest()
    return directory / f"ootasks-{digest}.json"


def _load(path: Path, project_id: str) -> dict[str, set[str]]:
    empty = {
        "active_goal_ids": set(),
        "fact_recorded_goal_ids": set(),
        "finish_requested_goal_ids": set(),
        "defer_requested_goal_ids": set(),
        "report_pending_goal_ids": set(),
        "summary_fact_goal_ids": set(),
        "summary_invalidated_goal_ids": set(),
        "summary_ready_goal_ids": set(),
        "prompt_cues": set(),
        "task_scope_cues": set(),
        "task_scope_target_goal_ids": set(),
        "scope_valid_goal_ids": set(),
        "ootask_paused_goal_ids": set(),
        "ootask_goal_ids": set(),
        "ootask_sde_candidate_pairs": set(),
        "ootask_sde_reviewed_candidate_pairs": set(),
        "completed_goal_ids": set(),
        "captured_evidence_fingerprints": set(),
        "sde_proposal_goal_ids": set(),
        "sde_candidate_pairs": set(),
        "sde_reviewed_candidate_pairs": set(),
        "stop_prompted_stages": set(),
    }
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_size > _MAX_STATE_BYTES
        ):
            return empty
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return empty
    if not isinstance(decoded, dict) or decoded.get("project_id") != project_id:
        return empty
    state: dict[str, set[str]] = {}
    for name in empty:
        values = decoded.get(name, [])
        if not isinstance(values, list) or len(values) > 32:
            return empty
        allowed = (
            _PROMPT_CUES if name == "prompt_cues"
            else _TASK_SCOPE_CUES if name == "task_scope_cues"
            else None
        )
        state[name] = {
            value for value in values
            if isinstance(value, str)
            and (
                value in allowed if allowed is not None
                else bool(_SHA256.fullmatch(value))
                if name == "captured_evidence_fingerprints"
                else _valid_sde_candidate_pair(value)
                if name in {
                    "sde_candidate_pairs",
                    "sde_reviewed_candidate_pairs",
                    "ootask_sde_candidate_pairs",
                    "ootask_sde_reviewed_candidate_pairs",
                }
                else bool(_GOAL_ID.fullmatch(value))
            )
        }
    return state


def _valid_sde_candidate_pair(value: str) -> bool:
    goal_id, separator, candidate_id = value.partition("|")
    return bool(
        separator
        and _GOAL_ID.fullmatch(goal_id)
        and _GOAL_ID.fullmatch(candidate_id)
    )


def _write(path: Path, project_id: str, state: dict[str, set[str]]) -> bool:
    if any(len(values) > 32 for values in state.values()):
        return False
    payload = json.dumps(
        {
            "project_id": project_id,
            **{name: sorted(values) for name, values in state.items()},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > _MAX_STATE_BYTES:
        return False
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".task-state-", dir=path.parent, delete=False
        ) as handle:
            temporary = handle.name
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def has_active_goal(event: dict[str, object], project_id: str) -> bool:
    """Check whether this Codex turn has a server-confirmed active goal."""

    path = _state_path(event)
    return bool(path and _load(path, project_id)["active_goal_ids"])


def has_active_goal_id(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Check that this exact goal was confirmed active during this turn."""

    path = _state_path(event)
    return bool(path and goal_id in _load(path, project_id)["active_goal_ids"])


def active_goal_ids(event: dict[str, object], project_id: str) -> list[str]:
    """Return opaque IDs of goals confirmed active in this Codex turn."""

    path = _state_path(event)
    return sorted(_load(path, project_id)["active_goal_ids"]) if path else []


def has_active_goal_with_fact(event: dict[str, object], project_id: str) -> bool:
    """Require a server-confirmed active goal with an accepted fact this turn."""

    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    matching = state["active_goal_ids"] & state["fact_recorded_goal_ids"]
    if state["task_scope_cues"]:
        matching &= state["scope_valid_goal_ids"]
    return bool(matching)


def task_scope_cue(event: dict[str, object], project_id: str) -> str | None:
    """Return only the normalized, owner-supplied task-scope prefix."""

    path = _state_path(event)
    if path is None:
        return None
    cues = _load(path, project_id)["task_scope_cues"]
    return next(iter(cues), None)


def ootask_paused_goal_ids(event: dict[str, object], project_id: str) -> set[str]:
    """Return deferred plan goals from an OOTASK across this session's turns."""

    path = _ootask_handoff_path(event, project_id)
    return _load(path, project_id)["ootask_paused_goal_ids"] if path else set()


def record_ootask_goal(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Remember the active one-off goal using only its opaque Curator ID."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    registry_path = _ootask_registry_path(project_id)
    if registry_path is None:
        return False
    registry = _load(registry_path, project_id)
    registry["ootask_goal_ids"].add(goal_id)
    if not _write(registry_path, project_id, registry):
        return False
    path = _ootask_handoff_path(event, project_id)
    if path is None:
        return False
    state = _load(path, project_id)
    if not state["ootask_paused_goal_ids"]:
        return True
    state["ootask_goal_ids"].add(goal_id)
    return _write(path, project_id, state)


def ootask_goal_registered(
    project_id: str, goal_id: str
) -> bool:
    """Check that an OOTASK goal ID came from an accepted OOTASK start."""

    path = _ootask_registry_path(project_id)
    return bool(
        path and goal_id in _load(path, project_id)["ootask_goal_ids"]
    )


def retire_ootask_goal(
    project_id: str, goal_id: str
) -> bool:
    """Forget a completed one-off ID after its terminal status is confirmed."""

    path = _ootask_registry_path(project_id)
    if path is None:
        return False
    state = _load(path, project_id)
    if goal_id not in state["ootask_goal_ids"]:
        return True
    state["ootask_goal_ids"].discard(goal_id)
    return _write(path, project_id, state)


def record_task_scope(
    event: dict[str, object],
    project_id: str,
    cue: str | None,
    target_goal_id: str | None = None,
) -> bool:
    """Persist the scope category and optional opaque AOTASK target ID."""

    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["task_scope_cues"] = {cue} if cue in _TASK_SCOPE_CUES else set()
    state["task_scope_target_goal_ids"] = (
        {target_goal_id}
        if cue == "aotask" and isinstance(target_goal_id, str)
        and _GOAL_ID.fullmatch(target_goal_id)
        else set()
    )
    state["scope_valid_goal_ids"].clear()
    return _write(path, project_id, state)


def task_scope_target_goal_id(
    event: dict[str, object], project_id: str
) -> str | None:
    """Return the bounded opaque target ID named by an AOTASK prefix."""

    path = _state_path(event)
    if path is None:
        return None
    targets = _load(path, project_id)["task_scope_target_goal_ids"]
    return next(iter(targets), None)


def has_scoped_goal_status(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Check that status readback matched this task's requested scope."""

    path = _state_path(event)
    return bool(
        path and goal_id in _load(path, project_id)["scope_valid_goal_ids"]
    )


def record_scoped_goal_status(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Trust an active goal for this task only when its requested relation fits."""

    path = _state_path(event)
    result = _response_object(event)
    goal = result.get("goal") if result else None
    if path is None or not isinstance(goal, dict) or goal.get("goal_id") != goal_id:
        return False
    state = _load(path, project_id)
    status = goal.get("status")
    scope = next(iter(state["task_scope_cues"]), None)
    if scope == "aotask":
        target = next(iter(state["task_scope_target_goal_ids"]), None)
        relation_matches = target is not None and target == goal_id
    elif scope == "ootask":
        relation_matches = ootask_goal_registered(project_id, goal_id)
    else:
        relation_matches = True
    if status not in {"active", "open", "planned", "deferred", "blocked"} or not relation_matches:
        state["scope_valid_goal_ids"].discard(goal_id)
        return _write(path, project_id, state)
    state["scope_valid_goal_ids"].add(goal_id)
    return _write(path, project_id, state)


def has_recorded_fact(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Check whether this turn saved an accepted task fact for the goal."""

    path = _state_path(event)
    return bool(
        path
        and goal_id in _load(path, project_id)["fact_recorded_goal_ids"]
    )


def has_completed_goal(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Check whether this turn confirmed the goal's completed endpoint."""

    path = _state_path(event)
    return bool(path and goal_id in _load(path, project_id)["completed_goal_ids"])


def has_summary_fact(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Check whether Curator accepted the required compact summary fact."""

    path = _state_path(event)
    return bool(path and goal_id in _load(path, project_id)["summary_fact_goal_ids"])


def has_summary_ready(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Check whether the summary was read back before the goal finish call."""

    path = _state_path(event)
    return bool(path and goal_id in _load(path, project_id)["summary_ready_goal_ids"])


def record_prompt_cue(
    event: dict[str, object], project_id: str, cue: str
) -> bool:
    """Persist only a recognized lifecycle category, never submitted text."""

    if cue not in _PROMPT_CUES:
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["prompt_cues"] = {cue}
    return _write(path, project_id, state)


def prompt_cue(event: dict[str, object], project_id: str) -> str | None:
    """Return the normalized user transition cue saved for this Codex turn."""

    path = _state_path(event)
    if path is None:
        return None
    cues = _load(path, project_id)["prompt_cues"]
    return next(iter(cues), None)


def has_unconfirmed_finish(event: dict[str, object], project_id: str) -> bool:
    """Check whether a finish request still needs a status readback."""

    path = _state_path(event)
    return bool(path and _load(path, project_id)["finish_requested_goal_ids"])


def has_unassessed_completion(event: dict[str, object], project_id: str) -> bool:
    """Require a completed task's pending owner-review proposal before stopping."""

    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    return bool(state["completed_goal_ids"] - state["sde_proposal_goal_ids"])


def has_sde_readback_pending(event: dict[str, object], project_id: str) -> bool:
    """Require exact candidate detail confirmation before another activation."""

    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    return any(
        pair.split("|", maxsplit=1)[0] in state["completed_goal_ids"]
        and pair not in state["sde_reviewed_candidate_pairs"]
        for pair in state["sde_candidate_pairs"]
    )


def has_unconfirmed_defer(event: dict[str, object], project_id: str) -> bool:
    """Check whether a defer request still needs a status readback."""

    path = _state_path(event)
    return bool(path and _load(path, project_id)["defer_requested_goal_ids"])


def has_unconfirmed_report(event: dict[str, object], project_id: str) -> bool:
    """Require a goal readback after an accepted task write."""

    path = _state_path(event)
    return bool(path and _load(path, project_id)["report_pending_goal_ids"])


def has_stop_followup(event: dict[str, object], project_id: str, stage: str) -> bool:
    """Check whether this turn already received one follow-up for a stage."""

    path = _state_path(event)
    return bool(path and stage in _load(path, project_id)["stop_prompted_stages"])


def record_goal_state(
    event: dict[str, object], project_id: str, goal_id: str, active: bool
) -> bool:
    """Record only an opaque goal ID after an accepted MCP response."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    goals = state["active_goal_ids"]
    if active:
        goals.add(goal_id)
    else:
        goals.discard(goal_id)
        state["fact_recorded_goal_ids"].discard(goal_id)
        state["scope_valid_goal_ids"].discard(goal_id)
    if any(len(values) > 32 for values in state.values()):
        return False
    return _write(path, project_id, state)


def record_fact_state(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Remember that an accepted fact was written, without its contents."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["fact_recorded_goal_ids"].add(goal_id)
    state["summary_ready_goal_ids"].discard(goal_id)
    tool_input = event.get("tool_input")
    is_summary = (
        isinstance(tool_input, dict)
        and tool_input.get("kind") == "change"
        and isinstance(tool_input.get("bullet"), str)
        and cast(str, tool_input["bullet"]).startswith("Task summary:")
    )
    if not is_summary:
        state["summary_invalidated_goal_ids"].add(goal_id)
    if len(state["fact_recorded_goal_ids"]) > 32:
        return False
    return _write(path, project_id, state)


def _evidence_fingerprint(
    goal_id: str, criterion_id: str, reference: object
) -> str | None:
    """Hash only the bounded evidence fields needed for same-turn matching."""

    if not isinstance(reference, dict):
        return None
    evidence = cast(dict[str, object], reference)
    evidence_kind = evidence.get("evidence_kind")
    locator = evidence.get("locator")
    sha256 = evidence.get("sha256")
    outcome = evidence.get("outcome")
    occurrence_id = evidence.get("occurrence_id")
    if (
        not isinstance(evidence_kind, str)
        or not 1 <= len(evidence_kind) <= 128
        or not isinstance(locator, str)
        or not 1 <= len(locator.encode("utf-8")) <= 4096
        or not isinstance(sha256, str)
        or not _SHA256.fullmatch(sha256)
        or not isinstance(outcome, str)
        or outcome not in {"passed", "failed", "unknown"}
        or (occurrence_id is not None and (
            not isinstance(occurrence_id, str) or not 1 <= len(occurrence_id) <= 256
        ))
    ):
        return None
    canonical = json.dumps(
        {
            "goal_id": goal_id,
            "criterion_id": criterion_id,
            "evidence_kind": evidence_kind,
            "locator": locator,
            "sha256": sha256,
            "outcome": outcome,
            "occurrence_id": occurrence_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_evidence_capture_state(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Remember only a hash of a successful configured evidence capture."""

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict) or tool_input.get("goal_id") != goal_id:
        return False
    criterion_id = tool_input.get("criterion_id")
    reference = _response_object(event)
    if (
        not isinstance(criterion_id, str)
        or not 1 <= len(criterion_id) <= 128
        or not isinstance(reference, dict)
        or reference.get("evidence_kind") != tool_input.get("evidence_kind")
        or reference.get("locator") != tool_input.get("locator")
        or reference.get("outcome") != "passed"
    ):
        return False
    fingerprint = _evidence_fingerprint(goal_id, criterion_id, reference)
    path = _state_path(event)
    if fingerprint is None or path is None:
        return False
    state = _load(path, project_id)
    state["captured_evidence_fingerprints"].add(fingerprint)
    return _write(path, project_id, state)


def has_captured_verification_evidence(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Require every verification reference to match a host capture this turn."""

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict) or tool_input.get("kind") != "verification":
        return True
    criterion_id = tool_input.get("criterion_id")
    evidence = tool_input.get("evidence")
    path = _state_path(event)
    if (
        not isinstance(criterion_id, str)
        or not 1 <= len(criterion_id) <= 128
        or not isinstance(evidence, list)
        or not evidence
        or path is None
    ):
        return False
    captured = _load(path, project_id)["captured_evidence_fingerprints"]
    return all(
        (fingerprint := _evidence_fingerprint(goal_id, criterion_id, reference))
        is not None and fingerprint in captured
        for reference in evidence
    )


def record_summary_fact(event: dict[str, object], project_id: str, goal_id: str) -> bool:
    """Remember only an accepted, explicitly marked task-summary fact."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return False
    if tool_input.get("kind") != "change":
        return False
    bullet = tool_input.get("bullet")
    if not isinstance(bullet, str) or not bullet.startswith("Task summary:"):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["summary_fact_goal_ids"].add(goal_id)
    state["summary_invalidated_goal_ids"].discard(goal_id)
    return _write(path, project_id, state)


def record_finish_request(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Wait for goal_status to confirm completion before requesting an SDE."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["finish_requested_goal_ids"].add(goal_id)
    if len(state["finish_requested_goal_ids"]) > 32:
        return False
    return _write(path, project_id, state)


def record_completed_goal(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Remember a confirmed finish so it receives an owner-review proposal."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    if goal_id not in state["finish_requested_goal_ids"]:
        return False
    state["completed_goal_ids"].add(goal_id)
    return _write(path, project_id, state)


def record_sde_proposal_state(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Remember only a successful pending proposal for its own completed goal."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    if goal_id not in state["completed_goal_ids"]:
        return False
    result = _response_object(event)
    candidate_id = result.get("candidate_id") if result else None
    if not isinstance(candidate_id, str) or not _GOAL_ID.fullmatch(candidate_id):
        return False
    pair = f"{goal_id}|{candidate_id}"
    state["sde_candidate_pairs"].add(pair)
    state["sde_proposal_goal_ids"].add(goal_id)
    if not _write(path, project_id, state):
        return False
    handoff_path = _ootask_handoff_path(event, project_id)
    if handoff_path is None:
        return False
    handoff = _load(handoff_path, project_id)
    if goal_id in handoff["ootask_goal_ids"]:
        handoff["ootask_sde_candidate_pairs"].add(pair)
        return _write(handoff_path, project_id, handoff)
    return True


def resolve_sde_candidate_readback(
    event: dict[str, object], project_id: str
) -> bool:
    """Clear the proposal gate only for exact pending candidate detail."""

    path = _state_path(event)
    result = _response_object(event)
    detail = result.get("candidate") if result else None
    if path is None or not isinstance(detail, dict):
        return False
    goal_id = detail.get("goal_id")
    candidate_id = detail.get("candidate_id")
    if (
        not isinstance(goal_id, str)
        or not _GOAL_ID.fullmatch(goal_id)
        or detail.get("status") != "pending_review"
        or not isinstance(candidate_id, str)
        or not _GOAL_ID.fullmatch(candidate_id)
    ):
        return False
    pair = f"{goal_id}|{candidate_id}"
    state = _load(path, project_id)
    reviewed_turn = pair in state["sde_candidate_pairs"]
    if reviewed_turn:
        state["sde_reviewed_candidate_pairs"].add(pair)
        if not _write(path, project_id, state):
            return False
    handoff_path = _ootask_handoff_path(event, project_id)
    if handoff_path is None:
        return reviewed_turn
    handoff = _load(handoff_path, project_id)
    if pair not in handoff["ootask_sde_candidate_pairs"]:
        return reviewed_turn
    handoff["ootask_sde_reviewed_candidate_pairs"].add(pair)
    return _write(handoff_path, project_id, handoff)


def ootask_resume_state(
    event: dict[str, object], project_id: str
) -> tuple[set[str], bool]:
    """Return paused child IDs and whether that OOTASK has a read-back SDE."""

    path = _ootask_handoff_path(event, project_id)
    if path is None:
        return set(), False
    state = _load(path, project_id)
    ready = any(
        pair in state["ootask_sde_reviewed_candidate_pairs"]
        and pair.split("|", maxsplit=1)[0] in state["ootask_goal_ids"]
        for pair in state["ootask_sde_candidate_pairs"]
    )
    return state["ootask_paused_goal_ids"], ready


def record_defer_request(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Wait for goal_status to confirm a requested hold before dropping it."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["defer_requested_goal_ids"].add(goal_id)
    if len(state["defer_requested_goal_ids"]) > 32:
        return False
    return _write(path, project_id, state)


def record_report_pending(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Remember that an accepted task write still needs a matching readback."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["report_pending_goal_ids"].add(goal_id)
    if len(state["report_pending_goal_ids"]) > 32:
        return False
    return _write(path, project_id, state)


def resolve_report_pending(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Clear readback only after a matching goal status/report response."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["report_pending_goal_ids"].discard(goal_id)
    return _write(path, project_id, state)


def resolve_defer_request(
    event: dict[str, object], project_id: str, goal_id: str, deferred: bool
) -> bool:
    """Clear a defer request after status readback and close active state if held."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    requested = goal_id in state["defer_requested_goal_ids"]
    state["defer_requested_goal_ids"].discard(goal_id)
    if deferred and requested:
        state["active_goal_ids"].discard(goal_id)
        state["fact_recorded_goal_ids"].discard(goal_id)
        if "ootask" in state["task_scope_cues"]:
            handoff_path = _ootask_handoff_path(event, project_id)
            if handoff_path is None:
                return False
            handoff = _load(handoff_path, project_id)
            handoff["ootask_paused_goal_ids"].add(goal_id)
            if not _write(handoff_path, project_id, handoff):
                return False
    return _write(path, project_id, state)


def resolve_ootask_resume(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Clear the handoff only after the exact paused goal is activated."""

    turn_path = _state_path(event)
    path = _ootask_handoff_path(event, project_id)
    if turn_path is None or path is None:
        return False
    turn_state = _load(turn_path, project_id)
    turn_state["ootask_paused_goal_ids"].discard(goal_id)
    if not _write(turn_path, project_id, turn_state):
        return False
    state = _load(path, project_id)
    if goal_id not in state["ootask_paused_goal_ids"]:
        return False
    state["ootask_paused_goal_ids"].discard(goal_id)
    for pair in tuple(state["ootask_sde_candidate_pairs"]):
        if pair.split("|", maxsplit=1)[0] in state["ootask_goal_ids"]:
            state["ootask_sde_candidate_pairs"].discard(pair)
            state["ootask_sde_reviewed_candidate_pairs"].discard(pair)
    state["ootask_goal_ids"].clear()
    return _write(path, project_id, state)


def record_stop_followup(
    event: dict[str, object], project_id: str, stage: str
) -> bool:
    """Remember a bounded lifecycle follow-up stage without storing its text."""

    if stage not in {"lifecycle", "report", "status", "summary", "sde", "sde_readback"}:
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    state["stop_prompted_stages"].add(stage)
    return _write(path, project_id, state)


def resolve_finish_request(
    event: dict[str, object], project_id: str, goal_id: str, completed: bool
) -> bool:
    """Clear completion intent after its final status readback."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    requested = goal_id in state["finish_requested_goal_ids"]
    state["finish_requested_goal_ids"].discard(goal_id)
    summary_ready = goal_id in state["summary_ready_goal_ids"]
    if completed and requested and summary_ready:
        state["active_goal_ids"].discard(goal_id)
        state["fact_recorded_goal_ids"].discard(goal_id)
        state["summary_ready_goal_ids"].discard(goal_id)
    elif requested:
        state["summary_ready_goal_ids"].discard(goal_id)
    return _write(path, project_id, state)


def resolve_task_summary_readback(
    event: dict[str, object], project_id: str, goal_id: str
) -> bool:
    """Mark summary ready only after a matching active-goal report shows it."""

    if not _GOAL_ID.fullmatch(goal_id):
        return False
    response = event.get("tool_response")
    if not isinstance(response, dict) or response.get("isError") is True:
        return False
    contents = response.get("content")
    if not isinstance(contents, list) or not any(
        isinstance(content, dict)
        and content.get("type") == "text"
        and isinstance(content.get("text"), str)
        and "Task summary:" in cast(str, content["text"])
        for content in contents
    ):
        return False
    path = _state_path(event)
    if path is None:
        return False
    state = _load(path, project_id)
    if goal_id not in state["active_goal_ids"] or (
        goal_id in state["summary_invalidated_goal_ids"]
        and goal_id not in state["summary_fact_goal_ids"]
    ):
        return False
    state["summary_fact_goal_ids"].discard(goal_id)
    state["summary_invalidated_goal_ids"].discard(goal_id)
    state["summary_ready_goal_ids"].add(goal_id)
    return _write(path, project_id, state)


def _response_object(event: dict[str, object]) -> dict[str, object] | None:
    response = event.get("tool_response")
    if isinstance(response, dict):
        if response.get("isError") is True:
            return None
        contents = response.get("content")
        if isinstance(contents, list):
            for content in contents:
                if not isinstance(content, dict) or content.get("type") != "text":
                    continue
                text = content.get("text")
                if (
                    isinstance(text, str)
                    and len(text.encode("utf-8")) <= _MAX_TOOL_RESPONSE_BYTES
                ):
                    try:
                        decoded: object = json.loads(text)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    if isinstance(decoded, dict):
                        return cast(dict[str, object], decoded)
        return None
    if (
        isinstance(response, str)
        and len(response.encode("utf-8")) <= _MAX_TOOL_RESPONSE_BYTES
    ):
        try:
            decoded = json.loads(response)
        except (ValueError, json.JSONDecodeError):
            return None
        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)
    return None


def accepted_event_result(event: dict[str, object]) -> bool:
    """Recognize only processed or exact duplicate lifecycle event receipts."""

    result = _response_object(event)
    return bool(result and result.get("status") in {"processed", "duplicate"})


def accepted_sde_result(event: dict[str, object], goal_id: str) -> bool:
    """Recognize only a matching proposal left pending for owner review."""

    result = _response_object(event)
    return bool(
        result
        and result.get("goal_id") == goal_id
        and result.get("status") == "pending_review"
        and isinstance(result.get("candidate_id"), str)
        and _GOAL_ID.fullmatch(cast(str, result["candidate_id"]))
    )


def goal_status_result(event: dict[str, object], goal_id: str) -> str | None:
    """Return a lifecycle status only for the matching goal."""

    result = _response_object(event)
    goal = result.get("goal") if result else None
    if not isinstance(goal, dict) or goal.get("goal_id") != goal_id:
        return None
    status = goal.get("status")
    return status if status in {
        "planned", "active", "open", "complete", "deferred", "blocked", "cancelled", "superseded"
    } else None


def goal_report_matches(event: dict[str, object], goal_id: str) -> bool:
    """Accept only a successful report that names the requested goal."""

    response = event.get("tool_response")
    if not isinstance(response, dict) or response.get("isError") is True:
        return False
    contents = response.get("content")
    if not isinstance(contents, list):
        return False
    for content in contents:
        if not isinstance(content, dict) or content.get("type") != "text":
            continue
        text = content.get("text")
        if not isinstance(text, str) or len(text.encode("utf-8")) > 64 * 1024:
            continue
        result = _response_object(event)
        goal = result.get("goal") if result else None
        if isinstance(goal, dict) and goal.get("goal_id") == goal_id:
            return True
        if f"# Goal `{goal_id}`" in text:
            return True
    return False


def goal_id_from_input(event: dict[str, object]) -> str | None:
    """Read only the opaque goal ID from a bounded MCP tool argument object."""

    value: Any = event.get("tool_input")
    if not isinstance(value, dict):
        return None
    goal_id = value.get("goal_id")
    return goal_id if isinstance(goal_id, str) and _GOAL_ID.fullmatch(goal_id) else None
