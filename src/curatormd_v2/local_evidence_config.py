"""Load owner-only host evidence configuration for local Curator alpha."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import cast

from .browser_evidence import LocalBrowserProofResolver, LocalBrowserProofSpec
from .evidence import (
    BrowserProofEvidenceAdapter,
    EvidenceAdapterPolicy,
    EvidenceAdapterRegistry,
    ReceiptEvidenceAdapter,
    EvidenceVerifier,
    ServiceProbeEvidenceAdapter,
)
from .models import EvidenceRef
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

    config = _parse_document(data, expected_project_id, "probe")
    raw_probe = config["probe"]
    if not isinstance(raw_probe, dict):
        raise ValueError("host evidence config probe is invalid")
    return _parse_probe(cast(dict[str, object], raw_probe), expected_project_id)


def _parse_browser_config(
    data: bytes, expected_project_id: str
) -> tuple[str, LocalBrowserProofSpec]:
    """Parse one project-bound local browser proof configuration."""

    config = _parse_document(data, expected_project_id, "browser_proof")
    raw_proof = config["browser_proof"]
    if not isinstance(raw_proof, dict):
        raise ValueError("host evidence config browser_proof is invalid")
    proof = cast(dict[str, object], raw_proof)
    required = {"adapter_id", "proof_id", "url", "executable"}
    optional = {"max_output_bytes", "timeout_seconds"}
    if not required.issubset(proof) or not set(proof).issubset(required | optional):
        raise ValueError("host evidence config browser_proof fields are invalid")
    adapter_id = _required_text(proof["adapter_id"], "adapter_id")
    proof_id = _required_text(proof["proof_id"], "proof_id")
    url = _required_text(proof["url"], "url", max_chars=450)
    executable = _required_text(proof["executable"], "executable", max_chars=4096)
    max_output_bytes = proof.get("max_output_bytes", 1024 * 1024)
    timeout_seconds = proof.get("timeout_seconds", 20)
    if not is_exact_int(max_output_bytes) or not is_exact_int(timeout_seconds):
        raise ValueError("host evidence config browser limits must be exact integers")
    if not hasattr(os, "geteuid"):
        raise ValueError("local browser proof requires a local OS identity")
    return (
        adapter_id,
        LocalBrowserProofSpec(
            project_id=expected_project_id,
            proof_id=proof_id,
            url=url,
            executable=executable,
            max_output_bytes=max_output_bytes,
            timeout_seconds=timeout_seconds,
        ),
    )


def _parse_document(
    data: bytes, expected_project_id: str, required_source: str | None
) -> dict[str, object]:
    """Validate the shared owner-only evidence config envelope."""

    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("host evidence config is not valid UTF-8 JSON") from None
    if not isinstance(document, dict):
        raise ValueError("host evidence config schema is invalid")
    config = cast(dict[str, object], document)
    allowed_fields = {"schema_version", "project_id", "probe", "browser_proof"}
    required_fields = {"schema_version", "project_id"}
    if required_source is not None:
        required_fields.add(required_source)
    if not required_fields.issubset(config) or not set(config).issubset(allowed_fields):
        raise ValueError("host evidence config schema is invalid")
    if not {"probe", "browser_proof"}.intersection(config):
        raise ValueError("host evidence config must define a source")
    if not is_exact_int(config["schema_version"]) or config["schema_version"] != 1:
        raise ValueError("host evidence config schema version is unsupported")
    project_id = _required_text(config["project_id"], "project_id")
    if project_id != expected_project_id:
        raise ValueError("host evidence config project does not match the bound project")
    return config


def _service_adapter(
    adapter_id: str, project_id: str, spec: LocalServiceProbeSpec
) -> ServiceProbeEvidenceAdapter:
    """Construct a bounded service adapter from validated host configuration."""

    return ServiceProbeEvidenceAdapter(
        adapter_id=adapter_id,
        scope_id=spec.scope_id,
        resolver=LocalServiceProbeResolver(spec),
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={spec.source_subject},
            max_observation_age_seconds=spec.timeout_seconds,
            max_validity_seconds=spec.timeout_seconds,
            max_revocation_age_seconds=60,
        ),
    )


def _browser_adapter(
    adapter_id: str, project_id: str, spec: LocalBrowserProofSpec
) -> BrowserProofEvidenceAdapter:
    """Construct a short-lived local browser adapter from host configuration."""

    return BrowserProofEvidenceAdapter(
        adapter_id=adapter_id,
        scope_id=spec.scope_id,
        resolver=LocalBrowserProofResolver(spec),
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={spec.source_subject},
            max_observation_age_seconds=900,
            max_validity_seconds=900,
            max_revocation_age_seconds=60,
        ),
    )


def load_local_service_probe_verifier(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceVerifier:
    """Load one owner-only probe config without consulting consumer config."""

    config_path = Path(path).expanduser()
    data = _read_owner_only_file(config_path)
    adapter_id, spec = _parse_config(data, project_id)
    return _service_adapter(adapter_id, project_id, spec)


def load_local_browser_proof_verifier(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceVerifier:
    """Load one owner-only loopback browser proof config."""

    data = _read_owner_only_file(Path(path).expanduser())
    adapter_id, spec = _parse_browser_config(data, project_id)
    return _browser_adapter(adapter_id, project_id, spec)


def capture_local_browser_proof_reference(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceRef:
    """Capture only a digest reference from one owner-configured local route."""

    data = _read_owner_only_file(Path(path).expanduser())
    _adapter_id, spec = _parse_browser_config(data, project_id)
    return LocalBrowserProofResolver(spec).capture_reference()


def load_local_evidence_verifier(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceVerifier:
    """Load configured local service/browser sources behind one fixed registry."""

    data = _read_owner_only_file(Path(path).expanduser())
    config = _parse_document(data, project_id, None)
    adapters: list[ReceiptEvidenceAdapter] = []
    if "probe" in config:
        adapter_id, spec = _parse_probe(
            cast(dict[str, object], config["probe"]), project_id
        )
        adapters.append(_service_adapter(adapter_id, project_id, spec))
    if "browser_proof" in config:
        adapter_id, spec = _parse_browser_config(data, project_id)
        adapters.append(_browser_adapter(adapter_id, project_id, spec))
    if len(adapters) == 1:
        return adapters[0]
    return EvidenceAdapterRegistry(tuple(adapters))
