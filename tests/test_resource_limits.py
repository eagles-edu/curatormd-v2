"""Test named domain limits independent of transport serialization."""

from __future__ import annotations

import unittest

from curatormd_v2.models import (
    MAX_ARTIFACTS_PER_RECEIPT,
    MAX_CRITERIA_REVISIONS,
    MAX_EVIDENCE_REFERENCES,
    MAX_GOAL_DEPENDENCIES,
    MAX_SDE_SUPPORTING_FACTS,
    MAX_SUCCESS_CRITERIA,
    ArtifactRef,
    AuditReceipt,
    EvidenceOutcome,
    EvidenceRef,
    Fact,
    FactKind,
    GoalCard,
    Materiality,
    ReviewDecision,
    SDECandidate,
    SuccessCriterion,
)
from curatormd_v2.events import FactRecorded, GoalCriteriaAmended, GoalStarted


class ResourceLimitTests(unittest.TestCase):
    """Enforce limits before records reach SQLite or destructive adapters."""

    @staticmethod
    def criteria(count: int) -> tuple[SuccessCriterion, ...]:
        """Create distinct criteria to exercise configured count bounds."""

        return tuple(
            SuccessCriterion(f"criterion-{index}", "observable result")
            for index in range(count)
        )

    @staticmethod
    def evidence(count: int) -> tuple[EvidenceRef, ...]:
        """Create stable synthetic evidence references for payload limits."""

        return tuple(
            EvidenceRef(
                "test",
                f"suite://check-{index}",
                "a" * 64,
                EvidenceOutcome.PASSED,
            )
            for index in range(count)
        )

    def test_goal_criteria_and_dependency_counts_are_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "success criteria exceed"):
            GoalCard("goal", "problem", self.criteria(MAX_SUCCESS_CRITERIA + 1))

        dependencies = tuple(
            f"dependency-{index}" for index in range(MAX_GOAL_DEPENDENCIES + 1)
        )
        with self.assertRaisesRegex(ValueError, "goal dependencies exceed"):
            GoalCard(
                "goal",
                "problem",
                (SuccessCriterion("one", "observable result"),),
                depends_on_goal_ids=dependencies,
            )

        with self.assertRaisesRegex(ValueError, "success criteria exceed"):
            GoalStarted(
                "goal",
                "problem",
                self.criteria(MAX_SUCCESS_CRITERIA + 1),
            )

        with self.assertRaisesRegex(ValueError, "criteria history is limited"):
            GoalCriteriaAmended(
                "goal",
                MAX_CRITERIA_REVISIONS,
                (SuccessCriterion("one", "observable result"),),
                "Revise the contract",
                "Run the check",
            )

    def test_fact_evidence_and_sde_support_are_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence references exceed"):
            Fact(
                "goal",
                FactKind.CHANGE,
                "Changed behavior",
                evidence=self.evidence(MAX_EVIDENCE_REFERENCES + 1),
            )

        with self.assertRaisesRegex(ValueError, "evidence references exceed"):
            FactRecorded(
                "goal",
                "fact",
                FactKind.CHANGE,
                "Changed behavior",
                evidence=self.evidence(MAX_EVIDENCE_REFERENCES + 1),
            )

        fact_ids = tuple(
            f"fact-{index}" for index in range(MAX_SDE_SUPPORTING_FACTS + 1)
        )
        with self.assertRaisesRegex(ValueError, "SDE supporting facts exceed"):
            SDECandidate(
                "goal",
                materiality=Materiality.IMPLEMENTATION,
                rationale="A verified material change",
                fact_ids=fact_ids,
            )

    def test_artifact_manifest_is_bounded_and_rejects_duplicate_paths(self) -> None:
        artifacts = tuple(
            ArtifactRef(f"/stage/{index}.tmp", "b" * 64)
            for index in range(MAX_ARTIFACTS_PER_RECEIPT + 1)
        )
        with self.assertRaisesRegex(ValueError, "artifact inventory exceeds"):
            AuditReceipt(
                "candidate",
                decision=ReviewDecision.APPROVED,
                facts_sha256="c" * 64,
                artifacts=artifacts,
            )

        with self.assertRaisesRegex(ValueError, "paths must be unique"):
            AuditReceipt(
                "candidate",
                decision=ReviewDecision.APPROVED,
                facts_sha256="c" * 64,
                artifacts=(
                    ArtifactRef("/stage/duplicate.tmp", "b" * 64),
                    ArtifactRef("/stage/duplicate.tmp", "d" * 64),
                ),
            )

    def test_artifact_hold_rejects_a_plain_string_from_dynamic_callers(self) -> None:
        with self.assertRaisesRegex(ValueError, "retention_hold must be"):
            ArtifactRef(
                "/stage/held.tmp",
                "b" * 64,
                retention_hold="legal",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
