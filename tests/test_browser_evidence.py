"""Local system-browser proof remains bounded, scoped, and content-free."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

from curatormd_v2 import (
    BrowserProofEvidenceAdapter,
    EvidenceAdapterPolicy,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    LocalBrowserProofResolver,
    LocalBrowserProofSpec,
)


class LocalBrowserProofTests(unittest.TestCase):
    """Use a disposable executable instead of relying on a downloaded browser."""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.temporary = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.executable = self.root / "system-browser-fixture"
        self._write_browser("<main>PRIVATE_BROWSER_CANARY</main>")

    def _write_browser(self, output: str, *, delay: float = 0) -> None:
        script = (
            f"#!{sys.executable}\n"
            "import sys\n"
            "import time\n"
            f"time.sleep({delay!r})\n"
            f"sys.stdout.write({output!r})\n"
        )
        self.executable.write_text(script, encoding="utf-8")
        self.executable.chmod(0o700)

    def _spec(
        self, *, timeout: int = 5, output_limit: int = 1024
    ) -> LocalBrowserProofSpec:
        return LocalBrowserProofSpec(
            project_id="vhost-manager-alpha",
            proof_id="vhost-home",
            url="http://127.0.0.1:8700/",
            executable=str(self.executable),
            timeout_seconds=timeout,
            max_output_bytes=output_limit,
        )

    def test_capture_reference_is_reverified_by_browser_adapter_without_content(self) -> None:
        resolver = LocalBrowserProofResolver(self._spec())
        evidence = resolver.capture_reference()
        self.assertEqual(evidence.sha256, hashlib.sha256(
            b"<main>PRIVATE_BROWSER_CANARY</main>"
        ).hexdigest())
        self.assertNotIn("PRIVATE_BROWSER_CANARY", repr(evidence))

        adapter = BrowserProofEvidenceAdapter(
            adapter_id="local-vhost-browser",
            scope_id=self._spec().scope_id,
            resolver=resolver,
            policy=EvidenceAdapterPolicy(
                allowed_projects={"vhost-manager-alpha"},
                allowed_subjects={self._spec().source_subject},
                max_observation_age_seconds=900,
                max_validity_seconds=900,
            ),
        )
        attestation = adapter.attest(
            evidence,
            EvidenceVerificationContext(
                project_id="vhost-manager-alpha",
                goal_id="browser-goal",
                criterion_id="rendered",
                now=datetime.now(UTC),
            ),
        )

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.authenticated_subject, self._spec().source_subject)
        self.assertEqual(attestation.source_revision, self._spec().source_revision)
        self.assertNotIn("PRIVATE_BROWSER_CANARY", repr(attestation))

    def test_rejects_external_or_credential_bearing_urls(self) -> None:
        for url in (
            "https://example.invalid/",
            "http://user:password@localhost/",
            "http://localhost/private?token=secret",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "loopback|credentials"):
                    LocalBrowserProofSpec(
                        project_id="vhost-manager-alpha",
                        proof_id="vhost-home",
                        url=url,
                        executable=str(self.executable),
                    )

    def test_rejects_wrong_project_and_proof_without_starting_browser(self) -> None:
        evidence = LocalBrowserProofResolver(self._spec()).capture_reference()
        resolver = LocalBrowserProofResolver(self._spec())
        self.assertIsNone(
            resolver.resolve(
                evidence,
                EvidenceVerificationContext(
                    project_id="other-project",
                    goal_id="browser-goal",
                    criterion_id="rendered",
                    now=datetime.now(UTC),
                ),
            )
        )
        wrong_proof = EvidenceRef(
            evidence_kind="browser",
            locator="browser-proof:other",
            sha256=evidence.sha256,
            outcome=EvidenceOutcome.PASSED,
        )
        self.assertIsNone(
            resolver.resolve(
                wrong_proof,
                EvidenceVerificationContext(
                    project_id="vhost-manager-alpha",
                    goal_id="browser-goal",
                    criterion_id="rendered",
                    now=datetime.now(UTC),
                ),
            )
        )

    def test_enforces_output_and_runtime_limits(self) -> None:
        self._write_browser("x" * 1025)
        with self.assertRaisesRegex(RuntimeError, "output exceeded its limit"):
            LocalBrowserProofResolver(self._spec(output_limit=1024)).capture_reference()

        self._write_browser("<main>ready</main>", delay=2)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            LocalBrowserProofResolver(self._spec(timeout=1)).capture_reference()


if __name__ == "__main__":
    unittest.main()
