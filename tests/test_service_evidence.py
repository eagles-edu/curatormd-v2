"""Host-configured service probes produce bounded, content-free receipts."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

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
        reference = adapter.capture(
            "service_probe", "service-probe:vhost-readiness", self.context
        )
        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(
            reference.sha256,
            hashlib.sha256(b"private-output-canary\n").hexdigest(),
        )
        self.assertEqual(reference.outcome, EvidenceOutcome.PASSED)
        self.assertNotIn("private-output-canary", repr(reference))

        attestation = adapter.attest(reference, self.context)

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.evidence_sha256, reference.sha256)
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

    def test_user_systemctl_probe_gets_only_its_derived_user_bus_environment(self) -> None:
        """Keep the restricted child environment while allowing user-unit probes."""

        runtime_root = self.root / "runtime"
        runtime_directory = runtime_root / str(os.getuid())
        runtime_directory.mkdir(parents=True)
        bus_socket = runtime_directory / "bus"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as bus:
            bus.bind(str(bus_socket))
            spec = LocalServiceProbeSpec(
                project_id="vhost-manager-alpha",
                probe_id="user-timer",
                source_subject="local-probe:eaglesvn",
                command=("systemctl", "--user", "is-active", "example.timer"),
                working_directory=self.root,
            )

        with patch("curatormd_v2.service_evidence.USER_RUNTIME_ROOT", runtime_root):
            environment = spec.environment

        self.assertEqual(environment["XDG_RUNTIME_DIR"], str(runtime_directory))
        self.assertEqual(
            environment["DBUS_SESSION_BUS_ADDRESS"],
            f"unix:path={bus_socket}",
        )
        self.assertEqual(set(environment), {
            "PATH",
            "LANG",
            "LC_ALL",
            "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS",
        })

    def test_other_probe_commands_do_not_receive_user_bus_environment(self) -> None:
        """Do not widen the environment for commands that do not need systemd."""

        self.assertEqual(
            set(self.resolver.spec.environment), {"PATH", "LANG", "LC_ALL"}
        )
