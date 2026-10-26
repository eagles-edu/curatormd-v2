"""GoalLifecycle regressions."""

from __future__ import annotations
import stat
from typing import Any
from lifecycle_fixtures import (
    FACT_ACCEPTING_GOAL_STATUSES,
    FINISHABLE_GOAL_STATUSES,
    UNFINISHED_GOAL_STATUSES,
)
from purge_fixtures import TestVerifier
from lifecycle_test_support import LifecycleTestSupport

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CriterionStatus,
    CuratorService,
    Fact,
    FactKind,
    GoalStatus,
    SuccessCriterion,
    GoalTransitionRequest,
)
from curatormd_v2.events import GoalCriteriaAmended


class GoalLifecycleTests(LifecycleTestSupport):
    """Cover goallifecycle invariants."""

    def test_goal_start_and_fact_reject_unknown_typed_options(self) -> None:
        unknown_options: Any = {"unexpected_field": "value"}
        with self.assertRaisesRegex(TypeError, "unsupported option"):
            self.service.goal_start(
                "Reject an unsupported intake field",
                (SuccessCriterion("done", "The field is rejected"),),
                **unknown_options,
            )
        with self.assertRaisesRegex(TypeError, "unsupported option"):
            self.service.goal_fact(
                self.goal.goal_id,
                FactKind.CHANGE,
                "Reject an unsupported fact field",
                **unknown_options,
            )

    def test_invalid_initial_status_does_not_retain_raw_value(self) -> None:
        """Goal intake errors must not chain caller-controlled enum values."""

        with self.assertRaisesRegex(ValueError, "planned or active") as raised:
            self.service.goal_start(
                "Reject an invalid status",
                (SuccessCriterion("done", "The invalid status is rejected"),),
                initial_status="PRIVATE_STATUS_CANARY",  # type: ignore[arg-type]
            )
        self.assertNotIn("PRIVATE_STATUS_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_start_preserves_problem_criteria_and_checklist_link(self) -> None:
        stored = self.store.get_goal(self.goal.goal_id)
        self.assertEqual(stored.problem, "Implement a reliable release health check")
        self.assertEqual(stored.success_criteria, self.criteria)
        self.assertEqual(stored.checklist_id, "task-17")
        self.assertIsNone(stored.checklist_source_text)
        self.assertEqual(stored.status, GoalStatus.ACTIVE)
        progress = self.service.goal_status(self.goal.goal_id).criteria
        self.assertEqual(
            [criterion.status for criterion in progress],
            [CriterionStatus.OPEN, CriterionStatus.OPEN],
        )

    def test_planned_goal_requires_revision_checked_activation_before_work(self) -> None:
        planned = self.service.goal_start(
            "Wait for explicit implementation acceptance",
            (SuccessCriterion("done", "The implementation is independently verified"),),
            initial_status=GoalStatus.PLANNED,
        )
        self.assertEqual(planned.status, GoalStatus.PLANNED)
        with self.assertRaisesRegex(ConflictError, "activated before completion"):
            self.service.goal_finish(planned.goal_id, "Claim completion", 1)
        with self.assertRaisesRegex(ConflictError, "activated before implementation"):
            self.service.goal_fact(planned.goal_id, FactKind.CHANGE, "Changed code")
        with self.assertRaisesRegex(ConflictError, "activated before implementation"):
            self.service.goal_fact(
                planned.goal_id,
                FactKind.VERIFICATION,
                "Claimed passing test",
                criterion_id="done",
                evidence=(self.proof("planned-proof"),),
            )
        with self.assertRaisesRegex(ConflictError, "lifecycle revision changed"):
            self.service.goal_activate(planned.goal_id, "Accept implementation", 2)
        self.assertEqual(self.store.get_goal(planned.goal_id).status, GoalStatus.PLANNED)
        self.assertEqual(self.store.list_facts(planned.goal_id), ())

        active = self.service.goal_activate(
            planned.goal_id, "User approved implementation", 1
        )
        self.assertEqual(active.status, GoalStatus.ACTIVE)
        self.assertEqual(active.lifecycle_revision, 2)
        self.assertEqual(
            self.store.list_facts(planned.goal_id)[0].bullet,
            "Activated: User approved implementation",
        )

    def test_parent_goal_waits_for_child_and_dependency_goals(self) -> None:
        """A parent closes only after all linked task and dependency gates."""

        parent = self.service.goal_start(
            "Deliver the release",
            (SuccessCriterion("release", "Release checks pass"),),
        )
        prerequisite = self.service.goal_start(
            "Prepare deployment config",
            (SuccessCriterion("config", "Config validates"),),
        )
        child = self.service.goal_start(
            "Run production readiness checks",
            (SuccessCriterion("probe", "Readiness probe passes"),),
            parent_goal_id=parent.goal_id,
            depends_on_goal_ids=(prerequisite.goal_id,),
        )

        with self.assertRaisesRegex(ConflictError, "resolve dependent goals"):
            self.service.goal_cancel(prerequisite.goal_id, "No longer required")

        children = self.service.goal_children(parent.goal_id)
        self.assertEqual([item.goal.goal_id for item in children], [child.goal_id])
        self.assertEqual(child.parent_goal_id, parent.goal_id)
        self.assertEqual(child.depends_on_goal_ids, (prerequisite.goal_id,))

        self.service.goal_fact(
            parent.goal_id,
            FactKind.VERIFICATION,
            "Release checks pass",
            criterion_id="release",
            evidence=(self.proof("parent-release"),),
        )
        parent_open = self.service.goal_finish(parent.goal_id, "All work complete")
        self.assertEqual(parent_open.status, GoalStatus.OPEN)
        self.assertIn(child.goal_id, parent_open.next_action or "")

        self.service.goal_fact(
            child.goal_id,
            FactKind.VERIFICATION,
            "Readiness probe passes",
            criterion_id="probe",
            evidence=(self.proof("child-probe"),),
        )
        child_open = self.service.goal_finish(child.goal_id, "Probe passed")
        self.assertEqual(child_open.status, GoalStatus.OPEN)
        self.assertIn(prerequisite.goal_id, child_open.next_action or "")

        self.service.goal_fact(
            prerequisite.goal_id,
            FactKind.VERIFICATION,
            "Config validates",
            criterion_id="config",
            evidence=(self.proof("config"),),
        )
        self.assertEqual(
            self.service.goal_finish(prerequisite.goal_id, "Config validated").status,
            GoalStatus.COMPLETE,
        )
        self.assertEqual(
            self.service.goal_finish(child.goal_id, "Probe passed").status,
            GoalStatus.COMPLETE,
        )
        self.assertEqual(
            self.service.goal_finish(parent.goal_id, "Release complete").status,
            GoalStatus.COMPLETE,
        )

    def test_parent_and_dependency_links_are_project_scoped(self) -> None:
        """Reject linking a task to a goal owned by another project."""

        other = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        foreign = other.goal_start(
            "Foreign task", (SuccessCriterion("done", "Foreign task is done"),)
        )
        with self.assertRaises(LookupError):
            self.service.goal_start(
                "Cross-project child",
                (SuccessCriterion("done", "Child task is done"),),
                parent_goal_id=foreign.goal_id,
            )
        with self.assertRaises(LookupError):
            self.service.goal_start(
                "Cross-project dependency",
                (SuccessCriterion("done", "Task is done"),),
                depends_on_goal_ids=(foreign.goal_id,),
            )

    def test_child_cannot_depend_on_parent_or_ancestor(self) -> None:
        """Reject a dependency graph that would make parent completion cyclic."""

        parent = self.service.goal_start(
            "Parent", (SuccessCriterion("parent", "Parent is complete"),)
        )
        child = self.service.goal_start(
            "Existing child",
            (SuccessCriterion("child", "Child is complete"),),
            parent_goal_id=parent.goal_id,
        )
        with self.assertRaisesRegex(ValueError, "parent or ancestor"):
            self.service.goal_start(
                "Cyclic child",
                (SuccessCriterion("cyclic", "Cyclic task is complete"),),
                parent_goal_id=child.goal_id,
                depends_on_goal_ids=(parent.goal_id,),
            )

    def test_cancel_is_terminal_and_never_counts_as_success(self) -> None:
        cancelled = self.service.goal_cancel(self.goal.goal_id, "Request withdrawn")

        self.assertEqual(cancelled.status, GoalStatus.CANCELLED)
        self.assertIsNone(cancelled.next_action)
        self.assertEqual(
            self.store.list_facts(self.goal.goal_id)[-1].kind,
            FactKind.CANCELLED,
        )
        with self.assertRaisesRegex(ConflictError, "terminal goals"):
            self.service.goal_finish(self.goal.goal_id, "Claimed complete")
        with self.assertRaisesRegex(ConflictError, "terminal goals"):
            self.service.goal_fact(self.goal.goal_id, FactKind.RESEARCH, "Late fact")
        with self.assertRaisesRegex(ConflictError, "terminal goals"):
            self.store.append_fact(
                Fact(
                    goal_id=self.goal.goal_id,
                    kind=FactKind.RESEARCH,
                    bullet="Direct store write after cancellation",
                )
            )
        with self.assertRaisesRegex(ConflictError, "only completed goals"):
            self.service.goal_reopen(self.goal.goal_id, "Try again", "Restart work")

    def test_parent_retirement_requires_children_to_be_resolved(self) -> None:
        parent = self.service.goal_start(
            "Parent work", (SuccessCriterion("parent", "Parent is done"),)
        )
        child = self.service.goal_start(
            "Child work",
            (SuccessCriterion("child", "Child is done"),),
            parent_goal_id=parent.goal_id,
        )
        with self.assertRaisesRegex(ConflictError, "resolve child goals"):
            self.service.goal_cancel(parent.goal_id, "Parent no longer needed")
        self.service.goal_cancel(child.goal_id, "Child scope withdrawn")
        cancelled_parent = self.service.goal_cancel(
            parent.goal_id, "Parent scope withdrawn"
        )
        self.assertEqual(cancelled_parent.status, GoalStatus.CANCELLED)

    def test_cancelled_child_does_not_supply_parent_criterion_evidence(self) -> None:
        parent = self.service.goal_start(
            "Parent release", (SuccessCriterion("release", "Release is ready"),)
        )
        child = self.service.goal_start(
            "Optional readiness task",
            (SuccessCriterion("probe", "Readiness probe passes"),),
            parent_goal_id=parent.goal_id,
        )
        self.service.goal_cancel(child.goal_id, "Probe is no longer required")
        still_open = self.service.goal_finish(parent.goal_id, "Claimed complete")
        self.assertEqual(still_open.status, GoalStatus.OPEN)
        self.assertIn("Release is ready", still_open.next_action or "")
        self.service.goal_fact(
            parent.goal_id,
            FactKind.VERIFICATION,
            "Release readiness verified independently",
            criterion_id="release",
            evidence=(self.proof("parent-release"),),
        )
        self.assertEqual(
            self.service.goal_finish(parent.goal_id, "Release is ready").status,
            GoalStatus.COMPLETE,
        )

    def test_supersession_requires_active_same_project_replacement(self) -> None:
        replacement = self.service.goal_start(
            "Revised task", (SuccessCriterion("done", "Revised task is done"),)
        )
        superseded = self.service.goal_supersede(
            self.goal.goal_id, replacement.goal_id, "Use revised scope"
        )

        self.assertEqual(superseded.status, GoalStatus.SUPERSEDED)
        self.assertEqual(superseded.superseded_by_goal_id, replacement.goal_id)
        with self.assertRaisesRegex(ConflictError, "terminal goals"):
            self.service.goal_defer(self.goal.goal_id, "Later", "Resume")
        with self.assertRaisesRegex(ConflictError, "cancelled or superseded"):
            self.service.goal_start(
                "Depends on retired work",
                (SuccessCriterion("done", "Task is done"),),
                depends_on_goal_ids=(self.goal.goal_id,),
            )

        other = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        foreign = other.goal_start(
            "Foreign replacement",
            (SuccessCriterion("done", "Foreign work is done"),),
        )
        local_old = self.service.goal_start(
            "Local goal",
            (SuccessCriterion("done", "Local work is done"),),
        )
        with self.assertRaisesRegex(ConflictError, "same project"):
            self.service.goal_supersede(local_old.goal_id, foreign.goal_id, "Wrong scope")

    def test_supersession_rejects_every_nonactive_replacement_state(self) -> None:
        """A replacement is valid only while it is active, not merely nonterminal."""

        expected_criteria = (
            SuccessCriterion("done", "Replacement work is independently verified"),
        )
        for replacement_status in GoalStatus:
            with self.subTest(replacement_status=replacement_status):
                old = self.service.goal_start(
                    f"Original task for {replacement_status.value}", expected_criteria
                )
                replacement = self.service.goal_start(
                    f"Replacement task for {replacement_status.value}",
                    expected_criteria,
                    initial_status=(
                        GoalStatus.PLANNED
                        if replacement_status is GoalStatus.PLANNED
                        else GoalStatus.ACTIVE
                    ),
                )

                if replacement_status is GoalStatus.OPEN:
                    replacement = self.service.goal_finish(
                        replacement.goal_id, "Claim incomplete replacement"
                    )
                elif replacement_status is GoalStatus.BLOCKED:
                    replacement = self.service.goal_block(
                        replacement.goal_id, "Waiting on dependency", "Resolve dependency"
                    )
                elif replacement_status is GoalStatus.DEFERRED:
                    replacement = self.service.goal_defer(
                        replacement.goal_id, "Work postponed", "Resume replacement"
                    )
                elif replacement_status is GoalStatus.COMPLETE:
                    self.service.goal_fact(
                        replacement.goal_id,
                        FactKind.VERIFICATION,
                        "Replacement criterion passed",
                        criterion_id="done",
                        evidence=(self.proof("replacement-complete"),),
                    )
                    replacement = self.service.goal_finish(
                        replacement.goal_id, "Complete replacement"
                    )
                elif replacement_status is GoalStatus.CANCELLED:
                    replacement = self.service.goal_cancel(
                        replacement.goal_id, "Replacement cancelled"
                    )
                elif replacement_status is GoalStatus.SUPERSEDED:
                    successor = self.service.goal_start(
                        "Successor replacement",
                        (SuccessCriterion("done", "Successor work is verified"),),
                    )
                    replacement = self.service.goal_supersede(
                        replacement.goal_id, successor.goal_id, "Replacement superseded"
                    )

                if replacement_status is GoalStatus.ACTIVE:
                    superseded = self.service.goal_supersede(
                        old.goal_id, replacement.goal_id, "Use active replacement"
                    )
                    self.assertEqual(superseded.status, GoalStatus.SUPERSEDED)
                else:
                    with self.assertRaisesRegex(ConflictError, "replacement goal must be active"):
                        self.service.goal_supersede(
                            old.goal_id, replacement.goal_id, "Reject nonactive replacement"
                        )
                    unchanged = self.store.get_goal(old.goal_id)
                    self.assertEqual(unchanged.status, GoalStatus.ACTIVE)
                    self.assertEqual(self.store.list_facts(old.goal_id), ())

    def test_lifecycle_action_matrix_matches_contract_for_every_goal_status(self) -> None:
        """Exercise every public lifecycle action against every stored status."""

        actions = {
            "activate": {GoalStatus.PLANNED},
            "change_fact": FACT_ACCEPTING_GOAL_STATUSES,
            "finish": FINISHABLE_GOAL_STATUSES,
            "block": UNFINISHED_GOAL_STATUSES,
            "defer": UNFINISHED_GOAL_STATUSES,
            "amend": UNFINISHED_GOAL_STATUSES,
            "cancel": UNFINISHED_GOAL_STATUSES,
            "supersede": UNFINISHED_GOAL_STATUSES,
            "reopen": {GoalStatus.COMPLETE},
        }

        for source_status in GoalStatus:
            for action, allowed_statuses in actions.items():
                with self.subTest(source_status=source_status, action=action):
                    goal = self._goal_in_status(source_status, f"{source_status}-{action}")
                    before = self.store.get_goal(goal.goal_id)
                    before_facts = self.store.list_facts(goal.goal_id)
                    replacement = None
                    if action == "supersede":
                        replacement = self.service.goal_start(
                            "Active matrix replacement",
                            (SuccessCriterion("done", "Replacement passes verification"),),
                        )

                    if source_status in allowed_statuses:
                        self._apply_matrix_action(action, goal, replacement)
                        actual = self.store.get_goal(goal.goal_id)
                        expected_status = {
                            "activate": GoalStatus.ACTIVE,
                            "change_fact": source_status,
                            "finish": (
                                GoalStatus.COMPLETE
                                if source_status is GoalStatus.COMPLETE
                                else GoalStatus.OPEN
                            ),
                            "block": GoalStatus.BLOCKED,
                            "defer": GoalStatus.DEFERRED,
                            "amend": source_status,
                            "cancel": GoalStatus.CANCELLED,
                            "supersede": GoalStatus.SUPERSEDED,
                            "reopen": GoalStatus.ACTIVE,
                        }[action]
                        expected_revision = before.lifecycle_revision + int(
                            action not in {"change_fact"}
                            and not (
                                action == "finish"
                                and source_status is GoalStatus.COMPLETE
                            )
                        )
                        self.assertEqual(actual.status, expected_status)
                        self.assertEqual(actual.lifecycle_revision, expected_revision)
                    else:
                        with self.assertRaises(ConflictError):
                            self._apply_matrix_action(action, goal, replacement)
                        unchanged = self.store.get_goal(goal.goal_id)
                        self.assertEqual(unchanged, before)
                        self.assertEqual(self.store.list_facts(goal.goal_id), before_facts)

    def test_store_transition_primitive_rejects_dedicated_lifecycle_targets(self) -> None:
        """Activation, reopening, and retirement must use their invariant checks."""

        for target in (
            GoalStatus.PLANNED,
            GoalStatus.ACTIVE,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        ):
            with self.subTest(target=target):
                goal = self.service.goal_start(
                    f"Reject direct transition to {target.value}",
                    (SuccessCriterion("done", "Task is verified"),),
                )
                before = self.store.get_goal(goal.goal_id)
                with self.assertRaisesRegex(ConflictError, "transition_goal may target only"):
                    self.store.transition_goal(
                        GoalTransitionRequest(
                            goal_id=goal.goal_id,
                            status=target,
                            next_action=None,
                            facts=(),
                            expected_lifecycle_revision=goal.lifecycle_revision,
                            project_id=self.service.project_id,
                        )
                    )
                self.assertEqual(self.store.get_goal(goal.goal_id), before)

    def test_nonterminal_status_updates_require_the_current_lifecycle_revision(self) -> None:
        self.assertEqual(self.goal.lifecycle_revision, 1)
        deferred = self.service.goal_defer(
            self.goal.goal_id,
            "Waiting for a test fixture",
            "Request the fixture",
            expected_lifecycle_revision=1,
        )
        self.assertEqual(deferred.lifecycle_revision, 2)

        with self.assertRaisesRegex(ConflictError, "lifecycle revision changed"):
            self.service.goal_block(
                self.goal.goal_id,
                "Fixture unavailable",
                "Ask the test owner",
                expected_lifecycle_revision=1,
            )
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 1)
        self.assertEqual(self.store.get_goal(self.goal.goal_id).status, GoalStatus.DEFERRED)

        blocked = self.service.goal_block(
            self.goal.goal_id,
            "Fixture unavailable",
            "Ask the test owner",
            expected_lifecycle_revision=2,
        )
        self.assertEqual(blocked.lifecycle_revision, 3)

    def test_criteria_amendment_checks_both_contract_and_lifecycle_revisions(self) -> None:
        self.service.goal_defer(
            self.goal.goal_id,
            "Waiting",
            "Resume after fixture arrives",
            expected_lifecycle_revision=1,
        )
        with self.assertRaisesRegex(ConflictError, "lifecycle revision changed"):
            self.service.goal_amend_criteria(
                GoalCriteriaAmended(
                    goal_id=self.goal.goal_id,
                    expected_revision=1,
                    success_criteria=(
                        SuccessCriterion("updated", "Updated criterion passes"),
                    ),
                    reason="Clarify scope",
                    next_action="Run updated test",
                    expected_lifecycle_revision=1,
                )
            )
        self.assertEqual(self.store.get_goal(self.goal.goal_id).criteria_revision, 1)
        self.assertEqual(self.store.get_goal(self.goal.goal_id).lifecycle_revision, 2)

    def test_database_file_is_private(self) -> None:
        mode = stat.S_IMODE((self.root / "curator.sqlite3").stat().st_mode)
        self.assertEqual(mode & 0o077, 0)
