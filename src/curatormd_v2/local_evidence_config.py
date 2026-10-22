"""Load owner-only host evidence configuration for local Curator alpha."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import cast

from .evidence import EvidenceAdapterPolicy, EvidenceVerifier, ServiceProbeEvidenceAdapter
from .service_evidence import LocalServiceProbeResolver, LocalServiceProbeSpec
from .validation import is_exact_int

MAX_LOCAL_EVIDENCE_CONFIG_BYTES = 16 * 1024


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of accepting the last value."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("host evidence config contains duplicate keys")
        result[key] = value
    return result


def _read_owner_only_file(path: Path) -> bytes:
    """Read one bounded regular file owned and readable only by this account."""

    if (
        not path.is_absolute()
        or not hasattr(os, "geteuid")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise ValueError("host evidence config must use an absolute local path")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ValueError("host evidence config is unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_LOCAL_EVIDENCE_CONFIG_BYTES
        ):
            raise ValueError("host evidence config ownership, mode, or size is invalid")
        chunks: list[bytes] = []
        total_bytes = 0
        while chunk := os.read(
            descriptor, min(4096, MAX_LOCAL_EVIDENCE_CONFIG_BYTES + 1 - total_bytes)
        ):
            chunks.append(chunk)
            total_bytes += len(chunk)
            if total_bytes > MAX_LOCAL_EVIDENCE_CONFIG_BYTES:
                raise ValueError("host evidence config exceeds its byte limit")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _required_text(value: object, name: str, max_chars: int = 128) -> str:
    """Validate one bounded host config string without echoing its value."""

    if not isinstance(value, str) or not value or len(value) > max_chars:
        raise ValueError(f"host evidence config {name} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"host evidence config {name} is invalid")
    return value


def _parse_probe(
    probe: dict[str, object], project_id: str
) -> tuple[str, LocalServiceProbeSpec]:
    """Validate and build one project-bound host service probe."""

    required = {
        "adapter_id",
        "probe_id",
        "source_subject",
        "command",
        "working_directory",
    }
    optional = {"max_output_bytes", "timeout_seconds"}
    if not required.issubset(probe) or not set(probe).issubset(required | optional):
        raise ValueError("host evidence config probe fields are invalid")
    adapter_id = _required_text(probe["adapter_id"], "adapter_id")
    probe_id = _required_text(probe["probe_id"], "probe_id")
    source_subject = _required_text(probe["source_subject"], "source_subject")
    if not source_subject.startswith("local-probe:") or len(
        source_subject
    ) == len("local-probe:"):
        raise ValueError("local service-probe subject must use the local-probe namespace")
    raw_command = probe["command"]
    if not isinstance(raw_command, list) or not raw_command:
        raise ValueError("host evidence config command must be a nonempty string array")
    command_values = cast(list[object], raw_command)
    if any(not isinstance(item, str) for item in command_values):
        raise ValueError("host evidence config command must be a nonempty string array")
    command = tuple(cast(str, item) for item in command_values)
    raw_working_directory = _required_text(
        probe["working_directory"], "working_directory", max_chars=4096
    )
    working_directory = Path(raw_working_directory)
    if not working_directory.is_absolute():
        raise ValueError("host evidence config working directory must be absolute")
    max_output_bytes = probe.get("max_output_bytes", 64 * 1024)
    timeout_seconds = probe.get("timeout_seconds", 30)
    if not is_exact_int(max_output_bytes) or not is_exact_int(timeout_seconds):
        raise ValueError("host evidence config limits must be exact integers")
    return (
        adapter_id,
        LocalServiceProbeSpec(
            project_id=project_id,
            probe_id=probe_id,
            source_subject=source_subject,
            command=command,
            working_directory=working_directory,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        ),
    )


def _parse_config(
    data: bytes, expected_project_id: str
) -> tuple[str, LocalServiceProbeSpec]:
    """Parse exactly one service probe pinned to the bound project."""

    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("host evidence config is not valid UTF-8 JSON") from None
    if not isinstance(document, dict):
        raise ValueError("host evidence config schema is invalid")
    config = cast(dict[str, object], document)
    if set(config) != {"schema_version", "project_id", "probe"}:
        raise ValueError("host evidence config schema is invalid")
    if not is_exact_int(config["schema_version"]) or config["schema_version"] != 1:
        raise ValueError("host evidence config schema version is unsupported")
    project_id = _required_text(config["project_id"], "project_id")
    if project_id != expected_project_id:
        raise ValueError("host evidence config project does not match the bound project")
    raw_probe = config["probe"]
    if not isinstance(raw_probe, dict):
        raise ValueError("host evidence config probe is invalid")
    return _parse_probe(cast(dict[str, object], raw_probe), project_id)


def load_local_service_probe_verifier(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceVerifier:
    """Load one owner-only probe config without consulting consumer config."""

    config_path = Path(path).expanduser()
    data = _read_owner_only_file(config_path)
    adapter_id, spec = _parse_config(data, project_id)
    resolver = LocalServiceProbeResolver(spec)
    return ServiceProbeEvidenceAdapter(
        adapter_id=adapter_id,
        scope_id=spec.scope_id,
        resolver=resolver,
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={spec.source_subject},
            max_observation_age_seconds=spec.timeout_seconds,
            max_validity_seconds=spec.timeout_seconds,
            max_revocation_age_seconds=60,
        ),
    )
