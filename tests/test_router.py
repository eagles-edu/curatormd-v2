"""Durable event-router retry, ordering, and queue visibility tests."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from curatormd_v2 import (
    ArtifactPurger,
    backup_database,
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
    restore_database,
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

    def retry_audit_actor(self, event_id: str) -> str:
        """Read the actor recorded for one project-local retry."""

        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT actor_id FROM event_retry_audit "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event_id),
            ).fetchone()
        assert row is not None
        return str(row["actor_id"])

    def test_router_does_not_claim_events_outside_its_fixed_project_map(self) -> None:
        """An omitted project binding stays untouched in the shared inbox."""

        bound = EventEnvelope(
            "bound-project-event",
            "project-a",
            GoalStarted(
                "bound-project-goal",
                "Route one explicitly trusted project",
                (SuccessCriterion("routed", "The bound event is processed"),),
                initial_status=GoalStatus.ACTIVE,
            ),
        )
        unbound = EventEnvelope(
            "unbound-project-event",
            "project-b",
            GoalStarted(
                "unbound-project-goal",
                "Keep an event for a project outside this router map",
                (SuccessCriterion("pending", "The unbound event remains pending"),),
                initial_status=GoalStatus.ACTIVE,
            ),
        )
        self.store.ingest_event(unbound)
        self.store.ingest_event(bound)

        result = self.router.route_once()

        self.assertEqual((result.attempted_count, result.processed_count), (1, 1))
        bound_receipt = self.store.event_receipt("project-a", bound.event_id)
        self.assertEqual(bound_receipt.status, EventInboxStatus.PROCESSED)
        unbound_receipt = self.store.event_receipt("project-b", unbound.event_id)
        self.assertEqual(unbound_receipt.status, EventInboxStatus.RECEIVED)
        self.assertEqual(unbound_receipt.attempts, 0)
        self.assertEqual(
            self.store.pending_events(project_id="project-b"),
            (unbound,),
        )

    def test_idle_router_pass_retries_a_blocked_event_payload_scrub(self) -> None:
        """Retry durable privacy cleanup even when no events remain to route."""

        canary = "router-wal-canary-691c"
        event = EventEnvelope(
            "router-wal-event",
            "project-a",
            GoalStarted(
                "router-wal-goal",
                canary,
                (SuccessCriterion("routed", "The event is processed"),),
                initial_status=GoalStatus.ACTIVE,
            ),
        )
        self.store.ingest_event(event)
        reader = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        self.assertIn(
            canary,
            reader.execute(
                "SELECT payload_json FROM event_inbox WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()[0],
        )

        first = self.router.route_once()

        self.assertEqual(first.processed_count, 1)
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 1)
        reader.execute("ROLLBACK")
        reader.close()

        idle = self.router.route_once()

        self.assertEqual(idle.attempted_count, 0)
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 0)
        wal_path = Path(f"{self.database}-wal")
        wal_bytes = wal_path.read_bytes() if wal_path.exists() else b""
        self.assertNotIn(canary.encode(), wal_bytes)

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

    def test_expired_claim_recovers_after_router_process_is_killed(self) -> None:
        """A crashed process cannot strand a durable event claim forever."""

        event = EventEnvelope(
            "crashed-worker-event",
            "project-a",
            GoalStarted(
                "crashed-worker-goal",
                "Recover an event after its worker process exits abruptly",
                (SuccessCriterion("received", "The event reaches the goal ledger"),),
                initial_status=GoalStatus.ACTIVE,
            ),
        )
        self.store.ingest_event(event)
        child_code = """\
import os
import signal
import sys

from curatormd_v2 import CuratorStore

store = CuratorStore(sys.argv[1])
claimed = store.claim_pending_events("crashed-worker", lease_seconds=1)
if len(claimed) != 1 or claimed[0].event_id != "crashed-worker-event":
    os._exit(71)
os.kill(os.getpid(), signal.SIGKILL)
"""
        crashed = subprocess.run(
            [sys.executable, "-c", child_code, str(self.database)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(crashed.returncode, -signal.SIGKILL, crashed.stderr)

        deadline = time.monotonic() + 3
        while self.store.event_queue_status("project-a").expired_claim_count == 0:
            if time.monotonic() >= deadline:
                self.fail("crashed worker's event lease did not expire")
            time.sleep(0.05)

        recovery_code = """\
import json
import sys
from pathlib import Path

from curatormd_v2 import ArtifactPurger, CuratorService, CuratorStore, DurableEventRouter

store = CuratorStore(sys.argv[1])
try:
    service = CuratorService(
        store, ArtifactPurger(Path(sys.argv[2])), project_id="project-a"
    )
    router = DurableEventRouter(store, {"project-a": service})
    result = router.route_once()
    print(json.dumps({"processed": result.processed_count, "failed": result.failed_count}))
