"""Local human confirmations are attended, scoped, short-lived, and revocable."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from io import StringIO
import tempfile
import unittest
from unittest.mock import patch

from project_fixtures import create_consumer_repo, write_consumer_config

from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.evidence_cli import main
from curatormd_v2.human_observation import new_human_confirmation_challenge
from curatormd_v2.local_evidence_config import (
    capture_local_human_observation_reference,
    load_local_evidence_verifier,
)
from curatormd_v2.models import EvidenceRef


class _TerminalInput(StringIO):
    def isatty(self) -> bool:
        return True


class _TerminalOutput(StringIO):
    def isatty(self) -> bool:
        return True


class HumanObservationTests(unittest.TestCase):
    """Exercise the single-user local confirmation path without retaining text."""

    def setUp(self) -> None:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(temporary)
        self.project_root = create_consumer_repo(self.root / "project")
        write_consumer_config(self.project_root, "vhost-manager-alpha")
        (self.project_root / "docs" / "tasks.md").write_text(
            "- [ ] local task\n", encoding="utf-8"
        )
        (self.project_root / "persistence" / "HISTORY.md").write_text(
            "# History\n", encoding="utf-8"
        )
        self.receipt_directory = self.root / "receipts"
        self.receipt_directory.mkdir(mode=0o700)
        self.config = self.root / "host-evidence.json"
        self._write_config()

    def _write_config(self, extra: dict[str, object] | None = None) -> None:
        document: dict[str, object] = {
            "schema_version": 1,
            "project_id": "vhost-manager-alpha",
            "human_observation": {
                "adapter_id": "local-human-review",
                "receipt_directory": str(self.receipt_directory),
                "validity_seconds": 900,
            },
        }
        if extra:
            document.update(extra)
        self.config.write_text(json.dumps(document), encoding="utf-8")
        self.config.chmod(0o600)

    def _capture(self, *, confirmation: str | None = None) -> EvidenceRef:
        challenge = new_human_confirmation_challenge()
        return capture_local_human_observation_reference(
            self.config,
            context=self._context(now=datetime.now(UTC)),
            challenge=challenge,
            confirmation=challenge if confirmation is None else confirmation,
        )

    def _context(
        self,
        *,
        project_id: str = "vhost-manager-alpha",
        goal_id: str = "goal-alpha",
        criterion_id: str = "criterion-alpha",
        now: datetime | None = None,
    ) -> EvidenceVerificationContext:
        return EvidenceVerificationContext(
            project_id=project_id,
            goal_id=goal_id,
            criterion_id=criterion_id,
            now=now or datetime.now(UTC) + timedelta(milliseconds=50),
        )

    def test_receipt_attests_exact_project_goal_criterion_and_os_subject(self) -> None:
        reference = self._capture()
        verifier = load_local_evidence_verifier(
            self.config, project_id="vhost-manager-alpha"
        )

        attestation = verifier.attest(reference, self._context())

        self.assertIsNotNone(attestation)
        assert attestation is not None
        self.assertEqual(attestation.authenticated_subject, f"local-uid:{os.geteuid()}")
        self.assertEqual(attestation.goal_id, "goal-alpha")
        self.assertEqual(attestation.criterion_id, "criterion-alpha")
        self.assertIsNone(
            verifier.attest(reference, self._context(goal_id="other-goal"))
        )
        self.assertIsNone(
            verifier.attest(reference, self._context(criterion_id="other-criterion"))
        )
        self.assertIsNone(
            verifier.attest(reference, self._context(project_id="other-project"))
        )

    def test_mismatch_and_receipt_deletion_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not match"):
            self._capture(confirmation="wrong confirmation")
        self.assertEqual(list(self.receipt_directory.iterdir()), [])

        reference = self._capture()
        receipt_path = self.receipt_directory / f"{reference.occurrence_id}.json"
        receipt_path.unlink()
        verifier = load_local_evidence_verifier(
            self.config, project_id="vhost-manager-alpha"
        )
        self.assertIsNone(verifier.attest(reference, self._context()))

    def test_tampered_receipt_is_rejected(self) -> None:
        reference = self._capture()
        receipt_path = self.receipt_directory / f"{reference.occurrence_id}.json"
        receipt_path.write_text("{}", encoding="utf-8")
        receipt_path.chmod(0o600)
        verifier = load_local_evidence_verifier(
            self.config, project_id="vhost-manager-alpha"
        )
        self.assertIsNone(verifier.attest(reference, self._context()))

    def test_expired_receipt_is_rejected(self) -> None:
        self._write_config()
        document = json.loads(self.config.read_text(encoding="utf-8"))
        document["human_observation"]["validity_seconds"] = 1
        self.config.write_text(json.dumps(document), encoding="utf-8")
        self.config.chmod(0o600)
        reference = self._capture()
        verifier = load_local_evidence_verifier(
            self.config, project_id="vhost-manager-alpha"
        )
        later = datetime.now(UTC) + timedelta(seconds=2)
        self.assertIsNone(verifier.attest(reference, self._context(now=later)))

    def test_cli_requires_attended_exact_confirmation_and_emits_no_prompt_text(self) -> None:
        challenge = "CONFIRM HUMAN OBSERVATION 0123456789abcdef"
        stdout = StringIO()
        stderr = _TerminalOutput()
        stdin = _TerminalInput(challenge + "\n")
        with (
            patch(
                "curatormd_v2.evidence_cli.new_human_confirmation_challenge",
                return_value=challenge,
            ),
            patch("sys.stdin", stdin),
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
        ):
            status = main(
                [
                    "human-observation",
                    "--project-root",
                    str(self.project_root),
                    "--host-config",
                    str(self.config),
                    "--goal-id",
                    "goal-alpha",
                    "--criterion-id",
                    "criterion-alpha",
                ]
            )

        self.assertEqual(status, 0, stderr.getvalue())
        receipts = list(self.receipt_directory.iterdir())
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].stat().st_mode & 0o777, 0o600)
        self.assertNotIn("CONFIRM", receipts[0].read_text(encoding="utf-8"))
        self.assertNotIn(challenge, stdout.getvalue())
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["evidence_kind"], "human_observation")
        self.assertEqual(output["outcome"], "passed")

    def test_cli_rejects_noninteractive_confirmation(self) -> None:
        stdout = StringIO()
        with (
            patch("sys.stdin", StringIO("CONFIRM\n")),
            patch("sys.stdout", stdout),
            patch("sys.stderr", StringIO()),
        ):
            status = main(
                [
                    "human-observation",
                    "--project-root",
                    str(self.project_root),
                    "--host-config",
                    str(self.config),
                    "--goal-id",
                    "goal-alpha",
                    "--criterion-id",
                    "criterion-alpha",
                ]
            )

        self.assertEqual(status, 2)
        self.assertEqual(list(self.receipt_directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
