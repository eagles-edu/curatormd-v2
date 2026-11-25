"""Schema step for recoverable cleanup authorization persistence state."""

from __future__ import annotations

import sqlite3


def migrate_cleanup_authorization_canonical_state_v50(
    connection: sqlite3.Connection,
) -> None:
    """Restore the canonical persistence fields omitted by malformed v49 DBs.

    Older databases can report user_version 49 while the table lacks columns
    that v21 defined. Add only the missing fields, default old records to
    unpersisted, and leave their eligibility fail-closed. Repeating this step
    is safe, including when a prior migration attempt added only some fields.
    """

    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='cleanup_authorizations'"
    ).fetchone()
    if exists is None:
        connection.execute("PRAGMA user_version = 50")
        return
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(cleanup_authorizations)"
        )
    }
    additions = (
        ("canonical_persisted", "INTEGER NOT NULL DEFAULT 0"),
        ("canonical_target", "TEXT"),
        ("canonical_sha256", "TEXT"),
        ("canonical_persisted_at", "TEXT"),
    )
    for name, definition in additions:
        if name not in columns:
            connection.execute(
                f"ALTER TABLE cleanup_authorizations ADD COLUMN {name} {definition}"
            )
    connection.execute("PRAGMA user_version = 50")
