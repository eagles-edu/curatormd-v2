"""Attended local-UID review and same-action purge authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import io
from io import StringIO
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence

from curatormd_v2.api import AuthenticatedCaller
from curatormd_v2.access_cli import main as access_main
from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.models import (
    ArtifactRef,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    Materiality,
    ReviewDecision,
    SuccessCriterion,
)
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.review_cli import LocalUIDReviewAuthorizer, main
from curatormd_v2.reviews import ReviewAuthorizationError
from curatormd_v2.store import CuratorStore


class _PurgeStatus(StrEnum):
    COMPLETE = "complete"


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    materiality: StrEnum
    rationale: str
    impact: str
    retrieval_value: str


@dataclass(frozen=True)
class _Goal:
    goal_id: str


@dataclass(frozen=True)
class _Detail:
    candidate: _Candidate
    goal: _Goal
    facts: tuple[()]
    receipt: None = None
    corrections: tuple[()] = ()


@dataclass(frozen=True)
class _InventoryUsage:
    inventory_complete: bool


@dataclass(frozen=True)
class _Artifact:
    path: str
    sha256: str
    retention_hold: None = None


@dataclass(frozen=True)
class _Inventory:
    artifacts: tuple[_Artifact, ...]
    usage: _InventoryUsage
    manifest_sha256: str
    scope_goal_id: str


@dataclass(frozen=True)
class _Packet:
    detail: _Detail
    artifact_inventory: _Inventory


class _InteractiveInput(StringIO):
    def __init__(self, value: str, *, interactive: bool = True) -> None:
        super().__init__(value)
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


class _InteractiveOutput(StringIO):
    def isatty(self) -> bool:
        return True


class _InteractiveErrors(StringIO):
    def isatty(self) -> bool:
        return True


class _PipedOutput(StringIO):
    def isatty(self) -> bool:
        return False


class _Receipt:
    receipt_id = "receipt-1"
    purge_status = _PurgeStatus.COMPLETE


class _Projection:
    target = Path("/tmp/HISTORY.md")
    sha256 = "b" * 64


@dataclass(frozen=True)
class _PreparedCliReview:
    goal_id: str
    candidate_id: str
    staged_artifact: ArtifactRef
    manifest_hash: str


class _TestEvidenceVerifier:
    def attest(
        self, evidence: EvidenceRef, context: EvidenceVerificationContext
    ):
        """Return fixture evidence only for this test's known locator."""
        if evidence.locator != "review-cli-proof:verified":
            return None
        return attest_test_evidence(evidence, context)


class _ReviewAPI:
    def __init__(self, packet: _Packet) -> None:
        self.packet = packet
        self.calls: list[tuple[str, Any]] = []

    def sde_review_packet(
        self, caller: AuthenticatedCaller, project_id: str, candidate_id: str
    ) -> _Packet:
        """Record and return the configured review packet."""
        self.calls.append(("packet", (caller.subject_id, project_id, candidate_id)))
        return self.packet

    def sde_confirm(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        artifacts: tuple[_Artifact, ...],
        *,
        artifact_inventory_complete: bool,
        rationale: str,
    ) -> _Receipt:
        """Record the exact decision request and return its fixture receipt."""
        self.calls.append(
            (
                "confirm",
                (
                    caller.subject_id,
                    project_id,
                    candidate_id,
                    decision,
                    artifacts,
                    artifact_inventory_complete,
                    rationale,
                ),
            )
        )
        return _Receipt()

    def persist_goal(
        self,
        _caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        target: str,
    ) -> _Projection:
        """Record the requested project-local Markdown projection."""
        self.calls.append(("persist", (project_id, goal_id, target)))
        return _Projection()

    def artifact_purge_status(
        self,
        _caller: AuthenticatedCaller,
        project_id: str,
        receipt_id: str,
    ) -> tuple[_Receipt, tuple[()]]:
        """Record a status lookup and return the complete fixture receipt."""
        self.calls.append(("purge_status", (project_id, receipt_id)))
        return _Receipt(), ()


