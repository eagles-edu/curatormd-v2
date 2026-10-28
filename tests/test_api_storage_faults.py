"""Storage exhaustion must never acknowledge an uncommitted event."""

from __future__ import annotations

import sqlite3
from typing import cast

from test_api import (
    AuthenticatedCuratorAPI,
    EventEnvelope,
    GoalStarted,
    NotFoundError,
    SuccessCriterion,
    _ApiTestSupport,
)


class ApiStorageFaultTests(_ApiTestSupport):
    """Exercise durable event behavior under SQLite page exhaustion."""

    def test_sqlite_full_never_returns_a_processed_event_without_a_receipt(self) -> None:
        """A real SQLITE_FULL fault rolls back processing and cannot acknowledge it."""

        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)
        connection = cast(sqlite3.Connection, getattr(self.store, "_connection"))
        connection.execute("CREATE TABLE storage_fault_fill (payload BLOB NOT NULL)")
        for _ in range(8):
            connection.execute(
                "INSERT INTO storage_fault_fill VALUES (randomblob(8192))"
            )
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        page_limit = connection.execute(
            f"PRAGMA max_page_count={page_count}"
        ).fetchone()[0]
        self.assertEqual(page_limit, page_count)

        event = EventEnvelope(
            "sqlite-full-event",
            "project-a",
            GoalStarted(
                "sqlite-full-goal",
                "Exercise a durable event when SQLite cannot allocate another page.",
                tuple(
                    SuccessCriterion(f"criterion-{index}", "x" * 480)
                    for index in range(12)
                ),
            ),
            source_id="sqlite-full-source",
            source_sequence=1,
        )

        with self.assertRaises(sqlite3.Error) as raised:
            api.process_event_json(self.caller, "project-a", event.to_json())
        self.assertEqual(
            raised.exception.sqlite_errorcode,
            sqlite3.SQLITE_FULL,
            str(raised.exception),
        )
        with self.assertRaises(NotFoundError):
            self.store.event_receipt("project-a", event.event_id)
        with self.assertRaises(NotFoundError):
            self.store.get_goal("sqlite-full-goal")

        with self.assertRaises(sqlite3.Error) as raised:
            connection.execute("INSERT INTO storage_fault_fill VALUES (randomblob(8192))")
        self.assertEqual(raised.exception.sqlite_errorcode, sqlite3.SQLITE_FULL)
