"""Shared fixtures for the split purge lifecycle tests."""
# pylint: disable=duplicate-code
# Parallel tests repeat setup to exercise distinct failure conditions.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from purge_fixtures import TestReviewAuthorizer, TestVerifier

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    AuditReceipt,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    Materiality,
    ReacquisitionAction,
    SuccessCriterion,
)
from curatormd_v2.service import SDEAssessmentRequest


class ReceiptCheckingPurger(ArtifactPurger):
    """Require a durable receipt before the test purger deletes an artifact."""

    def __init__(self, staging_root: Path, store: CuratorStore, candidate_id: str):
        super().__init__(staging_root)
        self.store = store
        self.candidate_id = candidate_id
        self.called = False

    def purge(self, artifact: ArtifactRef) -> bool:
        self.assert_receipt_exists()
        self.called = True
        return super().purge(artifact)

    def assert_receipt_exists(self) -> None:
        """Fail if canonical receipt persistence has not happened yet."""

        receipts = self.store.receipts_for_goal(
            self.store.get_sde_candidate(self.candidate_id).goal_id
        )
        receipt = next(
            (item for item in receipts if item.candidate_id == self.candidate_id),
            None,
        )
        if receipt is None or not receipt.canonical_persisted:
            raise AssertionError("purge started before durable audit receipt")

class DeleteThenCrashPurger(ArtifactPurger):  # pylint: disable=too-few-public-methods
    """Simulate process loss after unlink but before its SQLite result."""

    def __init__(self, staging_root: Path):
        super().__init__(staging_root)
        self.interrupted = False

    def purge(self, artifact: ArtifactRef) -> bool:
        if not self.interrupted:
            removed = super().purge(artifact)
            self.interrupted = True
            raise RuntimeError(f"simulated process loss after deletion: {removed}")
        return super().purge(artifact)

class PurgeTestSupport(unittest.TestCase):
    """Shared fixture and record builders for purge workflow tests."""

    def setUp(self) -> None:
        self.root = Path(
            self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        )
        self.stage = self.root / "stage"
        self.stage.mkdir()
        for directory in (".git", "src", "docs", "persistence"):
            (self.root / directory).mkdir()
        (self.root / "docs" / "tasks.md").write_text("- [ ] Purge retry\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        config_path = self.root / ".curatormd-v2.toml"
        config_path.write_text(
            '''\
schema_version = 1
backend_api_version = 1
project_id = "default"

[scope]
read_paths = ["src", "docs", "persistence"]

[checklists]
tasks = "docs/tasks.md"

[evidence]
adapters = []

[staging]
root = "stage"

[persistence]
targets = ["persistence/HISTORY.md"]
'''
        )
        config_path.chmod(0o600)
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        self.goal = self.service.goal_start(
            "Record and purge reviewed development artifacts",
            (SuccessCriterion("test", "targeted test passes"),),
        )


    def tearDown(self) -> None:
        self.store.close()


    @staticmethod
    def evidence() -> EvidenceRef:
        """Return deterministic passing proof for the purge criterion."""

        return EvidenceRef(
            "test",
            "test-proof:verified",
            hashlib.sha256(b"proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )


    def candidate(self, label: str = "") -> str:
        """Create a verified change proposal and return its candidate ID."""

        change, _ = self.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            f"Added the tested behavior {label}".strip(),
        )
        verification, _ = self.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            "Targeted test passed",
            criterion_id="test",
            evidence=(self.evidence(),),
        )
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The behavior is durable and verified",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        return candidate.candidate_id


    def artifact(self, name: str = "scratch.json") -> tuple[Path, ArtifactRef]:
        """Create one staged file and the reference to its exact content hash."""

        path = self.stage / name
        path.write_bytes(b"temporary evidence")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        metadata = path.stat()
        return path, ArtifactRef(
            str(path), digest, device_id=metadata.st_dev, inode_id=metadata.st_ino,
            occurrence_id=uuid4().hex,
        )


    def persist_canonical(
        self, receipt: AuditReceipt, service: CuratorService | None = None
    ) -> AuditReceipt:
        """Record a verified test projection before allowing purge to proceed."""

        active_service = service or self.service
        active_service.mark_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )
        if not receipt.artifact_inventory_complete:
            return active_service.store.get_receipt(receipt.receipt_id)
        with active_service.store.transaction() as connection:
            for artifact in receipt.artifacts:
                action = (
                    ReacquisitionAction.RETAIN_UNDER_HOLD
                    if artifact.retention_hold is not None
                    else ReacquisitionAction.NOT_REQUIRED
                )
                connection.execute(
                    "UPDATE purge_targets SET reacquisition_action = ? "
                    "WHERE receipt_id = ? AND path = ?",
                    (action.value, receipt.receipt_id, artifact.path),
                )
        manifest = json.dumps(
            [
                (item.path, item.sha256, item.occurrence_id)
                for item in sorted(receipt.artifacts, key=lambda item: item.path)
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        _authorization, _pending_receipt = active_service.authorize_artifact_cleanup(
            receipt.receipt_id,
            hashlib.sha256(manifest.encode("utf-8")).hexdigest(),
            "a" * 64,
        )
        return active_service.mark_cleanup_authorization_canonical_persisted(
            receipt.receipt_id,
            "/consumer/persistence/HISTORY.md",
            hashlib.sha256(receipt.receipt_id.encode()).hexdigest(),
        )
