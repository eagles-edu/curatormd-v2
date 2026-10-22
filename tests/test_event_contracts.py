"""Tests for bounded, versioned lifecycle event contracts."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from curatormd_v2.events import (
    EVENT_SCHEMA_VERSION,
    MAX_EVENT_BYTES,
    EventEnvelope,
    FactRecorded,
    GoalActivated,
    GoalCancelled,
    GoalCriteriaAmended,
    GoalReopened,
    GoalStarted,
    GoalSuperseded,
)
from curatormd_v2 import GoalStatus
from curatormd_v2.models import EvidenceOutcome, EvidenceRef, FactKind, SuccessCriterion


class EventContractTests(unittest.TestCase):
    """Validate strict serialization and bounds for lifecycle events."""

    def test_goal_start_round_trips_with_project_scope_and_criteria(self) -> None:
        """Round-trip a goal without changing its project or criteria."""

        event = EventEnvelope(
            event_id="evt-1",
            project_id="gptmd",
            payload=GoalStarted(
                goal_id="goal-1",
                problem="Add the readiness route",
                success_criteria=(SuccessCriterion("ready", "Readiness returns ready"),),
                owner="gptmd-coding",
                checklist_id="ops-12",
                checklist_version="sha256:" + "a" * 64,
                checklist_source_text="- [ ] Add readiness endpoint",
                parent_goal_id="release-goal",
                depends_on_goal_ids=("config-goal",),
                initial_status=GoalStatus.PLANNED,
                next_action="Inspect the readiness route contract",
            ),
        )

        decoded = EventEnvelope.from_json(event.to_json())

        self.assertEqual(decoded, event)
        self.assertEqual(decoded.schema_version, EVENT_SCHEMA_VERSION)
        self.assertEqual(decoded.event_kind.value, "goal.started")
        assert isinstance(decoded.payload, GoalStarted)
        self.assertEqual(decoded.payload.checklist_source_text, "- [ ] Add readiness endpoint")
        self.assertEqual(decoded.payload.checklist_version, "sha256:" + "a" * 64)
        self.assertEqual(decoded.payload.parent_goal_id, "release-goal")
        self.assertEqual(decoded.payload.depends_on_goal_ids, ("config-goal",))
        self.assertEqual(decoded.payload.next_action, "Inspect the readiness route contract")

    def test_published_event_v1_fixture_is_accepted_by_the_runtime_parser(self) -> None:
        """Keep the published example synchronized with the strict parser."""

        fixture = (
            Path(__file__).resolve().parents[1]
            / "docs/examples/event-v1-goal-started.json"
        )
        event = EventEnvelope.from_json(fixture.read_text(encoding="utf-8"))

        self.assertEqual(event.schema_version, 1)
        self.assertEqual(event.project_id, "gptmd")
        self.assertEqual(event.source_id, "gptmd-coding")
        self.assertEqual(EventEnvelope.from_json(event.to_json()), event)
        self.assertIsInstance(event.payload, GoalStarted)

    def test_planned_goal_start_and_activation_round_trip(self) -> None:
        """Carry planned status and explicit revision-fenced acceptance."""

        planned_start = EventEnvelope(
            "plan-1",
            "project-a",
            GoalStarted(
                "goal-planned",
                "Capture work before execution",
                (SuccessCriterion("proof", "The result has passing evidence"),),
                initial_status=GoalStatus.PLANNED,
            ),
        )
        activation = EventEnvelope(
            "activate-1",
            "project-a",
            GoalActivated("goal-planned", "User approved implementation", 1),
        )
        self.assertEqual(EventEnvelope.from_json(planned_start.to_json()), planned_start)
        self.assertEqual(EventEnvelope.from_json(activation.to_json()), activation)

    def test_goal_start_rejects_blank_multiline_or_oversized_next_action(self) -> None:
        """Intake actions must stay explicit and compact when supplied."""

        for action in ("", " \t ", "first step\nsecond step", "x" * 1001):
            with self.subTest(action=action[:24]), self.assertRaises(ValueError):
                GoalStarted(
                    "goal-action",
                    "Start a goal with an optional next step",
                    (SuccessCriterion("done", "The step remains bounded"),),
                    next_action=action,
                )

    def test_fact_event_round_trips_evidence_reference_without_raw_output(self) -> None:
        """Preserve evidence references without accepting raw output fields."""

        evidence = EvidenceRef(
            evidence_kind="test",
            locator="pytest://test_readyz",
            sha256="a" * 64,
            outcome=EvidenceOutcome.PASSED,
        )
        event = EventEnvelope(
            event_id="evt-2",
            project_id="gptmd",
            payload=FactRecorded(
                goal_id="goal-1",
                fact_id="fact-1",
                kind=FactKind.VERIFICATION,
                bullet="Readiness test passed",
                criterion_id="ready",
                evidence=(evidence,),
            ),
        )

        decoded = EventEnvelope.from_json(event.to_json())

        self.assertEqual(decoded, event)
        self.assertNotIn("raw output", event.to_json())

    def test_goal_reopen_event_round_trips_with_reason_and_next_action(self) -> None:
        event = EventEnvelope(
            "evt-reopen-1",
            "project-a",
            GoalReopened(
                "goal-1", "A post-release issue was found", "Rerun checks", 7
            ),
        )

        decoded = EventEnvelope.from_json(event.to_json())

        self.assertEqual(decoded, event)
        self.assertEqual(decoded.event_kind.value, "goal.reopened")
        assert isinstance(decoded.payload, GoalReopened)
        self.assertEqual(
            decoded.payload.expected_lifecycle_revision, 7
        )

    def test_cancel_and_supersede_events_round_trip(self) -> None:
        for payload, expected_kind in (
            (GoalCancelled("goal-old", "Scope was withdrawn"), "goal.cancelled"),
            (
                GoalSuperseded("goal-old", "goal-new", "Use the revised task"),
                "goal.superseded",
            ),
        ):
            event = EventEnvelope("evt-retire", "project-a", payload)
            decoded = EventEnvelope.from_json(event.to_json())
            self.assertEqual(decoded, event)
            self.assertEqual(decoded.event_kind.value, expected_kind)

    def test_goal_criteria_amendment_round_trips_with_revision_guard(self) -> None:
        event = EventEnvelope(
            "evt-amend-1",
            "project-a",
            GoalCriteriaAmended(
                "goal-1",
                2,
                (SuccessCriterion("ready", "Readiness returns healthy"),),
                "The owner clarified the acceptance condition",
                "Run the readiness probe",
                3,
            ),
        )

        decoded = EventEnvelope.from_json(event.to_json())

        self.assertEqual(decoded, event)
        self.assertEqual(decoded.event_kind.value, "goal.criteria_amended")

    def test_reopened_fact_cannot_be_forged_as_ordinary_fact_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "goal.reopened event"):
            FactRecorded(
                "goal-1",
                "fact-reopen-forged",
                FactKind.REOPENED,
                "Reopened without the lifecycle transition",
            )

        with self.assertRaisesRegex(ValueError, "goal.criteria_amended"):
            FactRecorded(
                "goal-1",
                "fact-amend-forged",
                FactKind.CRITERIA_AMENDED,
                "Criteria changed without a revision transition",
            )

    def test_research_advice_and_proposal_are_distinct_nonverification_facts(self) -> None:
        """Do not conflate plans and recommendations with implementation proof."""

        for kind in (FactKind.RESEARCH, FactKind.ADVICE, FactKind.PROPOSAL):
            with self.subTest(kind=kind):
                event = EventEnvelope(
                    f"evt-{kind.value}",
                    "gptmd",
                    FactRecorded("goal-1", f"fact-{kind.value}", kind, "Compact note"),
                )
                decoded = EventEnvelope.from_json(event.to_json())
                self.assertEqual(decoded.payload, event.payload)
                self.assertIsNot(kind, FactKind.VERIFICATION)

    def test_rejects_unknown_fields_and_duplicate_json_keys(self) -> None:
        """Reject ambiguous or unversioned extensions to the envelope."""

        event = EventEnvelope(
            event_id="evt-3",
            project_id="gptmd",
            payload=GoalStarted(
                goal_id="goal-1",
                problem="Add a route",
                success_criteria=(SuccessCriterion("r", "Route works"),),
            ),
        )
        extra = event.to_dict()
        extra["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            EventEnvelope.from_json(json.dumps(extra))
        duplicate_field = "PRIVATE_EVENT_CANARY"
        with self.assertRaisesRegex(ValueError, "duplicate JSON field") as raised:
            EventEnvelope.from_json(
                '{"schema_version":1,"PRIVATE_EVENT_CANARY":1,'
                '"PRIVATE_EVENT_CANARY":1,"event_id":"e",'
                '"project_id":"p","occurred_at":"2026-10-18T00:00:00+00:00",'
                '"event_type":"goal.started","payload":{}}'
            )
        self.assertNotIn(duplicate_field, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_event_json_does_not_retain_raw_source_in_exception(self) -> None:
        """Sanitized decoder errors must not retain raw JSON through chaining."""

        source = '{"problem":"PRIVATE_EVENT_CANARY", invalid'
        with self.assertRaisesRegex(ValueError, "valid UTF-8 JSON") as raised:
            EventEnvelope.from_json(source)
        self.assertNotIn("PRIVATE_EVENT_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_utf8_does_not_retain_raw_source_in_exception(self) -> None:
        """Sanitized size errors must not retain the invalid source string."""

        source = "PRIVATE_EVENT_CANARY\ud800"
        with self.assertRaisesRegex(ValueError, "valid UTF-8") as raised:
            EventEnvelope.from_json(source)
        self.assertNotIn("PRIVATE_EVENT_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_invalid_timestamp_does_not_retain_raw_source_in_exception(self) -> None:
        """Timestamp parser errors must not retain caller-controlled values."""

        with self.assertRaisesRegex(ValueError, "ISO-8601 timestamp") as raised:
            EventEnvelope(
                "timestamp-event",
                "project",
                GoalStarted(
                    "timestamp-goal",
                    "Test timestamp handling",
                    (SuccessCriterion("done", "The invalid input is rejected"),),
                ),
                occurred_at="PRIVATE_TIMESTAMP_CANARY",
            )
        self.assertNotIn("PRIVATE_TIMESTAMP_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_unknown_event_type_does_not_retain_raw_value_in_exception(self) -> None:
        """Enum parser errors must not chain the rejected event type."""

        source = (
            '{"schema_version":1,"event_id":"e","project_id":"p",'
            '"occurred_at":"2026-10-18T00:00:00+00:00",'
            '"event_type":"PRIVATE_EVENT_TYPE_CANARY","payload":{}}'
        )
        with self.assertRaisesRegex(ValueError, "unknown event type") as raised:
            EventEnvelope.from_json(source)
        self.assertNotIn("PRIVATE_EVENT_TYPE_CANARY", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_rejects_invalid_project_id_version_and_naive_timestamp(self) -> None:
        """Require bounded project IDs, supported versions, and timezone."""

        criteria = (SuccessCriterion("r", "Route works"),)
        with self.assertRaisesRegex(ValueError, "project_id"):
            EventEnvelope("evt", "../other", GoalStarted("g", "problem", criteria))
        with self.assertRaisesRegex(ValueError, "schema version"):
            EventEnvelope("evt", "project", GoalStarted("g", "problem", criteria), schema_version=2)
        with self.assertRaisesRegex(ValueError, "timezone"):
            EventEnvelope(
                "evt",
                "project",
                GoalStarted("g", "problem", criteria),
                occurred_at="2026-10-18T00:00:00",
            )

    def test_rejects_sensitive_event_ids_before_receipt_retention(self) -> None:
        """Do not retain a credential-like string as an opaque source ID."""

        with self.assertRaisesRegex(ValueError, "sensitive content rejected in event_id"):
            EventEnvelope(
                "sk-" + "A" * 24,
                "project",
                GoalStarted(
                    "goal-safe-id",
                    "Keep credential-like identifiers out of receipts",
                    (SuccessCriterion("done", "The event is rejected"),),
                ),
            )

    def test_source_identity_sequence_and_legacy_defaults(self) -> None:
        """Validate producer ordering fields and keep old V1 payloads readable."""

        event = EventEnvelope(
            "ordered-1",
            "project-a",
            GoalStarted("goal-1", "problem", (SuccessCriterion("done", "Done"),)),
            source_id="hermes-profile-a",
            source_sequence=1,
        )
        self.assertEqual(EventEnvelope.from_json(event.to_json()), event)

        old_payload = event.to_dict()
        old_payload.pop("source_id")
        old_payload.pop("source_sequence")
        legacy = EventEnvelope.from_json(json.dumps(old_payload))
        self.assertEqual(legacy.source_id, "unspecified")
        self.assertIsNone(legacy.source_sequence)

        with self.assertRaisesRegex(ValueError, "source_id"):
            EventEnvelope(
                "event", "project-a", event.payload, source_id="../invalid"
            )
        with self.assertRaisesRegex(ValueError, "explicit source_id"):
            EventEnvelope(
                "event", "project-a", event.payload, source_sequence=1
            )
        for invalid_sequence in (0, -1, True):
            with self.subTest(sequence=invalid_sequence):
                with self.assertRaisesRegex(ValueError, "source_sequence"):
                    EventEnvelope(
                        "event",
                        "project-a",
                        event.payload,
                        source_sequence=invalid_sequence,
                    )

    def test_rejects_unbounded_serialized_event(self) -> None:
        """Apply the byte budget both on encode and before decoding."""

        event = EventEnvelope(
            event_id="evt",
            project_id="project",
            payload=GoalStarted(
                goal_id="goal",
                problem="x" * 2000,
                success_criteria=(SuccessCriterion("r", "Route works"),),
            ),
        )
        # The domain cap permits this text, but the complete envelope has its own
        # stricter transport budget.
        too_large = EventEnvelope(
            event_id="evt",
            project_id="project",
            payload=GoalStarted(
                goal_id="goal",
                problem="x" * 1900,
                success_criteria=tuple(
                    SuccessCriterion(f"criterion-{index}", "y" * 500)
                    for index in range(30)
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, str(MAX_EVENT_BYTES)):
            too_large.to_json()
        with self.assertRaisesRegex(ValueError, str(MAX_EVENT_BYTES)):
            EventEnvelope.from_json(" " * (MAX_EVENT_BYTES + 1))
        self.assertLessEqual(len(event.to_json().encode("utf-8")), MAX_EVENT_BYTES)
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            EventEnvelope.from_json("\ud800")

    def test_verification_event_requires_criterion_and_evidence(self) -> None:
        """Refuse verification claims without evidence and a linked criterion."""

        with self.assertRaisesRegex(ValueError, "evidence references"):
            FactRecorded("g", "f", FactKind.VERIFICATION, "passed", "criterion")
        with self.assertRaisesRegex(ValueError, "success criterion"):
            FactRecorded(
                "g",
                "f",
                FactKind.VERIFICATION,
                "passed",
                evidence=(
                    EvidenceRef("test", "suite://test", "b" * 64, EvidenceOutcome.PASSED),
                ),
            )
