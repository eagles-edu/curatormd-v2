"""Durable project registration and exact grant administration primitives.

This module is deliberately not wired to MCP. A trusted host must authenticate
the caller and provide the project-administration policy before constructing
``ProjectAccessManager`` or using ``SQLiteProjectGrantAuthorizer``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from .api import AuthenticatedCaller, ProjectAction
from .store import (
    CuratorStore,
    ProjectGrantRecord,
    ProjectRegistrationRecord,
    ProjectRegistryAuditRecord,
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

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Return true only for an authenticated operator's exact admin scope."""
        ...


class SQLiteProjectGrantAuthorizer:
    """Resolve exact grants from SQLite and fail closed for suspended projects."""

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
        project_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Register one project after host authorization of its identity."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.REGISTER)
        return self._store.register_project(
            project_id,
            repository_fingerprint,
            config_sha256,
            backend_api_version,
            caller.subject_id,
            rationale,
        )

    def update_project_registration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        repository_fingerprint: str,
        config_sha256: str,
        backend_api_version: int,
        rationale: str,
    ) -> ProjectRegistrationRecord:
        """Update the host-verified fingerprint after an explicit admin check."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.UPDATE)
        return self._store.update_project_registration(
            project_id,
            repository_fingerprint,
            config_sha256,
            backend_api_version,
            caller.subject_id,
            rationale,
        )

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

    def list_registration_audit(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> tuple[ProjectRegistryAuditRecord, ...]:
        """Read the append-only project registration history."""

        self._require_admin(caller, project_id, ProjectAdministrationAction.VIEW)
        return self._store.project_registry_audit(project_id)
