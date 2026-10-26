"""Evidence and event ingress API regression tests."""

from __future__ import annotations

from test_api import (
    ArtifactRef,
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    DependencyReadiness,
    EventEnvelope,
    EventInboxStatus,
    FactCompactionApprovalRequest,
    FactCompactionProposal,
    FactKind,
    GoalActivated,
    GoalStarted,
    InMemoryTokenBucket,
    MAX_FACTS_PER_PROJECT,
    MAX_FACT_BYTES_PER_PROJECT,
    NotFoundError,
    Path,
    ProjectAction,
    ProjectConfig,
    ProjectGrantAuthorizer,
    ProjectPlugin,
    ProjectRegistrationRequest,
    REQUIRED_HEALTH_DEPENDENCIES,
    RateLimitExceeded,
    SensitiveContentError,
    SuccessCriterion,
    UTC,
    _ApiTestSupport,
    create_consumer_repo,
    datetime,
    timedelta,
)


class ApiEvidenceIngressTests(_ApiTestSupport):
    """Exercise apievidenceingress behavior."""

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
                FactCompactionApprovalRequest(
                    compaction_id=proposal.compaction_id,
                    goal_id=goal.goal_id,
                    project_id="untrusted-project-value",
                    fact_ids=(fact.fact_id,),
                    source_sha256=proposal.source_sha256,
                    reviewer_id="spoofed-reviewer",
                    approval_reason="Approval is required",
                ),
            )
        self.authorizer.grants.add(
            ("hermes-user-1", "project-a", ProjectAction.REVIEW)
        )
        receipt = api.fact_compaction_approve(
            self.caller,
            "project-a",
            FactCompactionApprovalRequest(
                compaction_id=proposal.compaction_id,
                goal_id=goal.goal_id,
                project_id="untrusted-project-value",
                fact_ids=(fact.fact_id,),
                source_sha256=proposal.source_sha256,
                reviewer_id="spoofed-reviewer",
                approval_reason="Approved the reviewed routine fact",
            ),
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
        secrets = (
            (
                "sensitive-event-1",
                "sensitive-goal-1",
                "Example token github_pat_abcdefghijklmnopqrstuvwxyz123456",
                "provider_token",
            ),
            (
                "sensitive-event-dns",
                "sensitive-goal-dns",
                "TXT value: " + "A" * 43,
                "dns_challenge",
            ),
        )
        for event_id, goal_id, sensitive_text, category in secrets:
            payload = (
                '{"schema_version":1,"event_id":'
                f'"{event_id}","project_id":"project-a",'
                '"source_id":"api-test","source_sequence":1,'
                '"occurred_at":"2026-10-18T00:00:00Z",'
                '"event_type":"goal.started","payload":{"goal_id":'
                f'"{goal_id}","problem":"{sensitive_text}",'
                '"success_criteria":[{"criterion_id":"done",'
                '"description":"The task is complete"}]}}'
            )
            with self.subTest(category=category):
                with self.assertRaises(SensitiveContentError) as caught:
                    api.process_event_json(self.caller, "project-a", payload)
                self.assertEqual(caught.exception.category, category)
                self.assertNotIn(sensitive_text, str(caught.exception))
            with self.assertRaises(NotFoundError):
                self.store.event_receipt("project-a", event_id)
            with self.assertRaises(NotFoundError):
                self.store.get_goal(goal_id, "project-a")

        self._assert_sensitive_content_absent(api, tuple(row[2] for row in secrets))


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
        scenario = self._create_review_scenario()
        artifacts = self._prepare_review_artifacts(scenario)
        inventory_artifacts = self._assert_inventory_scope_and_authorization(
            scenario, artifacts
        )
        self._assert_empty_inventory_rejected(scenario)
        receipt = self._complete_review_inventory(scenario, inventory_artifacts)
        packet = self._assert_review_dependencies(scenario, artifacts, receipt)
        self._authorize_exact_artifact_cleanup(scenario, artifacts, receipt, packet)
        self._assert_feedback_and_review_storage(scenario, receipt)
