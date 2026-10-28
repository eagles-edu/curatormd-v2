"""Translate bounded Hermes Codex-turn hooks into Curator lifecycle facts.

This adapter does not authenticate a Hermes profile or resolve a session-to-goal
binding. Its caller must supply a current binding obtained from a trusted host
registry and stable event metadata from a durable producer outbox. In
particular, hook metadata is never treated as a project ID, goal ID, or proof of
success.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping, cast

from .events import EventEnvelope, GoalActivityObserved
from .models import FactKind
from .validation import is_exact_int


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_START_EVENT = "codex:turn:start"
_END_EVENT = "codex:turn:end"
_START_FIELDS = frozenset({"attempt_id", "session_id", "model", "provider", "cwd"})
_END_FIELDS = _START_FIELDS | frozenset(
    {"turn_id", "outcome", "failure_kind", "work_summary_json"}
)
_OPTIONAL_METADATA_LIMITS = {
    "model": 128,
    "provider": 128,
    "cwd": 4096,
    "turn_id": 256,
    "failure_kind": 32,
    "work_summary_json": 4096,
}
_SUMMARY_PATH_RE = re.compile(r"^[A-Za-z0-9_./ @+-]{1,256}$")
_SUMMARY_CHANGE_KINDS = frozenset({"add", "update", "delete", "rename"})
_SUMMARY_CHECKS = frozenset(
    {"scripts/check", "scripts/run_tests.sh", "git diff --check", "pytest", "npm test"}
)


@dataclass(frozen=True, slots=True)
class CodexGoalBinding:
    """Host-resolved identity required before a Codex event can be projected."""

    profile_id: str
    project_id: str
    session_id: str
    goal_id: str
    source_id: str
    repository_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for name in ("profile_id", "project_id", "session_id", "goal_id", "source_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _ID_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded opaque identifier")
        if self.repository_fingerprint is not None and not re.fullmatch(
            r"[a-f0-9]{64}", self.repository_fingerprint
        ):
            raise ValueError("repository_fingerprint must be a lowercase SHA-256 digest")


def codex_hook_to_event(
    event_type: object,
    context: object,
    binding: CodexGoalBinding,
    *,
    source_sequence: int,
    occurred_at: object,
) -> EventEnvelope:
    """Build one compact fact event from a currently bound Hermes Codex hook.

    Stable opaque event/fact IDs are derived from the bound source, hook kind,
    and attempt ID. ``source_sequence`` and ``occurred_at`` must be assigned
    and durably retained by the producer before delivery. Runtime metadata
    other than the session match and bounded outcome is validated but omitted
    from the durable event.
    """

    selected_event = _validate_event_type(event_type)
    hook_context, attempt_id = _validated_hook_context(
        selected_event, context, binding
    )
    kind, bullet = _fact_for_hook(selected_event, hook_context, binding)
    if not isinstance(occurred_at, str):
        raise ValueError("occurred_at must be an ISO-8601 timestamp")
    if not is_exact_int(source_sequence) or source_sequence < 1:
        raise ValueError("source_sequence must be a positive integer")

    event_id, fact_id = _stable_ids(binding.source_id, selected_event, attempt_id)
    return EventEnvelope(
        event_id=event_id,
        project_id=binding.project_id,
        source_id=binding.source_id,
        source_sequence=source_sequence,
        occurred_at=occurred_at,
        payload=GoalActivityObserved(
            goal_id=binding.goal_id,
            fact_id=fact_id,
            kind=kind,
            bullet=bullet,
        ),
    )


def _validate_event_type(event_type: object) -> str:
    """Return a supported typed lifecycle event."""

    if isinstance(event_type, str) and event_type in {_START_EVENT, _END_EVENT}:
        return event_type
    raise ValueError("unsupported Hermes Codex lifecycle event")


def _validated_hook_context(
    event_type: str, context: object, binding: CodexGoalBinding
) -> tuple[Mapping[str, object], str]:
    """Validate bounded hook metadata against a host-resolved binding."""

    if not isinstance(context, Mapping):
        raise ValueError("hook context must be a mapping")
    raw_context = cast(Mapping[object, object], context)
    if any(not isinstance(key, str) for key in raw_context):
        raise ValueError("hook context keys must be strings")
    hook_context = cast(Mapping[str, object], raw_context)
    allowed_fields = _START_FIELDS if event_type == _START_EVENT else _END_FIELDS
    if not set(hook_context).issubset(allowed_fields):
        raise ValueError("hook context contains unsupported fields")
    attempt_id = _required_identifier(hook_context, "attempt_id")
    session_id = _required_identifier(hook_context, "session_id")
    if session_id != binding.session_id:
        raise ValueError("hook session does not match the current goal binding")
    _validate_optional_metadata(hook_context)
    return hook_context, attempt_id


def _fact_for_hook(
    event_type: str,
    hook_context: Mapping[str, object],
    binding: CodexGoalBinding,
) -> tuple[FactKind, str]:
    """Classify a lifecycle event without treating runtime status as proof."""

    if event_type == _START_EVENT:
        return FactKind.INTENT, "Codex turn started for the explicitly bound goal."

    _required_identifier(hook_context, "turn_id")
    outcome = hook_context.get("outcome")
    if outcome == "completed":
        summary = _work_summary_bullet(
            hook_context.get("work_summary_json"), binding.repository_fingerprint
        )
        if summary is not None:
            kind = (
                FactKind.OPEN_GATE
                if summary.startswith("A recorded development check failed.")
                else FactKind.CHANGE
            )
            return kind, f"{summary} No success criterion was verified."
        return (
            FactKind.CHANGE,
            "Codex turn ended normally; no success criterion was verified.",
        )
    if outcome in {"interrupted", "failed"}:
        summary = _work_summary_bullet(
            hook_context.get("work_summary_json"), binding.repository_fingerprint
        )
        detail = f" {summary}" if summary is not None else ""
        return (
            FactKind.OPEN_GATE,
            f"Codex turn ended with runtime outcome: {outcome}.{detail}",
        )
    raise ValueError("Codex turn end requires a supported runtime outcome")


def _work_summary_bullet(value: object, repository_fingerprint: str | None) -> str | None:
    """Render only validated, bounded file and check labels; never retain command text."""

    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value.encode("utf-8")) > 4096:
            return None
        decoded = json.loads(value)
    except (UnicodeEncodeError, TypeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    summary = cast(dict[str, object], decoded)
    if set(summary) != {
        "schema_version", "repository_fingerprint", "changed_files",
        "omitted_files", "checks", "omitted_checks"
    } or summary.get("schema_version") != 1:
        return None
    if (
        repository_fingerprint is None
        or summary.get("repository_fingerprint") != repository_fingerprint
    ):
        return None
    raw_changed_files = summary.get("changed_files")
    raw_checks = summary.get("checks")
    omitted_files = summary.get("omitted_files")
    omitted_checks = summary.get("omitted_checks")
    if (
        not isinstance(raw_changed_files, list)
        or not isinstance(raw_checks, list)
        or not is_exact_int(omitted_files) or not 0 <= omitted_files <= 1_000_000
        or not is_exact_int(omitted_checks) or not 0 <= omitted_checks <= 1_000_000
    ):
        return None
    changed_files = cast(list[object], raw_changed_files)
    checks = cast(list[object], raw_checks)
    if len(changed_files) > 16 or len(checks) > 8:
        return None
    paths: list[str] = []
    for item in changed_files:
        if not isinstance(item, dict):
            return None
        change_item = cast(dict[str, object], item)
        if set(change_item) != {"path", "change"}:
            return None
        path = change_item.get("path")
        change = change_item.get("change")
        if (
            not isinstance(path, str) or not _SUMMARY_PATH_RE.fullmatch(path)
            or path.startswith("/") or ".." in path.split("/")
            or any(
                part.lower().startswith((".env", "secret", "credential"))
                for part in path.split("/")
            )
            or not isinstance(change, str) or change not in _SUMMARY_CHANGE_KINDS
        ):
            return None
        paths.append(f"{path} ({change})")
    check_labels: list[str] = []
    has_failed_check = False
    for item in checks:
        if not isinstance(item, dict):
            return None
        check_item = cast(dict[str, object], item)
        if set(check_item) != {"name", "exit_code"}:
            return None
        name = check_item.get("name")
        exit_code = check_item.get("exit_code")
        if (
            not isinstance(name, str) or name not in _SUMMARY_CHECKS
            or not is_exact_int(exit_code) or not 0 <= exit_code <= 255
        ):
            return None
        has_failed_check = has_failed_check or exit_code != 0
        check_labels.append(f"{name} exited {exit_code}")
    parts: list[str] = []
    if paths or omitted_files:
        rendered = ", ".join(paths) if paths else "none listed"
        if omitted_files:
            rendered += f", {omitted_files} omitted"
        parts.append(f"Codex changed files: {rendered}.")
    if check_labels or omitted_checks:
        rendered = ", ".join(check_labels) if check_labels else "none listed"
        if omitted_checks:
            rendered += f", {omitted_checks} omitted"
        parts.append(f"Recorded checks: {rendered}.")
    if not parts:
        return None
    return " ".join(parts)[:900] if not has_failed_check else (
        "A recorded development check failed. " + " ".join(parts)
    )[:900]


def _stable_ids(source_id: str, event_type: str, attempt_id: str) -> tuple[str, str]:
    """Derive deterministic event and fact identifiers from a source attempt."""

    stable_key = f"{source_id}\0{event_type}\0{attempt_id}".encode("utf-8")
    event_digest = hashlib.sha256(stable_key).hexdigest()
    fact_digest = hashlib.sha256(stable_key + b"\0fact").hexdigest()
    return f"hermes-{event_digest}", f"fact-{fact_digest}"


def _required_identifier(context: Mapping[str, object], name: str) -> str:
    """Read one bounded, single-line correlation identifier from hook context."""

    value = context.get(name)
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError(f"{name} must be a bounded non-empty string")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be a single line")
    return value


def _validate_optional_metadata(context: Mapping[str, object]) -> None:
    """Reject unexpectedly large/non-text hook metadata without persisting it."""

    for name, limit in _OPTIONAL_METADATA_LIMITS.items():
        value = context.get(name)
        if value is not None and (
            not isinstance(value, str) or len(value) > limit or "\n" in value or "\r" in value
        ):
            raise ValueError(f"{name} must be bounded single-line text")

    outcome = context.get("outcome")
    if outcome is not None and (
        not isinstance(outcome, str)
        or len(outcome) > 32
        or "\n" in outcome
        or "\r" in outcome
    ):
        raise ValueError("outcome must be bounded single-line text")
