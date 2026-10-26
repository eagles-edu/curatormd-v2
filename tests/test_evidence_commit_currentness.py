"""Completion must recheck local evidence lease expiry at the commit edge."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

from evidence_fixtures import attest_test_evidence

from curatormd_v2 import ArtifactPurger, CuratorService, GoalStatus
from curatormd_v2.events import EventEnvelope, EventInboxReceipt, GoalFinishRequested
from curatormd_v2.evidence import EvidenceVerificationContext
from curatormd_v2.models import (
    EvidenceAttestation,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    GoalCard,
    SuccessCriterion,
)
from curatormd_v2.store import CuratorStore


class _MutableDateTime(datetime):
    """Supply a deterministic clock for the verification/commit boundary."""

    current = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        if tz is None:
            return cls.current.replace(tzinfo=None)
        return cls.current.astimezone(tz)


class _ExpiringVerifier:
    """Return a normal receipt for recording, then a short lease for finish."""

    # pylint: disable=too-few-public-methods  # Test-only evidence verifier.

    def __init__(self) -> None:
        self.expiring = False

    def attest(
        self,
        evidence: EvidenceRef,
        context: EvidenceVerificationContext,
    ) -> EvidenceAttestation:
        """Return the fixture receipt with a controllable finish lease."""

        if not self.expiring:
            return attest_test_evidence(evidence, context)
        receipt = attest_test_evidence(evidence, context)
        return replace(
            receipt,
            valid_until=(context.now_utc + timedelta(seconds=1)).isoformat(
                timespec="microseconds"
            ),
        )


class EvidenceCommitCurrentnessTests(unittest.TestCase):
    """Exercise both direct and event-driven completion after lease expiry."""

    def test_direct_finish_does_not_use_an_expired_pretransaction_attestation(self) -> None:
        goal, service, verifier = self._service_fixture()
        entered, release = Event(), Event()

        @contextmanager
        def pause_after_verification(
            _revision: int | None,
        ) -> Generator[None, None, None]:
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release the completion fence")
            yield

        result: list[GoalCard] = []
        failure: list[Exception] = []

        def finish() -> None:
            try:
                result.append(service.goal_finish(goal.goal_id, "Complete task"))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                failure.append(exc)

        verifier.expiring = True
        _MutableDateTime.current = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        with patch("curatormd_v2.service_goal_lifecycle.datetime", _MutableDateTime):
            with patch.object(service, "_effect_fence", pause_after_verification):
                worker = Thread(target=finish)
                worker.start()
                self.assertTrue(entered.wait(5), "verification did not reach the fence")
                _MutableDateTime.current += timedelta(seconds=2)
                release.set()
                worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(failure, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, GoalStatus.OPEN)

    def test_event_finish_does_not_use_an_expired_pretransaction_attestation(self) -> None:
        goal, service, verifier = self._service_fixture()
        entered, release = Event(), Event()
        guard_count = 0

        @contextmanager
        def pause_after_verification() -> Generator[None, None, None]:
            nonlocal guard_count
            guard_count += 1
            if guard_count == 2:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("test did not release the completion fence")
            yield

        event = EventEnvelope(
            "expire-proof-before-event-finish",
            "commit-currentness-project",
            GoalFinishRequested(goal.goal_id, "Complete task"),
        )
        result: list[EventInboxReceipt] = []
        failure: list[Exception] = []

        def finish() -> None:
            try:
                result.append(
                    service.process_event(
                        event, effect_fence=pause_after_verification
                    )
                )
            except Exception as exc:  # pylint: disable=broad-exception-caught
                failure.append(exc)

        verifier.expiring = True
        _MutableDateTime.current = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
        with patch("curatormd_v2.service_goal_lifecycle.datetime", _MutableDateTime):
            worker = Thread(target=finish)
            worker.start()
            self.assertTrue(entered.wait(5), "event verification did not reach the fence")
            _MutableDateTime.current += timedelta(seconds=2)
            release.set()
            worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(failure, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status.value, "processed")
        self.assertEqual(
            service.goal_status(goal.goal_id).goal.status, GoalStatus.OPEN
        )

    def _service_fixture(
        self,
    ) -> tuple[GoalCard, CuratorService, _ExpiringVerifier]:
        temporary = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        root = Path(temporary)
        stage = root / "stage"
        stage.mkdir()
        store = CuratorStore(root / "curator.sqlite3")
        self.addCleanup(store.close)
        verifier = _ExpiringVerifier()
        service = CuratorService(
            store,
            ArtifactPurger(stage),
            verifier,
            project_id="commit-currentness-project",
        )
        goal = service.goal_start(
            "Prove commit-time evidence currentness",
            (SuccessCriterion("proof", "Evidence remains current at commit"),),
        )
        service.goal_fact(
            goal.goal_id,
            FactKind.VERIFICATION,
            "Criterion verified",
            criterion_id="proof",
            evidence=(
                EvidenceRef(
                    "test", "test-proof:commit-currentness", "c" * 64,
                    EvidenceOutcome.PASSED,
                ),
            ),
        )
        return goal, service, verifier


if __name__ == "__main__":
    unittest.main()
