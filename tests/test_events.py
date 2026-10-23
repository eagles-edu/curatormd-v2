"""Tests for bounded, versioned lifecycle event contracts."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence

from curatormd_v2.events import (
    EventEnvelope,
    EventDisposition,
    FactRecorded,
    GoalActivityObserved,
    GoalBlocked,
    GoalCancelled,
    GoalDeferred,
    GoalFinishRequested,
    GoalReopened,
    GoalSuperseded,
    GoalStarted,
)
from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    EventOrderError,
    EvidenceVerificationContext,
    GoalStatus,
)
from curatormd_v2.store import (
    ConflictError,
    CuratorStore,
    EventInboxCapacityError,
    NotFoundError,
)
from curatormd_v2.models import (
    ArtifactRef,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    SuccessCriterion,
)


class EventInboxTests(unittest.TestCase):
    """Check durable event acceptance and compact replay receipts."""

    def setUp(self) -> None:
        self.temp_dir = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.database = Path(self.temp_dir) / "curator.sqlite3"
        self.stage = Path(self.temp_dir) / "stage"
        self.stage.mkdir()
        self.store = CuratorStore(self.database)
        self.addCleanup(self.store.close)
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), project_id="project-a"
        )
        self.event = EventEnvelope(
            event_id="stable-event-1",
            project_id="project-a",
            payload=GoalStarted(
                goal_id="goal-1",
                problem="Record project task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
                checklist_id="tasks",
                checklist_version="sha256:" + "b" * 64,
                checklist_source_text="- [ ] Record project task",
            ),
        )

    def test_acceptance_is_durable_and_same_event_id_is_idempotent(self) -> None:
        """Persist one acceptance and reuse it after store restart."""

        first, inserted_first = self.store.ingest_event(self.event)
        second, inserted_second = self.store.ingest_event(self.event)

        self.assertTrue(inserted_first)
        self.assertFalse(inserted_second)
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)

        self.store.close()
        reopened = CuratorStore(self.database)
        try:
            self.assertEqual(
                reopened.event_receipt("project-a", "stable-event-1"), first
            )
            self.assertEqual(len(reopened.pending_events(project_id="project-a")), 1)
        finally:
            reopened.close()

    def test_cancel_and_supersede_are_idempotent_lifecycle_events(self) -> None:
        self.service.process_event(self.event)
        cancelled_event = EventEnvelope(
            "cancel-goal-event",
            "project-a",
            GoalCancelled("goal-1", "Request withdrawn"),
        )
        cancelled_receipt = self.service.process_event(cancelled_event)
        self.assertEqual(cancelled_receipt.status.value, "processed")
        self.assertEqual(
            self.service.process_event(cancelled_event), cancelled_receipt
        )
        self.assertEqual(
            self.service.goal_status("goal-1").goal.status, GoalStatus.CANCELLED
        )

        replacement = self.service.goal_start(
            "Replacement work",
            (SuccessCriterion("done", "Replacement is complete"),),
        )
        prior = self.service.goal_start(
            "Prior work", (SuccessCriterion("done", "Prior work is complete"),)
        )
        superseded_event = EventEnvelope(
            "supersede-goal-event",
            "project-a",
            GoalSuperseded(prior.goal_id, replacement.goal_id, "Scope changed"),
        )
        receipt = self.service.process_event(superseded_event)
        self.assertEqual(receipt.status.value, "processed")
        self.assertEqual(
            self.service.goal_status(prior.goal_id).goal.superseded_by_goal_id,
            replacement.goal_id,
        )

    def test_stale_status_event_fails_without_overwriting_goal_state(self) -> None:
        self.service.process_event(self.event)
        deferred = EventEnvelope(
            "defer-at-rev-1",
            "project-a",
            GoalDeferred("goal-1", "Waiting for fixture", "Request fixture", 1),
        )
        blocked_stale = EventEnvelope(
            "block-stale-rev-1",
            "project-a",
            GoalBlocked("goal-1", "Fixture missing", "Ask test owner", 1),
        )

        self.assertEqual(self.service.process_event(deferred).status.value, "processed")
        failed = self.service.process_event(blocked_stale)

        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, ConflictError.__name__)
        snapshot = self.service.goal_status("goal-1")
        self.assertEqual(snapshot.goal.status, GoalStatus.DEFERRED)
        self.assertEqual(snapshot.goal.lifecycle_revision, 2)
        self.assertEqual(len(snapshot.facts), 1)

    def test_global_event_receipt_ceiling_is_shared_and_never_prunes(self) -> None:
        with patch("curatormd_v2.store.MAX_EVENT_RECEIPTS_GLOBAL", 1):
            accepted = self.service.process_event(self.event)
            self.assertEqual(accepted.status.value, "processed")
            replayed = self.service.process_event(self.event)
            self.assertEqual(replayed, accepted)

            other_service = CuratorService(
                self.store, ArtifactPurger(self.stage), project_id="project-b"
            )
            second_event = EventEnvelope(
                "global-cap-second",
                "project-b",
                GoalStarted(
                    "goal-b",
                    "A second project's event",
                    (SuccessCriterion("done", "Task is complete"),),
                ),
            )
            with self.assertRaises(EventInboxCapacityError):
                other_service.process_event(second_event)
            with self.assertRaises(NotFoundError):
                self.store.event_receipt("project-b", second_event.event_id)
            with self.assertRaises(NotFoundError):
                self.store.get_goal("goal-b", "project-b")

            usage_a = self.store.project_storage_usage("project-a")
            usage_b = self.store.project_storage_usage("project-b")
            self.assertEqual(usage_a.global_event_inbox.receipt_count, 1)
            self.assertEqual(usage_b.global_event_inbox.receipt_count, 1)
            self.assertFalse(usage_a.global_event_inbox.can_accept_new_event)
            self.assertIsNotNone(usage_a.global_event_inbox.open_gate)
            self.assertEqual(usage_a.event_receipt_count, 1)
            self.assertEqual(usage_b.event_receipt_count, 0)

    def test_global_event_byte_ceiling_rejects_before_receipt_write(self) -> None:
        with patch("curatormd_v2.store.MAX_EVENT_RECEIPT_BYTES_GLOBAL", 10):
            with self.assertRaises(EventInboxCapacityError):
                self.service.process_event(self.event)
            with self.assertRaises(NotFoundError):
                self.store.event_receipt("project-a", self.event.event_id)
            usage = self.store.project_storage_usage("project-a")
            self.assertEqual(usage.global_event_inbox.receipt_count, 0)
            self.assertFalse(usage.global_event_inbox.can_accept_new_event)

    def test_global_usage_accounts_for_unassigned_payload_scrub_rows(self) -> None:
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_payload_scrub_queue
                   (project_id, event_id, queued_at, attempts, last_error_code)
                   VALUES (NULL, NULL, ?, ?, ?)""",
                ("2026-10-23T00:00:00+00:00", 2, "wal_checkpoint_busy"),
            )

        global_usage = self.store.global_event_inbox_usage()
        project_usage = self.store.project_storage_usage("project-a")
        self.assertEqual(global_usage.payload_scrub_queue.record_count, 1)
        self.assertGreater(global_usage.payload_scrub_queue.logical_bytes, 0)
        self.assertEqual(
            global_usage.payload_scrub_queue.unassigned_record_count,
            1,
        )
        self.assertEqual(
            global_usage.payload_scrub_queue.unassigned_logical_bytes,
            global_usage.payload_scrub_queue.logical_bytes,
        )
        self.assertEqual(
            project_usage.global_event_inbox.payload_scrub_queue.unassigned_record_count,
            1,
        )
        self.assertEqual(project_usage.event_payload_scrub_count, 0)

    def test_event_id_reuse_with_different_content_is_a_conflict(self) -> None:
        """Reject an event ID that is reused for changed content."""

        self.store.ingest_event(self.event)
        conflicting = EventEnvelope(
            event_id=self.event.event_id,
            project_id=self.event.project_id,
            payload=GoalStarted(
                goal_id="goal-1",
                problem="A different task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
            ),
        )

        with self.assertRaisesRegex(ConflictError, "different payload"):
            self.store.ingest_event(conflicting)

    def test_source_sequence_gap_is_retryable_and_does_not_apply_facts(self) -> None:
        """Hold a delayed event until its source predecessor is processed."""

        start = EventEnvelope(
            "ordered-start",
            "project-a",
            self.event.payload,
            source_id="codex-session-1",
            source_sequence=1,
        )
        self.assertEqual(self.service.process_event(start).status.value, "processed")
        delayed = EventEnvelope(
            "ordered-third",
            "project-a",
            FactRecorded(
                "goal-1", "ordered-fact-3", FactKind.CHANGE, "Third fact"
            ),
            source_id="codex-session-1",
            source_sequence=3,
        )

        failed = self.service.process_event(delayed)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, EventOrderError.__name__)
        self.assertEqual(self.service.goal_status("goal-1").facts, ())

        second = EventEnvelope(
            "ordered-second",
            "project-a",
            FactRecorded("goal-1", "ordered-fact-2", FactKind.CHANGE, "Second fact"),
            source_id="codex-session-1",
            source_sequence=2,
        )
        self.assertEqual(self.service.process_event(second).status.value, "processed")
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", delayed.event_id),
            )
        self.assertEqual(self.service.process_event(delayed).status.value, "processed")
        facts = self.service.goal_status("goal-1").facts
        self.assertEqual(
            [item.fact_id for item in facts], ["ordered-fact-2", "ordered-fact-3"]
        )
        self.assertEqual(self.service.process_event(delayed).status.value, "processed")

    def test_terminal_activity_is_suppressed_once_and_reopen_resumes_source_order(self) -> None:
        """A durable suppressed activity advances ordering and stays suppressed on replay."""

        class TestVerifier:  # pylint: disable=too-few-public-methods
            """Approve deterministic evidence for the lifecycle fixture."""

            def attest(
                self,
                evidence: EvidenceRef,
                context: EvidenceVerificationContext,
            ) -> EvidenceAttestation:
                """Return the fixed test attestation for this evidence."""

                return attest_test_evidence(evidence, context)

        verified_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="project-a",
        )
        verified_service.process_event(self.event)
        proof = EvidenceRef(
            "test", "suite://terminal-reopen", "e" * 64, EvidenceOutcome.PASSED
        )
        verified_service.process_event(
            EventEnvelope(
                "terminal-proof",
                "project-a",
                FactRecorded(
                    "goal-1", "terminal-proof-fact", FactKind.VERIFICATION,
                    "Completion criterion verified", "recorded", (proof,),
                ),
            )
        )
        verified_service.process_event(
            EventEnvelope(
                "terminal-finish", "project-a",
                GoalFinishRequested("goal-1", "Verified task is complete"),
            )
        )
        self.assertEqual(
            verified_service.goal_status("goal-1").goal.status, GoalStatus.COMPLETE
        )

        activity = EventEnvelope(
            "late-hermes-activity",
            "project-a",
            GoalActivityObserved(
                "goal-1", "late-hermes-fact", FactKind.CHANGE,
                "A turn completed after the goal was closed.",
            ),
            source_id="hermes-profile-project",
            source_sequence=1,
        )
        suppressed = verified_service.process_event(activity)
        self.assertEqual(suppressed.status.value, "processed")
        self.assertEqual(
            suppressed.disposition, EventDisposition.SUPPRESSED_NONACTIVE_GOAL
        )
        before_reopen = verified_service.goal_status("goal-1").facts
        self.assertNotIn("late-hermes-fact", {fact.fact_id for fact in before_reopen})
        self.assertEqual(verified_service.process_event(activity), suppressed)

        reopened = EventEnvelope(
            "reopen-goal",
            "project-a",
            GoalReopened("goal-1", "Follow-up needed", "Rerun the task", 2),
            source_id="hermes-profile-project",
            source_sequence=2,
        )
        reopened_receipt = verified_service.process_event(reopened)
        self.assertEqual(reopened_receipt.disposition, EventDisposition.APPLIED)

        after_reopen = EventEnvelope(
            "post-reopen-hermes-activity",
            "project-a",
            GoalActivityObserved(
                "goal-1", "post-reopen-fact", FactKind.CHANGE,
                "A turn completed after reopening.",
            ),
            source_id="hermes-profile-project",
            source_sequence=3,
        )
        applied = verified_service.process_event(after_reopen)
        self.assertEqual(applied.disposition, EventDisposition.APPLIED)
        self.assertEqual(
            verified_service.store.get_fact("post-reopen-fact", "project-a").bullet,
            "A turn completed after reopening.",
        )

    def test_failure_receipt_rejects_unbounded_or_free_form_error_text(self) -> None:
        """Keep raw exception or user-provided text out of the event ledger."""

        self.store.ingest_event(self.event)
        with self.assertRaisesRegex(ValueError, "safe identifier"):
            self.store.mark_event_failed(
                "project-a", "stable-event-1", "secret value\nand more"
            )

    def test_failure_is_retryable_and_processing_discards_payload(self) -> None:
        """Retain failed payload for retry, then reduce success to a receipt."""

        self.store.ingest_event(self.event)
        failed = self.store.mark_event_failed(
            "project-a", "stable-event-1", "adapter_unavailable"
        )
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "adapter_unavailable")
        assert failed.next_attempt_at is not None
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())

        scheduled = datetime.fromisoformat(failed.next_attempt_at)
        remaining = (scheduled - datetime.now(UTC)).total_seconds()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 5)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", "stable-event-1"),
            )
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)

        processed = self.store.mark_event_processed("project-a", "stable-event-1")

        self.assertEqual(processed.status.value, "processed")
        self.assertIsNotNone(processed.processed_at)
        self.assertIsNone(processed.next_attempt_at)
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())
        repeated, inserted = self.store.ingest_event(self.event)
        self.assertFalse(inserted)
        self.assertEqual(repeated, processed)

    def test_pending_events_can_be_read_by_project_without_cross_scope_leak(self) -> None:
        """Filter inbox reads by project and enforce the caller's batch bound."""

        self.store.ingest_event(self.event)
        other_project = EventEnvelope(
            event_id="stable-event-2",
            project_id="project-b",
            payload=GoalStarted(
                goal_id="goal-2",
                problem="Other project task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
            ),
        )
        self.store.ingest_event(other_project)

        self.assertEqual(
            [event.project_id for event in self.store.pending_events(project_id="project-a")],
            ["project-a"],
        )
        self.assertEqual(len(self.store.pending_events(limit=1)), 1)
        with self.assertRaises(ValueError):
            self.store.pending_events(limit=1001)

    def test_service_applies_project_event_atomically_and_replay_is_safe(self) -> None:
        """Apply a start and finish event once while preserving open truth."""

        started = self.service.process_event(self.event)
        snapshot = self.service.goal_status("goal-1")
        self.assertEqual(snapshot.goal.checklist_id, "tasks")
        self.assertEqual(snapshot.goal.checklist_version, "sha256:" + "b" * 64)
        self.assertEqual(
            snapshot.goal.checklist_source_text, "- [ ] Record project task"
        )
        repeated = self.service.process_event(self.event)
        finish_event = EventEnvelope(
            event_id="finish-event-1",
            project_id="project-a",
            payload=GoalFinishRequested("goal-1", "Claimed complete"),
        )

        finish_receipt = self.service.process_event(finish_event)

        self.assertEqual(started.status.value, "processed")
        self.assertEqual(repeated, started)
        self.assertEqual(snapshot.goal.project_id, "project-a")
        self.assertEqual(finish_receipt.status.value, "processed")
        self.assertEqual(
            self.service.goal_status("goal-1").goal.status, GoalStatus.OPEN
        )
        self.assertEqual(len(self.store.list_goals(project_id="project-a")), 1)

    def test_failed_event_has_no_partial_ledger_effect_and_can_retry(self) -> None:
        """Rollback a failed event, then allow an explicit retry to succeed."""

        fact_event = EventEnvelope(
            event_id="orphan-fact",
            project_id="project-a",
            payload=FactRecorded(
                goal_id="goal-later",
                fact_id="fact-later",
                kind=FactKind.CHANGE,
                bullet="Added the work item",
            ),
        )

        failed = self.service.process_event(fact_event)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "NotFoundError")
        self.assertEqual(self.store.list_goals(project_id="project-a"), ())
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())
        premature = self.service.process_event(fact_event)
        self.assertEqual(premature, failed)
        self.assertEqual(premature.attempts, 1)

        self.service.goal_start(
            "Create an event goal",
            (SuccessCriterion("change", "Change fact is recorded"),),
            goal_id="goal-later",
        )
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", fact_event.event_id),
            )
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)
        retried = self.service.process_event(fact_event)

        self.assertEqual(retried.status.value, "processed")
        self.assertEqual(
            self.service.goal_status("goal-later").facts[0].fact_id,
            "fact-later",
        )
        recorded = self.store.get_fact("fact-later", "project-a")
        self.assertEqual(recorded.source_event_id, fact_event.event_id)
        self.assertIn("source event: orphan-fact", recorded.as_bullet())
        self.assertIn(
            "source event `orphan-fact`",
            self.service.goal_report("goal-later"),
        )

    def test_storage_usage_attributes_failed_payloads_to_project_and_event_class(self) -> None:
        """Count retry payload bytes without leaking other projects' events."""

        failed_event = EventEnvelope(
            event_id="usage-failed-event",
            project_id="project-a",
            payload=FactRecorded(
                goal_id="missing-goal",
                fact_id="usage-fact",
                kind=FactKind.CHANGE,
                bullet="Retryable project event",
            ),
        )
        self.assertEqual(self.service.process_event(failed_event).status.value, "failed")

        project_usage = self.store.project_storage_usage("project-a")
        other_usage = self.store.project_storage_usage("project-b")

        self.assertEqual(project_usage.event_receipt_count, 1)
        self.assertGreater(project_usage.event_payload_bytes_received, 0)
        self.assertGreater(project_usage.event_payload_bytes_retained, 0)
        self.assertEqual(
            [(item.event_type, item.status) for item in project_usage.event_classes],
            [("fact.recorded", "failed")],
        )
        self.assertEqual(other_usage.event_receipt_count, 0)
        self.assertEqual(other_usage.event_classes, ())

    def test_storage_usage_counts_every_event_inbox_column(self) -> None:
        """Include every stored event field in project and global logical bytes."""

        event = EventEnvelope(
            event_id="accounting-event",
            project_id="project-a",
            payload=FactRecorded(
                goal_id="not-yet-recorded",
                fact_id="accounting-fact",
                kind=FactKind.CHANGE,
                bullet="Count this event row exactly",
            ),
            source_id="accounting-source",
            source_sequence=987654,
        )
        self.store.ingest_event(event)
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (event.project_id, event.event_id),
            ).fetchone()
        assert row is not None
        expected_bytes = sum(
            len(value if isinstance(value, bytes) else str(value).encode("utf-8"))
            for value in row
            if value is not None
        )

        project_usage = self.store.project_storage_usage(event.project_id)
        global_usage = self.store.global_event_inbox_usage()

        self.assertEqual(project_usage.logical_record_bytes, expected_bytes)
        self.assertEqual(global_usage.retained_record_bytes, expected_bytes)
        self.assertEqual(project_usage.event_payload_bytes_received, row["payload_bytes"])
        self.assertEqual(
            project_usage.event_payload_bytes_retained,
            len(row["payload_json"].encode("utf-8")),
        )

    def test_project_scoped_service_cannot_mutate_another_project_goal(self) -> None:
        """Do not resolve goal IDs across project ownership boundaries."""

        self.service.process_event(self.event)
        other_service = CuratorService(
            self.store, ArtifactPurger(self.stage), project_id="project-b"
        )
        cross_project_fact = EventEnvelope(
            event_id="cross-project-fact",
            project_id="project-b",
            payload=FactRecorded(
                goal_id="goal-1",
                fact_id="other-fact",
                kind=FactKind.CHANGE,
                bullet="Must not cross the project boundary",
            ),
        )

        receipt = other_service.process_event(cross_project_fact)

        self.assertEqual(receipt.status.value, "failed")
        self.assertEqual(receipt.last_error_code, "NotFoundError")
        self.assertEqual(self.service.goal_status("goal-1").facts, ())
        self.assertEqual(other_service.goal_list(), ())

    def test_defer_and_block_events_set_truthful_state_and_next_action(self) -> None:
        """Apply deferred and blocked outcomes without losing their follow-up."""

        self.service.process_event(self.event)
        deferred = EventEnvelope(
            event_id="defer-1",
            project_id="project-a",
            payload=GoalDeferred("goal-1", "Waiting for test data", "Request fixture"),
        )
        blocked = EventEnvelope(
            event_id="block-1",
            project_id="project-a",
            payload=GoalBlocked(
                "goal-1", "fixture unavailable", "Ask test owner", 2
            ),
        )

        self.assertEqual(self.service.process_event(deferred).status.value, "processed")
        deferred_goal = self.service.goal_status("goal-1").goal
        self.assertEqual(deferred_goal.status, GoalStatus.DEFERRED)
        self.assertEqual(deferred_goal.next_action, "Request fixture")
        self.assertEqual(self.service.process_event(blocked).status.value, "processed")
        blocked_goal = self.service.goal_status("goal-1").goal
        self.assertEqual(blocked_goal.status, GoalStatus.BLOCKED)
        self.assertEqual(blocked_goal.next_action, "Ask test owner")

    def test_verified_fact_event_can_complete_all_criteria(self) -> None:
        """Use the configured evidence verifier before event-driven completion."""

        store = self.store

        class TestVerifier:  # pylint: disable=too-few-public-methods
            """Verify the synthetic evidence used by this event test."""

            def attest(
                self, evidence: EvidenceRef, context: EvidenceVerificationContext
            ):
                """Attest only the explicit test-proof locator."""

                if store.transaction_active:
                    raise AssertionError(
                        "event evidence verification held a SQLite transaction"
                    )
                return (
                    attest_test_evidence(evidence, context)
                    if evidence.locator.startswith("test-proof:")
                    else None
                )

        verified_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="project-a",
        )
        verified_service.process_event(self.event)
        proof = EvidenceRef(
            "test", "test-proof:criterion", "d" * 64, EvidenceOutcome.PASSED
        )
        fact_event = EventEnvelope(
            event_id="verified-fact",
            project_id="project-a",
            payload=FactRecorded(
                "goal-1",
                "verified-fact-1",
                FactKind.VERIFICATION,
                "Criterion verified",
                "recorded",
                (proof,),
            ),
        )
        finish_event = EventEnvelope(
            "verified-finish",
            "project-a",
            GoalFinishRequested("goal-1", "Criterion verified"),
        )

        self.assertEqual(verified_service.process_event(fact_event).status.value, "processed")
        self.assertEqual(verified_service.process_event(finish_event).status.value, "processed")
        self.assertEqual(
            verified_service.goal_status("goal-1").goal.status, GoalStatus.COMPLETE
        )

    def test_legacy_goal_schema_migrates_to_default_project(self) -> None:
        """Preserve pre-project goals as members of the default project."""

        legacy_database = Path(self.temp_dir) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_database)
        connection.execute(
            """CREATE TABLE goals (
                goal_id TEXT PRIMARY KEY, problem TEXT NOT NULL,
                criteria_json TEXT NOT NULL, owner TEXT, checklist_id TEXT,
                status TEXT NOT NULL, next_action TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-goal",
                "Legacy task",
                '[{"criterion_id":"c","description":"Works"}]',
                None,
                None,
                "active",
                None,
                "2026-10-18T00:00:00+00:00",
                "2026-10-18T00:00:00+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-complete-goal",
                "Legacy completed task",
                '[{"criterion_id":"c","description":"Works"}]',
                None,
                None,
                "complete",
                None,
                "2026-10-18T00:00:00+00:00",
                "2026-10-18T00:00:00+00:00",
            ),
        )
        connection.commit()
        connection.close()
        os.chmod(legacy_database, stat.S_IRUSR | stat.S_IWUSR)

        migrated = CuratorStore(legacy_database)
        self.addCleanup(migrated.close)

        self.assertEqual(migrated.get_goal("legacy-goal").project_id, "default")
        self.assertEqual(migrated.get_goal("legacy-goal").lifecycle_revision, 2)
        self.assertEqual(
            migrated.get_goal("legacy-complete-goal").lifecycle_revision, 2
        )
        history = migrated.list_goal_criteria_versions("legacy-goal", "default")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].criteria, (SuccessCriterion("c", "Works"),))
        self.assertEqual(history[0].reason, "Initial criteria")
        stage = Path(self.temp_dir) / "legacy-stage"
        stage.mkdir()
        legacy_service = CuratorService(
            migrated, ArtifactPurger(stage), project_id="default"
        )
        stale_legacy_event = EventEnvelope(
            "legacy-unversioned-defer",
            "default",
            GoalDeferred("legacy-goal", "Legacy producer", "Refresh status"),
        )
        self.assertEqual(
            legacy_service.process_event(stale_legacy_event).status.value, "failed"
        )
        self.assertEqual(
            legacy_service.goal_status("legacy-goal").goal.lifecycle_revision, 2
        )

    def test_legacy_event_inbox_schema_migrates_for_usage_reporting(self) -> None:
        """Upgrade old inbox rows without misclassifying unknown byte totals."""

        legacy_database = Path(self.temp_dir) / "legacy-events.sqlite3"
        connection = sqlite3.connect(legacy_database)
        connection.execute(
            """CREATE TABLE event_inbox (
                project_id TEXT NOT NULL, event_id TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL, payload_json TEXT,
                status TEXT NOT NULL, received_at TEXT NOT NULL,
                processed_at TEXT, last_error TEXT,
                PRIMARY KEY(project_id, event_id)
            )"""
        )
        connection.execute(
            """INSERT INTO event_inbox VALUES
               ('legacy-project', 'legacy-event', ?, NULL, 'processed',
                '2026-10-18T00:00:00+00:00', '2026-10-18T00:00:01+00:00', NULL)""",
            ("a" * 64,),
        )
        connection.commit()
        connection.close()
        os.chmod(legacy_database, stat.S_IRUSR | stat.S_IWUSR)

        migrated = CuratorStore(legacy_database)
        self.addCleanup(migrated.close)
        usage = migrated.project_storage_usage("legacy-project")

        self.assertEqual(usage.event_receipt_count, 1)
        self.assertEqual(usage.event_payload_bytes_received, 0)
        self.assertEqual(
            [(item.event_type, item.status) for item in usage.event_classes],
            [("legacy.unknown", "processed")],
        )


class EventSequencePersistenceTests(unittest.TestCase):
    """Check ordered event persistence and project-scoped cursor storage."""

    def setUp(self) -> None:
        self.temp_dir = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.database = Path(self.temp_dir) / "curator.sqlite3"
        self.stage = Path(self.temp_dir) / "stage"
        self.stage.mkdir()
        self.store = CuratorStore(self.database)
        self.addCleanup(self.store.close)

    def test_storage_usage_counts_project_owned_auxiliary_records(self) -> None:
        """Count project cursors and staging metadata without exposing IDs."""

        for project_id in ("project-a", "project-b"):
            service = CuratorService(
                self.store,
                ArtifactPurger(self.stage),
                project_id=project_id,
            )
            service.process_event(
                EventEnvelope(
                    f"cursor-event-{project_id}",
                    project_id,
                    GoalStarted(
                        f"cursor-goal-{project_id}",
                        "Persist one ordered source event",
                        (SuccessCriterion("done", "The event is processed"),),
                    ),
                    source_id="bounded-source",
                    source_sequence=1,
                )
            )
            self.store.record_staging_artifact_time(
                project_id,
                ArtifactRef(
                    f"{project_id}/temporary/import.json",
                    "d" * 64,
                    device_id=1,
                    inode_id=2,
                    occurrence_id="c" * 32,
                ),
            )

        usage_a = self.store.project_storage_usage("project-a")
        usage_b = self.store.project_storage_usage("project-b")
        self.assertEqual(usage_a.event_cursor_count, 1)
        self.assertEqual(usage_b.event_cursor_count, 1)
        self.assertGreater(usage_a.event_cursor_record_bytes, 0)
        self.assertGreater(usage_b.event_cursor_record_bytes, 0)
        self.assertEqual(usage_a.staging_artifact_time_count, 1)
        self.assertEqual(usage_b.staging_artifact_time_count, 1)
        self.assertGreater(usage_a.staging_artifact_time_record_bytes, 0)
        self.assertGreater(usage_b.staging_artifact_time_record_bytes, 0)
        self.assertEqual(usage_a.staging_artifact_occurrence_count, 1)
        self.assertEqual(usage_b.staging_artifact_occurrence_count, 1)
        self.assertGreater(usage_a.staging_artifact_occurrence_record_bytes, 0)
        self.assertGreater(usage_b.staging_artifact_occurrence_record_bytes, 0)
        self.assertGreaterEqual(
            usage_a.logical_record_bytes,
            usage_a.event_cursor_record_bytes
            + usage_a.staging_artifact_time_record_bytes
            + usage_a.staging_artifact_occurrence_record_bytes,
        )
        self.assertGreaterEqual(
            usage_b.logical_record_bytes,
            usage_b.event_cursor_record_bytes
            + usage_b.staging_artifact_time_record_bytes
            + usage_b.staging_artifact_occurrence_record_bytes,
        )

    def test_terminal_parent_reopen_failure_keeps_one_receipt_and_source_cursor(self) -> None:
        """Rejected ordered reopen retries retain one receipt and do not advance."""

        class TestVerifier:  # pylint: disable=too-few-public-methods
            """Approve deterministic evidence for the completed child fixture."""

            def attest(
                self,
                evidence: EvidenceRef,
                context: EvidenceVerificationContext,
            ) -> EvidenceAttestation:
                """Return deterministic evidence provenance for this fixture."""

                return attest_test_evidence(evidence, context)

        verified_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="project-a",
        )
        parent = verified_service.goal_start(
            "Terminal parent",
            (SuccessCriterion("parent", "Parent is complete"),),
        )
        child = verified_service.goal_start(
            "Completed child",
            (SuccessCriterion("child", "Child is complete"),),
            parent_goal_id=parent.goal_id,
        )
        verified_service.goal_fact(
            child.goal_id,
            FactKind.VERIFICATION,
            "Child criterion verified",
            criterion_id="child",
            evidence=(
                EvidenceRef(
                    "test",
                    "test-proof:terminal-parent-reopen",
                    "f" * 64,
                    EvidenceOutcome.PASSED,
                ),
            ),
        )
        completed_child = verified_service.goal_finish(child.goal_id, "Child complete")
        verified_service.goal_cancel(parent.goal_id, "Parent scope withdrawn")
        before_goal = self.store.get_goal(child.goal_id)
        before_facts = self.store.list_facts(child.goal_id)
        event = EventEnvelope(
            "ordered-reopen-under-terminal-parent",
            "project-a",
            GoalReopened(
                child.goal_id,
                "Resume after the parent was retired",
                "Start a correctly linked continuation",
                completed_child.lifecycle_revision,
            ),
            source_id="hermes-curator-test",
            source_sequence=1,
        )

        failed = verified_service.process_event(event)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, ConflictError.__name__)
        self.assertEqual(failed.attempts, 1)
        replay = verified_service.process_event(event)
        self.assertEqual(
            (replay.project_id, replay.event_id),
            (failed.project_id, failed.event_id),
        )
        self.assertEqual(replay.status, failed.status)
        self.assertEqual(replay.last_error_code, failed.last_error_code)
        self.assertEqual(replay.attempts, 1)

        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            )
        retried = verified_service.process_event(event)
        self.assertEqual(
            (retried.project_id, retried.event_id),
            (failed.project_id, failed.event_id),
        )
        self.assertEqual(retried.status, failed.status)
        self.assertEqual(retried.last_error_code, failed.last_error_code)
        self.assertEqual(retried.attempts, 2)
        with self.store.transaction() as connection:
            cursor = connection.execute(
                "SELECT last_sequence FROM event_cursors "
                "WHERE project_id = ? AND source_id = ?",
                ("project-a", "hermes-curator-test"),
            ).fetchone()
            receipt_count = connection.execute(
                "SELECT COUNT(*) FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            ).fetchone()[0]
        self.assertIsNone(cursor)
        self.assertEqual(receipt_count, 1)
        self.assertEqual(self.store.event_receipt("project-a", event.event_id), retried)
        self.assertEqual(self.store.get_goal(child.goal_id), before_goal)
        self.assertEqual(self.store.list_facts(child.goal_id), before_facts)

if __name__ == "__main__":
    unittest.main()
