"""Durable project registration and revocable access-grant tests."""

from __future__ import annotations

import hashlib
import tempfile
import unittest

from curatormd_v2 import (
    AuthenticatedCaller,
    ConflictError,
    CuratorStore,
    NotFoundError,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    SQLiteProjectGrantAuthorizer,
)


class TestProjectAdministrator:  # pylint: disable=too-few-public-methods
    """Allow only explicitly configured host-level project admin actions."""

    def __init__(self) -> None:
        self.allowed: set[tuple[str, str, ProjectAdministrationAction]] = set()

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Match the authenticated subject and exact project/admin action."""

        return (caller.subject_id, project_id, action) in self.allowed


class DurableProjectAccessTests(unittest.TestCase):
    """Prove persistent grants, auditability, revocation, and default denial."""

    def setUp(self) -> None:
        # unittest keeps the directory and store alive until teardown.
        # pylint: disable=consider-using-with
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        # pylint: enable=consider-using-with
        store = CuratorStore(
            f"{temporary}/curator.sqlite3"
        )
        self.store = self.enterContext(store)
        self.admin = TestProjectAdministrator()
        self.manager = ProjectAccessManager(self.store, self.admin)
        self.operator = AuthenticatedCaller("operator-1")
        self.reader = AuthenticatedCaller("consumer-1")
        self.project_id = "project-a"
        self.repository_fingerprint = hashlib.sha256(b"repo-a").hexdigest()
        self.config_sha256 = hashlib.sha256(b"config-v1").hexdigest()

    def _allow_admin(self, action: ProjectAdministrationAction) -> None:
        self.admin.allowed.add((self.operator.subject_id, self.project_id, action))

    def _register(self) -> None:
        self._allow_admin(ProjectAdministrationAction.REGISTER)
        self.manager.register_project(
            self.operator,
            self.project_id,
            self.repository_fingerprint,
            self.config_sha256,
            1,
            "Approve the pilot repository binding",
        )

    def _grant(self, action: ProjectAction = ProjectAction.READ):
        self._allow_admin(ProjectAdministrationAction.GRANT)
        return self.manager.grant(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            action,
            "Grant the pilot consumer its explicit read scope",
        )

    def test_registration_denial_is_atomic_and_records_no_project(self) -> None:
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.register_project(
                self.operator,
                self.project_id,
                self.repository_fingerprint,
                self.config_sha256,
                1,
                "Unapproved registration attempt",
            )
        with self.assertRaises(NotFoundError):
            self.store.get_project_registration(self.project_id)
        with self.store.transaction() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM project_registry").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM project_registry_audit"
                ).fetchone()[0],
                0,
            )

    def test_registration_is_unique_and_audits_updates_and_status_changes(self) -> None:
        self._register()
        with self.assertRaisesRegex(ConflictError, "already registered"):
            self.manager.register_project(
                self.operator,
                self.project_id,
                self.repository_fingerprint,
                self.config_sha256,
                1,
                "Duplicate registration",
            )

        updated_sha = hashlib.sha256(b"config-v2").hexdigest()
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        updated = self.manager.update_project_registration(
            self.operator,
            self.project_id,
            self.repository_fingerprint,
            updated_sha,
            1,
            "Approve the reviewed plugin configuration update",
        )
        self.assertEqual(updated.config_sha256, updated_sha)

        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        suspended = self.manager.set_project_status(
            self.operator,
            self.project_id,
            "suspended",
            "Disable the pilot binding while reviewing scope",
        )
        self.assertEqual(suspended.status, "suspended")
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        active = self.manager.set_project_status(
            self.operator,
            self.project_id,
            "active",
            "Re-enable the reviewed pilot binding",
        )
        self.assertEqual(active.status, "active")

        self._allow_admin(ProjectAdministrationAction.VIEW)
        audit = self.manager.list_registration_audit(self.operator, self.project_id)
        self.assertEqual(
            [entry.action for entry in audit],
            ["registered", "updated", "suspended", "reactivated"],
        )
        self.assertEqual(
            [entry.actor_id for entry in audit], [self.operator.subject_id] * 4
        )

    def test_repository_fingerprint_cannot_be_registered_under_two_ids(self) -> None:
        self._register()
        self._allow_admin(ProjectAdministrationAction.REGISTER)
        other_project_admin = AuthenticatedCaller("operator-2")
        self.admin.allowed.add(
            (
                other_project_admin.subject_id,
                "project-b",
                ProjectAdministrationAction.REGISTER,
            )
        )
        with self.assertRaisesRegex(ConflictError, "already registered"):
            self.manager.register_project(
                other_project_admin,
                "project-b",
                self.repository_fingerprint,
                self.config_sha256,
                1,
                "Attempt to bind the same repository twice",
            )

    def test_exact_grant_survives_restart_and_revocation_denies_immediately(self) -> None:
        self._register()
        first = self._grant()
        authorizer = SQLiteProjectGrantAuthorizer(self.store)
        self.assertTrue(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.WRITE))
        self.assertFalse(
            authorizer.authorize(
                AuthenticatedCaller("other-user"), self.project_id, ProjectAction.READ
            )
        )
        self.assertFalse(
            authorizer.authorize(self.reader, "other-project", ProjectAction.READ)
        )

        self._allow_admin(ProjectAdministrationAction.REVOKE)
        revoked = self.manager.revoke(
            self.operator,
            self.project_id,
            self.reader.subject_id,
            ProjectAction.READ,
            "The pilot read access is no longer needed",
        )
        self.assertEqual(revoked.grant_id, first.grant_id)
        self.assertFalse(revoked.active)
        self.assertEqual(revoked.revoked_by, self.operator.subject_id)
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))

        second = self._grant()
        self.assertNotEqual(first.grant_id, second.grant_id)
        self.assertTrue(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        self._allow_admin(ProjectAdministrationAction.VIEW)
        history = self.manager.list_grants(self.operator, self.project_id)
        self.assertEqual([entry.grant_id for entry in history], [first.grant_id, second.grant_id])
        self.assertEqual([entry.active for entry in history], [False, True])

    def test_suspended_project_denies_grants_and_authorization_without_deleting_history(
        self,
    ) -> None:
        self._register()
        self._grant()
        self._allow_admin(ProjectAdministrationAction.SUSPEND)
        self.manager.set_project_status(
            self.operator,
            self.project_id,
            "suspended",
            "Suspend access during the pilot pause",
        )
        authorizer = SQLiteProjectGrantAuthorizer(self.store)
        self.assertFalse(authorizer.authorize(self.reader, self.project_id, ProjectAction.READ))
        with self.assertRaisesRegex(ConflictError, "not active"):
            self._grant(ProjectAction.WRITE)
        self.assertEqual(len(self.store.project_grants(self.project_id)), 1)

    def test_denied_grant_and_revoke_leave_durable_state_unchanged(self) -> None:
        self._register()
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.grant(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                ProjectAction.READ,
                "Denied grant attempt",
            )
        self.assertEqual(self.store.project_grants(self.project_id), ())

        granted = self._grant()
        self.admin.allowed.discard(
            (self.operator.subject_id, self.project_id, ProjectAdministrationAction.REVOKE)
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            self.manager.revoke(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                ProjectAction.READ,
                "Denied revocation attempt",
            )
        self.assertTrue(
            SQLiteProjectGrantAuthorizer(self.store).authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )
        self.assertEqual(self.store.project_grants(self.project_id)[0].grant_id, granted.grant_id)

    def test_grant_administration_rejects_untyped_scope(self) -> None:
        self._register()
        with self.assertRaisesRegex(ValueError, "known ProjectAction"):
            self.manager.grant(
                self.operator,
                self.project_id,
                self.reader.subject_id,
                "read",  # type: ignore[arg-type]
                "A string is not an authorization enum",
            )
        self.assertEqual(self.store.project_grants(self.project_id), ())


if __name__ == "__main__":
    unittest.main()
