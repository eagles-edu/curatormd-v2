"""Executable validation for the published machine-readable v1 contracts."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
import tomllib
from typing import Any, cast
import unittest

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from curatormd_v2 import (
    APIErrorCode,
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    EventEnvelope,
    EventDisposition,
    EventInboxReceipt,
    EventInboxStatus,
    Fact,
    FactKind,
    FactRecorded,
    GoalActivityObserved,
    GoalCard,
    GoalActivated,
    GoalBlocked,
    GoalCancelled,
    GoalCriteriaAmended,
    GoalDeferred,
    GoalFinishRequested,
    GoalReopened,
    GoalStarted,
    GoalSuperseded,
    GoalStatus,
    Materiality,
    ReviewDecision,
    RetentionHoldKind,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    SDEReviewPacket,
    StagingArtifactInventory,
    StagingArtifactClass,
    StagingClassUsage,
    StagingUsage,
    SuccessCriterion,
    to_api_error,
)
from curatormd_v2.service import PurgeTargetStatus


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPOSITORY_ROOT / "docs/schemas/curator-v2-v1.schema.json"


def _json_record(
    record: (
        GoalCard
        | Fact
        | SDECandidate
        | SDECorrection
        | SDEQualityFeedback
        | SDEQualityFeedbackSummary
        | SDEReviewPacket
        | AuditReceipt
        | EventInboxReceipt
        | EvidenceAttestation
        | PurgeTargetStatus
    ),
) -> dict[str, object]:
    """Convert the dataclass's canonical fields and string enums to JSON data."""

    return json.loads(json.dumps(asdict(record), ensure_ascii=False))


