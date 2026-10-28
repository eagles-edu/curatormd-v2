"""Health and metrics API regression tests."""

from __future__ import annotations

import errno
import fcntl

from test_api import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    DependencyReadiness,
    EventEnvelope,
    EventFailureCategory,
    EventInboxStatus,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    FactRecorded,
    GoalActivated,
    GoalStarted,
    GoalStatus,
    ProjectConfig,
    ProjectConfigError,
    ProjectPlugin,
    REQUIRED_HEALTH_DEPENDENCIES,
    SuccessCriterion,
    _ApiTestSupport,
    cast,
    datetime,
    hashlib,
    patch,
    sqlite3,
)


class ApiHealthMetricsTests(_ApiTestSupport):
    """Exercise apihealthmetrics behavior."""

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

    def test_project_repository_fingerprint_requires_project_read_access(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)

        self.assertEqual(
            api.project_repository_fingerprint(self.caller, "project-a"),
            self.plugin.config.repository_fingerprint,
        )
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.project_repository_fingerprint(
                AuthenticatedCaller("other-user"), "project-a"
            )


    def test_project_activity_separates_no_capture_from_unknown_readiness(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)

        before = api.project_activity_status(self.caller, "project-a")
        self.assertFalse(before.events_observed)
        self.assertEqual(before.event_receipt_count, 0)
        self.assertEqual(before.goal_count, 0)
        self.assertEqual(
            {item.status: item.count for item in before.goal_status_counts},
            {status: 0 for status in GoalStatus},
        )
        self.assertEqual(before.fact_count, 0)
        self.assertEqual(before.sde_candidate_count, 0)
        self.assertIsNone(before.last_event_received_at)
        self.assertIsNone(before.last_event_processed_at)
        self.assertEqual(
            api.project_health(self.caller, "project-a").status.value, "unknown"
        )
        ready_api = self._api_with_healthy_dependencies(self.plugin)
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
        self.assertEqual(
            {item.status: item.count for item in after.goal_status_counts},
            {
                status: int(status is GoalStatus.ACTIVE)
                for status in GoalStatus
            },
        )
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

        api = self._api_with_healthy_dependencies(self.plugin)
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

        api = self._api_with_healthy_dependencies(self.plugin)
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


    def test_retry_payload_text_is_not_exposed_in_project_metrics(self) -> None:
        """Aggregate failed-event metrics never include retained event text."""

        canary = "PRIVATE_RETRY_METRIC_CANARY"
        event = EventEnvelope(
            "metrics-retry-event",
            "project-a",
            GoalStarted(
                "metrics-retry-goal",
                f"Retry request detail {canary}",
                (SuccessCriterion("done", "Keep metrics content-free"),),
            ),
        )
        self.store.ingest_event(event)
        self.store.mark_event_failed(
            "project-a", event.event_id, "temporary_adapter_error"
        )

        metrics = self._api_with_healthy_dependencies(
            self.plugin
        ).project_prometheus_metrics(self.caller, "project-a")

        self.assertIn('curatormd_event_queue_failed{project_id="project-a"} 1', metrics)
        self.assertNotIn(canary, metrics)


    def test_project_health_degrades_while_event_payload_scrub_is_pending(self) -> None:
        """Keep a blocked privacy scrub visible in project readiness."""

        api = self._api_with_healthy_dependencies(self.plugin)
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
        api = self._api_with_healthy_dependencies(self.plugin)

        with patch("curatormd_v2.project_plugin_staging.MAX_STAGING_SCAN_ENTRIES", 1):
            health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)


    def test_project_health_accounts_for_staging_root_adapter_failure(self) -> None:
        """Keep health readable and degraded when the staging root cannot open."""

        api = self._api_with_healthy_dependencies(self.plugin)
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


    def test_project_health_accounts_for_staging_lock_failure_without_details(
        self,
    ) -> None:
        """A lock error degrades readiness without leaking its filesystem detail."""

        api = self._api_with_healthy_dependencies(self.plugin)
        private_path = "/srv/private/customer/staging-lock"
        with patch.object(
            self.plugin,
            "_locked_staging_root",
            side_effect=OSError(f"cannot lock {private_path}"),
        ):
            health = api.project_health(self.caller, "project-a")
            metrics = api.project_prometheus_metrics(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)
        self.assertIn("staging_adapter_unavailable", health.gate_codes)
        self.assertNotIn(private_path, repr(health))
        self.assertNotIn(private_path, metrics)
        self.assertIn(
            'curatormd_project_open_gate{project_id="project-a",'
            'gate="staging_adapter_unavailable"} 1',
            metrics,
        )


    def test_real_staging_lock_acquisition_failure_is_degraded_and_retryable(
        self,
    ) -> None:
        """An OS lock failure degrades health, releases the root, and permits retry."""

        api = self._api_with_healthy_dependencies(self.plugin)
        private_path = "/srv/private/customer/staging-lock"
        original_flock = fcntl.flock

        def fail_only_lock_acquisition(fd: int, operation: int) -> None:
            if operation == fcntl.LOCK_EX:
                raise OSError(errno.EIO, f"cannot lock {private_path}")
            original_flock(fd, operation)

        with patch(
            "curatormd_v2.project_plugin.fcntl.flock",
            side_effect=fail_only_lock_acquisition,
        ):
            health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)
        self.assertIn("staging_adapter_unavailable", health.gate_codes)
        self.assertNotIn(private_path, repr(health))

        retried = api.project_health(self.caller, "project-a")

        self.assertEqual(retried.status.value, "healthy")
        self.assertTrue(retried.staging_inventory_complete)
        self.assertNotIn("staging_adapter_unavailable", retried.gate_codes)


    def test_real_staging_root_open_failure_is_degraded_and_retryable(self) -> None:
        """An OS root-open failure degrades health without leaking its path."""

        api = self._api_with_healthy_dependencies(self.plugin)
        private_path = "/srv/private/customer/staging-root"

        with patch(
            "curatormd_v2.project_plugin.os.open",
            side_effect=PermissionError(f"cannot open {private_path}"),
        ):
            health = api.project_health(self.caller, "project-a")

        self.assertEqual(health.status.value, "degraded")
        self.assertFalse(health.staging_inventory_complete)
        self.assertIn("staging_inventory_incomplete", health.gate_codes)
        self.assertIn("staging_adapter_unavailable", health.gate_codes)
        self.assertNotIn(private_path, repr(health))

        retried = api.project_health(self.caller, "project-a")

        self.assertEqual(retried.status.value, "healthy")
        self.assertTrue(retried.staging_inventory_complete)
        self.assertNotIn("staging_adapter_unavailable", retried.gate_codes)


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


    def test_staging_budget_emits_warning_at_75_percent_but_not_below(self) -> None:
        _, _, config_path, config_text = self._prepare_project_metrics_fixture()
        config_path.write_text(
            config_text.replace("max_project_bytes = 4096", "max_project_bytes = 32"),
            encoding="utf-8",
        )
        warning_plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        warning_api = AuthenticatedCuratorAPI(
            {"project-a": warning_plugin}, self.authorizer
        )

        warning_health = warning_api.project_health(self.caller, "project-a")
        warning_metrics = warning_api.project_prometheus_metrics(
            self.caller, "project-a"
        )

        self.assertIn("staging_budget_warning", warning_health.gate_codes)
        self.assertNotIn("staging_budget_reached", warning_health.gate_codes)
        self.assertIn(
            'gate="staging_budget_warning"} 1', warning_metrics
        )
        config_path.write_text(
            config_text.replace("max_project_bytes = 4096", "max_project_bytes = 33"),
            encoding="utf-8",
        )
        below_warning_plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), self.store
        )
        below_warning_api = AuthenticatedCuratorAPI(
            {"project-a": below_warning_plugin}, self.authorizer
        )
        below_warning_health = below_warning_api.project_health(
            self.caller, "project-a"
        )
        self.assertNotIn("staging_budget_warning", below_warning_health.gate_codes)


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
