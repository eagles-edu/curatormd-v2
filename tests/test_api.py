"""Authorization and request-budget tests for the API facade."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from datetime import UTC, datetime, timedelta
import hashlib
import json
from io import BytesIO
import sqlite3
import tempfile
from typing import cast
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from project_fixtures import create_consumer_repo
from purge_fixtures import approved_empty_inventory_request

from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    ArtifactCleanupAuthorizationRequest,
    AuditReceipt,
    backup_database,
    ArtifactRef,
    ConflictError,
    CuratorStore,
    EvidenceGateError,
    FactRecorded,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    EventEnvelope,
    EventFailureCategory,
    EventInboxStatus,
    EventReceiptArchiveRequest,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    FactKind,
    FactCompactionProposal,
    GoalChildrenPageRequest,
    GoalCriteriaAmended,
    GoalStarted,
    GoalActivated,
    GoalListCapacityError,
    GoalStatus,
    DependencyProbeObservation,
    REQUIRED_HEALTH_DEPENDENCIES,
    InMemoryTokenBucket,
    Materiality,
    ProjectAction,
    ProjectConfig,
    ProjectGrantAuthorizer,
    ProjectPlugin,
    ProjectRegistrationRequest,
    RateLimitExceeded,
    ReacquisitionAction,
    ReviewDecision,
    RetentionHoldKind,
    SDEQualityFeedbackLabel,
    SDEConfirmationRequest,
    SDECorrectionRequest,
    SDEQualityFeedbackRequest,
    SuccessCriterion,
)
from curatormd_v2.service import SDEAssessmentRequest
from curatormd_v2.read_models import SDEReviewPacket
from curatormd_v2.store import FactCompactionApprovalRequest
from curatormd_v2.store import ConsumerBindingTransitionRequest
from curatormd_v2.content_safety import SensitiveContentError
from curatormd_v2.project_config import ProjectConfigError
from curatormd_v2.store import NotFoundError
from curatormd_v2.hermes_context import hermes_source_id

__all__ = (
    'AllowProject', 'ArtifactCleanupAuthorizationRequest', 'ArtifactRef',
    'AuditReceipt', 'AuthenticatedCaller', 'AuthenticatedCuratorAPI',
    'BytesIO', 'ConflictError', 'ConsumerBindingTransitionRequest',
    'CuratorStore', 'DependencyProbeObservation', 'DependencyReadiness',
    'EventEnvelope', 'EventFailureCategory', 'EventInboxStatus',
    'EventReceiptArchiveRequest',
    'EvidenceGateError', 'EvidenceOutcome', 'EvidenceRef',
    'EvidenceVerificationContext', 'FactCompactionApprovalRequest', 'FactCompactionProposal',
    'FactKind', 'FactRecorded', 'GoalActivated',
    'GoalChildrenPageRequest', 'GoalCriteriaAmended', 'GoalListCapacityError',
    'GoalStarted', 'GoalStatus', 'InMemoryTokenBucket',
    'MAX_FACTS_PER_PROJECT', 'MAX_FACT_BYTES_PER_PROJECT', 'Materiality',
    'NotFoundError', 'Path', 'ProjectAction',
    'ProjectConfig', 'ProjectConfigError', 'ProjectGrantAuthorizer',
    'ProjectPlugin', 'ProjectRegistrationRequest', 'REQUIRED_HEALTH_DEPENDENCIES',
    'RateLimitExceeded', 'ReacquisitionAction', 'RetentionHoldKind',
    'ReviewDecision', 'ReviewHost', 'SDEAssessmentRequest',
    'SDEConfirmationRequest', 'SDECorrectionRequest', 'SDEQualityFeedbackLabel',
    'SDEQualityFeedbackRequest', 'SDEReviewPacket', 'SensitiveContentError',
    'SuccessCriterion', 'TestVerifier', 'UTC',
    '_ApiTestSupport', '_ReviewArtifacts', '_ReviewScenario',
    'annotations', 'approved_empty_inventory_request', 'attest_test_evidence',
    'backup_database', 'cast', 'create_consumer_repo',
    'dataclass', 'datetime', 'hashlib',
    'hermes_source_id', 'json', 'patch',
    'replace', 'sqlite3', 'tempfile',
    'timedelta', 'unittest',
)


class AllowProject:  # pylint: disable=too-few-public-methods
    """Allow only explicitly configured subject/project/action triples."""

    def __init__(self, grants: set[tuple[str, str, ProjectAction]]) -> None:
        self.grants = grants

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Allow only configured project operations for the test identity."""

        return (caller.subject_id, project_id, action) in self.grants


