"""Test-only trusted evidence receipts; never import from runtime code."""

from datetime import timedelta
from typing import cast

from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.models import EvidenceAttestation, EvidenceRef


def attest_test_evidence(
    evidence: EvidenceRef,
    context: EvidenceVerificationContext,
) -> EvidenceAttestation:
    """Create deterministic scoped provenance for an accepted test reference."""

    now = context.now
    fields = {
        "evidence_kind": evidence.evidence_kind,
        "evidence_sha256": evidence.sha256,
        "project_id": context.project_id,
        "goal_id": context.goal_id,
        "criterion_id": context.criterion_id,
        "adapter_id": "test-fixture",
        "authenticated_subject": "unit-test-runner",
        "source_revision": f"test-receipt:{evidence.locator}",
        "observed_at": now.isoformat(timespec="microseconds"),
        "verified_at": now.isoformat(timespec="microseconds"),
        "valid_until": (now + timedelta(days=1)).isoformat(timespec="microseconds"),
        "revocation_checked_at": now.isoformat(timespec="microseconds"),
        "occurrence_id": evidence.occurrence_id,
    }
    return EvidenceAttestation(**cast(dict[str, str], fields))
