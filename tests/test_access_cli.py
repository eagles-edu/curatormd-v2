"""Attended local operator workflow for durable project access."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from curatormd_v2 import ProjectAction
from curatormd_v2.access_cli import main
from curatormd_v2.hosted_mcp import build_local_profile_mcp


class _InteractiveInput(StringIO):
    def __init__(self, value: str, *, interactive: bool = True) -> None:
        super().__init__(value)
        self.interactive = interactive

    def isatty(self) -> bool:
        return self.interactive


class AccessCliTests(unittest.TestCase):
    """Require an attended exact confirmation before access-ledger writes."""

    def _project(self, root: Path) -> None:
        (root / ".git").mkdir()
        (root / "src").mkdir()
        (root / "docs").mkdir()
        (root / "persistence").mkdir()
        (root / ".curatormd-v2" / "staging").mkdir(parents=True)
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
            root.mkdir()
            self._project(root)
            database = Path(temporary) / "curator.sqlite3"

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
                phrase = f"GRANT {action} cli-project gptmd-coding"
                granted, _, errors = self._run(
                    "grant",
                    root,
                    database,
                    phrase,
                    "--subject-id",
                    "gptmd-coding",
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

            config_path = root / ".curatormd-v2.toml"
            config_path.write_text(config_path.read_text() + "\n")
            updated, _, errors = self._run(
                "update",
                root,
                database,
                "UPDATE cli-project",
                "--rationale",
                "Approve the reviewed config fingerprint change",
            )
            self.assertEqual(updated, 0, errors)

            suspended, _, errors = self._run(
                "suspend",
                root,
                database,
                "SUSPEND cli-project",
                "--rationale",
                "Suspend access during the lifecycle regression",
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
                "REACTIVATE cli-project",
                "--rationale",
                "Restore access after the suspension regression",
            )
            self.assertEqual(reactivated, 0, errors)
            revoked, _, errors = self._run(
                "revoke",
                root,
                database,
                "REVOKE write cli-project gptmd-coding",
                "--subject-id",
                "gptmd-coding",
                "--action",
                "write",
                "--rationale",
                "Remove write access after the positive launcher check",
            )
            self.assertEqual(revoked, 0, errors)

            viewed, view_output, errors = self._run(
                "view", root, database, "VIEW cli-project ACCESS"
            )
            self.assertEqual(viewed, 0, errors)
            audit = json.loads(view_output)
            self.assertEqual(len(audit["grants"]), 2)
            self.assertEqual(len(audit["audit"]), 4)
            self.assertEqual(audit["registration"]["status"], "active")
            self.assertTrue(
                next(
                    grant for grant in audit["grants"] if grant["action"] == "write"
                )["revoked_at"]
                is not None
            )

    def test_noninteractive_or_wrong_confirmation_cannot_modify_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            root.mkdir()
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
