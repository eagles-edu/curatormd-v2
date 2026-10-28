"""Consumer binding lifecycle and retirement tests."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sqlite3
from threading import Barrier
import unittest

from project_access_test_support import ProjectAccessTestCase

from curatormd_v2 import (
    ConflictError,
    ConsumerDrainAuthorizationRequest,
    ConsumerBindingTransitionRequest,
    CuratorStore,
    FingerprintBoundSQLiteProjectGrantAuthorizer,
    ProjectAccessManager,
    ProjectAction,
    ProjectAdministrationAction,
    ProjectAuthorizationBinding,
    SQLiteProjectGrantAuthorizer,
    TerminalEventDispositionRequest,
)
from curatormd_v2.events import EventEnvelope, GoalActivityObserved
from curatormd_v2.models import FactKind

class ConsumerBindingLifecycleTests(ProjectAccessTestCase):
    """Consumer binding lifecycle and retirement tests."""

    def test_consumer_binding_deregistration_is_separate_and_fences_old_grants(self) -> None:
        self._register()
        grant = self._grant()
        binding_config = ProjectAuthorizationBinding(
            project_id=self.project_id,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=self.config_sha256,
            backend_api_version=1,
            allowed_actions=frozenset({ProjectAction.READ}),
        )
        launcher = FingerprintBoundSQLiteProjectGrantAuthorizer(
            self.store, binding_config
        )
        self.assertTrue(launcher.authorize(self.reader, self.project_id, ProjectAction.READ))

        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistration_pending",
            rationale="Disable the detached consumer",
            expected_revision=1,
            transition_id="consumer-cutover-1",
        )
        pending = self.manager.transition_consumer_binding(
            self.operator, pending_request
        )
        self.assertEqual(
            (pending.binding.status, pending.binding.revision),
            ("deregistration_pending", 2),
        )
        self.assertFalse(launcher.authorize(self.reader, self.project_id, ProjectAction.READ))
        self.assertFalse(
            SQLiteProjectGrantAuthorizer(self.store).authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )
        self.assertEqual(self.store.get_project_registration(self.project_id).status, "active")
        self.assertEqual(self.store.get_project_registration(self.project_id).revision, 1)
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        with self.assertRaisesRegex(ConflictError, "consumer binding is not active"):
            self.manager.update_project_registration(
                self.operator,
                self._registration_request(
                    "Reject config changes during consumer deregistration",
                    config_sha256=hashlib.sha256(b"config-after-cutover").hexdigest(),
                    expected_revision=1,
                ),
                "config-after-cutover-1",
            )
        replay = self.manager.transition_consumer_binding(
            self.operator, pending_request
        )
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, pending.receipt)
        with self.assertRaisesRegex(ConflictError, "not active"):
            self._grant(ProjectAction.WRITE)

        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        final_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistered",
            rationale="All inventoried events have durable processed receipts",
            expected_revision=2,
            transition_id="consumer-cutover-final-1",
        )
        final = self.manager.transition_consumer_binding(self.operator, final_request)
        self.assertEqual((final.binding.status, final.binding.revision), ("deregistered", 3))
        self.assertEqual(final.binding.source_epoch, 1)
        self._allow_admin(ProjectAdministrationAction.VIEW)
        self.assertEqual(
            len(self.manager.list_consumer_binding_audit(self.operator, self.project_id)),
            3,
        )
        closed_grant = self.store.project_grants(self.project_id)[0]
        self.assertEqual(closed_grant.grant_id, grant.grant_id)
        self.assertEqual(closed_grant.revoked_by, self.operator.subject_id)
        self.assertEqual(closed_grant.revoke_rationale, pending_request.rationale)

    def test_consumer_deregistration_waits_for_unresolved_events(self) -> None:
        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending = self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Stop new consumer activity",
                expected_revision=1,
                transition_id="consumer-pending-unresolved",
            ),
        )
        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at)
                   VALUES (?, 'event-pending', 'test.event', ?, 0, 'received', ?)""",
                (self.project_id, "0" * 64, "2026-10-23T00:00:00.000Z"),
            )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        final_request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="deregistered",
            rationale="Attempt finalization with an unresolved event",
            expected_revision=pending.binding.revision,
            transition_id="consumer-final-unresolved",
        )
        with self.assertRaisesRegex(ConflictError, "unresolved source events"):
            self.manager.transition_consumer_binding(self.operator, final_request)
        self.assertEqual(
            self.store.get_consumer_binding(self.project_id).status,
            "deregistration_pending",
        )
        history = self.store.consumer_binding_audit(self.project_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1], pending.receipt)

    def test_concurrent_deregistration_transitions_compare_and_set_revision(self) -> None:
        """Two independent SQLite handles cannot both advance one binding revision."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        second_store = self.enterContext(CuratorStore(self.store.database))
        second_manager = ProjectAccessManager(second_store, self.admin)
        start = Barrier(2)
        requests = (
            ConsumerBindingTransitionRequest(
                self.project_id,
                "deregistration_pending",
                "Race first source cutover request",
                1,
                "concurrent-cutover-a",
            ),
            ConsumerBindingTransitionRequest(
                self.project_id,
                "deregistration_pending",
                "Race second source cutover request",
                1,
                "concurrent-cutover-b",
            ),
        )

        def transition(
            manager: ProjectAccessManager,
            request: ConsumerBindingTransitionRequest,
        ) -> str:
            start.wait(timeout=5)
            try:
                manager.transition_consumer_binding(self.operator, request)
            except ConflictError:
                return "conflict"
            return "committed"

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = tuple(
                future.result(timeout=10)
                for future in (
                    workers.submit(transition, self.manager, requests[0]),
                    workers.submit(transition, second_manager, requests[1]),
                )
            )

        self.assertCountEqual(results, ("committed", "conflict"))
        binding = self.store.get_consumer_binding(self.project_id)
        self.assertEqual((binding.status, binding.revision), ("deregistration_pending", 2))
        audit = self.store.consumer_binding_audit(self.project_id)
        self.assertEqual(len(audit), 2)
        self.assertIn(audit[-1].transition_id, {request.transition_id for request in requests})

    def test_deregistration_retry_after_lost_response_replays_durable_receipt(self) -> None:
        """A reconnect retry returns the committed transition without a second audit."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        request = ConsumerBindingTransitionRequest(
            self.project_id,
            "deregistration_pending",
            "Cut over after the source response was lost",
            1,
            "lost-response-cutover-1",
        )
        committed = self.manager.transition_consumer_binding(self.operator, request)

        reconnected_store = self.enterContext(CuratorStore(self.store.database))
        reconnected_manager = ProjectAccessManager(reconnected_store, self.admin)
        replay = reconnected_manager.transition_consumer_binding(self.operator, request)

        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, committed.receipt)
        self.assertEqual((replay.binding.status, replay.binding.revision),
                         ("deregistration_pending", 2))
        audit = self.store.consumer_binding_audit(self.project_id)
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[-1].transition_id, "lost-response-cutover-1")

    def test_drain_allows_only_the_reviewed_event_and_matching_profile(self) -> None:
        """A short drain cannot admit new IDs, changed envelopes, or other profiles."""

        self._register()
        event = EventEnvelope(
            "queued-event-1",
            self.project_id,
            GoalActivityObserved("goal-1", "fact-1", FactKind.CHANGE, "Done."),
            source_id="hermes-profile-alpha-generation-1",
            source_sequence=1,
        )
        self.store.ingest_event(event)
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending = self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                self.project_id,
                "deregistration_pending",
                "Stop new consumer work and review the queued event",
                1,
                "drain-transition-1",
            ),
        )
        count, inventory_digest = self.store.consumer_drain_inventory(self.project_id)
        self.assertEqual(count, 1)
        self._allow_admin(ProjectAdministrationAction.DRAIN)
        drain_request = ConsumerDrainAuthorizationRequest(
            project_id=self.project_id,
            transition_id=pending.receipt.transition_id,
            expected_revision=pending.binding.revision,
            expected_inventory_sha256=inventory_digest,
            lifetime_seconds=60,
            consumer_profile="alpha",
        )
        authorized_count, expires_at = self.manager.authorize_consumer_drain(
            self.operator, drain_request
        )
        self.assertEqual(authorized_count, 1)
        self.assertTrue(expires_at)
        replay_count, replay_expires_at = self.manager.authorize_consumer_drain(
            self.operator, drain_request
        )
        self.assertEqual(
            (replay_count, replay_expires_at), (authorized_count, expires_at)
        )
        self.assertTrue(
            self.store.consumer_drain_allows(self.operator.subject_id, "alpha", event)
        )
        self.assertFalse(
            self.store.consumer_drain_allows(self.operator.subject_id, "other", event)
        )
        self.assertFalse(
            self.store.consumer_drain_allows(
                self.operator.subject_id, "alpha", replace(event, event_id="new-event")
            )
        )
        retry, created = self.store.ingest_event(event)
        self.assertFalse(created)
        self.assertEqual(retry.event_id, event.event_id)
        with self.assertRaisesRegex(ConflictError, "does not accept new events"):
            self.store.ingest_event(replace(event, event_id="new-event"))

    def test_terminal_event_disposition_is_exact_ordered_and_replayable(self) -> None:
        """A fenced source can close one failed event without losing its receipt."""

        self._register()
        payload_canary = "terminal-disposition-private-payload-canary"
        event = EventEnvelope(
            "failed-event-1",
            self.project_id,
            GoalActivityObserved(
                "goal-1", "fact-1", FactKind.CHANGE, payload_canary
            ),
            source_id="source-generation-1",
            source_sequence=1,
        )
        received, _created = self.store.ingest_event(event)
        self.store.mark_event_failed(self.project_id, event.event_id, "adapter_error")
        failed = self.store.quarantine_event(self.project_id, event.event_id, 1)
        self.assertEqual(failed.status.value, "quarantined")
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        pending = self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                self.project_id,
                "deregistration_pending",
                "Fence the failed source before its terminal review",
                1,
                "terminal-review-cutover",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.VIEW)
        candidates = self.manager.terminal_event_inventory(
            self.operator, self.project_id, limit=1
        )
        self.assertTrue(candidates.complete)
        self.assertEqual(candidates.count_after_cursor, 1)
        self.assertEqual(candidates.events[0].event_id, event.event_id)
        self.assertEqual(candidates.events[0].payload_sha256, received.payload_sha256)
        observed = self.manager.lifecycle_status_snapshot(
            self.operator, self.project_id, event_limit=1
        )
        self.assertTrue(observed.complete)
        self.assertTrue(observed.observed_at)
        self.assertEqual(observed.project_status, "active")
        self.assertEqual(observed.consumer_binding.status, "deregistration_pending")
        self.assertEqual(observed.event_status_counts, (("quarantined", 1),))
        self.assertEqual(observed.unprocessed_event_count, 1)
        reader = sqlite3.connect(self.store.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        pinned_payload = reader.execute(
            "SELECT payload_json FROM event_inbox WHERE project_id = ? AND event_id = ?",
            (self.project_id, event.event_id),
        ).fetchone()[0]
        self.assertIn(payload_canary, pinned_payload)
        self._allow_admin(ProjectAdministrationAction.DISPOSE_EVENT)
        result, disposition = self.manager.terminally_dispose_event(
            self.operator,
            TerminalEventDispositionRequest(
                project_id=self.project_id,
                event_id=event.event_id,
                transition_id="terminal-disposition-1",
                rationale="Owner approves terminal disposition of this exact failed event",
                expected_binding_revision=pending.binding.revision,
                expected_source_epoch=pending.binding.source_epoch,
                expected_payload_sha256=received.payload_sha256,
            ),
        )
        self.assertEqual(result.status.value, "processed")
        self.assertEqual(result.disposition, "terminal_authorized")
        self.assertEqual(disposition.prior_status.value, "quarantined")
        self.assertEqual(disposition.payload_sha256, received.payload_sha256)
        self.assertNotIn(payload_canary, repr(result))
        self.assertNotIn(payload_canary, repr(disposition))
        with self.store.transaction() as connection:
            event_row = connection.execute(
                "SELECT status, payload_json, disposition FROM event_inbox "
                "WHERE project_id = ? AND event_id = ?",
                (self.project_id, event.event_id),
            ).fetchone()
            audit_row = connection.execute(
                "SELECT payload_sha256, rationale FROM terminal_event_dispositions "
                "WHERE project_id = ? AND event_id = ?",
                (self.project_id, event.event_id),
            ).fetchone()
        self.assertEqual(event_row["status"], "processed")
        self.assertIsNone(event_row["payload_json"])
        self.assertEqual(event_row["disposition"], "terminal_authorized")
        self.assertEqual(audit_row["payload_sha256"], received.payload_sha256)
        self.assertNotIn(payload_canary, repr(audit_row))
        database = Path(self.store.database)
        self.assertEqual(
            self.store.event_payload_scrub_pending_count(self.project_id), 1
        )
        wal_path = Path(f"{database}-wal")
        self.assertIn(payload_canary.encode(), wal_path.read_bytes())
        reader.execute("ROLLBACK")
        reader.close()
        self.assertEqual(self.store.consumer_drain_inventory(self.project_id)[0], 0)
        replay, replayed_disposition = self.manager.terminally_dispose_event(
            self.operator,
            TerminalEventDispositionRequest(
                project_id=self.project_id,
                event_id=event.event_id,
                transition_id="terminal-disposition-1",
                rationale="Owner approves terminal disposition of this exact failed event",
                expected_binding_revision=pending.binding.revision,
                expected_source_epoch=pending.binding.source_epoch,
                expected_payload_sha256=received.payload_sha256,
            ),
        )
        self.assertEqual(replay, result)
        self.assertEqual(replayed_disposition, disposition)
        self.assertEqual(
            self.store.event_payload_scrub_pending_count(self.project_id), 0
        )
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(f"{database}{suffix}")
            if candidate.exists():
                self.assertNotIn(payload_canary.encode(), candidate.read_bytes())
        finalized_status = self.manager.lifecycle_status_snapshot(
            self.operator, self.project_id, event_limit=1
        )
        self.assertEqual(finalized_status.event_status_counts, (("processed", 1),))
        self.assertEqual(finalized_status.unprocessed_event_count, 0)
        duplicate, is_new = self.store.ingest_event(event)
        self.assertFalse(is_new)
        self.assertEqual(duplicate.disposition, "terminal_authorized")

    def test_project_retirement_is_irreversible_and_keeps_records(self) -> None:
        """Retirement fences a project but preserves unresolved event records."""

        self._register()
        event = EventEnvelope(
            "preserved-pending-event",
            self.project_id,
            GoalActivityObserved("goal-1", "fact-1", FactKind.CHANGE, "Done."),
            source_id="retired-source-generation-1",
            source_sequence=1,
        )
        original_receipt, created = self.store.ingest_event(event)
        self.assertTrue(created)
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                self.project_id, "deregistration_pending", "Close consumer", 1,
                "retire-pending-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.RETIRE)
        receipt = self.manager.retire_project(
            self.operator, self.project_id, "Owner retires this project", 1,
            "retire-project-1",
        )
        self.assertEqual(receipt.retired_revision, 2)
        self.assertEqual(
            self.store.get_project_registration(self.project_id).status, "suspended"
        )
        self.assertEqual(self.store.get_project_retirement(self.project_id), receipt)
        with self.store.transaction() as connection:
            preserved_event = connection.execute(
                "SELECT status FROM event_inbox WHERE project_id = ? AND event_id = ?",
                (self.project_id, "preserved-pending-event"),
            ).fetchone()
        self.assertEqual(preserved_event["status"], "received")
        self.assertEqual(
            self.store.ingest_event(event), (original_receipt, False)
        )
        with self.assertRaisesRegex(ConflictError, "does not accept new events"):
            self.store.ingest_event(replace(event, event_id="post-retirement-event"))
        self.assertEqual(
            self.manager.retire_project(
                self.operator, self.project_id, "Owner retires this project", 1,
                "retire-project-1",
            ),
            receipt,
        )
        self._allow_admin(ProjectAdministrationAction.REACTIVATE)
        with self.assertRaisesRegex(ConflictError, "retired projects"):
            self._change_status("active", "Attempt to reopen retired project", 2,
                                "retire-reactivate-1")

    def test_reenrollment_rotates_source_epoch_without_restoring_grants(self) -> None:
        """A fresh source epoch requires explicit reviewed enrollment and grants."""

        self._register()
        original_grant = self._grant()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Cut over the old consumer source",
                expected_revision=1,
                transition_id="reenroll-pending-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistered",
                rationale="All old events have processed receipts",
                expected_revision=2,
                transition_id="reenroll-final-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.UPDATE)
        reviewed_config_sha = hashlib.sha256(b"reviewed-config-v2").hexdigest()
        updated = self.manager.update_project_registration(
            self.operator,
            self._registration_request(
                "Review the detached consumer's current repository config",
                config_sha256=reviewed_config_sha,
                expected_revision=1,
            ),
            "reenroll-config-review-1",
        )
        self.assertEqual(updated.registration.revision, 2)
        self._allow_admin(ProjectAdministrationAction.REENROLL)
        request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="active",
            rationale="Approve the fresh consumer source epoch",
            expected_revision=3,
            transition_id="reenroll-epoch-2",
            expected_source_epoch=1,
            expected_project_revision=2,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=reviewed_config_sha,
            backend_api_version=1,
        )

        result = self.manager.transition_consumer_binding(self.operator, request)

        self.assertEqual(result.binding.status, "active")
        self.assertEqual(result.binding.revision, 4)
        self.assertEqual(result.binding.source_epoch, 2)
        self.assertEqual(result.receipt.action, "reenrolled")
        self.assertEqual(result.receipt.source_epoch, 2)
        self.assertFalse(result.replayed)
        self.assertFalse(
            self.store.has_project_grant(
                self.reader.subject_id, self.project_id, ProjectAction.READ.value
            )
        )
        replay = self.manager.transition_consumer_binding(self.operator, request)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.receipt, result.receipt)
        self.assertEqual(
            self.store.project_grants(self.project_id)[0].grant_id,
            original_grant.grant_id,
        )

        self._grant()
        current_launcher = FingerprintBoundSQLiteProjectGrantAuthorizer(
            self.store,
            ProjectAuthorizationBinding(
                project_id=self.project_id,
                repository_fingerprint=self.repository_fingerprint,
                config_sha256=reviewed_config_sha,
                backend_api_version=1,
                allowed_actions=frozenset({ProjectAction.READ}),
            ),
        )
        self.assertTrue(
            current_launcher.authorize(
                self.reader, self.project_id, ProjectAction.READ
            )
        )

    def test_reenrollment_rejects_stale_epoch_and_unresolved_events(self) -> None:
        """Old source epochs and late pre-cutover receipts cannot be enrolled."""

        self._register()
        self._allow_admin(ProjectAdministrationAction.DEREGISTER)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistration_pending",
                rationale="Cut over the old consumer source",
                expected_revision=1,
                transition_id="reenroll-pending-open-1",
            ),
        )
        self._allow_admin(ProjectAdministrationAction.DEREGISTER_FINALIZE)
        self.manager.transition_consumer_binding(
            self.operator,
            ConsumerBindingTransitionRequest(
                project_id=self.project_id,
                status="deregistered",
                rationale="No old events were pending at cutover",
                expected_revision=2,
                transition_id="reenroll-final-open-1",
            ),
        )
        request = ConsumerBindingTransitionRequest(
            project_id=self.project_id,
            status="active",
            rationale="Approve the fresh consumer source epoch",
            expected_revision=3,
            transition_id="reenroll-epoch-stale",
            expected_source_epoch=2,
            expected_project_revision=1,
            repository_fingerprint=self.repository_fingerprint,
            config_sha256=self.config_sha256,
            backend_api_version=1,
        )
        self._allow_admin(ProjectAdministrationAction.REENROLL)
        with self.assertRaisesRegex(ConflictError, "source epoch is stale"):
            self.manager.transition_consumer_binding(self.operator, request)

        with self.store.transaction() as connection:
            connection.execute(
                """INSERT INTO event_inbox
                   (project_id, event_id, event_type, payload_sha256, payload_bytes,
                    status, received_at)
                   VALUES (?, 'late-old-event', 'test.event', ?, 0, 'received', ?)""",
                (self.project_id, "0" * 64, "2026-10-23T00:00:00.000Z"),
            )
        with self.assertRaisesRegex(ConflictError, "unresolved source events"):
            self.manager.transition_consumer_binding(
                self.operator,
                replace(request, expected_source_epoch=1),
            )
        binding = self.store.get_consumer_binding(self.project_id)
        self.assertEqual(
            (binding.status, binding.revision, binding.source_epoch),
            ("deregistered", 3, 1),
        )

if __name__ == "__main__":
    unittest.main()
