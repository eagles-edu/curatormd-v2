"""Shared support for project-plugin lifecycle tests."""

from __future__ import annotations

import io
import tempfile
import unittest
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from project_fixtures import create_consumer_repo, write_consumer_config

from curatormd_v2 import (
    ArtifactCleanupAuthorizationRequest,
    ArtifactRef,
    CuratorService,
    CuratorStore,
    EvidenceRef,
    EvidenceVerificationContext,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    SuccessCriterion,
)
from curatormd_v2.events import EventEnvelope
from curatormd_v2.models import (
    Materiality,
    ReviewDecision,
    SDEConfirmationRequest,
    SDEQualityFeedbackLabel,
)
from curatormd_v2.project_config import CONFIG_FILENAME, ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.read_models import ExpiryPurgeReceipt
from curatormd_v2.service import SDEAssessmentRequest
from curatormd_v2.store import (
    ConflictError,
    FactCompactionApprovalRequest,
    NotFoundError,
    ProjectRegistrationTransitionResult,
)


class PausingPurge:  # pylint: disable=too-few-public-methods
    """Pause one purge before unlink to make the lifecycle race deterministic."""

    def __init__(
        self,
        purge: Callable[[ArtifactRef], bool],
        entered: Event,
        release: Event,
    ) -> None:
        self.purge = purge
        self.entered = entered
        self.release = release

    def __call__(self, target: ArtifactRef) -> bool:
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release the paused purge")
        return self.purge(target)


class PausingStream(io.BytesIO):  # pylint: disable=too-few-public-methods
    """Hold a staged write open while a competing inventory requests a lock."""

    def __init__(self, contents: bytes, entered: Event, release: Event) -> None:
        super().__init__(contents)
        self.entered = entered
        self.release = release

    def read(self, size: int | None = -1) -> bytes:
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release the producer stream")
        return super().read(size)


class CountingStagingLock:  # pylint: disable=too-few-public-methods
    """Signal when a competing writer reaches the already-held staging lock."""

    def __init__(
        self,
        acquire: Callable[[], Generator[int, None, None]],
        contending_attempted: Event,
    ) -> None:
        self.acquire = acquire
        self.contending_attempted = contending_attempted
        self.guard = Lock()
        self.calls = 0

    def __call__(self) -> Generator[int, None, None]:
        with self.guard:
            self.calls += 1
            if self.calls == 2:
                self.contending_attempted.set()
        return self.acquire()


def suspend_project_after_start(
    store: CuratorStore,
    project_id: str,
    transition_id: str,
    started: Event,
) -> ProjectRegistrationTransitionResult:
    """Start a project suspension after a concurrent purge is admitted."""

    started.set()
    registration = store.get_project_registration(project_id)
    return store.set_project_status(
        ProjectStatusChangeRequest(
            project_id=project_id,
            status="suspended",
            rationale="Suspend only after admitted expiry unlink commits",
            expected_revision=registration.revision,
            transition_id=transition_id,
        ),
        "test-admin",
    )