class TestVerifier:  # pylint: disable=too-few-public-methods
    """Verify only the exact stable evidence locator used by this test."""

    def __init__(self, store: CuratorStore | None = None) -> None:
        self.store = store

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the exact proof locator used by API tests."""

        if self.store is not None and self.store.transaction_active:
            raise AssertionError("evidence verification ran inside a write transaction")
        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:verified"
            else None
        )


class DependencyReadiness:  # pylint: disable=too-few-public-methods
    """Supply explicit host-owned readiness for health aggregation tests."""

    def __init__(
        self,
        values: dict[str, bool | None],
        observed_at: str | None = None,
    ) -> None:
        self.values = values
        self.observed_at = observed_at or datetime.now(UTC).isoformat()

    def readiness(self, project_id: str) -> dict[str, object]:
        """Return the fixture's project-scoped dependency observations."""

        del project_id
        return {
            name: DependencyProbeObservation(ready, self.observed_at)
            for name, ready in self.values.items()
        }


class ReviewHost:  # pylint: disable=too-few-public-methods
    """Authorize the API's exact verified subject as the reviewer."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute API review decisions to the authenticated test subject."""

        del project_id, candidate_id, decision
        if authenticated_subject != "hermes-user-1":
            raise PermissionError("review subject is not authenticated")
        return authenticated_subject

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute API corrections to the authenticated test subject."""

        del project_id, candidate_id
        if authenticated_subject != "hermes-user-1":
            raise PermissionError("correction subject is not authenticated")
        return authenticated_subject

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute quality feedback to the authenticated test subject."""

        return self.authorize_correction(project_id, candidate_id, authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute releases to the authenticated test subject."""

        del project_id, receipt_id, path, rationale
        if authenticated_subject != "hermes-user-1":
            raise PermissionError("hold-release subject is not authenticated")
        return authenticated_subject

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute exact expiry cleanup to the authenticated reviewer."""

        del project_id, manifest_sha256
        if authenticated_subject != "hermes-user-1":
            raise PermissionError("expiry reviewer is not authenticated")
        return authenticated_subject

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
    ) -> str:
        """Attribute exact SDE cleanup approval to the authenticated reviewer."""

        del project_id, receipt_id, manifest_sha256
        if authenticated_subject != "hermes-user-1":
            raise PermissionError("cleanup reviewer is not authenticated")
        return authenticated_subject


@dataclass(frozen=True)
class _ReviewScenario:
    """Shared state for the API review and artifact-lifecycle regression."""

    api: AuthenticatedCuratorAPI
    plugin: ProjectPlugin
    goal_id: str
    candidate_id: str
    unrelated_goal_id: str


@dataclass(frozen=True)
class _ReviewArtifacts:
    """Disposable artifacts used by the API review lifecycle test."""

    staged: Path
    unrelated_staged: Path
    unmapped_staged: Path
    mapped_fact_id: str


@dataclass(frozen=True)
class _VerifiedGoal:
    """Minimal evidence-backed goal input shared by review API regressions."""

    goal_id: str
    change_fact_id: str
    verification_fact_id: str


