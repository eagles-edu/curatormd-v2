"""Exercise purge filesystem behavior."""
# pylint: disable=duplicate-code
# Parallel tests repeat setup to exercise distinct failure conditions.

from __future__ import annotations

import hashlib
import os
from unittest.mock import patch
from uuid import uuid4

from purge_fixtures import TestReviewAuthorizer, TestVerifier
from purge_test_support import PurgeTestSupport

from curatormd_v2 import (
    ArtifactPurger,
    ArtifactRef,
    ArtifactStatus,
    ConflictError,
    CuratorService,
    CuratorStore,
    PurgeError,
    PurgeOutcome,
    PurgeStatus,
    ReacquisitionAction,
    ReviewDecision,
    SDEConfirmationRequest,
)
from curatormd_v2.store import NotFoundError
from curatormd_v2.store_requests import PurgeTargetResult


class PurgeFilesystemTests(PurgeTestSupport):
    """Exercise purge filesystem behavior."""

    def test_hash_mismatch_never_deletes_artifact_and_reports_pending(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        path.write_bytes(b"changed after approval reference")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].outcome, PurgeOutcome.CHANGED)
        self.assertEqual(targets[0].error, "hash_mismatch")


    def test_replacement_after_hash_verification_is_not_unlinked(self) -> None:
        """Leave an unapproved in-root replacement intact and report pending."""

        candidate_id = self.candidate("path replacement race")
        path, artifact = self.artifact("replacement-race.json")
        original_stat = path.stat()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        real_fstat = os.fstat
        matching_fstats = 0

        def replace_after_hash(file_descriptor: int) -> os.stat_result:
            nonlocal matching_fstats
            metadata = real_fstat(file_descriptor)
            if (metadata.st_dev, metadata.st_ino) == (
                original_stat.st_dev,
                original_stat.st_ino,
            ):
                matching_fstats += 1
                if matching_fstats == 2:
                    path.unlink()
                    path.write_bytes(b"unapproved replacement")
            return metadata

        with patch("curatormd_v2.purge.os.fstat", side_effect=replace_after_hash):
            persisted = self.persist_canonical(receipt)

        self.assertEqual(matching_fstats, 2)
        self.assertEqual(path.read_bytes(), b"unapproved replacement")
        self.assertEqual(persisted.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].error, "path_changed")


    def test_artifact_outside_root_is_not_deleted(self) -> None:
        candidate_id = self.candidate()
        outside = self.root / "outside.json"
        outside.write_text("private", encoding="utf-8")
        artifact = ArtifactRef(
            str(outside), hashlib.sha256(b"private").hexdigest(),
            occurrence_id=uuid4().hex,
            reacquisition_action=ReacquisitionAction.REACQUIRE_FROM_SOURCE,
        )
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(outside.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].error, "outside_staging_root")


    def test_purge_errors_do_not_retain_private_paths(self) -> None:
        """Path confinement and filesystem failures expose no chained path."""

        private_path = "/srv/private/customer/staged.json"
        outside = ArtifactRef(private_path, hashlib.sha256(b"secret").hexdigest())
        with self.assertRaisesRegex(
            PurgeError, "artifact is outside the configured staging root"
        ) as raised:
            ArtifactPurger(self.stage).purge(outside)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

        in_scope = self.stage / "inside.json"
        in_scope.write_text("secret", encoding="utf-8")
        artifact = ArtifactRef(
            str(in_scope), hashlib.sha256(b"secret").hexdigest()
        )
        with patch(
            "curatormd_v2.purge.os.fstat",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            with self.assertRaisesRegex(
                PurgeError, "cannot safely inspect or remove artifact"
            ) as raised:
                ArtifactPurger(self.stage).purge(artifact)
        self.assertNotIn(private_path, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)


    def test_store_missing_purge_target_errors_do_not_echo_path(self) -> None:
        """Direct store failures do not retain caller-supplied artifact paths."""

        candidate_id = self.candidate("missing purge target")
        _, artifact = self.artifact("existing.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        private_path = "/srv/private/customer/not-in-this-receipt.json"

        with self.assertRaises(NotFoundError) as raised:
            self.store.release_artifact_hold(
                receipt.receipt_id,
                private_path,
                self.service.project_id,
                "test-reviewer",
                "Owner requested a hold release",
            )
        self.assertNotIn(private_path, str(raised.exception))

        with self.assertRaises(NotFoundError) as raised:
            self.store.record_purge_result(
                receipt.receipt_id,
                private_path,
                PurgeTargetResult(ArtifactStatus.FAILED, "filesystem_error"),
                self.service.project_id,
            )
        self.assertNotIn(private_path, str(raised.exception))


    def test_directories_and_symlinks_are_never_purged(self) -> None:
        nested = self.stage / "nested"
        nested.mkdir()
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(str(nested), hashlib.sha256(b"").hexdigest())
            )
        target = self.stage / "target.txt"
        target.write_text("target", encoding="utf-8")
        link = self.stage / "link.txt"
        link.symlink_to(target)
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(str(link), hashlib.sha256(b"target").hexdigest())
            )
        self.assertTrue(target.exists())

        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        outside_file = outside_dir / "keep.txt"
        outside_file.write_text("keep", encoding="utf-8")
        directory_link = self.stage / "directory-link"
        directory_link.symlink_to(outside_dir, target_is_directory=True)
        with self.assertRaises(PurgeError):
            ArtifactPurger(self.stage).purge(
                ArtifactRef(
                    str(directory_link / outside_file.name),
                    hashlib.sha256(b"keep").hexdigest(),
                )
            )
        self.assertTrue(outside_file.exists())


    def test_missing_artifact_retry_is_idempotent(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        path.unlink()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.PURGED)
        self.assertEqual(targets[0].outcome, PurgeOutcome.ALREADY_ABSENT)


    def test_unlink_failure_stays_pending_and_retries_same_receipt(self) -> None:
        """Keep an unlink error visible and retry only its approved receipt."""

        candidate_id = self.candidate("unlink failure recovery")
        path, artifact = self.artifact("unlink-failure.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )

        private_path = "/srv/private/customer/unlink-failure.json"
        with patch(
            "curatormd_v2.purge.os.unlink",
            side_effect=OSError(f"permission denied: {private_path}"),
        ):
            receipt = self.persist_canonical(receipt)

        self.assertTrue(path.exists())
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.FAILED)
        self.assertEqual(targets[0].outcome, PurgeOutcome.FAILED)
        self.assertEqual(targets[0].error, "filesystem_error")
        self.assertNotIn(private_path, targets[0].error or "")

        retried = self.service.retry_pending_purges()

        self.assertEqual(tuple(item.receipt_id for item in retried), (receipt.receipt_id,))
        self.assertFalse(path.exists())
        self.assertEqual(
            self.store.get_receipt(receipt.receipt_id).purge_status,
            PurgeStatus.COMPLETE,
        )
        _, targets = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(targets[0].status, ArtifactStatus.PURGED)
        self.assertEqual(targets[0].outcome, PurgeOutcome.DELETED)


    def test_incomplete_empty_inventory_stays_pending_until_explicitly_complete(self) -> None:
        candidate_id = self.candidate()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(),
                artifact_inventory_complete=False,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.PURGE_PENDING)
        self.assertFalse(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts()[0].receipt_id, receipt.receipt_id)
        receipt = self.service.artifact_inventory_complete(receipt.receipt_id, ())
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertTrue(receipt.artifact_inventory_complete)
        self.assertEqual(self.store.pending_receipts(), ())


    def test_partial_inventory_blocks_all_deletion_until_manifest_is_complete(self) -> None:
        candidate_id = self.candidate()
        path, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(artifact,),
                artifact_inventory_complete=False,
            )
        )
        receipt = self.persist_canonical(receipt)
        self.assertTrue(path.exists())
        _, target_status = self.service.artifact_purge_status(receipt.receipt_id)
        self.assertEqual(
            target_status[0].safe_recovery_action,
            "artifact_inventory_complete",
        )
        pending = self.service.retry_pending_purges()
        self.assertEqual(pending[0].purge_status, PurgeStatus.PURGE_PENDING)
        self.assertTrue(path.exists())
        receipt = self.service.artifact_inventory_complete(
            receipt.receipt_id, (artifact,)
        )
        receipt = self.persist_canonical(receipt)
        self.assertEqual(receipt.purge_status, PurgeStatus.COMPLETE)
        self.assertFalse(path.exists())


    def test_replayed_review_cannot_change_approved_artifact_list(self) -> None:
        candidate_id = self.candidate()
        _, original = self.artifact("original.json")
        self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.APPROVED,
                artifacts=(original,),
                artifact_inventory_complete=True,
            )
        )
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.REJECTED,
                    artifacts=(original,),
                    artifact_inventory_complete=True,
                )
            )
        _, replacement = self.artifact("replacement.json")
        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(replacement,),
                    artifact_inventory_complete=True,
                )
            )


    def test_rejected_review_decision_cannot_be_changed_to_approved(self) -> None:
        candidate_id = self.candidate("immutable rejection")
        _, artifact = self.artifact("rejected.json")
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )

        with self.assertRaises(ConflictError):
            self.service.sde_confirm(
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision.APPROVED,
                    artifacts=(artifact,),
                    artifact_inventory_complete=True,
                )
            )

        stored = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(stored.decision, ReviewDecision.REJECTED)


    def test_receipt_and_facts_survive_store_reopen(self) -> None:
        candidate_id = self.candidate()
        _, artifact = self.artifact()
        receipt = self.service.sde_confirm(
            SDEConfirmationRequest(
                candidate_id=candidate_id,
                decision=ReviewDecision.REJECTED,
                artifacts=(artifact,),
                artifact_inventory_complete=True,
            )
        )
        receipt = self.persist_canonical(receipt)
        database = self.root / "curator.sqlite3"
        self.store.close()
        self.store = CuratorStore(database)
        self.service = CuratorService(
            self.store,
            ArtifactPurger(self.stage),
            TestVerifier(),
            TestReviewAuthorizer(),
        )
        reloaded = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(reloaded.decision, ReviewDecision.REJECTED)
        self.assertEqual(reloaded.purge_status, PurgeStatus.COMPLETE)
        self.assertEqual(len(self.store.list_facts(self.goal.goal_id)), 2)
