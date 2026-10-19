"""Test-only stdio MCP process with an explicitly scoped fake host identity."""

from __future__ import annotations

import os
from pathlib import Path

from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    CuratorStore,
    InMemoryTokenBucket,
    ProjectAction,
    ProjectConfig,
    ProjectPlugin,
    build_mcp_server,
)


class _TestAuthorizer:  # pylint: disable=too-few-public-methods
    """Authorize the stable host identity for MCP subprocess tests."""

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Allow only the configured user, project, and read/write actions."""

        return (
            caller.subject_id == "stdio-test-subject"
            and project_id == "stdio-project"
            and action in (ProjectAction.READ, ProjectAction.WRITE)
        )


def main() -> None:
    """Launch a subprocess fixture without using any real host credentials."""

    project_root = Path(os.environ["CURATOR_TEST_PROJECT_ROOT"])
    store = CuratorStore(project_root / ".curatormd-v2" / "stdio.sqlite3")
    try:
        plugin = ProjectPlugin.bind(ProjectConfig.load(project_root), store)
        api = AuthenticatedCuratorAPI(
            {"stdio-project": plugin}, _TestAuthorizer(), InMemoryTokenBucket()
        )
        server = build_mcp_server(
            api,
            AuthenticatedCaller("stdio-test-subject"),
            "stdio-project",
            "stdio-test-stream",
        )
        server.run()
    finally:
        store.close()


if __name__ == "__main__":
    main()
