"""Cross-connection goal lifecycle ordering regressions."""

from __future__ import annotations

from pathlib import Path
import tempfile
from threading import Barrier, Event, Thread
import unittest
from unittest.mock import patch

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
    FactCapacityError,
    FactKind,
    EventInboxCapacityError,
    EventClaimError,
    GoalStatus,
    ProjectOperationalCounts,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    GoalCancelled,
    GoalStarted,
    GoalSuperseded,
)


class TestVerifier:
    """Accept only the stable fixture evidence locator."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the passing fixture locator used by concurrency tests."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:ready"
            else None
        )


class PausingStore(CuratorStore):
    """Pause immediately before append to expose lifecycle interleavings."""

    def __init__(self, database: Path) -> None:
        super().__init__(database)
        self.pause_append = False
        self.append_entered = Event()
        self.continue_append = Event()

    def append_fact(
        self, fact: Fact, project_id: str | None = None
    ) -> tuple[Fact, bool]:
        if self.pause_append:
            self.append_entered.set()
            if not self.continue_append.wait(timeout=5):
                raise TimeoutError("test did not release the paused append")
        return super().append_fact(fact, project_id)


class SnapshotInjectingStore(CuratorStore):
    """Commit a second-connection event between health aggregate queries."""

    def __init__(
        self, database: Path, writer: CuratorStore, event: EventEnvelope
    ) -> None:
        super().__init__(database)
        self.writer = writer
        self.event = event
        self.injected = False

    def project_operational_counts(self, project_id: str) -> ProjectOperationalCounts:
        if not self.injected:
            self.injected = True
            self.writer.ingest_event(self.event)
        return super().project_operational_counts(project_id)


class GoalConcurrencyTests(unittest.TestCase):
    """Prove fact append and completion serialize across SQLite connections."""

    def test_operational_health_inputs_share_one_sqlite_read_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "health.sqlite3"
            writer = CuratorStore(database)
            reader = SnapshotInjectingStore(database, writer, EventEnvelope(
                "concurrent-health-event",
                "project-a",
                GoalStarted(
                    "health-goal",
                    "Exercise snapshot isolation",
                    (SuccessCriterion("visible", "New event becomes visible"),),
                ),
            ))
            self.addCleanup(reader.close)
            self.addCleanup(writer.close)
            queue, _counts, usage = reader.project_health_inputs("project-a")

            self.assertTrue(reader.injected)
            self.assertEqual(queue.received_count, 0)
            self.assertEqual(usage.event_receipt_count, 0)
            self.assertEqual(
                reader.event_queue_status("project-a").received_count, 1
            )

    def test_competing_nonterminal_updates_reject_stale_lifecycle_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            setup_store = CuratorStore(database)
            setup_service = CuratorService(setup_store, ArtifactPurger(staging))
            goal = setup_service.goal_start(
                "Guard nonterminal status updates",
                (SuccessCriterion("done", "The task is resolved"),),
            )
            setup_store.close()

            stores = (CuratorStore(database), CuratorStore(database))
            self.addCleanup(stores[0].close)
            self.addCleanup(stores[1].close)
            services = tuple(CuratorService(store, ArtifactPurger(staging)) for store in stores)
            barrier = Barrier(3)
            outcomes: list[str] = []

            def defer() -> None:
                barrier.wait(timeout=3)
                try:
                    services[0].goal_defer(
                        goal.goal_id,
                        "Waiting on evidence",
                        "Request the evidence",
                        expected_lifecycle_revision=1,
                    )
                    outcomes.append("accepted")
                except ConflictError:
                    outcomes.append("stale")

            def block() -> None:
                barrier.wait(timeout=3)
                try:
                    services[1].goal_block(
                        goal.goal_id,
                        "Evidence source unavailable",
                        "Contact the owner",
                        expected_lifecycle_revision=1,
                    )
                    outcomes.append("accepted")
                except ConflictError:
                    outcomes.append("stale")

            threads = (Thread(target=defer), Thread(target=block))
            for thread in threads:
                thread.start()
            barrier.wait(timeout=3)
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertCountEqual(outcomes, ["accepted", "stale"])
            snapshot = services[0].goal_status(goal.goal_id)
            self.assertEqual(snapshot.goal.lifecycle_revision, 2)
            self.assertEqual(len(snapshot.facts), 1)
            self.assertIn(snapshot.goal.status, {GoalStatus.DEFERRED, GoalStatus.BLOCKED})

    def test_router_claims_are_exclusive_across_connections_and_expire_safely(self) -> None:
        """Lease one event once, then recover it after the owner disappears."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            setup_store = CuratorStore(database)
            event = EventEnvelope(
                "lease-event",
                "project-a",
                GoalStarted(
                    "lease-goal",
                    "Coordinate event workers across SQLite connections",
                    (SuccessCriterion("done", "Only the active lease owner processes it"),),
                ),
            )
            setup_store.ingest_event(event)
            setup_store.close()

            stores = (CuratorStore(database), CuratorStore(database))
            self.addCleanup(stores[0].close)
            self.addCleanup(stores[1].close)
            services = tuple(
                CuratorService(store, ArtifactPurger(staging), project_id="project-a")
                for store in stores
            )
            barrier = Barrier(3)
            claims: list[tuple[str, tuple[EventEnvelope, ...]]] = []

            def claim(index: int, owner: str) -> None:
                barrier.wait(timeout=3)
                result = stores[index].claim_pending_events(owner, lease_seconds=30)
                claims.append((owner, result))

            threads = (
                Thread(target=claim, args=(0, "worker-a")),
                Thread(target=claim, args=(1, "worker-b")),
            )
            for thread in threads:
                thread.start()
            barrier.wait(timeout=3)
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            owners_with_event = [
                (owner, events[0]) for owner, events in claims if events
            ]
            self.assertEqual(len(owners_with_event), 1)
            old_owner, claimed_event = owners_with_event[0]
            self.assertEqual(claimed_event.event_id, event.event_id)
            new_owner = "worker-b" if old_owner == "worker-a" else "worker-a"
            queue = stores[0].event_queue_status("project-a")
            self.assertEqual(queue.claimed_count, 1)

            with stores[1].transaction() as connection:
                connection.execute(
                    "UPDATE event_inbox SET lease_expires_at = "
                    "'2000-01-01T00:00:00+00:00' WHERE project_id = ? AND event_id = ?",
                    ("project-a", event.event_id),
                )
            self.assertEqual(stores[0].event_queue_status("project-a").expired_claim_count, 1)
            new_claim = stores[1].claim_pending_events(new_owner, lease_seconds=30)
            self.assertEqual(tuple(item.event_id for item in new_claim), (event.event_id,))
            stale_store = stores[0 if old_owner == "worker-a" else 1]
            with self.assertRaises(EventClaimError):
                stale_store.mark_event_processed(
                    "project-a", event.event_id, lease_owner=old_owner
                )
            with self.assertRaises(EventClaimError):
                stale_store.mark_event_failed(
                    "project-a",
                    event.event_id,
                    "stale_worker",
                    lease_owner=old_owner,
                )
            with self.assertRaises(EventClaimError):
                services[0 if old_owner == "worker-a" else 1].process_event(
                    event, lease_owner=old_owner
                )
            self.assertEqual(
                services[0 if new_owner == "worker-a" else 1]
                .process_event(event, lease_owner=new_owner)
                .status.value,
                "processed",
            )
            self.assertEqual(stores[0].event_queue_status("project-a").claimed_count, 0)

    def test_fact_validated_active_cannot_append_after_concurrent_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            setup_store = CuratorStore(database)
            setup_service = CuratorService(
                setup_store, ArtifactPurger(staging), TestVerifier()
            )
            goal = setup_service.goal_start(
                "Record a change without racing completion",
                (SuccessCriterion("ready", "The readiness check passes"),),
                goal_id="goal-race",
            )
            setup_service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The readiness check passed",
                criterion_id="ready",
                evidence=(
                    EvidenceRef(
                        "unit-test",
                        "test-proof:ready",
                        "a" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            setup_store.close()

            writer_store = PausingStore(database)
            finisher_store = CuratorStore(database)
            writer_service = CuratorService(
                writer_store, ArtifactPurger(staging), TestVerifier()
            )
            finisher_service = CuratorService(
                finisher_store, ArtifactPurger(staging), TestVerifier()
            )
            self.addCleanup(writer_store.close)
            self.addCleanup(finisher_store.close)
            writer_store.pause_append = True

            write_result: list[object] = []
            finish_result: list[object] = []
            failures: list[BaseException] = []
            finish_done = Event()

            def record_fact() -> None:
                try:
                    write_result.append(
                        writer_service.goal_fact(
                            goal.goal_id,
                            FactKind.CHANGE,
                            "Recorded the implementation change",
                        )
                    )
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # Capture worker failures so the parent test can assert them.
                    failures.append(exc)

            def finish_goal() -> None:
                try:
                    finish_result.append(
                        finisher_service.goal_finish(
                            goal.goal_id, "All criteria have passing evidence"
                        )
                    )
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # Capture worker failures so the parent test can assert them.
                    failures.append(exc)
                finally:
                    finish_done.set()

            writer = Thread(target=record_fact)
            finisher = Thread(target=finish_goal)
            writer.start()
            self.assertTrue(writer_store.append_entered.wait(timeout=3))
            finisher.start()
            try:
                self.assertFalse(
                    finish_done.wait(timeout=0.2),
                    "completion must wait while the fact transaction owns the write lock",
                )
            finally:
                writer_store.continue_append.set()
            writer.join(timeout=5)
            finisher.join(timeout=5)

            self.assertFalse(writer.is_alive())
            self.assertFalse(finisher.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(len(write_result), 1)
            self.assertEqual(len(finish_result), 1)
            completed = finisher_store.get_goal(goal.goal_id)
            self.assertEqual(completed.status, GoalStatus.COMPLETE)
            change_fact = next(
                fact
                for fact in finisher_store.list_facts(goal.goal_id)
                if fact.kind is FactKind.CHANGE
            )
            self.assertLess(change_fact.created_at, completed.updated_at)

            with self.assertRaises(ConflictError):
                writer_service.goal_fact(
                    goal.goal_id, FactKind.CHANGE, "Late unapproved fact"
                )

    def test_concurrent_cancel_and_supersede_have_one_terminal_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            initial_store = CuratorStore(database)
            initial_service = CuratorService(initial_store, ArtifactPurger(staging))
            old = initial_service.goal_start(
                "Old scope", (SuccessCriterion("done", "Old scope is done"),)
            )
            replacement = initial_service.goal_start(
                "Replacement scope",
                (SuccessCriterion("done", "Replacement scope is done"),),
            )
            initial_store.close()

            stores = (CuratorStore(database), CuratorStore(database))
            self.addCleanup(stores[0].close)
            self.addCleanup(stores[1].close)
            services = tuple(CuratorService(store, ArtifactPurger(staging)) for store in stores)
            events = (
                EventEnvelope(
                    "race-cancel",
                    "default",
                    GoalCancelled(old.goal_id, "Withdraw old scope"),
                ),
                EventEnvelope(
                    "race-supersede",
                    "default",
                    GoalSuperseded(old.goal_id, replacement.goal_id, "Replace old scope"),
                ),
            )
            barrier = Barrier(3)
            receipts: list[str] = []

            def apply(index: int) -> None:
                barrier.wait(timeout=3)
                receipt = services[index].process_event(events[index])
                receipts.append(receipt.status.value)

            threads = tuple(Thread(target=apply, args=(index,)) for index in range(2))
            for thread in threads:
                thread.start()
            barrier.wait(timeout=3)
            for thread in threads:
                thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertCountEqual(receipts, ["processed", "failed"])
            retired = services[0].goal_status(old.goal_id).goal
            self.assertIn(retired.status, {GoalStatus.CANCELLED, GoalStatus.SUPERSEDED})
            self.assertEqual(len(services[0].goal_status(old.goal_id).facts), 1)

    def test_concurrent_connections_cannot_exceed_fact_count_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            with patch("curatormd_v2.store.MAX_FACTS_PER_GOAL", 2):
                initial_store = CuratorStore(database)
                initial_service = CuratorService(
                    initial_store, ArtifactPurger(staging), TestVerifier()
                )
                goal = initial_service.goal_start(
                    "Keep a bounded fact history",
                    (SuccessCriterion("ready", "The check passes"),),
                    goal_id="goal-capacity-race",
                )
                initial_service.goal_fact(
                    goal.goal_id, FactKind.RESEARCH, "One fact remains below the cap"
                )
                initial_store.close()

                first_store = CuratorStore(database)
                second_store = CuratorStore(database)
                self.addCleanup(first_store.close)
                self.addCleanup(second_store.close)
                services = (
                    CuratorService(first_store, ArtifactPurger(staging), TestVerifier()),
                    CuratorService(second_store, ArtifactPurger(staging), TestVerifier()),
                )
                barrier = Barrier(3)
                outcomes: list[str] = []

                def append(service: CuratorService, bullet: str) -> None:
                    barrier.wait(timeout=3)
                    try:
                        service.goal_fact(goal.goal_id, FactKind.RESEARCH, bullet)
                        outcomes.append("accepted")
                    except FactCapacityError:
                        outcomes.append("capacity")

                threads = (
                    Thread(target=append, args=(services[0], "Concurrent fact A")),
                    Thread(target=append, args=(services[1], "Concurrent fact B")),
                )
                for thread in threads:
                    thread.start()
                barrier.wait(timeout=3)
                for thread in threads:
                    thread.join(timeout=5)

                self.assertTrue(all(not thread.is_alive() for thread in threads))
                self.assertCountEqual(outcomes, ["accepted", "capacity"])
                self.assertEqual(len(first_store.list_facts(goal.goal_id)), 2)

    def test_concurrent_projects_cannot_exceed_global_event_receipt_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "curator.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            first_store = CuratorStore(database)
            second_store = CuratorStore(database)
            self.addCleanup(first_store.close)
            self.addCleanup(second_store.close)
            services = (
                CuratorService(first_store, ArtifactPurger(staging), project_id="project-a"),
                CuratorService(second_store, ArtifactPurger(staging), project_id="project-b"),
            )
            events = (
                EventEnvelope(
                    "global-race-a",
                    "project-a",
                    GoalStarted(
                        "global-goal-a",
                        "Capture first project request",
                        (SuccessCriterion("done", "Task is complete"),),
                    ),
                ),
                EventEnvelope(
                    "global-race-b",
                    "project-b",
                    GoalStarted(
                        "global-goal-b",
                        "Capture second project request",
                        (SuccessCriterion("done", "Task is complete"),),
                    ),
                ),
            )
            with patch("curatormd_v2.store.MAX_EVENT_RECEIPTS_GLOBAL", 1):
                barrier = Barrier(3)
                outcomes: list[str] = []

                def ingest(index: int) -> None:
                    barrier.wait(timeout=3)
                    try:
                        services[index].process_event(events[index])
                        outcomes.append("accepted")
                    except EventInboxCapacityError:
                        outcomes.append("capacity")

                threads = (Thread(target=ingest, args=(0,)), Thread(target=ingest, args=(1,)))
                for thread in threads:
                    thread.start()
                barrier.wait(timeout=3)
                for thread in threads:
                    thread.join(timeout=5)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertCountEqual(outcomes, ["accepted", "capacity"])
            usage_a = first_store.global_event_inbox_usage()
            usage_b = second_store.global_event_inbox_usage()
            self.assertEqual(usage_a.receipt_count, 1)
            self.assertEqual(usage_b.receipt_count, 1)


if __name__ == "__main__":
    unittest.main()
