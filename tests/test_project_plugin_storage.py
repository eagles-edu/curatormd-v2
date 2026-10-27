"""Focused project-plugin storage and expiry tests."""

from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import shutil
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from store_test_support import patch_store_symbol

from project_plugin_test_support import ProjectPluginTestSupport
from purge_fixtures import TestReviewAuthorizer, approved_empty_inventory_request

from curatormd_v2 import (
    CuratorStore,
    ProjectStatusChangeRequest,
    backup_database,
    restore_database,
)
from curatormd_v2.models import FactKind, Materiality, SDECandidate, SDEStatus
from curatormd_v2.project_config import ProjectConfig
from curatormd_v2.project_plugin import ProjectPlugin
from curatormd_v2.store import ConflictError


class ProjectPluginStorageAndExpiryTests(ProjectPluginTestSupport):
    """Exercise project-plugin storage and expiry behavior."""

    def test_storage_usage_scans_sizes_without_following_staging_symlinks(self) -> None:
        """Measure nested regular files, but expose a skipped link as incomplete."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        nested = self.stage / "nested"
        nested.mkdir(parents=True)
        (nested / "small.bin").write_bytes(b"12345")
        outside = Path(self.temporary) / "outside.bin"
        outside.write_bytes(b"must not count or be followed")
        (self.stage / "escape").symlink_to(outside)

        usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.regular_file_count, 1)
        self.assertEqual(usage.observed_file_bytes, 5)
        self.assertEqual(usage.directory_count, 1)
        self.assertEqual(usage.symlink_count, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "symlink_skipped")

    def test_storage_usage_marks_a_bounded_partial_scan_incomplete(self) -> None:
        """Stop after the configured entry ceiling and report partial results."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "first.bin").write_bytes(b"a")
        (self.stage / "second.bin").write_bytes(b"bb")

        with patch("curatormd_v2.project_plugin_staging.MAX_STAGING_SCAN_ENTRIES", 1):
            usage = plugin.storage_usage().staging

        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.entries_scanned, 1)
        self.assertFalse(usage.inventory_complete)
        self.assertEqual(usage.error_code, "entry_limit")

    def test_storage_usage_attributes_bytes_to_fixed_temporary_classes(self) -> None:
        """Attribute repository staging totals without exposing artifact names."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        (self.stage / "goal-classes" / "cue").mkdir(parents=True)
        (self.stage / "goal-classes" / "cue" / "a.bin").write_bytes(b"123")
        (self.stage / "goal-classes" / "raw-chat" / "nested").mkdir(parents=True)
        (self.stage / "goal-classes" / "raw-chat" / "nested" / "b.bin").write_bytes(
            b"12345"
        )
        (self.stage / "legacy-root-file.bin").write_bytes(b"12")

        usage = plugin.storage_usage().staging

        assert usage is not None
        by_class = {item.artifact_class.value: item for item in usage.classes}
        self.assertEqual(usage.regular_file_count, 3)
        self.assertEqual(usage.observed_file_bytes, 10)
        self.assertEqual(by_class["cue"].regular_file_count, 1)
        self.assertEqual(by_class["cue"].observed_file_bytes, 3)
        self.assertEqual(by_class["raw-chat"].regular_file_count, 1)
        self.assertEqual(by_class["raw-chat"].observed_file_bytes, 5)
        self.assertEqual(by_class["other"].regular_file_count, 1)
        self.assertEqual(by_class["other"].observed_file_bytes, 2)
        self.assertTrue(usage.inventory_complete)

    def test_discover_staging_artifacts_streams_hashes_and_returns_exact_paths(
        self,
    ) -> None:
        """Hash regular files in scope while omitting no-follow symlinks."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "scan-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        nested = goal_stage / "nested"
        nested.mkdir(parents=True)
        artifact = nested / "cue.json"
        artifact.write_bytes(b'{"temporary":true}')
        outside = Path(self.temporary) / "outside.json"
        outside.write_bytes(b"outside")
        (goal_stage / "escape.json").symlink_to(outside)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "symlink_skipped")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.scope_goal_id, goal_id)
        self.assertEqual(len(inventory.artifacts), 1)
        self.assertEqual(inventory.artifacts[0].path, str(artifact))
        self.assertEqual(
            inventory.artifacts[0].sha256,
            hashlib.sha256(b'{"temporary":true}').hexdigest(),
        )

    def test_discovery_marks_file_changed_after_open_incomplete(self) -> None:
        """A same-file mutation after stat cannot produce an approved manifest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "changed-while-hashing"
        self._goal(plugin, goal_id)
        artifact = self.stage / goal_id / "scratch" / "changing.tmp"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"original payload with a longer size")
        original_open = os.open
        mutated = False

        def open_then_mutate(
            path: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
        ) -> int:
            nonlocal mutated
            descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
            if path == artifact.name and not mutated:
                mutated = True
                artifact.write_bytes(b"changed")
            return descriptor

        supported_dir_fd = os.supports_dir_fd
        with patch(
            "curatormd_v2.project_plugin_staging.os.open",
            side_effect=open_then_mutate,
        ) as patched_open:
            with patch(
                "curatormd_v2.project_plugin_staging.os.supports_dir_fd",
                supported_dir_fd | {patched_open},
            ):
                inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "changed_during_scan")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.artifacts, ())


    def test_unreadable_staged_file_is_incomplete_and_retryable(self) -> None:
        """Report a fixed permission code when an enumerated file cannot be read."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "unreadable-staged-file"
        self._goal(plugin, goal_id)
        artifact = self.stage / goal_id / "scratch" / "private.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"private payload")
        private_path = "/srv/private/customer/staging/private.bin"
        original_open = os.open

        def fail_only_artifact_open(
            path: str,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if path == artifact.name and dir_fd is not None:
                raise PermissionError(errno.EACCES, f"cannot read {private_path}")
            return original_open(path, flags, mode, dir_fd=dir_fd)

        supported_dir_fd = os.supports_dir_fd
        with patch(
            "curatormd_v2.project_plugin_staging.os.open",
            side_effect=fail_only_artifact_open,
        ) as patched_open:
            with patch(
                "curatormd_v2.project_plugin_staging.os.supports_dir_fd",
                supported_dir_fd | {patched_open},
            ):
                inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "permission_denied")
        self.assertIsNone(inventory.manifest_sha256)
        self.assertEqual(inventory.artifacts, ())
        self.assertNotIn(private_path, repr(inventory))

        retried = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(retried.usage.inventory_complete)
        self.assertIsNotNone(retried.manifest_sha256)
        self.assertEqual(len(retried.artifacts), 1)
        self.assertEqual(
            retried.artifacts[0].sha256,
            hashlib.sha256(b"private payload").hexdigest(),
        )

    def test_discovery_includes_temporary_artifact_classes_and_duplicates(self) -> None:
        """Inventory each temporary class, retaining same-content file paths."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "classes-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        artifact_files = {
            "raw-chat/session.jsonl": b"temporary chat bytes",
            "cue/event.json": b"cue bytes",
            "import/source.md": b"import bytes",
            "scratch/work.tmp": b"scratch bytes",
            "generated/intermediate.json": b"intermediate bytes",
            "duplicates/copy.tmp": b"scratch bytes",
        }
        for relative_path, contents in artifact_files.items():
            path = goal_stage / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)

        inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertTrue(inventory.usage.inventory_complete)
        self.assertIsNotNone(inventory.manifest_sha256)
        self.assertEqual(
            {
                Path(item.path).relative_to(goal_stage).as_posix()
                for item in inventory.artifacts
            },
            set(artifact_files),
        )
        scratch_hashes = {
            item.sha256
            for item in inventory.artifacts
            if Path(item.path).relative_to(goal_stage).as_posix()
            in {"scratch/work.tmp", "duplicates/copy.tmp"}
        }
        self.assertEqual(scratch_hashes, {hashlib.sha256(b"scratch bytes").hexdigest()})

    def test_occurrence_registry_is_stable_and_separate_from_expiry_age(self) -> None:
        """Persist content-free file identity without granting direct files age."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "occurrence-registry-goal"
        self._goal(plugin, goal_id)
        path = self.stage / goal_id / "scratch" / "manual.tmp"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"same transient bytes")

        first = plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertIsNotNone(first.occurrence_id)
        second = plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertEqual(second.occurrence_id, first.occurrence_id)

        reopened_store = CuratorStore(Path(self.temporary) / "global.sqlite3")
        self.addCleanup(reopened_store.close)
        reopened_plugin = ProjectPlugin.bind(
            ProjectConfig.load(self.root), reopened_store
        )
        after_reopen = reopened_plugin.discover_staging_artifacts(goal_id).artifacts[0]
        self.assertEqual(after_reopen.occurrence_id, first.occurrence_id)

        replacement = path.with_name("replacement.tmp")
        replacement.write_bytes(b"same transient bytes")
        replacement.replace(path)
        after_replacement = reopened_plugin.discover_staging_artifacts(
            goal_id
        ).artifacts[0]
        self.assertNotEqual(after_replacement.occurrence_id, first.occurrence_id)

        expiry = reopened_plugin.discover_expired_staging_artifacts(
            datetime.now(UTC) + timedelta(hours=73)
        )
        self.assertFalse(expiry.inventory_complete)
        self.assertEqual(expiry.unknown_age_count, 1)
        self.assertEqual(expiry.eligible_artifacts, ())

    def test_discovery_hash_byte_limit_returns_no_false_complete_manifest(self) -> None:
        """Do not hash past the configured byte budget or claim completeness."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "limit-goal"
        self._goal(plugin, goal_id)
        goal_stage = self.stage / goal_id
        goal_stage.mkdir()
        (goal_stage / "too-large.tmp").write_bytes(b"0123456789")

        with patch("curatormd_v2.project_plugin_staging.MAX_STAGING_HASH_BYTES", 5):
            inventory = plugin.discover_staging_artifacts(goal_id)

        self.assertFalse(inventory.usage.inventory_complete)
        self.assertEqual(inventory.usage.error_code, "hash_byte_limit")
        self.assertEqual(inventory.artifacts, ())
        self.assertIsNone(inventory.manifest_sha256)

    def test_stage_artifact_streams_to_atomic_goal_scoped_file(self) -> None:
        """The producer API writes bounded temporary bytes and returns only a digest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "writer-goal"
        self._goal(plugin, goal_id)
        payload = b"temporary cue payload"

        artifact = plugin.stage_artifact(goal_id, "cue", "event-1", io.BytesIO(payload))

        self.assertEqual(
            Path(artifact.path),
            self.stage / goal_id / "cue" / "event-1.bin",
        )
        self.assertEqual(artifact.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(Path(artifact.path).read_bytes(), payload)
        self.assertEqual(stat.S_IMODE(Path(artifact.path).stat().st_mode), 0o600)
        inventory = plugin.discover_staging_artifacts(goal_id)
        self.assertTrue(inventory.usage.inventory_complete)
        self.assertEqual(inventory.artifacts, (artifact,))

    def test_expired_staging_uses_72_hour_max_age_when_no_record_is_ready(self) -> None:
        """Unrecorded producer files reach the hard 72-hour age ceiling."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            expired = plugin.stage_artifact(
                goal_id, "cue", "expired-cue", io.BytesIO(b"old transient")
            )
            fresh = plugin.stage_artifact(
                goal_id, "import", "fresh-import", io.BytesIO(b"new transient")
            )

        before_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=71, minutes=59)
        )
        self.assertTrue(before_cap.inventory_complete)
        self.assertEqual(before_cap.eligible_artifacts, ())
        self.assertEqual(before_cap.unknown_age_count, 0)

        at_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        self.assertTrue(at_cap.inventory_complete)
        self.assertEqual(
            at_cap.eligible_artifacts,
            tuple(sorted((expired, fresh), key=lambda item: item.path)),
        )
        self.assertEqual(
            at_cap.manifest_sha256,
            hashlib.sha256(
                json.dumps(
                    [
                        (item.path, item.sha256, item.occurrence_id)
                        for item in at_cap.eligible_artifacts
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )

    def test_expiry_proposal_orders_files_fifo_without_deleting(self) -> None:
        """Oldest eligible artifacts appear first; discovery remains read-only."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-fifo-goal"
        self._goal(plugin, goal_id)
        oldest_time = datetime(2026, 10, 1, tzinfo=UTC)
        newer_time = oldest_time + timedelta(hours=1)
        with patch_store_symbol("utc_now", return_value=newer_time.isoformat()):
            newer = plugin.stage_artifact(
                goal_id, "cue", "a-newer", io.BytesIO(b"newer transient")
            )
        with patch_store_symbol("utc_now", return_value=oldest_time.isoformat()):
            oldest = plugin.stage_artifact(
                goal_id, "cue", "z-oldest", io.BytesIO(b"older transient")
            )

        snapshot = plugin.discover_expired_staging_artifacts(
            oldest_time + timedelta(hours=74)
        )

        self.assertTrue(snapshot.inventory_complete)
        self.assertEqual(snapshot.eligible_artifacts, (oldest, newer))
        self.assertTrue(Path(oldest.path).is_file())
        self.assertTrue(Path(newer.path).is_file())

    def test_replaying_exact_staging_occurrence_does_not_reset_retention_age(
        self,
    ) -> None:
        """Re-recording one exact occurrence preserves its first staged time."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-replay-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        replayed_at = staged_at + timedelta(hours=48)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "replayed-cue", io.BytesIO(b"same occurrence")
            )

        with patch_store_symbol("utc_now", return_value=replayed_at.isoformat()):
            recorded_at = self.store.record_staging_artifact_time(
                plugin.config.project_id, artifact
            )

        self.assertEqual(recorded_at, staged_at.isoformat())
        at_expiry = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        self.assertEqual(at_expiry.eligible_artifacts, (artifact,))

    def test_reusing_purged_artifact_id_cannot_restart_retention_age(self) -> None:
        """Require a new producer ID instead of resetting a purged path's age."""

        config = self._register_project("Register the purged artifact replay fixture")
        plugin = ProjectPlugin.bind(
            config, self.store, review_authorizer=TestReviewAuthorizer()
        )
        goal_id = "purged-artifact-replay-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        payload = b"same source bytes"
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "stable-source-id", io.BytesIO(payload)
            )

        expiry_at = staged_at + timedelta(hours=72)
        snapshot = plugin.discover_expired_staging_artifacts(expiry_at)
        manifest_sha256 = snapshot.manifest_sha256
        if manifest_sha256 is None:
            self.fail("complete expiry inventory must have a manifest hash")
        receipt = plugin.approve_expired_staging_inventory(
            snapshot.eligible_artifacts, manifest_sha256, now=expiry_at
        )
        self.assertEqual(receipt.status.value, "complete")
        self.assertFalse(Path(artifact.path).exists())

        with patch_store_symbol("utc_now", return_value=expiry_at.isoformat()):
            with self.assertRaisesRegex(ConflictError, "use a new artifact ID"):
                plugin.stage_artifact(
                    goal_id, "cue", "stable-source-id", io.BytesIO(payload)
                )

        self.assertFalse(Path(artifact.path).exists())
        fresh = plugin.stage_artifact(
            goal_id, "cue", "new-source-id", io.BytesIO(payload)
        )
        self.assertTrue(Path(fresh.path).is_file())
        self.assertNotEqual(fresh.occurrence_id, artifact.occurrence_id)

    def test_expiry_becomes_eligible_after_post_stage_facts_are_recorded(self) -> None:
        """Do not make reviewers wait 72 hours after facts are already recorded."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-immediate-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime.now(UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "raw-chat", "source-chat", io.BytesIO(b"temporary source")
            )

        before_facts = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(minutes=1)
        )
        self.assertEqual(before_facts.eligible_artifacts, ())

        plugin.service.goal_fact(
            goal_id,
            FactKind.RESEARCH,
            "Compact facts were recorded from the temporary source",
        )
        after_facts = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(minutes=1)
        )

        self.assertTrue(after_facts.inventory_complete)
        self.assertEqual(after_facts.eligible_artifacts, (artifact,))
        self.assertEqual(after_facts.pending_sde_artifact_count, 0)

    def test_expiry_retry_preserves_same_content_replacement_after_approval(
        self,
    ) -> None:
        """A persisted expiry receipt cannot unlink a replacement occurrence."""

        config = self._register_project("Register the expiry retry fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "expiry-replacement-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            approved = plugin.stage_artifact(
                goal_id, "cue", "same-content", io.BytesIO(b"temporary source")
            )
        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest = snapshot.manifest_sha256
        if manifest is None:
            self.fail("complete expiry snapshot must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            "consumer-a", "expiry-reviewer", manifest, snapshot.eligible_artifacts
        )

        original_path = Path(approved.path)
        replacement = original_path.with_name("replacement.tmp")
        replacement.write_bytes(b"temporary source")
        original_path.unlink()
        replacement.rename(original_path)

        current_expiry = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        self.assertEqual(current_expiry.eligible_artifacts, ())
        self.assertEqual(current_expiry.unknown_age_count, 1)

        retried = plugin.retry_expiry_purge(receipt.receipt_id)

        self.assertTrue(original_path.exists())
        self.assertEqual(original_path.read_bytes(), b"temporary source")
        self.assertEqual(retried.status.value, "purge_pending")
        self.assertEqual(retried.artifacts[0].device_id, approved.device_id)
        self.assertEqual(retried.artifacts[0].inode_id, approved.inode_id)
        self.assertEqual(retried.approval_stale_artifacts, (retried.artifacts[0],))
        self.assertEqual(self.store.due_expiry_purge_receipts(config.project_id), ())

        self.assertEqual(
            self.store.expiry_purge_targets(receipt.receipt_id, config.project_id),
            (),
        )
        retried_again = plugin.retry_expiry_purge(receipt.receipt_id)

        self.assertEqual(
            retried_again.approval_stale_artifacts, (retried_again.artifacts[0],)
        )
        self.assertTrue(original_path.exists())
        self.assertEqual(original_path.read_bytes(), b"temporary source")

    def test_suspended_project_blocks_direct_expiry_purge_paths(self) -> None:
        """Direct expiry approval and retry cannot unlink after suspension."""

        config = self._register_project("Register the suspended expiry fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "suspended-expiry-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "suspended-expiry", io.BytesIO(b"retained source")
            )
        expired = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest_sha256 = expired.manifest_sha256
        if manifest_sha256 is None:
            self.fail("complete expiry inventory must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            config.project_id,
            "test-admin",
            manifest_sha256,
            expired.eligible_artifacts,
        )
        self.store.set_project_status(
            ProjectStatusChangeRequest(
                project_id=config.project_id,
                status="suspended",
                rationale="Fence expiry cleanup before suspension cutover",
                expected_revision=1,
                transition_id="suspend-expiry-cleanup-1",
            ),
            "test-admin",
        )

        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.approve_expired_staging_inventory(
                expired.eligible_artifacts,
                manifest_sha256,
                now=staged_at + timedelta(hours=72),
            )
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.retry_expiry_purge(receipt.receipt_id)
        with self.assertRaisesRegex(ConflictError, "lifecycle changed"):
            plugin.retry_pending_purges()

        self.assertTrue(Path(artifact.path).is_file())
        self.assertEqual(
            self.store.expiry_purge_receipt(
                receipt.receipt_id, config.project_id
            ).status.value,
            "purge_pending",
        )

    def test_inflight_expiry_unlink_finishes_before_project_suspend_cutover(
        self,
    ) -> None:
        """An admitted unlink holds the project fence until its receipt commits."""

        config = self._register_project("Register the expiry unlink race fixture")
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "inflight-expiry-unlink-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "scratch", "inflight-unlink", io.BytesIO(b"expiry payload")
            )
        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )
        manifest = snapshot.manifest_sha256
        if manifest is None:
            self.fail("complete expiry inventory must have a manifest hash")
        receipt = self.store.create_expiry_purge_receipt(
            config.project_id, "test-admin", manifest, snapshot.eligible_artifacts
        )

        self._assert_expiry_unlink_holds_suspension_fence(
            config, plugin, receipt, Path(artifact.path)
        )

    def test_pending_sde_cannot_extend_the_72_hour_retention_ceiling(self) -> None:
        """Pending review delays prompt expiry but not the absolute age cap."""

        config = self._register_project("Register the pending SDE expiry fixture")
        plugin = ProjectPlugin.bind(
            config,
            self.store,
            review_authorizer=TestReviewAuthorizer(),
        )
        goal_id = "expiry-pending-sde-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "pending-sde-cue", io.BytesIO(b"temporary source")
            )
        fact, _ = plugin.service.goal_fact(
            goal_id, FactKind.RESEARCH, "A compact fact for the pending review"
        )
        self.store.add_sde_candidate(
            SDECandidate(
                goal_id=goal_id,
                materiality=Materiality.IMPLEMENTATION,
                rationale="Review a material outcome before expiry",
                fact_ids=(fact.fact_id,),
                impact="The source may contain a durable implementation decision",
                retrieval_value="A reviewer must decide whether the outcome is useful",
            ),
            project_id="consumer-a",
        )

        before_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=71, minutes=59)
        )
        self.assertEqual(before_cap.eligible_artifacts, ())
        self.assertEqual(before_cap.pending_sde_artifact_count, 1)

        at_cap = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=72)
        )

        self.assertTrue(at_cap.inventory_complete)
        self.assertEqual(at_cap.eligible_artifacts, (artifact,))
        self.assertEqual(at_cap.pending_sde_artifact_count, 1)
        self.assertTrue(Path(artifact.path).is_file())
        manifest_sha256 = at_cap.manifest_sha256
        if manifest_sha256 is None:
            self.fail("complete expiry snapshot must have a manifest hash")
        at_cap_time = staged_at + timedelta(hours=72)
        with patch_store_symbol("utc_now", return_value=at_cap_time.isoformat()):
            receipt = plugin.approve_expired_staging_inventory(
                at_cap.eligible_artifacts,
                manifest_sha256,
                now=at_cap_time,
            )
        self.assertEqual(receipt.status.value, "complete")
        self.assertFalse(Path(artifact.path).exists())

        candidate = self.store.list_sde_candidates(goal_id, "consumer-a")[0]
        self.assertEqual(candidate.status, SDEStatus.PENDING_REVIEW)
        plugin.service.sde_confirm(
            approved_empty_inventory_request(candidate.candidate_id)
        )
        reviewed_candidate = self.store.list_sde_candidates(goal_id, "consumer-a")[0]
        self.assertEqual(reviewed_candidate.status, SDEStatus.APPROVED)
        self.assertFalse(Path(artifact.path).exists())

    def test_expired_staging_fails_closed_for_untracked_files(self) -> None:
        """A direct filesystem writer cannot borrow another file's age proof."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-unknown-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            tracked = plugin.stage_artifact(
                goal_id, "cue", "tracked-cue", io.BytesIO(b"old transient")
            )
        untracked_path = self.stage / goal_id / "scratch" / "direct-writer.bin"
        untracked_path.parent.mkdir(parents=True)
        untracked_path.write_bytes(b"unknown age")

        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=73)
        )

        self.assertFalse(snapshot.inventory_complete)
        self.assertEqual(snapshot.unknown_age_count, 1)
        self.assertIsNone(snapshot.manifest_sha256)
        self.assertEqual(snapshot.eligible_artifacts, ())
        self.assertTrue(Path(tracked.path).is_file())


