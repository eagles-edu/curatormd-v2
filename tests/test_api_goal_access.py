"""Goal and project access API regression tests."""

from __future__ import annotations

from test_api import (
    AuthenticatedCaller,
    AuthenticatedCuratorAPI,
    ConsumerBindingTransitionRequest,
    EventEnvelope,
    EventInboxStatus,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    GoalChildrenPageRequest,
    GoalCriteriaAmended,
    GoalListCapacityError,
    GoalStarted,
    GoalStatus,
    InMemoryTokenBucket,
    NotFoundError,
    ProjectAction,
    ProjectGrantAuthorizer,
    ProjectPlugin,
    SuccessCriterion,
    TestVerifier,
    _ApiTestSupport,
    hashlib,
    hermes_source_id,
    replace,
)


class ApiGoalAccessTests(_ApiTestSupport):
    """Exercise apigoalaccess behavior."""

    def test_default_authorizer_fails_closed(self) -> None:
        api = AuthenticatedCuratorAPI({"project-a": self.plugin})
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_list(self.caller, "project-a")

    def test_fact_evidence_read_requires_exact_project_read_grant(self) -> None:
        goal = self.plugin.service.goal_start(
            "Expose a bounded evidence page only to project readers.",
            (SuccessCriterion("visible", "The fact is in the report."),),
        )
        fact, _ = self.plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "Recorded in the authorized project."
        )
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)

        result = api.goal_fact_evidence(
            self.caller, "project-a", goal.goal_id, fact.fact_id
        )

        self.assertEqual(result.project_id, "project-a")
        self.assertEqual(result.goal_id, goal.goal_id)
        self.assertEqual(result.fact_id, fact.fact_id)
        self.assertEqual(result.evidence, ())
        denied = AuthenticatedCuratorAPI({"project-a": self.plugin})
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            denied.goal_fact_evidence(
                self.caller, "project-a", goal.goal_id, fact.fact_id
            )

    def test_grant_revocation_between_report_and_evidence_reads_denies_next_page(self) -> None:
        """A prior report read cannot carry authority across grant revocation."""

        class MutableAuthorizer:
            allowed = True

            def authorize(
                self,
                caller: AuthenticatedCaller,
                project_id: str,
                action: ProjectAction,
            ) -> bool:
                return (
                    self.allowed
                    and caller.subject_id == "hermes-user-1"
                    and project_id == "project-a"
                    and action is ProjectAction.READ
                )

        goal = self.plugin.service.goal_start(
            "Recheck the read grant before every report detail request.",
            (SuccessCriterion("visible", "The fact appears on the report page."),),
        )
        fact, _ = self.plugin.service.goal_fact(
            goal.goal_id, FactKind.CHANGE, "This fact is visible only while granted."
        )
        authorizer = MutableAuthorizer()
        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, authorizer)

        report = api.goal_report(self.caller, "project-a", goal.goal_id)
        self.assertIn(fact.fact_id, report)
        prior_evidence = api.goal_fact_evidence(
            self.caller, "project-a", goal.goal_id, fact.fact_id
        )
        self.assertEqual(prior_evidence.fact_id, fact.fact_id)

        authorizer.allowed = False
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_report(self.caller, "project-a", goal.goal_id)
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_fact_evidence(
                self.caller, "project-a", goal.goal_id, fact.fact_id
            )


    def test_retired_source_can_reconcile_only_its_exact_processed_receipt(self) -> None:
        """Retirement permits a lost-ack read without reopening source writes."""

        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)
        profile_id = "renew-ssl-coding"
        caller = AuthenticatedCaller("hermes-user-1", profile_id)
        source_id = hermes_source_id(profile_id, "project-a", 1)
        event = EventEnvelope(
            "retired-source-processed-1",
            "project-a",
            GoalStarted(
                goal_id="retired-source-goal",
                problem="Process one event before the source is retired.",
                success_criteria=(
                    SuccessCriterion("saved", "The event is processed once."),
                ),
            ),
            source_id=source_id,
            source_sequence=1,
        )
        original = api.process_event_json(caller, "project-a", event.to_json())
        self.assertEqual(original.status, EventInboxStatus.PROCESSED)

        pending = self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id="project-a",
                status="deregistration_pending",
                rationale="Stop the exact source before retirement",
                expected_revision=1,
                transition_id="retired-source-pending-1",
            ),
            actor_id="test-admin",
        )
        deregistered = self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id="project-a",
                status="deregistered",
                rationale="Finish source cutover before retirement",
                expected_revision=pending.binding.revision,
                transition_id="retired-source-deregistered-1",
            ),
            actor_id="test-admin",
        )
        self.store.retire_project(
            "project-a",
            actor_id="test-admin",
            rationale="Retire the completed disposable source",
            expected_revision=1,
            transition_id="retired-source-project-1",
        )

        replay = api.process_event_json(
            caller, "project-a", event.to_json(), replay_only=True
        )
        self.assertEqual(replay, original)
        self.assertEqual(
            self.store.get_consumer_binding("project-a").revision,
            deregistered.binding.revision,
        )
        self.assertEqual(
            self.store.event_receipt("project-a", event.event_id), original
        )

        changed = replace(
            event,
            payload=GoalStarted(
                goal_id="retired-source-goal",
                problem="Changed content must not receive the prior acknowledgement.",
                success_criteria=(
                    SuccessCriterion("saved", "The event is processed once."),
                ),
            ),
        )
        with self.assertRaisesRegex(PermissionError, "retired project"):
            api.process_event_json(caller, "project-a", changed.to_json(), replay_only=True)
        unseen = replace(event, event_id="retired-source-unseen-2", source_sequence=2)
        with self.assertRaisesRegex(PermissionError, "retired project"):
            api.process_event_json(caller, "project-a", unseen.to_json())
        wrong_profile = AuthenticatedCaller("hermes-user-1", "other-profile")
        with self.assertRaisesRegex(PermissionError, "retired project"):
            api.process_event_json(
                wrong_profile, "project-a", event.to_json()
            )


    def test_goal_criteria_amendment_passes_typed_request_through_write_scope(self) -> None:
        """The API authorizes and forwards the existing amendment event unchanged."""

        api = AuthenticatedCuratorAPI({"project-a": self.plugin}, self.authorizer)
        goal = self.plugin.service.goal_start(
            "Keep criteria revision in the authenticated request.",
            (SuccessCriterion("old", "The original criterion is visible."),),
        )
        request = GoalCriteriaAmended(
            goal_id=goal.goal_id,
            expected_revision=1,
            success_criteria=(
                SuccessCriterion("new", "The amended criterion is visible."),
            ),
            reason="Owner clarified the acceptance condition.",
            next_action="Verify the amended criterion.",
            expected_lifecycle_revision=goal.lifecycle_revision,
        )

        result = api.goal_amend_criteria(self.caller, "project-a", request)

        self.assertEqual(result.goal.goal_id, goal.goal_id)
        self.assertEqual(result.goal.success_criteria, request.success_criteria)
        self.assertEqual(result.goal.next_action, request.next_action)


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
            self.caller,
            "project-a",
            GoalChildrenPageRequest(parent.goal_id, offset=0, limit=1),
        )
        second = api.goal_children_page(
            self.caller,
            "project-a",
            GoalChildrenPageRequest(
                parent.goal_id,
                offset=first.next_offset or 0,
                limit=1,
            ),
        )
        planned = api.goal_children_page(
            self.caller,
            "project-a",
            GoalChildrenPageRequest(
                parent.goal_id,
                offset=0,
                limit=10,
                statuses=(GoalStatus.PLANNED,),
            ),
        )

        self.assertEqual(first.total, 3)
        self.assertEqual(first.next_offset, 1)
        self.assertEqual(second.next_offset, 2)
        self.assertEqual(planned.total, 1)
        self.assertEqual(planned.goals[0].goal_id, "child-page-1")
        self.assertFalse(hasattr(first.goals[0], "facts"))
        with self.assertRaisesRegex(PermissionError, "not authorized"):
            api.goal_children_page(
                AuthenticatedCaller("other-user"),
                "project-a",
                GoalChildrenPageRequest(parent.goal_id),
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
