"""Bounded host-configured local service probe evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import cast

from .evidence import (
    EvidenceSourceReceipt,
    EvidenceVerificationContext,
    LocalSourceReceiptBinding,
    create_local_source_receipt,
)
from .evidence_process import BoundedEvidenceProcessRequest, hash_bounded_stdout
from .models import EvidenceRef
from .private_file_security import require_private_regular_file
from .validation import is_exact_int

MAX_SERVICE_PROBE_OUTPUT_BYTES = 64 * 1024
MAX_SERVICE_PROBE_TIMEOUT_SECONDS = 30
USER_RUNTIME_ROOT = Path("/run/user")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOCATOR_RE = re.compile(r"^service-probe:([A-Za-z0-9][A-Za-z0-9._:-]{0,127})$")


def _user_systemd_environment(
    command: tuple[str, ...], uid: int
) -> dict[str, str]:
    """Expose only this UID's existing user bus to a configured systemctl probe."""

    if Path(command[0]).name != "systemctl" or "--user" not in command[1:]:
        return {}
    runtime_directory = USER_RUNTIME_ROOT / str(uid)
    bus_socket = runtime_directory / "bus"
    if not runtime_directory.is_dir() or not bus_socket.is_socket():
        return {}
    return {
        "XDG_RUNTIME_DIR": str(runtime_directory),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={bus_socket}",
    }


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
    cache_directory: Path | None = None
    cache_validity_seconds: int = 60
    cache_integrity_files: tuple[Path, ...] = ()

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
        self._validate_cache()
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

    def _validate_cache(self) -> None:
        if not is_exact_int(self.cache_validity_seconds) or not (
            1 <= self.cache_validity_seconds <= 60
        ):
            raise ValueError("service-probe cache validity exceeds the fixed ceiling")
        if self.cache_directory is not None and not self.cache_directory.is_absolute():
            raise ValueError("service-probe cache directory must be absolute")
        if self.cache_directory is not None and (
            not self.cache_integrity_files or len(self.cache_integrity_files) > 16
            or any(not item.is_absolute() for item in self.cache_integrity_files)
        ):
            raise ValueError("cached service probe requires bounded absolute integrity files")
        if self.cache_directory is None and self.cache_integrity_files:
            raise ValueError("service-probe integrity files require a cache directory")

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
            **_user_systemd_environment(self.command, os.geteuid()),
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


class CachedLocalServiceProbeResolver(LocalServiceProbeResolver):
    """Capture a private short-lived receipt before a fenced ledger write."""

    def receipt_path(self, context: EvidenceVerificationContext) -> Path:
        """Resolve the private receipt path for this exact verification context."""
        directory = self.spec.cache_directory
        if directory is None:
            raise ValueError("service-probe cache is not configured")
        metadata = directory.lstat()
        if (not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077):
            raise ValueError("service-probe cache directory is not private")
        key = json.dumps([context.project_id, context.goal_id, context.criterion_id,
                          self.spec.probe_id], separators=(",", ":"))
        return directory / (hashlib.sha256(key.encode()).hexdigest() + ".json")

    def _source_revision(self) -> str:
        digest = hashlib.sha256()
        for source in self.spec.cache_integrity_files:
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1024 * 1024:
                    raise ValueError("cached service-probe source is invalid")
                digest.update(str(source).encode())
                total = 0
                while chunk := os.read(descriptor, 65536):
                    total += len(chunk)
                    if total > 1024 * 1024:
                        raise ValueError("cached service-probe source exceeds its limit")
                    digest.update(chunk)
            finally:
                os.close(descriptor)
        return f"{self.spec.source_revision}:{digest.hexdigest()}"

    def resolve(
        self, evidence: EvidenceRef, context: EvidenceVerificationContext
    ) -> EvidenceSourceReceipt | None:
        """Run the probe on capture; attest only its unexpired exact receipt."""
        if (context.project_id != self.spec.project_id or evidence.evidence_kind != "service_probe"
                or evidence.locator != f"service-probe:{self.spec.probe_id}"):
            return None
        destination = self.receipt_path(context)
        data = (self._capture_receipt(destination, evidence, context)
                if evidence.sha256 == "0" * 64 else self._read_receipt(destination))
        return self._verified_receipt(data, evidence, context) if data is not None else None

    def _capture_receipt(
        self, destination: Path, evidence: EvidenceRef, context: EvidenceVerificationContext
    ) -> dict[str, str]:
        revision = self._source_revision()
        digest = self._run_probe()
        if revision != self._source_revision():
            raise ValueError("cached service-probe source changed during capture")
        observed = context.now_utc
        data = {
            "project_id": context.project_id, "goal_id": context.goal_id,
            "criterion_id": context.criterion_id, "locator": evidence.locator,
            "source_revision": revision, "sha256": digest,
            "observed_at": observed.isoformat(timespec="microseconds"),
            "valid_until": (observed + timedelta(seconds=self.spec.cache_validity_seconds))
                .isoformat(timespec="microseconds"),
        }
        descriptor, name = tempfile.mkstemp(prefix=".probe-", dir=destination.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return data

    @staticmethod
    def _read_receipt(destination: Path) -> dict[str, str] | None:
        try:
            descriptor = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                require_private_regular_file(os.fstat(descriptor), maximum_bytes=4096,
                                             description="service-probe receipt")
                raw: object = json.loads(os.read(descriptor, 4097))
            finally:
                os.close(descriptor)
            if not isinstance(raw, dict):
                return None
            values = cast(dict[str, object], raw)
            if any(not isinstance(value, str) for value in values.values()):
                return None
            return cast(dict[str, str], values)
        except (OSError, ValueError):
            return None

    def _verified_receipt(
        self, data: dict[str, str], evidence: EvidenceRef, context: EvidenceVerificationContext
    ) -> EvidenceSourceReceipt | None:
        expected = {
            "project_id": context.project_id, "goal_id": context.goal_id,
            "criterion_id": context.criterion_id, "locator": evidence.locator,
            "source_revision": self._source_revision(),
        }
        if any(data.get(key) != value for key, value in expected.items()):
            return None
        if evidence.sha256 != "0" * 64 and data.get("sha256") != evidence.sha256:
            return None
        try:
            observed = datetime.fromisoformat(data["observed_at"])
            expires = datetime.fromisoformat(data["valid_until"])
            if (observed.tzinfo is None or expires.tzinfo is None or observed > context.now_utc
                    or expires <= context.now_utc
                    or expires - observed > timedelta(seconds=self.spec.cache_validity_seconds)):
                return None
            return EvidenceSourceReceipt(
                evidence_kind="service_probe", locator=evidence.locator,
                evidence_sha256=data["sha256"], project_id=context.project_id,
                goal_id=context.goal_id, criterion_id=context.criterion_id,
                scope_id=self.spec.scope_id, source_revision=data["source_revision"],
                authenticated_subject=self.spec.source_subject, observed_at=data["observed_at"],
                valid_until=data["valid_until"], revocation_checked_at=context.now_utc.isoformat(),
            )
        except (KeyError, TypeError, ValueError):
            return None