class ReviewCliTests(unittest.TestCase):
    """Bind human disposition to the visible inventory and local OS identity."""

    def _project(self, root: Path) -> None:
        (root / ".git").mkdir()
        (root / "src").mkdir()
        (root / "docs").mkdir()
        (root / "persistence").mkdir()
        (root / ".curatormd-v2" / "staging").mkdir(parents=True)
        (root / "docs" / "tasks.md").write_text("- [ ] Review CLI fixture\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        (root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "review-cli-project"

            [scope]
            read_paths = ["src", "docs"]

            [checklists]
            tasks = "docs/tasks.md"

            [evidence]
            adapters = []

            [staging]
            root = ".curatormd-v2/staging"

            [persistence]
            targets = ["persistence/HISTORY.md"]
            """
        )
        (root / ".curatormd-v2.toml").chmod(0o600)

    def _grant_local_reviewer(
        self, root: Path, database: Path, rationale: str
    ) -> None:
        subject = f"local-uid:{os.geteuid()}"
        for operation, phrase, extra in (
            ("register", "REGISTER review-cli-project", ()),
            (
                "grant",
                f"GRANT read review-cli-project {subject}",
                ("--subject-id", subject, "--action", "read"),
            ),
            (
                "grant",
                f"GRANT review review-cli-project {subject}",
                ("--subject-id", subject, "--action", "review"),
            ),
        ):
            errors = StringIO()
            result = access_main(
                [
                    operation,
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    *extra,
                    "--rationale",
                    rationale,
                ],
                stdin=_InteractiveInput(phrase + "\n"),
                stdout=StringIO(),
                stderr=errors,
            )
            self.assertEqual(result, 0, errors.getvalue())

    def _prepare_local_review(self, root: Path, database: Path) -> _PreparedCliReview:
        config = ProjectConfig.load(root)
        store = CuratorStore(database)
        plugin = ProjectPlugin.bind(
            config,
            store,
            evidence_verifier=_TestEvidenceVerifier(),
            review_authorizer=LocalUIDReviewAuthorizer(),
        )
        goal = plugin.service.goal_start(
            "Review one verified local change",
            (SuccessCriterion("verified", "The disposable proof passes"),),
            goal_id="review-cli-goal",
        )
        change, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Implemented the bounded change"
        )
        evidence = EvidenceRef(
            "unit-test",
            "review-cli-proof:verified",
            hashlib.sha256(b"disposable proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        verified, _ = plugin.service.goal_fact(
            goal.goal_id,
            FactKind.VERIFICATION,
            "The disposable proof passed",
            criterion_id="verified",
            evidence=(evidence,),
        )
        candidate = plugin.service.sde_assess(
            goal.goal_id,
            Materiality.IMPLEMENTATION,
            "A verified local implementation change",
            (change.fact_id, verified.fact_id),
            impact="Observed in the disposable fixture",
            retrieval_value="Useful when reviewing this local change",
        )
        if candidate is None:
            store.close()
            self.fail("verified implementation was not assessed as an SDE")
        staged_artifact = plugin.stage_artifact(
            goal.goal_id,
            "import",
            "transient-canary",
            io.BytesIO(b"TRANSIENT REVIEW CLI CANARY\n"),
        )
        inventory = plugin.discover_staging_artifacts(goal.goal_id)
        manifest_hash = inventory.manifest_sha256
        if manifest_hash is None:
            store.close()
            self.fail("staging inventory did not produce a manifest hash")
        prepared = _PreparedCliReview(
            goal.goal_id,
            candidate.candidate_id,
            staged_artifact,
            manifest_hash,
        )
        store.close()
        return prepared

    def test_review_uses_current_local_uid_and_rejects_a_profile_name(self) -> None:
        authorizer = LocalUIDReviewAuthorizer()
        with patch("curatormd_v2.review_cli._local_subject", return_value="local-uid:42"):
            self.assertEqual(
                authorizer.authorize(
                    "project-a", "candidate-a", ReviewDecision.APPROVED, "local-uid:42"
                ),
                "local-uid:42",
            )
            with self.assertRaises(ReviewAuthorizationError):
                authorizer.authorize(
                    "project-a", "candidate-a", ReviewDecision.APPROVED, "renew-ssl-coding"
                )

    def test_review_confirms_exact_inventory_then_persists_before_purge_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            CuratorStore(database).close()
            artifact = _Artifact(
                str(root / ".curatormd-v2/staging/goal-a/import" / "artifact.bin"),
                "a" * 64,
            )
            packet = _Packet(
                _Detail(
                    _Candidate(
                        "candidate-a",
                        _PurgeStatus.COMPLETE,
                        "A material verified outcome",
                        "Observed improvement",
                        "Find the decision later",
                    ),
                    _Goal("goal-a"),
                    (),
                ),
                _Inventory(
                    (artifact,), _InventoryUsage(True), "c" * 64, "goal-a"
                ),
            )
            api = _ReviewAPI(packet)
            phrase = (
                f"APPROVE candidate-a AND PURGE INVENTORY "
                f"{packet.artifact_inventory.manifest_sha256}"
            )
            stdin = _InteractiveInput(f"approve\n{phrase}\nVerified and approved\n")
            stdout = _InteractiveOutput()
            stderr = _InteractiveErrors()
            with patch("curatormd_v2.review_cli._build_api", return_value=api):
                result = main(
                    [
                        "--project-root",
                        str(root),
                        "--database",
                        str(database),
                        "review",
                        "candidate-a",
                    ],
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                )

            self.assertEqual(result, 0, stderr.getvalue())
            confirm = next(value for name, value in api.calls if name == "confirm")
            self.assertEqual(confirm[3], ReviewDecision.APPROVED)
            self.assertEqual(confirm[4], packet.artifact_inventory.artifacts)
            self.assertTrue(confirm[5])
            self.assertEqual(confirm[6], "Verified and approved")
            self.assertLess(
                next(i for i, (name, _) in enumerate(api.calls) if name == "confirm"),
                next(i for i, (name, _) in enumerate(api.calls) if name == "persist"),
            )
            self.assertIn('"purge_status": "complete"', stdout.getvalue())

    def test_review_refuses_noninteractive_input_before_opening_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "missing.sqlite3"
            stdin = _InteractiveInput("", interactive=False)
            stdout = _InteractiveOutput()
            stderr = StringIO()
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "review",
                    "candidate-a",
                ],
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(result, 2)
            self.assertFalse(database.exists())
            self.assertIn("interactive TTY", stderr.getvalue())

    def test_review_refuses_hidden_prompts_before_opening_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "missing.sqlite3"
            errors = StringIO()
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "review",
                    "candidate-a",
                ],
                stdin=_InteractiveInput(""),
                stdout=_InteractiveOutput(),
                stderr=errors,
            )

            self.assertEqual(result, 2)
            self.assertFalse(database.exists())
            self.assertIn("prompt TTY", errors.getvalue())

    def test_review_refuses_piped_output_before_opening_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "missing.sqlite3"
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "review",
                    "candidate-a",
                ],
                stdin=_InteractiveInput(""),
                stdout=_PipedOutput(),
                stderr=StringIO(),
            )

            self.assertEqual(result, 2)
            self.assertFalse(database.exists())

    def test_local_cli_reviews_real_store_and_purges_after_canonical_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            self._grant_local_reviewer(
                root,
                database,
                "Authorize the isolated reviewer fixture",
            )
            prepared = self._prepare_local_review(root, database)
            staged = Path(prepared.staged_artifact.path)

            phrase = (
                f"APPROVE {prepared.candidate_id} AND PURGE INVENTORY "
                f"{prepared.manifest_hash}"
            )
            result_output = _InteractiveOutput()
            result_errors = _InteractiveErrors()
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "review",
                    prepared.candidate_id,
                ],
                stdin=_InteractiveInput(
                    f"approve\n{phrase}\nVerified in the disposable suite\n"
                ),
                stdout=result_output,
                stderr=result_errors,
            )

            self.assertEqual(result, 0, result_errors.getvalue())
            self.assertFalse(staged.exists())
            reopened = CuratorStore(database)
            self.assertEqual(
                reopened.staging_artifact_times(
                    "review-cli-project", (prepared.staged_artifact,)
                ),
                {},
            )
            reopened_plugin = ProjectPlugin.bind(
                ProjectConfig.load(root), reopened
            )
            replacement = reopened_plugin.stage_artifact(
                prepared.goal_id,
                "import",
                "transient-canary",
                io.BytesIO(b"replacement transient bytes"),
            )
            replacement_age = reopened_plugin.discover_expired_staging_artifacts(
                datetime.now(UTC) + timedelta(hours=71)
            )
            self.assertTrue(replacement_age.inventory_complete)
            self.assertEqual(replacement_age.eligible_artifacts, ())
            self.assertEqual(replacement.path, prepared.staged_artifact.path)
            reopened.close()
            history = (root / "persistence" / "HISTORY.md").read_text()
            self.assertIn("Implemented the bounded change", history)
            self.assertNotIn("TRANSIENT REVIEW CLI CANARY", history)
            self.assertIn('"purge_status": "complete"', result_output.getvalue())

    def test_local_expiry_review_persists_exact_receipt_before_purge(self) -> None:
        """Require an attended exact manifest and retain its receipt after cleanup."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            self._grant_local_reviewer(
                root,
                database,
                "Authorize the disposable expiry fixture",
            )

            store = CuratorStore(database)
            plugin = ProjectPlugin.bind(
                ProjectConfig.load(root),
                store,
                review_authorizer=LocalUIDReviewAuthorizer(),
            )
            goal = plugin.service.goal_start(
                "Expire one old local artifact",
                (SuccessCriterion("verified", "The artifact is temporary"),),
                goal_id="expiry-cli-goal",
            )
            with patch(
                "curatormd_v2.store.utc_now",
                return_value=(datetime.now(UTC) - timedelta(hours=73)).isoformat(),
            ):
                artifact = plugin.stage_artifact(
                    goal.goal_id,
                    "scratch",
                    "old-scratch",
                    io.BytesIO(b"EXPIRED TRANSIENT CANARY"),
                )
            snapshot = plugin.discover_expired_staging_artifacts()
            self.assertTrue(snapshot.inventory_complete)
            self.assertEqual(snapshot.eligible_artifacts, (artifact,))
            self.assertIsNotNone(snapshot.manifest_sha256)
            manifest_hash = snapshot.manifest_sha256
            store.close()

            output = _InteractiveOutput()
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "expire",
                ],
                stdin=_InteractiveInput(
                    f"PURGE EXPIRED INVENTORY {manifest_hash}\n"
                ),
                stdout=output,
                stderr=_InteractiveErrors(),
            )

            self.assertEqual(result, 0, output.getvalue())
            self.assertFalse(Path(artifact.path).exists())
            emitted = json.loads(output.getvalue().splitlines()[-1])[
                "expiry_purge_receipt"
            ]
            reopened = CuratorStore(database)
            receipt = reopened.expiry_purge_receipt(
                emitted["receipt_id"], "review-cli-project"
            )
            self.assertEqual(receipt.reviewer_id, f"local-uid:{os.geteuid()}")
            self.assertEqual(receipt.manifest_sha256, manifest_hash)
            self.assertEqual(receipt.status.value, "complete")
            self.assertEqual(
                reopened.staging_artifact_times(
                    "review-cli-project", (artifact,)
                ),
                {},
            )
            self.assertEqual(
                (root / "persistence" / "HISTORY.md").read_text(), "# History\n"
            )
            reopened.close()

    def test_expiry_refuses_hidden_prompts_before_opening_database(self) -> None:
        """An expiry receipt cannot be authorized when its confirmation is hidden."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "missing.sqlite3"
            errors = StringIO()
            result = main(
                [
                    "--project-root",
                    str(root),
                    "--database",
                    str(database),
                    "expire",
                ],
                stdin=_InteractiveInput(""),
                stdout=_InteractiveOutput(),
                stderr=errors,
            )
            self.assertEqual(result, 2)
            self.assertFalse(database.exists())
            self.assertIn("visible prompt TTY", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
