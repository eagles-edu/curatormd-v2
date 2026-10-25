"""GoalFactCapacityAndSDE regressions."""

from __future__ import annotations

from unittest.mock import patch

from purge_fixtures import TestVerifier
from lifecycle_test_support import LifecycleTestSupport

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CuratorService,
    EvidenceGateError,
    FactKind,
    FactCapacityError,
    GoalStatus,
    MAX_FACTS_PER_GOAL,
    MAX_FACT_BYTES_PER_GOAL,
    Materiality,
    RejectUnverifiedEvidence,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    FactRecorded,
)
from curatormd_v2.service import SDEAssessmentRequest


class GoalFactCapacityAndSDETests(LifecycleTestSupport):
    """Cover goalfactcapacityandsde invariants."""

    def test_fact_count_capacity_blocks_without_pruning_and_reports_open_gate(self) -> None:
        for index in range(MAX_FACTS_PER_GOAL):
            self.service.goal_fact(
                self.goal.goal_id,
                FactKind.RESEARCH,
                f"Bounded research fact {index}",
            )

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertIsNotNone(snapshot.fact_capacity)
        assert snapshot.fact_capacity is not None
        self.assertEqual(len(snapshot.facts), MAX_FACTS_PER_GOAL)
        self.assertEqual(snapshot.fact_capacity.goal_fact_count, MAX_FACTS_PER_GOAL)
        self.assertFalse(snapshot.fact_capacity.append_available)
        self.assertIsNotNone(snapshot.fact_capacity.open_gate)
        assert snapshot.fact_capacity.open_gate is not None
        self.assertIn("capacity reached", snapshot.fact_capacity.open_gate)
        projection = self.service.goal_bullet_projection(self.goal.goal_id)
        self.assertTrue(
            any(
                item.category.value == "open_gate"
                and "capacity reached" in item.text
                for item in projection.bullets
            )
        )
        self.assertEqual(snapshot.goal.status, GoalStatus.ACTIVE)

        with self.assertRaises(FactCapacityError):
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "One more unique fact"
            )

        repeated, inserted = self.service.goal_fact(
            self.goal.goal_id, FactKind.RESEARCH, "Bounded research fact 511"
        )
        self.assertFalse(inserted, "semantic retries remain idempotent at capacity")
        self.assertIn(repeated.fact_id, {fact.fact_id for fact in snapshot.facts})
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), MAX_FACTS_PER_GOAL)

        event = EventEnvelope(
            "fact-capacity-event",
            "default",
            FactRecorded(
                self.goal.goal_id,
                "fact-over-capacity",
                FactKind.CHANGE,
                "Change blocked at the fact-history ceiling",
            ),
        )
        failed = self.service.process_event(event)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "FactCapacityError")
        self.assertEqual(self.store.pending_events(project_id="default"), ())
        self.assertEqual(
            self.store.project_storage_usage("default").event_payload_bytes_retained,
            0,
            "capacity-failed event payload is discarded after its digest receipt",
        )
        retry = self.service.process_event(event)
        self.assertEqual(retry.status.value, "failed")
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), MAX_FACTS_PER_GOAL)

    def test_fact_byte_capacity_blocks_oversized_history_without_pruning(self) -> None:
        ordinal = 0
        while True:
            evidence = tuple(
                self.proof(f"{ordinal}-{index}-" + "x" * 900)
                for index in range(16)
            )
            try:
                self.service.goal_fact(
                    self.goal.goal_id,
                    FactKind.RESEARCH,
                    f"Large bounded reference set {ordinal}",
                    evidence=evidence,
                )
                ordinal += 1
            except FactCapacityError:
                break

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertIsNotNone(snapshot.fact_capacity)
        assert snapshot.fact_capacity is not None
        self.assertGreater(ordinal, 0)
        self.assertLessEqual(
            snapshot.fact_capacity.goal_fact_bytes, MAX_FACT_BYTES_PER_GOAL
        )
        self.assertGreater(snapshot.fact_capacity.goal_fact_bytes_remaining, 0)
        self.assertTrue(
            snapshot.fact_capacity.append_available,
            "smaller facts remain admissible when this oversized one does not fit",
        )
        self.assertEqual(len(snapshot.facts), ordinal)

    def test_project_fact_capacity_is_shared_within_project_and_isolated_between_projects(
        self,
    ) -> None:
        other_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        other_goal = other_service.goal_start(
            "Independent project task",
            (SuccessCriterion("other", "Other project evidence is recorded"),),
        )

        with patch("curatormd_v2.store.MAX_FACTS_PER_PROJECT", 2):
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "First project fact"
            )
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "Second project fact"
            )
            capacity = self.service.goal_status(self.goal.goal_id).fact_capacity
            assert capacity is not None
            self.assertFalse(capacity.append_available)
            self.assertEqual(capacity.project_fact_count, 2)
            self.assertTrue(
                self.store.project_storage_usage("default").fact_capacity_reached,
            )
            with self.assertRaises(FactCapacityError):
                self.service.goal_fact(
                    self.goal.goal_id, FactKind.RESEARCH, "Third project fact"
                )

            other_service.goal_fact(
                other_goal.goal_id, FactKind.RESEARCH, "Other project remains writable"
            )
            self.assertFalse(
                self.store.project_storage_usage("other-project").fact_capacity_reached
            )

    def test_default_verifier_rejects_agent_asserted_pass(self) -> None:
        service = CuratorService(
            self.store, ArtifactPurger(self.stage), RejectUnverifiedEvidence()
        )
        with self.assertRaises(EvidenceGateError):
            service.goal_fact(
                self.goal.goal_id,
                FactKind.VERIFICATION,
                "agent says all tests passed",
                criterion_id="unit",
                evidence=(self.proof("claimed"),),
            )
        stored = service.goal_finish(self.goal.goal_id, "Claimed complete")
        self.assertEqual(stored.status, GoalStatus.OPEN)

    def test_duplicate_facts_are_idempotent(self) -> None:
        first, inserted_first = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Updated the health check"
        )
        second, inserted_second = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Updated the health check"
        )
        self.assertTrue(inserted_first)
        self.assertFalse(inserted_second)
        self.assertEqual(first.fact_id, second.fact_id)
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 1)

    def test_routine_progress_does_not_create_sde(self) -> None:
        self.verify("unit", "unit test suite passed")
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.ROUTINE,
                "Routine progress update",
                tuple(f.fact_id for f in self.store.list_facts(self.goal.goal_id)),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        self.assertIsNone(candidate)
        self.assertEqual(self.store.list_sde_candidates(self.goal.goal_id), ())

    def test_material_change_requires_verified_fact_for_sde(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added health check"
        )
        with self.assertRaises(EvidenceGateError):
            self.service.sde_assess(
                SDEAssessmentRequest(
                    self.goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "Durable change",
                    (change.fact_id,),
                    impact="Observed in the bounded test scenario",
                    retrieval_value="Useful for future maintenance review",
                )
            )

    def test_sde_rationale_is_a_compact_line_linked_to_verified_bullets(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added a durable health check"
        )
        verification = self.verify("unit", "Unit test passed")
        with self.assertRaisesRegex(ValueError, "single compact line"):
            self.service.sde_assess(
                SDEAssessmentRequest(
                    self.goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "First paragraph.\nSecond paragraph.",
                    (change.fact_id, verification.fact_id),
                    impact="Observed in the bounded test scenario",
                    retrieval_value="Useful for future maintenance review",
                )
            )
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The durable health check is supported by a passing test",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        review = self.service.sde_review_detail(candidate.candidate_id)
        self.assertEqual(len(review.facts), 2)
        self.assertTrue(any(fact.evidence for fact in review.facts))
        self.assertEqual(candidate.impact, "Observed in the bounded test scenario")
        self.assertEqual(
            candidate.retrieval_value, "Useful for future maintenance review"
        )

    def test_repeated_sde_assessment_deduplicates_the_same_fact_set(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added health check"
        )
        verification = self.verify("unit", "unit tests passed")
        selected = (change.fact_id, verification.fact_id)
        first = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable and tested implementation",
                selected,
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        repeated = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable and tested implementation",
                selected,
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(repeated)
        assert first is not None and repeated is not None
        self.assertEqual(first.candidate_id, repeated.candidate_id)
        self.assertEqual(len(self.store.list_sde_candidates(self.goal.goal_id)), 1)

    def test_replayed_sde_assessment_rejects_changed_proposal_context(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added a scoped readiness check"
        )
        verification = self.verify("unit", "Readiness regression passed")
        selected = (change.fact_id, verification.fact_id)
        self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The readiness check is durable and verified",
                selected,
                impact="Observed behavior is covered by a passing test",
                retrieval_value="Helps maintainers trace the readiness contract",
            )
        )
        with self.assertRaisesRegex(ConflictError, "changed its proposal context"):
            self.service.sde_assess(
                SDEAssessmentRequest(
                    self.goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "The readiness check is durable and verified",
                    selected,
                    impact="Expected production impact is unmeasured",
                    retrieval_value="Helps maintainers trace the readiness contract",
                )
            )

    def test_sde_assessment_requires_compact_impact_and_retrieval_value(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added another readiness check"
        )
        verification = self.verify("unit", "Readiness regression passed")
        with self.assertRaisesRegex(ValueError, "SDE impact must contain"):
            self.service.sde_assess(
                SDEAssessmentRequest(
                    self.goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "The readiness change is durable",
                    (change.fact_id, verification.fact_id),
                    impact=" ",
                    retrieval_value="Useful for future maintenance review",
                )
            )

    def test_review_queue_detail_is_bounded_and_project_scoped(self) -> None:
        """Show reviewers only selected facts and the goal in their project."""

        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added an evidence-backed change"
        )
        verification = self.verify("unit", "unit tests passed")
        candidate = self.service.sde_assess(
            SDEAssessmentRequest(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "The implementation is durable and directly verified",
                (change.fact_id, verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None

        other_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        other_goal = other_service.goal_start(
            "Other project's work",
            (SuccessCriterion("done", "Other project check passes"),),
        )
        other_change, _ = other_service.goal_fact(
            other_goal.goal_id, FactKind.CHANGE, "Other project's change"
        )
        other_verification, _ = other_service.goal_fact(
            other_goal.goal_id,
            FactKind.VERIFICATION,
            "Other project's check passed",
            criterion_id="done",
            evidence=(self.proof("other-project-check"),),
        )
        other_candidate = other_service.sde_assess(
            SDEAssessmentRequest(
                other_goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Other project change has direct evidence",
                (other_change.fact_id, other_verification.fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert other_candidate is not None

        queue = self.service.sde_review_queue(limit=1)
        self.assertEqual([item.candidate.candidate_id for item in queue], [candidate.candidate_id])
        detail = self.service.sde_review_detail(candidate.candidate_id)
        self.assertEqual(detail.goal.goal_id, self.goal.goal_id)
        self.assertEqual(
            {item.fact_id for item in detail.facts},
            {change.fact_id, verification.fact_id},
        )
        self.assertIsNone(detail.receipt)
        with self.assertRaises(LookupError):
            self.service.sde_review_detail(other_candidate.candidate_id)
        with self.assertRaises(ValueError):
            self.service.sde_review_queue(limit=0)
