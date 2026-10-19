"""Persistent token-bucket behavior across Curator SQLite workers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from curatormd_v2 import CuratorStore, SQLiteTokenBucket


class SQLiteTokenBucketTests(unittest.TestCase):
    """Shared SQLite state must enforce bounded subject/project quotas."""

    def test_two_store_connections_share_quota_and_refill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "curator.sqlite3"
            first_store = CuratorStore(database)
            second_store = CuratorStore(database)
            current_time = [100.0]
            first = SQLiteTokenBucket(
                first_store,
                capacity=1,
                refill_period_seconds=10,
                clock=lambda: current_time[0],
            )
            second = SQLiteTokenBucket(
                second_store,
                capacity=1,
                refill_period_seconds=10,
                clock=lambda: current_time[0],
            )
            try:
                self.assertTrue(first.allow("profile-a", "project-a"))
                self.assertFalse(second.allow("profile-a", "project-a"))
                self.assertTrue(second.allow("profile-a", "project-b"))
                current_time[0] += 10
                self.assertTrue(second.allow("profile-a", "project-a"))
            finally:
                second_store.close()
                first_store.close()

    def test_concurrent_connections_cannot_overconsume_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "curator.sqlite3"
            stores = (CuratorStore(database), CuratorStore(database))
            limiters = tuple(
                SQLiteTokenBucket(store, capacity=7, refill_period_seconds=60)
                for store in stores
            )

            def attempt(index: int) -> bool:
                return limiters[index % 2].allow("shared-profile", "project-a")

            try:
                with ThreadPoolExecutor(max_workers=12) as executor:
                    allowed = tuple(executor.map(attempt, range(36)))
                self.assertEqual(sum(allowed), 7)
            finally:
                stores[1].close()
                stores[0].close()

    def test_bucket_survives_store_reopen_and_clock_rollback_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "curator.sqlite3"
            current_time = [100.0]
            store = CuratorStore(database)
            limiter = SQLiteTokenBucket(
                store,
                capacity=1,
                refill_period_seconds=10,
                clock=lambda: current_time[0],
            )
            self.assertTrue(limiter.allow("profile-a", "project-a"))
            store.close()

            current_time[0] = 90.0
            reopened = CuratorStore(database)
            limiter = SQLiteTokenBucket(
                reopened,
                capacity=1,
                refill_period_seconds=10,
                clock=lambda: current_time[0],
            )
            try:
                self.assertFalse(limiter.allow("profile-a", "project-a"))
                current_time[0] = 110.0
                self.assertTrue(limiter.allow("profile-a", "project-a"))
            finally:
                reopened.close()

    def test_full_bucket_registry_fails_closed_then_prunes_fully_idle_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CuratorStore(Path(temporary) / "curator.sqlite3")
            current_time = [0.0]
            limiter = SQLiteTokenBucket(
                store,
                capacity=1,
                refill_period_seconds=1,
                max_tracked_buckets=1,
                clock=lambda: current_time[0],
            )
            try:
                self.assertTrue(limiter.allow("profile-a", "project-a"))
                self.assertFalse(limiter.allow("profile-b", "project-a"))
                with store.transaction() as connection:
                    count = connection.execute(
                        "SELECT count(*) FROM request_rate_buckets"
                    ).fetchone()[0]
                self.assertEqual(count, 1)

                current_time[0] = 61.0
                self.assertTrue(limiter.allow("profile-b", "project-a"))
                with store.transaction() as connection:
                    rows = connection.execute(
                        "SELECT subject_id FROM request_rate_buckets"
                    ).fetchall()
                self.assertEqual([row["subject_id"] for row in rows], ["profile-b"])
            finally:
                store.close()

    def test_slow_refill_bucket_is_not_pruned_before_full_refill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CuratorStore(Path(temporary) / "curator.sqlite3")
            current_time = [0.0]
            limiter = SQLiteTokenBucket(
                store,
                capacity=120,
                refill_period_seconds=600,
                max_tracked_buckets=1,
                clock=lambda: current_time[0],
            )
            try:
                self.assertEqual(
                    sum(
                        limiter.allow("profile-a", "project-a")
                        for _ in range(120)
                    ),
                    120,
                )
                current_time[0] = 60.0
                self.assertFalse(limiter.allow("profile-b", "project-a"))
                current_time[0] = 660.0
                self.assertTrue(limiter.allow("profile-b", "project-a"))
            finally:
                store.close()

    def test_invalid_keys_clock_and_policy_values_are_rejected_or_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CuratorStore(Path(temporary) / "curator.sqlite3")
            try:
                with self.assertRaises(ValueError):
                    SQLiteTokenBucket(store, capacity=True)
                with self.assertRaises(ValueError):
                    SQLiteTokenBucket(store, refill_period_seconds=float("inf"))
                with self.assertRaises(ValueError):
                    SQLiteTokenBucket(store, refill_period_seconds=10**1000)
                with self.assertRaises(ValueError):
                    SQLiteTokenBucket(store, refill_period_seconds=0.0001)
                with self.assertRaises(ValueError):
                    SQLiteTokenBucket(store, max_tracked_buckets=10_001)
                limiter = SQLiteTokenBucket(store, clock=lambda: float("nan"))
                self.assertFalse(limiter.allow("bad subject", "project-a"))
                with self.assertRaisesRegex(ValueError, "clock"):
                    limiter.allow("profile-a", "project-a")
                huge_clock = SQLiteTokenBucket(store, clock=lambda: 10**1000)
                with self.assertRaisesRegex(ValueError, "clock"):
                    huge_clock.allow("profile-a", "project-a")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
