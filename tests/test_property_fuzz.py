"""Deterministic generated cases for parser, lifecycle, replay, and path invariants."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

from hypothesis import given, settings, strategies as st

from evidence_fixtures import attest_test_evidence
from lifecycle_fixtures import (
    FACT_ACCEPTING_GOAL_STATUSES,
    FINISHABLE_GOAL_STATUSES,
    UNFINISHED_GOAL_STATUSES,
)

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CuratorService,
    GoalStatus,
    StagingArtifactClass,
    StagingClassUsage,
    StagingUsage,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    FactRecorded,
    GoalCriteriaAmended,
    GoalFinishRequested,
    GoalStarted,
)
from curatormd_v2.models import EvidenceOutcome, EvidenceRef, FactKind
from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.project_config import CONFIG_FILENAME, ProjectConfig, ProjectConfigError
from curatormd_v2.store import CuratorStore


SAFE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"


# EvidenceVerifier test double intentionally implements only `attest`.
class _TrustedFixtureEvidence:  # pylint: disable=too-few-public-methods
    """Accept only the two explicit local references used by this regression."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only explicit local evidence references emitted by tests."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator in {"suite://first", "suite://second"}
            else None
        )


@dataclass
class _LifecycleSequenceState:
    """Expected lifecycle state tracked independently from the service."""

    goal_id: str
    status: GoalStatus
    lifecycle_revision: int
    criteria_revision: int
    criterion_id: str
    epoch_verified: bool = False

    def record_success(self, action: str) -> None:
        """Advance the model only after the service accepts an action."""

        if action == "activate":
            self.status = GoalStatus.ACTIVE
            self.lifecycle_revision += 1
        elif action == "verify":
            self.epoch_verified = True
        elif action == "finish":
            if self.status is not GoalStatus.COMPLETE:
                self.status = (
                    GoalStatus.COMPLETE if self.epoch_verified else GoalStatus.OPEN
                )
                self.lifecycle_revision += 1
        elif action == "block":
            self.status = GoalStatus.BLOCKED
            self.lifecycle_revision += 1
        elif action == "defer":
            self.status = GoalStatus.DEFERRED
            self.lifecycle_revision += 1
        elif action == "amend":
            self.criteria_revision += 1
            self.criterion_id = f"criterion-{self.criteria_revision}"
            self.epoch_verified = False
            self.lifecycle_revision += 1
        elif action == "reopen":
            self.status = GoalStatus.ACTIVE
            self.epoch_verified = False
            self.lifecycle_revision += 1
        elif action == "cancel":
            self.status = GoalStatus.CANCELLED
            self.lifecycle_revision += 1
        elif action == "supersede":
            self.status = GoalStatus.SUPERSEDED
            self.lifecycle_revision += 1


def _lifecycle_action_allowed(state: _LifecycleSequenceState, action: str) -> bool:
    """Return whether the modeled state permits one generated action."""

    unfinished = state.status in UNFINISHED_GOAL_STATUSES
    facts_allowed = state.status in FACT_ACCEPTING_GOAL_STATUSES
    finish_allowed = state.status in FINISHABLE_GOAL_STATUSES
    return {
        "activate": state.status is GoalStatus.PLANNED,
        "change": facts_allowed,
        "verify": facts_allowed,
        "finish": finish_allowed,
        "block": unfinished,
        "defer": unfinished,
        "amend": unfinished,
        "reopen": state.status is GoalStatus.COMPLETE,
        "cancel": unfinished,
        "supersede": unfinished,
    }[action]


def _amend_generated_criterion(
    service: CuratorService, state: _LifecycleSequenceState, index: int
) -> None:
    """Apply one generated criteria revision at the current lifecycle fence."""

    next_criterion_id = f"criterion-{state.criteria_revision + 1}"
    service.goal_amend_criteria(
        GoalCriteriaAmended(
            goal_id=state.goal_id,
            expected_revision=state.criteria_revision,
            success_criteria=(
                SuccessCriterion(
                    next_criterion_id,
                    f"Generated amended criterion {index}",
                ),
            ),
            reason=f"Generated amendment {index}",
            next_action=f"Verify amended criterion {index}",
            expected_lifecycle_revision=state.lifecycle_revision,
        )
    )


def _supersede_generated_goal(
    service: CuratorService, state: _LifecycleSequenceState, index: int
) -> None:
    """Create and link a generated successor to the current goal."""

    replacement = service.goal_start(
        f"Generated successor {index}",
        (SuccessCriterion(f"successor-{index}", "Successor is verified"),),
    )
    service.goal_supersede(
        state.goal_id,
        replacement.goal_id,
        f"Generated supersession {index}",
    )


