"""Shared temporary consumer-repository layouts for Curator V2 tests."""

from __future__ import annotations

import json
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


class _TestProjectAdministrator:  # pylint: disable=too-few-public-methods
    # Implements the one-operation host administrator protocol for isolated tests.
    """Authorize only fixture registration and grants for one project."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow the test administrator's exact registration/grant actions."""

        return (
            caller.subject_id == "test-project-admin"
            and project_id == self.project_id
            and action
            in (ProjectAdministrationAction.REGISTER, ProjectAdministrationAction.GRANT)
        )


def bind_test_project(
    store: CuratorStore,
    root: Path,
    subject_id: str,
    *,
    evidence_verifier: EvidenceVerifier | None = None,
    review_authorizer: ReviewAuthorizer | None = None,
) -> ProjectPlugin:
    """Bind a test plugin after seeding its exact registration and grants."""

    config = ProjectConfig.load(root)
    manager = ProjectAccessManager(store, _TestProjectAdministrator(config.project_id))
    administrator = AuthenticatedCaller("test-project-admin")
    manager.register_project(
        administrator,
        ProjectRegistrationRequest.from_project_config(
            config, "Register an isolated test consumer"
        ),
    )
    for action in (
        ProjectAction.READ,
        ProjectAction.WRITE,
        ProjectAction.REVIEW,
        ProjectAction.RETENTION_HOLD_RELEASE,
    ):
        manager.grant(
            administrator,
            config.project_id,
            subject_id,
            action,
            "Grant the test identity its exact project action",
        )
    return ProjectPlugin.bind(config, store, evidence_verifier, review_authorizer)
