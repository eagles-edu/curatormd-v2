"""Shared local SQLite and staging roots for service-level tests."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from curatormd_v2 import CuratorStore


def create_store_stage(test_case: unittest.TestCase) -> tuple[Path, Path, CuratorStore]:
    """Create an isolated store and empty staging directory for one test case."""

    root = Path(
        test_case.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
    )
    stage = root / "stage"
    stage.mkdir()
    return root, stage, CuratorStore(root / "curator.sqlite3")
