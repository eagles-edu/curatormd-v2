"""Attended local operator workflow for durable project access."""

from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from project_fixtures import create_consumer_repo

from curatormd_v2 import ProjectAction
from curatormd_v2.access_cli import main
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.project_config import ProjectConfig


class _InteractiveInput(StringIO):
    def __init__(self, value: str, *, interactive: bool = True) -> None:
        super().__init__(value)
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


class AccessCliTests(unittest.TestCase):
    """Require an attended exact confirmation before access-ledger writes."""

    def _project(self, root: Path) -> None:
        create_consumer_repo(root)
        (root / "docs" / "tasks.md").write_text("- [ ] Access CLI test\n")
        (root / "persistence" / "HISTORY.md").write_text("# History\n")
        (root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "cli-project"

            [scope]
            read_paths = ["src", "docs"]

            [checklists]
            tasks = "docs/tasks.md"

            [evidence]
            adapters = []

            [staging]
            root = ".curatormd-v2/staging"

            [persistence]
            targets = ["persistence/HISTORY.md"]
            """
        )
        (root / ".curatormd-v2.toml").chmod(0o600)

    def _run(
        self,
        operation: str,
        root: Path,
        database: Path,
        phrase: str,
        *extra: str,
        attended: bool = True,
    ) -> tuple[int, str, str]:
        stdin = _InteractiveInput(phrase + "\n", interactive=attended)
        stdout = StringIO()
        stderr = StringIO()
        code = main(
            [
                operation,
                "--project-root",
                str(root),
                "--database",
                str(database),
                *extra,
            ],
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_attended_registration_and_exact_grants_activate_the_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            self._register_grants_and_verify_launcher(root, database)
            self._update_config_and_verify_replay(root, database)
            self._suspend_reactivate_and_revoke(root, database)
            self._assert_access_audit(root, database)

    def test_terminal_disposition_requires_reviewed_event_digest_and_exact_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            registered, _, errors = self._run(
                "register", root, database, "REGISTER cli-project",
                "--rationale", "Approve terminal disposition CLI fixture",
            )
            self.assertEqual(registered, 0, errors)
            digest = "a" * 64
            connection = sqlite3.connect(database)
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id,event_id,event_type,payload_sha256,payload_bytes,
                    status,received_at,source_id,source_sequence)
                   VALUES ('cli-project','failed-cli-event','goal.activity_observed',
                           ?,100,'quarantined','2026-10-23T00:00:00Z','cli-source',1)""",
                (digest,),
            )
            connection.commit()
            connection.close()
            pending, _, errors = self._run(
                "deregister", root, database,
                "DEREGISTER cli-project AT BINDING REVISION 1 TRANSITION cli-cutover",
                "--rationale", "Fence source before exact terminal disposition",
                "--expected-revision", "1", "--transition-id", "cli-cutover",
            )
            self.assertEqual(pending, 0, errors)
            viewed, view_output, errors = self._run(
                "view", root, database, "VIEW cli-project ACCESS", "--event-limit", "1"
            )
            self.assertEqual(viewed, 0, errors)
            inventory = json.loads(view_output)["terminal_event_inventory"]
            self.assertEqual(inventory["events"][0]["event_id"], "failed-cli-event")
            self.assertNotIn("payload_json", inventory["events"][0])
            phrase = (
                "DISPOSE EVENT cli-project failed-cli-event AT BINDING REVISION 2 "
                f"SOURCE EPOCH 1 TRANSITION cli-terminal-1 PAYLOAD {digest}"
            )
            disposed, output, errors = self._run(
                "dispose_event", root, database, phrase,
                "--rationale", "Owner approves the exact failed event disposition",
                "--expected-revision", "2", "--transition-id", "cli-terminal-1",
                "--expected-source-epoch", "1", "--event-id", "failed-cli-event",
                "--payload-sha256", digest,
            )
            self.assertEqual(disposed, 0, errors)
            self.assertEqual(
                json.loads(output)["receipt"]["disposition"], "terminal_authorized"
            )

    def _register_grants_and_verify_launcher(self, root: Path, database: Path) -> None:
        """Register one isolated project, grant exact access, and verify launch."""
        subject_id = f"local-uid:{os.geteuid()}"
        registered, registration_output, errors = self._run(
            "register",
            root,
            database,
            "REGISTER cli-project",
            "--rationale",
            "Approve the local CLI integration fixture",
        )
        self.assertEqual(registered, 0, errors)
        self.assertIn("Type exactly: REGISTER cli-project", errors)
        self.assertEqual(
            json.loads(registration_output)["registration"]["status"], "active"
        )
        for action in ("read", "write"):
            phrase = f"GRANT {action} cli-project {subject_id}"
            granted, _, errors = self._run(
                "grant",
                root,
                database,
                phrase,
                "--subject-id",
                subject_id,
                "--action",
                action,
                "--rationale",
                f"Grant exact {action} access for the test profile",
            )
            self.assertEqual(granted, 0, errors)
        runtime = build_local_profile_mcp(
            project_root=root,
            database=database,
            profile_id="gptmd-coding",
            allow_write=True,
        )
        try:
            self.assertTrue(
                runtime.api.authorizer.authorize(
                    runtime.caller, "cli-project", ProjectAction.WRITE
                )
            )
        finally:
            runtime.close()

    def _update_config_and_verify_replay(self, root: Path, database: Path) -> None:
        """Approve one reviewed config transition and prove its retry is stable."""
        config_path = root / ".curatormd-v2.toml"
        config_path.write_text(config_path.read_text() + "\n")
        reviewed_config = ProjectConfig.load(root)
        update_phrase = (
            "UPDATE cli-project TRANSITION cli-config-update-1 AT REVISION 1 "
            "TO REPOSITORY "
            f"{reviewed_config.repository_fingerprint} CONFIG "
            f"{reviewed_config.config_sha256} API "
            f"{reviewed_config.backend_api_version}"
        )
        updated, updated_output, errors = self._run(
            "update",
            root,
            database,
            update_phrase,
            "--rationale",
            "Approve the reviewed config fingerprint change",
            "--expected-revision",
            "1",
            "--transition-id",
            "cli-config-update-1",
        )
        self.assertEqual(updated, 0, errors)
        updated_payload = json.loads(updated_output)
        self.assertEqual(updated_payload["transition_receipt"]["revision"], 2)
        self.assertFalse(updated_payload["replayed"])
        retried, retry_output, errors = self._run(
            "update",
            root,
            database,
            update_phrase,
            "--rationale",
            "Approve the reviewed config fingerprint change",
            "--expected-revision",
            "1",
            "--transition-id",
            "cli-config-update-1",
        )
        self.assertEqual(retried, 0, errors)
        retry_payload = json.loads(retry_output)
        self.assertTrue(retry_payload["replayed"])
        self.assertEqual(
            retry_payload["transition_receipt"],
            updated_payload["transition_receipt"],
        )

    def _suspend_reactivate_and_revoke(self, root: Path, database: Path) -> None:
        subject_id = f"local-uid:{os.geteuid()}"
        """Verify suspension fencing, explicit reactivation, and exact revoke."""
        suspended, _, errors = self._run(
            "suspend",
            root,
            database,
            "SUSPEND cli-project AT REVISION 2 TRANSITION cli-suspend-1",
            "--rationale",
            "Suspend access during the lifecycle regression",
            "--expected-revision",
            "2",
            "--transition-id",
            "cli-suspend-1",
        )
        self.assertEqual(suspended, 0, errors)
        with self.assertRaisesRegex(ValueError, "registration fingerprint"):
            build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="gptmd-coding",
                allow_write=True,
            )
        reactivated, _, errors = self._run(
            "reactivate",
            root,
            database,
            "REACTIVATE cli-project AT REVISION 3 TRANSITION cli-reactivate-1",
            "--rationale",
            "Restore access after the suspension regression",
            "--expected-revision",
            "3",
            "--transition-id",
            "cli-reactivate-1",
        )
        self.assertEqual(reactivated, 0, errors)
        revoked, _, errors = self._run(
            "revoke",
            root,
            database,
            f"REVOKE write cli-project {subject_id}",
            "--subject-id",
            subject_id,
            "--action",
            "write",
            "--rationale",
            "Remove write access after the positive launcher check",
        )
        self.assertEqual(revoked, 0, errors)

    def _assert_access_audit(self, root: Path, database: Path) -> None:
        """Check the durable exact grant, revocation, and registration audit."""
        viewed, view_output, errors = self._run(
            "view", root, database, "VIEW cli-project ACCESS"
        )
        self.assertEqual(viewed, 0, errors)
        audit = json.loads(view_output)
        self.assertEqual(len(audit["grants"]), 2)
        self.assertEqual(len(audit["audit"]), 4)
        self.assertEqual(audit["registration"]["status"], "active")
        storage_classes = {
            item["class_name"]: item["record_count"]
            for item in audit["control_plane_storage_usage"]["classes"]
        }
        self.assertEqual(storage_classes["project_registry"], 1)
        self.assertEqual(storage_classes["project_registry_audit"], 4)
        self.assertEqual(storage_classes["project_grants"], 2)
        self.assertEqual(storage_classes["project_grant_revocations"], 1)
        physical = audit["control_plane_storage_usage"]["sqlite_physical"]
        self.assertIn(physical["status"], {"available", "unsupported"})
        if physical["status"] == "available":
            physical_classes = {
                item["class_name"]: item for item in physical["classes"]
            }
            self.assertIn("project_registry", physical_classes)
            self.assertGreater(
                physical_classes["project_registry"]["allocated_bytes"], 0
            )
        write_grant = next(
            grant for grant in audit["grants"] if grant["action"] == "write"
        )
        self.assertIsNotNone(write_grant["revoked_at"])

    def test_attended_binding_deregistration_is_exposed_as_separate_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            registered, _, errors = self._run(
                "register", root, database, "REGISTER cli-project",
                "--rationale", "Enroll the consumer fixture",
            )
            self.assertEqual(registered, 0, errors)
            granted, _, errors = self._run(
                "grant", root, database, "GRANT read cli-project cli-reader",
                "--subject-id", "cli-reader", "--action", "read",
                "--rationale", "Grant one read scope",
            )
            self.assertEqual(granted, 0, errors)
            pending, pending_output, errors = self._run(
                "deregister", root, database,
                "DEREGISTER cli-project AT BINDING REVISION 1 TRANSITION cli-deregister-1",
                "--rationale", "Stop consumer access",
                "--expected-revision", "1", "--transition-id", "cli-deregister-1",
            )
            self.assertEqual(pending, 0, errors)
            self.assertEqual(
                json.loads(pending_output)["binding"]["status"],
                "deregistration_pending",
            )
            finalized, final_output, errors = self._run(
                "deregister_finalize",
                root,
                database,
                "DEREGISTER_FINALIZE cli-project AT BINDING REVISION 2 "
                "TRANSITION cli-deregister-final-1",
                "--rationale", "Finalize after local event reconciliation",
                "--expected-revision", "2", "--transition-id", "cli-deregister-final-1",
            )
            self.assertEqual(finalized, 0, errors)
            self.assertEqual(
                json.loads(final_output)["binding"]["status"], "deregistered"
            )
            viewed, view_output, errors = self._run(
                "view", root, database, "VIEW cli-project ACCESS"
            )
            self.assertEqual(viewed, 0, errors)
            state = json.loads(view_output)
            self.assertEqual(state["registration"]["status"], "active")
            self.assertEqual(state["consumer_binding"]["status"], "deregistered")
            self.assertEqual(len(state["consumer_binding_audit"]), 3)
            self.assertEqual(state["grants"][0]["revoked_by"], f"local-uid:{os.geteuid()}")
            config = ProjectConfig.load(root)
            phrase = (
                "REENROLL cli-project FROM SOURCE EPOCH 1 AT BINDING REVISION 3 "
                "PROJECT REVISION 1 TRANSITION cli-reenroll-1 REPOSITORY "
                f"{config.repository_fingerprint} CONFIG {config.config_sha256} API 1"
            )
            reenrolled, reenrolled_output, errors = self._run(
                "reenroll",
                root,
                database,
                phrase,
                "--rationale",
                "Review and re-enable the consumer with a fresh event sequence",
                "--expected-revision",
                "3",
                "--expected-source-epoch",
                "1",
                "--expected-project-revision",
                "1",
                "--transition-id",
                "cli-reenroll-1",
            )
            self.assertEqual(reenrolled, 0, errors)
            reenrolled_state = json.loads(reenrolled_output)
            self.assertEqual(reenrolled_state["binding"]["status"], "active")
            self.assertEqual(reenrolled_state["binding"]["revision"], 4)
            self.assertEqual(reenrolled_state["binding"]["source_epoch"], 2)

    def test_noninteractive_or_wrong_confirmation_cannot_modify_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"
            code, output, _ = self._run(
                "register",
                root,
                database,
                "REGISTER another-project",
                "--rationale",
                "This must not persist",
            )
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertFalse(database.exists())

            code, output, _ = self._run(
                "register",
                root,
                database,
                "REGISTER cli-project",
                "--rationale",
                "This must not persist either",
                attended=False,
            )
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
