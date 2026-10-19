"""Safety and mapping tests for the proposed Hermes Codex event adapter."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from curatormd_v2 import (
    CodexGoalBinding,
    ArtifactPurger,
    CuratorService,
    CuratorStore,
    DurableEventRouter,
    EventEnvelope,
    FactKind,
    GoalActivityObserved,
    GoalStarted,
    GoalStatus,
    SuccessCriterion,
    codex_hook_to_event,
)


class HermesCodexEventTests(unittest.TestCase):
    """Keep the Hermes translation bound, compact, and non-verifying."""

    def setUp(self) -> None:
        self.binding = CodexGoalBinding(
            profile_id="gptmd-coding",
            project_id="gptmd",
            session_id="session-1",
            goal_id="goal-1",
            source_id="hermes.gptmd-coding",
        )

    def test_turn_start_maps_to_bound_intent_without_runtime_metadata(self) -> None:
        event = codex_hook_to_event(
            "codex:turn:start",
            {
                "attempt_id": "attempt-1",
                "session_id": "session-1",
                "model": "gpt-6-luna",
                "provider": "openai-codex",
                "cwd": "/work/gptmd",
            },
            self.binding,
            source_sequence=1,
            occurred_at="2026-10-19T00:00:00+00:00",
        )

        self.assertEqual(event.project_id, "gptmd")
        self.assertEqual(event.source_id, "hermes.gptmd-coding")
        self.assertEqual(event.source_sequence, 1)
        self.assertRegex(event.event_id, r"^hermes-[0-9a-f]{64}$")
        assert isinstance(event.payload, GoalActivityObserved)
        self.assertEqual(
            event.payload,
            GoalActivityObserved(
                goal_id="goal-1",
                fact_id=event.payload.fact_id,
                kind=FactKind.INTENT,
                bullet="Codex turn started for the explicitly bound goal.",
            ),
        )
        serialized = event.to_json()
        for private_or_transient in (
            "attempt-1",
            "session-1",
            "gpt-6-luna",
            "openai-codex",
            "/work/gptmd",
        ):
            self.assertNotIn(private_or_transient, serialized)
        self.assertEqual(EventEnvelope.from_json(serialized), event)
        replay = codex_hook_to_event(
            "codex:turn:start",
            {
                "attempt_id": "attempt-1",
                "session_id": "session-1",
                "model": "gpt-6-luna",
                "provider": "openai-codex",
                "cwd": "/work/gptmd",
            },
            self.binding,
            source_sequence=1,
            occurred_at="2026-10-19T00:00:00+00:00",
        )
        self.assertEqual(replay.to_json(), serialized)

    def test_normal_turn_end_is_a_change_not_verification_or_completion(self) -> None:
        event = codex_hook_to_event(
            "codex:turn:end",
            {
                "attempt_id": "attempt-1",
                "session_id": "session-1",
                "turn_id": "turn-1",
                "outcome": "completed",
            },
            self.binding,
            source_sequence=2,
            occurred_at="2026-10-19T00:01:00+00:00",
        )

        self.assertEqual(event.event_kind.value, "goal.activity_observed")
        assert isinstance(event.payload, GoalActivityObserved)
        self.assertEqual(event.payload.kind, FactKind.CHANGE)
        self.assertIn("no success criterion was verified", event.payload.bullet)
        self.assertNotIn("turn-1", event.to_json())

    def test_failed_or_interrupted_turn_remains_an_open_gate(self) -> None:
        for outcome in ("failed", "interrupted"):
            with self.subTest(outcome=outcome):
                event = codex_hook_to_event(
                    "codex:turn:end",
                    {
                        "attempt_id": "attempt-1",
                        "session_id": "session-1",
                        "turn_id": "turn-1",
                        "outcome": outcome,
                        "failure_kind": "exception",
                    },
                    self.binding,
                    source_sequence=3,
                    occurred_at="2026-10-19T00:02:00+00:00",
                )
                assert isinstance(event.payload, GoalActivityObserved)
                self.assertEqual(event.payload.kind, FactKind.OPEN_GATE)
                self.assertIn(outcome, event.payload.bullet)
                self.assertNotIn("exception", event.to_json())

    def test_mapping_fails_closed_on_missing_or_mismatched_binding_context(self) -> None:
        base = {"attempt_id": "attempt-1", "session_id": "session-1"}
        with self.assertRaisesRegex(ValueError, "session does not match"):
            codex_hook_to_event(
                "codex:turn:start",
                {**base, "session_id": "another-session"},
                self.binding,
                source_sequence=1,
                occurred_at="2026-10-19T00:00:00+00:00",
            )
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            codex_hook_to_event(
                "codex:turn:start",
                {**base, "prompt": "must never be forwarded"},
                self.binding,
                source_sequence=1,
                occurred_at="2026-10-19T00:00:00+00:00",
            )
        with self.assertRaisesRegex(ValueError, "session_id.*bounded opaque"):
            CodexGoalBinding(
                profile_id="gptmd-coding",
                project_id="gptmd",
                session_id="",
                goal_id="goal-1",
                source_id="hermes.gptmd-coding",
            )

    def test_turn_end_and_sequence_are_strictly_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "supported runtime outcome"):
            codex_hook_to_event(
                "codex:turn:end",
                {
                    "attempt_id": "attempt-1",
                    "session_id": "session-1",
                    "turn_id": "turn-1",
                    "outcome": "verified",
                },
                self.binding,
                source_sequence=1,
                occurred_at="2026-10-19T00:00:00+00:00",
            )
        with self.assertRaisesRegex(ValueError, "positive integer"):
            codex_hook_to_event(
                "codex:turn:start",
                {"attempt_id": "attempt-1", "session_id": "session-1"},
                self.binding,
                source_sequence=True,
                occurred_at="2026-10-19T00:00:00+00:00",
            )

    def test_projected_hooks_route_into_the_bound_goal_as_compact_facts(self) -> None:
        """Exercise the mapper, inbox, ordered router, and goal ledger together."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(root / "global.sqlite3")
            try:
                service = CuratorService(
                    store, ArtifactPurger(staging), project_id="gptmd"
                )
                router = DurableEventRouter(store, {"gptmd": service})
                store.ingest_event(
                    EventEnvelope(
                        "intake-goal-1",
                        "gptmd",
                        GoalStarted(
                            "goal-1",
                            "Exercise the explicit Hermes turn binding",
                            (SuccessCriterion("check", "Turn facts remain non-verifying"),),
                            initial_status=GoalStatus.ACTIVE,
                        ),
                        source_id="user-intake",
                    )
                )
                self.assertEqual(router.route_once().processed_count, 1)

                start = codex_hook_to_event(
                    "codex:turn:start",
                    {"attempt_id": "attempt-1", "session_id": "session-1"},
                    self.binding,
                    source_sequence=1,
                    occurred_at="2026-10-19T00:00:00+00:00",
                )
                end = codex_hook_to_event(
                    "codex:turn:end",
                    {
                        "attempt_id": "attempt-1",
                        "session_id": "session-1",
                        "turn_id": "turn-1",
                        "outcome": "completed",
                    },
                    self.binding,
                    source_sequence=2,
                    occurred_at="2026-10-19T00:01:00+00:00",
                )
                self.assertTrue(store.ingest_event(start)[1])
                self.assertTrue(store.ingest_event(end)[1])
                self.assertEqual(router.route_once().processed_count, 1)
                self.assertEqual(router.route_once().processed_count, 1)
                snapshot = service.goal_status("goal-1")
                self.assertEqual(
                    [fact.kind for fact in snapshot.facts],
                    [FactKind.INTENT, FactKind.CHANGE],
                )
                self.assertTrue(
                    all(fact.criterion_id is None for fact in snapshot.facts)
                )
                self.assertNotEqual(snapshot.goal.status, GoalStatus.COMPLETE)

                duplicate, inserted = store.ingest_event(start)
                self.assertFalse(inserted)
                self.assertEqual(duplicate.status.value, "processed")
                self.assertEqual(len(service.goal_status("goal-1").facts), 2)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
