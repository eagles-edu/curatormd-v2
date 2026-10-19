"""Smoke tests for the initial package scaffold."""

import unittest

import curatormd_v2


class PackageScaffoldTests(unittest.TestCase):
    """Check metadata exposed by the initial Curator V2 package."""

    def test_package_has_initial_version(self) -> None:
        self.assertEqual(curatormd_v2.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
