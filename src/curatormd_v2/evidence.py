"""Fail-closed evidence adapters and compact verification attestations.

The host owns adapter construction, credentials, project allowlists, and source
resolvers. Event/MCP callers can provide only an :class:`EvidenceRef`; they
cannot provide a receipt, identity, or adapter policy.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Protocol

from .content_safety import validate_safe_text
from .models import EvidenceAttestation, EvidenceOutcome, EvidenceRef
from .validation import is_exact_bool, is_exact_int


def _valid_identifier(value: object, limit: int) -> bool:
    """Check a runtime value against bounded single-line identifier rules."""

    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= limit
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def _aware_datetime(value: object) -> bool:
    """Return whether an untrusted runtime value is a timezone-aware datetime."""

    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


@dataclass(frozen=True, slots=True)
class EvidenceVerificationContext:
    """Host-bound scope and clock for one criterion verification attempt."""

    project_id: str
    goal_id: str
    criterion_id: str
    now: datetime

    def __post_init__(self) -> None:
        for name, value in (
            ("project_id", self.project_id),
            ("goal_id", self.goal_id),
            ("criterion_id", self.criterion_id),
        ):
            if not _valid_identifier(value, 128):
                raise ValueError(f"{name} must be a bounded single-line identifier")
        if not _aware_datetime(self.now):
            raise ValueError("verification clock must be timezone-aware")

    @property
    def now_utc(self) -> datetime:
        """Return the trusted host time normalized to UTC."""

        return self.now.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class EvidenceSourceReceipt:
    """Typed, bounded result returned by a host-authenticated source resolver."""

    evidence_kind: str
    locator: str
    evidence_sha256: str
    project_id: str
    goal_id: str
    criterion_id: str
    scope_id: str
    source_revision: str
    authenticated_subject: str
    observed_at: str
    valid_until: str
    revocation_checked_at: str
    revoked: bool = False

    def __post_init__(self) -> None:
        """Reject malformed or oversized resolver output at its typed boundary."""

        for name, value, limit in (
            ("evidence_kind", self.evidence_kind, 64),
            ("locator", self.locator, 1000),
            ("project_id", self.project_id, 128),
            ("goal_id", self.goal_id, 128),
            ("criterion_id", self.criterion_id, 128),
            ("scope_id", self.scope_id, 500),
            ("source_revision", self.source_revision, 256),
            ("authenticated_subject", self.authenticated_subject, 128),
        ):
            if not _valid_identifier(value, limit):
                raise ValueError(f"evidence receipt {name} must be bounded single-line text")
            validate_safe_text(value, f"evidence_receipt.{name}")
        if type(self.evidence_sha256) is not str or not re.fullmatch(  # pylint: disable=unidiomatic-typecheck
            r"[0-9a-f]{64}", self.evidence_sha256
        ):
            raise ValueError("evidence receipt digest must be 64 lowercase hex characters")
        for name, value in (
            ("observed_at", self.observed_at),
            ("valid_until", self.valid_until),
            ("revocation_checked_at", self.revocation_checked_at),
        ):
            if _parse_time(value) is None:
                raise ValueError(f"evidence receipt {name} must be a timezone-aware timestamp")
        if not is_exact_bool(self.revoked):
            raise ValueError("evidence receipt revoked must be a boolean")


class EvidenceSourceResolver(Protocol):
    """Resolve evidence through credentials and identity owned by the host."""

    def resolve(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceSourceReceipt | None:
        """Return a trusted source receipt, or ``None`` when unavailable."""
        ...


class EvidenceVerifier(Protocol):
    """Verify a reference and return provenance suitable for immutable storage."""

    def attest(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceAttestation | None:
        """Return a current attestation only when all trust checks pass."""
        ...


class EvidenceAdapterError(RuntimeError):
    """A trusted evidence adapter failed operationally, without source detail."""


class RejectUnverifiedEvidence:
    """Safe default until trusted source adapters are explicitly configured."""

    def attest(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceAttestation | None:
        """Reject every reference without consulting caller-controlled metadata."""

        del evidence, context


def _parse_time(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp only when it carries an explicit timezone."""

    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


