"""Deterministic generated cases for parser, lifecycle, replay, and path invariants."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from hypothesis import given, settings, strategies as st

from evidence_fixtures import attest_test_evidence

from curatormd_v2 import (
    ArtifactPurger,
    ConflictError,
    CuratorService,
    GoalStatus,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    FactRecorded,
    GoalFinishRequested,
    GoalStarted,
)
from curatormd_v2.models import EvidenceOutcome, EvidenceRef, FactKind
from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.project_config import CONFIG_FILENAME, ProjectConfig, ProjectConfigError
from curatormd_v2.store import CuratorStore


SAFE = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"


class _TrustedFixtureEvidence:
    """Accept only the two explicit local references used by this regression."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only explicit local evidence references emitted by tests."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator in {"suite://first", "suite://second"}
            else None
        )


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
                expected_bullets: list[str] = []

                for index, action in enumerate(actions):
                    if action == "block":
                        dependency = f"dependency-{index}"
                        recovery = f"recover-{index}"
                        goal = service.goal_block(goal.goal_id, dependency, recovery)
                        expected_bullets.append(
                            f"Blocked: {dependency}; recovery: {recovery}"
                        )
                        self.assertEqual(goal.status, GoalStatus.BLOCKED)
                        self.assertEqual(goal.next_action, recovery)
                    else:
                        reason = f"deferred-{index}"
                        next_action = f"resume-{index}"
                        goal = service.goal_defer(goal.goal_id, reason, next_action)
                        expected_bullets.append(
                            f"Deferred: {reason}; next: {next_action}"
                        )
                        self.assertEqual(goal.status, GoalStatus.DEFERRED)
                        self.assertEqual(goal.next_action, next_action)

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
                initial_status = (
                    GoalStatus.PLANNED if initially_planned else GoalStatus.ACTIVE
                )
                goal = service.goal_start(
                    "Fuzz a mixed lifecycle sequence",
                    (SuccessCriterion("criterion-1", "Current epoch is verified"),),
                    initial_status=initial_status,
                )
                expected_status = initial_status
                expected_lifecycle_revision = goal.lifecycle_revision
                expected_criteria_revision = goal.criteria_revision
                current_criterion_id = "criterion-1"
                current_epoch_verified = False

                for index, action in enumerate(actions):
                    before = store.get_goal(goal.goal_id)
                    before_facts = store.list_facts(goal.goal_id)
                    unfinished = expected_status in {
                        GoalStatus.PLANNED,
                        GoalStatus.ACTIVE,
                        GoalStatus.OPEN,
                        GoalStatus.BLOCKED,
                        GoalStatus.DEFERRED,
                    }
                    fact_allowed = expected_status in {
                        GoalStatus.ACTIVE,
                        GoalStatus.OPEN,
                        GoalStatus.BLOCKED,
                        GoalStatus.DEFERRED,
                    }
                    action_allowed = {
                        "activate": expected_status is GoalStatus.PLANNED,
                        "change": fact_allowed,
                        "verify": fact_allowed,
                        "finish": expected_status in {
                            GoalStatus.ACTIVE,
                            GoalStatus.OPEN,
                            GoalStatus.BLOCKED,
                            GoalStatus.DEFERRED,
                            GoalStatus.COMPLETE,
                        },
                        "block": unfinished,
                        "defer": unfinished,
                        "amend": unfinished,
                        "reopen": expected_status is GoalStatus.COMPLETE,
                        "cancel": unfinished,
                        "supersede": unfinished,
                    }[action]

                    try:
                        if action == "activate":
                            service.goal_activate(
                                goal.goal_id,
                                f"Generated acceptance {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "change":
                            service.goal_fact(
                                goal.goal_id,
                                FactKind.CHANGE,
                                f"Generated change {index}",
                            )
                        elif action == "verify":
                            service.goal_fact(
                                goal.goal_id,
                                FactKind.VERIFICATION,
                                f"Generated verification {index}",
                                criterion_id=current_criterion_id,
                                evidence=(
                                    EvidenceRef(
                                        "test",
                                        "suite://first",
                                        "a" * 64,
                                        EvidenceOutcome.PASSED,
                                    ),
                                ),
                            )
                        elif action == "finish":
                            service.goal_finish(
                                goal.goal_id,
                                f"Generated completion claim {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "block":
                            service.goal_block(
                                goal.goal_id,
                                f"Generated dependency {index}",
                                f"Generated recovery {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "defer":
                            service.goal_defer(
                                goal.goal_id,
                                f"Generated deferral {index}",
                                f"Generated next action {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "amend":
                            next_criterion_id = (
                                f"criterion-{expected_criteria_revision + 1}"
                            )
                            service.goal_amend_criteria(
                                goal.goal_id,
                                expected_criteria_revision,
                                (
                                    SuccessCriterion(
                                        next_criterion_id,
                                        f"Generated amended criterion {index}",
                                    ),
                                ),
                                f"Generated amendment {index}",
                                f"Verify amended criterion {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "reopen":
                            service.goal_reopen(
                                goal.goal_id,
                                f"Generated reopen {index}",
                                f"Reverify epoch {index}",
                                expected_lifecycle_revision,
                            )
                        elif action == "cancel":
                            service.goal_cancel(
                                goal.goal_id, f"Generated cancellation {index}"
                            )
                        else:
                            replacement = service.goal_start(
                                f"Generated successor {index}",
                                (
                                    SuccessCriterion(
                                        f"successor-{index}", "Successor is verified"
                                    ),
                                ),
                            )
                            service.goal_supersede(
                                goal.goal_id,
                                replacement.goal_id,
                                f"Generated supersession {index}",
                            )
                    except ConflictError:
                        self.assertFalse(action_allowed, f"unexpected refusal: {action}")
                        self.assertEqual(store.get_goal(goal.goal_id), before)
                        self.assertEqual(store.list_facts(goal.goal_id), before_facts)
                    else:
                        self.assertTrue(action_allowed, f"unexpected acceptance: {action}")
                        if action == "activate":
                            expected_status = GoalStatus.ACTIVE
                            expected_lifecycle_revision += 1
                        elif action in {"change", "verify"}:
                            if action == "verify":
                                current_epoch_verified = True
                        elif action == "finish":
                            if expected_status is not GoalStatus.COMPLETE:
                                expected_status = (
                                    GoalStatus.COMPLETE
                                    if current_epoch_verified
                                    else GoalStatus.OPEN
                                )
                                expected_lifecycle_revision += 1
                        elif action == "block":
                            expected_status = GoalStatus.BLOCKED
                            expected_lifecycle_revision += 1
                        elif action == "defer":
                            expected_status = GoalStatus.DEFERRED
                            expected_lifecycle_revision += 1
                        elif action == "amend":
                            expected_criteria_revision += 1
                            current_criterion_id = (
                                f"criterion-{expected_criteria_revision}"
                            )
                            current_epoch_verified = False
                            expected_lifecycle_revision += 1
                        elif action == "reopen":
                            expected_status = GoalStatus.ACTIVE
                            current_epoch_verified = False
                            expected_lifecycle_revision += 1
                        elif action == "cancel":
                            expected_status = GoalStatus.CANCELLED
                            expected_lifecycle_revision += 1
                        else:
                            expected_status = GoalStatus.SUPERSEDED
                            expected_lifecycle_revision += 1

                    goal = store.get_goal(goal.goal_id)
                    self.assertEqual(goal.status, expected_status)
                    self.assertEqual(
                        goal.lifecycle_revision, expected_lifecycle_revision
                    )
                    self.assertEqual(goal.criteria_revision, expected_criteria_revision)
                    self.assertEqual(
                        service.goal_status(goal.goal_id).criteria[0].status.value
                        == "verified",
                        current_epoch_verified,
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
                criteria = {
                    "dependency": SuccessCriterion("dependency", "Dependency passes"),
                    "child": SuccessCriterion("child", "Child passes"),
                    "parent": SuccessCriterion("parent", "Parent passes"),
                }
                dependency = service.goal_start(
                    "Generated prerequisite", (criteria["dependency"],)
                )
                parent = service.goal_start(
                    "Generated parent", (criteria["parent"],)
                )
                child = service.goal_start(
                    "Generated child",
                    (criteria["child"],),
                    parent_goal_id=parent.goal_id,
                    depends_on_goal_ids=(dependency.goal_id,),
                )
                goals = {
                    "dependency": dependency,
                    "child": child,
                    "parent": parent,
                }
                for label, goal in goals.items():
                    service.goal_fact(
                        goal.goal_id,
                        FactKind.VERIFICATION,
                        f"Generated {label} criterion passed",
                        criterion_id=criteria[label].criterion_id,
                        evidence=(
                            EvidenceRef(
                                "test",
                                "suite://first",
                                "a" * 64,
                                EvidenceOutcome.PASSED,
                            ),
                        ),
                    )

                expected = {
                    "dependency": GoalStatus.ACTIVE,
                    "child": GoalStatus.ACTIVE,
                    "parent": GoalStatus.ACTIVE,
                }
                revisions = {
                    label: goal.lifecycle_revision for label, goal in goals.items()
                }
                for index, action in enumerate(actions):
                    target = action.removeprefix("finish_").removeprefix("cancel_")
                    before_goals = {
                        label: store.get_goal(goal.goal_id)
                        for label, goal in goals.items()
                    }
                    before_facts = {
                        label: store.list_facts(goal.goal_id)
                        for label, goal in goals.items()
                    }
                    target_status = expected[target]
                    is_finish = action.startswith("finish_")
                    unfinished = target_status in {
                        GoalStatus.PLANNED,
                        GoalStatus.ACTIVE,
                        GoalStatus.OPEN,
                        GoalStatus.BLOCKED,
                        GoalStatus.DEFERRED,
                    }
                    if is_finish:
                        allowed = unfinished or target_status is GoalStatus.COMPLETE
                    else:
                        allowed = unfinished
                        if target == "dependency" and unfinished:
                            allowed = expected["child"] not in {
                                GoalStatus.PLANNED,
                                GoalStatus.ACTIVE,
                                GoalStatus.OPEN,
                                GoalStatus.BLOCKED,
                                GoalStatus.DEFERRED,
                            }
                        elif target == "parent" and unfinished:
                            allowed = expected["child"] in {
                                GoalStatus.COMPLETE,
                                GoalStatus.CANCELLED,
                                GoalStatus.SUPERSEDED,
                            }

                    try:
                        if is_finish:
                            service.goal_finish(
                                goals[target].goal_id,
                                f"Generated {target} finish {index}",
                                revisions[target],
                            )
                        else:
                            service.goal_cancel(
                                goals[target].goal_id,
                                f"Generated {target} cancellation {index}",
                            )
                    except ConflictError:
                        self.assertFalse(allowed, f"unexpected refusal: {action}")
                        for label, goal in goals.items():
                            self.assertEqual(store.get_goal(goal.goal_id), before_goals[label])
                            self.assertEqual(store.list_facts(goal.goal_id), before_facts[label])
                    else:
                        self.assertTrue(allowed, f"unexpected acceptance: {action}")
                        if is_finish:
                            if target_status is not GoalStatus.COMPLETE:
                                is_verified = service.goal_status(
                                    goals[target].goal_id
                                ).criteria[0].status.value == "verified"
                                has_open_related_work = (
                                    target == "child"
                                    and expected["dependency"] is not GoalStatus.COMPLETE
                                ) or (
                                    target == "parent"
                                    and expected["child"]
                                    not in {
                                        GoalStatus.COMPLETE,
                                        GoalStatus.CANCELLED,
                                        GoalStatus.SUPERSEDED,
                                    }
                                )
                                expected[target] = (
                                    GoalStatus.COMPLETE
                                    if is_verified and not has_open_related_work
                                    else GoalStatus.OPEN
                                )
                                revisions[target] += 1
                        else:
                            expected[target] = GoalStatus.CANCELLED
                            revisions[target] += 1

                    for label, goal in goals.items():
                        actual = store.get_goal(goal.goal_id)
                        self.assertEqual(actual.status, expected[label])
                        self.assertEqual(actual.lifecycle_revision, revisions[label])
                        if label == "child" and actual.status is GoalStatus.OPEN:
                            self.assertIn(
                                dependency.goal_id, actual.next_action or ""
                            )
                        if label == "parent" and actual.status is GoalStatus.OPEN:
                            self.assertIn(child.goal_id, actual.next_action or "")
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
