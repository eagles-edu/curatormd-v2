"""Content-free Hermes Codex turn telemetry storage tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from curatormd_v2 import ConflictError, CuratorStore


class HermesCodexTurnTests(unittest.TestCase):
    """Keep turn telemetry idempotent and separate from task lifecycle rows."""

    def test_turn_receipts_and_multiple_goal_links_are_replay_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CuratorStore(Path(temporary) / "telemetry.sqlite3")
            try:
                with store.transaction() as connection:
                    for goal_id in ("child-a", "child-b", "child-c"):
                        connection.execute(
                            """INSERT INTO goals
                               (goal_id, project_id, problem, criteria_json, status,
                                created_at, updated_at)
                               VALUES (?, 'project-a', 'test task', '[]', 'active',
                                       '2026-11-11T00:00:00Z', '2026-11-11T00:00:00Z')""",
                            (goal_id,),
                        )
                start = store.record_hermes_codex_turn_event(
                    "project-a", "profile-a", "session-a", "turn-a",
                    "start-event", "start", "2026-11-11T00:00:00Z",
                )
                self.assertEqual(start["status"], "processed")
                self.assertEqual(
                    store.record_hermes_codex_turn_event(
                        "project-a", "profile-a", "session-a", "turn-a",
                        "start-event", "start", "2026-11-11T00:00:00Z",
                    ),
                    start,
                )
                end = store.record_hermes_codex_turn_event(
                    "project-a", "profile-a", "session-a", "turn-a",
                    "end-event", "end", "2026-11-11T00:00:01Z", "completed",
                )
                self.assertEqual(end["status"], "processed")
                for index, (goal_id, source_tool) in enumerate(
                    (
                        ("child-a", "goal_finish"),
                        ("child-b", "goal_activate"),
                        ("child-c", "goal_amend_criteria"),
                    )
                ):
                    receipt = store.link_hermes_codex_turn_goal(
                        "project-a", "profile-a", "session-a", "turn-a",
                        goal_id, f"link-event-{index}", source_tool,
                    )
                    self.assertEqual(receipt["goal_id"], goal_id)
                with store.transaction() as connection:
                    rows = connection.execute(
                        """SELECT goal_id FROM hermes_codex_turn_links
                           WHERE project_id='project-a' AND session_id='session-a'
                             AND turn_id='turn-a' ORDER BY goal_id"""
                    ).fetchall()
                    turn_columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(hermes_codex_turns)"
                        )
                    }
                self.assertEqual(
                    [row["goal_id"] for row in rows],
                    ["child-a", "child-b", "child-c"],
                )
                self.assertEqual(
                    turn_columns,
                    {
                        "project_id", "profile_id", "session_id", "turn_id",
                        "started_at", "ended_at", "outcome",
                    },
                )
                with self.assertRaises(ConflictError):
                    store.record_hermes_codex_turn_event(
                        "project-a", "profile-a", "session-a", "turn-a",
                        "start-event", "start", "2026-11-11T00:00:02Z",
                    )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
