"""Focused project-plugin event lifecycle tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Event, Thread

from project_plugin_test_support import (
    PausingEvidenceVerifier,
    ProjectPluginTestSupport,
)

from curatormd_v2 import (
    ConsumerBindingTransitionRequest,
    CuratorService,
    CuratorStore,
    EvidenceOutcome,
    EvidenceRef,
    ProjectStatusChangeRequest,
    SuccessCriterion,
)
from curatormd_v2.events import (
    EventEnvelope,
    FactRecorded,
    GoalActivityObserved,
    GoalStarted,
)
from curatormd_v2.models import FactKind
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import ConflictError, NotFoundError
from curatormd_v2.store_requests import ConsumerDrainStoreRequest
from curatormd_v2.testing import assert_goal_started_event_contract


class ProjectPluginEventLifecycleTests(ProjectPluginTestSupport):
    """Exercise project-plugin event lifecycle behavior."""

    def test_event_verification_runs_outside_transaction_and_rechecks_revision(
        self,
    ) -> None:
        """A project cutover during evidence proof prevents the event commit."""

        config = ProjectConfig.load(self.root)
        verifier_entered = Event()
        release_verifier = Event()
        verifier = PausingEvidenceVerifier(
            self.store, verifier_entered, release_verifier
        )
        plugin = ProjectPlugin.bind(config, self.store, verifier)
        standalone_service = CuratorService(
            self.store,
            plugin.service.purger,
            verifier,
            project_id=config.project_id,
        )
        goal = self._goal(plugin, "event-proof-cutover-goal")
        evidence = EvidenceRef(
            "unit-test",
            "test-proof:event-cutover",
            hashlib.sha256(b"event-cutover-proof").hexdigest(),
            EvidenceOutcome.PASSED,
        )
        event = EventEnvelope(
            event_id="event-proof-cutover",
            project_id=config.project_id,
            source_id="test-producer",
            payload=FactRecorded(
                goal_id=goal.goal_id,
                fact_id="event-proof-cutover-fact",
                kind=FactKind.VERIFICATION,
                bullet="The event evidence was verified",
                criterion_id="verified",
                evidence=(evidence,),
            ),
        )
        failures: list[BaseException] = []

        def process() -> None:
            try:
                standalone_service.process_event(event)
            except BaseException as exc:  # pylint: disable=broad-exception-caught
                failures.append(exc)

        worker = Thread(target=process)
        worker.start()
        self.assertTrue(verifier_entered.wait(timeout=3))
        secondary_store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(secondary_store.close)
        registration = secondary_store.get_project_registration(config.project_id)
        secondary_store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Suspend during event evidence verification",
                expected_revision=registration.revision,
                transition_id="event-proof-cutover-suspend",
            ),
            "test-admin",
        )
        release_verifier.set()
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(verifier.transaction_states, [False])
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ConflictError)
        with self.assertRaises(NotFoundError):
            self.store.get_fact("event-proof-cutover-fact", config.project_id)
        self.assertEqual(
            self.store.event_receipt(config.project_id, event.event_id).status.value,
            "received",
        )

    def test_reenrollment_fences_old_plugin_and_bound_service_writes(self) -> None:
        """Old plugin objects cannot write through a fresh consumer epoch."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        binding = self.store.get_consumer_binding(config.project_id)
        pending = self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id=config.project_id,
                status="deregistration_pending",
                rationale="Fence the old consumer instance",
                expected_revision=binding.revision,
                transition_id="plugin-stale-pending",
            ),
            "test-admin",
        )
        deregistered = self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id=config.project_id,
                status="deregistered",
                rationale="Finish the empty consumer drain",
                expected_revision=pending.binding.revision,
                transition_id="plugin-stale-deregistered",
            ),
            "test-admin",
        )
        self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id=config.project_id,
                status="active",
                rationale="Enroll the reviewed source epoch",
                expected_revision=deregistered.binding.revision,
                transition_id="plugin-stale-reenrolled",
                expected_source_epoch=deregistered.binding.source_epoch,
                expected_project_revision=1,
                repository_fingerprint=config.repository_fingerprint,
                config_sha256=config.config_sha256,
                backend_api_version=config.backend_api_version,
            ),
            "test-admin",
        )

        criterion = SuccessCriterion("fenced", "No old binding can write")
        with self.assertRaisesRegex(ConflictError, "consumer lifecycle changed"):
            plugin.goal_start_from_request(
                "Reject writes from the old plugin instance", (criterion,)
            )
        with self.assertRaisesRegex(ConflictError, "consumer lifecycle changed"):
            plugin.service.goal_start(
                "Reject direct writes from the old service instance", (criterion,)
            )
        self.assertEqual(plugin.goal_list(), ())

    def test_old_plugin_allows_only_an_exact_attended_drain_event(self) -> None:
        """A stale binding may finish its reviewed event, but admit no new ID."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal = self._goal(plugin, "drain-goal")
        event = EventEnvelope(
            event_id="drain-event-1",
            project_id=config.project_id,
            source_id="consumer-generation-1",
            source_sequence=1,
            payload=GoalActivityObserved(
                goal.goal_id, "drain-fact-1", FactKind.CHANGE, "Drained once."
            ),
        )
        self.store.ingest_event(event)
        binding = self.store.get_consumer_binding(config.project_id)
        pending = self.store.transition_consumer_binding(
            ConsumerBindingTransitionRequest(
                project_id=config.project_id,
                status="deregistration_pending",
                rationale="Drain only the reviewed queued event",
                expected_revision=binding.revision,
                transition_id="plugin-drain-pending",
            ),
            "test-admin",
        )
        count, inventory_sha256 = self.store.consumer_drain_inventory(config.project_id)
        self.assertEqual(count, 1)
        self.store.authorize_consumer_drain(
            ConsumerDrainStoreRequest(
                project_id=config.project_id,
                transition_id=pending.receipt.transition_id,
                actor_id="test-admin",
                caller_subject="test-consumer",
                caller_profile="test-profile",
                expected_revision=pending.binding.revision,
                expected_inventory_sha256=inventory_sha256,
                lifetime_seconds=60,
            )
        )

        receipt = plugin.process_event(
            event, drain_caller=("test-consumer", "test-profile")
        )

        self.assertEqual(receipt.status.value, "processed")
        self.assertEqual(
            self.store.get_fact("drain-fact-1", config.project_id).bullet,
            "Drained once.",
        )
        new_event = EventEnvelope(
            event_id="drain-event-not-in-inventory",
            project_id=config.project_id,
            source_id=event.source_id,
            source_sequence=2,
            payload=GoalActivityObserved(
                goal.goal_id,
                "drain-fact-2",
                FactKind.CHANGE,
                "Must not be applied.",
            ),
        )
        with self.assertRaisesRegex(ConflictError, "consumer lifecycle changed"):
            plugin.process_event(
                new_event, drain_caller=("test-consumer", "test-profile")
            )
        with self.assertRaises(NotFoundError):
            self.store.event_receipt(config.project_id, new_event.event_id)

    def test_reusable_producer_backend_contract_assertions(self) -> None:
        """Exercise the importable contract helper against the reference plugin."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        event = EventEnvelope(
            event_id="shared-contract-event-1",
            project_id="consumer-a",
            source_id="contract-test-producer",
            source_sequence=1,
            payload=GoalStarted(
                goal_id="shared-contract-goal-1",
                problem="Preserve producer supplied goal contract fields",
                success_criteria=(
                    SuccessCriterion("persisted", "All supplied fields are retained"),
                ),
                owner="contract-test-owner",
                next_action="Verify the consumer implementation",
            ),
        )

        evidence = assert_goal_started_event_contract(
            plugin,
            event,
            expected_project_id="consumer-a",
        )

        self.assertEqual(evidence.project_id, "consumer-a")
        self.assertEqual(evidence.event_id, event.event_id)
        self.assertEqual(evidence.event_payload_bytes_retained, 0)
        self.assertGreaterEqual(
            evidence.event_payload_bytes_received,
            evidence.event_payload_bytes,
        )
