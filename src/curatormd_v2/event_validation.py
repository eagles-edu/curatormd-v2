"""Strict, content-safe validation primitives for versioned events."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar, cast

from .validation import is_exact_int

EnumValue = TypeVar("EnumValue", bound=StrEnum)


def parse_event_enum(enum_type: type[EnumValue], value: str, message: str) -> EnumValue:
    """Parse an untrusted enum without retaining it in an exception chain."""

    parse_failed = False
    parsed: EnumValue | None = None
    try:
        parsed = enum_type(value)
    except ValueError:
        parse_failed = True
    if parse_failed or parsed is None:
        raise ValueError(message)
    return parsed


def validate_lifecycle_revision(revision: int | None) -> None:
    """Require a positive exact lifecycle revision when supplied."""

    if revision is not None and (not is_exact_int(revision) or revision < 1):
        raise ValueError("expected_lifecycle_revision must be a positive integer")


def reject_duplicate_event_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build an event object while rejecting repeated JSON keys."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("event contains a duplicate JSON field")
        result[key] = value
    return result


def require_event_object(value: object, name: str) -> dict[str, object]:
    """Require a mapping with string keys for one event field."""

    if not isinstance(value, dict) or any(
        not isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise ValueError(f"{name} must be an object with string keys")
    return cast(dict[str, object], value)


def require_event_fields(
    value: dict[str, object],
    required: set[str],
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    """Require exactly the declared fields in an event object."""

    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        raise ValueError(f"invalid fields; missing={sorted(missing)}, extra={sorted(extra)}")


def event_string(value: object, name: str, *, optional: bool = False) -> str | None:
    """Validate an event string field, optionally accepting null."""

    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def optional_event_revision(value: object) -> int | None:
    """Parse a positive exact lifecycle revision or an absent value."""

    if value is None:
        return None
    if not is_exact_int(value) or value < 1:
        raise ValueError("expected_lifecycle_revision must be a positive integer")
    return value


def event_utf8_length(value: str) -> int:
    """Measure UTF-8 bytes without retaining malformed input in exceptions."""

    invalid_utf8 = False
    try:
        length = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        # UnicodeEncodeError retains the complete source in its ``object`` field.
        invalid_utf8 = True
        length = 0
    if invalid_utf8:
        raise ValueError("event contains text that is not valid UTF-8")
    return length
