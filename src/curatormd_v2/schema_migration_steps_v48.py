"""Schema step for content-free Hermes Codex turn telemetry."""

from __future__ import annotations

import sqlite3


def migrate_codex_session_turns_v48(connection: sqlite3.Connection) -> None:
    """Store content-free Codex turn observations and independent task links."""

    connection.execute(
        """CREATE TABLE IF NOT EXISTS hermes_codex_turns (
               project_id TEXT NOT NULL,
               profile_id TEXT NOT NULL,
               session_id TEXT NOT NULL,
               turn_id TEXT NOT NULL,
               started_at TEXT,
               ended_at TEXT,
               outcome TEXT,
               PRIMARY KEY(project_id, profile_id, session_id, turn_id),
               CHECK ((ended_at IS NULL AND outcome IS NULL)
                   OR (ended_at IS NOT NULL AND outcome IS NOT NULL))
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS hermes_codex_turn_links (
               project_id TEXT NOT NULL,
               profile_id TEXT NOT NULL,
               session_id TEXT NOT NULL,
               turn_id TEXT NOT NULL,
               goal_id TEXT NOT NULL,
               source_tool TEXT NOT NULL,
               linked_at TEXT NOT NULL,
               PRIMARY KEY(project_id, profile_id, session_id, turn_id, goal_id),
               FOREIGN KEY(project_id, profile_id, session_id, turn_id)
                   REFERENCES hermes_codex_turns(project_id, profile_id, session_id, turn_id),
               FOREIGN KEY(goal_id) REFERENCES goals(goal_id)
           )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS hermes_codex_telemetry_receipts (
               project_id TEXT NOT NULL,
               event_id TEXT NOT NULL,
               payload_sha256 TEXT NOT NULL,
               receipt_json TEXT NOT NULL,
               created_at TEXT NOT NULL,
               PRIMARY KEY(project_id, event_id)
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS hermes_codex_turn_session "
        "ON hermes_codex_turns(project_id, profile_id, session_id, started_at)"
    )
    connection.execute("PRAGMA user_version = 48")
