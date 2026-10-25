"""Shared setup and verifier for goal lifecycle test modules."""

from __future__ import annotations

import hashlib
import unittest

from evidence_fixtures import attest_test_evidence
from store_fixtures import create_store_stage
from purge_fixtures import TestVerifier

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CriterionStatus,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    GoalCard,
    GoalStatus,
    SuccessCriterion,
)
from curatormd_v2.events import GoalCriteriaAmended


class TransactionCheckingVerifier:  # pylint: disable=too-few-public-methods
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


class LifecycleTestSupport(unittest.TestCase):
    """Create one disposable V2 goal lifecycle context per test."""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        """Create a fresh store, service, and active test goal."""

        self.root, self.stage, self.store = create_store_stage(self)
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

    def tearDown(self) -> None:  # pylint: disable=invalid-name
        """Close the disposable SQLite store after each test."""

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
            result = self.service.goal_activate(
                goal.goal_id, "Matrix acceptance", goal.lifecycle_revision
            )
        elif action == "change_fact":
            self.service.goal_fact(goal.goal_id, FactKind.CHANGE, "Matrix change fact")
            result = self.store.get_goal(goal.goal_id)
        elif action == "finish":
            result = self.service.goal_finish(
                goal.goal_id, "Matrix completion request", goal.lifecycle_revision
            )
        elif action == "block":
            result = self.service.goal_block(
                goal.goal_id, "Matrix dependency", "Resolve it"
            )
        elif action == "defer":
            result = self.service.goal_defer(
                goal.goal_id, "Matrix deferral", "Resume it"
            )
        elif action == "amend":
            result = self.service.goal_amend_criteria(
                GoalCriteriaAmended(
                    goal_id=goal.goal_id,
                    expected_revision=1,
                    success_criteria=(
                        SuccessCriterion("revised", "Revised criterion passes"),
                    ),
                    reason="Matrix amendment",
                    next_action="Verify revised criterion",
                    expected_lifecycle_revision=goal.lifecycle_revision,
                )
            )
        elif action == "cancel":
            result = self.service.goal_cancel(goal.goal_id, "Matrix cancellation")
        elif action == "supersede":
            assert replacement is not None
            result = self.service.goal_supersede(
                goal.goal_id, replacement.goal_id, "Matrix supersession"
            )
        else:
            assert action == "reopen"
            result = self.service.goal_reopen(
                goal.goal_id,
                "Matrix reopen",
                "Reverify the criterion",
                goal.lifecycle_revision,
            )
        return result

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

    def _completed_linked_goal(self) -> tuple[GoalCard, GoalCard, GoalCard]:
        """Create a completed child with one parent and one prerequisite."""

        parent = self.service.goal_start(
            "Original parent",
            (SuccessCriterion("parent", "Parent work passes"),),
        )
        dependency = self.service.goal_start(
            "Original dependency",
            (SuccessCriterion("dependency", "Dependency passes"),),
        )
        goal = self.service.goal_start(
            "Completed linked work",
            (SuccessCriterion("goal", "Linked work passes"),),
            parent_goal_id=parent.goal_id,
            depends_on_goal_ids=(dependency.goal_id,),
        )
        for linked, label in ((dependency, "dependency"), (goal, "goal")):
            self.service.goal_fact(
                linked.goal_id,
                FactKind.VERIFICATION,
                f"{label} verified",
                criterion_id=label,
                evidence=(self.proof(f"terminal-links-{label}"),),
            )
            self.service.goal_finish(linked.goal_id, f"Complete {label}")
        return parent, dependency, goal

    def _make_linked_records_terminal(
        self,
        parent: GoalCard,
        dependency: GoalCard,
        parent_terminal: GoalStatus,
        dependency_terminal: GoalStatus,
    ) -> tuple[GoalCard, GoalCard]:
        """Retire the parent and seed the otherwise unreachable legacy dependency."""

        parent_replacement = self.service.goal_start(
            "Replacement parent",
            (SuccessCriterion("replacement", "Replacement parent passes"),),
        )
        dependency_replacement = self.service.goal_start(
            "Replacement dependency",
            (SuccessCriterion("replacement", "Replacement dependency passes"),),
        )
        if parent_terminal is GoalStatus.CANCELLED:
            self.service.goal_cancel(parent.goal_id, "Parent scope withdrawn")
        else:
            self.service.goal_supersede(
                parent.goal_id, parent_replacement.goal_id, "Parent scope changed"
            )

        # Current rules require a completed dependency before its dependent can
        # complete, and completed goals are terminal. Seed legacy persisted state.
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE goals SET status = ?, superseded_by_goal_id = ? "
                "WHERE project_id = ? AND goal_id = ?",
                (
                    dependency_terminal.value,
                    dependency_replacement.goal_id
                    if dependency_terminal is GoalStatus.SUPERSEDED
                    else None,
                    self.service.project_id,
                    dependency.goal_id,
                ),
            )
        return parent_replacement, dependency_replacement

    def _completed_reopen_order_fixture(self, scenario: str) -> dict[str, GoalCard]:
        """Build a fully evidenced nested parent/dependency completion graph."""

        criteria = {
            label: SuccessCriterion(f"{scenario}-{label}", f"{label} criterion passes")
            for label in ("root", "middle", "leaf", "dependency")
        }
        dependency = self.service.goal_start(
            f"{scenario} dependency", (criteria["dependency"],)
        )
        root = self.service.goal_start(f"{scenario} root", (criteria["root"],))
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
        return goals

    def _assert_reopen_order_step(
        self,
        scenario: str,
        label: str,
        goals: dict[str, GoalCard],
        expected_status: dict[str, GoalStatus],
        expected_revision: dict[str, int],
    ) -> None:
        """Check one reopen edge and prove rejected attempts are atomic."""

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
                self.assertEqual(self.store.get_goal(goal.goal_id), before_goals[name])
                self.assertEqual(self.store.list_facts(goal.goal_id), before_facts[name])
        else:
            self.assertTrue(allowed, f"unexpectedly reopened {label}")
            self.assertEqual(reopened.status, GoalStatus.ACTIVE)
            expected_status[label] = GoalStatus.ACTIVE
            expected_revision[label] += 1
            retained_fact_ids = {fact.fact_id for fact in before_facts[label]}
            reopened_facts = self.store.list_facts(goals[label].goal_id)
            self.assertTrue(
                retained_fact_ids.issubset(
                    {fact.fact_id for fact in reopened_facts}
                )
            )
            self.assertEqual(
                self.service.goal_status(goals[label].goal_id).criteria[0].status,
                CriterionStatus.OPEN,
            )

        for name, goal in goals.items():
            actual = self.store.get_goal(goal.goal_id)
            self.assertEqual(actual.status, expected_status[name])
            self.assertEqual(actual.lifecycle_revision, expected_revision[name])
