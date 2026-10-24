"""Shared validation primitives for persisted Curator V2 record models."""

from __future__ import annotations

from datetime import UTC, datetime
import re


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEWER_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def parse_aware_timestamp(name: str, value: object) -> datetime:
    """Parse one bounded timezone-aware timestamp from a runtime value."""

    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError(f"{name} must be a bounded ISO-8601 timestamp")
    parse_failed = False
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parse_failed = True
    if parse_failed or parsed is None:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def parse_optional_aware_timestamp(value: object) -> datetime | None:
    """Parse a bounded timezone-aware timestamp, returning None on invalid input."""

    try:
        return parse_aware_timestamp("timestamp", value)
    except (OverflowError, ValueError):
        return None
