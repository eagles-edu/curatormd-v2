"""Reviewer-gated fact archive tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from evidence_fixtures import attest_test_evidence

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    Fact,
    FactArchiveIntegrityError,
    FactCapacityError,
    FactKind,
    GoalStatus,
    Materiality,
    SuccessCriterion,
    SQLITE_SCHEMA_VERSION,
)


class AcceptTestEvidence:
    """Accept only the test's stable synthetic proof references."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest the stable synthetic proof references for archive tests."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator.startswith("test-proof:")
            else None
        )


class FactCompactionTests(unittest.TestCase):
    """Prove proposal, approval, archive integrity, and recovery behavior."""

    def setUp(self) -> None:
        self.root = Path(
            self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        )
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), AcceptTestEvidence(),
            project_id="archive-project",
        )
        self.goal = self.service.goal_start(
            "Exercise safe fact archive recovery",
            (SuccessCriterion("done", "The routine facts remain recoverable"),),
        )

    def tearDown(self) -> None:
        self.store.close()

    def add_fact(
        self,
        kind: FactKind,
        bullet: str,
        *,
        evidence: tuple[EvidenceRef, ...] = (),
        criterion_id: str | None = None,
    ) -> Fact:
        """Append a fact through the service and return the stored record."""

        return self.service.goal_fact(
            self.goal.goal_id,
            kind,
            bullet,
            evidence=evidence,
            criterion_id=criterion_id,
        )[0]

    def proof(self) -> EvidenceRef:
        """Return passing evidence with a deterministic content hash."""

        return EvidenceRef(
            "unit-test",
            "test-proof:archive-fixture",
            hashlib.sha256(b"archive-fixture").hexdigest(),
            EvidenceOutcome.PASSED,
        )

    def archive_routine_fact(self) -> tuple[Fact, str]:
        """Create one reviewed routine fact and return its archive key."""

        routine = self.add_fact(
            FactKind.RESEARCH,
            "A routine archive fixture with a stable source hash for integrity checks.",
        )
        proposal = self.service.fact_compaction_propose(self.goal.goal_id)
        receipt = self.service.fact_compaction_approve(
            proposal.compaction_id,
            self.goal.goal_id,
            (routine.fact_id,),
            proposal.source_sha256,
            "reviewer-1",
            "Approve archival",
        )
        return routine, receipt.compaction_id

    def replace_archive_source(self, compaction_id: str, source: bytes) -> None:
        """Replace one archive payload while keeping its integrity fields valid."""

        compressed = zlib.compress(source)
        with self.store.transaction() as connection:
            connection.execute(
                """UPDATE fact_archives SET payload_zlib = ?, compressed_bytes = ?,
                   source_bytes = ?, source_sha256 = ?, archive_sha256 = ?
                   WHERE compaction_id = ?""",
                (
                    compressed,
                    len(compressed),
                    len(source),
                    hashlib.sha256(source).hexdigest(),
                    hashlib.sha256(compressed).hexdigest(),
                    compaction_id,
                ),
            )

    def test_approval_archives_only_eligible_facts_and_keeps_them_retrievable(self) -> None:
        research = self.add_fact(
            FactKind.RESEARCH,
            "Inspected the stable persistence boundary and its bounded archive recovery path",
        )
        self.store.attach_fact_source_event(
            (research.fact_id,), "event-source-archive", "archive-project"
        )
        research = self.store.get_fact(research.fact_id, "archive-project")
        self.assertEqual(research.source_event_id, "event-source-archive")
        advice = self.add_fact(
            FactKind.ADVICE,
            "Keep operator review explicit before routine history is compacted",
        )
        change = self.add_fact(FactKind.CHANGE, "Changed the persistence boundary")
        verification = self.add_fact(
            FactKind.VERIFICATION,
            "The archive fixture passed",
            evidence=(self.proof(),),
            criterion_id="done",
        )

        proposal = self.service.fact_compaction_propose(self.goal.goal_id)
        self.assertEqual(
            tuple(fact.fact_id for fact in proposal.facts),
            (research.fact_id, advice.fact_id),
        )
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 4)

        receipt = self.service.fact_compaction_approve(
            proposal.compaction_id,
            self.goal.goal_id,
            tuple(fact.fact_id for fact in proposal.facts),
            proposal.source_sha256,
            "reviewer-1",
            "Approved routine research and advice archival",
        )
        self.assertEqual(receipt.reviewer_id, "reviewer-1")
        self.assertEqual(receipt.fact_ids, (research.fact_id, advice.fact_id))
        self.assertLess(receipt.compressed_bytes, receipt.source_bytes)
        self.assertEqual(receipt.compressed_bytes, proposal.estimated_compressed_bytes)
        self.assertEqual(
            tuple(fact.fact_id for fact in self.store.list_facts(self.goal.goal_id)),
            tuple(
                fact.fact_id
                for fact in sorted(
                    (research, advice, change, verification),
                    key=lambda item: (item.created_at, item.fact_id),
                )
            ),
        )
        self.assertEqual(self.store.get_fact(research.fact_id), research)
        self.assertIn(
            "source event: event-source-archive", self.store.get_fact(
                research.fact_id, "archive-project"
            ).as_bullet()
        )
        self.assertEqual(self.service.goal_status(self.goal.goal_id).goal.status, GoalStatus.ACTIVE)
        usage = self.store.project_storage_usage("archive-project")
        self.assertEqual(usage.fact_count, 2)
        self.assertEqual(usage.fact_archive_batch_count, 1)
        self.assertEqual(usage.fact_archive_item_count, 2)
        self.assertEqual(usage.fact_archive_compressed_bytes, receipt.compressed_bytes)
        self.assertGreaterEqual(
            usage.fact_archive_logical_bytes, usage.fact_archive_compressed_bytes
        )
        self.assertEqual(
            usage.fact_archive_bytes_remaining,
            usage.fact_archive_logical_bytes_limit - usage.fact_archive_logical_bytes,
        )
        self.assertGreater(usage.fact_archive_bytes_remaining, 0)

        replay = self.service.fact_compaction_approve(
            proposal.compaction_id,
            self.goal.goal_id,
            tuple(fact.fact_id for fact in proposal.facts),
            proposal.source_sha256,
            "reviewer-1",
            "Approved routine research and advice archival",
        )
        self.assertEqual(replay, receipt)
        with self.assertRaisesRegex(ConflictError, "fact ID was already used"):
            self.store.append_fact(
                Fact(
                    goal_id=self.goal.goal_id,
                    kind=FactKind.RESEARCH,
                    bullet="Changed content reuses an archived ID",
                    fact_id=research.fact_id,
                ),
                "archive-project",
            )
        database = self.root / "curator.sqlite3"
        with self.store.transaction() as connection:
            connection.execute(
                "ALTER TABLE fact_archives DROP COLUMN schema_version"
            )
            connection.execute("PRAGMA user_version = 0")
        self.store.close()
        self.store = CuratorStore(database)
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), AcceptTestEvidence(),
            project_id="archive-project",
        )
        self.assertEqual(self.store.get_fact(research.fact_id), research)
        self.assertEqual(
            self.store.project_storage_usage("archive-project").fact_archive_item_count,
            2,
        )
        with self.store.transaction() as connection:
            self.assertEqual(
                connection.execute("PRAGMA user_version").fetchone()[0],
                SQLITE_SCHEMA_VERSION,
            )

    def test_stale_proposal_and_nonroutine_selection_never_delete_facts(self) -> None:
        routine = self.add_fact(FactKind.RESEARCH, "Reviewed the safe recovery design")
        verification = self.add_fact(
            FactKind.VERIFICATION,
            "The evidence check passed",
            evidence=(self.proof(),),
            criterion_id="done",
        )
        proposal = self.service.fact_compaction_propose(self.goal.goal_id)

        with self.assertRaisesRegex(ConflictError, "source changed"):
            self.service.fact_compaction_approve(
                proposal.compaction_id,
                self.goal.goal_id,
                (routine.fact_id,),
                "0" * 64,
                "reviewer-1",
                "Approve archival",
            )
        with self.assertRaisesRegex(ConflictError, "non-routine"):
            self.service.fact_compaction_approve(
                "compaction-nonroutine",
                self.goal.goal_id,
                (verification.fact_id,),
                proposal.source_sha256,
                "reviewer-1",
                "Attempt to archive verification",
            )
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 2)
        self.assertEqual(
            self.store.project_storage_usage("archive-project").fact_archive_batch_count,
            0,
        )

    def test_sde_supported_routine_fact_is_not_proposed_for_compaction(self) -> None:
        research = self.add_fact(
            FactKind.RESEARCH,
            "This routine-looking fact supports a material development event.",
        )
        verification = self.add_fact(
            FactKind.VERIFICATION,
            "The material event was directly verified.",
            evidence=(self.proof(),),
            criterion_id="done",
        )
        candidate = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "The change is material and has passing direct verification.",
            (research.fact_id, verification.fact_id),
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
        )
        self.assertIsNotNone(candidate)
        with self.assertRaisesRegex(ConflictError, "no eligible routine facts"):
            self.service.fact_compaction_propose(self.goal.goal_id)
        self.assertEqual(self.store.get_fact(research.fact_id), research)
        self.assertEqual(self.store.get_fact(verification.fact_id), verification)

    def test_archive_hash_tampering_fails_closed_on_retrieval(self) -> None:
        routine = self.add_fact(
            FactKind.RESEARCH,
            "This deliberately repetitive routine note is retained exactly in the "
            "compressed archive "
            "and its immutable source hash detects any later modification.",
        )
        proposal = self.service.fact_compaction_propose(self.goal.goal_id)
        receipt = self.service.fact_compaction_approve(
            proposal.compaction_id,
            self.goal.goal_id,
            (routine.fact_id,),
            proposal.source_sha256,
            "reviewer-1",
            "Approve archival",
        )
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE fact_archives SET payload_zlib = ? WHERE compaction_id = ?",
                (b"\x00" * receipt.compressed_bytes, proposal.compaction_id),
            )
        with self.assertRaisesRegex(FactArchiveIntegrityError, "compressed hash"):
            self.store.get_fact(routine.fact_id, "archive-project")

    def test_invalid_archive_json_error_does_not_retain_raw_source(self) -> None:
        """Malformed archived JSON must not remain reachable through causes."""

        routine, compaction_id = self.archive_routine_fact()
        self.replace_archive_source(
            compaction_id,
            b'{"bullet":"PRIVATE_ARCHIVE_CANARY", invalid',
        )
        with self.assertRaisesRegex(FactArchiveIntegrityError, "JSON is invalid") as raised:
            self.store.get_fact(routine.fact_id, "archive-project")
        self.assertNotIn("PRIVATE_ARCHIVE_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_archive_kind_error_does_not_echo_raw_value(self) -> None:
        """Domain validation must not chain enum errors containing archive data."""

        routine, compaction_id = self.archive_routine_fact()
        source = json.dumps(
            [
                {
                    "fact_id": routine.fact_id,
                    "goal_id": self.goal.goal_id,
                    "kind": "PRIVATE_ARCHIVE_CANARY",
                    "bullet": "A malformed archive record.",
                    "criterion_id": None,
                    "evidence": [],
                    "created_at": routine.created_at,
                }
            ]
        ).encode("utf-8")
        self.replace_archive_source(compaction_id, source)
        with self.assertRaisesRegex(
            FactArchiveIntegrityError, "record failed domain validation"
        ) as raised:
            self.store.get_fact(routine.fact_id, "archive-project")
        self.assertNotIn("PRIVATE_ARCHIVE_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_archive_write_failure_rolls_back_before_active_fact_removal(self) -> None:
        routine = self.add_fact(
            FactKind.RESEARCH,
            "Keep routine history safely recoverable if archive commit is interrupted.",
        )
        proposal = self.service.fact_compaction_propose(self.goal.goal_id)
        with patch.object(
            self.store,
            "_fact_archive_receipt",
            side_effect=RuntimeError("simulated failure before transaction commit"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                self.service.fact_compaction_approve(
                    proposal.compaction_id,
                    self.goal.goal_id,
                    (routine.fact_id,),
                    proposal.source_sha256,
                    "reviewer-1",
                    "Approve after reviewing the exact source bullet",
                )
        self.assertEqual(self.store.get_fact(routine.fact_id), routine)
        usage = self.store.project_storage_usage("archive-project")
        self.assertEqual(usage.fact_archive_batch_count, 0)
        self.assertEqual(usage.fact_archive_item_count, 0)

    def test_archive_budget_failure_does_not_remove_active_facts(self) -> None:
        routine = self.add_fact(
            FactKind.RESEARCH,
            "The exact source bullet remains active when archive storage is full.",
        )
        proposal = self.service.fact_compaction_propose(self.goal.goal_id)
        with patch("curatormd_v2.store.MAX_FACT_ARCHIVE_BYTES_PER_PROJECT", 1):
            with self.assertRaises(FactCapacityError):
                self.service.fact_compaction_approve(
                    proposal.compaction_id,
                    self.goal.goal_id,
                    (routine.fact_id,),
                    proposal.source_sha256,
                    "reviewer-1",
                    "Attempt archival without archive capacity",
                )
        self.assertEqual(self.store.get_fact(routine.fact_id), routine)
        self.assertEqual(
            self.store.project_storage_usage("archive-project").fact_archive_batch_count,
            0,
        )

    def test_capacity_gate_reopens_only_after_approved_compaction(self) -> None:
        with patch("curatormd_v2.store.MAX_FACTS_PER_GOAL", 2):
            first = self.add_fact(
                FactKind.RESEARCH,
                "Inspect the bounded routine-fact persistence path carefully",
            )
            self.add_fact(
                FactKind.ADVICE,
                "Preserve the exact original bullet in the compressed reviewed archive",
            )
            with self.assertRaises(FactCapacityError):
                self.add_fact(FactKind.RESEARCH, "A third routine fact")
            blocked_capacity = self.service.goal_status(self.goal.goal_id).fact_capacity
            assert blocked_capacity is not None
            self.assertFalse(blocked_capacity.append_available)

            proposal = self.service.fact_compaction_propose(self.goal.goal_id)
            self.service.fact_compaction_approve(
                proposal.compaction_id,
                self.goal.goal_id,
                tuple(fact.fact_id for fact in proposal.facts),
                proposal.source_sha256,
                "reviewer-1",
                "Recover the explicitly reached active-fact limit",
            )
            recovered_capacity = self.service.goal_status(self.goal.goal_id).fact_capacity
            assert recovered_capacity is not None
            self.assertTrue(recovered_capacity.append_available)
            self.add_fact(FactKind.RESEARCH, "A third routine fact")
            self.assertEqual(self.store.get_fact(first.fact_id), first)


if __name__ == "__main__":
    unittest.main()
