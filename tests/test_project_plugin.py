"""Repository config and reference project-plugin boundary tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import tracemalloc
import unittest
from threading import Event, Lock, Thread
from typing import BinaryIO, cast
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from project_fixtures import create_consumer_repo
from purge_fixtures import TestReviewAuthorizer

from curatormd_v2 import (
    ArtifactRef,
    ChecklistGoalStartRequest,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    GoalStartOptions,
    ProjectRegistrationRequest,
    ProjectStatusChangeRequest,
    SuccessCriterion,
)
from curatormd_v2.events import EventEnvelope, FactRecorded, GoalStarted
from curatormd_v2.models import (
    FactKind,
    Materiality,
    ReviewDecision,
    SDECandidate,
    SDEQualityFeedbackLabel,
    SDEStatus,
)
from curatormd_v2.project_config import (
    CONFIG_FILENAME,
    PROJECT_PLUGIN_API_VERSION,
    ProjectConfig,
    ProjectConfigError,
    _sensitive_config_category,  # pyright: ignore[reportPrivateUsage]  # Direct traversal regression.
)
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import ConflictError, NotFoundError
from curatormd_v2.testing import assert_goal_started_event_contract


class PausingEvidenceVerifier:  # pylint: disable=too-few-public-methods
    """Pause source verification to exercise a project lifecycle cutover."""

    def __init__(self, store: CuratorStore, entered: Event, release: Event) -> None:
        self.store = store
        self.entered = entered
        self.release = release
        self.transaction_states: list[bool] = []

    def attest(
        self, evidence: EvidenceRef, context: EvidenceVerificationContext
    ):
        """Record transaction state, block, then issue fixture provenance."""

        self.transaction_states.append(self.store.transaction_active)
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release evidence verification")
        return attest_test_evidence(evidence, context)


class ProjectPluginTests(unittest.TestCase):
    """Verify strict repo-local config and project-bound service access."""

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

    def test_due_purge_scheduler_uses_exclusive_staging_lock(self) -> None:
        """Serialize scheduled deletes against project plugin staging writes."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        probe_fd = os.open(self.stage, os.O_RDONLY | os.O_DIRECTORY)

        def assert_staging_locked(limit: int) -> tuple[()]:
            self.assertEqual(limit, 9)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return ()

        try:
            with patch.object(
                plugin.service,
                "retry_due_purges",
                side_effect=assert_staging_locked,
            ) as retry:
                self.assertEqual(plugin.retry_due_purges(9), ())
            retry.assert_called_once_with(9)
        finally:
            os.close(probe_fd)

    def test_staging_open_error_does_not_retain_private_path(self) -> None:
        """Sanitized staging failures do not chain filesystem path details."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        private_path = "/srv/private/customer/staging"
        with patch(
            "curatormd_v2.project_plugin.os.open",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            with self.assertRaisesRegex(
                ProjectConfigError, "staging root cannot be opened safely"
            ) as raised:
                plugin.retry_due_purges(9)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def write_config(self, content: str | None = None) -> None:
        """Write a minimal, valid repository-local config fixture."""

        config = content or """\
            schema_version = 1
            backend_api_version = 1
            project_id = "consumer-a"

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
        (self.root / CONFIG_FILENAME).write_text(config)
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

    def test_valid_config_binds_only_existing_scoped_paths(self) -> None:
        """Load project identity, checklist, staging, and Markdown targets."""

        config = ProjectConfig.load(self.root)

        self.assertEqual(config.backend_api_version, PROJECT_PLUGIN_API_VERSION)
        self.assertEqual(config.project_id, "consumer-a")
        self.assertEqual(
            config.config_sha256,
            hashlib.sha256(
                (self.root / CONFIG_FILENAME).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(len(config.repository_fingerprint), 64)
        self.assertEqual(config.checklist_path("tasks"), self.root / "docs/tasks.md")
        self.assertEqual(config.staging_root, self.stage)
        self.assertEqual(
            config.persistence_targets,
            (self.root / "persistence/HISTORY.md",),
        )
        self.assertIsNone(config.staging_max_project_bytes)
        self.assertIsNone(config.staging_max_project_files)
        with self.assertRaisesRegex(ProjectConfigError, "outside configured read scope"):
            config.resolve_read_path("persistence/HISTORY.md")
        with self.assertRaisesRegex(ProjectConfigError, "not configured"):
            config.checklist_path("unknown")

    def test_invalid_toml_error_does_not_retain_config_source(self) -> None:
        """Sanitized TOML failures must not retain raw configuration text."""

        self.write_config('project_id = "PRIVATE_CONFIG_CANARY\n')
        with self.assertRaisesRegex(ProjectConfigError, "valid UTF-8 TOML") as raised:
            ProjectConfig.load(self.root)
        self.assertNotIn("PRIVATE_CONFIG_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_sensitive_config_error_does_not_retain_credential_value(self) -> None:
        """Credential rejection keeps safe metadata out of retained frames."""

        secret = "PRIVATE_CONFIG_CANARY_7f91a3"
        config = self._valid_config().replace(
            'project_id = "consumer-a"',
            f'project_id = "token={secret}"',
        )
        self.write_config(config)

        caught: ProjectConfigError | None = None
        try:
            ProjectConfig.load(self.root)
        except ProjectConfigError as exc:
            caught = exc

        self.assertIsNotNone(caught)
        error = cast(ProjectConfigError, caught)
        self.assertIn(
            "sensitive content rejected in project config value",
            str(error),
        )
        self.assertNotIn(secret, str(error))
        self.assertIn("credential_assignment", str(error))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        tb = error.__traceback__
        load_frames: list[dict[str, object]] = []
        while tb is not None:
            if tb.tb_frame.f_code.co_name == "load":
                load_frames.append(cast(dict[str, object], tb.tb_frame.f_locals))
            tb = tb.tb_next
        self.assertEqual(len(load_frames), 1)
        self.assertNotIn("root_table", load_frames[0])
        self.assertNotIn(secret, repr(load_frames[0]))

    def test_sensitive_config_scan_handles_deep_nesting(self) -> None:
        """Scan deeply nested TOML values without consuming Python call depth."""

        safe_value: object = "ordinary bounded value"
        sensitive_value: object = "token=private-test-canary"
        for _ in range(sys.getrecursionlimit() + 32):
            safe_value = [safe_value]
            sensitive_value = [sensitive_value]

        self.assertIsNone(_sensitive_config_category(safe_value))
        self.assertEqual(
            _sensitive_config_category(sensitive_value),
            "credential_assignment",
        )

    def test_missing_config_path_error_does_not_echo_untrusted_path(self) -> None:
        """Path resolution errors must not expose a configured filesystem path."""

        self.write_config(
            self._valid_config().replace(
                'tasks = "docs/tasks.md"', 'tasks = "PRIVATE_PATH_CANARY"'
            )
        )
        with self.assertRaisesRegex(ProjectConfigError, "does not exist") as raised:
            ProjectConfig.load(self.root)
        self.assertNotIn("PRIVATE_PATH_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_checklist_utf8_error_does_not_retain_source(self) -> None:
        """Checklist decode failures must not retain the source bytes."""

        config = ProjectConfig.load(self.root)
        (self.root / "docs" / "tasks.md").write_bytes(
            b"PRIVATE_CHECKLIST_CANARY\xff"
        )
        with self.assertRaisesRegex(ProjectConfigError, "bounded UTF-8") as raised:
            config.checklist_snapshot("tasks", "- [ ] Example task")
        self.assertNotIn("PRIVATE_CHECKLIST_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_published_project_config_fixture_loads(self) -> None:
        """Accept the checked-in config example in a matching consumer repo."""

        (self.root / "tests").mkdir()
        (self.root / "docs" / "implementation-checklist.md").write_text(
            "- [ ] Implement the consumer integration\n", encoding="utf-8"
        )
        (self.root / "persistence" / "LESSONS-LEARNED.md").write_text(
            "# Lessons\n", encoding="utf-8"
        )
        example = (
            Path(__file__).resolve().parents[1]
            / "docs/examples/curatormd-v2.toml"
        ).read_text(encoding="utf-8")
        self.write_config(example)

        config = ProjectConfig.load(self.root)

        self.assertEqual(config.project_id, "example-project")
        self.assertEqual(
            config.checklist_path("implementation"),
            self.root / "docs/implementation-checklist.md",
        )
        self.assertEqual(len(config.persistence_targets), 2)
        self.assertEqual(config.staging_root, self.stage)

    def test_project_staging_budgets_are_optional_bounded_integers(self) -> None:
        """Consumer config may opt into finite project-wide staging limits."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        configured = base.replace(
            'root = ".curatormd-v2/staging"',
            'root = ".curatormd-v2/staging"\n'
            "max_project_bytes = 4096\n"
            "max_project_files = 25",
        )
        self.write_config(configured)
        config = ProjectConfig.load(self.root)
        self.assertEqual(config.staging_max_project_bytes, 4096)
        self.assertEqual(config.staging_max_project_files, 25)

        for invalid in ("true", "0", "1099511627777"):
            updated = configured.replace(
                "max_project_bytes = 4096", f"max_project_bytes = {invalid}"
            )
            self.write_config(
                updated
            )
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ProjectConfigError, "staging.max_project_bytes"
            ):
                ProjectConfig.load(self.root)

    def test_reference_plugin_creates_checklist_goal_in_its_project_only(self) -> None:
        """Bind a repo config to the shared store with strict project scoping."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal = plugin.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Implement the linked task",
                success_criteria=(SuccessCriterion("done", "Task is verified"),),
                exact_item_text="- [ ] Example task",
                options=GoalStartOptions(
                    next_action="Inspect the linked implementation files"
                ),
            )
        )

        self.assertEqual(goal.project_id, "consumer-a")
        stored = plugin.goal_status(goal.goal_id).goal
        self.assertEqual(stored.checklist_id, "tasks")
        self.assertEqual(stored.checklist_source_text, "- [ ] Example task")
        self.assertEqual(stored.next_action, "Inspect the linked implementation files")
        self.assertTrue((stored.checklist_version or "").startswith("sha256:"))
        original_version = stored.checklist_version
        (self.root / "docs" / "tasks.md").write_text("- [x] Example task\n")
        self.assertEqual(
            plugin.goal_status(goal.goal_id).goal.checklist_version, original_version
        )
        with self.assertRaisesRegex(ProjectConfigError, "exact source line"):
            plugin.goal_start_from_checklist(
                ChecklistGoalStartRequest(
                    checklist_id="tasks",
                    problem="Not on the checklist",
                    success_criteria=(SuccessCriterion("done", "Task is verified"),),
                    exact_item_text="- [ ] Not the source",
                )
            )
        self.assertEqual(len(plugin.goal_list()), 1)
        with self.assertRaises(ProjectConfigError):
            ProjectPlugin(
                config,
                plugin.service.__class__(
                    self.store,
                    plugin.service.purger,
                    project_id="other-project",
                ),
            )

    def test_request_and_accepted_subtask_intake_preserve_explicit_criteria(self) -> None:
        """Create request and child goals without deriving success criteria."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        parent_criteria = (
            SuccessCriterion("intake", "The supplied request criteria are retained"),
        )
        parent = plugin.goal_start_from_request(
            "Implement the explicitly requested feature",
            parent_criteria,
            owner="user-1",
            next_action="Break the accepted request into bounded child work",
        )
        child_criteria = (
            SuccessCriterion("child-test", "The isolated child test passes"),
        )
        child = plugin.goal_start_subtask(
            parent.goal_id,
            "Add the isolated regression test",
            child_criteria,
            owner="agent-1",
        )

        self.assertEqual(parent.success_criteria, parent_criteria)
        self.assertEqual(
            plugin.goal_status(parent.goal_id).goal.next_action,
            "Break the accepted request into bounded child work",
        )
        self.assertEqual(child.success_criteria, child_criteria)
        self.assertEqual(child.parent_goal_id, parent.goal_id)
        self.assertEqual(plugin.goal_status(child.goal_id).goal.parent_goal_id, parent.goal_id)
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_from_request("Criteria must be explicit", ())
        with self.assertRaisesRegex(ValueError, "at least one success criterion"):
            plugin.goal_start_subtask(parent.goal_id, "No implicit criteria", ())

    def test_checklist_event_intake_rejects_forged_snapshot_and_allows_exact_retry(self) -> None:
        """Bind event-based checklist starts to the configured current source."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        version, source_text = plugin.config.checklist_snapshot(
            "tasks", "- [ ] Example task"
        )
        payload = GoalStarted(
            goal_id="checklist-event-goal",
            problem="Complete the selected checklist task",
            success_criteria=(SuccessCriterion("verified", "The task is verified"),),
            checklist_id="tasks",
            checklist_version=version,
            checklist_source_text=source_text,
        )
        event = EventEnvelope(
            event_id="checklist-event-1",
            project_id="consumer-a",
            source_id="test-producer",
            payload=payload,
        )
        accepted = plugin.process_event(event)
        self.assertEqual(accepted.status.value, "processed")

        # A completed event retry remains idempotent after checklist evolution.
        (self.root / "docs" / "tasks.md").write_text("- [x] Example task\n")
        self.assertEqual(plugin.process_event(event), accepted)

        forged = EventEnvelope(
            event_id="checklist-event-forged",
            project_id="consumer-a",
            source_id="test-producer",
            payload=GoalStarted(
                goal_id="forged-checklist-goal",
                problem="Pretend a checklist line was selected",
                success_criteria=(SuccessCriterion("verified", "The task is verified"),),
                checklist_id="tasks",
                checklist_version=version,
                checklist_source_text="- [ ] Not an actual checklist row",
            ),
        )
        with self.assertRaisesRegex(ProjectConfigError, "exact source line"):
            plugin.process_event(forged)
        self.assertEqual([item.goal.goal_id for item in plugin.goal_list()], [payload.goal_id])

    def test_direct_plugin_event_and_stage_writes_are_fenced_after_suspension(
        self,
    ) -> None:
        """Direct reference-plugin writes cannot bypass project suspension."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "direct-plugin-suspended-stage-goal"
        self._goal(plugin, goal_id)
        self.store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Suspend before direct plugin event processing",
                expected_revision=1,
                transition_id="direct-plugin-suspend-1",
            ),
            "test-admin",
        )
        event = EventEnvelope(
            event_id="direct-plugin-suspended-event",
            project_id=config.project_id,
            source_id="direct-plugin-test",
            payload=GoalStarted(
                goal_id="direct-plugin-suspended-goal",
                problem="Prove suspended plugin writes are fenced",
                success_criteria=(
                    SuccessCriterion("denied", "No event receipt is created"),
                ),
            ),
        )

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
            self.store, plugin.service.purger, project_id=config.project_id
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
        with (
            patch.object(plugin.service, "fact_compaction_approve") as archive,
            patch.object(plugin.service, "sde_assess") as assess,
            patch.object(plugin.service, "sde_correction_record") as correction,
            patch.object(plugin.service, "sde_quality_feedback_record") as feedback,
            patch.object(plugin.service, "sde_confirm") as confirm,
            patch.object(plugin.service, "artifact_inventory_complete") as inventory,
            patch.object(plugin.service, "authorize_artifact_cleanup") as authorize,
            patch.object(plugin.service, "release_artifact_hold") as release_hold,
            patch.object(plugin.service.store, "retry_quarantined_event") as retry_event,
        ):
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.fact_compaction_approve(
                    "compaction", goal_id, (), "0" * 64, "reviewer", "reason"
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_assess(goal_id, Materiality.ROUTINE, "reason", ())
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_correction_record("correction", "candidate", "fix", "why")
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_quality_feedback_record(
                    "feedback", "candidate", SDEQualityFeedbackLabel.USEFUL
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.sde_confirm(
                    "candidate",
                    ReviewDecision.REJECTED,
                    (),
                    artifact_inventory_complete=False,
                )
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.artifact_inventory_complete("receipt", (), "0" * 64)
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.authorize_artifact_cleanup(
                    "receipt", (), "0" * 64, "0" * 64, "persistence/HISTORY.md"
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
        with self.assertRaises(NotFoundError):
            self.store.event_receipt(config.project_id, event.event_id)
        self.assertEqual(
            [item.goal.goal_id for item in plugin.goal_list()], [goal_id]
        )
        self.assertFalse((self.stage / goal_id).exists())

    def test_event_verification_runs_outside_transaction_and_rechecks_revision(self) -> None:
        """A project cutover during evidence proof prevents the event commit."""

        config = ProjectConfig.load(self.root)
        verifier_entered = Event()
        release_verifier = Event()
        verifier = PausingEvidenceVerifier(
            self.store, verifier_entered, release_verifier
        )
        plugin = ProjectPlugin.bind(config, self.store, verifier)
        standalone_service = CuratorService(
            self.store,
            plugin.service.purger,
            verifier,
            project_id=config.project_id,
        )
        goal = self._goal(plugin, "event-proof-cutover-goal")
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:event-cutover",
            hashlib.sha256(b"event-cutover-proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        event = EventEnvelope(
            event_id="event-proof-cutover",
            project_id=config.project_id,
            source_id="test-producer",
            payload=FactRecorded(
                goal_id=goal.goal_id,
                fact_id="event-proof-cutover-fact",
                kind=FactKind.VERIFICATION,
                bullet="The event evidence was verified",
                criterion_id="verified",
                evidence=(evidence,),
            ),
        )
        failures: list[BaseException] = []

        def process() -> None:
            try:
                standalone_service.process_event(event)
            except BaseException as exc:  # pylint: disable=broad-exception-caught
                failures.append(exc)

        worker = Thread(target=process)
        worker.start()
        self.assertTrue(verifier_entered.wait(timeout=3))
        secondary_store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(secondary_store.close)
        registration = secondary_store.get_project_registration(config.project_id)
        secondary_store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Suspend during event evidence verification",
                expected_revision=registration.revision,
                transition_id="event-proof-cutover-suspend",
            ),
            "test-admin",
        )
        release_verifier.set()
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(verifier.transaction_states, [False])
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ConflictError)
        with self.assertRaises(NotFoundError):
            self.store.get_fact("event-proof-cutover-fact", config.project_id)
        self.assertEqual(
            self.store.event_receipt(config.project_id, event.event_id).status.value,
            "received",
        )

    def test_reusable_producer_backend_contract_assertions(self) -> None:
        """Exercise the importable contract helper against the reference plugin."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        event = EventEnvelope(
            event_id="shared-contract-event-1",
            project_id="consumer-a",
            source_id="contract-test-producer",
            source_sequence=1,
            payload=GoalStarted(
                goal_id="shared-contract-goal-1",
                problem="Preserve producer supplied goal contract fields",
                success_criteria=(
                    SuccessCriterion("persisted", "All supplied fields are retained"),
                ),
                owner="contract-test-owner",
                next_action="Verify the consumer implementation",
            ),
        )

        evidence = assert_goal_started_event_contract(
            plugin,
            event,
            expected_project_id="consumer-a",
        )

        self.assertEqual(evidence.project_id, "consumer-a")
        self.assertEqual(evidence.event_id, event.event_id)
        self.assertEqual(evidence.event_payload_bytes_retained, 0)
        self.assertGreaterEqual(
            evidence.event_payload_bytes_received,
            evidence.event_payload_bytes,
        )

    def test_storage_usage_scans_sizes_without_following_staging_symlinks(self) -> None:
        """Measure nested regular files, but expose a skipped link as incomplete."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        nested = self.stage / "nested"
        nested.mkdir(parents=True)
        (nested / "small.bin").write_bytes(b"12345")
        outside = Path(self.temporary) / "outside.bin"
        outside.write_bytes(b"must not count or be followed")
        (self.stage / "escape").symlink_to(outside)

        usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.regular_file_count, 1)
        self.assertEqual(usage.observed_file_bytes, 5)
        self.assertEqual(usage.directory_count, 1)
        self.assertEqual(usage.symlink_count, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "symlink_skipped")

    def test_storage_usage_marks_a_bounded_partial_scan_incomplete(self) -> None:
        """Stop after the configured entry ceiling and report partial results."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "first.bin").write_bytes(b"a")
        (self.stage / "second.bin").write_bytes(b"bb")

        with patch("curatormd_v2.project_plugin.MAX_STAGING_SCAN_ENTRIES", 1):
            usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.entries_scanned, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "entry_limit")

    def test_storage_usage_attributes_bytes_to_fixed_temporary_classes(self) -> None:
        """Attribute repository staging totals without exposing artifact names."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "goal-classes" / "cue").mkdir(parents=True)
        (self.stage / "goal-classes" / "cue" / "a.bin").write_bytes(b"123")
        (self.stage / "goal-classes" / "raw-chat" / "nested").mkdir(parents=True)
        (self.stage / "goal-classes" / "raw-chat" / "nested" / "b.bin").write_bytes(
            b"12345"
        )
        (self.stage / "legacy-root-file.bin").write_bytes(b"12")

        usage = plugin.storage_usage().staging

        assert usage is not None
        by_class = {item.artifact_class.value: item for item in usage.classes}
        self.assertEqual(usage.regular_file_count, 3)
        self.assertEqual(usage.observed_file_bytes, 10)
        self.assertEqual(by_class["cue"].regular_file_count, 1)
        self.assertEqual(by_class["cue"].observed_file_bytes, 3)
        self.assertEqual(by_class["raw-chat"].regular_file_count, 1)
        self.assertEqual(by_class["raw-chat"].observed_file_bytes, 5)
        self.assertEqual(by_class["other"].regular_file_count, 1)
        self.assertEqual(by_class["other"].observed_file_bytes, 2)
        self.assertTrue(usage.inventory_complete)

    def test_discover_staging_artifacts_streams_hashes_and_returns_exact_paths(self) -> None:
        """Hash regular files in scope while omitting no-follow symlinks."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "scan-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        nested = goal_stage / "nested"
        nested.mkdir(parents=True)
        artifact = nested / "cue.json"
        artifact.write_bytes(b'{"temporary":true}')
        outside = Path(self.temporary) / "outside.json"
        outside.write_bytes(b"outside")
        (goal_stage / "escape.json").symlink_to(outside)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "symlink_skipped")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.scope_goal_id, goal_id)
        self.assertEqual(len(inventory.artifacts), 1)
        self.assertEqual(inventory.artifacts[0].path, str(artifact))
        self.assertEqual(
            inventory.artifacts[0].sha256,
            hashlib.sha256(b'{"temporary":true}').hexdigest(),
        )

    def test_discovery_includes_temporary_artifact_classes_and_duplicates(self) -> None:
        """Inventory each temporary class, retaining same-content file paths."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "classes-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        artifact_files = {
            "raw-chat/session.jsonl": b"temporary chat bytes",
            "cue/event.json": b"cue bytes",
            "import/source.md": b"import bytes",
            "scratch/work.tmp": b"scratch bytes",
            "generated/intermediate.json": b"intermediate bytes",
            "duplicates/copy.tmp": b"scratch bytes",
        }
        for relative_path, contents in artifact_files.items():
            path = goal_stage / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNotNone(inventory.manifest_sha256)
        self.assertEqual(
            {Path(item.path).relative_to(goal_stage).as_posix() for item in inventory.artifacts},
            set(artifact_files),
        )
        scratch_hashes = {
            item.sha256
            for item in inventory.artifacts
            if Path(item.path).relative_to(goal_stage).as_posix()
            in {"scratch/work.tmp", "duplicates/copy.tmp"}
        }
        self.assertEqual(scratch_hashes, {hashlib.sha256(b"scratch bytes").hexdigest()})

    def test_occurrence_registry_is_stable_and_separate_from_expiry_age(self) -> None:
        """Persist content-free file identity without granting direct files age."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "occurrence-registry-goal"
        self._goal(plugin, goal_id)
        path = self.stage / goal_id / "scratch" / "manual.tmp"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"same transient bytes")

        first = plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertIsNotNone(first.occurrence_id)
        second = plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertEqual(second.occurrence_id, first.occurrence_id)

        reopened_store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(reopened_store.close)
        reopened_plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), reopened_store
        )
        after_reopen = reopened_plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertEqual(after_reopen.occurrence_id, first.occurrence_id)

        replacement = path.with_name("replacement.tmp")
        replacement.write_bytes(b"same transient bytes")
        replacement.replace(path)
        after_replacement = reopened_plugin.discover_staging_artifacts(
            goal_id
        ).artifacts[0]
        self.assertNotEqual(after_replacement.occurrence_id, first.occurrence_id)

        expiry = reopened_plugin.discover_expired_staging_artifacts(
            datetime.now(UTC) + timedelta(hours=73)
        )
        self.assertFalse(expiry.inventory_complete)
        self.assertEqual(expiry.unknown_age_count, 1)
        self.assertEqual(expiry.eligible_artifacts, ())

    def test_discovery_hash_byte_limit_returns_no_false_complete_manifest(self) -> None:
        """Do not hash past the configured byte budget or claim completeness."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "limit-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        goal_stage.mkdir()
        (goal_stage / "too-large.tmp").write_bytes(b"0123456789")

        with patch("curatormd_v2.project_plugin.MAX_STAGING_HASH_BYTES", 5):
            inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "hash_byte_limit")
        self.assertEqual(inventory.artifacts, ())
        self.assertIsNone(inventory.manifest_sha256)

    def test_stage_artifact_streams_to_atomic_goal_scoped_file(self) -> None:
        """The producer API writes bounded temporary bytes and returns only a digest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-goal"
        self._goal(plugin, goal_id)
        payload = b"temporary cue payload"

        artifact = plugin.stage_artifact(
            goal_id, "cue", "event-1", io.BytesIO(payload)
        )

        self.assertEqual(
            Path(artifact.path),
            self.stage / goal_id / "cue" / "event-1.bin",
        )
        self.assertEqual(artifact.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(Path(artifact.path).read_bytes(), payload)
        self.assertEqual(stat.S_IMODE(Path(artifact.path).stat().st_mode), 0o600)
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, (artifact,))

    def test_expired_staging_uses_72_hour_max_age_when_no_record_is_ready(self) -> None:
        """Unrecorded producer files reach the hard 72-hour age ceiling."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            expired = plugin.stage_artifact(
                goal_id, "cue", "expired-cue", io.BytesIO(b"old transient")
            )
            fresh = plugin.stage_artifact(
                goal_id, "import", "fresh-import", io.BytesIO(b"new transient")
            )

        before_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=71, minutes=59)
        )
        self.assertTrue(before_cap.inventory_complete)
        self.assertEqual(before_cap.eligible_artifacts, ())
        self.assertEqual(before_cap.unknown_age_count, 0)

        at_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        self.assertTrue(at_cap.inventory_complete)
        self.assertEqual(
            at_cap.eligible_artifacts,
            tuple(sorted((expired, fresh), key=lambda item: item.path)),
        )
        self.assertEqual(
            at_cap.manifest_sha256,
            hashlib.sha256(
                json.dumps(
                    [
                        (item.path, item.sha256, item.occurrence_id)
                        for item in at_cap.eligible_artifacts
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )

    def test_expiry_becomes_eligible_after_post_stage_facts_are_recorded(self) -> None:
        """Do not make reviewers wait 72 hours after facts are already recorded."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-immediate-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime.now(UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "raw-chat", "source-chat", io.BytesIO(b"temporary source")
            )

        before_facts = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(minutes=1)
        )
        self.assertEqual(before_facts.eligible_artifacts, ())

        plugin.service.goal_fact(
            goal_id,
            FactKind.RESEARCH,
            "Compact facts were recorded from the temporary source",
        )
        after_facts = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(minutes=1)
        )

        self.assertTrue(after_facts.inventory_complete)
        self.assertEqual(after_facts.eligible_artifacts, (artifact,))
        self.assertEqual(after_facts.pending_sde_artifact_count, 0)

    def test_expiry_retry_preserves_same_content_replacement_after_approval(self) -> None:
        """A persisted expiry receipt cannot unlink a replacement occurrence."""

        config = self._register_project("Register the expiry retry fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "expiry-replacement-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            approved = plugin.stage_artifact(
                goal_id, "cue", "same-content", io.BytesIO(b"temporary source")
            )
        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest = snapshot.manifest_sha256
        if manifest is None:
            self.fail("complete expiry snapshot must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            "consumer-a", "expiry-reviewer", manifest, snapshot.eligible_artifacts
        )

        original_path = Path(approved.path)
        replacement = original_path.with_name("replacement.tmp")
        replacement.write_bytes(b"temporary source")
        original_path.unlink()
        replacement.rename(original_path)

        current_expiry = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        self.assertEqual(current_expiry.eligible_artifacts, ())
        self.assertEqual(current_expiry.unknown_age_count, 1)

        retried = plugin.retry_expiry_purge(receipt.receipt_id)

        self.assertTrue(original_path.exists())
        self.assertEqual(original_path.read_bytes(), b"temporary source")
        self.assertEqual(retried.status.value, "purge_pending")
        self.assertEqual(retried.artifacts[0].device_id, approved.device_id)
        self.assertEqual(retried.artifacts[0].inode_id, approved.inode_id)

    def test_suspended_project_blocks_direct_expiry_purge_paths(self) -> None:
        """Direct expiry approval and retry cannot unlink after suspension."""

        config = self._register_project("Register the suspended expiry fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "suspended-expiry-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "suspended-expiry", io.BytesIO(b"retained source")
            )
        expired = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest_sha256 = expired.manifest_sha256
        if manifest_sha256 is None:
            self.fail("complete expiry inventory must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            config.project_id,
            "test-admin",
            manifest_sha256,
            expired.eligible_artifacts,
        )
        self.store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Fence expiry cleanup before suspension cutover",
                expected_revision=1,
                transition_id="suspend-expiry-cleanup-1",
            ),
            "test-admin",
        )

        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.approve_expired_staging_inventory(
                expired.eligible_artifacts,
                manifest_sha256,
                now=staged_at + timedelta(hours=72),
            )
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.retry_expiry_purge(receipt.receipt_id)
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.retry_pending_purges()

        self.assertTrue(Path(artifact.path).is_file())
        self.assertEqual(
            self.store.expiry_purge_receipt(receipt.receipt_id, config.project_id).status.value,
            "purge_pending",
        )

    def test_inflight_expiry_unlink_finishes_before_project_suspend_cutover(
        self,
    ) -> None:
        """An admitted unlink holds the project fence until its receipt commits."""

        config = self._register_project("Register the expiry unlink race fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "inflight-expiry-unlink-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "scratch", "inflight-unlink", io.BytesIO(b"expiry payload")
            )
        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest = snapshot.manifest_sha256
        if manifest is None:
            self.fail("complete expiry inventory must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            config.project_id, "test-admin", manifest, snapshot.eligible_artifacts
        )

        unlink_entered = Event()
        release_unlink = Event()
        suspension_started = Event()
        original_purge = plugin.service.purger.purge

        def pause_before_unlink(target: ArtifactRef) -> bool:
            unlink_entered.set()
            if not release_unlink.wait(timeout=5):
                raise TimeoutError("test did not release the paused purge")
            return original_purge(target)

        def suspend_project():
            suspension_started.set()
            registration = self.store.get_project_registration(config.project_id)
            return self.store.set_project_status(
                ProjectStatusChangeRequest(
                    project_id=config.project_id,
                    status="suspended",
                    rationale="Suspend only after admitted expiry unlink commits",
                    expected_revision=registration.revision,
                    transition_id="suspend-after-expiry-unlink-1",
                ),
                "test-admin",
            )

        try:
            with ThreadPoolExecutor(max_workers=2) as workers:
                with patch.object(plugin.service.purger, "purge", pause_before_unlink):
                    purge_future = workers.submit(
                        plugin.retry_expiry_purge, receipt.receipt_id
                    )
                    self.assertTrue(unlink_entered.wait(timeout=5))
                    suspend_future = workers.submit(suspend_project)
                    self.assertTrue(suspension_started.wait(timeout=5))
                    self.assertFalse(
                        suspend_future.done(),
                        "suspension must wait for the fenced unlink and receipt",
                    )
                    release_unlink.set()
                    completed_purge = purge_future.result(timeout=10)
                    transition = suspend_future.result(timeout=10)
            self.assertEqual(completed_purge.status.value, "complete")
            self.assertFalse(Path(artifact.path).exists())
            self.assertEqual(transition.registration.status, "suspended")
            self.assertEqual(transition.receipt.revision, 2)
            with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
                plugin.retry_expiry_purge(receipt.receipt_id)
        finally:
            release_unlink.set()

    def test_pending_sde_cannot_extend_the_72_hour_retention_ceiling(self) -> None:
        """Pending review delays prompt expiry but not the absolute age cap."""

        config = self._register_project("Register the pending SDE expiry fixture")
        plugin = ProjectPlugin.bind(
            config,
            self.store,
            review_authorizer=TestReviewAuthorizer(),
        )
        goal_id = "expiry-pending-sde-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "pending-sde-cue", io.BytesIO(b"temporary source")
            )
        fact, _ = plugin.service.goal_fact(
            goal_id, FactKind.RESEARCH, "A compact fact for the pending review"
        )
        self.store.add_sde_candidate(
            SDECandidate(
                goal_id=goal_id,
                materiality=Materiality.IMPLEMENTATION,
                rationale="Review a material outcome before expiry",
                fact_ids=(fact.fact_id,),
                impact="The source may contain a durable implementation decision",
                retrieval_value="A reviewer must decide whether the outcome is useful",
            ),
            project_id="consumer-a",
        )

        before_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=71, minutes=59)
        )
        self.assertEqual(before_cap.eligible_artifacts, ())
        self.assertEqual(before_cap.pending_sde_artifact_count, 1)

        at_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )

        self.assertTrue(at_cap.inventory_complete)
        self.assertEqual(at_cap.eligible_artifacts, (artifact,))
        self.assertEqual(at_cap.pending_sde_artifact_count, 1)
        self.assertTrue(Path(artifact.path).is_file())
        manifest_sha256 = at_cap.manifest_sha256
        if manifest_sha256 is None:
            self.fail("complete expiry snapshot must have a manifest hash")
        at_cap_time = staged_at + timedelta(hours=72)
        with patch("curatormd_v2.store.utc_now", return_value=at_cap_time.isoformat()):
            receipt = plugin.approve_expired_staging_inventory(
                at_cap.eligible_artifacts,
                manifest_sha256,
                now=at_cap_time,
            )
        self.assertEqual(receipt.status.value, "complete")
        self.assertFalse(Path(artifact.path).exists())

        candidate = self.store.list_sde_candidates(goal_id, "consumer-a")[0]
        self.assertEqual(candidate.status, SDEStatus.PENDING_REVIEW)
        plugin.service.sde_confirm(
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=True,
        )
        reviewed_candidate = self.store.list_sde_candidates(goal_id, "consumer-a")[0]
        self.assertEqual(reviewed_candidate.status, SDEStatus.APPROVED)
        self.assertFalse(Path(artifact.path).exists())

    def test_expired_staging_fails_closed_for_untracked_files(self) -> None:
        """A direct filesystem writer cannot borrow another file's age proof."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-unknown-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch("curatormd_v2.store.utc_now", return_value=staged_at.isoformat()):
            tracked = plugin.stage_artifact(
                goal_id, "cue", "tracked-cue", io.BytesIO(b"old transient")
            )
        untracked_path = self.stage / goal_id / "scratch" / "direct-writer.bin"
        untracked_path.parent.mkdir(parents=True)
        untracked_path.write_bytes(b"unknown age")

        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=73)
        )

        self.assertFalse(snapshot.inventory_complete)
        self.assertEqual(snapshot.unknown_age_count, 1)
        self.assertIsNone(snapshot.manifest_sha256)
        self.assertEqual(snapshot.eligible_artifacts, ())
        self.assertTrue(Path(tracked.path).is_file())

    def test_producer_api_stages_every_supported_temporary_artifact_class(self) -> None:
        """Inventory every temporary class after publication through the producer API."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "all-producer-classes-goal"
        self._goal(plugin, goal_id)
        classes = (
            "raw-chat",
            "cue",
            "import",
            "scratch",
            "generated",
            "duplicate",
        )
        payloads = {
            artifact_class: io.BytesIO(b"same temporary bytes")
            for artifact_class in classes
        }

        published = {
            artifact_class: plugin.stage_artifact(
                goal_id, artifact_class, f"artifact-{index}", payload
            )
            for index, (artifact_class, payload) in enumerate(payloads.items())
        }
        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNotNone(inventory.manifest_sha256)
        self.assertEqual(
            {Path(item.path).parent.name for item in inventory.artifacts},
            set(classes),
        )
        self.assertEqual(set(inventory.artifacts), set(published.values()))
        self.assertEqual(
            {item.sha256 for item in inventory.artifacts},
            {hashlib.sha256(b"same temporary bytes").hexdigest()},
        )

    def test_large_import_staging_uses_bounded_python_memory(self) -> None:
        """A large producer stream is copied in bounded chunks, not buffered whole."""

        # Stream fixture exposes only the required bounded `read` interface.
        class GeneratedStream:  # pylint: disable=too-few-public-methods
            """Generate a repeatable source without retaining the complete payload."""

            def __init__(self, total_bytes: int) -> None:
                self.remaining = total_bytes
                self.max_read_size = 0

            def read(self, size: int = -1) -> bytes:
                """Return one bounded chunk from the generated fixture input."""

                if size < 0 or size > 64 * 1024:
                    raise AssertionError("staging must request at most a 64 KiB chunk")
                self.max_read_size = max(self.max_read_size, size)
                chunk_size = min(size, self.remaining)
                self.remaining -= chunk_size
                return b"i" * chunk_size

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "large-import-goal"
        self._goal(plugin, goal_id)
        total_bytes = 24 * 1024 * 1024
        generated = GeneratedStream(total_bytes)

        tracemalloc.start()
        try:
            artifact = plugin.stage_artifact(
                goal_id, "import", "large-import", cast(BinaryIO, generated)
            )
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        expected_digest = hashlib.sha256()
        chunk = b"i" * (64 * 1024)
        for _ in range(total_bytes // len(chunk)):
            expected_digest.update(chunk)
        self.assertEqual(generated.remaining, 0)
        self.assertLessEqual(generated.max_read_size, 64 * 1024)
        self.assertEqual(Path(artifact.path).stat().st_size, total_bytes)
        self.assertEqual(artifact.sha256, expected_digest.hexdigest())
        self.assertLess(peak_bytes, 4 * 1024 * 1024)

    def test_stage_artifact_rejects_unsafe_names_oversize_and_overwrite(self) -> None:
        """Writes reject path injection, oversize streams, and artifact replacement."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-limits"
        self._goal(plugin, goal_id)
        with self.assertRaisesRegex(ValueError, "artifact_class"):
            plugin.stage_artifact(goal_id, "../outside", "safe", io.BytesIO(b"x"))
        with self.assertRaisesRegex(ValueError, "artifact_id"):
            plugin.stage_artifact(goal_id, "cue", "../outside", io.BytesIO(b"x"))

        with patch("curatormd_v2.project_plugin.MAX_STAGED_ARTIFACT_BYTES", 4):
            with self.assertRaisesRegex(ConflictError, "per-file byte ceiling"):
                plugin.stage_artifact(
                    goal_id, "cue", "too-large", io.BytesIO(b"12345")
                )
        self.assertFalse((self.stage / goal_id / "cue" / "too-large.bin").exists())

        first = plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"first"))
        with self.assertRaises(FileExistsError):
            plugin.stage_artifact(goal_id, "cue", "stable", io.BytesIO(b"second"))
        self.assertEqual(Path(first.path).read_bytes(), b"first")
        self.assertFalse(any(path.name.endswith(".partial") for path in self.stage.rglob("*")))

    def test_project_staging_budgets_block_excess_without_deleting(self) -> None:
        """Budgeted staging fails closed and reports limits without auto-purge."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\n'
                "max_project_bytes = 5\n"
                "max_project_files = 10",
            )
        )
        self._register_project("Update the project staging budget fixture")
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "budget-goal"
        self._goal(plugin, goal_id)
        first = plugin.stage_artifact(goal_id, "cue", "first", io.BytesIO(b"1234"))
        # A distinct goal can hit the byte limit during streaming; its partial
        # file is removed and the already-staged artifact is untouched.
        second_goal = "budget-bytes"
        self._goal(plugin, second_goal)
        with self.assertRaisesRegex(ConflictError, "project staging byte budget"):
            plugin.stage_artifact(second_goal, "cue", "too-large", io.BytesIO(b"12"))

        usage = plugin.storage_usage()
        self.assertEqual(usage.staging_project_byte_limit, 5)
        self.assertEqual(usage.staging_project_file_limit, 10)
        self.assertTrue(Path(first.path).is_file())
        self.assertFalse((self.stage / second_goal / "cue" / "too-large.bin").exists())
        self.assertFalse(any(path.name.endswith(".partial") for path in self.stage.rglob("*")))

        # A separate consumer-selected staging root demonstrates the file cap.
        second_root = self.root / ".curatormd-v2" / "staging-files"
        second_root.mkdir()
        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        base = base.replace("max_project_bytes = 5\n", "").replace(
            "max_project_files = 10\n", ""
        )
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging-files"\nmax_project_files = 1',
            )
        )
        self._register_project("Update the project file budget fixture")
        file_limited = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        file_goal = "file-budget"
        self._goal(file_limited, file_goal)
        file_limited.stage_artifact(file_goal, "cue", "first", io.BytesIO(b"a"))
        with self.assertRaisesRegex(ConflictError, "project staging file-count budget"):
            file_limited.stage_artifact(file_goal, "cue", "second", io.BytesIO(b"b"))

    def test_project_staging_budget_requires_complete_project_inventory(self) -> None:
        """Do not claim quota enforcement if skipped staging entries exist."""

        base = (self.root / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.write_config(
            base.replace(
                'root = ".curatormd-v2/staging"',
                'root = ".curatormd-v2/staging"\nmax_project_files = 10',
            )
        )
        self._register_project("Update the incomplete inventory fixture")
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "incomplete-budget"
        self._goal(plugin, goal_id)
        outside = Path(self.temporary) / "outside-budget.bin"
        outside.write_bytes(b"unaccounted")
        (self.stage / "skipped-link").symlink_to(outside)

        with self.assertRaisesRegex(ConflictError, "incomplete inventory"):
            plugin.stage_artifact(goal_id, "cue", "blocked", io.BytesIO(b"x"))
        self.assertFalse((self.stage / goal_id / "cue" / "blocked.bin").exists())

    def test_inventory_waits_for_plugin_writer_atomic_publication(self) -> None:
        """A concurrent review scan cannot adopt an in-progress partial file."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-race"
        self._goal(plugin, goal_id)
        read_entered = Event()
        allow_read = Event()
        contending_lock_attempted = Event()
        lock_call_guard = Lock()
        lock_calls = 0
        original_staging_lock = getattr(plugin, "_locked_staging_root")

        class PausingStream(io.BytesIO):
            """Hold a staged write open while another operation requests a lock."""

            def read(self, size: int | None = -1) -> bytes:
                read_entered.set()
                if not allow_read.wait(timeout=5):
                    raise TimeoutError("test did not release the producer stream")
                return super().read(size)

        stream = PausingStream(b"complete artifact bytes")

        def tracked_staging_lock():
            nonlocal lock_calls
            with lock_call_guard:
                lock_calls += 1
                if lock_calls == 2:
                    contending_lock_attempted.set()
            return original_staging_lock()

        def discover():
            return plugin.discover_staging_artifacts(goal_id)

        with patch.object(plugin, "_locked_staging_root", tracked_staging_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                writer = pool.submit(
                    plugin.stage_artifact,
                    goal_id,
                    "cue",
                    "atomic",
                    stream,
                )
                self.assertTrue(read_entered.wait(timeout=2))
                review_scan = pool.submit(discover)
                self.assertTrue(contending_lock_attempted.wait(timeout=2))
                time.sleep(0.05)
                self.assertFalse(review_scan.done())
                allow_read.set()
                artifact = writer.result(timeout=2)
                inventory = review_scan.result(timeout=2)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, (artifact,))
        self.assertEqual(Path(artifact.path).read_bytes(), b"complete artifact bytes")

    def test_staging_manifests_are_isolated_by_goal(self) -> None:
        """One goal's approved manifest cannot include another goal's files."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        self._goal(plugin, "goal-alpha")
        self._goal(plugin, "goal-beta")
        alpha = self.stage / "goal-alpha"
        beta = self.stage / "goal-beta"
        alpha.mkdir()
        beta.mkdir()
        alpha_file = alpha / "raw-event.json"
        beta_file = beta / "raw-event.json"
        alpha_file.write_bytes(b"alpha temporary artifact")
        beta_file.write_bytes(b"beta temporary artifact")

        alpha_inventory = plugin.discover_staging_artifacts("goal-alpha")
        beta_inventory = plugin.discover_staging_artifacts("goal-beta")

        self.assertTrue(alpha_inventory.usage.inventory_complete)
        self.assertTrue(beta_inventory.usage.inventory_complete)
        self.assertEqual(alpha_inventory.scope_goal_id, "goal-alpha")
        self.assertEqual(beta_inventory.scope_goal_id, "goal-beta")
        self.assertEqual(
            tuple(item.path for item in alpha_inventory.artifacts),
            (str(alpha_file),),
        )
        self.assertEqual(
            tuple(item.path for item in beta_inventory.artifacts),
            (str(beta_file),),
        )

    def test_project_inventory_includes_orphaned_goal_directories(self) -> None:
        """A project snapshot covers every class and orphaned goal directories."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        self._goal(plugin, "goal-alpha")
        self._goal(plugin, "goal-beta")
        artifacts = {
            "raw-chat": self.stage / "goal-alpha" / "raw-chat" / "raw.bin",
            "cue": self.stage / "goal-alpha" / "cue" / "cue.bin",
            "import": self.stage / "goal-beta" / "import" / "import.bin",
            "scratch": self.stage / "goal-beta" / "scratch" / "scratch.bin",
            "generated": self.stage / "goal-alpha" / "generated" / "generated.bin",
            "duplicate": self.stage / "orphaned-goal" / "duplicate" / "duplicate.bin",
            "other": self.stage / "orphaned-goal" / "unrecognized" / "other.bin",
        }
        for artifact_class, artifact in artifacts.items():
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(artifact_class.encode())

        inventory = plugin.discover_project_staging_artifacts()

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNone(inventory.scope_goal_id)
        self.assertEqual(inventory.usage.regular_file_count, len(artifacts))
        self.assertEqual(
            {item.path for item in inventory.artifacts},
            {str(artifact) for artifact in artifacts.values()},
        )
        self.assertEqual(
            {item.artifact_class.value for item in inventory.usage.classes},
            {"raw-chat", "cue", "import", "scratch", "generated", "duplicate", "other"},
        )
        self.assertEqual(len(inventory.manifest_sha256 or ""), 64)

    def test_goal_staging_scope_does_not_follow_a_symlink(self) -> None:
        """Reject a goal directory replaced by a symlink outside the staging root."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "symlink-goal"
        self._goal(plugin, goal_id)
        outside = Path(self.temporary) / "outside-stage"
        outside.mkdir()
        (outside / "must-remain.json").write_bytes(b"outside scope")
        (self.stage / goal_id).symlink_to(outside, target_is_directory=True)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "scope_unavailable")
        self.assertEqual(inventory.artifacts, ())
        self.assertEqual(inventory.scope_goal_id, goal_id)

    def test_missing_goal_staging_directory_is_a_scoped_empty_manifest(self) -> None:
        """A goal with no staged files has an explicit, complete empty manifest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "empty-stage-goal"
        self._goal(plugin, goal_id)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.regular_file_count, 0)
        self.assertEqual(inventory.artifacts, ())
        self.assertEqual(inventory.scope_goal_id, goal_id)
        self.assertEqual(inventory.manifest_sha256, hashlib.sha256(b"[]").hexdigest())

    def test_two_repository_plugins_share_backend_without_sharing_goals(self) -> None:
        """Keep each plugin's config and goals isolated in one global store."""

        project_a = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        root_b = Path(self.temporary) / "consumer-b"
        root_b.mkdir()
        (root_b / ".git").mkdir()
        (root_b / "src").mkdir()
        (root_b / "docs").mkdir()
        (root_b / "persistence").mkdir()
        (root_b / ".curatormd-v2" / "staging").mkdir(parents=True)
        (root_b / "docs" / "tasks.md").write_text("- [ ] Separate task\n")
        (root_b / "persistence" / "HISTORY.md").write_text("# B history\n")
        config_b = self._valid_config().replace(
            'project_id = "consumer-a"', 'project_id = "consumer-b"'
        )
        self.write_config_at(root_b, config_b)
        config_b = ProjectConfig.load(root_b)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config_b, "Register the second isolated plugin fixture"
            ),
            "test-admin",
        )
        project_b = ProjectPlugin.bind(config_b, self.store)

        goal_a = project_a.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Project A task",
                success_criteria=(SuccessCriterion("a", "A is done"),),
                exact_item_text="- [ ] Example task",
            )
        )
        goal_b = project_b.goal_start_from_checklist(
            ChecklistGoalStartRequest(
                checklist_id="tasks",
                problem="Project B task",
                success_criteria=(SuccessCriterion("b", "B is done"),),
                exact_item_text="- [ ] Separate task",
            )
        )

        artifact_a = (
            self.root
            / ".curatormd-v2"
            / "staging"
            / goal_a.goal_id
            / "import"
            / "project-a-only.bin"
        )
        artifact_a.parent.mkdir(parents=True)
        artifact_a.write_bytes(b"project-a-private-artifact")

        self.assertEqual([item.goal.goal_id for item in project_a.goal_list()], [goal_a.goal_id])
        self.assertEqual([item.goal.goal_id for item in project_b.goal_list()], [goal_b.goal_id])
        with self.assertRaises(LookupError):
            project_b.goal_status(goal_a.goal_id)
        with self.assertRaises(LookupError):
            project_b.discover_staging_artifacts(goal_a.goal_id)
        project_inventory_b = project_b.discover_project_staging_artifacts()
        self.assertTrue(project_inventory_b.usage.inventory_complete)
        self.assertNotIn(
            str(artifact_a), {item.path for item in project_inventory_b.artifacts}
        )

        projection_a = project_a.persist_goal(
            goal_a.goal_id, "persistence/HISTORY.md"
        )
        projection_b = project_b.persist_goal(
            goal_b.goal_id, "persistence/HISTORY.md"
        )
        history_a = (self.root / "persistence/HISTORY.md").read_text(
            encoding="utf-8"
        )
        history_b = (root_b / "persistence/HISTORY.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(projection_a.project_id, "consumer-a")
        self.assertEqual(projection_b.project_id, "consumer-b")
        self.assertIn(goal_a.goal_id, history_a)
        self.assertNotIn(goal_b.goal_id, history_a)
        self.assertIn(goal_b.goal_id, history_b)
        self.assertNotIn(goal_a.goal_id, history_b)
        with self.assertRaises(LookupError):
            project_b.persist_goal(goal_a.goal_id, "persistence/HISTORY.md")

    @staticmethod
    def write_config_at(root: Path, content: str) -> None:
        """Write a fixture config in the requested consumer repository."""

        (root / CONFIG_FILENAME).write_text(content)
        (root / CONFIG_FILENAME).chmod(0o600)

    def test_rejects_path_traversal_symlinks_unknown_fields_and_unknown_adapters(self) -> None:
        """Reject unsafe scope, config extensions, and unregistered adapters."""

        traversal = self._valid_config().replace('"src", "docs"', '"../"')
        self.write_config(traversal)
        with self.assertRaises(ProjectConfigError):
            ProjectConfig.load(self.root)

        unknown = self._valid_config().replace(
            'project_id = "consumer-a"',
            'project_id = "consumer-a"\nbackend_database = "./db.sqlite3"',
        )
        self.write_config(unknown)
        with self.assertRaisesRegex(ProjectConfigError, "invalid config fields"):
            ProjectConfig.load(self.root)

        self.write_config()
        adapter = self._valid_config().replace("adapters = []", 'adapters = ["git"]')
        self.write_config(adapter)
        with self.assertRaisesRegex(ProjectConfigError, "unregistered evidence"):
            ProjectConfig.load(self.root)
        self.assertEqual(
            ProjectConfig.load(
                self.root, registered_evidence_adapters=frozenset({"git"})
            ).evidence_adapters,
            ("git",),
        )

    def test_action_adapters_are_read_only_by_default_and_require_opt_in(self) -> None:
        """Actions require both repository allowlisting and host registration."""

        default_config = ProjectConfig.load(self.root)
        self.assertEqual(default_config.action_adapters, ())

        self.write_config(
            self._valid_config()
            + '\n[actions]\nadapters = ["approved-runner"]\n'
        )
        with self.assertRaisesRegex(ProjectConfigError, "unregistered action"):
            ProjectConfig.load(self.root)

        opted_in = ProjectConfig.load(
            self.root,
            registered_action_adapters=frozenset({"approved-runner"}),
        )
        self.assertEqual(opted_in.action_adapters, ("approved-runner",))

        self.write_config()
        outside = Path(self.temporary) / "outside"
        outside.mkdir()
        (self.root / "src" / "escape").symlink_to(outside, target_is_directory=True)
        self.write_config(self._valid_config().replace('"src", "docs"', '"src/escape"'))
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            ProjectConfig.load(self.root)

    def test_rejects_persistence_escape_and_oversized_config(self) -> None:
        """Constrain Markdown destinations and configuration resource use."""

        escaped_target = self._valid_config().replace(
            '"persistence/HISTORY.md"', '"../outside.md"'
        )
        self.write_config(escaped_target)
        with self.assertRaisesRegex(ProjectConfigError, "escape"):
            ProjectConfig.load(self.root)

        self.write_config(self._valid_config() + "\n#" + ("x" * 17_000))
        with self.assertRaisesRegex(ProjectConfigError, "exceeds"):
            ProjectConfig.load(self.root)

    def test_rejects_config_file_symlink(self) -> None:
        """Do not follow a config path outside the consumer repository."""

        external = Path(self.temporary) / "external-config.toml"
        external.write_text(self._valid_config())
        config_path = self.root / CONFIG_FILENAME
        config_path.unlink()
        config_path.symlink_to(external)

        with self.assertRaisesRegex(ProjectConfigError, "missing regular project config"):
            ProjectConfig.load(self.root)

    def test_rejects_config_owned_by_another_account(self) -> None:
        """Require the config to share the repository root's trusted owner."""

        repository_uid = self.root.stat().st_uid
        other_owner = os.stat_result(
            (stat.S_IFREG | 0o644, 1, 1, 1, repository_uid + 1, 1, 1, 1, 1, 1)
        )
        with patch("curatormd_v2.project_config.os.fstat", return_value=other_owner):
            with self.assertRaisesRegex(ProjectConfigError, "owner must match"):
                ProjectConfig.load(self.root)

    def test_rejects_group_or_world_writable_config(self) -> None:
        """Prevent another local account from silently replacing plugin policy."""

        (self.root / CONFIG_FILENAME).chmod(0o666)
        with self.assertRaisesRegex(ProjectConfigError, "must not be group- or world-writable"):
            ProjectConfig.load(self.root)

    def test_rejects_unsupported_backend_contract_version(self) -> None:
        """Refuse a config declaring a backend contract this runtime cannot honor."""

        self.write_config(
            self._valid_config().replace("backend_api_version = 1", "backend_api_version = 2")
        )
        with self.assertRaisesRegex(ProjectConfigError, "backend_api_version is not supported"):
            ProjectConfig.load(self.root)

    def test_rejects_secret_like_config_values_without_echoing_them(self) -> None:
        """Do not allow recognizable credentials in otherwise valid config fields."""

        secret = "sk-" + "A" * 24
        self.write_config(
            self._valid_config().replace('project_id = "consumer-a"', f'project_id = "{secret}"')
        )
        with self.assertRaises(ProjectConfigError) as captured:
            ProjectConfig.load(self.root)
        self.assertNotIn(secret, str(captured.exception))

    def test_rechecks_checklist_and_staging_paths_at_use_time(self) -> None:
        """Catch symlink swaps made after the initial config validation."""

        config = ProjectConfig.load(self.root)
        external = Path(self.temporary) / "outside.md"
        external.write_text("outside scope\n")
        checklist = self.root / "docs" / "tasks.md"
        checklist.unlink()
        checklist.symlink_to(external)
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            config.checklist_path("tasks")

        checklist.unlink()
        checklist.write_text("- [ ] Restored task\n")
        moved_stage = self.root / ".curatormd-v2" / "staging-original"
        self.stage.rename(moved_stage)
        self.stage.symlink_to(Path(self.temporary), target_is_directory=True)
        with self.assertRaisesRegex(ProjectConfigError, "symlinks"):
            ProjectPlugin.bind(config, self.store)

    def _valid_config(self) -> str:
        """Return the same valid TOML fixture used by setup."""

        return (self.root / CONFIG_FILENAME).read_text()


if __name__ == "__main__":
    unittest.main()
