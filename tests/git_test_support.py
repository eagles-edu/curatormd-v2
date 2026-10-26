"""Shared immutable-commit fixture for local Git evidence tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def create_git_commit_range(directory: Path) -> tuple[Path, Path, str, str]:
    """Create a tiny repository with two commits and return their full IDs."""

    root = directory / "repository"
    root.mkdir()

    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "Curator test")
    git("config", "user.email", "curator-test@example.invalid")
    source = root / "task.txt"
    source.write_text("before\n", encoding="utf-8")
    git("add", "task.txt")
    git("commit", "--quiet", "-m", "base")
    base_revision = git("rev-parse", "HEAD")
    source.write_text("private diff contents\n", encoding="utf-8")
    git("add", "task.txt")
    git("commit", "--quiet", "-m", "change")
    return root, source, base_revision, git("rev-parse", "HEAD")
