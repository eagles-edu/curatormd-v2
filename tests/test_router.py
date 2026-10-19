"""Durable event-router retry, ordering, and queue visibility tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest

from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    DurableEventRouter,
    EventEnvelope,
    EventInboxStatus,
    FactKind,
    FactRecorded,
    GoalActivated,
    GoalStarted,
    GoalStatus,
    SuccessCriterion,
)


class DurableEventRouterTests(unittest.TestCase):
    """Verify durable delivery semantics without claiming host scheduling."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        root = Path(self.temporary)
        self.stage = root / "staging"
        self.stage.mkdir()
        self.database = root / "global.sqlite3"
        self.store = CuratorStore(self.database)
        self.addCleanup(self.close_current_store)
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage),
            project_id="project-a",
        )
        self.router = DurableEventRouter(
            self.store,
            {"project-a": self.service},
            max_delivery_attempts=2,
        )

    def close_current_store(self) -> None:
        """Close whichever store instance remains after a restart test."""

        self.store.close()

    def test_ordered_pending_events_resume_after_store_restart_and_replay(self) -> None:
        """Recover the durable gap, route in order, and keep replay idempotent."""

        later = EventEnvelope(
            "restart-fact",
            "project-a",
            FactRecorded(
                "restart-goal",
                "restart-fact-1",
                FactKind.CHANGE,
                "The second event survives the router restart",
            ),
            source_id="restart-producer",
            source_sequence=2,
        )
        first = EventEnvelope(
            "restart-goal-start",
            "project-a",
            GoalStarted(
                "restart-goal",
                "Resume a persisted ordered queue",
                (SuccessCriterion("fact", "The change fact is recorded"),),
                initial_status=GoalStatus.ACTIVE,
            ),
            source_id="restart-producer",
            source_sequence=1,
        )

        accepted, inserted = self.store.ingest_event(later)
        self.assertTrue(inserted)
        self.assertEqual(accepted.status, EventInboxStatus.RECEIVED)
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())

        self.store.close()
        self.store = CuratorStore(self.database)
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), project_id="project-a"
        )
        self.router = DurableEventRouter(
            self.store,
            {"project-a": self.service},
            max_delivery_attempts=2,
        )
        self.assertEqual(
            self.store.event_receipt("project-a", later.event_id), accepted
        )

        self.store.ingest_event(first)
        start_result = self.router.route_once()
        self.assertEqual(start_result.processed_count, 1)
        fact_result = self.router.route_once()
        self.assertEqual(fact_result.processed_count, 1)
        self.assertEqual(
            self.store.event_receipt("project-a", later.event_id).status,
            EventInboxStatus.PROCESSED,
        )
        self.assertEqual(
            [fact.fact_id for fact in self.service.goal_status("restart-goal").facts],
            ["restart-fact-1"],
        )

        repeated, inserted_again = self.store.ingest_event(later)
        self.assertFalse(inserted_again)
        self.assertEqual(repeated.status, EventInboxStatus.PROCESSED)
        self.assertEqual(
            [fact.fact_id for fact in self.service.goal_status("restart-goal").facts],
            ["restart-fact-1"],
        )

    def test_failed_event_is_quarantined_and_operator_retry_is_audited(self) -> None:
        event = EventEnvelope(
            "activation-retry-event",
            "project-a",
            GoalActivated("retry-goal", "Retry after recovery", 1),
        )
        accepted, inserted = self.store.ingest_event(event)
        self.assertTrue(inserted)
        self.assertEqual(accepted.status, EventInboxStatus.RECEIVED)

        first = self.router.route_once()
        self.assertEqual((first.attempted_count, first.failed_count), (1, 1))
        receipt = self.store.event_receipt("project-a", event.event_id)
        self.assertEqual(receipt.status, EventInboxStatus.FAILED)
        self.assertEqual(receipt.attempts, 1)
        self.assertIsNotNone(receipt.next_attempt_at)
        self.assertEqual(self.store.pending_events(), ())
        self.assertEqual(self.store.pending_events(project_id="project-b"), ())

        # Fast-forward the durable schedule rather than sleeping in the test.
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            )

        second = self.router.route_once()
        self.assertEqual(second.quarantined_count, 1)
        receipt = self.store.event_receipt("project-a", event.event_id)
        self.assertEqual(receipt.status, EventInboxStatus.QUARANTINED)
        self.assertEqual(receipt.attempts, 2)
        self.assertEqual(second.queue.quarantined_count, 1)
        self.assertEqual(second.queue.oldest_pending_received_at, None)

        self.service.goal_start(
            "Create the dependency that was missing during delivery",
            (SuccessCriterion("ready", "The goal can be activated"),),
            goal_id="retry-goal",
            initial_status=GoalStatus.PLANNED,
        )
        retried = self.store.retry_quarantined_event(
            "project-a", event.event_id, "operator-7"
        )
        self.assertEqual(retried.status, EventInboxStatus.FAILED)
        self.assertEqual(retried.attempts, 0)
        with self.store.transaction() as connection:
            audit = connection.execute(
                "SELECT actor_id FROM event_retry_audit "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            ).fetchone()
        self.assertEqual(audit["actor_id"], "operator-7")

        final = self.router.route_once()
        self.assertEqual(final.processed_count, 1)
        self.assertEqual(
            self.store.event_receipt("project-a", event.event_id).status,
            EventInboxStatus.PROCESSED,
        )
        self.assertEqual(self.service.goal_status("retry-goal").goal.status, GoalStatus.ACTIVE)
        replay = self.service.process_event(event)
        self.assertEqual(replay.status, EventInboxStatus.PROCESSED)
        self.assertEqual(len(self.service.goal_status("retry-goal").facts), 1)
        self.assertIsNone(
            self.store.event_receipt("project-a", event.event_id).next_attempt_at
        )

    def test_source_sequence_gaps_wait_and_resume_in_order(self) -> None:
        later = EventEnvelope(
            "ordered-fact",
            "project-a",
            FactRecorded(
                "ordered-goal", "ordered-fact-1", FactKind.CHANGE,
                "The ordered second event was applied",
            ),
            source_id="hermes-gptmd",
            source_sequence=2,
        )
        first = EventEnvelope(
            "ordered-start",
            "project-a",
            GoalStarted(
                "ordered-goal",
                "Preserve source ordering",
                (SuccessCriterion("done", "The second event is recorded"),),
                initial_status=GoalStatus.ACTIVE,
            ),
            source_id="hermes-gptmd",
            source_sequence=1,
        )
        self.store.ingest_event(later)
        self.assertEqual(self.store.pending_events(), ())
        self.store.ingest_event(first)

        queue = self.store.event_queue_status("project-a")
        self.assertEqual(queue.received_count, 2)
        self.assertIsNotNone(queue.oldest_pending_received_at)
        self.assertIsNotNone(queue.oldest_pending_age_seconds)
        assert queue.oldest_pending_age_seconds is not None
        self.assertGreaterEqual(queue.oldest_pending_age_seconds, 0)

        first_pass = self.router.route_once()
        self.assertEqual(first_pass.attempted_count, 1)
        self.assertEqual(first_pass.processed_count, 1)
        self.assertEqual(self.store.pending_events()[0].event_id, later.event_id)

        second_pass = self.router.route_once()
        self.assertEqual(second_pass.attempted_count, 1)
        self.assertEqual(second_pass.processed_count, 1)
        self.assertEqual(len(self.service.goal_status("ordered-goal").facts), 1)

    def test_failed_delivery_uses_persisted_exponential_retry_schedule(self) -> None:
        """Delay failed retries and increase the durable delay by attempt."""

        event = EventEnvelope(
            "backoff-event",
            "project-a",
            GoalStarted(
                "backoff-goal",
                "Retry after a transient failure",
                (SuccessCriterion("ready", "The event is eventually processed"),),
            ),
        )
        self.store.ingest_event(event)

        first = self.store.mark_event_failed(
            "project-a", event.event_id, "temporary_failure"
        )
        assert first.next_attempt_at is not None
        first_delay = (
            datetime.fromisoformat(first.next_attempt_at) - datetime.now(UTC)
        ).total_seconds()
        self.assertGreater(first_delay, 4)
        self.assertLessEqual(first_delay, 5)
        self.assertEqual(self.store.pending_events(), ())

        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            )
        second = self.store.mark_event_failed(
            "project-a", event.event_id, "temporary_failure"
        )
        assert second.next_attempt_at is not None
        second_delay = (
            datetime.fromisoformat(second.next_attempt_at) - datetime.now(UTC)
        ).total_seconds()
        self.assertGreater(second_delay, 9)
        self.assertLessEqual(second_delay, 10)

    def test_router_rejects_invalid_binding_and_batch_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "key must match"):
            DurableEventRouter(self.store, {"other-project": self.service})
        with self.assertRaisesRegex(ValueError, "between 1"):
            self.router.route_once(limit=0)


if __name__ == "__main__":
    unittest.main()
