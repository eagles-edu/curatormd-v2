"""Authorization and request-budget tests for the API facade."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime, timedelta
import hashlib
from io import BytesIO
import tempfile
from typing import cast
import unittest

from evidence_fixtures import attest_test_evidence
from project_fixtures import create_consumer_repo

from curatormd_v2 import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
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
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    FactKind,
    FactCompactionProposal,
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
    RateLimitExceeded,
    ReviewDecision,
    RetentionHoldKind,
    SDEQualityFeedbackLabel,
    SuccessCriterion,
)
from curatormd_v2.content_safety import SensitiveContentError
from curatormd_v2.store import NotFoundError


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

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the exact proof locator used by API tests."""

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


class ApiFacadeTests(unittest.TestCase):
    """Prove authz, project binding, envelope validation, and rate limits."""

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
        self.plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        self.caller = AuthenticatedCaller("hermes-user-1")
        self.authorizer = AllowProject(
            {
                ("hermes-user-1", "project-a", ProjectAction.READ),
                ("hermes-user-1", "project-a", ProjectAction.WRITE),
            }
        )

    def test_default_authorizer_fails_closed(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin})
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list(self.caller, "project-a")

    def test_project_grants_are_exact_and_action_scoped(self) -> None:
        grants = [("hermes-user-1", "project-a", ProjectAction.READ)]
        authorizer = ProjectGrantAuthorizer(grants)
        grants.clear()
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, authorizer)

        self.assertEqual(api.goal_list(self.caller, "project-a"), ())
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list(AuthenticatedCaller("other-user"), "project-a")
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list(self.caller, "project-b")
        event = EventEnvelope(
            "unauthorized-write",
            "project-a",
            GoalStarted(
                "unauthorized-goal",
                "The read-only grant must not write",
                (SuccessCriterion("done", "The write remains denied"),),
            ),
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.process_event_json(self.caller, "project-a", event.to_json())
        with self.assertRaises(NotFoundError):
            self.store.event_receipt("project-a", event.event_id)

    def test_goal_list_page_is_bounded_compact_and_status_filtered(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            InMemoryTokenBucket(),
        )
        for index in range(3):
            event = EventEnvelope(
                event_id=f"goal-page-{index}",
                project_id="project-a",
                payload=GoalStarted(
                    goal_id=f"page-goal-{index}",
                    problem=f"Track page item {index}",
                    success_criteria=(
                        SuccessCriterion("done", "The item has current proof"),
                    ),
                    initial_status=(
                        GoalStatus.ACTIVE if index < 2 else GoalStatus.PLANNED
                    ),
                ),
            )
            api.process_event_json(self.caller, "project-a", event.to_json())

        first = api.goal_list_page(
            self.caller, "project-a", offset=0, limit=1
        )
        second = api.goal_list_page(
            self.caller,
            "project-a",
            offset=first.next_offset or 0,
            limit=1,
        )
        active = api.goal_list_page(
            self.caller,
            "project-a",
            offset=0,
            limit=10,
            statuses=(GoalStatus.ACTIVE,),
        )

        self.assertEqual(first.total, 3)
        self.assertEqual(first.next_offset, 1)
        self.assertEqual(second.next_offset, 2)
        self.assertEqual(active.total, 2)
        self.assertEqual(
            [card.goal_id for card in active.goals],
            ["page-goal-0", "page-goal-1"],
        )
        self.assertFalse(hasattr(first.goals[0], "facts"))
        with self.assertRaisesRegex(ValueError, "limit"):
            api.goal_list_page(self.caller, "project-a", limit=101)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list_page(AuthenticatedCaller("other-user"), "project-a")

    def test_legacy_unpaged_goal_list_fails_closed_over_100_records(self) -> None:
        parent = self.plugin.service.goal_start(
            "Parent for compatibility-boundary test",
            (SuccessCriterion("done", "The parent is verified"),),
            goal_id="compat-parent",
        )
        for index in range(101):
            self.plugin.service.goal_start(
                f"Compatibility goal {index}",
                (SuccessCriterion("done", "The result is verified"),),
                goal_id=f"compat-goal-{index:03d}",
                parent_goal_id=parent.goal_id,
            )

        with self.assertRaisesRegex(GoalListCapacityError, "goal_list_page"):
            self.plugin.goal_list()
        with self.assertRaisesRegex(GoalListCapacityError, "goal_children_page"):
            self.plugin.goal_children(parent.goal_id)

    def test_goal_children_page_is_compact_filtered_and_project_authorized(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            InMemoryTokenBucket(),
        )
        parent = self.plugin.service.goal_start(
            "Track child checklist work",
            (SuccessCriterion("done", "All child tasks are resolved"),),
            goal_id="child-page-parent",
        )
        for index, status in enumerate(
            (GoalStatus.ACTIVE, GoalStatus.PLANNED, GoalStatus.ACTIVE)
        ):
            self.plugin.service.goal_start(
                f"Child checklist item {index}",
                (SuccessCriterion("done", "The child has proof"),),
                goal_id=f"child-page-{index}",
                parent_goal_id=parent.goal_id,
                initial_status=status,
            )

        first = api.goal_children_page(
            self.caller, "project-a", parent.goal_id, offset=0, limit=1
        )
        second = api.goal_children_page(
            self.caller,
            "project-a",
            parent.goal_id,
            offset=first.next_offset or 0,
            limit=1,
        )
        planned = api.goal_children_page(
            self.caller,
            "project-a",
            parent.goal_id,
            offset=0,
            limit=10,
            statuses=(GoalStatus.PLANNED,),
        )

        self.assertEqual(first.total, 3)
        self.assertEqual(first.next_offset, 1)
        self.assertEqual(second.next_offset, 2)
        self.assertEqual(planned.total, 1)
        self.assertEqual(planned.goals[0].goal_id, "child-page-1")
        self.assertFalse(hasattr(first.goals[0], "facts"))
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_children_page(
                AuthenticatedCaller("other-user"), "project-a", parent.goal_id
            )

    def test_canonical_goal_projection_requires_reviewer_scope(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        goal = self.plugin.service.goal_start(
            "Persist a reviewed, compact goal record",
            (SuccessCriterion("verified", "The goal remains evidence-linked"),),
        )
        target = self.root / "persistence" / "HISTORY.md"

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.persist_goal(
                self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
            )
        self.assertEqual(target.read_text(), "# History\n")

        self.authorizer.grants.add(
            ("hermes-user-1", "project-a", ProjectAction.REVIEW)
        )
        api.persist_goal(
            self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
        )
        self.assertNotEqual(target.read_text(), "# History\n")

    def test_sde_review_packet_requires_review_scope_before_reading_details(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.sde_review_packet(
                self.caller, "project-a", "candidate-not-visible-to-reader"
            )

    def test_project_grants_reject_invalid_subject_or_project_ids(self) -> None:
        for subject_id, project_id in (("", "project-a"), ("user-a", "../other")):
            with self.subTest(subject_id=subject_id, project_id=project_id):
                with self.assertRaises(ValueError):
                    ProjectGrantAuthorizer(
                        [(subject_id, project_id, ProjectAction.READ)]
                    )
        with self.assertRaisesRegex(ValueError, "known ProjectAction"):
            ProjectGrantAuthorizer([("user-a", "project-a", "read")])

    def test_hold_release_requires_its_dedicated_project_action(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.release_artifact_hold(
                self.caller,
                "project-a",
                "receipt-not-reached",
                str(self.root / ".curatormd-v2" / "staging" / "held.json"),
                "The retention owner approved release",
            )

    def test_project_health_is_unknown_without_authoritative_host_probes(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "unknown")
        self.assertEqual(health.event_received_count, 0)
        self.assertEqual(health.operational_counts.pending_review_count, 0)
        self.assertIsNotNone(health.staging_inventory_complete)
        self.assertIn("dependency_unknown:event_router", health.gate_codes)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_health(AuthenticatedCaller("other-user"), "project-a")

    def test_project_activity_separates_no_capture_from_unknown_readiness(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)

        before = api.project_activity_status(self.caller, "project-a")
        self.assertFalse(before.events_observed)
        self.assertEqual(before.event_receipt_count, 0)
        self.assertEqual(before.goal_count, 0)
        self.assertEqual(before.fact_count, 0)
        self.assertEqual(before.sde_candidate_count, 0)
        self.assertIsNone(before.last_event_received_at)
        self.assertIsNone(before.last_event_processed_at)
        self.assertEqual(
            api.project_health(self.caller, "project-a").status.value, "unknown"
        )
        ready_api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        self.assertEqual(
            ready_api.project_health(self.caller, "project-a").status.value,
            "healthy",
        )
        ready_activity = ready_api.project_activity_status(self.caller, "project-a")
        self.assertFalse(ready_activity.events_observed)
        self.assertEqual(ready_activity.sde_candidate_count, 0)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_activity_status(AuthenticatedCaller("other-user"), "project-a")

        problem = "Never return this private task description"
        started = EventEnvelope(
            "activity-start",
            "project-a",
            GoalStarted(
                "activity-goal",
                problem,
                (SuccessCriterion("changed", "A compact change fact exists"),),
            ),
        )
        api.process_event_json(self.caller, "project-a", started.to_json())
        fact = EventEnvelope(
            "activity-fact",
            "project-a",
            FactRecorded(
                "activity-goal",
                "activity-fact-record",
                FactKind.CHANGE,
                "Recorded a compact implementation change",
            ),
        )
        api.process_event_json(self.caller, "project-a", fact.to_json())

        after = api.project_activity_status(self.caller, "project-a")
        self.assertTrue(after.events_observed)
        self.assertEqual(after.event_receipt_count, 2)
        self.assertEqual(after.processed_event_count, 2)
        self.assertEqual(after.goal_count, 1)
        self.assertEqual(after.fact_count, 1)
        self.assertEqual(after.sde_candidate_count, 0)
        self.assertEqual(after.pending_sde_count, 0)
        self.assertIsNotNone(after.last_event_received_at)
        self.assertIsNotNone(after.last_event_processed_at)
        self.assertNotIn(problem, str(after))
        self.assertNotIn("activity-goal", str(after))
        self.assertNotIn("activity-start", str(after))
        self.assertNotIn("activity-fact", str(after))

    def test_project_health_is_healthy_only_with_complete_positive_observations(self) -> None:
        readiness = DependencyReadiness(
            {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=readiness,
        )

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "healthy")
        self.assertEqual(health.gate_codes, ())
        self.assertTrue(health.event_capacity_available)
        self.assertTrue(health.staging_inventory_complete)
        self.assertTrue(all(item.status.value == "healthy" for item in health.dependencies))

    def test_project_health_degrades_for_known_failure_or_local_backlog(self) -> None:
        readiness = DependencyReadiness(
            {
                "event_router": True,
                "purge_scheduler": False,
                "host_identity": True,
                "human_review": True,
                "artifact_producer_inventory": True,
            }
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=readiness,
        )
        event = EventEnvelope(
            "health-event-failure",
            "project-a",
            GoalActivated("missing-goal", "Leave failed event visible", 1),
        )
        api.process_event_json(self.caller, "project-a", event.to_json())

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertEqual(health.event_failed_count, 1)
        self.assertIn("event_failures", health.gate_codes)
        self.assertIn("dependency_unavailable:purge_scheduler", health.gate_codes)

    def test_project_health_probe_exception_is_unknown_not_healthy(self) -> None:
        """A broken host probe must not yield misleading healthy status."""

        class BrokenProbe:  # pylint: disable=too-few-public-methods
            """Return a sanitized readiness failure for regression coverage."""

            def readiness(self, project_id: str) -> dict[str, object]:
                """Raise a private error that must not leak into health output."""

                del project_id
                raise RuntimeError("private host error")

        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=BrokenProbe(),
        )

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "unknown")
        self.assertIn("dependency_probe_failed", health.gate_codes)
        self.assertNotIn("private host error", str(health))

        class MalformedProbe:  # pylint: disable=too-few-public-methods
            """Return an invalid shape so health fails closed to unknown."""

            def readiness(self, project_id: str) -> dict[str, object]:
                """Return an invalid payload through the protocol test seam."""

                del project_id
                return cast(dict[str, object], None)

        malformed_api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=MalformedProbe(),
        )
        malformed_health = malformed_api.project_health(self.caller, "project-a")
        self.assertEqual(malformed_health.status.value, "unknown")
        self.assertIn("dependency_probe_failed", malformed_health.gate_codes)

    def test_project_metrics_are_authorized_bounded_and_content_free(self) -> None:
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
        api = AuthenticatedCuratorAPI(
            {"project-a": configured_plugin}, self.authorizer
        )

        metrics = api.project_prometheus_metrics(self.caller, "project-a")
        self.assertIn(
            'curatormd_project_health_state{project_id="project-a",state="degraded"} 1',
            metrics,
        )
        self.assertIn('curatormd_goals{project_id="project-a",status="active"} 1', metrics)
        self.assertIn('event_type="goal.started",status="processed"', metrics)
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
        self.assertNotIn(problem, metrics)
        self.assertNotIn("private artifact payload", metrics)
        self.assertNotIn("private-cue.json", metrics)
        self.assertNotIn("global_database_bytes", metrics)
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

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_prometheus_metrics(AuthenticatedCaller("other-user"), "project-a")

    def test_event_failure_metrics_classify_rejection_and_adapter_error_without_details(
        self,
    ) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        for goal_id, event_id in (
            ("rejected-goal", "rejected-goal-start"),
            ("adapter-goal", "adapter-goal-start"),
        ):
            api.process_event_json(
                self.caller,
                "project-a",
                EventEnvelope(
                    event_id,
                    "project-a",
                    GoalStarted(
                        goal_id,
                        "Private problem statement",
                        (SuccessCriterion("done", "The fact must be verified"),),
                    ),
                ).to_json(),
            )

        def verification_event(event_id: str, goal_id: str) -> EventEnvelope:
            evidence = EvidenceRef(
                "repository_test",
                "test-proof:private-locator",
                hashlib.sha256(b"private-proof").hexdigest(),
                EvidenceOutcome.PASSED,
            )
            return EventEnvelope(
                event_id,
                "project-a",
                FactRecorded(
                    goal_id,
                    f"fact-{event_id}",
                    FactKind.VERIFICATION,
                    "Private verification detail",
                    "done",
                    (evidence,),
                ),
            )

        rejected = api.process_event_json(
            self.caller,
            "project-a",
            verification_event("rejected-fact", "rejected-goal").to_json(),
        )
        self.assertEqual(rejected.status, EventInboxStatus.FAILED)
        self.assertEqual(rejected.last_error_code, "EvidenceGateError")

        class BrokenVerifier:
            """Simulate a trusted adapter that fails with sensitive details."""

            def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
                """Raise a secret-bearing failure to verify safe classification."""

                del evidence, context
                raise RuntimeError("secret resolver response")

        self.plugin.service.evidence_verifier = BrokenVerifier()
        adapter_failure = api.process_event_json(
            self.caller,
            "project-a",
            verification_event("adapter-fact", "adapter-goal").to_json(),
        )
        self.assertEqual(adapter_failure.status, EventInboxStatus.FAILED)
        self.assertEqual(adapter_failure.last_error_code, "EvidenceAdapterError")

        other_project_event = EventEnvelope(
            "other-project-adapter-failure",
            "project-b",
            GoalStarted(
                "other-project-goal",
                "Other project's private text",
                (SuccessCriterion("done", "This project remains isolated"),),
            ),
        )
        self.store.ingest_event(other_project_event)
        self.store.mark_event_failed(
            "project-b", other_project_event.event_id, "EvidenceAdapterError"
        )
        self.store.quarantine_event(
            "project-b", other_project_event.event_id, max_attempts=1
        )
        other_usage = self.store.project_storage_usage("project-b")
        other_failures = {item.category: item.count for item in other_usage.event_failures}
        self.assertEqual(other_failures[EventFailureCategory.EVIDENCE_ADAPTER_ERROR], 1)
        self.assertEqual(other_failures[EventFailureCategory.EVIDENCE_REJECTED], 0)

        metrics = api.project_prometheus_metrics(self.caller, "project-a")
        self.assertIn(
            'curatormd_event_failures{project_id="project-a",category="evidence_rejected"} 1',
            metrics,
        )
        self.assertIn(
            'curatormd_event_failures{project_id="project-a",category="evidence_adapter_error"} 1',
            metrics,
        )
        self.assertIn(
            'curatormd_event_failures{project_id="project-a",category="other"} 0',
            metrics,
        )
        self.assertNotIn("secret resolver response", metrics)
        self.assertNotIn("Private verification detail", metrics)
        self.assertNotIn("Other project's private text", metrics)

    def test_project_health_degrades_while_staging_contains_any_artifact(self) -> None:
        readiness = DependencyReadiness(
            {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=readiness,
        )
        staging_file = self.root / ".curatormd-v2" / "staging" / "unreviewed.json"
        staging_file.write_text("{}", encoding="utf-8")

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertEqual(health.staging_regular_file_count, 1)
        self.assertIn("staged_artifacts_present", health.gate_codes)

    def test_markdown_reconciliation_is_authorized_read_only_and_reports_drift(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        goal = self.plugin.service.goal_start(
            "Compare the canonical projection",
            (SuccessCriterion("reported", "Reconciliation reports current state"),),
        )
        target = self.root / "persistence" / "HISTORY.md"
        initial = target.read_text(encoding="utf-8")

        missing = api.reconcile_goal(
            self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
        )
        self.assertEqual(missing.status.value, "missing")
        self.assertEqual(target.read_text(encoding="utf-8"), initial)

        self.plugin.persist_goal(goal.goal_id, "persistence/HISTORY.md")
        synced = api.reconcile_goal(
            self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
        )
        self.assertEqual(synced.status.value, "synced")
        synced_content = target.read_text(encoding="utf-8")
        target.write_text(synced_content + "\nManual unrelated edit.\n", encoding="utf-8")
        edited_content = target.read_text(encoding="utf-8")
        unrelated_edit = api.reconcile_goal(
            self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
        )
        self.assertEqual(unrelated_edit.status.value, "synced")
        self.assertEqual(target.read_text(encoding="utf-8"), edited_content)

        edited_content = edited_content.replace(
            "- Problem: Compare the canonical projection",
            "- Problem: Manually edited projection",
            1,
        )
        target.write_text(edited_content, encoding="utf-8")

        divergent = api.reconcile_goal(
            self.caller, "project-a", goal.goal_id, "persistence/HISTORY.md"
        )
        self.assertEqual(divergent.status.value, "malformed")
        self.assertNotEqual(divergent.expected_sha256, divergent.actual_sha256)
        self.assertEqual(target.read_text(encoding="utf-8"), edited_content)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.reconcile_goal(
                AuthenticatedCaller("other-user"),
                "project-a",
                goal.goal_id,
                "persistence/HISTORY.md",
            )

    def test_project_reconciliation_is_read_authorized_and_paged(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        self.plugin.service.goal_start(
            "First project reconciliation row",
            (SuccessCriterion("visible", "A bounded page is returned"),),
        )
        self.plugin.service.goal_start(
            "Second project reconciliation row",
            (SuccessCriterion("visible", "Pagination is stable"),),
        )
        first = api.reconcile_project(
            self.caller, "project-a", "persistence/HISTORY.md", limit=1
        )
        self.assertEqual(first.total_goals, 2)
        self.assertEqual(len(first.goals), 1)
        self.assertEqual(first.next_offset, 1)
        second = api.reconcile_project(
            self.caller,
            "project-a",
            "persistence/HISTORY.md",
            offset=first.next_offset or 0,
            limit=1,
        )
        self.assertEqual(len(second.goals), 1)
        self.assertIsNone(second.next_offset)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.reconcile_project(
                AuthenticatedCaller("other-user"),
                "project-a",
                "persistence/HISTORY.md",
            )

    def test_project_health_treats_old_or_invalid_probe_time_as_unknown(self) -> None:
        stale = DependencyReadiness(
            {name: True for name in REQUIRED_HEALTH_DEPENDENCIES},
            (datetime.now(UTC) - timedelta(seconds=90)).isoformat(),
        )
        stale_api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=stale,
        )
        stale_health = stale_api.project_health(self.caller, "project-a")
        self.assertEqual(stale_health.status.value, "unknown")
        self.assertIn("dependency_probe_stale:event_router", stale_health.gate_codes)

        invalid = DependencyReadiness(
            {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}, "not-a-timestamp"
        )
        invalid_api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer,
            dependency_readiness=invalid,
        )
        invalid_health = invalid_api.project_health(self.caller, "project-a")
        self.assertEqual(invalid_health.status.value, "unknown")
        self.assertIn("dependency_probe_time_invalid:event_router", invalid_health.gate_codes)

    def test_project_usage_is_authorized_and_reports_processed_payload_discard(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)
        event = EventEnvelope(
            "usage-event-1",
            "project-a",
            GoalStarted(
                "usage-goal-1",
                "Measure project storage",
                (SuccessCriterion("measured", "Usage can be queried"),),
            ),
        )
        api.process_event_json(self.caller, "project-a", event.to_json())

        usage = api.project_storage_usage(self.caller, "project-a")
        self.assertEqual(usage.project_id, "project-a")
        self.assertEqual(usage.goal_count, 1)
        self.assertEqual(usage.event_receipt_count, 1)
        self.assertEqual(usage.global_event_inbox.receipt_count, 1)
        self.assertEqual(usage.global_event_inbox.receipt_count_limit, 250_000)
        self.assertTrue(usage.global_event_inbox.can_accept_new_event)
        self.assertEqual(usage.event_payload_bytes_retained, 0)
        self.assertGreater(usage.event_payload_bytes_received, 0)
        self.assertIsNotNone(usage.staging)
        assert usage.staging is not None
        self.assertEqual(usage.staging.classes, ())
        self.assertGreater(usage.logical_record_bytes, 0)
        self.assertEqual(usage.fact_count_limit, MAX_FACTS_PER_PROJECT)
        self.assertEqual(usage.fact_record_bytes_limit, MAX_FACT_BYTES_PER_PROJECT)
        self.assertFalse(usage.fact_capacity_reached)
        self.assertIsNotNone(usage.global_database_bytes)
        self.assertEqual(
            [(item.event_type, item.status) for item in usage.event_classes],
            [("goal.started", "processed")],
        )

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_storage_usage(AuthenticatedCaller("other-user"), "project-a")
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_storage_usage(self.caller, "unregistered-project")

    def test_event_ingress_authorizes_project_and_returns_durable_receipt(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        event = EventEnvelope(
            "api-event-1",
            "project-a",
            GoalStarted(
                "goal-api-1",
                "Record the API task",
                (SuccessCriterion("recorded", "Goal appears in project status"),),
            ),
        )
        receipt = api.process_event_json(
            self.caller, "project-a", event.to_json()
        )

        self.assertEqual(receipt.status.value, "processed")
        self.assertEqual(
            api.goal_status(self.caller, "project-a", "goal-api-1").goal.problem,
            "Record the API task",
        )

    def test_published_producer_fixture_runs_through_authenticated_backend(self) -> None:
        config_path = self.root / ".curatormd-v2.toml"
        config_text = config_path.read_text(encoding="utf-8").replace(
            'project_id = "project-a"', 'project_id = "gptmd"'
        ).replace(
            'tasks = "docs/tasks.md"',
            'tasks = "docs/tasks.md"\n            api-readiness = "docs/tasks.md"',
        )
        config_path.write_text(config_text, encoding="utf-8")
        (self.root / "docs" / "tasks.md").write_text(
            "- [ ] Add readiness endpoint\n", encoding="utf-8"
        )
        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        for goal_id in ("goal-api-modernization", "goal-health-contract"):
            plugin.service.goal_start(
                f"Prerequisite {goal_id}",
                (SuccessCriterion("ready", "The referenced goal exists"),),
                goal_id=goal_id,
            )
        authorizer = ProjectGrantAuthorizer(
            {
                ("hermes-user-1", "gptmd", ProjectAction.READ),
                ("hermes-user-1", "gptmd", ProjectAction.WRITE),
            }
        )
        api = AuthenticatedCuratorAPI({"gptmd": plugin}, authorizer)
        fixture_path = (
            Path(__file__).resolve().parents[1]
            / "docs/examples/event-v1-goal-started.json"
        )
        producer_event_json = fixture_path.read_text(encoding="utf-8")

        accepted = api.process_event_json(
            self.caller, "gptmd", producer_event_json
        )
        replay = api.process_event_json(self.caller, "gptmd", producer_event_json)
        goal = api.goal_status(self.caller, "gptmd", "goal-readyz-001").goal
        usage = api.project_storage_usage(self.caller, "gptmd")

        self.assertEqual(accepted.status, EventInboxStatus.PROCESSED)
        self.assertEqual(accepted.project_id, "gptmd")
        self.assertEqual(accepted.event_id, "evt-gptmd-readyz-001")
        self.assertEqual(replay, accepted)
        self.assertEqual(goal.project_id, "gptmd")
        self.assertEqual(goal.status.value, "planned")
        self.assertEqual(goal.problem, "Add the readiness route")
        self.assertEqual(usage.goal_count, 3)
        self.assertEqual(usage.event_receipt_count, 1)
        self.assertGreater(usage.event_payload_bytes_received, 0)
        self.assertEqual(usage.event_payload_bytes_retained, 0)

    def test_quarantine_retry_requires_event_retry_scope_and_audits_identity(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        event = EventEnvelope(
            "api-quarantined-event",
            "project-a",
            GoalActivated("api-missing-goal", "Retry after repair", 1),
        )
        failed = api.process_event_json(self.caller, "project-a", event.to_json())
        self.assertEqual(failed.status, EventInboxStatus.FAILED)
        quarantined = self.store.quarantine_event(
            "project-a", event.event_id, max_attempts=1
        )
        self.assertEqual(quarantined.status, EventInboxStatus.QUARANTINED)

        status = api.event_queue_status(self.caller, "project-a")
        self.assertEqual(status.quarantined_count, 1)
        self.assertEqual(status.claimed_count, 0)
        self.assertEqual(status.expired_claim_count, 0)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.retry_quarantined_event(
                self.caller, "project-a", event.event_id
            )

        self.authorizer.grants.add(
            ("hermes-user-1", "project-a", ProjectAction.EVENT_RETRY)
        )
        retried = api.retry_quarantined_event(
            self.caller, "project-a", event.event_id
        )
        self.assertEqual(retried.status, EventInboxStatus.FAILED)
        with self.store.transaction() as connection:
            audit = connection.execute(
                "SELECT actor_id FROM event_retry_audit "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", event.event_id),
            ).fetchone()
        self.assertEqual(audit["actor_id"], self.caller.subject_id)

    def test_fact_archive_approval_requires_review_scope_and_binds_reviewer(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        goal = self.plugin.service.goal_start(
            "Archive routine facts through the API",
            (SuccessCriterion("done", "Routine fact remains retrievable"),),
        )
        fact, _ = self.plugin.service.goal_fact(
            goal.goal_id, FactKind.RESEARCH, "Reviewed the source fact"
        )
        proposal = api.fact_compaction_propose(
            self.caller, "project-a", goal.goal_id
        )
        self.assertIsInstance(proposal, FactCompactionProposal)

        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.fact_compaction_approve(
                self.caller,
                "project-a",
                proposal.compaction_id,
                goal.goal_id,
                (fact.fact_id,),
                proposal.source_sha256,
                "Approval is required",
            )
        self.authorizer.grants.add(
            ("hermes-user-1", "project-a", ProjectAction.REVIEW)
        )
        receipt = api.fact_compaction_approve(
            self.caller,
            "project-a",
            proposal.compaction_id,
            goal.goal_id,
            (fact.fact_id,),
            proposal.source_sha256,
            "Approved the reviewed routine fact",
        )
        self.assertEqual(receipt.reviewer_id, self.caller.subject_id)
        self.assertEqual(receipt.fact_ids, (fact.fact_id,))
        self.assertEqual(
            api.fact_archive_receipts(self.caller, "project-a", goal.goal_id),
            (receipt,),
        )

    def test_sensitive_event_is_rejected_before_any_inbox_or_goal_write(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        secret = "sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        payload = (
            '{"schema_version":1,"event_id":"sensitive-event-1",'
            '"project_id":"project-a","source_id":"api-test",'
            '"source_sequence":1,"occurred_at":"2026-10-18T00:00:00Z",'
            '"event_type":"goal.started","payload":{"goal_id":"sensitive-goal",'
            f'"problem":"api_key={secret}",'
            '"success_criteria":[{"criterion_id":"done",'
            '"description":"The task is complete"}]}}'
        )
        with self.assertRaises(SensitiveContentError) as caught:
            api.process_event_json(self.caller, "project-a", payload)
        self.assertNotIn(secret, str(caught.exception))
        with self.assertRaises(NotFoundError):
            self.store.event_receipt("project-a", "sensitive-event-1")
        with self.assertRaises(NotFoundError):
            self.store.get_goal("sensitive-goal", "project-a")

        metrics = api.project_prometheus_metrics(self.caller, "project-a")
        self.assertNotIn(secret, metrics)

        secret_bytes = secret.encode("utf-8")
        database_path = Path(self.store.database)
        for path in (
            database_path,
            Path(f"{database_path}-wal"),
            Path(f"{database_path}-shm"),
        ):
            if path.exists():
                self.assertNotIn(secret_bytes, path.read_bytes(), str(path))
        history = (self.root / "persistence" / "HISTORY.md").read_bytes()
        self.assertNotIn(secret_bytes, history)

        backup_path = self.root.parent / "sensitive-rejection-backup.sqlite3"
        backup_database(self.store.database, backup_path)
        self.assertNotIn(secret_bytes, backup_path.read_bytes())

    def test_event_project_mismatch_and_unknown_projects_are_denied(self) -> None:
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer
        )
        event = EventEnvelope(
            "wrong-project-event",
            "project-b",
            GoalStarted(
                "goal-b",
                "Wrong project",
                (SuccessCriterion("done", "Task is done"),),
            ),
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.process_event_json(self.caller, "project-b", event.to_json())
        with self.assertRaisesRegex(PermissionError, "does not match"):
            api.process_event_json(self.caller, "project-a", event.to_json())

    def test_rate_limit_is_per_subject_and_project_and_refills(self) -> None:
        current_time = [0.0]
        limiter = InMemoryTokenBucket(
            capacity=1,
            refill_period_seconds=10,
            clock=lambda: current_time[0],
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin}, self.authorizer, limiter
        )
        self.assertEqual(api.goal_list(self.caller, "project-a"), ())
        with self.assertRaises(RateLimitExceeded):
            api.goal_list(self.caller, "project-a")
        current_time[0] = 10.0
        self.assertEqual(api.goal_list(self.caller, "project-a"), ())

    def test_review_receipt_binds_to_the_api_authenticated_subject(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        goal = plugin.service.goal_start(
            "Implement a verified change",
            (SuccessCriterion("verified", "Verification passes"),),
        )
        change, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Implemented the change"
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
            "Verification passed",
            criterion_id="verified",
            evidence=(evidence,),
        )
        candidate = plugin.service.sde_assess(
            goal.goal_id,
            Materiality.IMPLEMENTATION,
            "A durable change has passing evidence",
            (change.fact_id, verification.fact_id),
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
        stage_root = self.root / ".curatormd-v2" / "staging"
        staged_dir = stage_root / goal.goal_id
        staged_dir.mkdir()
        staged = staged_dir / "cue.json"
        staged.write_bytes(b'{"temporary":true}')
        unrelated_dir = stage_root / unrelated_goal.goal_id
        unrelated_dir.mkdir()
        unrelated_staged = unrelated_dir / "cue.json"
        unrelated_staged.write_bytes(b'{"unrelated":true}')
        inventory = api.discover_artifact_inventory(
            self.caller, "project-a", goal.goal_id
        )
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.scope_goal_id, goal.goal_id)
        self.assertEqual(len(inventory.artifacts), 1)
        with self.assertRaisesRegex(ConflictError, "does not match current staging"):
            api.sde_confirm(
                self.caller,
                "project-a",
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                (),
                artifact_inventory_complete=True,
            )

        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (),
            artifact_inventory_complete=False,
        )
        receipt = api.artifact_inventory_complete(
            self.caller,
            "project-a",
            receipt.receipt_id,
            inventory.artifacts,
        )

        self.assertEqual(receipt.reviewer_id, self.caller.subject_id)
        self.assertTrue(receipt.artifact_inventory_complete)
        correction = api.sde_correction_record(
            self.caller,
            "project-a",
            "api-correction-1",
            candidate.candidate_id,
            "Narrow the outcome claim",
            "The evidence proves a passing test, not a production impact",
        )
        detail = api.sde_review_detail(
            self.caller, "project-a", candidate.candidate_id
        )
        packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )

        self.assertEqual(correction.reviewer_id, self.caller.subject_id)
        self.assertEqual(detail.corrections, (correction,))
        self.assertEqual(
            packet.detail.candidate.candidate_id, candidate.candidate_id
        )
        self.assertEqual(packet.detail.candidate.status.value, "approved")
        self.assertEqual(packet.detail.corrections, (correction,))
        self.assertTrue(packet.artifact_inventory.usage.inventory_complete)
        self.assertEqual(packet.artifact_inventory.scope_goal_id, goal.goal_id)
        self.assertEqual(
            tuple(item.path for item in packet.artifact_inventory.artifacts),
            (str(staged),),
        )
        api.persist_goal(
            self.caller,
            "project-a",
            goal.goal_id,
            "persistence/HISTORY.md",
        )
        self.assertFalse(staged.exists())
        self.assertTrue(unrelated_staged.exists())
        saved_receipt = self.store.get_receipt(receipt.receipt_id, "project-a")
        feedback = api.sde_quality_feedback_record(
            self.caller,
            "project-a",
            "quality-feedback-1",
            candidate.candidate_id,
            SDEQualityFeedbackLabel.USEFUL,
            "The proposed event captured the material implementation facts",
        )
        replayed_feedback = api.sde_quality_feedback_record(
            self.caller,
            "project-a",
            "quality-feedback-1",
            candidate.candidate_id,
            SDEQualityFeedbackLabel.USEFUL,
            "The proposed event captured the material implementation facts",
        )
        feedback_summary = api.sde_quality_feedback_summary(
            self.caller, "project-a"
        )
        self.assertEqual(feedback, replayed_feedback)
        self.assertEqual(feedback.reviewer_id, self.caller.subject_id)
        self.assertEqual(feedback_summary.total, 1)
        self.assertEqual(feedback_summary.counts[0][1], 1)
        metrics = api.project_prometheus_metrics(self.caller, "project-a")
        self.assertIn(
            'curatormd_sde_reviewer_feedback_total{project_id="project-a",label="useful"} 1',
            metrics,
        )
        self.assertNotIn("hermes-user-1", metrics)
        self.assertNotIn("implementation facts", metrics)
        with self.assertRaisesRegex(ConflictError, "already submitted feedback"):
            api.sde_quality_feedback_record(
                self.caller,
                "project-a",
                "quality-feedback-2",
                candidate.candidate_id,
                SDEQualityFeedbackLabel.NOT_USEFUL,
            )
        usage = api.project_storage_usage(self.caller, "project-a")
        self.assertEqual(usage.sde_correction_count, 1)
        self.assertGreater(usage.sde_correction_record_bytes, 0)
        self.assertEqual(usage.sde_quality_feedback_count, 1)
        self.assertGreater(usage.sde_quality_feedback_record_bytes, 0)
        self.assertEqual(
            self.store.get_receipt(receipt.receipt_id, "project-a"), saved_receipt
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.sde_correction_record(
                AuthenticatedCaller("other-user"),
                "project-a",
                "api-correction-denied",
                candidate.candidate_id,
                "Unapproved correction",
                "The caller has no review grant",
            )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.sde_quality_feedback_record(
                AuthenticatedCaller("other-user"),
                "project-a",
                "quality-feedback-denied",
                candidate.candidate_id,
                SDEQualityFeedbackLabel.NOT_USEFUL,
            )

    def test_sde_assessment_requires_write_scope_and_verified_goal_facts(self) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier()
        )
        goal = plugin.service.goal_start(
            "Assess a verified implementation",
            (SuccessCriterion("verified", "Verification evidence passes"),),
        )
        change, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Implemented the scoped change"
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
            "The scoped verification passed",
            criterion_id="verified",
            evidence=(evidence,),
        )
        read_only = AllowProject(
            {("hermes-user-1", "project-a", ProjectAction.READ)}
        )
        read_api = AuthenticatedCuratorAPI({"project-a": plugin}, read_only)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            read_api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "A verified change should be reviewable",
                (change.fact_id, verification.fact_id),
            )

        api = AuthenticatedCuratorAPI({"project-a": plugin}, self.authorizer)
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            goal.goal_id,
            Materiality.IMPLEMENTATION,
            "A verified change should be reviewable",
            (change.fact_id, verification.fact_id),
        )
        assert candidate is not None
        self.assertEqual(candidate.status.value, "pending_review")
        self.assertEqual(candidate.fact_ids, (change.fact_id, verification.fact_id))
        activity = api.project_activity_status(self.caller, "project-a")
        self.assertEqual(activity.sde_candidate_count, 1)
        self.assertEqual(activity.pending_sde_count, 1)
        self.assertEqual(activity.approved_sde_count, 0)
        self.assertEqual(activity.rejected_sde_count, 0)
        self.assertEqual(
            tuple(item.candidate.candidate_id for item in api.sde_review_queue(
                self.caller, "project-a"
            )),
            (candidate.candidate_id,),
        )
        self.assertEqual(
            api.project_health(self.caller, "project-a")
            .operational_counts.pending_review_count,
            1,
        )
        fully_probed_api = AuthenticatedCuratorAPI(
            {"project-a": plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        review_health = fully_probed_api.project_health(self.caller, "project-a")
        self.assertEqual(review_health.status.value, "degraded")
        self.assertIn("review_backlog", review_health.gate_codes)
        with self.assertRaisesRegex(EvidenceGateError, "fact IDs must be unique"):
            api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Repeated support is invalid",
                (verification.fact_id, verification.fact_id),
            )
        with self.assertRaisesRegex(EvidenceGateError, "supporting fact limit"):
            api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Oversized support is invalid",
                (verification.fact_id,) * 33,
            )

        self.assertIsNone(
            api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.ROUTINE,
                "Ordinary progress is not an SDE",
                (),
            )
        )

    def test_project_health_reports_held_purge_receipt_and_artifact_as_required_work(
        self,
    ) -> None:
        plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store, TestVerifier(), ReviewHost()
        )
        goal = plugin.service.goal_start(
            "Keep an approved held artifact visible to operations",
            (SuccessCriterion("verified", "Verification evidence passes"),),
        )
        change, _ = plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Implemented the scoped change"
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
            "The scoped verification passed",
            criterion_id="verified",
            evidence=(evidence,),
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": plugin},
            AllowProject(
                {
                    ("hermes-user-1", "project-a", ProjectAction.READ),
                    ("hermes-user-1", "project-a", ProjectAction.WRITE),
                    ("hermes-user-1", "project-a", ProjectAction.REVIEW),
                }
            ),
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            goal.goal_id,
            Materiality.IMPLEMENTATION,
            "A verified change should be reviewable",
            (change.fact_id, verification.fact_id),
        )
        assert candidate is not None
        staged = plugin.stage_artifact(
            goal.goal_id, "scratch", "held-health-artifact", BytesIO(b"held")
        )
        held = ArtifactRef(staged.path, staged.sha256, RetentionHoldKind.LEGAL)

        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (held,),
            artifact_inventory_complete=True,
            rationale="Keep the legal hold visible to operations",
        )

        self.assertEqual(receipt.purge_status.value, "purge_pending")
        health = api.project_health(self.caller, "project-a")
        self.assertEqual(health.status.value, "degraded")
        self.assertEqual(health.operational_counts.pending_purge_receipt_count, 1)
        self.assertEqual(health.operational_counts.pending_purge_artifact_count, 1)
        self.assertIn("purge_pending", health.gate_codes)
        self.assertIn("purge_artifacts_pending", health.gate_codes)
        self.assertIn("staged_artifacts_present", health.gate_codes)


if __name__ == "__main__":
    unittest.main()
