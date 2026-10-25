"""Shared support for project access tests."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import tempfile
import unittest

from curatormd_v2 import (
    AuthenticatedCaller,
    CuratorStore,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
)
from curatormd_v2.read_models import StagingArtifactInventory
from curatormd_v2.staging_models import StagingUsage

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

class ProjectAccessTestCase(unittest.TestCase):  # pylint: disable=too-few-public-methods
    """Shared setup for project access and consumer binding tests."""

    project_id = "project-a"
    repository_fingerprint = hashlib.sha256(b"repo-a").hexdigest()
    config_sha256 = hashlib.sha256(b"config-v1").hexdigest()

    def setUp(self) -> None:  # pylint: disable=invalid-name
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

    def _allow_admin(self, action: ProjectAdministrationAction) -> None:
        self.admin.allowed.add((self.operator.subject_id, self.project_id, action))

    def _registration_request(
        self,
        rationale: str,
        *,
        project_id: str | None = None,
        repository_fingerprint: str | None = None,
        config_sha256: str | None = None,
        expected_revision: int | None = None,
    ) -> ProjectRegistrationRequest:
        """Build a typed host registration request for one test case."""

        return ProjectRegistrationRequest(
            project_id=project_id or self.project_id,
            repository_fingerprint=(
                repository_fingerprint or self.repository_fingerprint
            ),
            config_sha256=config_sha256 or self.config_sha256,
            backend_api_version=1,
            rationale=rationale,
            expected_revision=expected_revision,
        )

    def _register(self) -> None:
        self._allow_admin(ProjectAdministrationAction.REGISTER)
        self.manager.register_project(
            self.operator,
            self._registration_request("Approve the pilot repository binding"),
        )

    @staticmethod
    def _empty_staging_inventory() -> StagingArtifactInventory:
        """Build one complete, freshly observed empty test staging tree."""

        return StagingArtifactInventory(
            artifacts=(),
            usage=StagingUsage(
                entries_scanned=0,
                regular_file_count=0,
                observed_file_bytes=0,
                directory_count=0,
                symlink_count=0,
                special_file_count=0,
                inventory_complete=True,
                observed_at=datetime.now(UTC).isoformat(),
            ),
            manifest_sha256=hashlib.sha256(b"[]").hexdigest(),
            scope_goal_id=None,
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

    def _change_status(
        self,
        status: str,
        rationale: str,
        expected_revision: int,
        transition_id: str,
    ):
        review_packet_sha256: str | None = None
        suspension_transition_id: str | None = None
        staging_inventory_sha256: str | None = None
        staging_inventory_count: int | None = None
        staging_inventory_bytes: int | None = None
        staging_inventory_observed_at: str | None = None
        if status == "active":
            registration = self.store.get_project_registration(self.project_id)
            if (
                registration.status == "suspended"
                and self.store.get_project_retirement(self.project_id) is None
            ):
                self._allow_admin(ProjectAdministrationAction.VIEW)
                inventory = self._empty_staging_inventory()
                packet = self.manager.project_reactivation_review_packet(
                    self.operator, self.project_id, inventory
                )
                assert packet.packet_sha256 is not None
                review_packet_sha256 = packet.packet_sha256
                suspension_transition_id = packet.suspension_transition_id
                staging_inventory_sha256 = packet.staging_inventory_sha256
                staging_inventory_count = packet.staging_inventory_count
                staging_inventory_bytes = packet.staging_inventory_bytes
                staging_inventory_observed_at = packet.staging_inventory_observed_at
            elif self.store.get_project_retirement(self.project_id) is not None:
                # Supply syntactically valid review IDs so the store reaches
                # the irreversible retirement tombstone check.
                review_packet_sha256 = "0" * 64
                suspension_transition_id = "prior-suspension"
        return self.manager.set_project_status(
            self.operator,
            ProjectStatusChangeRequest(
                project_id=self.project_id,
                status=status,
                rationale=rationale,
                expected_revision=expected_revision,
                transition_id=transition_id,
                review_packet_sha256=review_packet_sha256,
                suspension_transition_id=suspension_transition_id,
                staging_inventory_sha256=staging_inventory_sha256,
                staging_inventory_count=staging_inventory_count,
                staging_inventory_bytes=staging_inventory_bytes,
                staging_inventory_observed_at=staging_inventory_observed_at,
            ),
        )