def _apply_generated_lifecycle_action(
    service: CuratorService,
    state: _LifecycleSequenceState,
    action: str,
    index: int,
) -> None:
    """Dispatch one generated action with the model's current revisions."""

    actions: dict[str, Callable[[], object]] = {
        "activate": lambda: service.goal_activate(
            state.goal_id,
            f"Generated acceptance {index}",
            state.lifecycle_revision,
        ),
        "change": lambda: service.goal_fact(
            state.goal_id, FactKind.CHANGE, f"Generated change {index}"
        ),
        "verify": lambda: service.goal_fact(
            state.goal_id,
            FactKind.VERIFICATION,
            f"Generated verification {index}",
            criterion_id=state.criterion_id,
            evidence=(
                EvidenceRef(
                    "test", "suite://first", "a" * 64, EvidenceOutcome.PASSED
                ),
            ),
        ),
        "finish": lambda: service.goal_finish(
            state.goal_id,
            f"Generated completion claim {index}",
            state.lifecycle_revision,
        ),
        "block": lambda: service.goal_block(
            state.goal_id,
            f"Generated dependency {index}",
            f"Generated recovery {index}",
            state.lifecycle_revision,
        ),
        "defer": lambda: service.goal_defer(
            state.goal_id,
            f"Generated deferral {index}",
            f"Generated next action {index}",
            state.lifecycle_revision,
        ),
        "amend": lambda: _amend_generated_criterion(service, state, index),
        "reopen": lambda: service.goal_reopen(
            state.goal_id,
            f"Generated reopen {index}",
            f"Reverify epoch {index}",
            state.lifecycle_revision,
        ),
        "cancel": lambda: service.goal_cancel(
            state.goal_id, f"Generated cancellation {index}"
        ),
        "supersede": lambda: _supersede_generated_goal(service, state, index),
    }
    actions[action]()


@dataclass
class _RelatedLifecycleState:
    """Expected state for linked dependency, child, and parent goals."""

    goal_ids: dict[str, str]
    statuses: dict[str, GoalStatus]
    revisions: dict[str, int]


def _create_related_lifecycle_state(
    service: CuratorService,
) -> _RelatedLifecycleState:
    """Create and verify one dependency/child/parent goal graph."""

    criteria = {
        "dependency": SuccessCriterion("dependency", "Dependency passes"),
        "child": SuccessCriterion("child", "Child passes"),
        "parent": SuccessCriterion("parent", "Parent passes"),
    }
    dependency = service.goal_start(
        "Generated prerequisite", (criteria["dependency"],)
    )
    parent = service.goal_start("Generated parent", (criteria["parent"],))
    child = service.goal_start(
        "Generated child",
        (criteria["child"],),
        parent_goal_id=parent.goal_id,
        depends_on_goal_ids=(dependency.goal_id,),
    )
    goals = {"dependency": dependency, "child": child, "parent": parent}
    for label, goal in goals.items():
        service.goal_fact(
            goal.goal_id,
            FactKind.VERIFICATION,
            f"Generated {label} criterion passed",
            criterion_id=criteria[label].criterion_id,
            evidence=(
                EvidenceRef("test", "suite://first", "a" * 64, EvidenceOutcome.PASSED),
            ),
        )
    return _RelatedLifecycleState(
        goal_ids={label: goal.goal_id for label, goal in goals.items()},
        statuses={label: GoalStatus.ACTIVE for label in goals},
        revisions={label: goal.lifecycle_revision for label, goal in goals.items()},
    )


def _related_action_allowed(
    state: _RelatedLifecycleState, target: str, is_finish: bool
) -> bool:
    """Apply the modeled parent/child/dependency prerequisite rules."""

    target_status = state.statuses[target]
    unfinished = target_status in UNFINISHED_GOAL_STATUSES
    if is_finish:
        return unfinished or target_status is GoalStatus.COMPLETE
    if not unfinished:
        return False
    if target == "dependency":
        return state.statuses["child"] not in UNFINISHED_GOAL_STATUSES
    if target == "parent":
        return state.statuses["child"] in {
            GoalStatus.COMPLETE,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
        }
    return True


