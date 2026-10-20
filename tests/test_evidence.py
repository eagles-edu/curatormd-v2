"""Fail-closed host receipt adapters and persisted evidence attestations."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
import unittest

from curatormd_v2 import (
    BrowserProofEvidenceAdapter,
    EvidenceAdapterRegistry,
    EvidenceAttestation,
    EvidenceAdapterError,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceSourceReceipt,
    EvidenceVerificationContext,
    HumanObservationEvidenceAdapter,
    RepositoryEvidenceAdapter,
    ServiceProbeEvidenceAdapter,
)


class FixedReceiptResolver:
    """Return one controlled host-side receipt for trust-boundary tests."""

    def __init__(self, receipt: EvidenceSourceReceipt) -> None:
        self.receipt = receipt
        self.raise_error = False
        self.calls = 0

    def resolve(
        self, evidence: EvidenceRef, context: EvidenceVerificationContext
    ) -> EvidenceSourceReceipt:
        """Return the fixed host receipt controlled by this test."""

        del evidence, context
        self.calls += 1
        if self.raise_error:
            raise TimeoutError("private source response must not escape")
        return self.receipt


class EvidenceAdapterTests(unittest.TestCase):
    """Receipts must bind exact proof, project, goal, criterion, and policy."""

    def setUp(self) -> None:
        self.now = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
        self.context = EvidenceVerificationContext(
            "project-a", "goal-a", "criterion-a", self.now
        )
        self.evidence = EvidenceRef(
            "service_probe",
            "service://api/readiness",
            "a" * 64,
            EvidenceOutcome.PASSED,
        )
        self.receipt = EvidenceSourceReceipt(
            evidence_kind="service_probe",
            locator=self.evidence.locator,
            evidence_sha256=self.evidence.sha256,
            project_id=self.context.project_id,
            goal_id=self.context.goal_id,
            criterion_id=self.context.criterion_id,
            scope_id="gptmd-api-readiness",
            source_revision="probe-receipt-42",
            authenticated_subject="host-probe:gptmd",
            observed_at=(self.now - timedelta(seconds=10)).isoformat(),
            valid_until=(self.now + timedelta(seconds=30)).isoformat(),
            revocation_checked_at=(self.now - timedelta(seconds=1)).isoformat(),
        )
        self.resolver = FixedReceiptResolver(self.receipt)
        self.adapter = ServiceProbeEvidenceAdapter(
            adapter_id="gptmd-readiness-probe",
            scope_id="gptmd-api-readiness",
            resolver=self.resolver,
            allowed_projects=frozenset({"project-a"}),
            allowed_subjects=frozenset({"host-probe:gptmd"}),
        )

    def test_service_receipt_creates_exact_compact_attestation(self) -> None:
        attestation = self.adapter.attest(self.evidence, self.context)

        self.assertIsInstance(attestation, EvidenceAttestation)
        assert attestation is not None
        self.assertEqual(attestation.project_id, "project-a")
        self.assertEqual(attestation.goal_id, "goal-a")
        self.assertEqual(attestation.criterion_id, "criterion-a")
        self.assertEqual(attestation.evidence_sha256, "a" * 64)
        self.assertEqual(attestation.adapter_id, "gptmd-readiness-probe")
        self.assertEqual(attestation.source_revision, "probe-receipt-42")
        self.assertEqual(self.resolver.calls, 1)

    def test_rejects_project_goal_criterion_scope_identity_and_digest_mismatch(self) -> None:
        changes = (
            {"project_id": "project-b"},
            {"goal_id": "goal-b"},
            {"criterion_id": "criterion-b"},
            {"scope_id": "other-service"},
            {"authenticated_subject": "caller-asserted-user"},
            {"evidence_sha256": "b" * 64},
            {"locator": "service://other/readiness"},
        )
        for changeset in changes:
            with self.subTest(changes=changeset):
                self.resolver.receipt = replace(self.receipt, **changeset)
                self.assertIsNone(self.adapter.attest(self.evidence, self.context))

    def test_rejects_stale_future_expired_revoked_and_overlong_receipts(self) -> None:
        invalid_receipts = (
            replace(
                self.receipt,
                observed_at=(self.now - timedelta(seconds=61)).isoformat(),
            ),
            replace(
                self.receipt,
                observed_at=(self.now + timedelta(seconds=1)).isoformat(),
            ),
            replace(
                self.receipt,
                valid_until=(self.now - timedelta(seconds=1)).isoformat(),
            ),
            replace(
                self.receipt,
                valid_until=(self.now + timedelta(seconds=61)).isoformat(),
            ),
            replace(self.receipt, revoked=True),
            replace(
                self.receipt,
                revocation_checked_at=(self.now - timedelta(seconds=61)).isoformat(),
            ),
            replace(
                self.receipt,
                revocation_checked_at=(self.now + timedelta(seconds=1)).isoformat(),
            ),
        )
        for receipt in invalid_receipts:
            with self.subTest(receipt=receipt):
                self.resolver.receipt = receipt
                self.assertIsNone(self.adapter.attest(self.evidence, self.context))

    def test_resolver_exception_and_nonpassing_claim_fail_closed(self) -> None:
        self.resolver.raise_error = True
        with self.assertRaises(EvidenceAdapterError) as caught:
            self.adapter.attest(self.evidence, self.context)
        self.assertNotIn("private source response", str(caught.exception))
        self.resolver.raise_error = False
        failed = replace(self.evidence, outcome=EvidenceOutcome.FAILED)
        self.assertIsNone(self.adapter.attest(failed, self.context))

    def test_project_allowlist_and_registry_selection_are_host_owned(self) -> None:
        other_context = replace(self.context, project_id="project-b")
        self.assertIsNone(self.adapter.attest(self.evidence, other_context))
        registry = EvidenceAdapterRegistry((self.adapter,))
        self.assertIsNotNone(registry.attest(self.evidence, self.context))
        unknown = replace(self.evidence, evidence_kind="unknown")
        self.assertIsNone(registry.attest(unknown, self.context))
        with self.assertRaisesRegex(ValueError, "duplicate evidence adapter"):
            EvidenceAdapterRegistry((self.adapter, self.adapter))

    def test_source_receipt_rejects_malformed_or_unbounded_fields(self) -> None:
        """Validate host resolver output before it reaches attestation creation."""

        invalid_fields = (
            {"locator": "x" * 1001},
            {"scope_id": "scope\nforged"},
            {"source_revision": "r" * 257},
            {"authenticated_subject": "subject\tforged"},
            {"evidence_sha256": "G" * 64},
            {"observed_at": "2026-10-18T12:00:00"},
            {"valid_until": "not-a-timestamp"},
            {"revocation_checked_at": "2026-10-18T12:00:00"},
        )
        for changeset in invalid_fields:
            with self.subTest(field=next(iter(changeset))), self.assertRaises(ValueError):
                replace(self.receipt, **changeset)
        with self.assertRaisesRegex(ValueError, "revoked must be a boolean"):
            replace(self.receipt, revoked=cast(bool, 1))

    def test_source_specific_adapters_enforce_short_ttl_ceilings(self) -> None:
        source_specs = (
            (BrowserProofEvidenceAdapter, "browser", "https://gptmd.test", 900),
            (
                HumanObservationEvidenceAdapter,
                "human_observation",
                "human-confirmation",
                86_400,
            ),
        )
        for adapter_type, kind, scope, ceiling in source_specs:
            evidence = replace(self.evidence, evidence_kind=kind)
            receipt = replace(
                self.receipt,
                evidence_kind=kind,
                locator=evidence.locator,
                evidence_sha256=evidence.sha256,
                scope_id=scope,
                observed_at=(self.now - timedelta(seconds=1)).isoformat(),
                valid_until=(self.now + timedelta(seconds=ceiling + 1)).isoformat(),
            )
            resolver = FixedReceiptResolver(receipt)
            adapter = adapter_type(
                adapter_id=f"adapter-{kind}",
                scope_id=scope,
                resolver=resolver,
                allowed_projects=frozenset({"project-a"}),
                allowed_subjects=frozenset({"host-probe:gptmd"}),
            )
            with self.subTest(kind=kind):
                self.assertIsNone(adapter.attest(evidence, self.context))

    def test_revision_bound_repository_receipt_allows_old_immutable_result(self) -> None:
        evidence = replace(self.evidence, evidence_kind="repository_test")
        receipt = replace(
            self.receipt,
            evidence_kind="repository_test",
            locator=evidence.locator,
            evidence_sha256=evidence.sha256,
            scope_id="repo:/srv/gptmd",
            observed_at=(self.now - timedelta(days=365)).isoformat(),
            valid_until=(self.now + timedelta(days=365)).isoformat(),
            source_revision="git:0123456789abcdef",
            revocation_checked_at=(self.now - timedelta(seconds=1)).isoformat(),
        )
        adapter = RepositoryEvidenceAdapter(
            adapter_id="gptmd-test-runner",
            scope_id="repo:/srv/gptmd",
            resolver=FixedReceiptResolver(receipt),
            allowed_projects={"project-a"},
            allowed_subjects={"host-probe:gptmd"},
        )

        attestation = adapter.attest(evidence, self.context)

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.source_revision, "git:0123456789abcdef")

    def test_source_specific_ttl_cannot_be_relaxed_by_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy ceiling"):
            ServiceProbeEvidenceAdapter(
                adapter_id="gptmd-readiness-probe",
                scope_id="gptmd-api-readiness",
                resolver=self.resolver,
                allowed_projects={"project-a"},
                allowed_subjects={"host-probe:gptmd"},
                max_observation_age_seconds=61,
            )
        with self.assertRaisesRegex(ValueError, "revocation age"):
            ServiceProbeEvidenceAdapter(
                adapter_id="gptmd-readiness-probe",
                scope_id="gptmd-api-readiness",
                resolver=self.resolver,
                allowed_projects={"project-a"},
                allowed_subjects={"host-probe:gptmd"},
                max_revocation_age_seconds=61,
            )

    def test_attestation_rejects_naive_or_expired_timestamps(self) -> None:
        values = {
            "evidence_kind": "repository_test",
            "evidence_sha256": "a" * 64,
            "project_id": "project-a",
            "goal_id": "goal-a",
            "criterion_id": "criterion-a",
            "adapter_id": "runner",
            "authenticated_subject": "test-runner:trusted",
            "source_revision": "commit-1",
            "observed_at": self.now.isoformat(),
            "verified_at": self.now.isoformat(),
            "valid_until": (self.now + timedelta(days=1)).isoformat(),
            "revocation_checked_at": self.now.isoformat(),
        }
        EvidenceAttestation(**values)
        with self.assertRaisesRegex(ValueError, "ISO-8601 timestamp") as raised:
            EvidenceAttestation(
                **{**values, "observed_at": "PRIVATE_TIMESTAMP_CANARY"}
            )
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        with self.assertRaisesRegex(ValueError, "timezone"):
            EvidenceAttestation(**{**values, "observed_at": "2026-10-18T12:00:00"})
        with self.assertRaisesRegex(ValueError, "remain valid"):
            EvidenceAttestation(**{**values, "valid_until": self.now.isoformat()})


if __name__ == "__main__":
    unittest.main()
