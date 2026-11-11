#!/usr/bin/python3
"""Select a configured maintenance runtime compatible with the ledger."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import quote


def compatible(binary: str, database_version: int) -> bool:
    path = Path(binary)
    if not path.is_absolute() or path.name != "curatormd-v2-maintenance":
        return False
    python = path.parent / "python"
    if not path.is_file() or not os.access(path, os.X_OK) or not python.is_file():
        return False
    try:
        result = subprocess.run(
            [str(python), "-c", "from curatormd_v2.schema_migrations import SQLITE_SCHEMA_VERSION; print(SQLITE_SCHEMA_VERSION)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=15, check=True,
        )
        value = result.stdout.strip()
        return value.isascii() and value.isdecimal() and int(value) >= database_version
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def main() -> int:
    database = os.environ.get("CURATORMD_V2_DATABASE", "")
    if not Path(database).is_absolute() or not Path(database).is_file():
        print("Curator maintenance runtime check failed: database unavailable.", file=sys.stderr)
        return 2
    try:
        uri = "file:" + quote(database, safe="/") + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
    except (OSError, sqlite3.Error):
        print("Curator maintenance runtime check failed: database unreadable.", file=sys.stderr)
        return 2
    for key in ("CURATORMD_V2_MAINTENANCE_BIN", "CURATORMD_V2_MAINTENANCE_FALLBACK_BIN"):
        candidate = os.environ.get(key, "")
        if candidate and compatible(candidate, version):
            if key.endswith("FALLBACK_BIN"):
                print("Curator maintenance selected the compatible fallback runtime.", file=sys.stderr)
            os.execv(candidate, [candidate, *sys.argv[1:]])
    print("Curator maintenance runtime check failed: no compatible runtime.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
