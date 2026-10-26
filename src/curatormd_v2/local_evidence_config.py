"""Load owner-only host evidence configuration for local Curator alpha."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast
from datetime import UTC, datetime

from .browser_evidence import LocalBrowserProofResolver, LocalBrowserProofSpec
from .evidence import (
    BrowserProofEvidenceAdapter,
    EvidenceAdapterPolicy,
    EvidenceAdapterRegistry,
    ReceiptEvidenceAdapter,
    EvidenceSourceResolver,
    EvidenceVerificationContext,
    EvidenceVerifier,
    HumanObservationEvidenceAdapter,
    ServiceProbeEvidenceAdapter,
)
from .human_observation import (
    LocalHumanObservationResolver,
    LocalHumanObservationSpec,
    capture_local_human_observation_reference as capture_human_reference,
)
from .git_evidence import (
    GitCommitDiffResolver,
    LocalGitTestRunnerConfig,
    LocalGitTestRunnerResolver,
)
from .models import EvidenceOutcome, EvidenceRef
from .private_file_security import require_private_regular_file
from .service_evidence import LocalServiceProbeResolver, LocalServiceProbeSpec
from .validation import is_exact_int

MAX_LOCAL_EVIDENCE_CONFIG_BYTES = 16 * 1024


class _RepositoryDiffAdapter(ReceiptEvidenceAdapter):
    """Adapter for one owner-configured immutable local Git diff source."""

    # pylint: disable=too-few-public-methods  # Selects the repository-diff evidence kind.

    evidence_kinds = frozenset({"repository_diff"})


class _RepositoryTestAdapter(ReceiptEvidenceAdapter):
    """Adapter for one owner-configured exact-commit local test runner."""

    # pylint: disable=too-few-public-methods  # Selects the repository-test evidence kind.

    evidence_kinds = frozenset({"repository_test"})


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
        require_private_regular_file(
            metadata,
            maximum_bytes=MAX_LOCAL_EVIDENCE_CONFIG_BYTES,
            description="host evidence config",
        )
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


def _required_string_array(value: object, name: str) -> tuple[str, ...]:
    """Validate a nonempty JSON string array without accepting coercions."""

    if not isinstance(value, list) or not value:
        raise ValueError(f"host evidence config {name} must be a string array")
    values = cast(list[object], value)
    if any(not isinstance(item, str) for item in values):
        raise ValueError(f"host evidence config {name} must be a string array")
    return tuple(cast(str, item) for item in values)


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


def _parse_repository_diff_config(
    data: bytes, expected_project_id: str
) -> tuple[str, GitCommitDiffResolver]:
    """Build one bounded Git diff resolver from the owner-only host file."""

    config = _parse_document(data, expected_project_id, "repository_diff")
    raw_source = config["repository_diff"]
    if not isinstance(raw_source, dict):
        raise ValueError("host evidence config repository_diff is invalid")
    source = cast(dict[str, object], raw_source)
    required = {"adapter_id", "source_subject", "repository_root"}
    optional = {"max_diff_bytes", "timeout_seconds"}
    if not required.issubset(source) or not set(source).issubset(required | optional):
        raise ValueError("host evidence config repository_diff fields are invalid")
    adapter_id = _required_text(source["adapter_id"], "adapter_id")
    subject = _required_text(source["source_subject"], "source_subject")
    if not subject.startswith("local-git:") or len(subject) == len("local-git:"):
        raise ValueError("local Git subject must use the local-git namespace")
    repository_root = _required_text(
        source["repository_root"], "repository_root", max_chars=4096
    )
    if not Path(repository_root).is_absolute():
        raise ValueError("host evidence Git repository root must be absolute")
    max_diff_bytes = source.get("max_diff_bytes", 32 * 1024 * 1024)
    timeout_seconds = source.get("timeout_seconds", 30)
    if not is_exact_int(max_diff_bytes) or not is_exact_int(timeout_seconds):
        raise ValueError("host evidence config Git limits must be exact integers")
    return adapter_id, GitCommitDiffResolver(
        repository_root,
        project_id=expected_project_id,
        source_subject=subject,
        max_diff_bytes=max_diff_bytes,
        timeout_seconds=timeout_seconds,
    )


def _parse_repository_test_config(
    data: bytes, expected_project_id: str
) -> tuple[str, LocalGitTestRunnerResolver]:
    """Build one fixed-argv Git test runner from the owner-only host file."""

    config = _parse_document(data, expected_project_id, "repository_test")
    raw_runner = config["repository_test"]
    if not isinstance(raw_runner, dict):
        raise ValueError("host evidence config repository_test is invalid")
    runner = cast(dict[str, object], raw_runner)
    required = {
        "adapter_id",
        "runner_id",
        "source_subject",
        "repository_root",
        "command",
    }
    optional = {"max_output_bytes", "timeout_seconds"}
    if not required.issubset(runner) or not set(runner).issubset(required | optional):
        raise ValueError("host evidence config repository_test fields are invalid")
    adapter_id = _required_text(runner["adapter_id"], "adapter_id")
    runner_id = _required_text(runner["runner_id"], "runner_id")
    subject = _required_text(runner["source_subject"], "source_subject")
    if not subject.startswith("local-git:") or len(subject) == len("local-git:"):
        raise ValueError("local Git subject must use the local-git namespace")
    repository_root = _required_text(
        runner["repository_root"], "repository_root", max_chars=4096
    )
    if not Path(repository_root).is_absolute():
        raise ValueError("host evidence Git repository root must be absolute")
    command = _required_string_array(runner["command"], "test command")
    max_output_bytes = runner.get("max_output_bytes", 4 * 1024 * 1024)
    timeout_seconds = runner.get("timeout_seconds", 300)
    if not is_exact_int(max_output_bytes) or not is_exact_int(timeout_seconds):
        raise ValueError("host evidence config Git limits must be exact integers")
    spec = LocalGitTestRunnerConfig(
        project_id=expected_project_id,
        runner_id=runner_id,
        source_subject=subject,
        command=command,
        max_output_bytes=max_output_bytes,
        timeout_seconds=timeout_seconds,
    )
    return adapter_id, LocalGitTestRunnerResolver(repository_root, config=spec)


def _parse_human_observation_config(
    data: bytes, expected_project_id: str
) -> tuple[str, LocalHumanObservationSpec]:
    """Build a local human source bound to the current effective OS account."""

    config = _parse_document(data, expected_project_id, "human_observation")
    raw_source = config["human_observation"]
    if not isinstance(raw_source, dict):
        raise ValueError("host evidence config human_observation is invalid")
    source = cast(dict[str, object], raw_source)
    required = {"adapter_id", "receipt_directory"}
    optional = {"validity_seconds"}
    if not required.issubset(source) or not set(source).issubset(required | optional):
        raise ValueError("host evidence config human_observation fields are invalid")
    if not hasattr(os, "geteuid"):
        raise ValueError("local human observation requires a local OS identity")
    adapter_id = _required_text(source["adapter_id"], "adapter_id")
    receipt_directory = _required_text(
        source["receipt_directory"], "receipt_directory", max_chars=4096
    )
    validity_seconds = source.get("validity_seconds", 900)
    if not is_exact_int(validity_seconds):
        raise ValueError("human observation validity_seconds must be an integer")
    return adapter_id, LocalHumanObservationSpec(
        adapter_id=adapter_id,
        project_id=expected_project_id,
        receipt_directory=Path(receipt_directory),
        validity_seconds=validity_seconds,
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
    source_fields = {
        "probe",
        "browser_proof",
        "repository_diff",
        "repository_test",
        "human_observation",
    }
    allowed_fields = {"schema_version", "project_id", *source_fields}
    required_fields = {"schema_version", "project_id"}
    if required_source is not None:
        required_fields.add(required_source)
    if not required_fields.issubset(config) or not set(config).issubset(allowed_fields):
        raise ValueError("host evidence config schema is invalid")
    if not source_fields.intersection(config):
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


def _repository_diff_adapter(
    adapter_id: str, project_id: str, resolver: GitCommitDiffResolver
) -> _RepositoryDiffAdapter:
    """Bind immutable commit-diff evidence to this exact local project."""

    return _RepositoryDiffAdapter(
        adapter_id=adapter_id,
        scope_id=resolver.scope_id,
        resolver=resolver,
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={resolver.source_subject},
            max_revocation_age_seconds=60,
        ),
    )


def _repository_test_adapter(
    adapter_id: str,
    project_id: str,
    resolver: LocalGitTestRunnerResolver,
) -> _RepositoryTestAdapter:
    """Bind exact-commit test receipts to this local project and runner."""

    return _RepositoryTestAdapter(
        adapter_id=adapter_id,
        scope_id=resolver.scope_id,
        resolver=resolver,
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={resolver.config.source_subject},
            max_revocation_age_seconds=60,
        ),
    )


def _human_observation_adapter(
    adapter_id: str, project_id: str, spec: LocalHumanObservationSpec
) -> HumanObservationEvidenceAdapter:
    """Bind attended receipts to one project, OS UID, and freshness window."""

    return HumanObservationEvidenceAdapter(
        adapter_id=adapter_id,
        scope_id=spec.scope_id,
        resolver=LocalHumanObservationResolver(spec),
        policy=EvidenceAdapterPolicy(
            allowed_projects={project_id},
            allowed_subjects={spec.authenticated_subject},
            max_observation_age_seconds=spec.validity_seconds,
            max_validity_seconds=spec.validity_seconds,
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


def _capture_source_reference(
    resolver: EvidenceSourceResolver,
    evidence: EvidenceRef,
    project_id: str,
    source_label: str,
) -> EvidenceRef:
    """Run one configured source and return only its digest receipt."""

    now = datetime.now(UTC)
    context = EvidenceVerificationContext(
        project_id=project_id,
        goal_id="local-evidence-capture",
        criterion_id="local-evidence-capture",
        now=now,
    )
    receipt = resolver.resolve(evidence, context)
    if receipt is None:
        raise ValueError(f"configured {source_label} source rejected the reference")
    return EvidenceRef(
        evidence_kind=evidence.evidence_kind,
        locator=evidence.locator,
        sha256=receipt.evidence_sha256,
        outcome=EvidenceOutcome.PASSED,
    )


def capture_local_service_probe_reference(
    path: str | Path,
    *,
    project_id: str,
) -> EvidenceRef:
    """Run the configured probe and print only its project-scoped digest ref."""

    data = _read_owner_only_file(Path(path).expanduser())
    config = _parse_document(data, project_id, "probe")
    raw_probe = config["probe"]
    if not isinstance(raw_probe, dict):
        raise ValueError("host evidence config probe is invalid")
    _adapter_id, spec = _parse_probe(cast(dict[str, object], raw_probe), project_id)
    evidence = EvidenceRef(
        evidence_kind="service_probe",
        locator=f"service-probe:{spec.probe_id}",
        sha256="0" * 64,
        outcome=EvidenceOutcome.PASSED,
    )
    return _capture_source_reference(
        LocalServiceProbeResolver(spec), evidence, project_id, "service probe"
    )


def capture_local_repository_diff_reference(
    path: str | Path,
    *,
    project_id: str,
    base_revision: str,
    head_revision: str,
) -> EvidenceRef:
    """Hash one exact host-configured full-commit diff without returning it."""

    data = _read_owner_only_file(Path(path).expanduser())
    _adapter_id, resolver = _parse_repository_diff_config(data, project_id)
    evidence = EvidenceRef(
        evidence_kind="repository_diff",
        locator=f"git-diff:{base_revision}..{head_revision}",
        sha256="0" * 64,
        outcome=EvidenceOutcome.PASSED,
    )
    return _capture_source_reference(
        resolver, evidence, project_id, "Git diff"
    )


def capture_local_repository_test_reference(
    path: str | Path,
    *,
    project_id: str,
    runner_id: str,
    commit_id: str,
) -> EvidenceRef:
    """Run one host-configured test command at an exact immutable commit."""

    data = _read_owner_only_file(Path(path).expanduser())
    _adapter_id, resolver = _parse_repository_test_config(data, project_id)
    evidence = EvidenceRef(
        evidence_kind="repository_test",
        locator=f"git-test:{runner_id}:{commit_id}",
        sha256="0" * 64,
        outcome=EvidenceOutcome.PASSED,
    )
    return _capture_source_reference(
        resolver, evidence, project_id, "Git test runner"
    )


def capture_local_human_observation_reference(
    path: str | Path,
    *,
    context: EvidenceVerificationContext,
    challenge: str,
    confirmation: str,
) -> EvidenceRef:
    """Create one attended, content-free local human observation receipt."""

    data = _read_owner_only_file(Path(path).expanduser())
    _adapter_id, spec = _parse_human_observation_config(data, context.project_id)
    return capture_human_reference(
        spec,
        context=context,
        challenge=challenge,
        confirmation=confirmation,
    )


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
    if "repository_diff" in config:
        adapter_id, resolver = _parse_repository_diff_config(data, project_id)
        adapters.append(_repository_diff_adapter(adapter_id, project_id, resolver))
    if "repository_test" in config:
        adapter_id, resolver = _parse_repository_test_config(data, project_id)
        adapters.append(_repository_test_adapter(adapter_id, project_id, resolver))
    if "human_observation" in config:
        adapter_id, spec = _parse_human_observation_config(data, project_id)
        adapters.append(_human_observation_adapter(adapter_id, project_id, spec))
    if len(adapters) == 1:
        return adapters[0]
    return EvidenceAdapterRegistry(tuple(adapters))