def _run_related_action(
    service: CuratorService,
    state: _RelatedLifecycleState,
    target: str,
    action: str,
    index: int,
) -> None:
    """Apply the selected generated finish or cancel operation."""

    if action.startswith("finish_"):
        service.goal_finish(
            state.goal_ids[target],
            f"Generated {target} finish {index}",
            state.revisions[target],
        )
    else:
        service.goal_cancel(
            state.goal_ids[target], f"Generated {target} cancellation {index}"
        )


def _snapshot_related_goals(
    store: CuratorStore, state: _RelatedLifecycleState
) -> tuple[dict[str, object], dict[str, object]]:
    """Capture goal rows and fact tuples for an exact denial assertion."""

    return (
        {
            label: store.get_goal(goal_id)
            for label, goal_id in state.goal_ids.items()
        },
        {
            label: store.list_facts(goal_id)
            for label, goal_id in state.goal_ids.items()
        },
    )


def _assert_related_goals_unchanged(
    test_case: unittest.TestCase,
    store: CuratorStore,
    state: _RelatedLifecycleState,
    before_goals: dict[str, object],
    before_facts: dict[str, object],
) -> None:
    """Confirm a denied linked transition changed no goal or fact rows."""

    for label, goal_id in state.goal_ids.items():
        test_case.assertEqual(store.get_goal(goal_id), before_goals[label])
        test_case.assertEqual(store.list_facts(goal_id), before_facts[label])


def _advance_related_state(
    service: CuratorService,
    state: _RelatedLifecycleState,
    target: str,
    action: str,
) -> None:
    """Advance only the model state proven by an accepted linked-goal action."""

    if action.startswith("cancel_"):
        state.statuses[target] = GoalStatus.CANCELLED
        state.revisions[target] += 1
        return
    if state.statuses[target] is GoalStatus.COMPLETE:
        return

    verified = (
        service.goal_status(state.goal_ids[target]).criteria[0].status.value
        == "verified"
    )
    child_status = state.statuses["child"]
    related_work_open = (
        target == "child" and state.statuses["dependency"] is not GoalStatus.COMPLETE
    ) or (
        target == "parent"
        and child_status
        not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
    )
    state.statuses[target] = (
        GoalStatus.COMPLETE if verified and not related_work_open else GoalStatus.OPEN
    )
    state.revisions[target] += 1


def _assert_related_goals_match_model(
    test_case: unittest.TestCase,
    store: CuratorStore,
    state: _RelatedLifecycleState,
) -> None:
    """Compare every linked goal's persisted status and revision to the model."""

    for label, goal_id in state.goal_ids.items():
        actual = store.get_goal(goal_id)
        test_case.assertEqual(actual.status, state.statuses[label])
        test_case.assertEqual(actual.lifecycle_revision, state.revisions[label])
        if label == "child" and actual.status is GoalStatus.OPEN:
            test_case.assertIn(state.goal_ids["dependency"], actual.next_action or "")
        if label == "parent" and actual.status is GoalStatus.OPEN:
            test_case.assertIn(state.goal_ids["child"], actual.next_action or "")


