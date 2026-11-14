# pyright: reportPrivateUsage=false
# pylint: disable=protected-access  # Tests deliberately exercise failure-boundary helpers.
"""Regression coverage for Curator V2 local-alpha operations policy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
from typing import Any
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

from curatormd_v2 import ops_cli
from curatormd_v2 import ops_resource_monitor
from curatormd_v2.backup import restore_database
from curatormd_v2.ops_health import OPERATIONAL_COUNT_NAMES


class OpsBindingTests(unittest.TestCase):
    """Check private binding authority and malformed permission states."""

    def test_health_command_calls_pinned_hermes_api_without_cli_startup(self) -> None:
        command = ops_cli._manifest_expected()["health_command"]
        self.assertEqual(command[0], str(ops_cli.HERMES_PYTHON))
        self.assertEqual(command[1], "-c")
        self.assertIn("hermes_cli.mcp_test_command", command[2])
        self.assertIn("cmd_mcp_test", command[2])
        self.assertIn("probe_curator_status=True", command[2])
        self.assertNotIn("source_completion", command[2])
        self.assertFalse(command[0].endswith("/hermes"))

    def test_manifest_requires_owner_private_permissions_and_exact_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            with mock.patch.object(ops_cli, "MANIFEST", manifest):
                self.assertEqual(ops_cli._read_manifest()[1], "manifest_missing")
                manifest.write_text(json.dumps(ops_cli._manifest_expected()))
                os.chmod(manifest, 0o600)
                self.assertIsNone(ops_cli._read_manifest()[1])
                expected = ops_cli._manifest_expected()
                expected["os_uid"] = 999
                manifest.write_text(json.dumps(expected))
                os.chmod(manifest, 0o600)
                self.assertEqual(ops_cli._read_manifest()[1], "binding_conflict")

    def test_manifest_group_readable_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            manifest.write_text(json.dumps(ops_cli._manifest_expected()))
            os.chmod(manifest, 0o644)
            with mock.patch.object(ops_cli, "MANIFEST", manifest):
                self.assertEqual(ops_cli._read_manifest()[1], "manifest_permissions")

    def test_older_ai_limits_do_not_conflict_with_project_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            value = ops_cli._manifest_expected()
            value["ai_timeout_seconds"] = 300
            value["ai_token_budget"] = 24000
            manifest.write_text(json.dumps(value))
            os.chmod(manifest, 0o600)
            with mock.patch.object(ops_cli, "MANIFEST", manifest):
                loaded, error = ops_cli._read_manifest()
        self.assertEqual(error, None)
        assert loaded is not None
        self.assertEqual(loaded["ai_timeout_seconds"], 300)
        self.assertLessEqual(ops_cli.MAX_AI_SECONDS, 300)

    def test_every_non_ai_manifest_authority_field_is_exact(self) -> None:
        expected = ops_cli._manifest_expected()
        authority_fields = set(expected) - {"ai_timeout_seconds", "ai_token_budget"}
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            for field in sorted(authority_fields):
                with self.subTest(field=field):
                    changed = dict(expected)
                    changed[field] = "changed-authority"
                    manifest.write_text(json.dumps(changed))
                    os.chmod(manifest, 0o600)
                    with mock.patch.object(ops_cli, "MANIFEST", manifest):
                        self.assertEqual(ops_cli._read_manifest()[1], "binding_conflict")

    def test_health_command_manifest_conflict_dispatches_one_incident_and_skips_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "manifest.json"
            manifest = ops_cli._manifest_expected()
            manifest["health_command"] = ["/usr/local/bin/hermes", "--probe-curator-status"]
            manifest_path.write_text(json.dumps(manifest))
            os.chmod(manifest_path, 0o600)
            incidents = root / "incidents"
            healthy = {"status": "healthy"}

            def binding_status(error: str | None) -> dict[str, Any]:
                return {
                    "status": "healthy" if error is None else "degraded",
                    "reason": error,
                }

            def failed_diagnosis(path: Path) -> None:
                value = json.loads(path.read_text())
                value["ai_status"] = "failed"
                path.write_text(json.dumps(value))

            with (
                mock.patch.object(ops_cli, "MANIFEST", manifest_path),
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(
                    ops_cli,
                    "_binding_status",
                    side_effect=binding_status,
                ),
                mock.patch.object(ops_cli, "_probe_database", return_value=healthy),
                mock.patch.object(ops_cli, "_runtime_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_retention_status", return_value=healthy),
                mock.patch.object(ops_cli, "_monitor_status", return_value=healthy),
                mock.patch.object(ops_cli, "_acceptance_history_status", return_value=healthy),
                mock.patch.object(ops_cli, "_maintenance_timer_status", return_value=healthy),
                mock.patch.object(ops_cli, "_maintenance_status", return_value=healthy),
                mock.patch.object(ops_cli, "_probe_health") as health_probe,
                mock.patch.object(ops_cli, "_dispatch_ai", side_effect=failed_diagnosis) as dispatch,
            ):
                first = ops_cli.check()
                second = ops_cli.check()
            self.assertIn("binding", first["gates"])
            self.assertEqual(first["incident_id"], second["incident_id"])
            health_probe.assert_not_called()
            dispatch.assert_called_once()


class OpsDatabaseTests(unittest.TestCase):
    """Check integrity, foreign-key, schema, missing, and corrupt DB paths."""

    def _database(self, path: Path, schema: int) -> None:
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA user_version = ?".replace("?", str(schema)))

    def test_sqlite_integrity_foreign_keys_and_schema_are_all_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            self._database(database, ops_cli.SQLITE_SCHEMA_VERSION)
            with mock.patch.object(ops_cli, "DATABASE", database):
                self.assertEqual(ops_cli._probe_database()["status"], "healthy")
                self._database(database, ops_cli.SQLITE_SCHEMA_VERSION - 1)
                self.assertEqual(ops_cli._probe_database()["status"], "degraded")

    def test_missing_and_corrupt_database_are_not_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            with mock.patch.object(ops_cli, "DATABASE", database):
                self.assertEqual(ops_cli._probe_database()["status"], "database_missing")
                database.write_bytes(b"not sqlite")
                self.assertEqual(ops_cli._probe_database()["status"], "database_error")

    def test_completed_goal_conflict_fixture_is_in_failure_diagnosis_without_payload(self) -> None:
        """Keep the real late fact failure shape as content-free diagnostic coverage."""
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "late-fact-record-after-completion.json")
            .read_text(encoding="utf-8")
        )
        event = fixture["event"]
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """CREATE TABLE event_inbox (
                         project_id TEXT, event_id TEXT, status TEXT, event_type TEXT,
                         source_id TEXT, source_sequence INTEGER, payload_sha256 TEXT,
                         attempts INTEGER, last_error TEXT, received_at TEXT,
                         payload_json TEXT)"""
                )
                connection.execute(
                    """INSERT INTO event_inbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fixture["project_id"], event["event_id"], event["status"],
                        event["event_type"], "codex-local", None,
                        event["payload_sha256"], 1, event["error_code"],
                        "2026-11-12T17:36:08Z", None,
                    ),
                )
            with mock.patch.object(ops_cli, "DATABASE", database), mock.patch.object(
                ops_cli, "PROJECT_ID", fixture["project_id"]
            ):
                snapshot = ops_cli._event_failure_status()
        self.assertEqual(snapshot["status"], "degraded")
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["events"][0]["event_id"], event["event_id"])
        self.assertEqual(snapshot["events"][0]["error_code"], "ConflictError")
        self.assertNotIn("payload_json", json.dumps(snapshot))
        self.assertFalse(event["payload_included"])

    def test_locked_database_fails_closed_without_leaking_sqlite_details(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            database.touch()
            locked = sqlite3.OperationalError("database is locked")
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(
                    ops_cli.sqlite3, "connect", side_effect=locked
                ),
            ):
                result = ops_cli._probe_database()
        self.assertEqual(result["status"], "database_error")
        self.assertEqual(result["error"], "SQLITE_ERROR")

    def test_failed_pre_migration_snapshot_is_removed_and_blocks_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "alpha.sqlite3"
            database.touch()
            state = root / "ops"
            locked = sqlite3.OperationalError("database is locked")
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(
                    ops_cli.sqlite3, "connect", side_effect=locked
                ),
            ):
                with self.assertRaises(sqlite3.OperationalError):
                    ops_cli._snapshot_for_migration(
                        {"status": "degraded", "foreign_key_schema_mismatch": True}
                    )
            self.assertEqual(list((state / "incident-backups").glob("*.sqlite3")), [])

    def test_composite_foreign_key_mismatch_is_classified_for_additive_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    "CREATE TABLE parent(a INTEGER PRIMARY KEY);"
                    "CREATE TABLE child(a INTEGER, b INTEGER, "
                    "FOREIGN KEY(a,b) REFERENCES parent(a,b));"
                )
                connection.execute(f"PRAGMA user_version = {ops_cli.SQLITE_SCHEMA_VERSION - 1}")
            with mock.patch.object(ops_cli, "DATABASE", database):
                result = ops_cli._probe_database()
            self.assertEqual(result["integrity"], "ok")
            self.assertEqual(result["foreign_keys"], "schema_mismatch")
            self.assertTrue(result["foreign_key_schema_mismatch"])

    def test_migration_snapshot_records_failed_fk_check_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "alpha.sqlite3"
            state = Path(temporary) / "ops"
            with sqlite3.connect(database) as connection:
                connection.executescript(
                    "CREATE TABLE parent(a INTEGER PRIMARY KEY);"
                    "CREATE TABLE child(a INTEGER, b INTEGER, "
                    "FOREIGN KEY(a,b) REFERENCES parent(a,b));"
                )
                connection.execute(f"PRAGMA user_version = {ops_cli.SQLITE_SCHEMA_VERSION - 1}")
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(ops_cli, "STATE", state),
            ):
                health = ops_cli._probe_database()
                ops_cli._snapshot_for_migration(health)
            snapshot = next((state / "incident-backups").glob("*.sqlite3"))
            metadata = json.loads(snapshot.with_suffix(".json").read_text())
            self.assertEqual(metadata["integrity_check"], "ok")
            self.assertEqual(metadata["foreign_key_check"], "failed_before_migration")
            self.assertEqual(metadata["foreign_key_error_class"], "foreign_key_schema_mismatch")
            self.assertEqual(metadata["database_sha256"], ops_cli._sha256_file(snapshot))

    def test_migration_snapshot_restores_pre_change_database_to_new_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "alpha.sqlite3"
            state = root / "ops"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE marker(value TEXT)")
                connection.execute("INSERT INTO marker VALUES ('before')")
                connection.execute(f"PRAGMA user_version = {ops_cli.SQLITE_SCHEMA_VERSION - 1}")
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(ops_cli, "STATE", state),
            ):
                health = ops_cli._probe_database()
                ops_cli._snapshot_for_migration(health)
                snapshot = next((state / "incident-backups").glob("*.sqlite3"))
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE marker SET value = 'after'")
            restored = root / "restored.sqlite3"
            restore_database(snapshot, restored)
            with sqlite3.connect(restored) as connection:
                self.assertEqual(connection.execute("SELECT value FROM marker").fetchone()[0], "before")

    def test_incident_backup_retention_requires_closed_incident_and_verified_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "ops"
            incidents = state / "incidents"
            backups = state / "incident-backups"
            incidents.mkdir(parents=True, mode=0o700)
            backups.mkdir(mode=0o700)
            now = datetime(2026, 11, 12, tzinfo=timezone.utc)
            expired_id = "12345678-abcd-4abc-8abc-123456789abc"
            expired = backups / "expired.sqlite3"
            expired.write_bytes(b"verified old snapshot")
            os.chmod(expired, 0o600)
            expired.with_suffix(".json").write_text(
                json.dumps({
                    "project_id": ops_cli.PROJECT_ID,
                    "incident_id": expired_id,
                    "database_sha256": ops_cli._sha256_file(expired),
                })
            )
            os.chmod(expired.with_suffix(".json"), 0o600)
            expired_incident = incidents / f"{expired_id}.json"
            expired_incident.write_text(json.dumps({
                "incident_id": expired_id,
                "status": "closed",
                "closed_at": (now - timedelta(days=31)).isoformat(),
            }))
            os.chmod(expired_incident, 0o600)
            keep_id = "12345678-abcd-4abc-8abc-123456789abd"
            keep = backups / "open.sqlite3"
            keep.write_bytes(b"open incident snapshot")
            os.chmod(keep, 0o600)
            keep.with_suffix(".json").write_text(json.dumps({
                "project_id": ops_cli.PROJECT_ID,
                "incident_id": keep_id,
                "database_sha256": ops_cli._sha256_file(keep),
            }))
            os.chmod(keep.with_suffix(".json"), 0o600)
            open_incident = incidents / f"{keep_id}.json"
            open_incident.write_text(json.dumps({
                "incident_id": keep_id,
                "status": "open",
            }))
            os.chmod(open_incident, 0o600)
            tampered = backups / "tampered.sqlite3"
            tampered.write_bytes(b"changed after snapshot")
            os.chmod(tampered, 0o600)
            tampered.with_suffix(".json").write_text(json.dumps({
                "project_id": ops_cli.PROJECT_ID,
                "incident_id": expired_id,
                "database_sha256": "0" * 64,
            }))
            os.chmod(tampered.with_suffix(".json"), 0o600)
            unlinked = backups / "unlinked.sqlite3"
            unlinked.write_bytes(b"uncertain snapshot")
            os.chmod(unlinked, 0o600)
            unlinked.with_suffix(".json").write_text(json.dumps({
                "project_id": ops_cli.PROJECT_ID,
                "database_sha256": ops_cli._sha256_file(unlinked),
            }))
            os.chmod(unlinked.with_suffix(".json"), 0o600)
            with (
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
            ):
                result = ops_cli._prune_incident_backups(30, now=now)
            self.assertEqual(result["status"], "evidence_uncertain")
            self.assertEqual(result["deleted"], 1)
            self.assertEqual(result["retained_uncertain"], 2)
            self.assertFalse(expired.exists())
            self.assertFalse(expired.with_suffix(".json").exists())
            self.assertTrue(keep.exists())
            self.assertTrue(tampered.exists())
            self.assertTrue(unlinked.exists())

    def test_backup_retention_receipt_detects_missing_malformed_and_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            receipt = state / "last-backup-retention.json"
            with mock.patch.object(ops_cli, "STATE", state):
                self.assertEqual(ops_cli._backup_retention_status()["status"], "missing_or_malformed")
                state.mkdir()
                receipt.write_text("{")
                self.assertEqual(ops_cli._backup_retention_status()["status"], "missing_or_malformed")
                receipt.write_text(json.dumps({
                    "status": "healthy",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "deleted": "none",
                    "retained_uncertain": 0,
                }))
                self.assertEqual(ops_cli._backup_retention_status()["status"], "malformed")
                receipt.write_text(json.dumps({
                    "status": "healthy",
                    "completed_at": "2026-11-10T00:00:00Z",
                    "deleted": 0,
                    "retained_uncertain": 0,
                }))
                self.assertEqual(ops_cli._backup_retention_status()["status"], "stale")

    def test_repeated_additive_repair_failure_stays_degraded_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "ops"
            incidents = state / "incidents"
            manifest = ops_cli._manifest_expected()
            with (
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(ops_cli, "_read_manifest", return_value=(manifest, None)),
                mock.patch.object(ops_cli, "_probe_database", return_value={"integrity": "ok"}),
                mock.patch.object(
                    ops_cli, "_prepare_database", side_effect=sqlite3.OperationalError("injected")
                ),
            ):
                self.assertEqual(ops_cli.maintain(), 2)
                self.assertEqual(ops_cli.maintain(), 2)
                receipt = json.loads((state / "last-maintenance.json").read_text())
                self.assertEqual(receipt["exit_code"], 2)
                self.assertEqual(receipt["error"], "OperationalError")

                def failed_diagnosis(path: Path) -> None:
                    value = json.loads(path.read_text())
                    value["ai_status"] = "failed"
                    path.write_text(json.dumps(value))

                with mock.patch.object(ops_cli, "_dispatch_ai", side_effect=failed_diagnosis):
                    first = ops_cli._incident("same-repair-failure", {"database": {"status": "degraded"}})
                    second = ops_cli._incident("same-repair-failure", {"database": {"status": "degraded"}})
            self.assertEqual(first, second)
            self.assertEqual(len(list(incidents.glob("*.json"))), 1)

    def test_maintenance_success_records_fresh_receipts_and_runs_retention_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "alpha.sqlite3"
            state = root / "ops"
            with sqlite3.connect(database) as connection:
                connection.execute(f"PRAGMA user_version = {ops_cli.SQLITE_SCHEMA_VERSION}")
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=b'{"backup_status":"verified"}', stderr=b""
            )
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "_read_manifest", return_value=(ops_cli._manifest_expected(), None)),
                mock.patch.object(ops_cli.subprocess, "run", return_value=completed) as run,
            ):
                self.assertEqual(ops_cli.maintain(), 0)
            run.assert_called_once()
            maintenance = json.loads((state / "last-maintenance.json").read_text())
            retention = json.loads((state / "last-backup-retention.json").read_text())
            self.assertEqual(maintenance["exit_code"], 0)
            self.assertEqual(retention["status"], "healthy")


