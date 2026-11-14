"""Schema step for project-scoped goal references in Codex telemetry."""

from __future__ import annotations

import sqlite3


def migrate_goal_project_reference_v49(connection: sqlite3.Connection) -> None:
    """Make the referenced project/goal pair a valid SQLite parent key.

    Some v48 databases already store ``hermes_codex_turn_links`` with a
    composite foreign key to ``goals(project_id, goal_id)``. SQLite requires
    that exact parent key to be unique; ``goal_id`` being globally unique is
    not enough to satisfy composite-FK validation. The extra index is
    compatible with both v48 link-table shapes and preserves all data.
    """

    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone() is not None:
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS goals_project_goal_unique "
            "ON goals(project_id, goal_id)"
        )
    connection.execute("PRAGMA user_version = 49")
