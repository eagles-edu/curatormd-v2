"""Resource lifecycle tests for the SQLite store."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from curatormd_v2 import CuratorStore


class StoreResourceTests(unittest.TestCase):
    """Ensure the store releases SQLite resources at context exit."""

    def test_event_claim_rejects_tuple_subclass_project_bindings(self) -> None:
        """Project bindings must use an exact inert tuple."""

        class TupleSubclass(tuple[str, ...]):
            """Expose why broad isinstance checks are insufficient."""

        with CuratorStore(":memory:") as store:
            with self.assertRaisesRegex(ValueError, "tuple of at most 128"):
                store.claim_pending_events(
                    "worker", project_ids=TupleSubclass(("project-a",))
                )

    def test_context_manager_closes_the_connection(self) -> None:
        store = CuratorStore(":memory:")

        with store:
            self.assertEqual(store.list_goals(), ())

        with self.assertRaises(sqlite3.ProgrammingError):
            store.list_goals()

    def test_commit_failure_rolls_back_and_leaves_store_usable(self) -> None:
        """A deferred constraint failure must not strand a transaction open."""

        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "curator.sqlite3"
            store = CuratorStore(database)
            with store.transaction() as connection:
                connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
                connection.execute(
                    "CREATE TABLE child ("
                    "parent_id INTEGER REFERENCES parent(id) "
                    "DEFERRABLE INITIALLY DEFERRED)"
                )

            with self.assertRaises(sqlite3.IntegrityError):
                with store.transaction() as connection:
                    connection.execute("INSERT INTO child(parent_id) VALUES (99)")

            with store.transaction() as connection:
                connection.execute("INSERT INTO parent(id) VALUES (99)")
            store.close()

            with CuratorStore(database) as reopened:
                with reopened.transaction() as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM child"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM parent"
                        ).fetchone()[0],
                        1,
                    )

    def test_rollback_failure_closes_connection_and_preserves_commit_error(self) -> None:
        """A failed rollback closes SQLite and annotates the commit error safely."""

        class FailingCommitConnection:
            """Inject commit and rollback faults around one real SQLite handle."""

            def __init__(
                self, connection: sqlite3.Connection, fail_close: bool
            ) -> None:
                self.connection = connection
                self.fail_close = fail_close
                self.closed = False

            @property
            def in_transaction(self) -> bool:
                return self.connection.in_transaction

            def execute(self, statement: str) -> sqlite3.Cursor:
                return self.connection.execute(statement)

            def commit(self) -> None:
                raise sqlite3.OperationalError("injected commit failure")

            def rollback(self) -> None:
                raise sqlite3.OperationalError("injected rollback failure")

            def close(self) -> None:
                if self.fail_close:
                    raise sqlite3.OperationalError("injected close failure")
                self.closed = True
                self.connection.close()

        for fail_close in (False, True):
            with self.subTest(fail_close=fail_close):
                store = CuratorStore(":memory:")
                with store.transaction() as connection:
                    connection.execute("CREATE TABLE cleanup_probe (id INTEGER)")
                broken = FailingCommitConnection(connection, fail_close)

                try:
                    with patch.object(
                        cast(Any, store), "_connection", broken
                    ):
                        with self.assertRaisesRegex(
                            sqlite3.OperationalError, "injected commit failure"
                        ) as raised:
                            with store.transaction():
                                pass
                    expected_note = (
                        "transaction rollback and connection close failed "
                        "(OperationalError, OperationalError)"
                        if fail_close
                        else "transaction rollback failed; connection closed "
                        "(OperationalError)"
                    )
                    self.assertIn(expected_note, raised.exception.__notes__)
                    self.assertEqual(broken.closed, not fail_close)
                finally:
                    connection.close()

    def test_interrupted_transaction_rolls_back_and_remains_usable(self) -> None:
        """A KeyboardInterrupt after a write rolls back before it is re-raised."""

        with CuratorStore(":memory:") as store:
            with store.transaction() as connection:
                connection.execute("CREATE TABLE interruption_probe (id INTEGER)")

            with self.assertRaises(KeyboardInterrupt):
                with store.transaction() as connection:
                    connection.execute("INSERT INTO interruption_probe VALUES (1)")
                    raise KeyboardInterrupt

            with store.transaction() as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM interruption_probe"
                    ).fetchone()[0],
                    0,
                )
                connection.execute("INSERT INTO interruption_probe VALUES (2)")
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM interruption_probe"
                    ).fetchone()[0],
                    1,
                )


if __name__ == "__main__":
    unittest.main()
