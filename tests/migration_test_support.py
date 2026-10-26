"""Shared adapters and builders for schema migration tests."""
# pylint: disable=duplicate-code
# Migration cases repeat schema setup across distinct version/failure contracts.

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from evidence_fixtures import attest_test_evidence
from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    FactKind,
    GoalStatus,
    Materiality,
    ReviewDecision,
    SDEConfirmationRequest,
    SuccessCriterion,
)
from curatormd_v2.service import SDEAssessmentRequest


PROJECT_USAGE_COLUMNS = {
    "audit_receipts": frozenset(
        {
            "receipt_id", "candidate_id", "decision", "facts_sha256",
            "artifact_inventory_complete", "reviewer_id", "review_rationale",
            "canonical_persisted", "canonical_target", "canonical_sha256",
            "canonical_persisted_at", "purge_status", "created_at", "updated_at",
        }
    ),
    "cleanup_authorizations": frozenset(
        {
            "receipt_id", "project_id", "reviewer_id", "manifest_sha256",
            "approved_at", "canonical_persisted", "canonical_target",
            "canonical_sha256", "canonical_persisted_at", "dependency_map_sha256",
        }
    ),
    "event_cursors": frozenset(
        {"project_id", "source_id", "last_sequence", "updated_at"}
    ),
    "event_inbox": frozenset(
        {
            "project_id", "event_id", "event_type", "payload_sha256",
            "payload_bytes", "payload_json", "status", "received_at", "processed_at",
            "last_error", "next_attempt_at", "lease_owner", "lease_expires_at",
            "disposition", "attempts", "source_id", "source_sequence",
            "idempotency_sha256",
        }
    ),
    "event_payload_scrub_queue": frozenset(
        {"scrub_id", "project_id", "event_id", "queued_at", "attempts", "last_error_code"}
    ),
    "event_retry_audit": frozenset(
        {"retry_id", "project_id", "event_id", "actor_id", "created_at"}
    ),
    "expiry_purge_receipts": frozenset(
        {
            "receipt_id", "project_id", "reviewer_id", "manifest_sha256", "status",
            "created_at", "updated_at",
        }
    ),
    "expiry_purge_targets": frozenset(
        {
            "receipt_id", "path", "sha256", "status", "attempts", "error",
            "created_at", "last_attempt_at", "next_attempt_at", "device_id",
            "inode_id", "occurrence_id", "approval_stale",
        }
    ),
    "fact_archive_items": frozenset(
        {"fact_id", "compaction_id", "project_id", "goal_id", "dedupe_key", "created_at"}
    ),
    "fact_archives": frozenset(
        {
            "compaction_id", "schema_version", "project_id", "goal_id", "source_sha256",
            "archive_sha256", "source_bytes", "compressed_bytes", "fact_count",
            "payload_zlib", "reviewer_id", "approval_reason", "created_at",
        }
    ),
    "facts": frozenset(
        {
            "fact_id", "goal_id", "kind", "bullet", "criterion_id", "evidence_json",
            "verification_attestations_json", "source_event_id", "dedupe_key", "created_at",
        }
    ),
    "goal_criteria_versions": frozenset(
        {"goal_id", "revision", "criteria_json", "reason", "created_at"}
    ),
    "goals": frozenset(
        {
            "goal_id", "project_id", "problem", "criteria_json", "owner", "checklist_id",
            "checklist_version", "checklist_source_text", "parent_goal_id",
            "depends_on_json", "status", "next_action", "superseded_by_goal_id",
            "criteria_revision", "lifecycle_revision", "created_at", "updated_at",
            "initial_status", "source_event_id",
        }
    ),
    "purge_targets": frozenset(
        {
            "receipt_id", "path", "sha256", "status", "attempts", "error", "created_at",
            "last_attempt_at", "next_attempt_at", "retention_hold", "hold_created_at",
            "hold_created_by", "hold_released_at", "hold_released_by",
            "hold_release_rationale", "device_id", "inode_id", "occurrence_id",
            "approval_stale", "reacquisition_action", "outcome",
        }
    ),
    "sde_candidates": frozenset(
        {
            "candidate_id", "goal_id", "materiality", "rationale", "fact_ids_json",
            "dedupe_key", "status", "created_at", "impact", "retrieval_value",
        }
    ),
    "sde_corrections": frozenset(
        {"correction_id", "candidate_id", "correction", "rationale", "reviewer_id", "created_at"}
    ),
    "sde_quality_feedback": frozenset(
        {"feedback_id", "candidate_id", "reviewer_id", "label", "rationale", "created_at"}
    ),
    "staging_artifact_occurrences": frozenset(
        {"project_id", "path", "sha256", "device_id", "inode_id", "occurrence_id", "observed_at"}
    ),
    "staging_artifact_times": frozenset(
        {"project_id", "path", "sha256", "staged_at", "device_id", "inode_id", "occurrence_id"}
    ),
}

