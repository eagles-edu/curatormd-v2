"""Host-configured service probes produce bounded, content-free receipts."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

from curatormd_v2 import (
    EvidenceAdapterPolicy,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    LocalServiceProbeResolver,
    LocalServiceProbeSpec,
    ServiceProbeEvidenceAdapter,
)


class LocalServiceProbeResolverTests(unittest.TestCase):
    """Probe identity and execution are host-owned and bounded."""

    def setUp(self) -> None:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(temporary)
        self.now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        self.context = EvidenceVerificationContext(
            "vhost-manager-alpha", "goal-alpha", "service-ready", self.now
        )
        self.resolver = self._resolver("print('private-output-canary')")

    def _resolver(
        self,
        source: str,
        *,
        output_limit: int = 1024,
        timeout: int = 3,
    ) -> LocalServiceProbeResolver:
        return LocalServiceProbeResolver(
            LocalServiceProbeSpec(
                project_id="vhost-manager-alpha",
                probe_id="vhost-readiness",
                source_subject="local-probe:eaglesvn",
                command=(sys.executable, "-c", source),
                working_directory=self.root,
                max_output_bytes=output_limit,
                timeout_seconds=timeout,
            )
        )

    def _evidence(
        self, digest: str, locator: str = "service-probe:vhost-readiness"
    ) -> EvidenceRef:
        return EvidenceRef("service_probe", locator, digest, EvidenceOutcome.PASSED)

    def test_probe_attests_exact_host_output_without_retaining_it(self) -> None:
        first = self.resolver.resolve(self._evidence("0" * 64), self.context)

        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(
            first.evidence_sha256,
            hashlib.sha256(b"private-output-canary\n").hexdigest(),
        )
        self.assertEqual(first.project_id, "vhost-manager-alpha")
        self.assertEqual(first.goal_id, "goal-alpha")
        self.assertEqual(first.criterion_id, "service-ready")
        self.assertEqual(first.scope_id, "local-service-probe:vhost-readiness")
        self.assertEqual(first.authenticated_subject, "local-probe:eaglesvn")
        self.assertNotIn("private-output-canary", repr(first))

        adapter = ServiceProbeEvidenceAdapter(
            adapter_id="vhost-local-readiness",
            scope_id=self.resolver.spec.scope_id,
            resolver=self.resolver,
            policy=EvidenceAdapterPolicy(
                allowed_projects={"vhost-manager-alpha"},
                allowed_subjects={"local-probe:eaglesvn"},
                max_observation_age_seconds=30,
                max_validity_seconds=30,
            ),
        )
        attestation = adapter.attest(self._evidence(first.evidence_sha256), self.context)

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.evidence_sha256, first.evidence_sha256)
        self.assertEqual(attestation.adapter_id, "vhost-local-readiness")

    def test_wrong_project_or_probe_locator_does_not_execute_probe(self) -> None:
        wrong_project = EvidenceVerificationContext(
            "other-project", "goal-alpha", "service-ready", self.now
        )
        self.assertIsNone(self.resolver.resolve(self._evidence("0" * 64), wrong_project))
        self.assertIsNone(
            self.resolver.resolve(
                self._evidence("0" * 64, "service-probe:other"), self.context
            )
        )

    def test_failed_timed_out_and_oversized_probes_fail_closed(self) -> None:
        failed = self._resolver("raise SystemExit(4)")
        timed_out = self._resolver("import time; time.sleep(5)", timeout=1)
        oversized = self._resolver("print('x' * 2000)", output_limit=32)

        for resolver in (failed, timed_out, oversized):
            with self.subTest(resolver=resolver), self.assertRaises(RuntimeError):
                resolver.resolve(self._evidence("0" * 64), self.context)

    def test_probe_command_is_not_interpolated_from_evidence(self) -> None:
        evidence = self._evidence(
            "0" * 64, "service-probe:vhost-readiness;touch /tmp/not-run"
        )

        self.assertIsNone(self.resolver.resolve(evidence, self.context))
