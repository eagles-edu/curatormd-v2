"""One-shot maintenance entrypoint opt-in and alert behavior."""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from curatormd_v2.maintenance_cli import main, _positive_limit  # pyright: ignore[reportPrivateUsage]
from curatormd_v2.models import PurgeStatus


class MaintenanceCliTests(unittest.TestCase):
    """Keep scheduled retries explicit, bounded, and content-free."""

    @staticmethod
    def _store_context() -> MagicMock:
        """Model the store context manager and its close behavior."""

        store = MagicMock()
        store.__enter__.return_value = store

        def close_without_suppressing(*_exception: object) -> bool:
            store.close()
            return False

        store.__exit__.side_effect = close_without_suppressing
        return store

    @staticmethod
    def _project_config() -> SimpleNamespace:
        return SimpleNamespace(project_id="project-a")

    def test_invalid_limit_error_does_not_retain_source_value(self) -> None:
        """Argument errors must not chain the rejected command-line value."""

        with self.assertRaisesRegex(argparse.ArgumentTypeError, "integer from 1 to 1000") as raised:
            _positive_limit("PRIVATE_LIMIT_CANARY")
        self.assertNotIn("PRIVATE_LIMIT_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_execution_requires_explicit_opt_in_before_opening_project(self) -> None:
        errors = StringIO()
        with patch("curatormd_v2.maintenance_cli.ProjectConfig.load") as load:
            result = main(
                ["--project-root", "/repo", "--database", "/state/curator.sqlite"],
                stderr=errors,
            )

        self.assertEqual(result, 2)
        self.assertIn("--execute-due-purges", errors.getvalue())
        load.assert_not_called()

    def test_due_retry_counts_are_bounded_and_pending_returns_alert_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "curator.sqlite"
            store = self._store_context()
            plugin = SimpleNamespace(
                retry_due_purge_pass=Mock(
                    return_value=(
                        (
                            SimpleNamespace(purge_status=PurgeStatus.COMPLETE),
                            SimpleNamespace(purge_status=PurgeStatus.PURGE_PENDING),
                        ),
                        (SimpleNamespace(status=PurgeStatus.PURGE_PENDING),),
                    )
                ),
            )
            output = StringIO()
            errors = StringIO()
            with (
                patch("curatormd_v2.maintenance_cli.backup_daily"),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectConfig.load",
                    return_value=self._project_config(),
                ),
                patch(
                    "curatormd_v2.maintenance_cli.CuratorStore",
                    return_value=store,
                ),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectPlugin.bind",
                    return_value=plugin,
                ),
            ):
                result = main(
                    [
                        "--project-root",
                        "/repo",
                        "--database",
                        str(database),
                        "--batch-limit",
                        "7",
                        "--execute-due-purges",
                    ],
                    stdout=output,
                    stderr=errors,
                )

        self.assertEqual(result, 1)
        plugin.retry_due_purge_pass.assert_called_once_with(7)
        store.close.assert_called_once_with()
        self.assertEqual(
            output.getvalue(),
            '{"backup_status":"verified","complete":1,"expiry_complete":0,"expiry_pending":1,'
            '"expiry_processed":1,"pending":1,"processed":2,'
            '"project_id":"project-a"}\n',
        )
        self.assertEqual(errors.getvalue(), "")
        self.assertNotIn("receipt", output.getvalue())
        self.assertNotIn("path", output.getvalue())

    def test_clean_batch_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store_context()
            plugin = SimpleNamespace(
                retry_due_purge_pass=Mock(return_value=((), ())),
            )
            output = StringIO()
            with (
                patch("curatormd_v2.maintenance_cli.backup_daily"),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectConfig.load",
                    return_value=self._project_config(),
                ),
                patch(
                    "curatormd_v2.maintenance_cli.CuratorStore",
                    return_value=store,
                ),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectPlugin.bind",
                    return_value=plugin,
                ),
            ):
                result = main(
                    [
                        "--project-root",
                        "/repo",
                        "--database",
                        str(Path(temporary) / "curator.sqlite"),
                        "--execute-due-purges",
                    ],
                    stdout=output,
                )

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            '{"backup_status":"verified","complete":0,"expiry_complete":0,"expiry_pending":0,'
            '"expiry_processed":0,"pending":0,"processed":0,'
            '"project_id":"project-a"}\n',
        )
        store.close.assert_called_once_with()

    def test_runtime_error_is_sanitized_and_store_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = self._store_context()
            errors = StringIO()
            with (
                patch("curatormd_v2.maintenance_cli.backup_daily"),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectConfig.load",
                    return_value=self._project_config(),
                ),
                patch(
                    "curatormd_v2.maintenance_cli.CuratorStore",
                    return_value=store,
                ),
                patch(
                    "curatormd_v2.maintenance_cli.ProjectPlugin.bind",
                    side_effect=OSError("/private/repo/staging"),
                ),
            ):
                result = main(
                    [
                        "--project-root",
                        "/repo",
                        "--database",
                        str(Path(temporary) / "curator.sqlite"),
                        "--execute-due-purges",
                    ],
                    stderr=errors,
                )

        self.assertEqual(result, 2)
        self.assertIn("maintenance failed", errors.getvalue())
        self.assertNotIn("/private/repo/staging", errors.getvalue())
        store.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
