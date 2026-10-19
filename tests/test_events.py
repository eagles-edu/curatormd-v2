"""Tests for bounded, versioned lifecycle event contracts."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence

from curatormd_v2.events import (
    EVENT_SCHEMA_VERSION,
    MAX_EVENT_BYTES,
    EventEnvelope,
    FactRecorded,
    GoalActivated,
    GoalBlocked,
    GoalCancelled,
    GoalDeferred,
    GoalFinishRequested,
    GoalReopened,
    GoalCriteriaAmended,
    GoalSuperseded,
    GoalStarted,
)
from curatormd_v2 import (
    ArtifactPurger,
    CuratorService,
    EventOrderError,
    EvidenceVerificationContext,
    GoalStatus,
)
from curatormd_v2.store import (
    ConflictError,
    CuratorStore,
    EventInboxCapacityError,
    NotFoundError,
)
from curatormd_v2.models import (
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    SuccessCriterion,
)


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
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            EventEnvelope.from_json(
                '{"schema_version":1,"schema_version":1,"event_id":"e",'
                '"project_id":"p","occurred_at":"2026-10-18T00:00:00+00:00",'
                '"event_type":"goal.started","payload":{}}'
            )

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


class EventInboxTests(unittest.TestCase):
    """Check durable event acceptance and compact replay receipts."""

    def setUp(self) -> None:
        self.temp_dir = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.database = Path(self.temp_dir) / "curator.sqlite3"
        self.stage = Path(self.temp_dir) / "stage"
        self.stage.mkdir()
        self.store = CuratorStore(self.database)
        self.addCleanup(self.store.close)
        self.service = CuratorService(
            self.store, ArtifactPurger(self.stage), project_id="project-a"
        )
        self.event = EventEnvelope(
            event_id="stable-event-1",
            project_id="project-a",
            payload=GoalStarted(
                goal_id="goal-1",
                problem="Record project task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
                checklist_id="tasks",
                checklist_version="sha256:" + "b" * 64,
                checklist_source_text="- [ ] Record project task",
            ),
        )

    def test_acceptance_is_durable_and_same_event_id_is_idempotent(self) -> None:
        """Persist one acceptance and reuse it after store restart."""

        first, inserted_first = self.store.ingest_event(self.event)
        second, inserted_second = self.store.ingest_event(self.event)

        self.assertTrue(inserted_first)
        self.assertFalse(inserted_second)
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)

        self.store.close()
        reopened = CuratorStore(self.database)
        try:
            self.assertEqual(
                reopened.event_receipt("project-a", "stable-event-1"), first
            )
            self.assertEqual(len(reopened.pending_events(project_id="project-a")), 1)
        finally:
            reopened.close()

    def test_cancel_and_supersede_are_idempotent_lifecycle_events(self) -> None:
        self.service.process_event(self.event)
        cancelled_event = EventEnvelope(
            "cancel-goal-event",
            "project-a",
            GoalCancelled("goal-1", "Request withdrawn"),
        )
        cancelled_receipt = self.service.process_event(cancelled_event)
        self.assertEqual(cancelled_receipt.status.value, "processed")
        self.assertEqual(
            self.service.process_event(cancelled_event), cancelled_receipt
        )
        self.assertEqual(
            self.service.goal_status("goal-1").goal.status, GoalStatus.CANCELLED
        )

        replacement = self.service.goal_start(
            "Replacement work",
            (SuccessCriterion("done", "Replacement is complete"),),
        )
        prior = self.service.goal_start(
            "Prior work", (SuccessCriterion("done", "Prior work is complete"),)
        )
        superseded_event = EventEnvelope(
            "supersede-goal-event",
            "project-a",
            GoalSuperseded(prior.goal_id, replacement.goal_id, "Scope changed"),
        )
        receipt = self.service.process_event(superseded_event)
        self.assertEqual(receipt.status.value, "processed")
        self.assertEqual(
            self.service.goal_status(prior.goal_id).goal.superseded_by_goal_id,
            replacement.goal_id,
        )

    def test_stale_status_event_fails_without_overwriting_goal_state(self) -> None:
        self.service.process_event(self.event)
        deferred = EventEnvelope(
            "defer-at-rev-1",
            "project-a",
            GoalDeferred("goal-1", "Waiting for fixture", "Request fixture", 1),
        )
        blocked_stale = EventEnvelope(
            "block-stale-rev-1",
            "project-a",
            GoalBlocked("goal-1", "Fixture missing", "Ask test owner", 1),
        )

        self.assertEqual(self.service.process_event(deferred).status.value, "processed")
        failed = self.service.process_event(blocked_stale)

        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, ConflictError.__name__)
        snapshot = self.service.goal_status("goal-1")
        self.assertEqual(snapshot.goal.status, GoalStatus.DEFERRED)
        self.assertEqual(snapshot.goal.lifecycle_revision, 2)
        self.assertEqual(len(snapshot.facts), 1)

    def test_global_event_receipt_ceiling_is_shared_and_never_prunes(self) -> None:
        with patch("curatormd_v2.store.MAX_EVENT_RECEIPTS_GLOBAL", 1):
            accepted = self.service.process_event(self.event)
            self.assertEqual(accepted.status.value, "processed")
            replayed = self.service.process_event(self.event)
            self.assertEqual(replayed, accepted)

            other_service = CuratorService(
                self.store, ArtifactPurger(self.stage), project_id="project-b"
            )
            second_event = EventEnvelope(
                "global-cap-second",
                "project-b",
                GoalStarted(
                    "goal-b",
                    "A second project's event",
                    (SuccessCriterion("done", "Task is complete"),),
                ),
            )
            with self.assertRaises(EventInboxCapacityError):
                other_service.process_event(second_event)
            with self.assertRaises(NotFoundError):
                self.store.event_receipt("project-b", second_event.event_id)
            with self.assertRaises(NotFoundError):
                self.store.get_goal("goal-b", "project-b")

            usage_a = self.store.project_storage_usage("project-a")
            usage_b = self.store.project_storage_usage("project-b")
            self.assertEqual(usage_a.global_event_inbox.receipt_count, 1)
            self.assertEqual(usage_b.global_event_inbox.receipt_count, 1)
            self.assertFalse(usage_a.global_event_inbox.can_accept_new_event)
            self.assertIsNotNone(usage_a.global_event_inbox.open_gate)
            self.assertEqual(usage_a.event_receipt_count, 1)
            self.assertEqual(usage_b.event_receipt_count, 0)

    def test_global_event_byte_ceiling_rejects_before_receipt_write(self) -> None:
        with patch("curatormd_v2.store.MAX_EVENT_RECEIPT_BYTES_GLOBAL", 10):
            with self.assertRaises(EventInboxCapacityError):
                self.service.process_event(self.event)
            with self.assertRaises(NotFoundError):
                self.store.event_receipt("project-a", self.event.event_id)
            usage = self.store.project_storage_usage("project-a")
            self.assertEqual(usage.global_event_inbox.receipt_count, 0)
            self.assertFalse(usage.global_event_inbox.can_accept_new_event)

    def test_event_id_reuse_with_different_content_is_a_conflict(self) -> None:
        """Reject an event ID that is reused for changed content."""

        self.store.ingest_event(self.event)
        conflicting = EventEnvelope(
            event_id=self.event.event_id,
            project_id=self.event.project_id,
            payload=GoalStarted(
                goal_id="goal-1",
                problem="A different task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
            ),
        )

        with self.assertRaisesRegex(ConflictError, "different payload"):
            self.store.ingest_event(conflicting)

    def test_source_sequence_gap_is_retryable_and_does_not_apply_facts(self) -> None:
        """Hold a delayed event until its source predecessor is processed."""

        start = EventEnvelope(
            "ordered-start",
            "project-a",
            self.event.payload,
            source_id="codex-session-1",
            source_sequence=1,
        )
        self.assertEqual(self.service.process_event(start).status.value, "processed")
        delayed = EventEnvelope(
            "ordered-third",
            "project-a",
            FactRecorded(
                "goal-1", "ordered-fact-3", FactKind.CHANGE, "Third fact"
            ),
            source_id="codex-session-1",
            source_sequence=3,
        )

        failed = self.service.process_event(delayed)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, EventOrderError.__name__)
        self.assertEqual(self.service.goal_status("goal-1").facts, ())

        second = EventEnvelope(
            "ordered-second",
            "project-a",
            FactRecorded("goal-1", "ordered-fact-2", FactKind.CHANGE, "Second fact"),
            source_id="codex-session-1",
            source_sequence=2,
        )
        self.assertEqual(self.service.process_event(second).status.value, "processed")
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", delayed.event_id),
            )
        self.assertEqual(self.service.process_event(delayed).status.value, "processed")
        facts = self.service.goal_status("goal-1").facts
        self.assertEqual(
            [item.fact_id for item in facts], ["ordered-fact-2", "ordered-fact-3"]
        )
        self.assertEqual(self.service.process_event(delayed).status.value, "processed")

    def test_failure_receipt_rejects_unbounded_or_free_form_error_text(self) -> None:
        """Keep raw exception or user-provided text out of the event ledger."""

        self.store.ingest_event(self.event)
        with self.assertRaisesRegex(ValueError, "safe identifier"):
            self.store.mark_event_failed(
                "project-a", "stable-event-1", "secret value\nand more"
            )

    def test_failure_is_retryable_and_processing_discards_payload(self) -> None:
        """Retain failed payload for retry, then reduce success to a receipt."""

        self.store.ingest_event(self.event)
        failed = self.store.mark_event_failed(
            "project-a", "stable-event-1", "adapter_unavailable"
        )
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "adapter_unavailable")
        assert failed.next_attempt_at is not None
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())

        scheduled = datetime.fromisoformat(failed.next_attempt_at)
        remaining = (scheduled - datetime.now(UTC)).total_seconds()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 5)
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", "stable-event-1"),
            )
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)

        processed = self.store.mark_event_processed("project-a", "stable-event-1")

        self.assertEqual(processed.status.value, "processed")
        self.assertIsNotNone(processed.processed_at)
        self.assertIsNone(processed.next_attempt_at)
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())
        repeated, inserted = self.store.ingest_event(self.event)
        self.assertFalse(inserted)
        self.assertEqual(repeated, processed)

    def test_pending_events_can_be_read_by_project_without_cross_scope_leak(self) -> None:
        """Filter inbox reads by project and enforce the caller's batch bound."""

        self.store.ingest_event(self.event)
        other_project = EventEnvelope(
            event_id="stable-event-2",
            project_id="project-b",
            payload=GoalStarted(
                goal_id="goal-2",
                problem="Other project task",
                success_criteria=(SuccessCriterion("recorded", "Fact is recorded"),),
            ),
        )
        self.store.ingest_event(other_project)

        self.assertEqual(
            [event.project_id for event in self.store.pending_events(project_id="project-a")],
            ["project-a"],
        )
        self.assertEqual(len(self.store.pending_events(limit=1)), 1)
        with self.assertRaises(ValueError):
            self.store.pending_events(limit=1001)

    def test_service_applies_project_event_atomically_and_replay_is_safe(self) -> None:
        """Apply a start and finish event once while preserving open truth."""

        started = self.service.process_event(self.event)
        snapshot = self.service.goal_status("goal-1")
        self.assertEqual(snapshot.goal.checklist_id, "tasks")
        self.assertEqual(snapshot.goal.checklist_version, "sha256:" + "b" * 64)
        self.assertEqual(
            snapshot.goal.checklist_source_text, "- [ ] Record project task"
        )
        repeated = self.service.process_event(self.event)
        finish_event = EventEnvelope(
            event_id="finish-event-1",
            project_id="project-a",
            payload=GoalFinishRequested("goal-1", "Claimed complete"),
        )

        finish_receipt = self.service.process_event(finish_event)

        self.assertEqual(started.status.value, "processed")
        self.assertEqual(repeated, started)
        self.assertEqual(snapshot.goal.project_id, "project-a")
        self.assertEqual(finish_receipt.status.value, "processed")
        self.assertEqual(
            self.service.goal_status("goal-1").goal.status, GoalStatus.OPEN
        )
        self.assertEqual(len(self.store.list_goals(project_id="project-a")), 1)

    def test_failed_event_has_no_partial_ledger_effect_and_can_retry(self) -> None:
        """Rollback a failed event, then allow an explicit retry to succeed."""

        fact_event = EventEnvelope(
            event_id="orphan-fact",
            project_id="project-a",
            payload=FactRecorded(
                goal_id="goal-later",
                fact_id="fact-later",
                kind=FactKind.CHANGE,
                bullet="Added the work item",
            ),
        )

        failed = self.service.process_event(fact_event)
        self.assertEqual(failed.status.value, "failed")
        self.assertEqual(failed.last_error_code, "NotFoundError")
        self.assertEqual(self.store.list_goals(project_id="project-a"), ())
        self.assertEqual(self.store.pending_events(project_id="project-a"), ())
        premature = self.service.process_event(fact_event)
        self.assertEqual(premature, failed)
        self.assertEqual(premature.attempts, 1)

        self.service.goal_start(
            "Create an event goal",
            (SuccessCriterion("change", "Change fact is recorded"),),
            goal_id="goal-later",
        )
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE event_inbox SET next_attempt_at = '2000-01-01T00:00:00+00:00' "
                "WHERE project_id = ? AND event_id = ?",
                ("project-a", fact_event.event_id),
            )
        self.assertEqual(len(self.store.pending_events(project_id="project-a")), 1)
        retried = self.service.process_event(fact_event)

        self.assertEqual(retried.status.value, "processed")
        self.assertEqual(
            self.service.goal_status("goal-later").facts[0].fact_id,
            "fact-later",
        )

    def test_storage_usage_attributes_failed_payloads_to_project_and_event_class(self) -> None:
        """Count retry payload bytes without leaking other projects' events."""

        failed_event = EventEnvelope(
            event_id="usage-failed-event",
            project_id="project-a",
            payload=FactRecorded(
                goal_id="missing-goal",
                fact_id="usage-fact",
                kind=FactKind.CHANGE,
                bullet="Retryable project event",
            ),
        )
        self.assertEqual(self.service.process_event(failed_event).status.value, "failed")

        project_usage = self.store.project_storage_usage("project-a")
        other_usage = self.store.project_storage_usage("project-b")

        self.assertEqual(project_usage.event_receipt_count, 1)
        self.assertGreater(project_usage.event_payload_bytes_received, 0)
        self.assertGreater(project_usage.event_payload_bytes_retained, 0)
        self.assertEqual(
            [(item.event_type, item.status) for item in project_usage.event_classes],
            [("fact.recorded", "failed")],
        )
        self.assertEqual(other_usage.event_receipt_count, 0)
        self.assertEqual(other_usage.event_classes, ())

    def test_project_scoped_service_cannot_mutate_another_project_goal(self) -> None:
        """Do not resolve goal IDs across project ownership boundaries."""

        self.service.process_event(self.event)
        other_service = CuratorService(
            self.store, ArtifactPurger(self.stage), project_id="project-b"
        )
        cross_project_fact = EventEnvelope(
            event_id="cross-project-fact",
            project_id="project-b",
            payload=FactRecorded(
                goal_id="goal-1",
                fact_id="other-fact",
                kind=FactKind.CHANGE,
                bullet="Must not cross the project boundary",
            ),
        )

        receipt = other_service.process_event(cross_project_fact)

        self.assertEqual(receipt.status.value, "failed")
        self.assertEqual(receipt.last_error_code, "NotFoundError")
        self.assertEqual(self.service.goal_status("goal-1").facts, ())
        self.assertEqual(other_service.goal_list(), ())

    def test_defer_and_block_events_set_truthful_state_and_next_action(self) -> None:
        """Apply deferred and blocked outcomes without losing their follow-up."""

        self.service.process_event(self.event)
        deferred = EventEnvelope(
            event_id="defer-1",
            project_id="project-a",
            payload=GoalDeferred("goal-1", "Waiting for test data", "Request fixture"),
        )
        blocked = EventEnvelope(
            event_id="block-1",
            project_id="project-a",
            payload=GoalBlocked(
                "goal-1", "fixture unavailable", "Ask test owner", 2
            ),
        )

        self.assertEqual(self.service.process_event(deferred).status.value, "processed")
        deferred_goal = self.service.goal_status("goal-1").goal
        self.assertEqual(deferred_goal.status, GoalStatus.DEFERRED)
        self.assertEqual(deferred_goal.next_action, "Request fixture")
        self.assertEqual(self.service.process_event(blocked).status.value, "processed")
        blocked_goal = self.service.goal_status("goal-1").goal
        self.assertEqual(blocked_goal.status, GoalStatus.BLOCKED)
        self.assertEqual(blocked_goal.next_action, "Ask test owner")

    def test_verified_fact_event_can_complete_all_criteria(self) -> None:
        """Use the configured evidence verifier before event-driven completion."""

        store = self.store

        class TestVerifier:
            """Verify the synthetic evidence used by this event test."""

            def attest(
                self, evidence: EvidenceRef, context: EvidenceVerificationContext
            ):
                """Attest only the explicit test-proof locator."""

                if store.transaction_active:
                    raise AssertionError(
                        "event evidence verification held a SQLite transaction"
                    )
                return (
                    attest_test_evidence(evidence, context)
                    if evidence.locator.startswith("test-proof:")
                    else None
                )

        verified_service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            project_id="project-a",
        )
        verified_service.process_event(self.event)
        proof = EvidenceRef(
            "test", "test-proof:criterion", "d" * 64, EvidenceOutcome.PASSED
        )
        fact_event = EventEnvelope(
            event_id="verified-fact",
            project_id="project-a",
            payload=FactRecorded(
                "goal-1",
                "verified-fact-1",
                FactKind.VERIFICATION,
                "Criterion verified",
                "recorded",
                (proof,),
            ),
        )
        finish_event = EventEnvelope(
            "verified-finish",
            "project-a",
            GoalFinishRequested("goal-1", "Criterion verified"),
        )

        self.assertEqual(verified_service.process_event(fact_event).status.value, "processed")
        self.assertEqual(verified_service.process_event(finish_event).status.value, "processed")
        self.assertEqual(
            verified_service.goal_status("goal-1").goal.status, GoalStatus.COMPLETE
        )

    def test_legacy_goal_schema_migrates_to_default_project(self) -> None:
        """Preserve pre-project goals as members of the default project."""

        legacy_database = Path(self.temp_dir) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_database)
        connection.execute(
            """CREATE TABLE goals (
                goal_id TEXT PRIMARY KEY, problem TEXT NOT NULL,
                criteria_json TEXT NOT NULL, owner TEXT, checklist_id TEXT,
                status TEXT NOT NULL, next_action TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-goal",
                "Legacy task",
                '[{"criterion_id":"c","description":"Works"}]',
                None,
                None,
                "active",
                None,
                "2026-10-18T00:00:00+00:00",
                "2026-10-18T00:00:00+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-complete-goal",
                "Legacy completed task",
                '[{"criterion_id":"c","description":"Works"}]',
                None,
                None,
                "complete",
                None,
                "2026-10-18T00:00:00+00:00",
                "2026-10-18T00:00:00+00:00",
            ),
        )
        connection.commit()
        connection.close()
        os.chmod(legacy_database, stat.S_IRUSR | stat.S_IWUSR)

        migrated = CuratorStore(legacy_database)
        self.addCleanup(migrated.close)

        self.assertEqual(migrated.get_goal("legacy-goal").project_id, "default")
        self.assertEqual(migrated.get_goal("legacy-goal").lifecycle_revision, 2)
        self.assertEqual(
            migrated.get_goal("legacy-complete-goal").lifecycle_revision, 2
        )
        history = migrated.list_goal_criteria_versions("legacy-goal", "default")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].criteria, (SuccessCriterion("c", "Works"),))
        self.assertEqual(history[0].reason, "Initial criteria")
        stage = Path(self.temp_dir) / "legacy-stage"
        stage.mkdir()
        legacy_service = CuratorService(
            migrated, ArtifactPurger(stage), project_id="default"
        )
        stale_legacy_event = EventEnvelope(
            "legacy-unversioned-defer",
            "default",
            GoalDeferred("legacy-goal", "Legacy producer", "Refresh status"),
        )
        self.assertEqual(
            legacy_service.process_event(stale_legacy_event).status.value, "failed"
        )
        self.assertEqual(
            legacy_service.goal_status("legacy-goal").goal.lifecycle_revision, 2
        )

    def test_legacy_event_inbox_schema_migrates_for_usage_reporting(self) -> None:
        """Upgrade old inbox rows without misclassifying unknown byte totals."""

        legacy_database = Path(self.temp_dir) / "legacy-events.sqlite3"
        connection = sqlite3.connect(legacy_database)
        connection.execute(
            """CREATE TABLE event_inbox (
                project_id TEXT NOT NULL, event_id TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL, payload_json TEXT,
                status TEXT NOT NULL, received_at TEXT NOT NULL,
                processed_at TEXT, last_error TEXT,
                PRIMARY KEY(project_id, event_id)
            )"""
        )
        connection.execute(
            """INSERT INTO event_inbox VALUES
               ('legacy-project', 'legacy-event', ?, NULL, 'processed',
                '2026-10-18T00:00:00+00:00', '2026-10-18T00:00:01+00:00', NULL)""",
            ("a" * 64,),
        )
        connection.commit()
        connection.close()
        os.chmod(legacy_database, stat.S_IRUSR | stat.S_IWUSR)

        migrated = CuratorStore(legacy_database)
        self.addCleanup(migrated.close)
        usage = migrated.project_storage_usage("legacy-project")

        self.assertEqual(usage.event_receipt_count, 1)
        self.assertEqual(usage.event_payload_bytes_received, 0)
        self.assertEqual(
            [(item.event_type, item.status) for item in usage.event_classes],
            [("legacy.unknown", "processed")],
        )


if __name__ == "__main__":
    unittest.main()
