"""Shared temporary consumer-repository layouts for Curator V2 tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sys

from mcp.client.stdio import StdioServerParameters

from curatormd_v2 import (
    AuthenticatedCaller,
    CuratorStore,
    EvidenceVerifier,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectConfig,
    ProjectPlugin,
    ProjectRegistrationRequest,
    ReviewAuthorizer,
)
from curatormd_v2.hosted_mcp import LocalProfileMCP, build_local_profile_mcp


def create_consumer_repo(root: Path) -> Path:
    """Create the minimal isolated repository tree expected by project config."""

    root.mkdir(parents=True)
    for directory in (".git", "src", "docs", "persistence"):
        (root / directory).mkdir()
    (root / ".curatormd-v2" / "staging").mkdir(parents=True)
    return root


def write_consumer_config(root: Path, project_id: str) -> Path:
    """Write the shared minimal config for one test consumer repository."""

    config_path = root / ".curatormd-v2.toml"
    config_path.write_text(
        f"""\
        schema_version = 1
        backend_api_version = 1
        project_id = {json.dumps(project_id)}

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
    config_path.chmod(0o600)
    return config_path


def configure_stdio_consumer(root: Path, project_id: str) -> StdioServerParameters:
    """Prepare an isolated consumer and its test-only stdio server command."""

    create_consumer_repo(root)
    (root / "docs" / "tasks.md").write_text("- [ ] stdio task\n")
    (root / "persistence" / "HISTORY.md").write_text("# History\n")
    write_consumer_config(root, project_id)
    return StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("mcp_stdio_fixture.py"))],
        env={"CURATOR_TEST_PROJECT_ROOT": str(root)},
        cwd=Path(__file__).parents[1],
    )


def build_test_profile_mcp(
    project_root: Path,
    database: Path,
    *,
    allow_write: bool = False,
) -> LocalProfileMCP:
    """Build the common isolated gptmd-coding profile used by launcher tests."""

    return build_local_profile_mcp(
        project_root=project_root,
        database=database,
        profile_id="gptmd-coding",
        allow_write=allow_write,
    )


@contextmanager
def open_test_profile_mcp(
    project_root: Path,
    database: Path,
    *,
    allow_write: bool = False,
) -> Generator[LocalProfileMCP, None, None]:
    """Open and reliably close a common disposable profile runtime."""

    runtime = build_test_profile_mcp(
        project_root, database, allow_write=allow_write
    )
    try:
        yield runtime
    finally:
        runtime.close()


class _TestProjectAdministrator:  # pylint: disable=too-few-public-methods
    # Implements the one-operation host administrator protocol for isolated tests.
    """Authorize only fixture registration and grants for one project."""

    def __init__(
        self, project_id: str, subject_id: str = "test-project-admin"
    ) -> None:
        self.project_id = project_id
        self.subject_id = subject_id

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow the test administrator's exact registration/grant actions."""

        return (
            caller.subject_id == self.subject_id
            and project_id == self.project_id
            and action
            in (ProjectAdministrationAction.REGISTER, ProjectAdministrationAction.GRANT)
        )


@dataclass(frozen=True, slots=True)
class TestProjectAccess:
    """Exact test-only administrator and grants for one consumer fixture."""

    actions: tuple[ProjectAction, ...]
    admin_subject: str = "test-project-admin"
    registration_rationale: str = "Register an isolated test consumer"
    grant_rationale: str = "Grant the test identity its exact project action"


def bind_test_project(
    store: CuratorStore,
    root: Path,
    subject_id: str,
    *,
    evidence_verifier: EvidenceVerifier | None = None,
    review_authorizer: ReviewAuthorizer | None = None,
) -> ProjectPlugin:
    """Bind a test plugin after seeding its exact registration and grants."""

    config = register_test_project_access(
        store,
        root,
        subject_id,
        TestProjectAccess(
            actions=(
                ProjectAction.READ,
                ProjectAction.WRITE,
                ProjectAction.REVIEW,
                ProjectAction.RETENTION_HOLD_RELEASE,
            )
        ),
    )
    return ProjectPlugin.bind(config, store, evidence_verifier, review_authorizer)


def register_test_project_access(
    store: CuratorStore,
    root: Path,
    subject_id: str,
    access: TestProjectAccess,
) -> ProjectConfig:
    """Register one fixture project and seed only its exact requested grants."""

    config = ProjectConfig.load(root)
    manager = ProjectAccessManager(
        store,
        _TestProjectAdministrator(config.project_id, access.admin_subject),
    )
    administrator = AuthenticatedCaller(access.admin_subject)
    manager.register_project(
        administrator,
        ProjectRegistrationRequest.from_project_config(
            config, access.registration_rationale
        ),
    )
    for action in access.actions:
        manager.grant(
            administrator,
            config.project_id,
            subject_id,
            action,
            access.grant_rationale,
        )
    return config
