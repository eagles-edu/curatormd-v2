"""Bounded host-configured local service probe evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from .evidence import (
    EvidenceSourceReceipt,
    EvidenceVerificationContext,
    LocalSourceReceiptBinding,
    create_local_source_receipt,
)
from .evidence_process import BoundedEvidenceProcessRequest, hash_bounded_stdout
from .models import EvidenceRef
from .validation import is_exact_int

MAX_SERVICE_PROBE_OUTPUT_BYTES = 64 * 1024
MAX_SERVICE_PROBE_TIMEOUT_SECONDS = 30
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOCATOR_RE = re.compile(r"^service-probe:([A-Za-z0-9][A-Za-z0-9._:-]{0,127})$")


@dataclass(frozen=True, slots=True)
class LocalServiceProbeSpec:  # pylint: disable=too-many-instance-attributes
    """Validated immutable host configuration for one local service probe."""

    project_id: str
    probe_id: str
    source_subject: str
    command: tuple[str, ...]
    working_directory: Path
    max_output_bytes: int = MAX_SERVICE_PROBE_OUTPUT_BYTES
    timeout_seconds: int = MAX_SERVICE_PROBE_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        for name, value in (
            ("project_id", self.project_id),
            ("probe_id", self.probe_id),
            ("source_subject", self.source_subject),
        ):
            if not _IDENTIFIER_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded opaque identifier")
        if not self.command or len(self.command) > 64:
            raise ValueError("probe command must contain 1-64 arguments")
        if any(not item or len(item) > 1024 or "\x00" in item for item in self.command):
            raise ValueError("probe command arguments must be nonempty and bounded")
        if sum(len(item.encode("utf-8")) for item in self.command) > 8192:
            raise ValueError("probe command exceeds the local argument ceiling")
        if not is_exact_int(self.max_output_bytes) or not (
            1 <= self.max_output_bytes <= MAX_SERVICE_PROBE_OUTPUT_BYTES
        ):
            raise ValueError("max_output_bytes exceeds the local output ceiling")
        if not is_exact_int(self.timeout_seconds) or not (
            1 <= self.timeout_seconds <= MAX_SERVICE_PROBE_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds exceeds the service-probe ceiling")
        executable = shutil.which(self.command[0])
        if executable is None:
            raise ValueError("configured probe executable is unavailable")
        try:
            root = Path(self.working_directory).resolve(strict=True)
        except OSError:
            raise ValueError("probe working directory is unavailable") from None
        if not root.is_dir():
            raise ValueError("probe working directory is not a directory")
        object.__setattr__(self, "command", (executable, *self.command[1:]))
        object.__setattr__(self, "working_directory", root)

    @property
    def scope_id(self) -> str:
        """Return the non-secret probe scope identifier."""

        return f"local-service-probe:{self.probe_id}"

    @property
    def source_revision(self) -> str:
        """Return a digest identifying this exact configured command."""

        serialized_command = json.dumps(
            self.command, ensure_ascii=True, separators=(",", ":")
        ).encode()
        command_digest = hashlib.sha256(serialized_command).hexdigest()
        return f"local-probe:{self.probe_id}:{command_digest}"

    @property
    def environment(self) -> dict[str, str]:
        """Return the minimal environment used by the pinned executable."""

        return {
            "PATH": os.path.dirname(self.command[0]),
            "LANG": "C",
            "LC_ALL": "C",
        }


class LocalServiceProbeResolver:  # pylint: disable=too-few-public-methods
    """Run one exact host-configured command and retain only its output digest.

    The command, project, source subject, and working directory are host-owned.
    Evidence references can select this probe by its opaque ID, but cannot
    change its target or arguments. This is a local host assertion, not proof
    of a deployment-authenticated service identity.
    """

    def __init__(self, spec: LocalServiceProbeSpec) -> None:
        self.spec = spec

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Run the selected probe and return a receipt containing no raw output."""

        if (
            context.project_id != self.spec.project_id
            or evidence.evidence_kind != "service_probe"
        ):
            return None
        match = _LOCATOR_RE.fullmatch(evidence.locator)
        if match is None or match.group(1) != self.spec.probe_id:
            return None

        digest = self._run_probe()
        return create_local_source_receipt(
            LocalSourceReceiptBinding(
                evidence_kind="service_probe",
                scope_id=self.spec.scope_id,
                source_revision=self.spec.source_revision,
                authenticated_subject=self.spec.source_subject,
                validity_seconds=self.spec.timeout_seconds,
            ),
            evidence.locator,
            digest,
            context,
        )

    def _run_probe(self) -> str:
        """Hash bounded stdout only; never return or persist service output."""
        return hash_bounded_stdout(
            BoundedEvidenceProcessRequest(
                command=self.spec.command,
                working_directory=self.spec.working_directory,
                environment=self.spec.environment,
                timeout_seconds=self.spec.timeout_seconds,
                max_output_bytes=self.spec.max_output_bytes,
                label="configured service probe",
                empty_output_message="configured service probe returned no evidence",
            )
        )
