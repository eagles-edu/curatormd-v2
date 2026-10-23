"""Explicit local event-router command and project-isolation tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from project_fixtures import bind_test_project, create_consumer_repo

from curatormd_v2 import (
    CuratorStore,
    EventEnvelope,
    EventInboxStatus,
    GoalStarted,
    GoalStatus,
    SuccessCriterion,
)
from curatormd_v2.router_cli import MAX_ROUTER_BATCH, _positive_limit, main  # pyright: ignore[reportPrivateUsage]


class RouterCliTests(unittest.TestCase):
    """Keep one-shot routing opt-in, bounded, and scoped to listed projects."""

    def test_batch_limit_uses_the_router_ceiling(self) -> None:
        """Accept the router maximum and reject the next value."""
        self.assertEqual(_positive_limit(str(MAX_ROUTER_BATCH)), MAX_ROUTER_BATCH)
        self.assertRaises(
            argparse.ArgumentTypeError,
            _positive_limit,
            str(MAX_ROUTER_BATCH + 1),
        )

    def test_processing_requires_explicit_opt_in_before_loading_projects(self) -> None:
        """A default invocation must not inspect configs or open the database."""

        errors = StringIO()
        with patch("curatormd_v2.router_cli.ProjectConfig.load") as load:
            result = main(
                ["--database", "/tmp/unused.sqlite3", "--project-root", "/repo"],
                stderr=errors,
            )

        self.assertEqual(result, 2)
        self.assertIn("--route-events", errors.getvalue())
        load.assert_not_called()

    def test_configuration_failure_does_not_echo_exception_details(self) -> None:
        """A project-config error must not leak private source details to stderr."""

        canary = "ROUTER_PRIVATE_CONFIG_CANARY"
        errors = StringIO()
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "curatormd_v2.router_cli.ProjectConfig.load",
                side_effect=ValueError(canary),
            ):
                result = main(
                    [
                        "--database",
                        str(Path(temporary) / "unused.sqlite3"),
                        "--project-root",
                        temporary,
                        "--route-events",
                    ],
                    stderr=errors,
                )

        self.assertEqual(result, 2)
        self.assertIn("configuration or routing error", errors.getvalue())
        self.assertNotIn(canary, errors.getvalue())

    def test_one_shot_processes_only_explicitly_bound_projects(self) -> None:
        """Unlisted projects remain received with their payload and retry count."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            consumer_a = self._consumer(root / "consumer-a", "router-consumer-a")
            self._consumer(root / "consumer-b", "router-consumer-b")
            database = root / "global.sqlite3"
            store = CuratorStore(database)
            try:
                bind_test_project(store, consumer_a, "router-test")
                for project_id, event_id, goal_id in (
                    ("router-consumer-a", "event-a", "goal-a"),
                    ("router-consumer-b", "event-b", "goal-b"),
                ):
                    store.ingest_event(
                        EventEnvelope(
                            event_id,
                            project_id,
                            GoalStarted(
                                goal_id,
                                f"Process one {project_id} event",
                                (SuccessCriterion("routed", "The event is processed"),),
                                initial_status=GoalStatus.ACTIVE,
                            ),
                        )
                    )
            finally:
                store.close()

            output = StringIO()
            errors = StringIO()
            result = main(
                [
                    "--database",
                    str(database),
                    "--project-root",
                    str(consumer_a),
                    "--route-events",
                ],
                stdout=output,
                stderr=errors,
            )

            self.assertEqual(result, 0, errors.getvalue())
            self.assertEqual(errors.getvalue(), "")
            self.assertEqual(
                json.loads(output.getvalue()),
                {
                    "attempted": 1,
                    "claim_lost": 0,
                    "claimed": 0,
                    "expired_claims": 0,
                    "failed": 0,
                    "pending": 0,
                    "processed": 1,
                    "project_count": 1,
                    "quarantined": 0,
                },
            )

            store = CuratorStore(database)
            try:
                bound = store.event_receipt("router-consumer-a", "event-a")
                unbound = store.event_receipt("router-consumer-b", "event-b")
                self.assertEqual(bound.status, EventInboxStatus.PROCESSED)
                self.assertEqual(unbound.status, EventInboxStatus.RECEIVED)
                self.assertEqual(unbound.attempts, 0)
                self.assertEqual(
                    len(store.pending_events(project_id="router-consumer-b")), 1
                )
            finally:
                store.close()

    @staticmethod
    def _consumer(root: Path, project_id: str) -> Path:
        """Create a valid isolated consumer config for one router binding."""

        create_consumer_repo(root)
        (root / "docs" / "tasks.md").write_text("- [ ] Route a bounded event\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        config_path = root / ".curatormd-v2.toml"
        config_path.write_text(
            "\n".join(
                (
                    "schema_version = 1",
                    "backend_api_version = 1",
                    f'project_id = "{project_id}"',
                    "",
                    "[scope]",
                    'read_paths = ["src", "docs"]',
                    "",
                    "[checklists]",
                    'tasks = "docs/tasks.md"',
                    "",
                    "[evidence]",
                    "adapters = []",
                    "",
                    "[staging]",
                    'root = ".curatormd-v2/staging"',
                    "",
                    "[persistence]",
                    'targets = ["persistence/HISTORY.md"]',
                    "",
                )
            )
        )
        config_path.chmod(0o600)
        return root


if __name__ == "__main__":
    unittest.main()
