"""Host-injected evidence verifiers flow through the profile-bound plugin."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from project_fixtures import (
    TestProjectAccess,
    create_consumer_repo,
    register_test_project_access,
    write_consumer_config,
)

from curatormd_v2 import (
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EventEnvelope,
    FactKind,
    FactRecorded,
    GoalStarted,
    ProjectAction,
    SuccessCriterion,
    hosted_mcp,
)
from curatormd_v2.models import CriterionStatus


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
            write_consumer_config(root, "probe-project")
            database = Path(temporary) / "global.sqlite3"
            store = CuratorStore(database)
            try:
                register_test_project_access(
                    store,
                    root,
                    f"local-uid:{os.geteuid()}",
                    TestProjectAccess(
                        actions=(ProjectAction.READ, ProjectAction.WRITE),
                        admin_subject="test-operator",
                        registration_rationale="Register the disposable test project",
                        grant_rationale=(
                            "Grant exact disposable integration-test access"
                        ),
                    ),
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
