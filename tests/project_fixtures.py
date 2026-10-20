"""Shared temporary consumer-repository layouts for Curator V2 tests."""

from __future__ import annotations

from pathlib import Path


def create_consumer_repo(root: Path) -> Path:
    """Create the minimal isolated repository tree expected by project config."""

    root.mkdir(parents=True)
    for directory in (".git", "src", "docs", "persistence"):
        (root / directory).mkdir()
    (root / ".curatormd-v2" / "staging").mkdir(parents=True)
    return root