class OpsIncidentTests(unittest.TestCase):
    """Check dispatch deduplication and health evidence completeness."""

    def test_expired_inactive_diagnosis_becomes_terminal_and_closes_on_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            incidents = Path(temporary) / "incidents"
            incidents.mkdir()
            incident = incidents / "incident.json"
            incident.write_text(
                json.dumps(
                    {
                        "incident_id": "12345678-abcd-4abc-8abc-123456789abc",
                        "status": "open",
                        "created_at": "2000-01-01T00:00:00Z",
                        "ai_status": "running",
                    }
                )
            )
            with (
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(ops_cli, "_ai_unit_active", return_value=False),
            ):
                ops_cli._reconcile_abandoned_ai_runs()
                ops_cli._close_recovered_incidents()
            result = json.loads(incident.read_text())
        self.assertEqual(result["ai_status"], "timeout")
        self.assertEqual(result["status"], "closed")

    def test_expired_diagnosis_remains_running_when_unit_state_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            incidents = Path(temporary) / "incidents"
            incidents.mkdir()
            incident = incidents / "incident.json"
            incident.write_text(
                json.dumps(
                    {
                        "incident_id": "12345678-abcd-4abc-8abc-123456789abc",
                        "status": "open",
                        "created_at": "2000-01-01T00:00:00Z",
                        "ai_status": "running",
                    }
                )
            )
            with (
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(ops_cli, "_ai_unit_active", return_value=None),
            ):
                ops_cli._reconcile_abandoned_ai_runs()
            result = json.loads(incident.read_text())
        self.assertEqual(result["ai_status"], "running")

    def test_incidents_deduplicate_identical_open_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:

            def dispatched(path: Path) -> None:
                value = json.loads(path.read_text())
                value["ai_status"] = "dispatching"
                path.write_text(json.dumps(value))

            with (
                mock.patch.object(ops_cli, "INCIDENTS", Path(temporary) / "incidents"),
                mock.patch.object(ops_cli, "_dispatch_ai", side_effect=dispatched) as dispatch,
            ):
                first = ops_cli._incident("same-fingerprint", {"database": {"status": "degraded"}})
                second = ops_cli._incident("same-fingerprint", {"database": {"status": "degraded"}})
                self.assertEqual(first, second)
                dispatch.assert_called_once()

    def test_repeated_failed_diagnosis_waits_for_retry_backoff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:

            def failed(path: Path) -> None:
                value = json.loads(path.read_text())
                value["ai_status"] = "failed"
                path.write_text(json.dumps(value))

            with (
                mock.patch.object(ops_cli, "INCIDENTS", Path(temporary) / "incidents"),
                mock.patch.object(ops_cli, "_dispatch_ai", side_effect=failed) as dispatch,
            ):
                first = ops_cli._incident("repeat-failure", {"runtime": {"status": "unavailable"}})
                second = ops_cli._incident("repeat-failure", {"runtime": {"status": "unavailable"}})
                stored_path = next((Path(temporary) / "incidents").glob("*.json"))
                stored = json.loads(stored_path.read_text())
            self.assertEqual(first, second)
            self.assertEqual(stored["status"], "open")
            self.assertEqual(stored["ai_status"], "failed")
            dispatch.assert_called_once()

    def test_failed_diagnosis_retries_after_backoff_without_duplicate_incident(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            incidents = Path(temporary) / "incidents"
            incidents.mkdir()
            incident_id = "12345678-abcd-4abc-8abc-123456789abc"
            incident_path = incidents / f"{incident_id}.json"
            now = datetime(2026, 11, 13, 0, 0, tzinfo=timezone.utc)
            incident_path.write_text(json.dumps({
                "incident_id": incident_id,
                "fingerprint": "retryable-fault",
                "status": "open",
                "ai_status": "timeout",
                "ai_attempt_count": 1,
                "ai_finished_at": (now - timedelta(seconds=ops_cli.AI_RETRY_BASE_SECONDS)).isoformat(),
            }))

            def dispatched(path: Path) -> None:
                value = json.loads(path.read_text())
                value["ai_status"] = "dispatching"
                path.write_text(json.dumps(value))

            with (
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(ops_cli, "_now", return_value=now),
                mock.patch.object(ops_cli, "_dispatch_ai", side_effect=dispatched) as dispatch,
            ):
                result = ops_cli._incident(
                    "retryable-fault", {"runtime": {"status": "degraded"}}
                )
                stored = json.loads(incident_path.read_text())
            self.assertEqual(result, incident_id)
            self.assertEqual(stored["ai_status"], "dispatching")
            dispatch.assert_called_once_with(incident_path)

    def test_diagnosis_retry_backoff_is_capped(self) -> None:
        self.assertEqual(ops_cli._retry_delay_seconds(1), 300)
        self.assertEqual(ops_cli._retry_delay_seconds(2), 600)
        self.assertEqual(ops_cli._retry_delay_seconds(100), 21600)

    def test_one_shot_healthy_check_does_not_close_monitor_incident(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            incidents = Path(temporary) / "incidents"
            incidents.mkdir()
            prior_components: dict[str, dict[str, Any]] = {
                name: {"status": "healthy"}
                for name in (
                    "binding",
                    "database",
                    "runtime",
                    "backup",
                    "backup_retention",
                    "monitor",
                    "acceptance_history",
                    "maintenance_timer",
                    "maintenance",
                    "health",
                )
            }
            prior_components["runtime"] = {
                "status": "degraded",
                "source_fingerprint_match": False,
            }
            fingerprint = ops_cli._incident_fingerprint(prior_components)
            incident_id = "12345678-abcd-4abc-8abc-123456789abc"
            incident_path = incidents / f"{incident_id}.json"
            incident_path.write_text(
                json.dumps(
                    {
                        "incident_id": incident_id,
                        "fingerprint": fingerprint,
                        "status": "open",
                        "ai_status": "timeout",
                        "components": prior_components,
                    }
                )
            )
            healthy = {"status": "healthy"}
            with (
                mock.patch.object(ops_cli, "INCIDENTS", incidents),
                mock.patch.object(
                    ops_cli, "_read_manifest", return_value=(ops_cli._manifest_expected(), None)
                ),
                mock.patch.object(ops_cli, "_binding_status", return_value=healthy),
                mock.patch.object(ops_cli, "_probe_database", return_value=healthy),
                mock.patch.object(ops_cli, "_runtime_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_retention_status", return_value=healthy),
                mock.patch.object(ops_cli, "_monitor_status", return_value=healthy),
                mock.patch.object(ops_cli, "_acceptance_history_status", return_value=healthy),
                mock.patch.object(ops_cli, "_maintenance_timer_status", return_value=healthy),
                mock.patch.object(ops_cli, "_maintenance_status", return_value=healthy),
                mock.patch.object(ops_cli, "_probe_health", return_value=healthy),
                mock.patch.object(ops_cli, "_close_recovered_incidents") as close,
                mock.patch.object(ops_cli, "_reconcile_abandoned_ai_runs") as reconcile,
                mock.patch.object(ops_cli, "_dispatch_ai") as dispatch,
            ):
                one_shot = ops_cli.check()
                self.assertEqual(one_shot["status"], "healthy")
                self.assertIsNone(one_shot["incident_id"])
                close.assert_not_called()
                reconcile.assert_not_called()
                with mock.patch.object(
                    ops_cli,
                    "_runtime_status",
                    return_value={"status": "degraded", "source_fingerprint_match": False},
                ):
                    monitor_observation = ops_cli.check()
                self.assertEqual(monitor_observation["incident_id"], incident_id)
                dispatch.assert_not_called()
            stored = json.loads(incident_path.read_text())
        self.assertEqual(stored["status"], "open")
        self.assertEqual(stored["fingerprint"], fingerprint)

    def test_monitor_check_reconciles_ai_without_premature_recovery_closure(self) -> None:
        healthy = {"status": "healthy"}
        with (
            mock.patch.object(
                ops_cli, "_read_manifest", return_value=(ops_cli._manifest_expected(), None)
            ),
            mock.patch.object(ops_cli, "_binding_status", return_value=healthy),
            mock.patch.object(ops_cli, "_probe_database", return_value=healthy),
            mock.patch.object(ops_cli, "_runtime_status", return_value=healthy),
            mock.patch.object(ops_cli, "_backup_status", return_value=healthy),
            mock.patch.object(ops_cli, "_backup_retention_status", return_value=healthy),
            mock.patch.object(ops_cli, "_monitor_status", return_value=healthy),
            mock.patch.object(ops_cli, "_acceptance_history_status", return_value=healthy),
            mock.patch.object(ops_cli, "_maintenance_timer_status", return_value=healthy),
            mock.patch.object(ops_cli, "_maintenance_status", return_value=healthy),
            mock.patch.object(ops_cli, "_probe_health", return_value=healthy),
            mock.patch.object(ops_cli, "_reconcile_abandoned_ai_runs") as reconcile,
            mock.patch.object(ops_cli, "_close_recovered_incidents") as close,
        ):
            result = ops_cli.check(manage_incidents=True)
        self.assertEqual(result["status"], "healthy")
        reconcile.assert_called_once()
        close.assert_not_called()

    def test_each_check_component_failure_dispatches_one_incident(self) -> None:
        healthy = {"status": "healthy"}
        faults = {
            "binding": "_binding_status",
            "database": "_probe_database",
            "runtime": "_runtime_status",
            "backup": "_backup_status",
            "backup_retention": "_backup_retention_status",
            "monitor": "_monitor_status",
            "acceptance_history": "_acceptance_history_status",
            "maintenance_timer": "_maintenance_timer_status",
            "maintenance": "_maintenance_status",
            "health": "_probe_health",
        }
        for component, helper in faults.items():
            with self.subTest(component=component), tempfile.TemporaryDirectory() as temporary:
                incidents = Path(temporary) / "incidents"

                def dispatched(path: Path) -> None:
                    value = json.loads(path.read_text())
                    value["ai_status"] = "dispatching"
                    path.write_text(json.dumps(value))

                with (
                    mock.patch.object(ops_cli, "INCIDENTS", incidents),
                    mock.patch.object(
                        ops_cli,
                        "_read_manifest",
                        return_value=(ops_cli._manifest_expected(), None),
                    ),
                    mock.patch.object(ops_cli, "_binding_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_probe_database", return_value=healthy),
                    mock.patch.object(ops_cli, "_runtime_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_backup_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_backup_retention_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_monitor_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_acceptance_history_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_maintenance_timer_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_maintenance_status", return_value=healthy),
                    mock.patch.object(ops_cli, "_probe_health", return_value=healthy),
                    mock.patch.object(ops_cli, helper, return_value={"status": "degraded"}),
                    mock.patch.object(ops_cli, "_dispatch_ai", side_effect=dispatched) as dispatch,
                ):
                    first = ops_cli.check()
                    second = ops_cli.check()
                self.assertEqual(first["gates"], [component])
                self.assertEqual(first["incident_id"], second["incident_id"])
                dispatch.assert_called_once()

    def test_health_probe_rejects_stale_dependency_and_incomplete_queue(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        health: dict[str, Any] = {
            "status": "healthy",
            "project_id": ops_cli.PROJECT_ID,
            "observed_at": now,
            "database_observed_at": now,
            "database_observation_complete": True,
            "staging_inventory_complete": True,
            "staging_observed_at": now,
            "staging_regular_file_count": 0,
            "operational_counts": {name: 0 for name in OPERATIONAL_COUNT_NAMES},
            "event_received_count": 0,
            "event_claimed_count": 0,
            "event_failed_count": 0,
            "event_quarantined_count": 0,
            "event_expired_claim_count": 0,
            "oldest_pending_event_age_seconds": None,
            "gate_codes": [],
            "dependencies": [
                {"name": name, "status": "healthy", "observed_at": now}
                for name in ops_cli.HEALTH_NAMES
            ],
        }
        payload = json.dumps(
            {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
        ).encode()
        completed = subprocess.CompletedProcess([], 0, payload, b"")
        manifest = ops_cli._manifest_expected()
        with mock.patch.object(ops_resource_monitor.subprocess, "run", return_value=completed):
            self.assertEqual(ops_cli._probe_health(manifest)["status"], "healthy")
            health["database_observation_complete"] = False
            stale_payload = json.dumps(
                {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
            ).encode()
            with mock.patch.object(
                ops_cli.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stale_payload, b""),
            ):
                result = ops_cli._probe_health(manifest)
            self.assertEqual(result["status"], "degraded")
            self.assertFalse(result["queue_snapshot_complete"])
            health["database_observation_complete"] = True
            for field, invalid in (
                ("database_observed_at", None),
                ("database_observed_at", "2020-01-01T00:00:00+00:00"),
                ("staging_observed_at", None),
                ("staging_observed_at", "2020-01-01T00:00:00+00:00"),
                ("staging_regular_file_count", None),
                ("event_expired_claim_count", None),
                ("event_received_count", -1),
                ("oldest_pending_event_age_seconds", -1),
            ):
                original = health.get(field)
                health[field] = invalid
                self.assertEqual(
                    ops_cli._summarize_health(
                        {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
                    )["status"],
                    "degraded",
                    field,
                )
                health[field] = original
            original_counts = health["operational_counts"]
            health["operational_counts"] = {}
            self.assertFalse(
                ops_cli._summarize_health(
                    {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
                )["queue_snapshot_complete"]
            )
            health["operational_counts"] = original_counts
            original_dependencies = health["dependencies"]
            health["dependencies"] = [*original_dependencies, original_dependencies[0]]
            self.assertEqual(
                ops_cli._summarize_health(
                    {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
                )["status"],
                "degraded",
            )
            health["dependencies"] = original_dependencies
            for dependency in health["dependencies"]:
                dependency["status"] = "degraded"
                summary = ops_cli._summarize_health(
                    {"connected": True, "project_id": ops_cli.PROJECT_ID, "health": health}
                )
                self.assertEqual(summary["status"], "degraded", dependency["name"])
                dependency["status"] = "healthy"

    def test_runtime_requires_source_install_parity_and_both_entrypoints(self) -> None:
        runtime = ops_cli._runtime_status()
        self.assertEqual(runtime["status"], "healthy")
        self.assertEqual(runtime["source_version"], runtime["installed_version"])
        self.assertTrue(runtime["source_module_match"])
        self.assertTrue(runtime["source_fingerprint_match"])
        self.assertTrue(runtime["entrypoints_available"])
        with mock.patch.object(ops_cli, "SOURCE_FINGERPRINT_AT_IMPORT", "mismatched"):
            self.assertEqual(ops_cli._runtime_status()["status"], "degraded")

    def test_each_health_dependency_fault_remains_a_single_deduplicated_incident(self) -> None:
        for dependency in sorted(ops_cli.HEALTH_NAMES):
            with self.subTest(dependency=dependency), tempfile.TemporaryDirectory() as temporary:
                incidents = Path(temporary) / "incidents"

                def dispatched(path: Path) -> None:
                    value = json.loads(path.read_text())
                    value["ai_status"] = "dispatching"
                    path.write_text(json.dumps(value))

                healthy_components = {"status": "healthy"}
                unhealthy_health: dict[str, Any] = {
                    "status": "degraded",
                    "dependencies": {name: {"status": "healthy"} for name in ops_cli.HEALTH_NAMES},
                }
                unhealthy_health["dependencies"][dependency]["status"] = "unknown"
                with (
                    mock.patch.object(ops_cli, "INCIDENTS", incidents),
                    mock.patch.object(
                        ops_cli,
                        "_read_manifest",
                        return_value=(ops_cli._manifest_expected(), None),
                    ),
                    mock.patch.object(ops_cli, "_binding_status", return_value=healthy_components),
                    mock.patch.object(ops_cli, "_probe_database", return_value=healthy_components),
                    mock.patch.object(ops_cli, "_backup_status", return_value=healthy_components),
                    mock.patch.object(
                        ops_cli, "_backup_retention_status", return_value=healthy_components
                    ),
                    mock.patch.object(ops_cli, "_monitor_status", return_value=healthy_components),
                    mock.patch.object(
                        ops_cli, "_acceptance_history_status", return_value=healthy_components
                    ),
                    mock.patch.object(
                        ops_cli, "_maintenance_timer_status", return_value=healthy_components
                    ),
                    mock.patch.object(
                        ops_cli, "_maintenance_status", return_value=healthy_components
                    ),
                    mock.patch.object(ops_cli, "_probe_health", return_value=unhealthy_health),
                    mock.patch.object(ops_cli, "_dispatch_ai", side_effect=dispatched) as dispatch,
                ):
                    first = ops_cli.check()
                    second = ops_cli.check()
                self.assertIn("health", first["gates"])
                self.assertEqual(first["incident_id"], second["incident_id"])
                dispatch.assert_called_once()

    def test_failed_health_command_is_unknown(self) -> None:
        with mock.patch.object(
            ops_cli.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 1)
        ):
            result = ops_cli._probe_health(ops_cli._manifest_expected())
        self.assertEqual(result["status"], "probe_failed")

    def test_codex_token_usage_must_be_observable_for_bounded_runs(self) -> None:
        completed = json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 8,
                    "cached_input_tokens": 7,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 5,
                    "reasoning_output_tokens": 2,
                },
            }
        ).encode()
        unbounded = json.dumps({"type": "turn.completed", "usage": {}}).encode()
        self.assertEqual(ops_cli._reported_token_count(completed), (True, 13))
        self.assertEqual(ops_cli._reported_token_count(unbounded), (True, None))

    def test_codex_token_budget_does_not_double_count_cached_input(self) -> None:
        completed = json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 18512,
                    "cached_input_tokens": 11520,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 5,
                    "reasoning_output_tokens": 0,
                },
            }
        ).encode()
        self.assertEqual(ops_cli._reported_token_count(completed), (True, 18517))
        self.assertLess(18517, ops_cli.MAX_AI_TOKENS)

    def test_codex_run_stops_reading_after_token_budget_exhaustion(self) -> None:
        """A completed over-budget turn must stop the run before more output is read."""
        completed = json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": ops_cli.MAX_AI_TOKENS, "output_tokens": 1},
        }).encode() + b"\n"
        class FakeProcess:
            def __init__(self) -> None:
                self.stdout = mock.MagicMock()
                self.stdout.fileno.return_value = 123
                self.returncode: int | None = None
                self.kill_calls = 0

            def __enter__(self) -> "FakeProcess":
                return self

            def __exit__(self, *_args: Any) -> None:
                return None

            def poll(self) -> int | None:
                return self.returncode

            def kill(self) -> None:
                self.kill_calls += 1
                self.returncode = -9

            def wait(self, timeout: int) -> int:
                del timeout
                return self.returncode or 0

        process = FakeProcess()

        class ReadySelector:
            def register(self, *_args: Any) -> None:
                return None

            def select(self, _timeout: float) -> list[tuple[None, None]]:
                return [(None, None)]

            def close(self) -> None:
                return None

        with (
            mock.patch.object(ops_cli.subprocess, "Popen", return_value=process),
            mock.patch.object(ops_cli.selectors, "DefaultSelector", return_value=ReadySelector()),
            mock.patch.object(
                ops_cli.os,
                "read",
                side_effect=[completed, b"extra output\n"],
            ) as read,
        ):
            returncode, _output, tokens, exhausted, unobservable = ops_cli._run_codex_bounded(
                ["codex", "exec"]
            )
        self.assertEqual(returncode, -9)
        self.assertEqual(tokens, ops_cli.MAX_AI_TOKENS + 1)
        self.assertTrue(exhausted)
        self.assertFalse(unobservable)
        read.assert_called_once()
        self.assertEqual(process.kill_calls, 1)

    def test_codex_dispatch_has_hard_wall_context_and_output_bounds(self) -> None:
        command = ops_cli._codex_command("bounded test prompt")
        self.assertEqual(ops_cli.MAX_AI_SECONDS, 300)
        self.assertIn("--disable", command)
        self.assertIn("multi_agent", command)
        self.assertIn("model_context_window=8192", command)
        self.assertIn("model_auto_compact_token_limit=6144", command)
        self.assertIn("tool_output_token_limit=2048", command)
        self.assertIn('models.new_thread.model_reasoning_effort="low"', command)
        self.assertIn("--worktree", command)
        self.assertIn("workspace-write", command)

    def test_backup_requires_fresh_private_file_and_verified_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "global.sqlite3"
            backups = root / "backups"
            backups.mkdir(mode=0o700)
            backup = (
                backups / f"curator-v2-{ops_cli._now().astimezone().date().isoformat()}.sqlite3"
            )
            backup.write_bytes(b"verified placeholder")
            os.chmod(backup, 0o600)
            state = root / "ops"
            state.mkdir(mode=0o700)
            marker = {
                "completed_at": ops_cli._iso(),
                "exit_code": 0,
                "stdout": json.dumps({"backup_status": "verified"}),
            }
            (state / "last-maintenance.json").write_text(json.dumps(marker))
            with (
                mock.patch.object(ops_cli, "DATABASE", database),
                mock.patch.object(ops_cli, "STATE", state),
            ):
                self.assertEqual(ops_cli._backup_status()["status"], "healthy")
                os.chmod(backup, 0o644)
                self.assertEqual(ops_cli._backup_status()["status"], "stale_or_unverified")