class PausingEvidenceVerifier:  # pylint: disable=too-few-public-methods
    """Pause source verification to exercise a project lifecycle cutover."""

    def __init__(self, store: CuratorStore, entered: Event, release: Event) -> None:
        self.store = store
        self.entered = entered
        self.release = release
        self.transaction_states: list[bool] = []

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Record transaction state, block, then issue fixture provenance."""

        self.transaction_states.append(self.store.transaction_active)
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release evidence verification")
        return attest_test_evidence(evidence, context)


class ProjectPluginTestSupport(unittest.TestCase):
    """Shared fixture and helpers for project-plugin behavior tests."""

    def setUp(self) -> None:
        self.temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(self.temporary) / "consumer"
        create_consumer_repo(self.root)
        self.stage = self.root / ".curatormd-v2" / "staging"
        (self.root / "docs" / "tasks.md").write_text("- [ ] Example task\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        self.write_config()
        self.store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(self.store.close)
        self._register_project("Register the reference-plugin test project")

    def _assert_expiry_unlink_holds_suspension_fence(
        self,
        config: ProjectConfig,
        plugin: ProjectPlugin,
        receipt: ExpiryPurgeReceipt,
        artifact_path: Path,
    ) -> None:
        """Hold an admitted unlink and prove suspension waits for its receipt."""

        unlink_entered = Event()
        release_unlink = Event()
        suspension_started = Event()
        pausing_purge = PausingPurge(
            plugin.service.purger.purge,
            unlink_entered,
            release_unlink,
        )

        try:
            with ThreadPoolExecutor(max_workers=2) as workers:
                with patch.object(plugin.service.purger, "purge", pausing_purge):
                    purge_future = workers.submit(
                        plugin.retry_expiry_purge, receipt.receipt_id
                    )
                    self.assertTrue(unlink_entered.wait(timeout=5))
                    suspend_future = workers.submit(
                        suspend_project_after_start,
                        self.store,
                        config.project_id,
                        "suspend-after-expiry-unlink-1",
                        suspension_started,
                    )
                    self.assertTrue(suspension_started.wait(timeout=5))
                    self.assertFalse(
                        suspend_future.done(),
                        "suspension must wait for the fenced unlink and receipt",
                    )
                    release_unlink.set()
                    completed_purge = purge_future.result(timeout=10)
                    transition = suspend_future.result(timeout=10)
            self.assertEqual(completed_purge.status.value, "complete")
            self.assertFalse(artifact_path.exists())
            self.assertEqual(transition.registration.status, "suspended")
            self.assertEqual(transition.receipt.revision, 2)
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.retry_expiry_purge(receipt.receipt_id)
        finally:
            release_unlink.set()

    def _assert_suspended_start_event_and_stage_denied(
        self,
        plugin: ProjectPlugin,
        goal_id: str,
        event: EventEnvelope,
    ) -> None:
        """Reject goal, event, activation, and staging writes after suspension."""

        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.goal_start_from_request(
                "A direct plugin start must honor project suspension",
                (SuccessCriterion("denied", "No new goal is created"),),
            )
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.service.goal_start(
                "A direct service start must honor project suspension",
                (SuccessCriterion("denied", "No new goal is created"),),
            )
        standalone_service = CuratorService(
            self.store, plugin.service.purger, project_id=plugin.config.project_id
        )
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            standalone_service.goal_start(
                "A standalone registered service start must be denied",
                (SuccessCriterion("denied", "No new goal is created"),),
            )
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.goal_activate(goal_id, "Must remain planned", 1)
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.process_event(event)
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.stage_artifact(
                goal_id, "cue", "suspended-stage", io.BytesIO(b"must not write")
            )

    def _assert_suspended_service_effects_denied(
        self, plugin: ProjectPlugin, goal_id: str
    ) -> None:
        """Verify review and cleanup effects are rejected before service calls."""

        with (
            patch.object(plugin.service, "fact_compaction_approve") as archive,
            patch.object(plugin.service, "sde_assess") as assess,
            patch.object(plugin.service, "sde_correction_record") as correction,
            patch.object(plugin.service, "sde_quality_feedback_record") as feedback,
            patch.object(plugin.service, "sde_confirm") as confirm,
            patch.object(plugin.service, "artifact_inventory_complete") as inventory,
            patch.object(plugin.service, "authorize_artifact_cleanup") as authorize,
            patch.object(plugin.service, "release_artifact_hold") as release_hold,
            patch.object(
                plugin.service.store, "retry_quarantined_event"
            ) as retry_event,
        ):
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.fact_compaction_approve(
                    FactCompactionApprovalRequest(
                        compaction_id="compaction",
                        goal_id=goal_id,
                        project_id="untrusted-project-value",
                        fact_ids=(),
                        source_sha256="0" * 64,
                        reviewer_id="reviewer",
                        approval_reason="reason",
                    )
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_assess(
                    SDEAssessmentRequest(
                        goal_id, Materiality.ROUTINE, "reason", (), None, None
                    )
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_correction_record("correction", "candidate", "fix", "why")
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_quality_feedback_record(
                    "feedback", "candidate", SDEQualityFeedbackLabel.USEFUL
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_confirm(
                    SDEConfirmationRequest(
                        "candidate",
                        ReviewDecision.REJECTED,
                        (),
                        artifact_inventory_complete=False,
                    ),
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.artifact_inventory_complete("receipt", (), "0" * 64)
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.authorize_artifact_cleanup(
                    ArtifactCleanupAuthorizationRequest(
                        receipt_id="receipt",
                        artifacts=(),
                        manifest_sha256="0" * 64,
                        dependency_map_sha256="0" * 64,
                        target="persistence/HISTORY.md",
                    )
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.release_artifact_hold("receipt", "goal/cue/file", "reason")
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.retry_quarantined_event("event", "test-operator")
            for service_write in (
                archive,
                assess,
                correction,
                feedback,
                confirm,
                inventory,
                authorize,
                release_hold,
                retry_event,
            ):
                service_write.assert_not_called()

    def write_config(self, content: str | None = None) -> None:
        """Write a minimal, valid repository-local config fixture."""

        if not content:
            write_consumer_config(self.root, "consumer-a")
        else:
            (self.root / CONFIG_FILENAME).write_text(content)
            (self.root / CONFIG_FILENAME).chmod(0o600)

    @staticmethod
    def _goal(plugin: ProjectPlugin, goal_id: str):
        """Create a scoped goal that owns a fixture staging directory."""

        return plugin.service.goal_start(
            f"Exercise staging scope {goal_id}",
            (SuccessCriterion("verified", "The staging scope is isolated"),),
            goal_id=goal_id,
        )

    def _register_project(self, rationale: str) -> ProjectConfig:
        """Provision the exact local binding required by lifecycle-fenced effects."""

        config = ProjectConfig.load(self.root)
        try:
            registration = self.store.get_project_registration(config.project_id)
        except NotFoundError:
            self.store.register_project(
                ProjectRegistrationRequest.from_project_config(config, rationale),
                "test-admin",
            )
        else:
            binding = (
                registration.repository_fingerprint,
                registration.config_sha256,
                registration.backend_api_version,
            )
            configured = (
                config.repository_fingerprint,
                config.config_sha256,
                config.backend_api_version,
            )
            if binding != configured:
                self.store.update_project_registration(
                    ProjectRegistrationRequest.from_project_config(
                        config, rationale, registration.revision
                    ),
                    "test-admin",
                    f"test-config-update-{registration.revision + 1}",
                )
        return config

    @staticmethod
    def write_config_at(root: Path, content: str) -> None:
        """Write a fixture config in the requested consumer repository."""

        (root / CONFIG_FILENAME).write_text(content)
        (root / CONFIG_FILENAME).chmod(0o600)

    def _valid_config(self) -> str:
        """Return the same valid TOML fixture used by setup."""

        return (self.root / CONFIG_FILENAME).read_text()