class ProjectPluginExpiryClockTests(ProjectPluginTestSupport):
    """Keep invalid staging timestamps out of expiry authorization."""

    def test_future_staging_timestamp_keeps_expiry_inventory_unknown(self) -> None:
        """A wall-clock rollback cannot turn a future age into a fresh lease."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-future-age-goal"
        self._goal(plugin, goal_id)
        observed_at = datetime(2026, 10, 27, tzinfo=UTC)
        future_staged_at = observed_at + timedelta(minutes=5)
        with patch_store_symbol("utc_now", return_value=future_staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "future-timestamp", io.BytesIO(b"temporary")
            )

        snapshot = plugin.discover_expired_staging_artifacts(observed_at)

        self.assertFalse(snapshot.inventory_complete)
        self.assertEqual(snapshot.unknown_age_count, 1)
        self.assertIsNone(snapshot.manifest_sha256)
        self.assertEqual(snapshot.eligible_artifacts, ())
        self.assertTrue(Path(artifact.path).is_file())

    def test_malformed_or_timezone_naive_staging_timestamp_is_unknown(self) -> None:
        """Invalid age metadata cannot produce an expiry purge manifest."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-invalid-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "invalid-timestamp", io.BytesIO(b"temporary")
            )

        observed_at = staged_at + timedelta(hours=73)
        invalid_timestamps = ("not-a-timestamp", "2026-10-01T00:00:00")
        for invalid_timestamp in invalid_timestamps:
            with self.subTest(timestamp=invalid_timestamp):
                with patch.object(
                    plugin.service.store,
                    "staging_artifact_times",
                    return_value={artifact.path: invalid_timestamp},
                ), patch.object(
                    plugin.service.store,
                    "staging_artifact_expiry_readiness",
                    return_value={artifact.path: (False, False, 0)},
                ):
                    snapshot = plugin.discover_expired_staging_artifacts(observed_at)

                self.assertFalse(snapshot.inventory_complete)
                self.assertEqual(snapshot.unknown_age_count, 1)
                self.assertIsNone(snapshot.manifest_sha256)
                self.assertEqual(snapshot.eligible_artifacts, ())
                self.assertTrue(Path(artifact.path).is_file())

    def test_paired_restore_fails_closed_for_unverified_file_identity(self) -> None:
        """A copied restore tree cannot borrow age without its file identity."""

        config = ProjectConfig.load(self.root)
        plugin = ProjectPlugin.bind(config, self.store)
        goal_id = "expiry-restore-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "restore-age", io.BytesIO(b"temporary source")
            )

        backup_path = Path(self.temporary) / "staging-age-backup.sqlite3"
        restored_path = Path(self.temporary) / "staging-age-restored.sqlite3"
        staging_backup = Path(self.temporary) / "staging-tree-backup"
        backup_database(self.store.database, backup_path)
        shutil.copytree(self.stage, staging_backup)
        shutil.rmtree(self.stage)
        restore_database(backup_path, restored_path)
        shutil.copytree(staging_backup, self.stage)
        restored_store = CuratorStore(restored_path)
        self.addCleanup(restored_store.close)
        restored_plugin = ProjectPlugin.bind(config, restored_store)

        for observed_at in (
            staged_at + timedelta(hours=71, minutes=59),
            staged_at + timedelta(hours=72),
        ):
            with self.subTest(observed_at=observed_at):
                snapshot = restored_plugin.discover_expired_staging_artifacts(
                    observed_at
                )
                self.assertFalse(snapshot.inventory_complete)
                self.assertEqual(snapshot.unknown_age_count, 1)
                self.assertIsNone(snapshot.manifest_sha256)
                self.assertEqual(snapshot.eligible_artifacts, ())
                self.assertTrue(Path(artifact.path).is_file())

    def test_renamed_or_copied_artifact_does_not_inherit_expiry_age(self) -> None:
        """A new path cannot borrow age metadata from a same-content source."""

        plugin = ProjectPlugin.bind(ProjectConfig.load(self.root), self.store)
        goal_id = "expiry-copy-age-goal"
        self._goal(plugin, goal_id)
        staged_at = datetime(2026, 10, 1, tzinfo=UTC)
        with patch_store_symbol("utc_now", return_value=staged_at.isoformat()):
            artifact = plugin.stage_artifact(
                goal_id, "cue", "original-source", io.BytesIO(b"same bytes")
            )

        renamed_path = Path(artifact.path).with_name("renamed.tmp")
        copied_path = Path(artifact.path).with_name("copied.tmp")
        Path(artifact.path).rename(renamed_path)
        shutil.copyfile(renamed_path, copied_path)
        snapshot = plugin.discover_expired_staging_artifacts(
            staged_at + timedelta(hours=73)
        )

        self.assertFalse(snapshot.inventory_complete)
        self.assertEqual(snapshot.unknown_age_count, 2)
        self.assertIsNone(snapshot.manifest_sha256)
        self.assertEqual(snapshot.eligible_artifacts, ())
        self.assertTrue(renamed_path.is_file())
        self.assertTrue(copied_path.is_file())
