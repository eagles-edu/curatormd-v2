"""Durable project registration and exact grant administration primitives.

The SQLite grant authorizers may guard MCP/API operations. Project
administration remains outside MCP: a trusted host must authenticate the
administrator and provide its policy before constructing
``ProjectAccessManager``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .api import AuthenticatedCaller, ProjectAction
from .project_config import ProjectConfig
from .store import (
    CuratorStore,
    ProjectGrantRecord,
    ProjectRegistrationRecord,
    ProjectRegistrationRequest,
    ProjectRegistryAuditRecord,
    NotFoundError,
)


class ProjectAdministrationAction(StrEnum):
    """Host-level permissions separate from ordinary project API grants."""

    VIEW = "view"
    REGISTER = "register"
    UPDATE = "update"
    SUSPEND = "suspend"
    REACTIVATE = "reactivate"
    GRANT = "grant"
    REVOKE = "revoke"


def _is_project_action(value: object) -> bool:
    """Check an untrusted runtime value against the fixed project scopes."""

    return isinstance(value, ProjectAction)


def _project_admin_action_for_status(
    value: object,
) -> ProjectAdministrationAction | None:
    """Resolve a raw status value without assuming it is hashable or textual."""

    if not isinstance(value, str):
        return None
    return {
        "active": ProjectAdministrationAction.REACTIVATE,
        "suspended": ProjectAdministrationAction.SUSPEND,
    }.get(value)


class ProjectAdministrationAuthorizer(Protocol):
    """Trusted-host policy for operators managing registrations and grants."""

    # pylint: disable=too-few-public-methods  # Single-operation host administration contract.

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Return true only for an authenticated operator's exact admin scope."""
        ...


@dataclass(frozen=True, slots=True)
class ProjectAuthorizationBinding:
    """Immutable config fingerprints and action scopes for one profile."""

    project_id: str
    repository_fingerprint: str
    config_sha256: str
    backend_api_version: int
    allowed_actions: frozenset[ProjectAction]

    @classmethod
    def from_project_config(
        cls,
        config: ProjectConfig,
        allowed_actions: frozenset[ProjectAction],
    ) -> ProjectAuthorizationBinding:
        """Bind grants to the exact values from a validated project config."""

        return cls(
            project_id=config.project_id,
            repository_fingerprint=config.repository_fingerprint,
            config_sha256=config.config_sha256,
            backend_api_version=config.backend_api_version,
            allowed_actions=allowed_actions,
        )


class SQLiteProjectGrantAuthorizer:
    """Resolve exact grants from SQLite and fail closed for suspended projects."""

    # pylint: disable=too-few-public-methods  # Implements the one-operation project authorizer contract.

    def __init__(self, store: CuratorStore) -> None:
        self._store = store

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Allow only an exact, active persisted project grant."""

        if not _is_project_action(action):
            return False
        return self._store.has_project_grant(
            caller.subject_id, project_id, action.value
        )


class FingerprintBoundSQLiteProjectGrantAuthorizer:
    """Require a live registration matching one loaded repository config.

    The bound fingerprints are computed by the trusted repository adapter at
    startup. Registry status and exact grants are read from SQLite on every
    authorization decision, so suspension and revocation take effect without
    restarting the MCP process.
    """

    # pylint: disable=too-few-public-methods  # Implements the one-operation project authorizer contract.

    def __init__(
        self, store: CuratorStore, binding: ProjectAuthorizationBinding
    ) -> None:
        self._store = store
        self._binding = binding

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Allow only an exact grant for the active, fingerprint-matched repo."""

        if (
            project_id != self._binding.project_id
            or not _is_project_action(action)
            or action not in self._binding.allowed_actions
        ):
            return False
        try:
            registration = self._store.get_project_registration(project_id)
        except NotFoundError:
            return False
        if (
            registration.status != "active"
            or registration.repository_fingerprint
            != self._binding.repository_fingerprint
            or registration.config_sha256 != self._binding.config_sha256
            or registration.backend_api_version
            != self._binding.backend_api_version
        ):
            return False
        return self._store.has_project_grant(
            caller.subject_id, project_id, action.value
        )


class ProjectAccessManager:
    """Administer project identities and exact grants through host policy.

    ``AuthenticatedCaller`` construction is not authentication. This manager
    must only receive callers produced by a trusted host, and its injected
    administration authorizer must not be exposed to untrusted MCP clients.
    """

    def __init__(
        self,
        store: CuratorStore,
        administrator: ProjectAdministrationAuthorizer,
    ) -> None:
        self._store = store
        self._administrator = administrator

    def _require_admin(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> None:
        if not self._administrator.authorize_project_administration(
            caller, project_id, action
        ):
            raise PermissionError("not authorized to administer project access")

    def register_project(
        self,
        caller: AuthenticatedCaller,
        request: ProjectRegistrationRequest,
    ) -> ProjectRegistrationRecord:
        """Register one project after host authorization of its identity."""

        self._require_admin(
            caller, request.project_id, ProjectAdministrationAction.REGISTER
        )
        return self._store.register_project(request, caller.subject_id)

    def update_project_registration(
        self,
        caller: AuthenticatedCaller,
        request: ProjectRegistrationRequest,
    ) -> ProjectRegistrationRecord:
        """Update the host-verified fingerprint after an explicit admin check."""

        self._require_admin(
            caller, request.project_id, ProjectAdministrationAction.UPDATE
        )
        return self._store.update_project_registration(request, caller.subject_id)

    def set_project_status(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        status: str,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Suspend or reactivate a project under distinct host permissions."""

        action = _project_admin_action_for_status(status)
        if action is None:
            raise ValueError("project status must be active or suspended")
        self._require_admin(caller, project_id, action)
        return self._store.set_project_status(
            project_id, status, caller.subject_id, rationale
        )

    def grant(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        subject_id: str,
        action: ProjectAction,
        rationale: str,
    ) -> ProjectGrantRecord:
        """Create an exact action grant; grant-admin rights are not delegable."""

        if not _is_project_action(action):
            raise ValueError("action must be a known ProjectAction")
        self._require_admin(caller, project_id, ProjectAdministrationAction.GRANT)
        return self._store.add_project_grant(
            project_id, subject_id, action.value, caller.subject_id, rationale
        )

    def revoke(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        subject_id: str,
        action: ProjectAction,
        rationale: str,
    ) -> ProjectGrantRecord:
        """Revoke one active exact grant without deleting its grant history."""

        if not _is_project_action(action):
            raise ValueError("action must be a known ProjectAction")
        self._require_admin(caller, project_id, ProjectAdministrationAction.REVOKE)
        return self._store.revoke_project_grant(
            project_id, subject_id, action.value, caller.subject_id, rationale
        )

    def list_grants(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> tuple[ProjectGrantRecord, ...]:
        """Read grant and revocation history after host authorization."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.VIEW)
        return self._store.project_grants(project_id)

    def get_registration(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> ProjectRegistrationRecord:
        """Read one project registration after host authorization."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.VIEW)
        return self._store.get_project_registration(project_id)

    def list_registration_audit(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> tuple[ProjectRegistryAuditRecord, ...]:
        """Read the append-only project registration history."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.VIEW)
        return self._store.project_registry_audit(project_id)
