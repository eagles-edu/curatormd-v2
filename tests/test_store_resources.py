"""Resource lifecycle tests for the SQLite store."""

from __future__ import annotations

import sqlite3
import unittest

from curatormd_v2 import CuratorStore


class StoreResourceTests(unittest.TestCase):
    """Ensure the store releases SQLite resources at context exit."""

    def test_context_manager_closes_the_connection(self) -> None:
        store = CuratorStore(":memory:")

        with store:
            self.assertEqual(store.list_goals(), ())

        with self.assertRaises(sqlite3.ProgrammingError):
            store.list_goals()


if __name__ == "__main__":
    unittest.main()
