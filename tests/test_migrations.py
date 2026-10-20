"""Versioned SQLite schema migration and rollback fixtures."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from evidence_fixtures import attest_test_evidence

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    CuratorService,
    CuratorStore,
    CriterionStatus,
    EvidenceOutcome,
    EvidenceRef,
    EvidenceVerificationContext,
    EventEnvelope,
    FactKind,
    GoalStarted,
    GoalStatus,
    Materiality,
    ReviewDecision,
    SQLITE_SCHEMA_VERSION,
    SuccessCriterion,
)


class MigrationEvidenceVerifier:
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


class SchemaMigrationTests(unittest.TestCase):
    """Verify supported SQLite upgrades and refusal of unknown schemas."""

    def test_v15_migration_redacts_legacy_purge_failure_details(self) -> None:
        """Remove potentially sensitive exception text without clearing retry state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v15.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """INSERT INTO purge_targets (
                       receipt_id, path, sha256, status, attempts, error, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "legacy-receipt",
                    "/private/SENSITIVE_PURGE_PATH_SENTINEL",
                    "0" * 64,
                    "failed",
                    3,
                    "cannot safely remove /private/SENSITIVE_PURGE_PATH_SENTINEL",
                    "2026-10-20T00:00:00+00:00",
                ),
            )
            connection.execute(
                """CREATE TRIGGER block_legacy_error_redaction
                   BEFORE UPDATE OF error ON purge_targets
                   BEGIN SELECT RAISE(ABORT, 'injected redaction failure'); END"""
            )
            connection.execute("PRAGMA user_version = 15")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.IntegrityError):
                CuratorStore(database_path)
            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 15
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT error FROM purge_targets WHERE receipt_id = ?",
                        ("legacy-receipt",),
                    ).fetchone()[0],
                    "cannot safely remove /private/SENSITIVE_PURGE_PATH_SENTINEL",
                )
                connection.execute("DROP TRIGGER block_legacy_error_redaction")
                connection.commit()
            finally:
                connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        """SELECT status, attempts, error
                           FROM purge_targets WHERE receipt_id = ?""",
                        ("legacy-receipt",),
                    ).fetchone()
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SQLITE_SCHEMA_VERSION)
                self.assertEqual(row["status"], "failed")
                self.assertEqual(row["attempts"], 3)
                self.assertEqual(row["error"], "legacy_failure_detail_redacted")
                self.assertNotIn("SENSITIVE_PURGE_PATH_SENTINEL", row["error"])
            finally:
                migrated.close()

    def test_v16_migration_backfills_semantic_digest_for_retained_event(self) -> None:
        """Backfill retry identity only while the bounded payload is retained."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v16.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                event_id="migration-replay-event",
                project_id="migration-project",
                payload=GoalStarted(
                    goal_id="migration-replay-goal",
                    problem="Preserve a received event across schema migration",
                    success_criteria=(
                        SuccessCriterion("verified", "The event remains retryable"),
                    ),
                ),
            )
            store.ingest_event(event)
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE event_inbox DROP COLUMN idempotency_sha256")
            connection.execute("PRAGMA user_version = 16")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    row = connection.execute(
                        "SELECT idempotency_sha256 FROM event_inbox WHERE event_id = ?",
                        (event.event_id,),
                    ).fetchone()
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SQLITE_SCHEMA_VERSION)
                self.assertEqual(row["idempotency_sha256"], event.idempotency_sha256)
            finally:
                migrated.close()

    def test_v11_database_migrates_to_current_schema_without_feedback_labels(
        self,
    ) -> None:
        """Upgrade schema v11 without inventing feedback or limiter state."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v11.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute("DROP TABLE sde_quality_feedback")
            connection.execute("PRAGMA user_version = 11")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT count(*) FROM sde_quality_feedback"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT count(*) FROM request_rate_buckets"
                        ).fetchone()[0],
                        0,
                    )
            finally:
                migrated.close()

    def test_v12_database_migrates_shared_request_limiter_v13(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v12.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute("PRAGMA user_version = 12")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(request_rate_buckets)"
                        ).fetchall()
                    }
                    self.assertEqual(
                        columns,
                        {"subject_id", "project_id", "tokens", "updated_at", "touched_at"},
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v13_database_adds_event_disposition_without_losing_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v13.sqlite3"
            store = CuratorStore(database_path)
            receipt, inserted = store.ingest_event(
                EventEnvelope(
                    "event-before-disposition",
                    "migration-project",
                    GoalStarted(
                        "migration-goal", "Keep prior event receipts",
                        (SuccessCriterion("done", "Receipt remains available"),),
                    ),
                )
            )
            self.assertTrue(inserted)
            self.assertEqual(receipt.status.value, "received")
            processed = store.mark_event_processed(
                "migration-project", "event-before-disposition"
            )
            self.assertEqual(processed.status.value, "processed")
            store.close()

            connection = sqlite3.connect(database_path)
            connection.execute("ALTER TABLE event_inbox DROP COLUMN disposition")
            connection.execute("PRAGMA user_version = 13")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(event_inbox)"
                        ).fetchall()
                    }
                    self.assertIn("disposition", columns)
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                preserved = migrated.event_receipt(
                    "migration-project", "event-before-disposition"
                )
                self.assertEqual(preserved.status.value, "processed")
                self.assertIsNone(preserved.disposition)
            finally:
                migrated.close()

    def test_v14_database_adds_nullable_fact_source_event(self) -> None:
        """Add source provenance without guessing it for existing facts."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v14.sqlite3"
            staging_root = Path(temporary) / "staging"
            staging_root.mkdir()
            store = CuratorStore(database_path)
            service = CuratorService(
                store,
                ArtifactPurger(staging_root),
                MigrationEvidenceVerifier(),
                MigrationReviewAuthorizer(),
                project_id="migration-project",
            )
            goal = service.goal_start(
                "Preserve fact history through v15",
                (SuccessCriterion("done", "Existing fact remains readable"),),
            )
            fact, _ = service.goal_fact(
                goal.goal_id, FactKind.CHANGE, "Legacy fact has unknown origin"
            )
            store.close()

            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            connection.execute("DROP INDEX facts_source_event")
            connection.execute("ALTER TABLE facts DROP COLUMN source_event_id")
            connection.execute("PRAGMA user_version = 14")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                self.assertIsNone(migrated.get_fact(fact.fact_id).source_event_id)
                with migrated.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    self.assertIn(
                        "source_event_id",
                        {
                            row["name"]
                            for row in connection.execute(
                                "PRAGMA table_info(facts)"
                            ).fetchall()
                        },
                    )
            finally:
                migrated.close()

    def test_v12_rate_limiter_migration_rolls_back_on_incompatible_table(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v12-failed.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX request_rate_buckets_touched")
            connection.execute("DROP TABLE request_rate_buckets")
            connection.execute(
                "CREATE TABLE request_rate_buckets (unexpected TEXT)"
            )
            connection.execute("PRAGMA user_version = 12")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.OperationalError):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 12
                )
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(request_rate_buckets)"
                    ).fetchall()
                }
                self.assertEqual(columns, {"unexpected"})
            finally:
                connection.close()

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

    def test_unversioned_legacy_database_migrates_and_preserves_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "legacy.sqlite3"
            self._create_unversioned_legacy_database(database_path)

            store = CuratorStore(database_path)
            try:
                goal = store.get_goal("legacy-goal", "default")
                self.assertEqual(goal.problem, "Preserve data through schema migration")
                self.assertEqual(goal.lifecycle_revision, 2)
                self.assertEqual(goal.criteria_revision, 1)
                self.assertEqual(len(goal.success_criteria), 1)
                with store.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                store.close()

    def test_failed_migration_rolls_back_ddl_data_repairs_and_version_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "legacy.sqlite3"
            self._create_unversioned_legacy_database(database_path)
            connection = sqlite3.connect(database_path)
            connection.execute(
                """CREATE TRIGGER fail_lifecycle_revision_migration
                   BEFORE UPDATE ON goals
                   BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END"""
            )
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(sqlite3.IntegrityError, "injected migration failure"):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                goal_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(goals)")
                }
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 0
                )
                self.assertNotIn("project_id", goal_columns)
                self.assertNotIn("lifecycle_revision", goal_columns)
                self.assertEqual(tables, {"goals"})
                self.assertEqual(
                    connection.execute(
                        "SELECT problem FROM goals WHERE goal_id = 'legacy-goal'"
                    ).fetchone()[0],
                    "Preserve data through schema migration",
                )
                connection.execute("DROP TRIGGER fail_lifecycle_revision_migration")
                connection.commit()
            finally:
                connection.close()

            store = CuratorStore(database_path)
            try:
                self.assertEqual(
                    store.get_goal("legacy-goal", "default").lifecycle_revision, 2
                )
            finally:
                store.close()

    def test_v1_event_inbox_migrates_to_current_schema_without_losing_receipt(self) -> None:
        """Add router metadata and retry scheduling without losing receipts."""

        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v1.sqlite3"
            store = CuratorStore(database_path)
            event = EventEnvelope(
                "v1-event",
                "project-a",
                GoalStarted(
                    "v1-goal",
                    "Preserve an accepted event during migration",
                    (SuccessCriterion("done", "The goal remains recorded"),),
                ),
            )
            receipt, inserted = store.ingest_event(event)
            self.assertTrue(inserted)
            store.close()

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
            connection.execute("DROP INDEX event_inbox_source_order")
            connection.execute("DROP INDEX event_retry_audit_event")
            connection.execute("DROP TABLE event_retry_audit")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN source_sequence")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN source_id")
            connection.execute("ALTER TABLE event_inbox DROP COLUMN attempts")
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                after = migrated.event_receipt("project-a", "v1-event")
                self.assertEqual(after.payload_sha256, receipt.payload_sha256)
                self.assertEqual(after.status, receipt.status)
                self.assertEqual(after.attempts, 0)
                self.assertIsNone(after.next_attempt_at)
                with migrated.transaction() as migrated_connection:
                    self.assertEqual(
                        migrated_connection.execute(
                            "PRAGMA user_version"
                        ).fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    columns = {
                        row["name"]
                        for row in migrated_connection.execute(
                            "PRAGMA table_info(event_inbox)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {"attempts", "source_id", "source_sequence"} <= columns
                    )
                    self.assertIsNotNone(
                        migrated_connection.execute(
                            "SELECT name FROM sqlite_master "
                            "WHERE type = 'table' AND name = 'event_retry_audit'"
                        ).fetchone()
                    )
            finally:
                migrated.close()

    def test_v2_purge_targets_migrate_with_receipt_age_and_no_attempt(self) -> None:
        """Backfill v2 artifact age from its durable parent receipt."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database_path = root / "v2.sqlite3"
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
                ),
            )
            candidate = service.sde_assess(
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Durable migration fixture",
                (changed.fact_id, verified.fact_id),
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            target = staging / "temporary-artifact.json"
            target_hash = "b" * 64
            receipt = service.sde_confirm(
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                (ArtifactRef(str(target), target_hash),),
                artifact_inventory_complete=True,
            )
            self.assertFalse(receipt.canonical_persisted)
            store.close()

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
                stored_receipt = migrated.get_receipt(
                    receipt.receipt_id, "migration-project"
                )
                target_record = migrated.get_purge_target_records(
                    receipt.receipt_id, "migration-project"
                )[0]
                self.assertEqual(stored_receipt.receipt_id, receipt.receipt_id)
                self.assertEqual(target_record.artifact.path, str(target))
                self.assertEqual(target_record.created_at, receipt.created_at)
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

    def test_v5_purge_target_migrates_as_immediately_due(self) -> None:
        """Upgrade v5 purge receipts without inventing a retry delay."""

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
                goal.goal_id,
                Materiality.IMPLEMENTATION,
                "Purge retry migration fixture",
                (changed.fact_id, verified.fact_id),
            )
            self.assertIsNotNone(candidate)
            assert candidate is not None
            receipt = service.sde_confirm(
                candidate.candidate_id,
                ReviewDecision.APPROVED,
                (ArtifactRef(str(staging / "temporary.txt"), "b" * 64),),
                artifact_inventory_complete=True,
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
                self.assertEqual(
                    tuple(
                        item.receipt_id
                        for item in migrated.due_pending_purge_receipts(
                            "migration-project"
                        )
                    ),
                    (receipt.receipt_id,),
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

    def test_newer_schema_version_is_refused_without_downgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "future.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("PRAGMA user_version = 99")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)
            finally:
                connection.close()

    def test_v9_database_migrates_hold_release_audit_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v9.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_hold_status")
            for column in (
                "hold_created_at",
                "hold_created_by",
                "hold_released_at",
                "hold_released_by",
                "hold_release_rationale",
            ):
                connection.execute(f"ALTER TABLE purge_targets DROP COLUMN {column}")
            connection.execute(
                "CREATE INDEX purge_targets_hold_status "
                "ON purge_targets(status, retention_hold, receipt_id)"
            )
            connection.execute("PRAGMA user_version = 9")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(purge_targets)"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "hold_created_at",
                            "hold_created_by",
                            "hold_released_at",
                            "hold_released_by",
                            "hold_release_rationale",
                        }.issubset(columns)
                    )
                    index_columns = [
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA index_info(purge_targets_hold_status)"
                        ).fetchall()
                    ]
                    self.assertEqual(
                        index_columns,
                        ["status", "retention_hold", "hold_released_at", "receipt_id"],
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v10_database_migrates_durable_project_access_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v10.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP TABLE project_grant_revocations")
            connection.execute("DROP TABLE project_grants")
            connection.execute("DROP TABLE project_registry_audit")
            connection.execute("DROP TABLE project_registry")
            connection.execute("PRAGMA user_version = 10")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    tables = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    self.assertTrue(
                        {
                            "project_registry",
                            "project_registry_audit",
                            "project_grants",
                            "project_grant_revocations",
                        }.issubset(tables)
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()

    def test_v10_project_access_migration_rolls_back_and_retries_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v10-failed-access.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP TABLE project_grant_revocations")
            connection.execute("DROP TABLE project_grants")
            connection.execute("DROP TABLE project_registry_audit")
            connection.execute("DROP TABLE project_registry")
            connection.execute(
                "CREATE TABLE project_registry_audit (unexpected TEXT)"
            )
            connection.execute("PRAGMA user_version = 10")
            connection.commit()
            connection.close()

            with self.assertRaises(sqlite3.OperationalError):
                CuratorStore(database_path)

            connection = sqlite3.connect(database_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 10
                )
                self.assertNotIn("project_registry", tables)
                self.assertIn("project_registry_audit", tables)
                connection.execute("DROP TABLE project_registry_audit")
                connection.commit()
            finally:
                connection.close()

            retried = CuratorStore(database_path)
            try:
                with retried.transaction() as connection:
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
                    tables = {
                        row["name"]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table'"
                        ).fetchall()
                    }
                    self.assertIn("project_registry", tables)
                    self.assertIn("project_grants", tables)
            finally:
                retried.close()

    def test_v8_database_migrates_with_unheld_artifact_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database_path = Path(temporary) / "v8.sqlite3"
            store = CuratorStore(database_path)
            store.close()
            connection = sqlite3.connect(database_path)
            connection.execute("DROP INDEX purge_targets_hold_status")
            for column in (
                "hold_created_at",
                "hold_created_by",
                "hold_released_at",
                "hold_released_by",
                "hold_release_rationale",
            ):
                connection.execute(f"ALTER TABLE purge_targets DROP COLUMN {column}")
            connection.execute("ALTER TABLE purge_targets DROP COLUMN retention_hold")
            connection.execute("PRAGMA user_version = 8")
            connection.commit()
            connection.close()

            migrated = CuratorStore(database_path)
            try:
                with migrated.transaction() as connection:
                    columns = {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(purge_targets)"
                        ).fetchall()
                    }
                    self.assertIn("retention_hold", columns)
                    self.assertTrue(
                        {
                            "hold_created_at",
                            "hold_created_by",
                            "hold_released_at",
                            "hold_released_by",
                            "hold_release_rationale",
                        }.issubset(columns)
                    )
                    self.assertEqual(
                        connection.execute("PRAGMA user_version").fetchone()[0],
                        SQLITE_SCHEMA_VERSION,
                    )
            finally:
                migrated.close()


if __name__ == "__main__":
    unittest.main()