class OpsServiceTests(unittest.TestCase):
    """Check monitor service recovery and resource ceilings."""

    def test_monitor_reports_measured_cpu_and_memory_budgets(self) -> None:
        active_since = time.monotonic_ns() // 1000 - 600_000_000
        output = (
            "ActiveState=active\n"
            f"ActiveEnterTimestampMonotonic={active_since}\n"
            "CPUUsageNSec=5000000000\n"
            "MemoryCurrent=33554432\n"
            "MemoryMax=67108864\n"
        ).encode()
        completed = subprocess.CompletedProcess([], 0, output, b"")
        with mock.patch.object(ops_resource_monitor.subprocess, "run", return_value=completed):
            result = ops_cli._monitor_status()
        self.assertEqual(result["status"], "healthy")
        resource = result["resource"]
        self.assertEqual(resource["average_cpu_status"], "healthy")
        self.assertLessEqual(resource["average_cpu_percent"], 1.0)
        self.assertEqual(resource["memory_status"], "healthy")

    def test_monitor_degrades_when_warm_cpu_average_exceeds_target(self) -> None:
        active_since = time.monotonic_ns() // 1000 - 600_000_000
        output = (
            "ActiveState=active\n"
            f"ActiveEnterTimestampMonotonic={active_since}\n"
            "CPUUsageNSec=12000000000\n"
            "MemoryCurrent=33554432\n"
            "MemoryMax=67108864\n"
        ).encode()
        completed = subprocess.CompletedProcess([], 0, output, b"")
        with mock.patch.object(ops_cli.subprocess, "run", return_value=completed):
            result = ops_cli._monitor_status()
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["resource"]["average_cpu_status"], "over_target")

    def test_unavailable_maintenance_runtime_is_reported_as_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                mock.patch.object(ops_cli, "ROOT", root),
                mock.patch.object(
                    ops_cli,
                    "_read_manifest",
                    return_value=(ops_cli._manifest_expected(), None),
                ),
                mock.patch.object(ops_cli, "_binding_status", return_value={"status": "healthy"}),
                mock.patch.object(ops_cli, "_probe_database", return_value={"status": "healthy"}),
                mock.patch.object(ops_cli, "_backup_status", return_value={"status": "healthy"}),
                mock.patch.object(ops_cli, "_monitor_status", return_value={"status": "healthy"}),
                mock.patch.object(
                    ops_cli, "_maintenance_timer_status", return_value={"status": "healthy"}
                ),
                mock.patch.object(
                    ops_cli, "_maintenance_status", return_value={"status": "healthy"}
                ),
                mock.patch.object(ops_cli, "_probe_health", return_value={"status": "healthy"}),
            ):
                result = ops_cli.check(dispatch=False)
        self.assertEqual(result["components"]["runtime"]["status"], "unavailable")
        self.assertIn("runtime", result["gates"])

    def test_health_history_keeps_private_resource_and_gate_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            result = {
                "checked_at": ops_cli._iso(),
                "status": "degraded",
                "gates": ["health"],
                "incident_id": "incident-id",
                "components": {
                    "monitor": {
                        "status": "healthy",
                        "resource": {"average_cpu_percent": 0.2},
                    }
                },
            }
            ops_resource_monitor.record_check(result, state, ops_cli.UID)
            sample_path = next(state.glob("checks-*.jsonl"))
            sample = json.loads(sample_path.read_text())
            sample_mode = sample_path.stat().st_mode & 0o777
        self.assertEqual(sample["gates"], ["health"])
        self.assertEqual(sample["monitor"]["resource"]["average_cpu_percent"], 0.2)
        self.assertEqual(sample_mode, 0o600)

    def test_acceptance_history_requires_fresh_well_formed_private_sample(self) -> None:
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            day = now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
            sample_path = state / f"checks-{day}.jsonl"
            sample: dict[str, Any] = {
                "checked_at": now.isoformat(),
                "status": "healthy",
                "gates": [],
                "incident_id": None,
                "monitor": {"status": "healthy"},
            }
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "missing",
            )
            warming = ops_resource_monitor.acceptance_history_status(
                state, ops_cli.UID, allow_missing=True, now=now
            )
            self.assertEqual(warming["status"], "healthy")
            self.assertEqual(warming["phase"], "warming_up")
            sample_path.write_text(json.dumps(sample) + "\n")
            os.chmod(sample_path, 0o600)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "healthy",
            )
            sample["checked_at"] = (now - timedelta(seconds=181)).isoformat()
            sample_path.write_text(json.dumps(sample) + "\n")
            os.chmod(sample_path, 0o600)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "stale",
            )
            sample_path.write_text("{malformed}\n")
            os.chmod(sample_path, 0o600)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "malformed",
            )
            sample_path.write_text("{\"payload\":\"" + ("x" * 9000) + "\"}\n")
            os.chmod(sample_path, 0o600)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "malformed",
            )
            earlier: dict[str, Any] = {
                **sample,
                "checked_at": (now - timedelta(seconds=1)).isoformat(),
            }
            sample_path.write_text(
                json.dumps({**sample, "checked_at": now.isoformat()})
                + "\n"
                + json.dumps(earlier)
                + "\n"
            )
            os.chmod(sample_path, 0o600)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "malformed",
            )
            sample_path.write_text(json.dumps({**sample, "checked_at": now.isoformat()}) + "\n")
            os.chmod(sample_path, 0o644)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "permissions",
            )
            os.chmod(sample_path, 0o600)
            os.chmod(state, 0o755)
            self.assertEqual(
                ops_resource_monitor.acceptance_history_status(
                    state, ops_cli.UID, now=now
                )["status"],
                "permissions",
            )

    def test_acceptance_history_missing_grace_ends_at_two_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            state.mkdir(mode=0o700)
            with mock.patch.object(ops_cli, "STATE", state):
                warming = ops_cli._acceptance_history_status(
                    {"status": "healthy", "resource": {"elapsed_seconds": 119}}
                )
                self.assertEqual(warming["status"], "healthy")
                self.assertEqual(warming["phase"], "warming_up")
                self.assertEqual(
                    ops_cli._acceptance_history_status(
                        {"status": "healthy", "resource": {"elapsed_seconds": 120}}
                    )["status"],
                    "missing",
                )

    def test_startup_grace_does_not_dispatch_until_history_is_overdue(self) -> None:
        healthy = {"status": "healthy"}
        monitor: dict[str, Any] = {"status": "healthy", "resource": {"elapsed_seconds": 119}}
        with tempfile.TemporaryDirectory() as temporary:
            with (
                mock.patch.object(ops_cli, "STATE", Path(temporary)),
                mock.patch.object(
                    ops_cli, "_read_manifest", return_value=(ops_cli._manifest_expected(), None)
                ),
                mock.patch.object(ops_cli, "_binding_status", return_value=healthy),
                mock.patch.object(ops_cli, "_probe_database", return_value=healthy),
                mock.patch.object(ops_cli, "_runtime_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_status", return_value=healthy),
                mock.patch.object(ops_cli, "_backup_retention_status", return_value=healthy),
                mock.patch.object(ops_cli, "_monitor_status", return_value=monitor),
                mock.patch.object(ops_cli, "_maintenance_timer_status", return_value=healthy),
                mock.patch.object(ops_cli, "_maintenance_status", return_value=healthy),
                mock.patch.object(ops_cli, "_probe_health", return_value=healthy),
                mock.patch.object(ops_cli, "_incident", return_value="incident") as incident,
            ):
                warming = ops_cli.check()
                self.assertEqual(warming["status"], "healthy")
                self.assertEqual(warming["gates"], [])
                incident.assert_not_called()
                monitor["resource"]["elapsed_seconds"] = 120
                overdue = ops_cli.check()
                self.assertEqual(overdue["gates"], ["acceptance_history"])
                self.assertEqual(overdue["incident_id"], "incident")
                incident.assert_called_once()

    def test_journal_record_reports_incident_age_and_next_action_without_raw_details(self) -> None:
        record = ops_cli._journal_record(
            {
                "checked_at": "2026-11-12T08:00:00Z",
                "project_id": ops_cli.PROJECT_ID,
                "status": "degraded",
                "gates": ["health"],
                "incident_id": "incident-id",
                "next_action": "inspect incident",
                "components": {
                    "health": {
                        "status": "degraded",
                        "age_seconds": 2,
                        "dependencies": {"event_router": {"status": "healthy", "age_seconds": 2}},
                        "private_detail": "/home/owner/private-value",
                    }
                },
            }
        )
        wire = json.dumps(record)
        self.assertEqual(record["incident_id"], "incident-id")
        self.assertEqual(record["components"]["health"]["age_seconds"], 2)
        self.assertEqual(record["next_action"], "inspect incident")
        self.assertNotIn("private_detail", wire)
        self.assertNotIn("private-value", wire)

    def test_resident_service_has_restart_and_resource_limits(self) -> None:
        root = Path(__file__).resolve().parents[1]
        service = (root / "deploy/systemd/user/curatormd-v2-ops@.service").read_text()
        source = (root / "src/curatormd_v2/ops_cli.py").read_text()
        self.assertIn("Restart=on-failure", service)
        self.assertIn("CPUQuota=5%", service)
        self.assertIn("MemoryMax=64M", service)
        self.assertIn("time.sleep(max(0, 60", source)

    def test_monitor_lock_recovers_when_systemd_restarts_the_worker(self) -> None:
        class StopAfterOneCheck(Exception):
            pass

        result: dict[str, Any] = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": "healthy",
            "gates": [],
            "components": {
                "maintenance_timer": {"status": "healthy"},
                "monitor": {"resource": {"status": "healthy"}},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            lock = state / "monitor.lock"
            with (
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "LOCK", lock),
                mock.patch.object(ops_cli, "check", return_value=result) as check,
                mock.patch.object(ops_cli, "record_check"),
                mock.patch.object(ops_cli, "_json"),
                mock.patch.object(ops_cli, "_close_recovered_incidents"),
                mock.patch.object(ops_cli, "_journal_record", return_value={"status": "healthy"}),
                mock.patch.object(ops_cli, "_maintenance_due", return_value=False),
                mock.patch("builtins.print"),
                mock.patch.object(ops_cli.time, "sleep", side_effect=StopAfterOneCheck),
            ):
                with self.assertRaises(StopAfterOneCheck):
                    ops_cli.monitor()
                # A service restart starts a fresh worker after the first worker
                # exits; the process lock must have been released on exit.
                with self.assertRaises(StopAfterOneCheck):
                    ops_cli.monitor()
        self.assertEqual(
            check.call_args_list,
            [
                mock.call(dispatch=True, manage_incidents=True),
                mock.call(dispatch=True, manage_incidents=True),
            ],
        )

    def test_history_write_failure_is_reported_and_monitor_recovers(self) -> None:
        class StopAfterTwoChecks(Exception):
            pass

        def healthy_result() -> dict[str, Any]:
            return {
                "status": "healthy",
                "gates": [],
                "components": {
                    "acceptance_history": {"status": "healthy"},
                    "maintenance_timer": {"status": "healthy"},
                },
            }

        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            with (
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "LOCK", state / "monitor.lock"),
                mock.patch.object(ops_cli, "_read_manifest", return_value=(None, "missing")),
                mock.patch.object(ops_cli, "check", side_effect=[healthy_result(), healthy_result()]),
                mock.patch.object(ops_cli, "record_check", side_effect=[OSError("private path"), None]),
                mock.patch.object(ops_cli, "_incident", return_value="incident") as incident,
                mock.patch.object(ops_cli, "_json") as save,
                mock.patch.object(ops_cli, "_close_recovered_incidents") as close,
                mock.patch.object(ops_cli, "_maintenance_due", return_value=False),
                mock.patch("builtins.print") as journal,
                mock.patch.object(ops_cli.time, "sleep", side_effect=[None, StopAfterTwoChecks]),
            ):
                with self.assertRaises(StopAfterTwoChecks):
                    ops_cli.monitor()
            self.assertEqual(incident.call_count, 1)
            self.assertEqual(close.call_count, 1)
            first_result = save.call_args_list[0].args[1]
            self.assertEqual(first_result["gates"], ["acceptance_history"])
            self.assertEqual(first_result["incident_id"], "incident")
            first_journal = json.loads(journal.call_args_list[0].args[0])
            self.assertEqual(first_journal["status"], "degraded")
            self.assertNotIn("private path", json.dumps(first_journal))

    def test_disk_write_failure_keeps_worker_running_and_reports_journal_gate(self) -> None:
        class StopAfterCheck(Exception):
            pass

        result: dict[str, Any] = {
            "status": "healthy",
            "gates": [],
            "components": {
                "acceptance_history": {"status": "healthy"},
                "maintenance_timer": {"status": "healthy"},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "ops"
            with (
                mock.patch.object(ops_cli, "STATE", state),
                mock.patch.object(ops_cli, "LOCK", state / "monitor.lock"),
                mock.patch.object(ops_cli, "_read_manifest", return_value=(None, "missing")),
                mock.patch.object(ops_cli, "check", return_value=result),
                mock.patch.object(ops_cli, "record_check", side_effect=OSError("private path")),
                mock.patch.object(ops_cli, "_incident", side_effect=OSError("private path")),
                mock.patch.object(ops_cli, "_json", side_effect=OSError("private path")),
                mock.patch.object(ops_cli, "_close_recovered_incidents") as close,
                mock.patch.object(ops_cli, "_maintenance_due", return_value=False),
                mock.patch("builtins.print") as journal,
                mock.patch.object(ops_cli.time, "sleep", side_effect=StopAfterCheck),
            ):
                with self.assertRaises(StopAfterCheck):
                    ops_cli.monitor()
            close.assert_not_called()
            event = json.loads(journal.call_args.args[0])
            self.assertEqual(event["gates"], ["acceptance_history", "last_check"])
            self.assertEqual(event["next_action"], "inspect journal; incident recording failed")
            self.assertNotIn("private path", json.dumps(event))

    def test_maintenance_stays_on_existing_six_hour_local_slots(self) -> None:
        zone = ZoneInfo("Asia/Ho_Chi_Minh")
        last = datetime(2026, 11, 12, 13, 50, tzinfo=zone).isoformat()
        with mock.patch.object(ops_cli, "read_maintenance_timestamp", return_value=last):
            self.assertFalse(ops_cli._maintenance_due(datetime(2026, 11, 12, 17, 59, tzinfo=zone)))
            self.assertTrue(ops_cli._maintenance_due(datetime(2026, 11, 12, 18, 0, tzinfo=zone)))
        with mock.patch.object(ops_cli, "read_maintenance_timestamp", return_value=None):
            self.assertTrue(ops_cli._maintenance_due())

    def test_maintenance_timer_is_required_and_reads_only_alpha_unit(self) -> None:
        active = subprocess.CompletedProcess([], 0, b"active\n", b"")
        with mock.patch.object(ops_cli.subprocess, "run", return_value=active) as run:
            self.assertEqual(ops_cli._maintenance_timer_status()["status"], "healthy")
        self.assertIn(
            "curatormd-v2-maintenance@curatormd-v2-dev-alpha.timer",
            run.call_args.args[0],
        )
        inactive = subprocess.CompletedProcess([], 3, b"inactive\n", b"")
        with mock.patch.object(ops_cli.subprocess, "run", return_value=inactive):
            self.assertEqual(ops_cli._maintenance_timer_status()["status"], "inactive")


if __name__ == "__main__":
    unittest.main()