finally:
    store.close()
"""
        recovered = subprocess.run(
            [sys.executable, "-c", recovery_code, str(self.database), str(self.stage)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(
            json.loads(recovered.stdout), {"processed": 1, "failed": 0}
        )
        receipt = self.store.event_receipt("project-a", event.event_id)
        self.assertEqual(receipt.status, EventInboxStatus.PROCESSED)
        self.assertEqual(
            self.service.goal_status("crashed-worker-goal").goal.status,
            GoalStatus.ACTIVE,
        )

        backup_path = Path(self.temporary) / "post-recovery.sqlite3"
        restored_path = Path(self.temporary) / "post-recovery-restored.sqlite3"
        backup_database(self.database, backup_path)
        restore_database(backup_path, restored_path)
        restored_store = CuratorStore(restored_path)
        try:
            restored_service = CuratorService(
                restored_store,
                ArtifactPurger(self.stage),
                project_id="project-a",
            )
            self.assertEqual(
                restored_store.event_receipt("project-a", event.event_id).status,
                EventInboxStatus.PROCESSED,
            )
            self.assertEqual(
                restored_service.goal_status("crashed-worker-goal").goal.status,
                GoalStatus.ACTIVE,
            )
        finally:
            restored_store.close()
        self.assertEqual(
            self.store.event_queue_status("project-a").expired_claim_count, 0
        )
        replayed, inserted_again = self.store.ingest_event(event)
        self.assertFalse(inserted_again)
        self.assertEqual(replayed.status, EventInboxStatus.PROCESSED)
        self.assertEqual(
            self.service.goal_status("crashed-worker-goal").goal.status,
            GoalStatus.ACTIVE,
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
        self.assertEqual(self.retry_audit_actor(event.event_id), "operator-7")
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

    def test_failure_detail_is_not_exposed_while_retry_payload_is_preserved(self) -> None:
        """Keep exception text out of logs and receipts without dropping retry data."""

        payload_canary = "PRIVATE_ROUTER_PAYLOAD_CANARY"
        exception_canary = "PRIVATE_ROUTER_EXCEPTION_CANARY"
        exception_type_canary = "PRIVATE_ROUTER_EXCEPTION_TYPE_CANARY"
        private_exception_type = type(exception_type_canary, (RuntimeError,), {})
        event = EventEnvelope(
            "private-router-failure",
            "project-a",
            GoalStarted(
                "private-router-goal",
                f"Transient request detail {payload_canary}",
                (SuccessCriterion("retry", "Retry after the adapter recovers"),),
            ),
        )
        self.store.ingest_event(event)

        with patch.object(
            self.service,
            "process_event",
            side_effect=private_exception_type(exception_canary),
        ):
            with self.assertNoLogs("curatormd_v2", level="DEBUG"):
                result = self.router.route_once()

                # Make the second delivery immediately eligible so this test
                # also covers the durable quarantine transition.
                with self.store.transaction() as connection:
                    connection.execute(
                        "UPDATE event_inbox SET next_attempt_at = "
                        "'2000-01-01T00:00:00+00:00' "
                        "WHERE project_id = ? AND event_id = ?",
                        ("project-a", event.event_id),
                    )
                quarantined_result = self.router.route_once()

                retried_receipt = self.store.retry_quarantined_event(
                    "project-a", event.event_id, "operator-7"
                )
                retry_result = self.router.route_once()

        receipt = self.store.event_receipt("project-a", event.event_id)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(quarantined_result.quarantined_count, 1)
        self.assertEqual(retried_receipt.status, EventInboxStatus.FAILED)
        self.assertEqual(retried_receipt.attempts, 0)
        self.assertEqual(retry_result.failed_count, 1)
        self.assertEqual(receipt.status, EventInboxStatus.FAILED)
        self.assertEqual(receipt.attempts, 1)
        self.assertEqual(receipt.last_error_code, "unexpected_exception")
        for public_result in (result, quarantined_result, retried_receipt, retry_result, receipt):
            self.assertNotIn(exception_canary, repr(public_result))
            self.assertNotIn(exception_type_canary, repr(public_result))

        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT payload_json, last_error FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIn(payload_canary, row["payload_json"])
        self.assertNotIn(exception_canary, row["payload_json"])
        self.assertEqual(row["last_error"], "unexpected_exception")
        self.assertNotIn(exception_type_canary, row["last_error"])
        audit_actor = self.retry_audit_actor(event.event_id)
        self.assertEqual(audit_actor, "operator-7")
        self.assertNotIn(exception_canary, audit_actor)

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
