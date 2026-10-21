"""Resource lifecycle tests for the SQLite store."""

from __future__ import annotations

import sqlite3
import unittest

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


if __name__ == "__main__":
    unittest.main()
