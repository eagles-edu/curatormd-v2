"""Validate trusted Hermes context and derive its stable Curator source ID."""

from __future__ import annotations

import hashlib
import json
import re
from typing import cast

_HERMES_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}$")
_OPAQUE_SUBJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_AUTHENTICATED_SUBJECT_PREFIX = "auth:v1:"


def hermes_source_id(profile_id: str, project_id: str, source_epoch: int) -> str:
    """Keep existing source IDs at epoch one and separate later enrollments."""

    identity = f"{profile_id}\0{project_id}"
    if source_epoch > 1:
        identity += f"\0{source_epoch}"
    return "hermes-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def hermes_subject_grant_id(value: object) -> str | None:
    """Map a trusted Hermes subject to a stable, content-free project grant ID."""

    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        return None
    if (
        _OPAQUE_SUBJECT_RE.fullmatch(value)
        and value != "unbound"
        and not value.startswith(_AUTHENTICATED_SUBJECT_PREFIX)
    ):
        return value
    if not value.startswith(_AUTHENTICATED_SUBJECT_PREFIX):
        return None
    parts = _canonical_authenticated_subject_parts(
        value[len(_AUTHENTICATED_SUBJECT_PREFIX) :]
    )
    if parts is None:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"hermes-auth:{digest}"


def _canonical_authenticated_subject_parts(encoded: str) -> list[str] | None:
    """Accept exactly Hermes' canonical bounded provider/issuer/user tuple."""

    try:
        parts_value: object = json.loads(encoded)
    except ValueError:
        return None
    if not isinstance(parts_value, list):
        return None
    parts = cast(list[object], parts_value)
    if len(parts) != 3:
        return None
    if any(not isinstance(part, str) or len(part) > 256 for part in parts):
        return None
    string_parts = cast(list[str], parts)
    if (
        not string_parts[0]
        or not string_parts[2]
        or any(
            any(ord(char) < 0x20 or ord(char) == 0x7F for char in part)
            for part in string_parts
        )
        or json.dumps(string_parts, separators=(",", ":"), ensure_ascii=True) != encoded
    ):
        return None
    return string_parts


def require_durable_hermes_context(
    metadata: object,
    expected_profile_id: str,
) -> tuple[str, str]:
    """Validate the host-injected profile, session, and durable-event marker."""

    if not isinstance(metadata, dict):
        raise PermissionError("trusted Hermes profile context is unavailable or mismatched")
    values = cast(dict[str, object], metadata)
    profile_id = values.get("hermes/profile_id")
    if not isinstance(profile_id, str) or profile_id != expected_profile_id:
        raise PermissionError("trusted Hermes profile context is unavailable or mismatched")
    if values.get("hermes/durable_event") is not True:
        raise PermissionError(
            "Codex lifecycle ingestion requires a host-dispatched durable event"
        )
    session_id = values.get("hermes/session_id")
    if not isinstance(session_id, str) or not _HERMES_SESSION_ID_RE.fullmatch(session_id):
        raise PermissionError("trusted Hermes session context is unavailable")
    return profile_id, session_id