class _ApiTestSupport(unittest.TestCase):
    """Shared API test setup and review/artifact scenario helpers."""

    def setUp(self) -> None:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.root = Path(temporary) / "consumer"
        create_consumer_repo(self.root)
        (self.root / "docs" / "tasks.md").write_text("- [ ] API task\n")
        (self.root / "persistence" / "HISTORY.md").write_text("# History\n")
        (self.root / ".curatormd-v2.toml").write_text(
            """\
            schema_version = 1
            backend_api_version = 1
            project_id = "project-a"

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
        (self.root / ".curatormd-v2.toml").chmod(0o600)
        self.store = CuratorStore(Path(temporary) / "global.sqlite3")
        self.addCleanup(self.store.close)
        config = ProjectConfig.load(self.root)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config, "Register the API facade fixture"
            ),
            "test-admin",
        )
        self.plugin = ProjectPlugin.bind(config, self.store)
        self.caller = AuthenticatedCaller("hermes-user-1")
        self.authorizer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.READ),
                ("hermes-user-1", "project-a", ProjectAction.WRITE),
            }
        )


    def _prepare_project_metrics_fixture(
        self,
    ) -> tuple[AuthenticatedCuratorAPI, str, Path, str]:
        """Create one goal and private staging artifact for the metrics contract."""
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        problem = "Never export this task description"
        event = EventEnvelope(
            "metrics-goal-start",
            "project-a",
            GoalStarted(
                "metrics-goal",
                problem,
                (SuccessCriterion("done", "A metrics sample exists"),),
            ),
            source_id="metrics-source",
            source_sequence=1,
        )
        api.process_event_json(self.caller, "project-a", event.to_json())
        staged = (
            self.root
            / ".curatormd-v2"
            / "staging"
            / "metrics-goal"
            / "cue"
            / "private-cue.json"
        )
        staged.parent.mkdir(parents=True)
        staged.write_text("private artifact payload", encoding="utf-8")
        self.store.record_staging_artifact_time(
            "project-a",
            ArtifactRef(
                str(staged),
                hashlib.sha256(b"private artifact payload").hexdigest(),
                device_id=1,
                inode_id=2,
                occurrence_id="b" * 32,
            ),
        )
        config_path = self.root / ".curatormd-v2.toml"
        config_text = config_path.read_text(encoding="utf-8").replace(
            'root = ".curatormd-v2/staging"',
            'root = ".curatormd-v2/staging"\n'
            "max_project_bytes = 4096\n"
            "max_project_files = 25",
        )
        config_path.write_text(config_text, encoding="utf-8")
        config_path.chmod(0o600)
        configured_plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        configured_api = AuthenticatedCuratorAPI(
            {"project-a": configured_plugin}, self.authorizer
        )
        return configured_api, problem, config_path, config_text


    def _assert_project_metrics_content_free(
        self, metrics: str, problem: str
    ) -> None:
        """Check bounded counters and ensure private source content is absent."""
        self.assertIn(
            'curatormd_project_health_state{project_id="project-a",state="degraded"} 1',
            metrics,
        )
        self.assertIn('curatormd_goals{project_id="project-a",status="active"} 1', metrics)
        self.assertIn('event_type="goal.started",status="processed"', metrics)
        self.assertIn('curatormd_event_cursors{project_id="project-a"} 1', metrics)
        self.assertIn(
            'curatormd_staging_artifact_time_records{project_id="project-a"} 1',
            metrics,
        )
        self.assertIn(
            'curatormd_staging_artifact_occurrence_records{project_id="project-a"} 1',
            metrics,
        )
        self.assertIn(
            'curatormd_staging_artifact_occurrence_bytes{project_id="project-a"}',
            metrics,
        )
        self.assertNotIn("b" * 32, metrics)
        self.assertIn('curatormd_event_cursor_bytes{project_id="project-a"}', metrics)
        self.assertIn(
            'curatormd_cleanup_authorization_records{project_id="project-a"} 0',
            metrics,
        )
        self.assertIn(
            'curatormd_event_payload_scrub_records{project_id="project-a"}',
            metrics,
        )
        self.assertIn("curatormd_staging_bytes", metrics)
        self.assertIn(
            'curatormd_staging_project_byte_limit{project_id="project-a"} 4096',
            metrics,
        )
        self.assertIn(
            'curatormd_staging_project_file_limit{project_id="project-a"} 25',
            metrics,
        )
        self.assertIn(
            'curatormd_staging_class_files{project_id="project-a",class="cue"} 1',
            metrics,
        )
        self.assertIn(
            'curatormd_staging_class_bytes{project_id="project-a",class="cue"} 24',
            metrics,
        )
        self.assertNotIn('gate="staging_budget_reached"', metrics)
        self.assertNotIn(problem, metrics)
        self.assertNotIn("private artifact payload", metrics)
        self.assertNotIn("private-cue.json", metrics)
        self.assertNotIn("global_database_bytes", metrics)


    def _assert_project_metrics_format(self, metrics: str) -> None:
        """Validate unique Prometheus TYPE declarations and family samples."""
        type_families = [
            line.split()[2]
            for line in metrics.splitlines()
            if line.startswith("# TYPE ")
        ]
        self.assertEqual(len(type_families), len(set(type_families)))
        current_family: str | None = None
        pending_help: str | None = None
        for line in metrics.splitlines():
            if line.startswith("# TYPE "):
                current_family = line.split()[2]
                self.assertEqual(pending_help, current_family)
                pending_help = None
            elif line.startswith("# HELP "):
                pending_help = line.split()[2]
            elif line and not line.startswith("#"):
                self.assertIsNotNone(current_family)
                self.assertEqual(line.split("{", maxsplit=1)[0], current_family)
        self.assertIsNone(pending_help)


    def _assert_project_staging_budget_metrics(
        self, config_path: Path, config_text: str
    ) -> None:
        """Confirm either project budget limit blocks healthy staging status."""
        for byte_limit, file_limit in ((24, 25), (4096, 1)):
            with self.subTest(byte_limit=byte_limit, file_limit=file_limit):
                limited_config = config_text.replace(
                    "max_project_bytes = 4096",
                    f"max_project_bytes = {byte_limit}",
                ).replace(
                    "max_project_files = 25",
                    f"max_project_files = {file_limit}",
                )
                config_path.write_text(limited_config, encoding="utf-8")
                limited_plugin = ProjectPlugin.bind(
                    ProjectConfig.load(self.root), self.store
                )
                limited_api = AuthenticatedCuratorAPI(
                    {"project-a": limited_plugin}, self.authorizer
                )
                health = limited_api.project_health(self.caller, "project-a")
                self.assertEqual(health.status.value, "degraded")
                self.assertIn("staging_budget_reached", health.gate_codes)
                limited_metrics = limited_api.project_prometheus_metrics(
                    self.caller, "project-a"
                )
                self.assertIn(
                    'curatormd_project_open_gate{project_id="project-a",'
                    'gate="staging_budget_reached"} 1',
                    limited_metrics,
                )


    def _assert_sensitive_content_absent(
        self,
        api: AuthenticatedCuratorAPI,
        sensitive_texts: tuple[str, ...],
    ) -> None:
        """Verify rejected sensitive text is absent from API and storage sinks."""
        metrics = api.project_prometheus_metrics(self.caller, "project-a")
        for sensitive_text in sensitive_texts:
            self.assertNotIn(sensitive_text, metrics)

        secret_bytes = tuple(text.encode("utf-8") for text in sensitive_texts)
        database_path = Path(self.store.database)
        for path in (
            database_path,
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
        ):
            if path.exists():
                content = path.read_bytes()
                for secret in secret_bytes:
                    self.assertNotIn(secret, content, str(path))
        history = (self.root / "persistence" / "HISTORY.md").read_bytes()
        for secret in secret_bytes:
            self.assertNotIn(secret, history)

        backup_path = self.root.parent / "sensitive-rejection-backup.sqlite3"
        backup_database(self.store.database, backup_path)
        backup = backup_path.read_bytes()
        for secret in secret_bytes:
            self.assertNotIn(secret, backup)


    def _create_review_scenario(self) -> _ReviewScenario:
        """Create a candidate and API bound to the authenticated reviewer."""
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root),
            self.store,
            TestVerifier(self.store),
            ReviewHost(),
        )
        verified = self._create_verified_goal(
            plugin,
            "Implement a verified change",
            "Implemented the change",
            "Verification passed",
        )
        candidate = plugin.service.sde_assess(
            SDEAssessmentRequest(
                verified.goal_id,
                Materiality.IMPLEMENTATION,
                "A durable change has passing evidence",
                (verified.change_fact_id, verified.verification_fact_id),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        )
        assert candidate is not None
        authorizer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                ("hermes-user-1", "project-a", ProjectAction.READ),
            }
        )
        api = AuthenticatedCuratorAPI({"project-a": plugin}, authorizer)
        unrelated_goal = plugin.service.goal_start(
            "Keep another goal's temporary evidence isolated",
            (SuccessCriterion("verified", "Its files remain in its own scope"),),
            goal_id="unrelated-goal",
        )
        return _ReviewScenario(
            api,
            plugin,
            verified.goal_id,
            candidate.candidate_id,
            unrelated_goal.goal_id,
        )


    def _create_verified_goal(
        self,
        plugin: ProjectPlugin,
        title: str,
        change_text: str,
        verification_text: str,
    ) -> _VerifiedGoal:
        """Create a goal with one passing verification for review tests."""
        goal = plugin.service.goal_start(
            title,
            (SuccessCriterion("verified", "Verification evidence passes"),),
        )
        change, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, change_text
        )
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:verified",
            hashlib.sha256(b"test-proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        verification, _ = plugin.service.goal_fact(
            goal.goal_id,
            FactKind.VERIFICATION,
            verification_text,
            criterion_id="verified",
            evidence=(evidence,),
        )
        return _VerifiedGoal(goal.goal_id, change.fact_id, verification.fact_id)


    def _api_with_healthy_dependencies(
        self, plugin: ProjectPlugin, authorizer: AllowProject | None = None
    ) -> AuthenticatedCuratorAPI:
        """Build the API with every required synthetic host probe healthy."""
        return AuthenticatedCuratorAPI(
            {"project-a": plugin},
            authorizer or self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )


    def _prepare_review_artifacts(
        self, scenario: _ReviewScenario
    ) -> _ReviewArtifacts:
        """Create mapped, unrelated, and unmapped files; reject a stale packet."""
        plugin = scenario.plugin
        stage_root = self.root / ".curatormd-v2" / "staging"
        staged_dir = stage_root / scenario.goal_id
        staged_dir.mkdir()
        staged = staged_dir / "cue.json"
        staged.write_bytes(b'{"temporary":true}')
        staged_evidence = EvidenceRef(
            "staging_artifact",
            str(staged),
            hashlib.sha256(staged.read_bytes()).hexdigest(),
            EvidenceOutcome.PASSED,
        )
        mapped_fact, _ = plugin.service.goal_fact(
            scenario.goal_id,
            FactKind.RESEARCH,
            "Staged evidence source recorded",
            criterion_id="verified",
            evidence=(staged_evidence,),
        )
        displayed_packet = scenario.api.sde_review_packet(
            self.caller, "project-a", scenario.candidate_id
        )
        plugin.service.goal_fact(
            scenario.goal_id,
            FactKind.RESEARCH,
            "A later fact changes the displayed dependency map",
            criterion_id="verified",
            evidence=(staged_evidence,),
        )
        with self.assertRaisesRegex(ConflictError, "dependency map changed"):
            scenario.api.sde_confirm(
                self.caller,
                "project-a",
                SDEConfirmationRequest(
                    candidate_id=scenario.candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=displayed_packet.artifact_inventory.artifacts,
                    artifact_inventory_complete=True,
                    dependency_map_sha256=displayed_packet.dependency_map_sha256,
                ),
            )
        self.assertTrue(staged.exists())
        unrelated_dir = stage_root / scenario.unrelated_goal_id
        unrelated_dir.mkdir()
        unrelated_staged = unrelated_dir / "cue.json"
        unrelated_staged.write_bytes(b'{"unrelated":true}')
        unmapped_staged = staged_dir / "unmapped.json"
        unmapped_staged.write_bytes(b'{"unmapped":true}')
        return _ReviewArtifacts(
            staged,
            unrelated_staged,
            unmapped_staged,
            mapped_fact.fact_id,
        )


    def _assert_inventory_scope_and_authorization(
        self, scenario: _ReviewScenario, artifacts: _ReviewArtifacts
    ) -> tuple[ArtifactRef, ...]:
        """Check goal/project inventory and fail-closed review authorization."""
        stage_root = self.root / ".curatormd-v2" / "staging"
        inventory = scenario.api.discover_artifact_inventory(
            self.caller, "project-a", scenario.goal_id
        )
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.scope_goal_id, scenario.goal_id)
        self.assertEqual(len(inventory.artifacts), 2)
        orphan = stage_root / "orphaned-goal" / "scratch" / "unbound.bin"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"orphaned temporary data")
        project_inventory = scenario.api.discover_project_artifact_inventory(
            self.caller, "project-a"
        )
        self.assertTrue(project_inventory.usage.inventory_complete)
        self.assertIsNone(project_inventory.scope_goal_id)
        self.assertEqual(len(project_inventory.artifacts), 4)
        self.assertIn(
            str(orphan), {item.path for item in project_inventory.artifacts}
        )
        expiry_inventory = scenario.api.discover_project_expiry_inventory(
            self.caller, "project-a"
        )
        self.assertFalse(expiry_inventory.inventory_complete)
        self.assertEqual(expiry_inventory.unknown_age_count, 4)
        self.assertEqual(expiry_inventory.eligible_artifacts, ())
        self.assertIsNone(expiry_inventory.manifest_sha256)

        read_only_api = AuthenticatedCuratorAPI(
            {"project-a": scenario.plugin},
            AllowProject({("hermes-user-1", "project-a", ProjectAction.READ)}),
        )
        with self.assertRaisesRegex(PermissionError, "project is not authorized"):
            read_only_api.discover_project_artifact_inventory(
                self.caller, "project-a"
            )
        with self.assertRaisesRegex(PermissionError, "project is not authorized"):
            read_only_api.discover_project_expiry_inventory(
                self.caller, "project-a"
            )
        self.assertTrue(artifacts.staged.exists())
        return inventory.artifacts


    def _assert_empty_inventory_rejected(self, scenario: _ReviewScenario) -> None:
        """Reject a review request that omits the current staged artifacts."""
        with self.assertRaisesRegex(ConflictError, "does not match current inventory"):
            scenario.api.sde_confirm(
                self.caller,
                "project-a",
                approved_empty_inventory_request(scenario.candidate_id),
            )


    def _complete_review_inventory(
        self,
        scenario: _ReviewScenario,
        artifacts: tuple[ArtifactRef, ...],
    ) -> AuditReceipt:
        """Record the review and then complete its exact artifact inventory."""
        receipt = scenario.api.sde_confirm(
            self.caller,
            "project-a",
            SDEConfirmationRequest(
                candidate_id=scenario.candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=False,
            ),
        )
        completion_packet = scenario.api.sde_review_packet(
            self.caller,
            "project-a",
            scenario.candidate_id,
            tuple(
                replace(
                    item,
                    reacquisition_action=ReacquisitionAction.NOT_REQUIRED,
                )
                for item in artifacts
            ),
        )
        receipt = scenario.api.artifact_inventory_complete(
            self.caller,
            "project-a",
            receipt.receipt_id,
            completion_packet.review_artifacts,
            completion_packet.dependency_map_sha256,
        )
        self.assertEqual(receipt.reviewer_id, self.caller.subject_id)
        self.assertTrue(receipt.artifact_inventory_complete)
        return receipt


    def _assert_review_dependencies(
        self,
        scenario: _ReviewScenario,
        artifacts: _ReviewArtifacts,
        receipt: AuditReceipt,
    ) -> SDEReviewPacket:
        """Check authenticated review detail and exact evidence dependencies."""
        correction = scenario.api.sde_correction_record(
            self.caller,
            "project-a",
            SDECorrectionRequest(
                correction_id="api-correction-1",
                candidate_id=scenario.candidate_id,
                correction="Narrow the outcome claim",
                rationale="The evidence proves a passing test, not a production impact",
            ),
        )
        detail = scenario.api.sde_review_detail(
            self.caller, "project-a", scenario.candidate_id
        )
        packet = scenario.api.sde_review_packet(
            self.caller,
            "project-a",
            scenario.candidate_id,
            receipt.artifacts,
        )
        self.assertEqual(correction.reviewer_id, self.caller.subject_id)
        self.assertEqual(detail.corrections, (correction,))
        self.assertEqual(packet.detail.candidate.candidate_id, scenario.candidate_id)
        self.assertEqual(packet.detail.candidate.status.value, "approved")
        self.assertEqual(packet.detail.corrections, (correction,))
        self.assertTrue(packet.artifact_inventory.usage.inventory_complete)
        self.assertEqual(packet.artifact_inventory.scope_goal_id, scenario.goal_id)
        self.assertEqual(
            tuple(item.path for item in packet.artifact_inventory.artifacts),
            tuple(sorted((str(artifacts.staged), str(artifacts.unmapped_staged)))),
        )
        self.assertEqual(len(packet.artifact_dependencies), 2)
        dependency = packet.artifact_dependencies[0]
        self.assertEqual(dependency.artifact.path, str(artifacts.staged))
        self.assertEqual(
            dependency.binding.value,
            "path_and_digest_match_occurrence_unbound",
        )
        self.assertEqual(len(dependency.evidence_dependencies), 2)
        self.assertIn(
            artifacts.mapped_fact_id,
            {item.fact_id for item in dependency.evidence_dependencies},
        )
        self.assertTrue(
            all(item.criterion_id == "verified" for item in dependency.evidence_dependencies)
        )
        self.assertTrue(
            all(item.criterion_status == "verified" for item in dependency.evidence_dependencies)
        )
        unmapped_dependency = packet.artifact_dependencies[1]
        self.assertEqual(
            unmapped_dependency.artifact.path, str(artifacts.unmapped_staged)
        )
        self.assertEqual(unmapped_dependency.binding.value, "unmapped")
        self.assertEqual(unmapped_dependency.evidence_dependencies, ())
        self.assertEqual(len(packet.dependency_map_sha256), 64)
        return packet


    def _authorize_exact_artifact_cleanup(
        self,
        scenario: _ReviewScenario,
        artifacts: _ReviewArtifacts,
        receipt: AuditReceipt,
        packet: SDEReviewPacket,
    ) -> None:
        """Purge only the reviewed goal inventory and retain its receipt."""
        cleanup_manifest = packet.artifact_inventory.manifest_sha256
        assert cleanup_manifest is not None
        scenario.api.authorize_artifact_cleanup(
            self.caller,
            "project-a",
            ArtifactCleanupAuthorizationRequest(
                receipt_id=receipt.receipt_id,
                artifacts=packet.review_artifacts,
                manifest_sha256=cleanup_manifest,
                dependency_map_sha256=packet.dependency_map_sha256,
                target="persistence/HISTORY.md",
            ),
        )
        self.assertFalse(artifacts.staged.exists())
        self.assertFalse(artifacts.unmapped_staged.exists())
        self.assertTrue(artifacts.unrelated_staged.exists())
        saved_receipt = self.store.get_receipt(receipt.receipt_id, "project-a")
        self.assertEqual(
            saved_receipt.cleanup_dependency_map_sha256,
            packet.dependency_map_sha256,
        )


    def _assert_feedback_and_review_storage(
        self, scenario: _ReviewScenario, receipt: AuditReceipt
    ) -> None:
        """Check feedback replay, uniqueness, reviewer scope, and accounting."""
        saved_receipt = self.store.get_receipt(receipt.receipt_id, "project-a")
        feedback_request = SDEQualityFeedbackRequest(
            feedback_id="quality-feedback-1",
            candidate_id=scenario.candidate_id,
            label=SDEQualityFeedbackLabel.USEFUL,
            rationale="The proposed event captured the material implementation facts",
        )
        feedback = scenario.api.sde_quality_feedback_record(
            self.caller, "project-a", feedback_request
        )
        replayed_feedback = scenario.api.sde_quality_feedback_record(
            self.caller, "project-a", feedback_request
        )
        feedback_summary = scenario.api.sde_quality_feedback_summary(
            self.caller, "project-a"
        )
        self.assertEqual(feedback, replayed_feedback)
        self.assertEqual(feedback.reviewer_id, self.caller.subject_id)
        self.assertEqual(feedback_summary.total, 1)
        self.assertEqual(feedback_summary.counts[0][1], 1)
        metrics = scenario.api.project_prometheus_metrics(self.caller, "project-a")
        self.assertIn(
            'curatormd_sde_reviewer_feedback_total{project_id="project-a",label="useful"} 1',
            metrics,
        )
        self.assertNotIn("hermes-user-1", metrics)
        self.assertNotIn("implementation facts", metrics)
        with self.assertRaisesRegex(ConflictError, "already submitted feedback"):
            scenario.api.sde_quality_feedback_record(
                self.caller,
                "project-a",
                SDEQualityFeedbackRequest(
                    feedback_id="quality-feedback-2",
                    candidate_id=scenario.candidate_id,
                    label=SDEQualityFeedbackLabel.NOT_USEFUL,
                ),
            )
        usage = scenario.api.project_storage_usage(self.caller, "project-a")
        self.assertEqual(usage.sde_correction_count, 1)
        self.assertGreater(usage.sde_correction_record_bytes, 0)
        self.assertEqual(usage.sde_quality_feedback_count, 1)
        self.assertGreater(usage.sde_quality_feedback_record_bytes, 0)
        self.assertEqual(
            self.store.get_receipt(receipt.receipt_id, "project-a"), saved_receipt
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            scenario.api.sde_correction_record(
                AuthenticatedCaller("other-user"),
                "project-a",
                SDECorrectionRequest(
                    correction_id="api-correction-denied",
                    candidate_id=scenario.candidate_id,
                    correction="Unapproved correction",
                    rationale="The caller has no review grant",
                ),
            )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            scenario.api.sde_quality_feedback_record(
                AuthenticatedCaller("other-user"),
                "project-a",
                SDEQualityFeedbackRequest(
                    feedback_id="quality-feedback-denied",
                    candidate_id=scenario.candidate_id,
                    label=SDEQualityFeedbackLabel.NOT_USEFUL,
                ),
            )




















if __name__ == "__main__":
    unittest.main()
