"""Fail-closed host receipt adapters and persisted evidence attestations."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import cast
import unittest

from curatormd_v2 import (
    BrowserProofEvidenceAdapter,
    EvidenceAdapterRegistry,
    EvidenceAdapterPolicy,
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
from curatormd_v2.git_evidence import (
    GitCommitDiffResolver,
    LocalGitTestRunnerResolver,
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
            policy=EvidenceAdapterPolicy(
                allowed_projects=frozenset({"project-a"}),
                allowed_subjects=frozenset({"host-probe:gptmd"}),
            ),
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
                policy=EvidenceAdapterPolicy(
                    allowed_projects=frozenset({"project-a"}),
                    allowed_subjects=frozenset({"host-probe:gptmd"}),
                ),
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
            policy=EvidenceAdapterPolicy(
                allowed_projects={"project-a"},
                allowed_subjects={"host-probe:gptmd"},
            ),
        )

        attestation = adapter.attest(evidence, self.context)

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.source_revision, "git:0123456789abcdef")

    def test_local_git_diff_receipt_hashes_only_configured_immutable_commit_range(self) -> None:
        """Attest exact Git diff bytes without returning or retaining patch text."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()

            def git(*arguments: str) -> str:
                result = subprocess.run(
                    ["git", "-C", str(root), *arguments],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return result.stdout.strip()

            git("init", "--quiet")
            git("config", "user.name", "Curator test")
            git("config", "user.email", "curator-test@example.invalid")
            source = root / "task.txt"
            source.write_text("before\n", encoding="utf-8")
            git("add", "task.txt")
            git("commit", "--quiet", "-m", "base")
            base_revision = git("rev-parse", "HEAD")

            source.write_text("private diff contents\n", encoding="utf-8")
            git("add", "task.txt")
            git("commit", "--quiet", "-m", "change")
            head_revision = git("rev-parse", "HEAD")

            resolver = GitCommitDiffResolver(
                root,
                project_id="project-a",
                source_subject="local-git-runner",
            )
            locator = f"git-diff:{base_revision}..{head_revision}"
            evidence = EvidenceRef(
                "repository_diff", locator, "a" * 64, EvidenceOutcome.PASSED
            )
            context = EvidenceVerificationContext(
                "project-a", "goal-a", "criterion-a", datetime.now(UTC)
            )
            receipt = resolver.resolve(evidence, context)
            self.assertIsNotNone(receipt)
            assert receipt is not None
            raw_diff = subprocess.run(
                [
                    "git", "-C", str(root), "diff", "--binary", "--no-color",
                    "--no-ext-diff", "--no-textconv", "--no-renames",
                    "--diff-algorithm=myers", "--unified=0", base_revision,
                    head_revision, "--",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
            self.assertEqual(receipt.evidence_sha256, hashlib.sha256(raw_diff).hexdigest())
            self.assertNotIn(b"private diff contents", repr(receipt).encode())
            self.assertNotIn(str(root), repr(receipt))

            source.write_text("uncommitted private content\n", encoding="utf-8")
            replayed_receipt = resolver.resolve(evidence, context)
            self.assertIsNotNone(replayed_receipt)
            assert replayed_receipt is not None
            self.assertEqual(
                replayed_receipt.evidence_sha256, receipt.evidence_sha256
            )
            self.assertNotIn(b"uncommitted private content", repr(replayed_receipt).encode())

            adapter = RepositoryEvidenceAdapter(
                adapter_id="local-git-project-a",
                scope_id=resolver.scope_id,
                resolver=resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"local-git-runner"},
                ),
            )
            attestation = adapter.attest(
                replace(evidence, sha256=receipt.evidence_sha256), context
            )
            self.assertIsNotNone(attestation)
            assert attestation is not None
            self.assertEqual(
                attestation.source_revision,
                f"git:{base_revision}..{head_revision}",
            )
            self.assertNotIn(str(root), repr(attestation))

            wrong_project = EvidenceVerificationContext(
                "project-b", "goal-a", "criterion-a", context.now
            )
            self.assertIsNone(
                resolver.resolve(
                    replace(evidence, sha256=receipt.evidence_sha256),
                    wrong_project,
                )
            )

            limited_resolver = GitCommitDiffResolver(
                root,
                project_id="project-a",
                source_subject="local-git-runner",
                max_diff_bytes=1,
            )
            limited_adapter = RepositoryEvidenceAdapter(
                adapter_id="bounded-local-git-project-a",
                scope_id=limited_resolver.scope_id,
                resolver=limited_resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"local-git-runner"},
                ),
            )
            with self.assertRaises(EvidenceAdapterError):
                limited_adapter.attest(
                    replace(evidence, sha256=receipt.evidence_sha256), context
                )

    def test_local_git_test_runner_uses_isolated_exact_commit_checkout(self) -> None:
        """Run a fixed test command at one commit and retain only its digest."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()

            def git(*arguments: str) -> str:
                result = subprocess.run(
                    ["git", "-C", str(root), *arguments],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                return result.stdout.strip()

            git("init", "--quiet")
            git("config", "user.name", "Curator test")
            git("config", "user.email", "curator-test@example.invalid")
            marker = root / "test-marker.txt"
            marker.write_text("pass\n", encoding="utf-8")
            git("add", "test-marker.txt")
            git("commit", "--quiet", "-m", "passing test input")
            revision = git("rev-parse", "HEAD")
            command = (
                sys.executable,
                "-c",
                "from pathlib import Path; value=Path('test-marker.txt').read_text(); "
                "print(value.strip()); raise SystemExit(value != 'pass\\n')",
            )
            resolver = LocalGitTestRunnerResolver(
                root,
                project_id="project-a",
                runner_id="unit-tests",
                source_subject="local-test-runner",
                command=command,
            )
            context = EvidenceVerificationContext(
                "project-a", "goal-a", "criterion-a", datetime.now(UTC)
            )
            evidence = EvidenceRef(
                "repository_test",
                f"git-test:unit-tests:{revision}",
                "a" * 64,
                EvidenceOutcome.PASSED,
            )
            receipt = resolver.resolve(evidence, context)
            self.assertIsNotNone(receipt)
            assert receipt is not None
            self.assertEqual(
                receipt.source_revision, f"git-test:unit-tests:{revision}"
            )
            self.assertNotIn("pass", repr(receipt))
            self.assertNotIn(str(root), repr(receipt))

            marker.write_text("uncommitted failure\n", encoding="utf-8")
            self.assertEqual(resolver.resolve(evidence, context), receipt)

            adapter = RepositoryEvidenceAdapter(
                adapter_id="local-unit-tests",
                scope_id=resolver.scope_id,
                resolver=resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"local-test-runner"},
                ),
            )
            self.assertIsNotNone(
                adapter.attest(replace(evidence, sha256=receipt.evidence_sha256), context)
            )

    def test_local_git_test_runner_rejects_wrong_runner_failure_and_large_output(self) -> None:
        """A nonpassing or unbounded runner result cannot produce an attestation."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Curator test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "curator-test@example.invalid"],
                check=True,
            )
            marker = root / "test-marker.txt"
            marker.write_text("fail\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "test-marker.txt"], check=True
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "--quiet", "-m", "failing input"],
                check=True,
            )
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            command = (
                sys.executable,
                "-c",
                "from pathlib import Path; value=Path('test-marker.txt').read_text(); "
                "raise SystemExit(value != 'pass\\n')",
            )
            resolver = LocalGitTestRunnerResolver(
                root,
                project_id="project-a",
                runner_id="unit-tests",
                source_subject="local-test-runner",
                command=command,
            )
            context = EvidenceVerificationContext(
                "project-a", "goal-a", "criterion-a", datetime.now(UTC)
            )
            wrong_runner = EvidenceRef(
                "repository_test",
                f"git-test:unapproved:{revision}",
                "a" * 64,
                EvidenceOutcome.PASSED,
            )
            self.assertIsNone(resolver.resolve(wrong_runner, context))
            failed_run = replace(
                wrong_runner, locator=f"git-test:unit-tests:{revision}"
            )
            self.assertIsNone(resolver.resolve(failed_run, context))

            limited = LocalGitTestRunnerResolver(
                root,
                project_id="project-a",
                runner_id="unit-tests",
                source_subject="local-test-runner",
                command=(sys.executable, "-c", "print('output too long')"),
                max_output_bytes=8,
            )
            with self.assertRaisesRegex(RuntimeError, "output exceeds"):
                limited.resolve(failed_run, context)

            timed = LocalGitTestRunnerResolver(
                root,
                project_id="project-a",
                runner_id="unit-tests",
                source_subject="local-test-runner",
                command=(
                    sys.executable,
                    "-c",
                    "import subprocess,sys,time; "
                    "subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)']); "
                    "time.sleep(10)",
                ),
                timeout_seconds=1,
            )
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                timed.resolve(failed_run, context)

    def test_source_specific_ttl_cannot_be_relaxed_by_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy ceiling"):
            ServiceProbeEvidenceAdapter(
                adapter_id="gptmd-readiness-probe",
                scope_id="gptmd-api-readiness",
                resolver=self.resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"host-probe:gptmd"},
                    max_observation_age_seconds=61,
                ),
            )
        with self.assertRaisesRegex(ValueError, "revocation age"):
            ServiceProbeEvidenceAdapter(
                adapter_id="gptmd-readiness-probe",
                scope_id="gptmd-api-readiness",
                resolver=self.resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"host-probe:gptmd"},
                    max_revocation_age_seconds=61,
                ),
            )
        with self.assertRaisesRegex(ValueError, "nonnegative integer"):
            ServiceProbeEvidenceAdapter(
                adapter_id="gptmd-readiness-probe",
                scope_id="gptmd-api-readiness",
                resolver=self.resolver,
                policy=EvidenceAdapterPolicy(
                    allowed_projects={"project-a"},
                    allowed_subjects={"host-probe:gptmd"},
                    max_revocation_age_seconds=cast(int, True),
                ),
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