class ReceiptEvidenceAdapter:
    """Validate host-authenticated receipts for one configured evidence scope.

    The resolver is the host trust root: it must authenticate the source and
    check current revocation state. This class independently enforces exact
    evidence, goal, criterion, project, scope, freshness, expiry, and subject
    binding before emitting a persistable attestation.
    """

    evidence_kinds: frozenset[str] = frozenset()
    max_observation_age_ceiling_seconds: int | None = None
    max_validity_ceiling_seconds: int | None = None

    def __init__(
        self,
        *,
        adapter_id: str,
        scope_id: str,
        resolver: EvidenceSourceResolver,
        allowed_projects: Collection[str],
        allowed_subjects: Collection[str],
        max_observation_age_seconds: int | None = None,
        max_validity_seconds: int | None = None,
        max_revocation_age_seconds: int = 60,
    ) -> None:
        if not adapter_id.strip() or len(adapter_id) > 128:
            raise ValueError("adapter_id must contain 1-128 characters")
        if not scope_id.strip() or len(scope_id) > 500:
            raise ValueError("scope_id must contain 1-500 characters")
        projects = frozenset(allowed_projects)
        subjects = frozenset(allowed_subjects)
        if not projects or not subjects:
            raise ValueError("trusted adapters require project and subject allowlists")
        for value in projects | subjects:
            if not _valid_identifier(value, 128):
                raise ValueError("adapter allowlists cannot contain empty values")
        for name, value in (
            ("max_observation_age_seconds", max_observation_age_seconds),
            ("max_validity_seconds", max_validity_seconds),
            ("max_revocation_age_seconds", max_revocation_age_seconds),
        ):
            if value is not None and (not is_exact_int(value) or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer or None")
        if max_revocation_age_seconds > 60:
            raise ValueError("max revocation age exceeds the 60-second policy ceiling")
        observation_ceiling = type(self).max_observation_age_ceiling_seconds
        validity_ceiling = type(self).max_validity_ceiling_seconds
        if observation_ceiling is not None:
            if max_observation_age_seconds is None:
                max_observation_age_seconds = observation_ceiling
            elif max_observation_age_seconds > observation_ceiling:
                raise ValueError("max observation age exceeds source policy ceiling")
        if validity_ceiling is not None:
            if max_validity_seconds is None:
                max_validity_seconds = validity_ceiling
            elif max_validity_seconds > validity_ceiling:
                raise ValueError("max validity exceeds source policy ceiling")
        self.adapter_id = adapter_id
        self.scope_id = scope_id
        self.resolver = resolver
        self.allowed_projects = projects
        self.allowed_subjects = subjects
        self.max_observation_age_seconds = max_observation_age_seconds
        self.max_validity_seconds = max_validity_seconds
        self.max_revocation_age_seconds = max_revocation_age_seconds

    def attest(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceAttestation | None:
        """Resolve and validate one proof, failing closed on all adapter faults."""

        if (
            evidence.outcome is not EvidenceOutcome.PASSED
            or evidence.evidence_kind not in self.evidence_kinds
            or context.project_id not in self.allowed_projects
        ):
            return None
        try:
            receipt = self.resolver.resolve(evidence, context)
            if not isinstance(receipt, EvidenceSourceReceipt):
                return None
            now = context.now_utc
            if not self._receipt_matches_binding(receipt, evidence, context):
                return None
            if not self._receipt_times_are_current(receipt, now):
                return None
            return EvidenceAttestation(
                evidence_kind=evidence.evidence_kind,
                evidence_sha256=evidence.sha256,
                project_id=context.project_id,
                goal_id=context.goal_id,
                criterion_id=context.criterion_id,
                adapter_id=self.adapter_id,
                authenticated_subject=receipt.authenticated_subject,
                source_revision=receipt.source_revision,
                observed_at=receipt.observed_at,
                verified_at=now.isoformat(timespec="microseconds"),
                valid_until=receipt.valid_until,
                revocation_checked_at=receipt.revocation_checked_at,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            # Distinguish a broken trusted adapter from an ordinary bad proof,
            # but never expose the resolver's exception or message.
            raise EvidenceAdapterError() from None

    def _receipt_matches_binding(
        self,
        receipt: EvidenceSourceReceipt,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> bool:
        """Match a resolved receipt to its exact proof and host-owned scope."""

        return not any(
            (
                receipt.evidence_kind != evidence.evidence_kind,
                receipt.locator != evidence.locator,
                receipt.evidence_sha256 != evidence.sha256,
                receipt.project_id != context.project_id,
                receipt.goal_id != context.goal_id,
                receipt.criterion_id != context.criterion_id,
                receipt.scope_id != self.scope_id,
                receipt.authenticated_subject not in self.allowed_subjects,
            )
        )

    def _receipt_times_are_current(
        self, receipt: EvidenceSourceReceipt, now: datetime
    ) -> bool:
        """Enforce revocation, freshness, expiry, and source age ceilings."""

        observed_at = _parse_time(receipt.observed_at)
        valid_until = _parse_time(receipt.valid_until)
        revocation_checked_at = _parse_time(receipt.revocation_checked_at)
        if (
            observed_at is None
            or valid_until is None
            or revocation_checked_at is None
            or not is_exact_bool(receipt.revoked)
            or receipt.revoked
        ):
            return False
        if any(
            (
                observed_at > now,
                revocation_checked_at > now,
                valid_until <= now,
                revocation_checked_at < observed_at,
                now - revocation_checked_at
                > timedelta(seconds=self.max_revocation_age_seconds),
            )
        ):
            return False
        if self.max_observation_age_seconds is not None and (
            now - observed_at > timedelta(seconds=self.max_observation_age_seconds)
        ):
            return False
        if self.max_validity_seconds is not None and (
            valid_until - observed_at > timedelta(seconds=self.max_validity_seconds)
        ):
            return False
        return True


class RepositoryEvidenceAdapter(ReceiptEvidenceAdapter):
    """Adapter for immutable repository-diff and test-run receipts."""

    evidence_kinds = frozenset({"repository_diff", "repository_test"})


class ServiceProbeEvidenceAdapter(ReceiptEvidenceAdapter):
    """Adapter for short-lived host-authenticated service health probes."""

    evidence_kinds = frozenset({"service_probe"})
    max_observation_age_ceiling_seconds = 60
    max_validity_ceiling_seconds = 60


class BrowserProofEvidenceAdapter(ReceiptEvidenceAdapter):
    """Adapter for origin-bound browser receipts with a short session window."""

    evidence_kinds = frozenset({"browser"})
    max_observation_age_ceiling_seconds = 900
    max_validity_ceiling_seconds = 900


class HumanObservationEvidenceAdapter(ReceiptEvidenceAdapter):
    """Adapter for explicit, authenticated human confirmations."""

    evidence_kinds = frozenset({"human_observation"})
    max_observation_age_ceiling_seconds = 86_400
    max_validity_ceiling_seconds = 86_400


class EvidenceAdapterRegistry:
    """Fixed host-created adapter map; evidence callers cannot register adapters."""

    def __init__(self, adapters: tuple[ReceiptEvidenceAdapter, ...]) -> None:
        by_kind: dict[str, ReceiptEvidenceAdapter] = {}
        for adapter in adapters:
            for kind in adapter.evidence_kinds:
                if kind in by_kind:
                    raise ValueError(f"duplicate evidence adapter for kind: {kind}")
                by_kind[kind] = adapter
        self._by_kind = by_kind

    def attest(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceAttestation | None:
        """Route only to the adapter registered by the trusted host."""

        adapter = self._by_kind.get(evidence.evidence_kind)
        if adapter is None:
            return None
        return adapter.attest(evidence, context)


def evidence_has_current_attestations(
    verifier: EvidenceVerifier,
    *,
    project_id: str,
    goal_id: str,
    criterion_id: str,
    evidence: tuple[EvidenceRef, ...],
    stored: tuple[EvidenceAttestation, ...],
    now: datetime | None = None,
) -> bool:
    """Revalidate provenance outside write transactions and reject drift."""

    if not evidence or len(evidence) != len(stored):
        return False
    context = EvidenceVerificationContext(
        project_id=project_id,
        goal_id=goal_id,
        criterion_id=criterion_id,
        now=now or datetime.now(UTC),
    )
    try:
        fresh_items = tuple(verifier.attest(item, context) for item in evidence)
    except Exception:  # pylint: disable=broad-exception-caught
        raise EvidenceAdapterError() from None
    if any(item is None for item in fresh_items):
        return False
    for reference, current, original in zip(
        evidence,
        (item for item in fresh_items if item is not None),
        stored,
        strict=True,
    ):
        if (
            current.evidence_kind != reference.evidence_kind
            or current.evidence_sha256 != reference.sha256
            or current.project_id != project_id
            or current.goal_id != goal_id
            or current.criterion_id != criterion_id
            or original.evidence_kind != reference.evidence_kind
            or original.evidence_sha256 != reference.sha256
            or original.project_id != project_id
            or original.goal_id != goal_id
            or original.criterion_id != criterion_id
            or current.source_revision != original.source_revision
            or current.adapter_id != original.adapter_id
            or current.authenticated_subject != original.authenticated_subject
        ):
            return False
    return True
