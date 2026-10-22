"""Privacy cleanup for discarded SQLite event payloads."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from curatormd_v2 import CuratorStore, EventEnvelope, GoalStarted, SuccessCriterion


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

    def test_permanent_failure_payload_discard_is_removed_from_wal(self) -> None:
        """Apply the same WAL scrub when a permanent failure discards input."""

        canary = "permanent-failure-wal-canary-68ad"
        event_id = "permanent-failure-wal-event"
        self.ingest_canary(event_id, canary)

        receipt = self.store.mark_event_failed(
            "project-a", event_id, "fact_capacity_exhausted", discard_payload=True
        )

        self.assertEqual(receipt.status.value, "failed")
        self.assertEqual(self.store.event_payload_scrub_pending_count("project-a"), 0)
        self.assertNotIn(canary.encode(), self.wal_bytes())

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
