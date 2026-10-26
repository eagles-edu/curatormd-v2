"""Local system-browser proof for loopback-only alpha checks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from .evidence import (
    EvidenceSourceReceipt,
    EvidenceVerificationContext,
    LocalSourceReceiptBinding,
    create_local_source_receipt,
)
from .evidence_process import BoundedEvidenceProcessRequest, hash_bounded_stdout
from .models import EvidenceOutcome, EvidenceRef
from .validation import is_exact_int

MAX_BROWSER_PROOF_OUTPUT_BYTES = 1024 * 1024
MAX_BROWSER_PROOF_TIMEOUT_SECONDS = 30
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LOCATOR_RE = re.compile(r"^browser-proof:([A-Za-z0-9][A-Za-z0-9._:-]{0,127})$")


def _loopback_url(value: str) -> tuple[str, str]:
    """Accept one credential-free loopback URL without query or fragment data."""

    if len(value) > 450 or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("browser proof URL must be bounded single-line text")
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError:
        raise ValueError("browser proof URL has an invalid port") from None
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("browser proof URL must be a credential-free loopback URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("browser proof URL must not contain credentials")
    if parsed.query or parsed.fragment or not parsed.path.startswith("/"):
        raise ValueError("browser proof URL must be a credential-free loopback URL")
    hostname = parsed.hostname.lower()
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname == "localhost"
    if not is_loopback:
        raise ValueError("browser proof URL must use a loopback host")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return value, origin


@dataclass(frozen=True, slots=True)
class LocalBrowserProofSpec:
    """Owner-selected system browser and one exact local route."""

    project_id: str
    proof_id: str
    url: str
    executable: str = "google-chrome"
    timeout_seconds: int = 20
    max_output_bytes: int = MAX_BROWSER_PROOF_OUTPUT_BYTES

    def __post_init__(self) -> None:
        for name, value in (("project_id", self.project_id), ("proof_id", self.proof_id)):
            if not _IDENTIFIER_RE.fullmatch(value):
                raise ValueError(f"{name} must be a bounded opaque identifier")
        normalized_url, origin = _loopback_url(self.url)
        del origin
        if not self.executable or len(self.executable) > 4096:
            raise ValueError("browser executable must be bounded host configuration")
        executable = shutil.which(self.executable)
        if executable is None:
            raise ValueError("configured system browser is unavailable")
        if not is_exact_int(self.timeout_seconds) or not (
            1 <= self.timeout_seconds <= MAX_BROWSER_PROOF_TIMEOUT_SECONDS
        ):
            raise ValueError("browser proof timeout exceeds the local ceiling")
        if not is_exact_int(self.max_output_bytes) or not (
            1 <= self.max_output_bytes <= MAX_BROWSER_PROOF_OUTPUT_BYTES
        ):
            raise ValueError("browser proof output exceeds the local ceiling")
        object.__setattr__(self, "url", normalized_url)
        object.__setattr__(self, "executable", executable)

    @property
    def scope_id(self) -> str:
        """Return the exact route scope without query strings or credentials."""

        return f"local-browser-proof:{self.proof_id}:{self.url}"

    @property
    def source_subject(self) -> str:
        """Return the kernel-reported local account that launches Chrome."""

        if not hasattr(os, "geteuid"):
            raise RuntimeError("local browser proof requires an effective OS identity")
        return f"local-uid:{os.geteuid()}"

    @property
    def source_revision(self) -> str:
        """Identify the configured browser binary, route, and runner limits."""

        stat_result = Path(self.executable).stat()
        payload = json.dumps(
            {
                "executable": self.executable,
                "device": stat_result.st_dev,
                "inode": stat_result.st_ino,
                "size": stat_result.st_size,
                "mtime_ns": stat_result.st_mtime_ns,
                "url": self.url,
                "timeout_seconds": self.timeout_seconds,
                "max_output_bytes": self.max_output_bytes,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"local-browser:{self.proof_id}:{hashlib.sha256(payload).hexdigest()}"


class LocalBrowserProofResolver:
    """Render one host-configured loopback route and retain only its DOM digest."""

    def __init__(self, spec: LocalBrowserProofSpec) -> None:
        self.spec = spec

    def capture_reference(self) -> EvidenceRef:
        """Capture a compact reference that the caller can attach to a criterion."""

        return EvidenceRef(
            evidence_kind="browser",
            locator=f"browser-proof:{self.spec.proof_id}",
            sha256=self._rendered_dom_sha256(),
            outcome=EvidenceOutcome.PASSED,
        )

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Rerender and return a receipt only for this configured project/proof."""

        match = _LOCATOR_RE.fullmatch(evidence.locator)
        if (
            context.project_id != self.spec.project_id
            or evidence.evidence_kind != "browser"
            or match is None
            or match.group(1) != self.spec.proof_id
        ):
            return None
        return create_local_source_receipt(
            LocalSourceReceiptBinding(
                evidence_kind="browser",
                scope_id=self.spec.scope_id,
                source_revision=self.spec.source_revision,
                authenticated_subject=self.spec.source_subject,
                validity_seconds=900,
            ),
            evidence.locator,
            self._rendered_dom_sha256(),
            context,
        )

    def _rendered_dom_sha256(self) -> str:
        """Hash bounded Chrome DOM output without returning or saving its contents."""

        with tempfile.TemporaryDirectory(prefix="curator-v2-browser-") as profile:
            command = (
                self.spec.executable,
                "--headless=new",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=5000",
                f"--timeout={self.spec.timeout_seconds * 1000}",
                "--dump-dom",
                self.spec.url,
            )
            return hash_bounded_stdout(
                BoundedEvidenceProcessRequest(
                    command=command,
                    working_directory=Path(profile),
                    environment={
                        "PATH": os.path.dirname(command[0]),
                        "LANG": "C",
                        "LC_ALL": "C",
                    },
                    timeout_seconds=self.spec.timeout_seconds,
                    max_output_bytes=self.spec.max_output_bytes,
                    label="configured browser proof",
                    empty_output_message=(
                        "configured browser proof returned no rendered DOM"
                    ),
                )
            )
