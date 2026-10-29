"""Privacy cleanup for discarded SQLite event payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from curatormd_v2 import (
    CuratorStore,
    CuratorService,
    EventEnvelope,
    EventReceiptArchiveRequest,
    GoalStarted,
    ArtifactPurger,
    SuccessCriterion,
)


class EventPayloadScrubTests(unittest.TestCase):
    """Verify WAL cleanup, durable retries, and transient payload disposal."""

    def setUp(self) -> None:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.database = Path(temporary) / "curator.sqlite3"
        self.store = CuratorStore(self.database)
        self.addCleanup(self.store.close)

    def ingest_canary(self, event_id: str, canary: str) -> None:
        """Write one valid event whose problem field acts as a WAL canary."""

        self.store.ingest_event(
            EventEnvelope(
                event_id=event_id,
                project_id="project-a",
                payload=GoalStarted(
                    goal_id=f"goal-{event_id}",
                    problem=canary,
                    success_criteria=(
                        SuccessCriterion("stored", "The event is disposed"),
                    ),
                ),
            )
        )

    def wal_bytes(self) -> bytes:
        """Read the current WAL only for the disposable canary fixture."""

        path = Path(f"{self.database}-wal")
        return path.read_bytes() if path.exists() else b""

    def test_processed_payload_is_removed_from_wal(self) -> None:
        """Scrub transient event bytes from the WAL after durable processing."""

        canary = "transient-event-canary-8b2c9f"
        event_id = "wal-scrub-event"
        self.ingest_canary(event_id, canary)

        receipt = self.store.mark_event_processed("project-a", event_id)

        reader = sqlite3.connect(self.database)
        self.addCleanup(reader.close)
        row = reader.execute(
            "SELECT payload_json FROM event_inbox WHERE event_id = ?", (event_id,)
        ).fetchone()
        self.assertEqual(receipt.status.value, "processed")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNone(row[0])
        self.assertNotIn(canary.encode(), self.wal_bytes())
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 0)

    def test_compaction_proposal_is_paged_stable_and_read_only(self) -> None:
        """Inventory only scrubbed processed receipts without changing the ledger."""

        self.ingest_canary("compact-a", "transient-a")
        self.ingest_canary("compact-b", "transient-b")
        self.ingest_canary("compact-pending", "transient-pending")
        self.store.mark_event_processed("project-a", "compact-a")
        self.store.mark_event_processed("project-a", "compact-b")

        before = self.store.global_event_inbox_usage()
        first = self.store.propose_event_receipt_compaction("project-a", 0, 1)
        second = self.store.propose_event_receipt_compaction("project-a", 1, 1)
        after = self.store.global_event_inbox_usage()

        self.assertEqual(first.eligible_count, 2)
        self.assertEqual(tuple(item.event_id for item in first.items), ("compact-a",))
        self.assertEqual(tuple(item.event_id for item in second.items), ("compact-b",))
        self.assertEqual(first.manifest_sha256, second.manifest_sha256)
        self.assertEqual(before, after)
        self.assertEqual(self.store.event_receipt("project-a", "compact-a").status.value, "processed")
        self.assertEqual(self.store.event_receipt("project-a", "compact-pending").status.value, "received")
        with self.assertRaises(ValueError):
            self.store.propose_event_receipt_compaction("project-a", 0, 101)

    def test_exact_reviewed_event_page_archives_without_losing_replay_receipt(self) -> None:
        """Archive frees active capacity while preserving the durable event row."""

        self.ingest_canary("archive-a", "transient-a")
        self.ingest_canary("archive-b", "transient-b")
        self.store.mark_event_processed("project-a", "archive-a")
        self.store.mark_event_processed("project-a", "archive-b")
        proposal = self.store.propose_event_receipt_compaction("project-a", 0, 1)
        event_id = proposal.items[0].event_id
        request = EventReceiptArchiveRequest(
            archive_id="archive-batch-1",
            project_id="project-a",
            reviewer_id="eaglesvn",
            event_ids=(event_id,),
            inventory_sha256=proposal.manifest_sha256,
            offset=0,
            approval_reason="Archive the reviewed processed receipt page",
        )

        before = self.store.global_event_inbox_usage()
        receipt = self.store.archive_event_receipt_page(request)
        after = self.store.global_event_inbox_usage()
        event = EventEnvelope(
            event_id=event_id,
            project_id="project-a",
            payload=GoalStarted(
                goal_id=f"goal-{event_id}",
                problem=f"transient-{event_id[-1]}",
                success_criteria=(
                    SuccessCriterion("stored", "The event is disposed"),
                ),
            ),
        )
        replay, inserted = self.store.ingest_event(event)
        staging = self.database.parent / "staging"
        staging.mkdir()
        service_replay = CuratorService(
            self.store, ArtifactPurger(staging),
            project_id="project-a",
        ).process_event(event)

        self.assertEqual(receipt.event_ids, (event_id,))
        self.assertEqual(before.receipt_count, 2)
        self.assertEqual(after.receipt_count, 1)
        self.assertFalse(inserted)
        self.assertEqual(replay.status.value, "processed")
        self.assertEqual(service_replay.status.value, "processed")
        self.assertEqual(self.store.event_receipt("project-a", event_id), replay)
        self.assertEqual(self.store.archive_event_receipt_page(request), receipt)

    def test_archive_rejects_stale_manifest_without_marking_any_receipt(self) -> None:
        """Require a fresh exact review when the eligible receipt set changes."""

        self.ingest_canary("stale-archive-a", "transient-a")
        self.store.mark_event_processed("project-a", "stale-archive-a")
        proposal = self.store.propose_event_receipt_compaction("project-a")
        self.ingest_canary("stale-archive-b", "transient-b")
        self.store.mark_event_processed("project-a", "stale-archive-b")
        with self.assertRaisesRegex(RuntimeError, "inventory changed"):
            self.store.archive_event_receipt_page(
                EventReceiptArchiveRequest(
                    archive_id="stale-archive-batch",
                    project_id="project-a",
                    reviewer_id="eaglesvn",
                    event_ids=(proposal.items[0].event_id,),
                    inventory_sha256=proposal.manifest_sha256,
                    offset=0,
                    approval_reason="Reject stale receipt inventory",
                )
            )
        with sqlite3.connect(self.database) as reader:
            archived = reader.execute(
                "SELECT COUNT(*) FROM event_inbox WHERE archive_id IS NOT NULL"
            ).fetchone()[0]
        self.assertEqual(archived, 0)

    def test_failed_payload_remains_until_explicit_terminal_disposition(self) -> None:
        """A failed payload stays available until retry or reviewed disposition."""

        canary = "permanent-failure-wal-canary-68ad"
        event_id = "permanent-failure-wal-event"
        self.ingest_canary(event_id, canary)

        receipt = self.store.mark_event_failed(
            "project-a", event_id, "fact_capacity_exhausted"
        )

        self.assertEqual(receipt.status.value, "failed")
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 0)
        self.assertIn(canary.encode(), self.wal_bytes())

    def test_busy_reader_keeps_scrub_pending_until_checkpoint_can_truncate(self) -> None:
        """Expose a blocked WAL scrub as pending and clear it on a later retry."""

        canary = "busy-reader-event-canary-571e"
        event_id = "busy-reader-event"
        self.ingest_canary(event_id, canary)
        reader = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        row = reader.execute(
            "SELECT payload_json FROM event_inbox WHERE event_id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        self.assertIn(canary, row[0])

        self.store.mark_event_processed("project-a", event_id)

        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 1)
        self.assertIn(canary.encode(), self.wal_bytes())
        reader.execute("ROLLBACK")
        reader.close()

        self.assertEqual(self.store.retry_pending_event_payload_scrubs(), 1)
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 0)
        self.assertNotIn(canary.encode(), self.wal_bytes())

    def test_blocked_scrub_survives_restart_and_startup_retries_it(self) -> None:
        """Keep blocked scrub work durable and retry automatically on startup."""

        canary = "restart-wal-canary-2d5a"
        event_id = "restart-wal-event"
        self.ingest_canary(event_id, canary)
        reader = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        row = reader.execute(
            "SELECT payload_json FROM event_inbox WHERE event_id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        self.assertIn(canary, row[0])
        self.store.mark_event_processed("project-a", event_id)
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 1)

        self.store.close()
        after_blocked_startup = CuratorStore(self.database)
        self.addCleanup(after_blocked_startup.close)
        self.assertEqual(
            after_blocked_startup.event_payload_scrub_pending_count("project-a"), 1
        )
        reader.execute("ROLLBACK")
        reader.close()
        after_blocked_startup.close()

        after_clear_startup = CuratorStore(self.database)
        self.addCleanup(after_clear_startup.close)
        self.assertEqual(
            after_clear_startup.event_payload_scrub_pending_count("project-a"), 0
        )
        self.assertNotIn(canary.encode(), self.wal_bytes())
