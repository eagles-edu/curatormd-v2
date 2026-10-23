"""Authorization and request-budget tests for the API facade."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime, timedelta
from dataclasses import replace
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
    ProjectRegistrationRequest,
    RateLimitExceeded,
    ReacquisitionAction,
    ReviewDecision,
    RetentionHoldKind,
    SDEQualityFeedbackLabel,
    SuccessCriterion,
)
from curatormd_v2.content_safety import SensitiveContentError
from curatormd_v2.project_config import ProjectConfigError
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

    def test_default_authorizer_fails_closed(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin})
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list(self.caller, "project-a")

    def test_invalid_utf8_request_does_not_retain_raw_source_in_exception(self) -> None:
        """The API boundary must not chain an encoder error containing input."""

        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)
        with self.assertRaisesRegex(ValueError, "valid UTF-8") as raised:
            api.process_event_json(
                self.caller, "project-a", "PRIVATE_EVENT_CANARY\ud800"
            )
        self.assertNotIn("PRIVATE_EVENT_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

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
        plugin = ProjectPlugin.bind(
            self.plugin.config, self.store, TestVerifier(self.store)
        )
        api = AuthenticatedCuratorAPI({"project-a": plugin}, self.authorizer)
        goal = plugin.service.goal_start(
            "Persist a reviewed, compact goal record",
            (SuccessCriterion("verified", "The goal remains evidence-linked"),),
        )
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:verified",
            hashlib.sha256(b"proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        plugin.service.goal_fact(
            goal.goal_id,
            FactKind.VERIFICATION,
            "The bounded persistence check passed",
            criterion_id="verified",
            evidence=(evidence,),
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
        assert health.operational_counts is not None
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
        self.assertTrue(health.database_observation_complete)
        assert health.database_observed_at is not None
        self.assertIsNotNone(
            datetime.fromisoformat(health.database_observed_at).tzinfo
        )
        self.assertIsNotNone(health.staging_observed_at)
        self.assertTrue(
            all(item.observed_at is not None for item in health.dependencies)
        )
        self.assertTrue(all(item.status.value == "healthy" for item in health.dependencies))

    def test_project_health_reports_unknown_when_database_snapshot_fails(self) -> None:
        """A failed aggregate read must not be rendered as zero-valued health."""

        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        with patch.object(
            self.plugin,
            "operational_health_inputs",
            side_effect=sqlite3.OperationalError("database read failed"),
        ):
            health = api.project_health(self.caller, "project-a")
            metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self.assertEqual(health.status.value, "unknown")
        self.assertFalse(health.database_observation_complete)
        self.assertIsNone(health.database_observed_at)
        self.assertIsNone(health.event_received_count)
        self.assertIsNone(health.operational_counts)
        self.assertIsNone(health.event_capacity_available)
        self.assertIn("database_observation_failed", health.gate_codes)
        self.assertIn(
            'curatormd_database_observation_complete{project_id="project-a"} 0',
            metrics,
        )
        self.assertIn(
            'curatormd_project_health_state{project_id="project-a",'
            'state="unknown"} 1',
            metrics,
        )
        self.assertNotIn("curatormd_event_queue_received", metrics)
        self.assertNotIn("curatormd_facts{", metrics)

    def test_project_health_requires_storage_and_alert_delivery_observations(self) -> None:
        """Missing storage or alert observations cannot leave local health green."""

        for dependency in ("database_storage_adapter", "alert_delivery"):
            with self.subTest(dependency=dependency):
                readiness = DependencyReadiness(
                    {
                        name: True
                        for name in REQUIRED_HEALTH_DEPENDENCIES
                        if name != dependency
                    }
                )
                api = AuthenticatedCuratorAPI(
                    {"project-a": self.plugin},
                    self.authorizer,
                    dependency_readiness=readiness,
                )

                health = api.project_health(self.caller, "project-a")
                metrics = api.project_prometheus_metrics(self.caller, "project-a")

                self.assertEqual(health.status.value, "unknown")
                self.assertIn(f"dependency_unknown:{dependency}", health.gate_codes)
                self.assertTrue(
                    all(
                        item.status.value
                        == ("unknown" if item.name == dependency else "healthy")
                        for item in health.dependencies
                    )
                )
                self.assertIn(
                    'curatormd_project_health_state{project_id="project-a",'
                    'state="unknown"} 1',
                    metrics,
                )
                self.assertIn(
                    f'curatormd_dependency_readiness{{project_id="project-a",'
                    f'dependency="{dependency}",state="unknown"}} 1',
                    metrics,
                )

                failed_values: dict[str, bool | None] = {
                    name: True for name in REQUIRED_HEALTH_DEPENDENCIES
                }
                failed_values[dependency] = False
                failed_api = AuthenticatedCuratorAPI(
                    {"project-a": self.plugin},
                    self.authorizer,
                    dependency_readiness=DependencyReadiness(failed_values),
                )
                failed_health = failed_api.project_health(self.caller, "project-a")
                failed_metrics = failed_api.project_prometheus_metrics(
                    self.caller, "project-a"
                )
                self.assertEqual(failed_health.status.value, "degraded")
                self.assertIn(
                    f"dependency_unavailable:{dependency}", failed_health.gate_codes
                )
                self.assertIn(
                    f'curatormd_dependency_readiness{{project_id="project-a",'
                    f'dependency="{dependency}",state="degraded"}} 1',
                    failed_metrics,
                )

    def test_project_health_degrades_while_event_is_pending(self) -> None:
        """Do not report green while a received event has not been processed."""

        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        event = EventEnvelope(
            "health-pending-event",
            "project-a",
            GoalStarted(
                "health-pending-goal",
                "Keep the event backlog visible",
                (SuccessCriterion("done", "The event is processed"),),
            ),
        )
        self.store.ingest_event(event)

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertIn("event_backlog", health.gate_codes)
        self.assertEqual(health.event_received_count, 1)

    def test_project_health_degrades_while_event_payload_scrub_is_pending(self) -> None:
        """Keep a blocked privacy scrub visible in project readiness."""

        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        event = EventEnvelope(
            "health-scrub-event",
            "project-a",
            GoalStarted(
                "health-scrub-goal",
                "A scrub remains pending",
                (SuccessCriterion("scrubbed", "WAL remnants are scrubbed"),),
            ),
        )
        self.store.ingest_event(event)
        reader = sqlite3.connect(self.store.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        reader.execute(
            "SELECT payload_json FROM event_inbox WHERE event_id = ?",
            ("health-scrub-event",),
        ).fetchone()
        self.store.mark_event_processed("project-a", "health-scrub-event")

        health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertIn("sqlite_payload_scrub_pending", health.gate_codes)

    def test_project_health_degrades_when_staging_inventory_is_incomplete(self) -> None:
        """Do not report green when bounded traversal cannot complete inventory."""

        staging = self.root / ".curatormd-v2" / "staging"
        (staging / "one.bin").write_bytes(b"one")
        (staging / "two.bin").write_bytes(b"two")
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )

        with patch("curatormd_v2.project_plugin.MAX_STAGING_SCAN_ENTRIES", 1):
            health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)

    def test_project_health_accounts_for_staging_root_adapter_failure(self) -> None:
        """Keep health readable and degraded when the staging root cannot open."""

        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )
        with patch.object(
            self.plugin,
            "_locked_staging_root",
            side_effect=ProjectConfigError("staging root cannot be opened safely"),
        ):
            health = api.project_health(self.caller, "project-a")
            metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)
        self.assertIn("staging_adapter_unavailable", health.gate_codes)
        self.assertIn(
            'curatormd_project_open_gate{project_id="project-a",'
            'gate="staging_adapter_unavailable"} 1',
            metrics,
        )

    def test_project_health_degrades_for_known_failure_or_local_backlog(self) -> None:
        readiness = DependencyReadiness(
            {
                "event_router": True,
                "purge_scheduler": False,
                "database_storage_adapter": True,
                "host_identity": True,
                "human_review": True,
                "alert_delivery": True,
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
        api, problem, config_path, config_text = self._prepare_project_metrics_fixture()
        metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self._assert_project_metrics_content_free(metrics, problem)
        self._assert_project_metrics_format(metrics)
        self._assert_project_staging_budget_metrics(config_path, config_text)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_prometheus_metrics(AuthenticatedCaller("other-user"), "project-a")

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

        # EvidenceVerifier test double implements only `attest`.
        class BrokenVerifier:  # pylint: disable=too-few-public-methods
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
        self.store.record_staging_artifact_time(
            "project-a",
            ArtifactRef(
                "usage-goal/import/artifact.json",
                "e" * 64,
                device_id=1,
                inode_id=2,
                occurrence_id="a" * 32,
            ),
        )
        event = EventEnvelope(
            "usage-event-1",
            "project-a",
            GoalStarted(
                "usage-goal-1",
                "Measure project storage",
                (SuccessCriterion("measured", "Usage can be queried"),),
            ),
            source_id="storage-usage-source",
            source_sequence=1,
        )
        api.process_event_json(self.caller, "project-a", event.to_json())

        usage = api.project_storage_usage(self.caller, "project-a")
        self.assertEqual(usage.project_id, "project-a")
        self.assertEqual(usage.goal_count, 1)
        self.assertEqual(usage.event_receipt_count, 1)
        self.assertEqual(usage.event_cursor_count, 1)
        self.assertGreater(usage.event_cursor_record_bytes, 0)
        self.assertEqual(usage.event_retry_audit_count, 0)
        self.assertEqual(usage.event_retry_audit_record_bytes, 0)
        self.assertEqual(usage.staging_artifact_time_count, 1)
        self.assertGreater(usage.staging_artifact_time_record_bytes, 0)
        self.assertEqual(usage.staging_artifact_occurrence_count, 1)
        self.assertGreater(usage.staging_artifact_occurrence_record_bytes, 0)
        self.assertEqual(usage.expiry_purge_receipt_count, 0)
        self.assertEqual(usage.expiry_purge_receipt_record_bytes, 0)
        self.assertEqual(usage.expiry_purge_target_count, 0)
        self.assertEqual(usage.expiry_purge_target_record_bytes, 0)
        self.assertEqual(usage.cleanup_authorization_count, 0)
        self.assertEqual(usage.cleanup_authorization_record_bytes, 0)
        self.assertGreaterEqual(usage.event_payload_scrub_count, 0)
        self.assertGreaterEqual(usage.event_payload_scrub_record_bytes, 0)
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
        gptmd_root = create_consumer_repo(self.root.parent / "gptmd-consumer")
        (gptmd_root / "docs" / "tasks.md").write_text(
            "- [ ] Add readiness endpoint\n", encoding="utf-8"
        )
        (gptmd_root / "persistence" / "HISTORY.md").write_text(
            "# History\n", encoding="utf-8"
        )
        config_path = gptmd_root / ".curatormd-v2.toml"
        config_text = (self.root / ".curatormd-v2.toml").read_text(
            encoding="utf-8"
        ).replace(
            'project_id = "project-a"', 'project_id = "gptmd"'
        ).replace(
            'tasks = "docs/tasks.md"',
            'tasks = "docs/tasks.md"\n            api-readiness = "docs/tasks.md"',
        )
        config_path.write_text(config_text, encoding="utf-8")
        config_path.chmod(0o600)
        config = ProjectConfig.load(gptmd_root)
        self.store.register_project(
            ProjectRegistrationRequest.from_project_config(
                config, "Register the published producer fixture"
            ),
            "test-admin",
        )
        plugin = ProjectPlugin.bind(config, self.store)
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
        secret = "github_pat_abcdefghijklmnopqrstuvwxyz123456"
        payload = (
            '{"schema_version":1,"event_id":"sensitive-event-1",'
            '"project_id":"project-a","source_id":"api-test",'
            '"source_sequence":1,"occurred_at":"2026-10-18T00:00:00Z",'
            '"event_type":"goal.started","payload":{"goal_id":"sensitive-goal",'
            f'"problem":"Example token {secret}",'
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
            ProjectConfig.load(self.root),
            self.store,
            TestVerifier(self.store),
            ReviewHost(),
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
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
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
        staged_evidence = EvidenceRef(
            "staging_artifact",
            str(staged),
            hashlib.sha256(staged.read_bytes()).hexdigest(),
            EvidenceOutcome.PASSED,
        )
        mapped_fact, _ = plugin.service.goal_fact(
            goal.goal_id,
            FactKind.RESEARCH,
            "Staged evidence source recorded",
            criterion_id="verified",
            evidence=(staged_evidence,),
        )
        displayed_packet = api.sde_review_packet(
            self.caller, "project-a", candidate.candidate_id
        )
        plugin.service.goal_fact(
            goal.goal_id,
            FactKind.RESEARCH,
            "A later fact changes the displayed dependency map",
            criterion_id="verified",
            evidence=(staged_evidence,),
        )
        with self.assertRaisesRegex(ConflictError, "dependency map changed"):
            api.sde_confirm(
                self.caller,
                "project-a",
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                displayed_packet.artifact_inventory.artifacts,
                artifact_inventory_complete=True,
                dependency_map_sha256=displayed_packet.dependency_map_sha256,
            )
        self.assertTrue(staged.exists())
        unrelated_dir = stage_root / unrelated_goal.goal_id
        unrelated_dir.mkdir()
        unrelated_staged = unrelated_dir / "cue.json"
        unrelated_staged.write_bytes(b'{"unrelated":true}')
        unmapped_staged = staged_dir / "unmapped.json"
        unmapped_staged.write_bytes(b'{"unmapped":true}')
        inventory = api.discover_artifact_inventory(
            self.caller, "project-a", goal.goal_id
        )
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.scope_goal_id, goal.goal_id)
        self.assertEqual(len(inventory.artifacts), 2)

        orphan = stage_root / "orphaned-goal" / "scratch" / "unbound.bin"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"orphaned temporary data")
        project_inventory = api.discover_project_artifact_inventory(
            self.caller, "project-a"
        )
        self.assertTrue(project_inventory.usage.inventory_complete)
        self.assertIsNone(project_inventory.scope_goal_id)
        self.assertEqual(len(project_inventory.artifacts), 4)
        self.assertIn(
            str(orphan), {item.path for item in project_inventory.artifacts}
        )
        expiry_inventory = api.discover_project_expiry_inventory(
            self.caller, "project-a"
        )
        self.assertFalse(expiry_inventory.inventory_complete)
        self.assertEqual(expiry_inventory.unknown_age_count, 4)
        self.assertEqual(expiry_inventory.eligible_artifacts, ())
        self.assertIsNone(expiry_inventory.manifest_sha256)

        read_only_api = AuthenticatedCuratorAPI(
            {"project-a": plugin},
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

        with self.assertRaisesRegex(ConflictError, "does not match current inventory"):
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
        completion_packet = api.sde_review_packet(
            self.caller,
            "project-a",
            candidate.candidate_id,
            tuple(
                replace(
                    item,
                    reacquisition_action=ReacquisitionAction.NOT_REQUIRED,
                )
                for item in inventory.artifacts
            ),
        )
        receipt = api.artifact_inventory_complete(
            self.caller,
            "project-a",
            receipt.receipt_id,
            completion_packet.review_artifacts,
            completion_packet.dependency_map_sha256,
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
            self.caller,
            "project-a",
            candidate.candidate_id,
            receipt.artifacts,
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
            tuple(sorted((str(staged), str(unmapped_staged)))),
        )
        self.assertEqual(len(packet.artifact_dependencies), 2)
        dependency = packet.artifact_dependencies[0]
        self.assertEqual(dependency.artifact.path, str(staged))
        self.assertEqual(
            dependency.binding.value,
            "path_and_digest_match_occurrence_unbound",
        )
        self.assertEqual(len(dependency.evidence_dependencies), 2)
        self.assertIn(
            mapped_fact.fact_id,
            {item.fact_id for item in dependency.evidence_dependencies},
        )
        self.assertTrue(
            all(item.criterion_id == "verified" for item in dependency.evidence_dependencies)
        )
        self.assertTrue(
            all(item.criterion_status == "verified" for item in dependency.evidence_dependencies)
        )
        unmapped_dependency = packet.artifact_dependencies[1]
        self.assertEqual(unmapped_dependency.artifact.path, str(unmapped_staged))
        self.assertEqual(unmapped_dependency.binding.value, "unmapped")
        self.assertEqual(unmapped_dependency.evidence_dependencies, ())
        self.assertEqual(len(packet.dependency_map_sha256), 64)
        cleanup_manifest = packet.artifact_inventory.manifest_sha256
        assert cleanup_manifest is not None
        api.authorize_artifact_cleanup(
            self.caller,
            "project-a",
            receipt.receipt_id,
            packet.review_artifacts,
            cleanup_manifest,
            packet.dependency_map_sha256,
            "persistence/HISTORY.md",
        )
        self.assertFalse(staged.exists())
        self.assertFalse(unmapped_staged.exists())
        self.assertTrue(unrelated_staged.exists())
        saved_receipt = self.store.get_receipt(receipt.receipt_id, "project-a")
        self.assertEqual(
            saved_receipt.cleanup_dependency_map_sha256,
            packet.dependency_map_sha256,
        )
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
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )

        api = AuthenticatedCuratorAPI({"project-a": plugin}, self.authorizer)
        candidate = api.sde_assess(
            self.caller,
            "project-a",
            goal.goal_id,
            Materiality.IMPLEMENTATION,
            "A verified change should be reviewable",
            (change.fact_id, verification.fact_id),
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
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
        review_health = api.project_health(self.caller, "project-a")
        assert review_health.operational_counts is not None
        self.assertEqual(review_health.operational_counts.pending_review_count, 1)
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
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )
        with self.assertRaisesRegex(EvidenceGateError, "supporting fact limit"):
            api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Oversized support is invalid",
                (verification.fact_id,) * 33,
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
            )

        self.assertIsNone(
            api.sde_assess(
                self.caller,
                "project-a",
                goal.goal_id,
                Materiality.ROUTINE,
                "Ordinary progress is not an SDE",
                (),
                impact="Observed in the bounded test scenario",
                retrieval_value="Useful for future maintenance review",
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
            impact="Observed in the bounded test scenario",
            retrieval_value="Useful for future maintenance review",
        )
        assert candidate is not None
        staged = plugin.stage_artifact(
            goal.goal_id, "scratch", "held-health-artifact", BytesIO(b"held")
        )
        held = ArtifactRef(
            staged.path, staged.sha256, RetentionHoldKind.LEGAL,
            staged.device_id, staged.inode_id, staged.occurrence_id,
            ReacquisitionAction.RETAIN_UNDER_HOLD,
        )

        hold_review_packet = api.sde_review_packet(
            self.caller,
            "project-a",
            candidate.candidate_id,
            (held,),
        )
        receipt = api.sde_confirm(
            self.caller,
            "project-a",
            candidate.candidate_id,
            ReviewDecision.APPROVED,
            (held,),
            artifact_inventory_complete=True,
            dependency_map_sha256=hold_review_packet.dependency_map_sha256,
            rationale="Keep the legal hold visible to operations",
        )

        self.assertEqual(receipt.purge_status.value, "purge_pending")
        health = api.project_health(self.caller, "project-a")
        self.assertEqual(health.status.value, "degraded")
        assert health.operational_counts is not None
        self.assertEqual(health.operational_counts.pending_purge_receipt_count, 1)
        self.assertEqual(health.operational_counts.pending_purge_artifact_count, 1)
        self.assertIn("purge_pending", health.gate_codes)
        self.assertIn("purge_artifacts_pending", health.gate_codes)
        self.assertIn("staged_artifacts_present", health.gate_codes)

    def test_project_health_reports_pending_expiry_receipt_and_targets(self) -> None:
        """A failed attended expiry purge must keep local health degraded."""

        artifact = ArtifactRef("expiry-goal/scratch/transient", "a" * 64)
        manifest = json.dumps(
            [(artifact.path, artifact.sha256, artifact.occurrence_id)],
            separators=(",", ":")
        )
        manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
        self.store.create_expiry_purge_receipt(
            "project-a",
            "hermes-user-1",
            manifest_sha256,
            (artifact,),
        )
        api = AuthenticatedCuratorAPI(
            {"project-a": self.plugin},
            self.authorizer,
            dependency_readiness=DependencyReadiness(
                {name: True for name in REQUIRED_HEALTH_DEPENDENCIES}
            ),
        )

        health = api.project_health(self.caller, "project-a")
        metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        assert health.operational_counts is not None
        self.assertEqual(
            health.operational_counts.pending_expiry_purge_receipt_count, 1
        )
        self.assertEqual(
            health.operational_counts.pending_expiry_purge_artifact_count, 1
        )
        self.assertIn("expiry_purge_pending", health.gate_codes)
        self.assertIn("expiry_purge_artifacts_pending", health.gate_codes)
        self.assertIn('curatormd_expiry_purge_receipts_pending{project_id="project-a"} 1', metrics)
        self.assertIn('curatormd_expiry_purge_artifacts_pending{project_id="project-a"} 1', metrics)


if __name__ == "__main__":
    unittest.main()