CONTROL_PLANE_USAGE_COLUMNS = {
    "consumer_drain_events": frozenset(
        {
            "project_id", "transition_id", "event_id", "payload_sha256",
            "idempotency_sha256", "source_id", "source_sequence",
        }
    ),
    "consumer_drain_sessions": frozenset(
        {
            "project_id", "transition_id", "actor_id", "caller_subject",
            "caller_profile", "binding_revision", "source_epoch", "config_sha256",
            "inventory_sha256", "created_at", "expires_at", "revoked_at",
        }
    ),
    "consumer_bindings": frozenset(
        {"project_id", "status", "revision", "source_epoch", "updated_by", "updated_at"}
    ),
    "consumer_binding_audit": frozenset(
        {
            "audit_id", "project_id", "actor_id", "action", "from_status", "to_status",
            "source_epoch", "revision", "transition_id", "rationale", "created_at",
        }
    ),
    "project_grant_revocations": frozenset(
        {"grant_id", "revoked_by", "rationale", "revoked_at"}
    ),
    "project_grants": frozenset(
        {"grant_id", "project_id", "subject_id", "action", "granted_by", "rationale", "granted_at"}
    ),
    "project_registry": frozenset(
        {
            "project_id", "repository_fingerprint", "config_sha256", "backend_api_version",
            "status", "registered_by", "registered_at", "updated_by", "updated_at", "revision",
        }
    ),
    "project_registry_audit": frozenset(
        {
            "audit_id", "project_id", "actor_id", "action", "repository_fingerprint",
            "config_sha256", "backend_api_version", "rationale", "created_at", "revision",
            "transition_id", "review_packet_sha256", "review_packet_json",
            "suspension_transition_id",
        }
    ),
    "project_retirement_tombstones": frozenset(
        {
            "project_id", "transition_id", "retired_by", "retired_revision",
            "source_epoch", "rationale", "retired_at",
        }
    ),
    "terminal_event_dispositions": frozenset(
        {
            "project_id", "event_id", "transition_id", "actor_id", "prior_status",
            "payload_sha256", "rationale", "created_at",
        }
    ),
    "request_rate_buckets": frozenset(
        {"subject_id", "project_id", "tokens", "updated_at", "touched_at"}
    ),
}

class MigrationEvidenceVerifier:  # pylint: disable=too-few-public-methods
    """Accept the stable synthetic evidence reference used by this fixture."""

    def attest(self, evidence: EvidenceRef, context: EvidenceVerificationContext):
        """Attest only the migration fixture's exact proof locator."""

        return (
            attest_test_evidence(evidence, context)
            if evidence.locator == "test-proof:migration"
            else None
        )


class MigrationReviewAuthorizer:
    """Supply a stable reviewer identity for local migration fixtures."""

    def authorize(
        self,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        authenticated_subject: str | None = None,
        ) -> str:
        """Return a stable reviewer identity for the local fixture."""

        del project_id, candidate_id, decision
        return authenticated_subject or "migration-operator"

    def authorize_correction(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
        ) -> str:
        """Supply an attributable reviewer for linked correction fixtures."""

        del project_id, candidate_id
        return authenticated_subject or "migration-operator"

    def authorize_feedback(
        self,
        project_id: str,
        candidate_id: str,
        authenticated_subject: str | None = None,
        ) -> str:
        """Supply an attributable identity for quality-feedback migration tests."""

        return self.authorize_correction(project_id, candidate_id, authenticated_subject)

    def authorize_hold_release(
        self,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
        authenticated_subject: str | None = None,
        ) -> str:
        """Supply an attributable identity for migration hold-release tests."""

        del project_id, receipt_id, path, rationale
        return authenticated_subject or "migration-operator"

    def authorize_expiry_purge(
        self,
        project_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
        ) -> str:
        """Attribute an expiry decision to the migration fixture reviewer."""

        del project_id, manifest_sha256
        return authenticated_subject or "migration-operator"

    def authorize_cleanup(
        self,
        project_id: str,
        receipt_id: str,
        manifest_sha256: str,
        authenticated_subject: str | None = None,
        ) -> str:
        """Attribute a cleanup decision to the migration fixture reviewer."""

        del project_id, receipt_id, manifest_sha256
        return authenticated_subject or "migration-operator"


class LegacySchemaMigrationSupport(unittest.TestCase):
    """Build legacy databases shared by versioned migration cases."""

    @staticmethod
    def _create_unversioned_legacy_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.execute(
            """CREATE TABLE goals (
                goal_id TEXT PRIMARY KEY,
                problem TEXT NOT NULL,
                criteria_json TEXT NOT NULL,
                owner TEXT,
                checklist_id TEXT,
                status TEXT NOT NULL,
                next_action TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO goals
               (goal_id, problem, criteria_json, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "legacy-goal",
                "Preserve data through schema migration",
                '[{"criterion_id":"done","description":"Migration passes"}]',
                GoalStatus.ACTIVE.value,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()
        connection.close()
        path.chmod(0o600)

    def _create_v2_purge_migration_fixture(
        self, database_path: Path, staging: Path
    ) -> tuple[str, str, str]:
        """Create the durable receipt and return its bounded migration fields."""

        store = CuratorStore(database_path)
        try:
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Create an artifact receipt before schema migration",
                (SuccessCriterion("verified", "The local migration proof is accepted"),),
            )
            changed, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Prepared the v2 receipt fixture"
            )
            verified, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The migration evidence fixture passed",
                criterion_id="verified",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "a" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                )
            )
            candidate = service.sde_assess(
                SDEAssessmentRequest(
                    goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "Durable migration fixture",
                    (changed.fact_id, verified.fact_id),
                    impact="Observed in the bounded test scenario",
                    retrieval_value="Useful for future maintenance review",
                )
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            target = staging / "temporary-artifact.json"
            receipt = service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate.candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(ArtifactRef(str(target), "b" * 64),),
                    artifact_inventory_complete=True,
                )
            )
            self.assertFalse(receipt.canonical_persisted)
            return receipt.receipt_id, str(target), receipt.created_at
        finally:
            store.close()