class EventPropertyTests(unittest.TestCase):
    """Generated valid inputs must round-trip and retries must not duplicate state."""

    @settings(max_examples=60, deadline=None, derandomize=True)
    @given(
        event_id=st.text(alphabet=SAFE, min_size=1, max_size=96),
        goal_id=st.text(alphabet=SAFE, min_size=1, max_size=96),
        problem=st.text(alphabet=SAFE, min_size=1, max_size=160),
        criterion_id=st.text(alphabet=SAFE, min_size=1, max_size=64),
        criterion=st.text(alphabet=SAFE, min_size=1, max_size=160),
    )
    def test_generated_valid_goal_events_round_trip(
        self,
        event_id: str,
        goal_id: str,
        problem: str,
        criterion_id: str,
        criterion: str,
    ) -> None:
        event = EventEnvelope(
            event_id,
            "generated-project",
            GoalStarted(
                goal_id,
                problem,
                (SuccessCriterion(criterion_id, criterion),),
            ),
        )

        self.assertEqual(EventEnvelope.from_json(event.to_json()), event)

    @settings(max_examples=25, deadline=None, derandomize=True)
    @given(bullets=st.lists(st.text(alphabet=SAFE, min_size=1, max_size=80), max_size=20))
    def test_replayed_generated_change_facts_do_not_prove_completion(
        self, bullets: list[str]
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = CuratorStore(root / "curator.sqlite3")
            try:
                stage = root / "stage"
                stage.mkdir()
                service = CuratorService(
                    store,
                    ArtifactPurger(stage),
                    _TrustedFixtureEvidence(),
                    project_id="generated-project",
                )
                start = EventEnvelope(
                    "generated-start",
                    "generated-project",
                    GoalStarted(
                        "generated-goal",
                        "Prove generated facts cannot self-complete",
                        (SuccessCriterion("proof", "A passing verification exists"),),
                    ),
                )
                self.assertEqual(
                    service.process_event(start), service.process_event(start)
                )

                for index, bullet in enumerate(bullets):
                    fact_event = EventEnvelope(
                        f"generated-fact-{index}",
                        "generated-project",
                        FactRecorded(
                            "generated-goal",
                            f"generated-fact-id-{index}",
                            FactKind.CHANGE,
                            bullet,
                        ),
                    )
                    first = service.process_event(fact_event)
                    self.assertEqual(first, service.process_event(fact_event))

                finish = EventEnvelope(
                    "generated-finish",
                    "generated-project",
                    GoalFinishRequested(
                        "generated-goal", "Claim the goal is complete"
                    ),
                )
                service.process_event(finish)
                state = service.goal_status("generated-goal")
                self.assertEqual(state.goal.status, GoalStatus.OPEN)
                self.assertEqual(
                    len(state.facts), len(set(bullets)) + 3
                )  # claim, open-gate/outcome facts, and distinct changes
                outcomes = tuple(
                    fact for fact in state.facts if fact.kind is FactKind.OUTCOME
                )
                self.assertEqual(tuple(fact.bullet for fact in outcomes), ("open",))
            finally:
                store.close()


class StagingUsagePropertyTests(unittest.TestCase):
    """Generated bounded measurements must preserve their aggregate invariants."""

    @settings(max_examples=60, deadline=None, derandomize=True)
    @given(
        classes=st.lists(
            st.tuples(
                st.sampled_from(tuple(StagingArtifactClass)),
                st.integers(min_value=0, max_value=100),
                st.integers(min_value=0, max_value=100_000),
            ),
            unique_by=lambda item: item[0],
            max_size=len(StagingArtifactClass),
        ),
        non_file_entries=st.integers(min_value=0, max_value=100),
    )
    def test_generated_class_totals_match_bounded_scan(
        self,
        classes: list[tuple[StagingArtifactClass, int, int]],
        non_file_entries: int,
    ) -> None:
        class_usage = tuple(
            StagingClassUsage(artifact_class, file_count, file_bytes)
            for artifact_class, file_count, file_bytes in classes
        )
        file_count = sum(item.regular_file_count for item in class_usage)
        file_bytes = sum(item.observed_file_bytes for item in class_usage)
        usage = StagingUsage(
            entries_scanned=file_count + non_file_entries,
            regular_file_count=file_count,
            observed_file_bytes=file_bytes,
            directory_count=non_file_entries,
            symlink_count=0,
            special_file_count=0,
            inventory_complete=True,
            classes=class_usage,
        )

        self.assertEqual(sum(item.regular_file_count for item in usage.classes), file_count)
        self.assertEqual(sum(item.observed_file_bytes for item in usage.classes), file_bytes)
        with self.assertRaises(ValueError):
            StagingUsage(
                entries_scanned=usage.entries_scanned,
                regular_file_count=file_count + 1,
                observed_file_bytes=file_bytes,
                directory_count=non_file_entries,
                symlink_count=0,
                special_file_count=0,
                inventory_complete=True,
                classes=class_usage,
            )

    @settings(max_examples=40, deadline=None, derandomize=True)
    @given(actions=st.lists(st.sampled_from(("block", "defer")), min_size=1, max_size=12))
    def test_generated_open_gate_paths_remain_nonterminal_and_revisioned(
        self, actions: list[str]
    ) -> None:
        """Repeated blocker/defer updates stay visible and never imply completion."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            store = CuratorStore(root / "curator.sqlite3")
            try:
                service = CuratorService(
                    store,
                    ArtifactPurger(stage),
                    _TrustedFixtureEvidence(),
                    project_id="transition-project",
                )
                goal = service.goal_start(
                    "Exercise generated nonterminal lifecycle updates",
                    (SuccessCriterion("proof", "A passing verification exists"),),
                )
                initial_revision = goal.lifecycle_revision

                for index, action in enumerate(actions):
                    if action == "block":
                        goal = service.goal_block(
                            goal.goal_id,
                            f"dependency-{index}",
                            f"recover-{index}",
                        )
                        self.assertEqual(goal.status, GoalStatus.BLOCKED)
                        self.assertEqual(goal.next_action, f"recover-{index}")
                    else:
                        goal = service.goal_defer(
                            goal.goal_id,
                            f"deferred-{index}",
                            f"resume-{index}",
                        )
                        self.assertEqual(goal.status, GoalStatus.DEFERRED)
                        self.assertEqual(goal.next_action, f"resume-{index}")

                    self.assertEqual(
                        goal.lifecycle_revision, initial_revision + index + 1
                    )

                goal = service.goal_finish(goal.goal_id, "Claim that work is done")
                self.assertEqual(goal.status, GoalStatus.OPEN)
                self.assertEqual(
                    goal.lifecycle_revision, initial_revision + len(actions) + 1
                )
                facts = store.list_facts(goal.goal_id)
                transition_bullets = [
                    fact.bullet
                    for fact in facts
                    if fact.kind is FactKind.OPEN_GATE
                    and fact.bullet.startswith(("Blocked:", "Deferred:"))
                ]
                expected_bullets = [
                    (
                        f"Blocked: dependency-{index}; recovery: recover-{index}"
                        if action == "block"
                        else f"Deferred: deferred-{index}; next: resume-{index}"
                    )
                    for index, action in enumerate(actions)
                ]
                self.assertEqual(transition_bullets, expected_bullets)
                self.assertTrue(
                    any(
                        fact.kind is FactKind.COMPLETION_CLAIM
                        for fact in facts
                    )
                )
                outcomes = tuple(
                    fact for fact in facts if fact.kind is FactKind.OUTCOME
                )
                self.assertEqual(tuple(fact.bullet for fact in outcomes), ("open",))
            finally:
                store.close()

    @settings(max_examples=40, deadline=None, derandomize=True)
    @given(
        actions=st.lists(
            st.sampled_from(
                (
                    "activate",
                    "change",
                    "verify",
                    "finish",
                    "block",
                    "defer",
                    "amend",
                    "reopen",
                    "cancel",
                    "supersede",
                )
            ),
            min_size=1,
            max_size=12,
        ),
        initially_planned=st.booleans(),
    )
    def test_generated_lifecycle_sequences_preserve_revision_and_evidence_epoch(
        self, actions: list[str], initially_planned: bool
    ) -> None:
        """Mixed legal/illegal actions preserve the contract across long sequences."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            store = CuratorStore(root / "curator.sqlite3")
            try:
                service = CuratorService(
                    store,
                    ArtifactPurger(stage),
                    _TrustedFixtureEvidence(),
                    project_id="sequence-project",
                )
                goal = service.goal_start(
                    "Fuzz a mixed lifecycle sequence",
                    (SuccessCriterion("criterion-1", "Current epoch is verified"),),
                    initial_status=(
                        GoalStatus.PLANNED
                        if initially_planned
                        else GoalStatus.ACTIVE
                    ),
                )
                state = _LifecycleSequenceState(
                    goal_id=goal.goal_id,
                    status=(
                        GoalStatus.PLANNED
                        if initially_planned
                        else GoalStatus.ACTIVE
                    ),
                    lifecycle_revision=goal.lifecycle_revision,
                    criteria_revision=goal.criteria_revision,
                    criterion_id="criterion-1",
                )

                for index, action in enumerate(actions):
                    before = store.get_goal(state.goal_id)
                    before_facts = store.list_facts(state.goal_id)
                    action_allowed = _lifecycle_action_allowed(state, action)

                    try:
                        _apply_generated_lifecycle_action(
                            service, state, action, index
                        )
                    except ConflictError:
                        self.assertFalse(action_allowed, f"unexpected refusal: {action}")
                        self.assertEqual(store.get_goal(state.goal_id), before)
                        self.assertEqual(
                            store.list_facts(state.goal_id), before_facts
                        )
                    else:
                        self.assertTrue(action_allowed, f"unexpected acceptance: {action}")
                        state.record_success(action)

                    goal = store.get_goal(state.goal_id)
                    self.assertEqual(goal.status, state.status)
                    self.assertEqual(
                        goal.lifecycle_revision, state.lifecycle_revision
                    )
                    self.assertEqual(goal.criteria_revision, state.criteria_revision)
                    self.assertEqual(
                        service.goal_status(goal.goal_id).criteria[0].status.value == "verified",
                        state.epoch_verified,
                    )
            finally:
                store.close()

    @settings(max_examples=40, deadline=None, derandomize=True)
    @given(
        actions=st.lists(
            st.sampled_from(
                (
                    "finish_dependency",
                    "finish_child",
                    "finish_parent",
                    "cancel_dependency",
                    "cancel_child",
                    "cancel_parent",
                )
            ),
            min_size=1,
            max_size=24,
        )
    )
    def test_generated_parent_dependency_sequences_preserve_gates(
        self, actions: list[str]
    ) -> None:
        """Parents and dependents close or retire only after linked work resolves."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            store = CuratorStore(root / "curator.sqlite3")
            try:
                service = CuratorService(
                    store,
                    ArtifactPurger(stage),
                    _TrustedFixtureEvidence(),
                    project_id="relationship-sequence-project",
                )
                state = _create_related_lifecycle_state(service)
                for index, action in enumerate(actions):
                    target = action.removeprefix("finish_").removeprefix("cancel_")
                    is_finish = action.startswith("finish_")
                    before_goals, before_facts = _snapshot_related_goals(store, state)
                    allowed = _related_action_allowed(state, target, is_finish)

                    try:
                        _run_related_action(service, state, target, action, index)
                    except ConflictError:
                        self.assertFalse(allowed, f"unexpected refusal: {action}")
                        _assert_related_goals_unchanged(
                            self, store, state, before_goals, before_facts
                        )
                    else:
                        self.assertTrue(allowed, f"unexpected acceptance: {action}")
                        _advance_related_state(service, state, target, action)

                    _assert_related_goals_match_model(self, store, state)
            finally:
                store.close()

    def test_semantically_distinct_evidence_is_not_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            stage.mkdir()
            store = CuratorStore(root / "curator.sqlite3")
            try:
                service = CuratorService(
                    store,
                    ArtifactPurger(stage),
                    _TrustedFixtureEvidence(),
                    project_id="generated-project",
                )
                service.process_event(
                    EventEnvelope(
                        "evidence-start",
                        "generated-project",
                        GoalStarted(
                            "evidence-goal",
                            "Keep distinct proof references",
                            (SuccessCriterion("proof", "Two independent checks exist"),),
                        ),
                    )
                )
                first_evidence = EvidenceRef(
                    "test", "suite://first", "a" * 64, EvidenceOutcome.PASSED
                )
                second_evidence = EvidenceRef(
                    "test", "suite://second", "b" * 64, EvidenceOutcome.PASSED
                )
                for index, evidence in enumerate((first_evidence, second_evidence)):
                    service.process_event(
                        EventEnvelope(
                            f"evidence-event-{index}",
                            "generated-project",
                            FactRecorded(
                                "evidence-goal",
                                f"evidence-fact-{index}",
                                FactKind.VERIFICATION,
                                "The success criterion passed",
                                criterion_id="proof",
                                evidence=(evidence,),
                            ),
                        )
                    )

                verification_facts = tuple(
                    fact
                    for fact in service.goal_status("evidence-goal").facts
                    if fact.kind is FactKind.VERIFICATION
                )
                self.assertEqual(len(verification_facts), 2)
                self.assertNotEqual(
                    verification_facts[0].evidence, verification_facts[1].evidence
                )
            finally:
                store.close()


class ProjectPathPropertyTests(unittest.TestCase):
    """Generated traversal paths must never escape the configured read scope."""

    @settings(max_examples=40, deadline=None, derandomize=True)
    @given(
        depth=st.integers(min_value=1, max_value=12),
        leaf=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
            min_size=1,
            max_size=48,
        ),
    )
    def test_generated_parent_paths_are_rejected(self, depth: int, leaf: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "consumer"
            for directory in ("src", "docs", "persistence", ".curatormd-v2/staging"):
                (root / directory).mkdir(parents=True, exist_ok=True)
            (root / ".git").mkdir()
            (root / "docs" / "tasks.md").write_text("- [ ] generated path test\n")
            (root / "persistence" / "HISTORY.md").write_text("# History\n")
            (root / CONFIG_FILENAME).write_text(
                'schema_version = 1\nbackend_api_version = 1\n'
                'project_id = "generated-project"\n'
                '[scope]\nread_paths = ["src", "docs"]\n'
                '[checklists]\ntasks = "docs/tasks.md"\n'
                '[evidence]\nadapters = []\n'
                '[staging]\nroot = ".curatormd-v2/staging"\n'
                '[persistence]\ntargets = ["persistence/HISTORY.md"]\n'
            )
            (root / CONFIG_FILENAME).chmod(0o600)
            config = ProjectConfig.load(root)

            with self.assertRaises(ProjectConfigError):
                config.resolve_read_path("../" * depth + leaf)


if __name__ == "__main__":
    unittest.main()
