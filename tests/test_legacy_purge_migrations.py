"""Legacy purge and attestation schema migrations."""
# pylint: disable=duplicate-code
# Migration cases repeat schema setup across distinct version/failure contracts.

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from migration_test_support import (
    LegacySchemaMigrationSupport,
    MigrationEvidenceVerifier,
    MigrationReviewAuthorizer,
)
from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    CuratorService,
    CuratorStore,
    CriterionStatus,
    EvidenceOutcome,
    EvidenceRef,
    EventEnvelope,
    FactKind,
    GoalStarted,
    GoalStatus,
    Materiality,
    ReviewDecision,
    SDEConfirmationRequest,
    SQLITE_SCHEMA_VERSION,
    SuccessCriterion,
)
from curatormd_v2.service import SDEAssessmentRequest


class LegacyPurgeMigrationTests(LegacySchemaMigrationSupport):
    """Exercise the selected legacy migration contracts."""

    def test_v2_purge_targets_migrate_with_receipt_age_and_no_attempt(self) -> None:
        """Backfill v2 artifact age from its durable parent receipt."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v2.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            receipt_id, target_path, receipt_created_at = (
                self._create_v2_purge_migration_fixture(database_path, staging)
            )

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX purge_targets_queue_age")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN last_attempt_at")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN created_at")
            connection.execute("DROP INDEX event_inbox_retry_due")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                stored_receipt = migrated.get_receipt(receipt_id, "migration-project")
                target_record = migrated.get_purge_target_records(
                    receipt_id, "migration-project"
                )[0]
                self.assertEqual(stored_receipt.receipt_id, receipt_id)
                self.assertEqual(target_record.artifact.path, target_path)
                self.assertEqual(target_record.created_at, receipt_created_at)
                self.assertIsNone(target_record.last_attempt_at)
                self.assertEqual(target_record.attempts, 0)
                self.assertEqual(
                    target_record.status.value,
                    "pending",
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v3_failed_events_migrate_without_an_invented_retry_delay(self) -> None:
        """Keep legacy failed payloads immediately eligible after v4 upgrade."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v3.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v3-failed-event",
                "migration-project",
                GoalStarted(
                    "migration-event-goal",
                    "Preserve a failed event through retry schema migration",
                    (SuccessCriterion("done", "The event remains retryable"),),
                ),
            )
            store.ingest_event(event)
            original = store.mark_event_failed(
                "migration-project", event.event_id, "adapter_unavailable"
            )
            self.assertIsNotNone(original.next_attempt_at)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("DROP INDEX event_inbox_retry_due")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN next_attempt_at")
            connection.execute("PRAGMA user_version = 3")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                receipt = migrated.event_receipt("migration-project", event.event_id)
                self.assertEqual(receipt.status.value, "failed")
                self.assertEqual(receipt.attempts, 1)
                self.assertIsNone(receipt.next_attempt_at)
                self.assertEqual(
                    tuple(item.event_id for item in migrated.pending_events()),
                    (event.event_id,),
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v4_retry_deadline_survives_lease_schema_migration(self) -> None:
        """Upgrade v4 inboxes without erasing scheduled retry state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v4.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v4-failed-event",
                "migration-project",
                GoalStarted(
                    "migration-v4-goal",
                    "Preserve a retry deadline while adding worker leases",
                    (SuccessCriterion("done", "The retry remains scheduled"),),
                ),
            )
            store.ingest_event(event)
            original = store.mark_event_failed(
                "migration-project", event.event_id, "adapter_unavailable"
            )
            self.assertIsNotNone(original.next_attempt_at)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("DROP INDEX event_inbox_claim_expiry")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_owner")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN lease_expires_at")
            connection.execute("PRAGMA user_version = 4")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                receipt = migrated.event_receipt("migration-project", event.event_id)
                self.assertEqual(receipt.next_attempt_at, original.next_attempt_at)
                self.assertEqual(migrated.pending_events(), ())
                self.assertEqual(migrated.event_queue_status().claimed_count, 0)
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v5_purge_target_stays_pending_without_cleanup_authorization(self) -> None:
        """Migrate the target without inventing either retry delay or approval."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v5.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve a purge target through the v6 migration",
                (SuccessCriterion("verified", "The migration keeps the target"),),
            )
            changed, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Prepared the purge migration fixture"
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
                ),
            )
            candidate = service.sde_assess(
                SDEAssessmentRequest(
                    goal.goal_id,
                    Materiality.IMPLEMENTATION,
                    "Purge retry migration fixture",
                    (changed.fact_id, verified.fact_id),
                    impact="Observed in the bounded test scenario",
                    retrieval_value="Useful for future maintenance review",
                )
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            receipt = service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate.candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(ArtifactRef(str(staging / "temporary.txt"), "b" * 64),),
                    artifact_inventory_complete=True,
                )
            )
            receipt = store.mark_receipt_canonical_persisted(
                receipt.receipt_id,
                "persistence/HISTORY.md",
                "c" * 64,
                "migration-project",
            )
            self.assertEqual(receipt.purge_status.value, "purge_pending")
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_retry_due")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN next_attempt_at")
            connection.execute("PRAGMA user_version = 5")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                target = migrated.get_purge_target_records(
                    receipt.receipt_id, "migration-project"
                )[0]
                self.assertEqual(target.status.value, "pending")
                self.assertEqual(target.attempts, 0)
                self.assertIsNone(target.next_attempt_at)
                self.assertIsNone(
                    migrated.cleanup_authorization(
                        receipt.receipt_id, "migration-project"
                    )
                )
                self.assertEqual(
                    tuple(
                        item.receipt_id
                        for item in migrated.due_pending_purge_receipts(
                            "migration-project"
                        )
                    ),
                    (),
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v6_adds_nullable_goal_intake_provenance_without_inventing_legacy_values(self) -> None:
        """Preserve old goals and leave unknown historical intake fields null."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v6.sqlite3"
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(Path(temporary)),
                project_id="migration-project",
            )
            legacy_goal = service.goal_start(
                "Preserve the v6 goal through provenance migration",
                (SuccessCriterion("done", "The old goal is unchanged"),),
                owner="legacy-owner",
            )
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX goals_project_source_event")
            connection.execute("ALTER TABLE goals DROP COLUMN source_event_id")
            connection.execute("ALTER TABLE goals DROP COLUMN initial_status")
            connection.execute("PRAGMA user_version = 6")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                preserved = migrated.get_goal(legacy_goal.goal_id, "migration-project")
                self.assertEqual(preserved.problem, legacy_goal.problem)
                self.assertEqual(preserved.owner, "legacy-owner")
                legacy_context = migrated.goal_report_context(
                    legacy_goal.goal_id, "migration-project"
                )
                self.assertIsNone(legacy_context.initial_status)
                self.assertIsNone(legacy_context.source_event_id)

                new_service = CuratorService(
                    migrated,
                    ArtifactPurger(Path(temporary)),
                    project_id="migration-project",
                )
                new_goal = new_service.goal_start(
                    "Record provenance for a new goal",
                    (SuccessCriterion("new", "The new fields are saved"),),
                    initial_status=GoalStatus.PLANNED,
                    source_event_id="v7-source-event",
                )
                new_context = migrated.goal_report_context(
                    new_goal.goal_id, "migration-project"
                )
                self.assertEqual(new_context.initial_status, GoalStatus.PLANNED)
                self.assertEqual(new_context.source_event_id, "v7-source-event")
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_verification_attestations_survive_store_reopen(self) -> None:
        """Persisted provenance remains attached to its exact evidence fact."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "attestations.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Retain exact verification provenance",
                (SuccessCriterion("tested", "The stored receipt remains trusted"),),
            )
            original, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "The runner receipt verified the criterion",
                criterion_id="tested",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "c" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            store.close()

            reopened = CuratorStore(database_path)
            try:
                facts = reopened.list_facts(goal.goal_id, "migration-project")
                self.assertEqual(len(facts), 1)
                self.assertEqual(
                    facts[0].verification_attestations,
                    original.verification_attestations,
                )
                service = CuratorService(
                    reopened,
                    ArtifactPurger(staging),
                    MigrationEvidenceVerifier(),
                    project_id="migration-project",
                )
                self.assertEqual(
                    service.goal_status(goal.goal_id).criteria[0].status,
                    CriterionStatus.VERIFIED,
                )
                self.assertGreater(
                    reopened.goal_fact_capacity(
                        goal.goal_id, "migration-project"
                    ).goal_fact_bytes,
                    0,
                )
            finally:
                reopened.close()

    def test_v7_attestation_migration_preserves_facts_but_fails_legacy_proof_closed(self) -> None:
        """Legacy verification facts migrate without invented trust provenance."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v7.sqlite3"
            staging = root / "staging"
            staging.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging),
                MigrationEvidenceVerifier(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve verification history without fabricating provenance",
                (SuccessCriterion("tested", "A passing immutable receipt exists"),),
            )
            original, _ = service.goal_fact(
                goal.goal_id,
                FactKind.VERIFICATION,
                "A trusted fixture receipt passed before the schema upgrade",
                criterion_id="tested",
                evidence=(
                    EvidenceRef(
                        "test",
                        "test-proof:migration",
                        "b" * 64,
                        EvidenceOutcome.PASSED,
                    ),
                ),
            )
            self.assertEqual(len(original.verification_attestations), 1)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute(
                "ALTER TABLE facts DROP COLUMN verification_attestations_json"
            )
            connection.execute("PRAGMA user_version = 7")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                service = CuratorService(
                    migrated,
                    ArtifactPurger(staging),
                    MigrationEvidenceVerifier(),
                    project_id="migration-project",
                )
                facts = migrated.list_facts(goal.goal_id, "migration-project")
                self.assertEqual(len(facts), 1)
                self.assertEqual(facts[0].fact_id, original.fact_id)
                self.assertEqual(facts[0].bullet, original.bullet)
                self.assertEqual(facts[0].verification_attestations, ())
                self.assertEqual(
                    service.goal_status(goal.goal_id).criteria[0].status,
                    CriterionStatus.OPEN,
                )
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    attestation_default = connection.execute(
                        "SELECT verification_attestations_json FROM facts WHERE fact_id = ?",
                        (original.fact_id,),
                    ).fetchone()[0]
                    self.assertEqual(attestation_default, "[]")
            finally:
                migrated.close()
