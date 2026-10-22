"""Host-injected evidence verifiers flow through the profile-bound plugin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from project_fixtures import create_consumer_repo

from curatormd_v2 import (
    AuthenticatedCaller,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EventEnvelope,
    FactKind,
    FactRecorded,
    GoalStarted,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectConfig,
    ProjectRegistrationRequest,
    SuccessCriterion,
    hosted_mcp,
)
from curatormd_v2.models import CriterionStatus


class _TestProjectAdmin:  # pylint: disable=too-few-public-methods
    """Provision only the disposable project and grants used by this test."""

    def authorize_project_administration(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAdministrationAction,
    ) -> bool:
        """Allow registration and grants only for the disposable test actor."""

        del project_id
        return caller.subject_id == "test-operator" and action in {
            ProjectAdministrationAction.REGISTER,
            ProjectAdministrationAction.GRANT,
        }


class HostedServiceEvidenceTests(
    unittest.TestCase
):  # pylint: disable=too-few-public-methods
    """A host-owned resolver can verify a project fact without repo config."""

# pylint: disable=too-many-locals
    def test_profile_builder_injects_host_verifier_into_event_processing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            create_consumer_repo(root)
            (root / "docs" / "tasks.md").write_text("- [ ] Verify readiness\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / ".curatormd-v2.toml").write_text(
                """\
                schema_version = 1
                backend_api_version = 1
                project_id = "probe-project"

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
            database = Path(temporary) / "global.sqlite3"
            config = ProjectConfig.load(root)
            store = CuratorStore(database)
            try:
                manager = ProjectAccessManager(store, _TestProjectAdmin())
                operator = AuthenticatedCaller("test-operator")
                manager.register_project(
                    operator,
                    ProjectRegistrationRequest.from_project_config(
                        config, "Register the disposable test project"
                    ),
                )
                for action in (ProjectAction.READ, ProjectAction.WRITE):
                    manager.grant(
                        operator,
                        config.project_id,
                        "profile-a",
                        action,
                        "Grant exact disposable integration-test access",
                    )
            finally:
                store.close()

            host_config = Path(temporary) / "host-evidence.json"
            host_config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "probe-project",
                        "probe": {
                            "adapter_id": "local-readiness",
                            "probe_id": "readiness",
                            "source_subject": "local-probe:test-host",
                            "command": [sys.executable, "-c", "print('healthy')"],
                            "working_directory": str(root),
                        },
                    }
                ),
                encoding="utf-8",
            )
            host_config.chmod(0o600)
            initial = EvidenceRef(
                "service_probe",
                "service-probe:readiness",
                hashlib.sha256(b"healthy\n").hexdigest(),
                EvidenceOutcome.PASSED,
            )
            runtime = hosted_mcp.build_local_profile_mcp(
                project_root=root,
                database=database,
                profile_id="profile-a",
                allow_write=True,
                evidence_config=host_config,
            )
            try:
                started = EventEnvelope(
                    "probe-goal-start",
                    "probe-project",
                    GoalStarted(
                        "probe-goal",
                        "Verify the configured service readiness probe",
                        (SuccessCriterion("service-ready", "The readiness probe passes"),),
                    ),
                )
                runtime.api.process_event_json(
                    runtime.caller, "probe-project", started.to_json()
                )
                fact = EventEnvelope(
                    "probe-verification",
                    "probe-project",
                    FactRecorded(
                        "probe-goal",
                        "readiness-proof",
                        FactKind.VERIFICATION,
                        "The host-configured readiness probe returned its expected digest",
                        "service-ready",
                        (initial,),
                    ),
                )

                receipt = runtime.api.process_event_json(
                    runtime.caller, "probe-project", fact.to_json()
                )
                snapshot = runtime.api.goal_status(
                    runtime.caller, "probe-project", "probe-goal"
                )

                self.assertEqual(receipt.status.value, "processed")
                self.assertEqual(snapshot.criteria[0].status, CriterionStatus.VERIFIED)
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
