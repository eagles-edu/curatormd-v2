"""Project-local runtime/source parity checks for the operations worker."""

from __future__ import annotations

import hashlib
from importlib import metadata
import os
from pathlib import Path
import tomllib
from typing import Any


def source_fingerprint(root: Path) -> str:
    """Hash the ops and maintenance source set plus project metadata."""
    package_root = root / "src/curatormd_v2"
    paths = [root / "pyproject.toml"]
    if package_root.is_dir():
        for pattern in (
            "ops_*.py",
            "maintenance_cli.py",
            "maintenance_runtime.py",
            "schema_migrations.py",
            "schema_migration_steps_*.py",
            "store.py",
        ):
            paths.extend(path for path in package_root.glob(pattern) if not path.is_symlink())
    digest = hashlib.sha256()
    for path in sorted(paths):
        try:
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            digest.update(b"unreadable-source-artifact")
    return digest.hexdigest()


def runtime_status(
    root: Path,
    module_file: Path,
    import_fingerprint: str,
    schema_version: int,
) -> dict[str, Any]:
    """Compare source metadata and loaded package identity with installed commands."""
    try:
        source_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["version"]
        installed_version = metadata.version("curatormd-v2")
    except (OSError, KeyError, tomllib.TOMLDecodeError, metadata.PackageNotFoundError):
        source_version = None
        installed_version = None
    expected_module = (root / "src/curatormd_v2/ops_cli.py").resolve()
    source_module_match = module_file.resolve() == expected_module
    source_fingerprint_match = source_fingerprint(root) == import_fingerprint
    entrypoints = (
        root / ".venv/bin/curatormd-v2-ops",
        root / ".venv/bin/curatormd-v2-maintenance",
    )
    entrypoints_available = all(path.is_file() and os.access(path, os.X_OK) for path in entrypoints)
    healthy = (
        isinstance(source_version, str)
        and source_version == installed_version
        and source_module_match
        and source_fingerprint_match
        and entrypoints_available
    )
    status = "healthy" if healthy else "degraded" if entrypoints_available else "unavailable"
    return {
        "status": status,
        "source_version": source_version,
        "installed_version": installed_version,
        "source_module_match": source_module_match,
        "source_fingerprint_match": source_fingerprint_match,
        "entrypoints_available": entrypoints_available,
        "schema_version": schema_version,
    }
