"""Attended, short-lived human observation receipts for local alpha."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import cast

from .evidence import EvidenceSourceReceipt, EvidenceVerificationContext
from .models import EvidenceOutcome, EvidenceRef
from .private_file_security import require_private_regular_file
from .validation import is_exact_int

MAX_HUMAN_RECEIPT_BYTES = 4096
MAX_HUMAN_OBSERVATION_VALIDITY_SECONDS = 900
_RECEIPT_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class LocalHumanObservationSpec:
    """Host-owned receipt location and the sole local-alpha OS subject."""

    adapter_id: str
    project_id: str
    receipt_directory: Path
    validity_seconds: int = MAX_HUMAN_OBSERVATION_VALIDITY_SECONDS

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.adapter_id):
            raise ValueError("human observation adapter ID is invalid")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.project_id):
            raise ValueError("human observation project ID is invalid")
        if not is_exact_int(self.validity_seconds) or not (
            1 <= self.validity_seconds <= MAX_HUMAN_OBSERVATION_VALIDITY_SECONDS
        ):
            raise ValueError("human observation validity exceeds the 15-minute limit")
        if not self.receipt_directory.is_absolute():
            raise ValueError("human receipt directory must be absolute")

    @property
    def authenticated_subject(self) -> str:
        """Return the effective local OS account as an opaque subject."""

        if not hasattr(os, "geteuid"):
            raise ValueError("local human observation requires an OS identity")
        return f"local-uid:{os.geteuid()}"

    @property
    def scope_id(self) -> str:
        """Return the project-bound local confirmation scope."""

        return f"local-human-observation:{self.project_id}"

    @property
    def source_revision(self) -> str:
        """Identify this local confirmation contract and OS subject."""

        return f"local-human-v1:{self.authenticated_subject}"


def new_human_confirmation_challenge() -> str:
    """Make one short attended-confirmation challenge."""

    return f"CONFIRM HUMAN OBSERVATION {secrets.token_hex(8)}"


def capture_local_human_observation_reference(
    spec: LocalHumanObservationSpec,
    *,
    context: EvidenceVerificationContext,
    challenge: str,
    confirmation: str,
) -> EvidenceRef:
    """Persist only a bounded receipt after an exact attended confirmation."""

    if context.project_id != spec.project_id:
        raise ValueError("human observation project does not match host configuration")
    if (
        not re.fullmatch(r"CONFIRM HUMAN OBSERVATION [0-9a-f]{16}", challenge)
        or not hmac.compare_digest(challenge, confirmation)
    ):
        raise ValueError("human confirmation did not match")

    observed_at = context.now_utc
    receipt_id = secrets.token_hex(16)
    payload = {
        "schema_version": 1,
        "receipt_id": receipt_id,
        "project_id": spec.project_id,
        "goal_id": context.goal_id,
        "criterion_id": context.criterion_id,
        "authenticated_subject": spec.authenticated_subject,
        "observed_at": observed_at.isoformat(timespec="microseconds"),
        "valid_until": (
            observed_at + timedelta(seconds=spec.validity_seconds)
        ).isoformat(timespec="microseconds"),
        "outcome": EvidenceOutcome.PASSED.value,
    }
    serialized = _canonical_json(payload)
    digest = hashlib.sha256(serialized).hexdigest()
    _write_receipt(spec.receipt_directory, receipt_id, serialized)
    return EvidenceRef(
        evidence_kind="human_observation",
        locator=f"human-confirmation:{receipt_id}",
        sha256=digest,
        outcome=EvidenceOutcome.PASSED,
        occurrence_id=receipt_id,
    )


class LocalHumanObservationResolver:
    """Resolve attended receipts from a private, host-owned directory."""

    # pylint: disable=too-few-public-methods  # One-operation source resolver.

    def __init__(self, spec: LocalHumanObservationSpec) -> None:
        self.spec = spec

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Return a receipt only for the exact current project and criterion."""

        match = re.fullmatch(r"human-confirmation:([0-9a-f]{32})", evidence.locator)
        if (
            evidence.evidence_kind != "human_observation"
            or match is None
            or evidence.outcome is not EvidenceOutcome.PASSED
            or evidence.occurrence_id != match.group(1)
            or context.project_id != self.spec.project_id
        ):
            return None
        receipt_id = match.group(1)
        try:
            payload_bytes = _read_receipt(self.spec.receipt_directory, receipt_id)
            payload = _decode_receipt(payload_bytes)
            if hashlib.sha256(_canonical_json(payload)).hexdigest() != evidence.sha256:
                return None
            if not _receipt_matches_context(payload, receipt_id, self.spec, context):
                return None
            observed_at = datetime.fromisoformat(cast(str, payload["observed_at"]))
            valid_until = datetime.fromisoformat(cast(str, payload["valid_until"]))
            now = context.now_utc
            if (
                observed_at.tzinfo is None
                or valid_until.tzinfo is None
                or observed_at > now
                or valid_until <= now
                or now - observed_at > timedelta(seconds=self.spec.validity_seconds)
            ):
                return None
            return EvidenceSourceReceipt(
                evidence_kind=evidence.evidence_kind,
                locator=evidence.locator,
                evidence_sha256=evidence.sha256,
                project_id=context.project_id,
                goal_id=context.goal_id,
                criterion_id=context.criterion_id,
                scope_id=self.spec.scope_id,
                source_revision=self.spec.source_revision,
                authenticated_subject=self.spec.authenticated_subject,
                observed_at=observed_at.isoformat(timespec="microseconds"),
                valid_until=valid_until.isoformat(timespec="microseconds"),
                revocation_checked_at=now.isoformat(timespec="microseconds"),
                revoked=False,
                occurrence_id=receipt_id,
            )
        except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError):
            return None


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload), ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def _open_receipt_directory(path: Path) -> int:
    if not path.is_absolute():
        raise ValueError("human receipt directory must be absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ValueError("human receipt directory is unavailable") from None
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        os.close(descriptor)
        raise ValueError("human receipt directory ownership or mode is invalid")
    return descriptor


def _write_receipt(directory: Path, receipt_id: str, payload: bytes) -> None:
    if len(payload) > MAX_HUMAN_RECEIPT_BYTES:
        raise ValueError("human observation receipt exceeds its byte limit")
    descriptor = _open_receipt_directory(directory)
    name = f"{receipt_id}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        file_descriptor = os.open(name, flags, 0o600, dir_fd=descriptor)
        try:
            with os.fdopen(file_descriptor, "wb", closefd=False) as receipt_file:
                receipt_file.write(payload)
                receipt_file.flush()
                os.fsync(file_descriptor)
        finally:
            os.close(file_descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_receipt(directory: Path, receipt_id: str) -> bytes:
    if not _RECEIPT_ID_RE.fullmatch(receipt_id):
        raise ValueError("human receipt ID is invalid")
    descriptor = _open_receipt_directory(directory)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(f"{receipt_id}.json", flags, dir_fd=descriptor)
        try:
            metadata = os.fstat(file_descriptor)
            require_private_regular_file(
                metadata,
                maximum_bytes=MAX_HUMAN_RECEIPT_BYTES,
                description="human receipt",
            )
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(
                file_descriptor, MAX_HUMAN_RECEIPT_BYTES + 1 - total
            ):
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_HUMAN_RECEIPT_BYTES:
                    raise ValueError("human receipt exceeds its byte limit")
            return b"".join(chunks)
        finally:
            os.close(file_descriptor)
    finally:
        os.close(descriptor)


def _decode_receipt(data: bytes) -> dict[str, object]:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("human receipt contains duplicate fields")
            result[key] = value
        return result

    decoded = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    if not isinstance(decoded, dict):
        raise ValueError("human receipt is malformed")
    payload = cast(dict[str, object], decoded)
    if set(payload) != {
        "schema_version",
        "receipt_id",
        "project_id",
        "goal_id",
        "criterion_id",
        "authenticated_subject",
        "observed_at",
        "valid_until",
        "outcome",
    }:
        raise ValueError("human receipt fields are invalid")
    if not is_exact_int(payload["schema_version"]) or payload["schema_version"] != 1:
        raise ValueError("human receipt version is invalid")
    return payload


def _receipt_matches_context(
    payload: dict[str, object],
    receipt_id: str,
    spec: LocalHumanObservationSpec,
    context: EvidenceVerificationContext,
) -> bool:
    return (
        payload["receipt_id"] == receipt_id
        and payload["project_id"] == context.project_id == spec.project_id
        and payload["goal_id"] == context.goal_id
        and payload["criterion_id"] == context.criterion_id
        and payload["authenticated_subject"] == spec.authenticated_subject
        and payload["outcome"] == EvidenceOutcome.PASSED.value
        and isinstance(payload["observed_at"], str)
        and isinstance(payload["valid_until"], str)
    )
