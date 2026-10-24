"""Small shared validators for external Python values."""

from __future__ import annotations

import re
from typing import TypeGuard

_CHECKLIST_VERSION_RE = re.compile(r"sha256:[0-9a-f]{64}")


def validate_checklist_snapshot(
    checklist_id: str | None,
    checklist_version: str | None,
    source_text: str | None,
) -> None:
    """Validate an optional exact one-line checklist source snapshot."""

    snapshot = (checklist_version, source_text)
    if not any(value is not None for value in snapshot):
        return
    if checklist_id is None or any(value is None for value in snapshot):
        raise ValueError(
            "checklist snapshot requires checklist_id, version, and source text"
        )
    if not _CHECKLIST_VERSION_RE.fullmatch(checklist_version or ""):
        raise ValueError("checklist_version must be a SHA-256 source revision")
    text = source_text or ""
    if not text.strip() or len(text) > 4000:
        raise ValueError("checklist source text must contain 1-4000 characters")
    if "\n" in text or "\r" in text:
        raise ValueError("checklist source text must be one exact item line")


def is_exact_int(value: object) -> TypeGuard[int]:
    """Accept built-in integers only, excluding booleans and integer subclasses."""

    return type(value) is int  # pylint: disable=unidiomatic-typecheck


def is_exact_bool(value: object) -> TypeGuard[bool]:
    """Accept only built-in bool values at untrusted runtime boundaries."""

    return type(value) is bool  # pylint: disable=unidiomatic-typecheck


def is_exact_number(value: object) -> TypeGuard[int | float]:
    """Accept built-in integers/floats only, excluding booleans and subclasses."""

    return type(value) in (int, float)  # pylint: disable=unidiomatic-typecheck