class ContractSchemaTests(unittest.TestCase):
    """Keep machine-readable contracts aligned with code and checked-in samples."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)

    def validate_contract(self, name: str, instance: object) -> None:
        """Validate one runtime value against a named contract schema."""

        root = {
            "$schema": self.schema["$schema"],
            "$id": self.schema["$id"],
            "$defs": self.schema["$defs"],
            "$ref": f"#/$defs/{name}",
        }
        validator = cast(
            Any,
            Draft202012Validator(root, format_checker=FormatChecker()),
        )
        validator.validate(instance)

    def test_event_and_plugin_examples_validate_against_v1_definitions(self) -> None:
        event = json.loads(
            (REPOSITORY_ROOT / "docs/examples/event-v1-goal-started.json").read_text(
                encoding="utf-8"
            )
        )
        self.validate_contract("eventEnvelope", event)

        config = tomllib.loads(
            (REPOSITORY_ROOT / "docs/examples/curatormd-v2.toml").read_text(
                encoding="utf-8"
            )
        )
        self.validate_contract("projectConfig", config)
        budgeted_config = json.loads(json.dumps(config))
        budgeted_config["staging"]["max_project_bytes"] = 1_073_741_824
        budgeted_config["staging"]["max_project_files"] = 10_000
        self.validate_contract("projectConfig", budgeted_config)

    def test_all_lifecycle_event_payloads_validate_against_v1_schema(self) -> None:
        evidence = EvidenceRef(
            "test", "unittest://lifecycle-event", "f" * 64, EvidenceOutcome.PASSED
        )
        criterion = SuccessCriterion("criteria-1", "The lifecycle event validates")
        payloads = (
            GoalStarted("goal-events", "Validate every event type", (criterion,)),
            GoalActivated("goal-events", "Start the planned work", 1),
            FactRecorded(
                "goal-events",
                "fact-events",
                FactKind.VERIFICATION,
                "The schema accepts the runtime event",
                criterion_id=criterion.criterion_id,
                evidence=(evidence,),
            ),
            GoalActivityObserved(
                "goal-events", "activity-events", FactKind.OPEN_GATE,
                "A runtime interruption was observed.",
            ),
            GoalFinishRequested("goal-events", "All declared criteria are proven", 1),
            GoalDeferred("goal-events", "Wait for the reviewer", "Resume review", 1),
            GoalBlocked(
                "goal-events",
                "Host identity is unavailable",
                "Bind a trusted identity",
                1,
            ),
            GoalReopened("goal-events", "A new evidence epoch is needed", "Rerun the checks", 1),
            GoalCriteriaAmended(
                "goal-events",
                1,
                (SuccessCriterion("criteria-2", "The amended criterion is explicit"),),
                "The original criterion was underspecified",
                "Verify the amended criterion",
                1,
            ),
            GoalCancelled("goal-events", "The requested work is no longer needed"),
            GoalSuperseded(
                "goal-events", "goal-successor", "The successor goal replaces this one"
            ),
        )

        for index, payload in enumerate(payloads, start=1):
            event = EventEnvelope(
                event_id=f"event-{index}",
                project_id="gptmd",
                source_id="contract-tests",
                source_sequence=index,
                payload=payload,
            )
            with self.subTest(event_type=event.event_kind.value):
                self.validate_contract("eventEnvelope", event.to_dict())

    def test_processed_event_receipts_validate_with_both_dispositions(self) -> None:
        for disposition in (
            EventDisposition.APPLIED,
            EventDisposition.SUPPRESSED_NONACTIVE_GOAL,
        ):
            receipt = EventInboxReceipt(
                project_id="gptmd",
                event_id="hermes-event-1",
                payload_sha256="a" * 64,
                status=EventInboxStatus.PROCESSED,
                received_at="2026-10-20T00:00:00+00:00",
                processed_at="2026-10-20T00:00:01+00:00",
                last_error_code=None,
                attempts=1,
                next_attempt_at=None,
                disposition=disposition,
            )
            with self.subTest(disposition=disposition.value):
                self.validate_contract("eventInboxReceipt", _json_record(receipt))

    def test_goal_fact_sde_correction_and_receipt_records_match_schemas(self) -> None:
        goal = GoalCard(
            goal_id="goal-contracts",
            project_id="gptmd",
            problem="Publish machine-readable record contracts",
            success_criteria=(
                SuccessCriterion("schema-valid", "Each canonical record validates"),
            ),
            status=GoalStatus.ACTIVE,
        )
        evidence = EvidenceRef(
            "test", "unittest://test_contract_schemas", "a" * 64, EvidenceOutcome.PASSED
        )
        attestation = EvidenceAttestation(
            evidence_kind=evidence.evidence_kind,
            evidence_sha256=evidence.sha256,
            project_id=goal.project_id,
            goal_id=goal.goal_id,
            criterion_id="schema-valid",
            adapter_id="contract-test-runner",
            authenticated_subject="runner:contracts",
            source_revision="test-run:contract-schema",
            observed_at="2026-10-18T12:00:00+00:00",
            verified_at="2026-10-18T12:00:00+00:00",
            valid_until="2026-10-18T12:01:00+00:00",
            revocation_checked_at="2026-10-18T12:00:00+00:00",
        )
        fact = Fact(
            goal_id=goal.goal_id,
            fact_id="fact-contract-schema",
            kind=FactKind.VERIFICATION,
            bullet="The contract schema test passed",
            criterion_id="schema-valid",
            evidence=(evidence,),
            verification_attestations=(attestation,),
            source_event_id="evt-contract-schema",
        )
        candidate = SDECandidate(
            goal_id=goal.goal_id,
            candidate_id="sde-contract-schema",
            materiality=Materiality.VERIFIED_LESSON,
            rationale="The record contract now has executable schema coverage",
            fact_ids=(fact.fact_id,),
            impact="Observed local schema coverage is passing",
            retrieval_value="Helps future maintainers find the schema contract",
        )
        correction = SDECorrection(
            correction_id="correction-schema",
            candidate_id=candidate.candidate_id,
            correction="Keep the compatibility boundary explicit",
            rationale="The schema is a local v1 contract, not a deployed transport",
            reviewer_id="reviewer:owner",
        )
        receipt = AuditReceipt(
            candidate_id=candidate.candidate_id,
            decision=ReviewDecision.REJECTED,
            facts_sha256="b" * 64,
            artifacts=(
                ArtifactRef(
                    "/stage/source.txt",
                    "c" * 64,
                    RetentionHoldKind.OPERATIONAL,
                ),
            ),
            artifact_inventory_complete=True,
            reviewer_id="reviewer:owner",
            review_rationale="Keep the schema proposal open pending integration",
        )
        purge_target = PurgeTargetStatus(
            artifact=ArtifactRef(
                "/stage/source.txt",
                "c" * 64,
                RetentionHoldKind.OPERATIONAL,
            ),
            status=ArtifactStatus.PURGED,
            attempts=1,
            error=None,
            created_at="2026-10-18T12:00:00+00:00",
            last_attempt_at="2026-10-18T12:01:00+00:00",
            next_attempt_at=None,
            next_attempt_in_seconds=None,
            age_seconds=60,
            last_attempt_age_seconds=0,
            safe_recovery_action="none",
            hold_created_at="2026-10-18T11:59:00+00:00",
            hold_created_by="reviewer:owner",
            hold_released_at="2026-10-18T12:00:30+00:00",
            hold_released_by="reviewer:owner",
            hold_release_rationale="The retention owner approved purge",
        )
        quality_feedback = SDEQualityFeedback(
            feedback_id="feedback-contract-1",
            candidate_id=candidate.candidate_id,
            reviewer_id="reviewer:owner",
            label=SDEQualityFeedbackLabel.USEFUL,
            rationale="The proposal was concise and evidence-bound",
        )
        quality_summary = SDEQualityFeedbackSummary(
            project_id="gptmd",
            counts=(
                (SDEQualityFeedbackLabel.USEFUL, 1),
                (SDEQualityFeedbackLabel.NOT_USEFUL, 0),
                (SDEQualityFeedbackLabel.INACCURATE, 0),
                (SDEQualityFeedbackLabel.DUPLICATE, 0),
            ),
            total=1,
        )
        review_packet = SDEReviewPacket(
            detail=SDEReviewDetail(
                candidate=candidate,
                goal=goal,
                facts=(fact,),
                receipt=receipt,
                corrections=(correction,),
            ),
            artifact_inventory=StagingArtifactInventory(
                artifacts=receipt.artifacts,
                usage=StagingUsage(
                    entries_scanned=1,
                    regular_file_count=1,
                    observed_file_bytes=128,
                    directory_count=0,
                    symlink_count=0,
                    special_file_count=0,
                    inventory_complete=True,
                    classes=(
                        StagingClassUsage(
                            StagingArtifactClass.CUE, 1, 128
                        ),
                    ),
                ),
                manifest_sha256="f" * 64,
                scope_goal_id=goal.goal_id,
            ),
        )

        for name, record in (
            ("goalCard", goal),
            ("evidenceAttestation", attestation),
            ("fact", fact),
            ("sdeCandidate", candidate),
            ("sdeCorrection", correction),
            ("sdeQualityFeedback", quality_feedback),
            ("sdeQualityFeedbackSummary", quality_summary),
            ("auditReceipt", receipt),
            ("purgeTargetStatus", purge_target),
            ("sdeReviewPacket", review_packet),
        ):
            with self.subTest(contract=name):
                self.validate_contract(name, _json_record(record))

        failed_target = replace(
            purge_target,
            status=ArtifactStatus.FAILED,
            error="filesystem_error",
            safe_recovery_action="retry_pending_purges",
        )
        self.validate_contract("purgeTargetStatus", _json_record(failed_target))
        with self.assertRaises(ValidationError):
            self.validate_contract(
                "purgeTargetStatus",
                _json_record(replace(failed_target, error="private path detail")),
            )

    def test_schemas_reject_contradictory_goal_fact_and_receipt_states(self) -> None:
        goal = _json_record(
            GoalCard(
                goal_id="goal-open",
                project_id="gptmd",
                problem="Keep unsupported work open",
                success_criteria=(SuccessCriterion("proof", "Evidence exists"),),
            )
        )
        goal["status"] = "superseded"
        with self.assertRaises(ValidationError):
            self.validate_contract("goalCard", goal)

        fact = _json_record(
            Fact(
                goal_id="goal-open",
                kind=FactKind.VERIFICATION,
                bullet="Verification without evidence must fail",
                criterion_id="proof",
                evidence=(EvidenceRef("test", "test://proof", "d" * 64, EvidenceOutcome.PASSED),),
            )
        )
        fact["evidence"] = []
        with self.assertRaises(ValidationError):
            self.validate_contract("fact", fact)

        receipt = _json_record(
            AuditReceipt(
                candidate_id="sde-open",
                decision=ReviewDecision.REJECTED,
                facts_sha256="e" * 64,
                artifacts=(),
            )
        )
        receipt["canonical_persisted"] = True
        with self.assertRaises(ValidationError):
            self.validate_contract("auditReceipt", receipt)

    def test_api_error_code_is_a_valid_v1_schema_instance(self) -> None:
        response = to_api_error(RuntimeError("private detail"))
        self.assertEqual(response.code, APIErrorCode.INTERNAL_ERROR)
        self.validate_contract("apiError", response.to_dict())


if __name__ == "__main__":
    unittest.main()
