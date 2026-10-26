"""Capture CLI emits only an owner-scoped browser evidence reference."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from project_fixtures import create_consumer_repo, write_consumer_config
from git_test_support import create_git_commit_range
from evidence_test_support import local_service_probe_config

from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.local_evidence_config import load_local_evidence_verifier
from curatormd_v2.models import EvidenceOutcome, EvidenceRef
from curatormd_v2.evidence_cli import main


class EvidenceCaptureCliTests(unittest.TestCase):
    """Keep browser output content-free and host config outside the consumer."""

    def test_service_probe_capture_emits_a_digest_only_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_root = create_consumer_repo(root / "project")
            write_consumer_config(project_root, "vhost-manager-alpha")
            (project_root / "docs" / "tasks.md").write_text("- [ ] local task\n")
            (project_root / "persistence" / "HISTORY.md").write_text("# History\n")
            host_config = root / "host-evidence.json"
            host_config.write_text(
                json.dumps(
                    local_service_probe_config(
                        source_subject="local-probe:test-host",
                        command=[
                            sys.executable,
                            "-c",
                            "print('PRIVATE_SERVICE_OUTPUT_CANARY')",
                        ],
                        working_directory=str(project_root),
                    )
                ),
                encoding="utf-8",
            )
            host_config.chmod(0o600)
            output = StringIO()
            with patch("sys.stdout", output):
                status = main(
                    [
                        "service-probe",
                        "--project-root",
                        str(project_root),
                        "--host-config",
                        str(host_config),
                    ]
                )

            payload = json.loads(output.getvalue())
            evidence = EvidenceRef(
                payload["evidence_kind"],
                payload["locator"],
                payload["sha256"],
                EvidenceOutcome(payload["outcome"]),
            )
            verifier = load_local_evidence_verifier(
                host_config, project_id="vhost-manager-alpha"
            )
            attestation = verifier.attest(
                evidence,
                EvidenceVerificationContext(
                    "vhost-manager-alpha",
                    "readiness-goal",
                    "service-ready",
                    datetime.now(UTC),
                ),
            )

        self.assertEqual(status, 0)
        self.assertEqual(evidence.evidence_kind, "service_probe")
        self.assertEqual(evidence.locator, "service-probe:readiness")
        self.assertEqual(evidence.outcome, EvidenceOutcome.PASSED)
        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.authenticated_subject, "local-probe:test-host")
        self.assertNotIn("PRIVATE_SERVICE_OUTPUT_CANARY", output.getvalue())

    def test_browser_capture_prints_only_the_compact_evidence_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_root = create_consumer_repo(root / "project")
            write_consumer_config(project_root, "vhost-manager-alpha")
            (project_root / "docs" / "tasks.md").write_text("- [ ] local task\n")
            (project_root / "persistence" / "HISTORY.md").write_text("# History\n")
            browser = root / "system-browser-fixture"
            browser.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "sys.stdout.write('<main>PRIVATE_CAPTURE_CANARY</main>')\n",
                encoding="utf-8",
            )
            browser.chmod(0o700)
            host_config = root / "host-evidence.json"
            host_config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "vhost-manager-alpha",
                        "browser_proof": {
                            "adapter_id": "local-browser",
                            "proof_id": "vhost-home",
                            "url": "http://127.0.0.1:8700/",
                            "executable": str(browser),
                        },
                    }
                ),
                encoding="utf-8",
            )
            host_config.chmod(0o600)
            output = StringIO()
            with patch("sys.stdout", output):
                status = main(
                    [
                        "browser",
                        "--project-root",
                        str(project_root),
                        "--host-config",
                        str(host_config),
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["evidence_kind"], "browser")
        self.assertEqual(payload["locator"], "browser-proof:vhost-home")
        self.assertEqual(payload["outcome"], "passed")
        self.assertNotIn("PRIVATE_CAPTURE_CANARY", output.getvalue())

    def test_repository_capture_commands_emit_only_content_free_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_root = create_consumer_repo(root / "project")
            write_consumer_config(project_root, "vhost-manager-alpha")
            (project_root / "docs" / "tasks.md").write_text("- [ ] local task\n")
            (project_root / "persistence" / "HISTORY.md").write_text("# History\n")
            repository, _, base, head = create_git_commit_range(root)
            host_config = root / "host-evidence.json"
            host_config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "vhost-manager-alpha",
                        "repository_diff": {
                            "adapter_id": "local-diff",
                            "source_subject": "local-git:eaglesvn",
                            "repository_root": str(repository),
                        },
                        "repository_test": {
                            "adapter_id": "local-tests",
                            "runner_id": "unit-tests",
                            "source_subject": "local-git:eaglesvn",
                            "repository_root": str(repository),
                            "command": [
                                sys.executable,
                                "-c",
                                "print('PRIVATE_GIT_TEST_CANARY')",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            host_config.chmod(0o600)

            references: list[dict[str, object]] = []
            for source, options in (
                ("repository-diff", ["--base", base, "--head", head]),
                ("repository-test", ["--runner", "unit-tests", "--commit", head]),
            ):
                output = StringIO()
                with patch("sys.stdout", output):
                    status = main(
                        [
                            source,
                            "--project-root",
                            str(project_root),
                            "--host-config",
                            str(host_config),
                            *options,
                        ]
                    )
                self.assertEqual(status, 0)
                self.assertNotIn("PRIVATE_GIT_TEST_CANARY", output.getvalue())
                references.append(json.loads(output.getvalue()))

        self.assertEqual(references[0]["evidence_kind"], "repository_diff")
        self.assertEqual(references[0]["locator"], f"git-diff:{base}..{head}")
        self.assertEqual(references[1]["evidence_kind"], "repository_test")
        self.assertEqual(references[1]["locator"], f"git-test:unit-tests:{head}")
        self.assertEqual(references[0]["outcome"], "passed")
        self.assertEqual(references[1]["outcome"], "passed")


if __name__ == "__main__":
    unittest.main()
