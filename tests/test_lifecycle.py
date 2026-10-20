"""Regression tests for goal truth, significance, and review gates."""

from __future__ import annotations

import hashlib
from itertools import permutations
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence
from purge_fixtures import TestVerifier

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CriterionStatus,
    CuratorService,
    CuratorStore,
    Fact,
    EvidenceGateError,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    FactCapacityError,
    GoalCard,
    GoalStatus,
    MAX_FACTS_PER_GOAL,
    MAX_FACT_BYTES_PER_GOAL,
    Materiality,
    RejectUnverifiedEvidence,
    SuccessCriterion,
)
from curatormd_v2.events import EventEnvelope, FactRecorded, GoalStarted


class TransactionCheckingVerifier:
    """Fail tests if external proof verification runs inside SQLite work."""

    def __init__(self, store: CuratorStore) -> None:
        self.store = store
        self.calls = 0

    def attest(
        self, evidence: EvidenceRef, context: EvidenceVerificationContext
    ):
        """Assert the verifier is called only after store transactions close."""

        if self.store.transaction_active:
            raise AssertionError("evidence verifier ran inside a SQLite transaction")
        self.calls += 1
        return attest_test_evidence(evidence, context)


class CuratorLifecycleTests(unittest.TestCase):
    """Exercise lifecycle invariants and evidence-gated goal transitions."""

    def setUp(self) -> None:
        self.root = Path(
            self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        )
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.store = CuratorStore(self.root / "curator.sqlite3")
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), TestVerifier()
        )
        self.criteria = (
            SuccessCriterion("unit", "unit tests pass"),
            SuccessCriterion("probe", "readiness probe returns healthy"),
        )
        self.goal = self.service.goal_start(
            "Implement a reliable release health check",
            self.criteria,
            owner="agent",
            checklist_id="task-17",
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

    def tearDown(self) -> None:
        self.store.close()

    def proof(self, locator: str, outcome: EvidenceOutcome = EvidenceOutcome.PASSED):
        """Create stable synthetic evidence for one lifecycle assertion."""

        return EvidenceRef(
            evidence_kind="test",
            locator=f"test-proof:{locator}",
            sha256=hashlib.sha256(locator.encode()).hexdigest(),
            outcome=outcome,
        )

    def verify(self, criterion_id: str, description: str):
        """Record an independently verified criterion fact for this goal."""

        return self.service.goal_fact(
            self.goal.goal_id,
            FactKind.VERIFICATION,
            description,
            criterion_id=criterion_id,
            evidence=(self.proof(criterion_id),),
        )[0]

    def _apply_matrix_action(
        self,
        action: str,
        goal: GoalCard,
        replacement: GoalCard | None,
    ) -> object:
        """Apply one lifecycle-matrix action using explicit loop inputs."""

        if action == "activate":
            return self.service.goal_activate(
                goal.goal_id, "Matrix acceptance", goal.lifecycle_revision
            )
        if action == "change_fact":
            self.service.goal_fact(goal.goal_id, FactKind.CHANGE, "Matrix change fact")
            return self.store.get_goal(goal.goal_id)
        if action == "finish":
            return self.service.goal_finish(
                goal.goal_id, "Matrix completion request", goal.lifecycle_revision
            )
        if action == "block":
            return self.service.goal_block(goal.goal_id, "Matrix dependency", "Resolve it")
        if action == "defer":
            return self.service.goal_defer(goal.goal_id, "Matrix deferral", "Resume it")
        if action == "amend":
            return self.service.goal_amend_criteria(
                goal.goal_id,
                1,
                (SuccessCriterion("revised", "Revised criterion passes"),),
                "Matrix amendment",
                "Verify revised criterion",
                goal.lifecycle_revision,
            )
        if action == "cancel":
            return self.service.goal_cancel(goal.goal_id, "Matrix cancellation")
        if action == "supersede":
            assert replacement is not None
            return self.service.goal_supersede(
                goal.goal_id, replacement.goal_id, "Matrix supersession"
            )
        assert action == "reopen"
        return self.service.goal_reopen(
            goal.goal_id,
            "Matrix reopen",
            "Reverify the criterion",
            goal.lifecycle_revision,
        )

    def _goal_in_status(self, status: GoalStatus, label: str):
        criteria = (SuccessCriterion("done", f"{label} work passes verification"),)
        goal = self.service.goal_start(
            f"Lifecycle matrix: {label}",
            criteria,
            initial_status=(
                GoalStatus.PLANNED if status is GoalStatus.PLANNED else GoalStatus.ACTIVE
            ),
        )
        if status is GoalStatus.OPEN:
            goal = self.service.goal_finish(goal.goal_id, "Claim incomplete work")
        elif status is GoalStatus.BLOCKED:
            goal = self.service.goal_block(goal.goal_id, "Dependency", "Resolve dependency")
        elif status is GoalStatus.DEFERRED:
            goal = self.service.goal_defer(goal.goal_id, "Postponed", "Resume work")
        elif status is GoalStatus.COMPLETE:
            self.service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The matrix criterion passed",
                criterion_id="done",
                evidence=(self.proof(f"matrix-{label}"),),
            )
            goal = self.service.goal_finish(goal.goal_id, "Complete matrix fixture")
        elif status is GoalStatus.CANCELLED:
            goal = self.service.goal_cancel(goal.goal_id, "Matrix fixture cancelled")
        elif status is GoalStatus.SUPERSEDED:
            successor = self.service.goal_start(
                f"Successor for {label}",
                (SuccessCriterion("done", "Successor work passes verification"),),
            )
            goal = self.service.goal_supersede(
                goal.goal_id, successor.goal_id, "Matrix fixture superseded"
            )
        return goal

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

        unfinished = {
            GoalStatus.PLANNED,
            GoalStatus.ACTIVE,
            GoalStatus.OPEN,
            GoalStatus.BLOCKED,
            GoalStatus.DEFERRED,
        }
        actions = {
            "activate": {GoalStatus.PLANNED},
            "change_fact": {
                GoalStatus.ACTIVE,
                GoalStatus.OPEN,
                GoalStatus.BLOCKED,
                GoalStatus.DEFERRED,
            },
            "finish": {
                GoalStatus.ACTIVE,
                GoalStatus.OPEN,
                GoalStatus.BLOCKED,
                GoalStatus.DEFERRED,
                GoalStatus.COMPLETE,
            },
            "block": unfinished,
            "defer": unfinished,
            "amend": unfinished,
            "cancel": unfinished,
            "supersede": unfinished,
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
                        goal.goal_id,
                        target,
                        None,
                        (),
                        goal.lifecycle_revision,
                        self.service.project_id,
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
                self.goal.goal_id,
                1,
                (SuccessCriterion("updated", "Updated criterion passes"),),
                "Clarify scope",
                "Run updated test",
                expected_lifecycle_revision=1,
            )
        self.assertEqual(self.store.get_goal(self.goal.goal_id).criteria_revision, 1)
        self.assertEqual(self.store.get_goal(self.goal.goal_id).lifecycle_revision, 2)

    def test_database_file_is_private(self) -> None:
        mode = stat.S_IMODE((self.root / "curator.sqlite3").stat().st_mode)
        self.assertEqual(mode & 0o077, 0)

    def test_incomplete_finish_stays_open_with_concrete_next_action(self) -> None:
        verified = self.verify("unit", "unit test suite passed")
        before_finish = self.service.goal_status(self.goal.goal_id).criteria
        self.assertEqual(before_finish[0].status, CriterionStatus.VERIFIED)
        self.assertEqual(
            before_finish[0].verification_fact_ids, (verified.fact_id,)
        )
        self.assertEqual(before_finish[1].status, CriterionStatus.OPEN)
        stored = self.service.goal_finish(self.goal.goal_id, "Work is finished")
        self.assertEqual(stored.status, GoalStatus.OPEN)
        self.assertIn("readiness probe returns healthy", stored.next_action or "")
        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertTrue(any(fact.kind is FactKind.OPEN_GATE for fact in snapshot.facts))
        self.assertFalse(any(fact.kind is FactKind.OUTCOME for fact in snapshot.facts))

    def test_bullet_projection_separates_verified_claims_and_current_open_gates(self) -> None:
        self.verify("unit", "Unit test suite passed")
        opened = self.service.goal_finish(
            self.goal.goal_id, "The implementation is complete"
        )
        self.assertEqual(opened.status, GoalStatus.OPEN)
        projection = self.service.goal_bullet_projection(self.goal.goal_id)
        categories = [item.category.value for item in projection.bullets]
        rendered = [item.as_bullet() for item in projection.bullets]

        self.assertIn("verified_fact", categories)
        self.assertIn("unverified_claim", categories)
        self.assertIn("open_gate", categories)
        self.assertTrue(
            any(
                item.category.value == "open_gate" and "probe" in item.text
                for item in projection.bullets
            )
        )
        self.assertTrue(all("\n" not in bullet for bullet in rendered))
        self.assertEqual(projection.next_action, opened.next_action)

        self.verify("probe", "Readiness probe returned healthy")
        completed = self.service.goal_finish(
            self.goal.goal_id, "Every required criterion is verified"
        )
        final_projection = self.service.goal_bullet_projection(self.goal.goal_id)
        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertFalse(
            any(item.category.value == "open_gate" for item in final_projection.bullets)
        )

    def test_evidence_verifier_runs_outside_sqlite_write_transactions(self) -> None:
        verifier = TransactionCheckingVerifier(self.store)
        self.service.evidence_verifier = verifier

        self.verify("unit", "Unit suite passed")
        self.verify("probe", "Readiness probe returned healthy")
        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertTrue(
            all(item.status is CriterionStatus.VERIFIED for item in snapshot.criteria)
        )
        completed = self.service.goal_finish(
            self.goal.goal_id,
            "All criteria have current verified evidence",
            snapshot.goal.lifecycle_revision,
        )

        self.assertEqual(completed.status, GoalStatus.COMPLETE)
        self.assertGreaterEqual(verifier.calls, 6)

    def test_goal_report_preserves_truth_labels_and_bounds_fact_pages(self) -> None:
        self.service.goal_fact(
            self.goal.goal_id,
            FactKind.CHANGE,
            "Implemented the unit check",
        )
        self.verify("unit", "Unit suite passed")
        self.service.goal_finish(
            self.goal.goal_id, "Claimed complete without the readiness probe"
        )

        # Evidence adapters may perform slow I/O. Reporting must not hold the
        # store's BEGIN IMMEDIATE write transaction while evaluating evidence.
        with patch.object(
            self.store,
            "transaction",
            side_effect=AssertionError("read report opened a write transaction"),
        ):
            report = self.service.goal_report(self.goal.goal_id, fact_limit=1)

        self.assertIn("## Success criteria", report)
        self.assertIn("## Facts to date (showing 1–1 of", report)
        self.assertIn("## Open TODOs", report)
        self.assertIn("Verify criterion `probe`", report)
        self.assertIn("readiness probe returns healthy", report)
        self.assertIn("More facts available: request `fact_offset=1`", report)
        self.assertNotIn("test-proof:", report)

        second_page = self.service.goal_report(
            self.goal.goal_id, fact_offset=1, fact_limit=3
        )
        self.assertIn("Verified facts", second_page)
        self.assertIn("Unverified claims or checks", second_page)
        self.assertIn("completion claim", second_page)
        with self.assertRaisesRegex(ValueError, "fact_limit"):
            self.service.goal_report(self.goal.goal_id, fact_limit=17)

    def test_goal_intake_report_preserves_next_action_and_names_open_criteria(self) -> None:
        """Expose the caller's concrete first step without inventing one."""

        goal = self.service.goal_start(
            "Implement the requested lifecycle report",
            (SuccessCriterion("report", "The report lists verified facts and TODOs"),),
            goal_id="goal-with-next-action",
            initial_status=GoalStatus.PLANNED,
            next_action="Add the report's bounded next-action field",
        )
        report = self.service.goal_report(goal.goal_id)

        self.assertIn(
            "- Next action: Add the report's bounded next-action field", report
        )
        self.assertIn(
            "Verify criterion `report`: The report lists verified facts and TODOs",
            report,
        )
        self.assertEqual(
            self.service.goal_status(goal.goal_id).goal.next_action,
            "Add the report's bounded next-action field",
        )
        activated = self.service.goal_activate(
            goal.goal_id, "The user accepted the planned work", 1
        )
        self.assertEqual(activated.status, GoalStatus.ACTIVE)
        self.assertEqual(
            activated.next_action,
            "Add the report's bounded next-action field",
        )
        self.assertIn(
            "- Next action: Add the report's bounded next-action field",
            self.service.goal_report(goal.goal_id),
        )

    def test_goal_report_uses_bounded_history_pages_and_exact_child_counts(self) -> None:
        for index in range(35):
            self.service.goal_start(
                f"Child task {index}",
                (SuccessCriterion(f"child-{index}", "child criterion remains tracked"),),
                parent_goal_id=self.goal.goal_id,
                goal_id=f"child-{index:02d}",
            )

        with (
            patch.object(
                self.store,
                "list_sde_candidates",
                side_effect=AssertionError("unpaged SDE history loaded"),
            ),
            patch.object(
                self.store,
                "pending_receipts_for_goal",
                side_effect=AssertionError("unpaged purge history loaded"),
            ),
            patch.object(
                self.store,
                "receipts_for_goal",
                side_effect=AssertionError("unpaged receipt history loaded"),
            ),
            patch.object(
                self.store,
                "list_child_goals",
                side_effect=AssertionError("unpaged child history loaded"),
            ),
        ):
            first_page = self.service.goal_report(self.goal.goal_id)
            second_page = self.service.goal_report(
                self.goal.goal_id, child_offset=32
            )

        self.assertIn("35 child goal(s) remain open overall", first_page)
        self.assertIn("3 additional child goal(s) omitted", first_page)
        self.assertIn("`child-00`", first_page)
        self.assertIn("`child-31`", first_page)
        self.assertNotIn("`child-32`", first_page)
        self.assertIn("`child-32`", second_page)
        self.assertIn("`child-34`", second_page)

    def test_goal_status_paginates_candidate_and_purge_histories(self) -> None:
        with self.store.transaction() as connection:
            for index in range(105):
                candidate_id = f"sde-status-{index:03d}"
                receipt_id = f"receipt-status-{index:03d}"
                timestamp = f"2026-10-19T00:00:00.{index:06d}+00:00"
                connection.execute(
                    """INSERT INTO sde_candidates
                       (candidate_id, goal_id, materiality, rationale, fact_ids_json,
                        dedupe_key, status, created_at)
                       VALUES (?, ?, 'implementation', 'bounded test candidate', ?, ?,
                               'pending_review', ?)""",
                    (
                        candidate_id,
                        self.goal.goal_id,
                        json.dumps(["fact-not-required-by-this-read"]),
                        candidate_id,
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO audit_receipts
                       (receipt_id, candidate_id, decision, facts_sha256,
                        artifact_inventory_complete, reviewer_id, review_rationale,
                        canonical_persisted, canonical_target, canonical_sha256,
                        canonical_persisted_at, purge_status, created_at, updated_at)
                       VALUES (?, ?, 'approved', ?, 1, 'reviewer:test', 'fixture',
                               0, NULL, NULL, NULL, 'purge_pending', ?, ?)""",
                    (
                        receipt_id,
                        candidate_id,
                        "a" * 64,
                        timestamp,
                        timestamp,
                    ),
                )

        with (
            patch.object(
                self.store,
                "list_sde_candidates",
                side_effect=AssertionError("unpaged SDE history loaded"),
            ),
            patch.object(
                self.store,
                "pending_receipts_for_goal",
                side_effect=AssertionError("unpaged purge history loaded"),
            ),
        ):
            first_page = self.service.goal_status(self.goal.goal_id)
            second_page = self.service.goal_status(
                self.goal.goal_id, sde_offset=32, purge_offset=16
            )
            final_page = self.service.goal_status(
                self.goal.goal_id, sde_offset=96, purge_offset=96
            )

        self.assertEqual(len(first_page.sde_candidates), 32)
        self.assertEqual(len(first_page.pending_purges), 16)
        self.assertEqual(first_page.sde_candidate_total, 105)
        self.assertEqual(first_page.sde_candidate_status_counts, (("pending_review", 105),))
        self.assertEqual(first_page.sde_candidate_next_offset, 32)
        self.assertEqual(first_page.pending_purge_total, 105)
        self.assertEqual(first_page.pending_purge_next_offset, 16)
        projected = self.service.goal_bullet_projection(self.goal.goal_id)
        projected_text = [bullet.text for bullet in projected.bullets]
        self.assertTrue(
            any(
                "105 SDE candidate(s) await review overall" in text
                and "sde_offset=32" in text
                for text in projected_text
            )
        )
        self.assertTrue(
            any(
                "105 purge receipt(s) remain pending" in text
                and "purge_offset=16" in text
                for text in projected_text
            )
        )
        self.assertEqual(len(second_page.sde_candidates), 32)
        self.assertEqual(len(second_page.pending_purges), 16)
        self.assertEqual(second_page.sde_candidate_next_offset, 64)
        self.assertEqual(second_page.pending_purge_next_offset, 32)
        self.assertEqual(len(final_page.sde_candidates), 9)
        self.assertEqual(len(final_page.pending_purges), 9)
        self.assertIsNone(final_page.sde_candidate_next_offset)
        self.assertIsNone(final_page.pending_purge_next_offset)

    def test_goal_report_keeps_intake_provenance_after_activation_and_reopen(self) -> None:
        criterion = SuccessCriterion("verified", "The request is verified")
        event = EventEnvelope(
            event_id="source-request-17",
            project_id=self.service.project_id,
            source_id="mcp-user-intake",
            payload=GoalStarted(
                goal_id="provenance-goal",
                problem="Preserve request identity in reports",
                success_criteria=(criterion,),
                owner="agent-7",
                checklist_id="release-gate-3",
                checklist_version="sha256:" + "a" * 64,
                checklist_source_text="- [ ] Verify report provenance",
                initial_status=GoalStatus.PLANNED,
            ),
        )
        self.service.process_event(event)
        self.service.goal_activate("provenance-goal", "Accepted for work", 1)
        self.service.goal_fact(
            "provenance-goal",
            FactKind.VERIFICATION,
            "The focused proof passed",
            criterion_id="verified",
            evidence=(self.proof("origin"),),
        )
        self.service.goal_finish("provenance-goal", "The criterion is verified")
        self.service.goal_reopen(
            "provenance-goal",
            "A follow-up regression was reported",
            "Re-run the proof against the regression",
        )

        report = self.service.goal_report("provenance-goal")

        self.assertIn("- Outcome: `active`", report)
        self.assertIn("- Project: `default`", report)
        self.assertIn("- Owner: agent-7", report)
        self.assertIn("- Initial state: `planned`", report)
        self.assertIn("- Source event: `source-request-17`", report)
        self.assertIn("- Checklist: `release-gate-3`", report)
        self.assertIn("revision `aaaaaaaaaaaa`", report)
        self.assertIn(
            "- Checklist item (captured): - \\[ \\] Verify report provenance",
            report,
        )
        self.assertIn("## Current open gates", report)
        self.assertIn("Required criterion remains unverified", report)
        self.assertIn("Re-run the proof against the regression", report)

    def test_all_success_criteria_need_independently_verified_passing_evidence(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        stored = self.service.goal_finish(self.goal.goal_id, "All checks passed")
        self.assertEqual(stored.status, GoalStatus.COMPLETE)
        self.assertEqual(stored.success_criteria, self.criteria)
        progress = self.service.goal_status(self.goal.goal_id).criteria
        self.assertEqual(
            [criterion.status for criterion in progress],
            [CriterionStatus.VERIFIED, CriterionStatus.VERIFIED],
        )
        with self.assertRaises(ConflictError):
            self.service.goal_fact(self.goal.goal_id, FactKind.CHANGE, "late edit")

    def test_reopen_starts_new_evidence_epoch_without_erasing_old_facts(self) -> None:
        old_proofs = (
            self.verify("unit", "Original unit suite passed"),
            self.verify("probe", "Original readiness probe passed"),
        )
        old_proof_ids = {fact.fact_id for fact in old_proofs}
        self.assertEqual(
            self.service.goal_finish(self.goal.goal_id, "Initial work is complete").status,
            GoalStatus.COMPLETE,
        )

        reopened = self.service.goal_reopen(
            self.goal.goal_id,
            "A post-release regression was reported",
            "Reproduce and repair the regression",
        )
        reopened_snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(reopened.status, GoalStatus.ACTIVE)
        self.assertEqual(reopened.next_action, "Reproduce and repair the regression")
        self.assertEqual(
            [item.status for item in reopened_snapshot.criteria],
            [CriterionStatus.OPEN, CriterionStatus.OPEN],
        )
        self.assertTrue(
            all(fact.fact_id in {item.fact_id for item in reopened_snapshot.facts}
                for fact in old_proofs)
        )
        self.assertTrue(
            any(fact.kind is FactKind.REOPENED for fact in reopened_snapshot.facts)
        )

        still_open = self.service.goal_finish(
            self.goal.goal_id, "The reopened work is complete"
        )
        self.assertEqual(still_open.status, GoalStatus.OPEN)
        self.verify("unit", "Fresh unit suite passed after reopen")
        self.verify("probe", "Fresh readiness probe passed after reopen")
        finished_again = self.service.goal_finish(
            self.goal.goal_id, "Fresh evidence now satisfies the criteria"
        )
        self.assertEqual(finished_again.status, GoalStatus.COMPLETE)
        current = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(
            [item.status for item in current.criteria],
            [CriterionStatus.VERIFIED, CriterionStatus.VERIFIED],
        )
        current_proof_ids = {
            proof_id
            for item in current.criteria
            for proof_id in item.verification_fact_ids
        }
        self.assertFalse(
            old_proof_ids.intersection(current_proof_ids),
            "completion after reopen must use fresh criterion evidence",
        )

    def test_reopen_requires_completed_dependents_and_parent_to_reopen_first(self) -> None:
        prerequisite = self.service.goal_start(
            "Complete the prerequisite",
            (SuccessCriterion("prerequisite", "Prerequisite passes"),),
        )
        dependent = self.service.goal_start(
            "Complete the dependent",
            (SuccessCriterion("dependent", "Dependent passes"),),
            depends_on_goal_ids=(prerequisite.goal_id,),
        )
        self.service.goal_fact(
            prerequisite.goal_id,
            FactKind.VERIFICATION,
            "Prerequisite verified",
            criterion_id="prerequisite",
            evidence=(self.proof("prerequisite"),),
        )
        self.service.goal_finish(prerequisite.goal_id, "Prerequisite complete")
        self.service.goal_fact(
            dependent.goal_id,
            FactKind.VERIFICATION,
            "Dependent verified",
            criterion_id="dependent",
            evidence=(self.proof("dependent"),),
        )
        self.service.goal_finish(dependent.goal_id, "Dependent complete")

        with self.assertRaisesRegex(ConflictError, "dependent goals first"):
            self.service.goal_reopen(
                prerequisite.goal_id, "Prerequisite regression", "Repair prerequisite"
            )
        self.service.goal_reopen(
            dependent.goal_id, "Dependent follow-up", "Revalidate dependent"
        )
        reopened = self.service.goal_reopen(
            prerequisite.goal_id, "Prerequisite regression", "Repair prerequisite"
        )
        self.assertEqual(reopened.status, GoalStatus.ACTIVE)

    def test_every_reopen_order_obeys_nested_parent_and_dependency_gates(self) -> None:
        """Exhaust all four-goal reopen orders and preserve facts on rejected edges."""

        for index, order in enumerate(
            permutations(("root", "middle", "leaf", "dependency"))
        ):
            with self.subTest(order=order):
                scenario = f"reopen-order-{index}"
                criteria = {
                    label: SuccessCriterion(
                        f"{scenario}-{label}", f"{label} criterion passes"
                    )
                    for label in ("root", "middle", "leaf", "dependency")
                }
                dependency = self.service.goal_start(
                    f"{scenario} dependency", (criteria["dependency"],)
                )
                root = self.service.goal_start(
                    f"{scenario} root", (criteria["root"],)
                )
                middle = self.service.goal_start(
                    f"{scenario} middle",
                    (criteria["middle"],),
                    parent_goal_id=root.goal_id,
                )
                leaf = self.service.goal_start(
                    f"{scenario} leaf",
                    (criteria["leaf"],),
                    parent_goal_id=middle.goal_id,
                    depends_on_goal_ids=(dependency.goal_id,),
                )
                goals = {
                    "root": root,
                    "middle": middle,
                    "leaf": leaf,
                    "dependency": dependency,
                }
                for label in ("dependency", "leaf", "middle", "root"):
                    goal = goals[label]
                    self.service.goal_fact(
                        goal.goal_id,
                        FactKind.VERIFICATION,
                        f"{scenario} {label} passed",
                        criterion_id=criteria[label].criterion_id,
                        evidence=(self.proof(f"{scenario}-{label}"),),
                    )
                    goals[label] = self.service.goal_finish(
                        goal.goal_id, f"Complete {scenario} {label}"
                    )
                    self.assertEqual(goals[label].status, GoalStatus.COMPLETE)

                expected_status = {
                    label: GoalStatus.COMPLETE for label in goals
                }
                expected_revision = {
                    label: goal.lifecycle_revision for label, goal in goals.items()
                }
                for label in order:
                    before_goals = {
                        name: self.store.get_goal(goal.goal_id)
                        for name, goal in goals.items()
                    }
                    before_facts = {
                        name: self.store.list_facts(goal.goal_id)
                        for name, goal in goals.items()
                    }
                    allowed = (
                        label == "root"
                        or (label == "middle" and expected_status["root"] is GoalStatus.ACTIVE)
                        or (label == "leaf" and expected_status["middle"] is GoalStatus.ACTIVE)
                        or (
                            label == "dependency"
                            and expected_status["leaf"] is not GoalStatus.COMPLETE
                        )
                    )

                    try:
                        reopened = self.service.goal_reopen(
                            goals[label].goal_id,
                            f"Reopen {scenario} {label}",
                            f"Reverify {scenario} {label}",
                            expected_revision[label],
                        )
                    except ConflictError:
                        self.assertFalse(allowed, f"unexpected refusal reopening {label}")
                        for name, goal in goals.items():
                            self.assertEqual(
                                self.store.get_goal(goal.goal_id), before_goals[name]
                            )
                            self.assertEqual(
                                self.store.list_facts(goal.goal_id), before_facts[name]
                            )
                    else:
                        self.assertTrue(allowed, f"unexpectedly reopened {label}")
                        self.assertEqual(reopened.status, GoalStatus.ACTIVE)
                        expected_status[label] = GoalStatus.ACTIVE
                        expected_revision[label] += 1
                        retained_fact_ids = {
                            fact.fact_id for fact in before_facts[label]
                        }
                        reopened_facts = self.store.list_facts(goals[label].goal_id)
                        self.assertTrue(
                            retained_fact_ids.issubset(
                                {fact.fact_id for fact in reopened_facts}
                            )
                        )
                        self.assertEqual(
                            self.service.goal_status(goals[label].goal_id)
                            .criteria[0]
                            .status,
                            CriterionStatus.OPEN,
                        )

                    for name, goal in goals.items():
                        actual = self.store.get_goal(goal.goal_id)
                        self.assertEqual(actual.status, expected_status[name])
                        self.assertEqual(actual.lifecycle_revision, expected_revision[name])

    def test_criteria_amendment_is_versioned_and_starts_a_fresh_evidence_epoch(self) -> None:
        original_criteria = self.goal.success_criteria
        old_proofs = (
            self.verify("unit", "Original unit criteria verified"),
            self.verify("probe", "Original probe criteria verified"),
        )
        amended_criteria = (
            SuccessCriterion("unit", "Updated unit suite passes"),
            SuccessCriterion("probe", "Updated readiness probe passes"),
            SuccessCriterion("release", "Release smoke test passes"),
        )

        amended = self.service.goal_amend_criteria(
            self.goal.goal_id,
            expected_revision=1,
            success_criteria=amended_criteria,
            reason="The owner added an explicit release smoke criterion",
            next_action="Run all three updated checks",
        )

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertEqual(amended.criteria_revision, 2)
        self.assertEqual(amended.success_criteria, amended_criteria)
        self.assertEqual(
            [item.status for item in snapshot.criteria],
            [CriterionStatus.OPEN, CriterionStatus.OPEN, CriterionStatus.OPEN],
        )
        self.assertEqual(
            [version.criteria for version in snapshot.criteria_history],
            [original_criteria, amended_criteria],
        )
        self.assertEqual(snapshot.criteria_history[1].reason,
                         "The owner added an explicit release smoke criterion")
        self.assertTrue(
            all(fact.fact_id in {item.fact_id for item in snapshot.facts} for fact in old_proofs)
        )
        self.assertTrue(
            any(fact.kind is FactKind.CRITERIA_AMENDED for fact in snapshot.facts)
        )

        with self.assertRaisesRegex(ConflictError, "revision changed"):
            self.service.goal_amend_criteria(
                self.goal.goal_id,
                expected_revision=1,
                success_criteria=amended_criteria,
                reason="Stale concurrent edit",
                next_action="Reload the goal first",
            )

        self.assertEqual(
            self.service.goal_finish(self.goal.goal_id, "Claimed complete").status,
            GoalStatus.OPEN,
        )
        for criterion in amended_criteria:
            self.service.goal_fact(
                self.goal.goal_id,
                FactKind.VERIFICATION,
                f"Verified {criterion.criterion_id} under revision two",
                criterion_id=criterion.criterion_id,
                evidence=(self.proof(f"revision-two-{criterion.criterion_id}"),),
            )
        self.assertEqual(
            self.service.goal_finish(
                self.goal.goal_id, "All amended criteria have fresh evidence"
            ).status,
            GoalStatus.COMPLETE,
        )

    def test_fact_count_capacity_blocks_without_pruning_and_reports_open_gate(self) -> None:
        for index in range(MAX_FACTS_PER_GOAL):
            self.service.goal_fact(
                self.goal.goal_id,
                FactKind.RESEARCH,
                f"Bounded research fact {index}",
            )

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertIsNotNone(snapshot.fact_capacity)
        assert snapshot.fact_capacity is not None
        self.assertEqual(len(snapshot.facts), MAX_FACTS_PER_GOAL)
        self.assertEqual(snapshot.fact_capacity.goal_fact_count, MAX_FACTS_PER_GOAL)
        self.assertFalse(snapshot.fact_capacity.append_available)
        self.assertIsNotNone(snapshot.fact_capacity.open_gate)
        assert snapshot.fact_capacity.open_gate is not None
        self.assertIn("capacity reached", snapshot.fact_capacity.open_gate)
        projection = self.service.goal_bullet_projection(self.goal.goal_id)
        self.assertTrue(
            any(
                item.category.value == "open_gate"
                and "capacity reached" in item.text
                for item in projection.bullets
            )
        )
        self.assertEqual(snapshot.goal.status, GoalStatus.ACTIVE)

        with self.assertRaises(FactCapacityError):
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "One more unique fact"
            )

        repeated, inserted = self.service.goal_fact(
            self.goal.goal_id, FactKind.RESEARCH, "Bounded research fact 511"
        )
        self.assertFalse(inserted, "semantic retries remain idempotent at capacity")
        self.assertIn(repeated.fact_id, {fact.fact_id for fact in snapshot.facts})
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), MAX_FACTS_PER_GOAL)

        event = EventEnvelope(
            "fact-capacity-event",
            "default",
            FactRecorded(
                self.goal.goal_id,
                "fact-over-capacity",
                FactKind.CHANGE,
                "Change blocked at the fact-history ceiling",
            ),
        )
        failed = self.service.process_event(event)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "FactCapacityError")
        self.assertEqual(self.store.pending_events(project_id="default"), ())
        self.assertEqual(
            self.store.project_storage_usage("default").event_payload_bytes_retained,
            0,
            "capacity-failed event payload is discarded after its digest receipt",
        )
        retry = self.service.process_event(event)
        self.assertEqual(retry.status.value, "failed")
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), MAX_FACTS_PER_GOAL)

    def test_fact_byte_capacity_blocks_oversized_history_without_pruning(self) -> None:
        ordinal = 0
        while True:
            evidence = tuple(
                self.proof(f"{ordinal}-{index}-" + "x" * 900)
                for index in range(16)
            )
            try:
                self.service.goal_fact(
                    self.goal.goal_id,
                    FactKind.RESEARCH,
                    f"Large bounded reference set {ordinal}",
                    evidence=evidence,
                )
                ordinal += 1
            except FactCapacityError:
                break

        snapshot = self.service.goal_status(self.goal.goal_id)
        self.assertIsNotNone(snapshot.fact_capacity)
        assert snapshot.fact_capacity is not None
        self.assertGreater(ordinal, 0)
        self.assertLessEqual(
            snapshot.fact_capacity.goal_fact_bytes, MAX_FACT_BYTES_PER_GOAL
        )
        self.assertGreater(snapshot.fact_capacity.goal_fact_bytes_remaining, 0)
        self.assertTrue(
            snapshot.fact_capacity.append_available,
            "smaller facts remain admissible when this oversized one does not fit",
        )
        self.assertEqual(len(snapshot.facts), ordinal)

    def test_project_fact_capacity_is_shared_within_project_and_isolated_between_projects(
        self,
    ) -> None:
        other_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        other_goal = other_service.goal_start(
            "Independent project task",
            (SuccessCriterion("other", "Other project evidence is recorded"),),
        )

        with patch("curatormd_v2.store.MAX_FACTS_PER_PROJECT", 2):
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "First project fact"
            )
            self.service.goal_fact(
                self.goal.goal_id, FactKind.RESEARCH, "Second project fact"
            )
            capacity = self.service.goal_status(self.goal.goal_id).fact_capacity
            assert capacity is not None
            self.assertFalse(capacity.append_available)
            self.assertEqual(capacity.project_fact_count, 2)
            self.assertTrue(
                self.store.project_storage_usage("default").fact_capacity_reached,
            )
            with self.assertRaises(FactCapacityError):
                self.service.goal_fact(
                    self.goal.goal_id, FactKind.RESEARCH, "Third project fact"
                )

            other_service.goal_fact(
                other_goal.goal_id, FactKind.RESEARCH, "Other project remains writable"
            )
            self.assertFalse(
                self.store.project_storage_usage("other-project").fact_capacity_reached
            )

    def test_default_verifier_rejects_agent_asserted_pass(self) -> None:
        service = CuratorService(
            self.store, ArtifactPurger(self.stage), RejectUnverifiedEvidence()
        )
        with self.assertRaises(EvidenceGateError):
            service.goal_fact(
                self.goal.goal_id,
                FactKind.VERIFICATION,
                "agent says all tests passed",
                criterion_id="unit",
                evidence=(self.proof("claimed"),),
            )
        stored = service.goal_finish(self.goal.goal_id, "Claimed complete")
        self.assertEqual(stored.status, GoalStatus.OPEN)

    def test_duplicate_facts_are_idempotent(self) -> None:
        first, inserted_first = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Updated the health check"
        )
        second, inserted_second = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Updated the health check"
        )
        self.assertTrue(inserted_first)
        self.assertFalse(inserted_second)
        self.assertEqual(first.fact_id, second.fact_id)
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 1)

    def test_routine_progress_does_not_create_sde(self) -> None:
        self.verify("unit", "unit test suite passed")
        candidate = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.ROUTINE,
            "Routine progress update",
            tuple(f.fact_id for f in self.store.list_facts(self.goal.goal_id)),
        )
        self.assertIsNone(candidate)
        self.assertEqual(self.store.list_sde_candidates(self.goal.goal_id), ())

    def test_material_change_requires_verified_fact_for_sde(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added health check"
        )
        with self.assertRaises(EvidenceGateError):
            self.service.sde_assess(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable change",
                (change.fact_id,),
            )

    def test_sde_rationale_is_a_compact_line_linked_to_verified_bullets(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added a durable health check"
        )
        verification = self.verify("unit", "Unit test passed")
        with self.assertRaisesRegex(ValueError, "single compact line"):
            self.service.sde_assess(
                self.goal.goal_id,
                Materiality.IMPLEMENTATION,
                "First paragraph.\nSecond paragraph.",
                (change.fact_id, verification.fact_id),
            )
        candidate = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "The durable health check is supported by a passing test",
            (change.fact_id, verification.fact_id),
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        review = self.service.sde_review_detail(candidate.candidate_id)
        self.assertEqual(len(review.facts), 2)
        self.assertTrue(any(fact.evidence for fact in review.facts))

    def test_repeated_sde_assessment_deduplicates_the_same_fact_set(self) -> None:
        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added health check"
        )
        verification = self.verify("unit", "unit tests passed")
        selected = (change.fact_id, verification.fact_id)
        first = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "Durable and tested implementation",
            selected,
        )
        repeated = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "Repeated assessment of the same facts",
            selected,
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(repeated)
        assert first is not None and repeated is not None
        self.assertEqual(first.candidate_id, repeated.candidate_id)
        self.assertEqual(len(self.store.list_sde_candidates(self.goal.goal_id)), 1)

    def test_review_queue_detail_is_bounded_and_project_scoped(self) -> None:
        """Show reviewers only selected facts and the goal in their project."""

        change, _ = self.service.goal_fact(
            self.goal.goal_id, FactKind.CHANGE, "Added an evidence-backed change"
        )
        verification = self.verify("unit", "unit tests passed")
        candidate = self.service.sde_assess(
            self.goal.goal_id,
            Materiality.IMPLEMENTATION,
            "The implementation is durable and directly verified",
            (change.fact_id, verification.fact_id),
        )
        assert candidate is not None

        other_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="other-project",
        )
        other_goal = other_service.goal_start(
            "Other project's work",
            (SuccessCriterion("done", "Other project check passes"),),
        )
        other_change, _ = other_service.goal_fact(
            other_goal.goal_id, FactKind.CHANGE, "Other project's change"
        )
        other_verification, _ = other_service.goal_fact(
            other_goal.goal_id,
            FactKind.VERIFICATION,
            "Other project's check passed",
            criterion_id="done",
            evidence=(self.proof("other-project-check"),),
        )
        other_candidate = other_service.sde_assess(
            other_goal.goal_id,
            Materiality.IMPLEMENTATION,
            "Other project change has direct evidence",
            (other_change.fact_id, other_verification.fact_id),
        )
        assert other_candidate is not None

        queue = self.service.sde_review_queue(limit=1)
        self.assertEqual([item.candidate.candidate_id for item in queue], [candidate.candidate_id])
        detail = self.service.sde_review_detail(candidate.candidate_id)
        self.assertEqual(detail.goal.goal_id, self.goal.goal_id)
        self.assertEqual(
            {item.fact_id for item in detail.facts},
            {change.fact_id, verification.fact_id},
        )
        self.assertIsNone(detail.receipt)
        with self.assertRaises(LookupError):
            self.service.sde_review_detail(other_candidate.candidate_id)
        with self.assertRaises(ValueError):
            self.service.sde_review_queue(limit=0)

    def test_successful_completion_facts_are_compact_single_bullets(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        self.service.goal_finish(self.goal.goal_id, "Complete")
        for fact in self.store.list_facts(self.goal.goal_id):
            self.assertNotIn("\n", fact.bullet)
            self.assertLessEqual(len(fact.bullet), 1000)
            self.assertTrue(fact.as_bullet().startswith("- "))

    def test_goal_list_can_filter_open_and_complete_goals(self) -> None:
        self.verify("unit", "unit test suite passed")
        self.verify("probe", "readiness probe returned 200")
        self.service.goal_finish(self.goal.goal_id, "Complete")
        open_goal = self.service.goal_start(
            "Another task", (SuccessCriterion("next", "next thing passes"),)
        )
        self.service.goal_finish(open_goal.goal_id, "Claimed complete")
        completed = self.service.goal_list((GoalStatus.COMPLETE,))
        opened = self.service.goal_list((GoalStatus.OPEN,))
        self.assertEqual([item.goal.goal_id for item in completed], [self.goal.goal_id])
        self.assertEqual([item.goal.goal_id for item in opened], [open_goal.goal_id])

    def test_failed_transition_rolls_back_facts_and_goal_state_atomically(self) -> None:
        other_goal = self.service.goal_start(
            "Other goal", (SuccessCriterion("other", "other criterion"),)
        )
        misplaced_fact = Fact(
            goal_id=other_goal.goal_id,
            kind=FactKind.OUTCOME,
            bullet="Must not be attached to the first goal",
        )
        with self.assertRaises(ConflictError):
            self.store.transition_goal(
                self.goal.goal_id,
                GoalStatus.COMPLETE,
                None,
                (misplaced_fact,),
                1,
            )
        self.assertEqual(self.store.get_goal(self.goal.goal_id).status, GoalStatus.ACTIVE)
        self.assertEqual(self.store.list_facts(self.goal.goal_id), ())


if __name__ == "__main__":
    unittest.main()
