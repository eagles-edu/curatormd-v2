"""Persist and retry exact artifact cleanup decisions."""

from __future__ import annotations

__all__ = (
    "_PurgeMixin",
)

from datetime import (
    UTC,
    datetime,
)
from .models import (
    ArtifactRef,
    ArtifactStatus,
    AuditReceipt,
    CleanupAuthorizationReceipt,
    PurgeFailureCode,
    PurgeOutcome,
)
from .purge import PurgeError
from .store_requests import PurgeTargetResult
from .validation import is_exact_int

from .service_types import (
    PurgeTargetStatus,
    _purge_recovery_action,
    _timestamp_age_seconds,
    _timestamp_delay_seconds,
)
from .service_review import _ReviewMixin


class _PurgeMixin(_ReviewMixin):
    """Persist and retry exact artifact cleanup decisions."""

    def authorize_artifact_cleanup(
        self,
        receipt_id: str,
        manifest_sha256: str,
        dependency_map_sha256: str,
        *,
        authenticated_subject: str | None = None,
    ) -> tuple[CleanupAuthorizationReceipt, AuditReceipt]:
        """Record review-authorized cleanup; canonical projection still gates deletion."""

        expected_effect_revision = self._capture_effect_revision()
        reviewer_id = self.review_authorizer.authorize_cleanup(
            self.project_id, receipt_id, manifest_sha256, authenticated_subject
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        with self._effect_fence(expected_effect_revision):
            authorization = self.store.create_cleanup_authorization(
                receipt_id,
                self.project_id,
                reviewer_id,
                manifest_sha256,
                dependency_map_sha256,
            )
        return authorization, self.store.get_receipt(receipt_id, self.project_id)

    def mark_cleanup_authorization_canonical_persisted(
        self, receipt_id: str, target: str, sha256: str
    ) -> AuditReceipt:
        """Record the projection containing cleanup approval before deletion."""

        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            self.store.mark_cleanup_authorization_canonical_persisted(
                receipt_id, self.project_id, target, sha256
            )
            return self._process_purge(receipt_id)

    def artifact_inventory_complete(
        self,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Commit the complete staged-file manifest without authorizing deletion."""

        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            receipt = self.store.complete_artifact_inventory(
                receipt_id,
                artifacts,
                self.project_id,
                hold_created_by=authenticated_subject,
            )
            if not receipt.artifact_inventory_complete or not receipt.canonical_persisted:
                return receipt
            return self._process_purge(receipt_id)

    def release_artifact_hold(
        self,
        receipt_id: str,
        path: str,
        rationale: str,
        *,
        authenticated_subject: str | None = None,
    ) -> AuditReceipt:
        """Authorize a hold release; retry only if cleanup was separately approved."""

        expected_effect_revision = self._capture_effect_revision()
        reviewer_id = self.review_authorizer.authorize_hold_release(
            self.project_id,
            receipt_id,
            path,
            rationale,
            authenticated_subject,
        )
        if authenticated_subject is not None and reviewer_id != authenticated_subject:
            raise PermissionError(
                "review authorizer returned a different authenticated subject"
            )
        with self._effect_fence(expected_effect_revision):
            receipt = self.store.release_artifact_hold(
                receipt_id,
                path,
                self.project_id,
                reviewer_id,
                rationale,
            )
            if receipt.artifact_inventory_complete and receipt.canonical_persisted:
                return self._process_purge(receipt_id)
            return receipt

    def mark_canonical_persisted(
        self, receipt_id: str, target: str, sha256: str
    ) -> AuditReceipt:
        """Record the configured Markdown proof without granting cleanup authority."""

        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            receipt = self.store.mark_receipt_canonical_persisted(
                receipt_id, target, sha256, self.project_id
            )
            if receipt.artifact_inventory_complete:
                return self._process_purge(receipt_id)
            return receipt

    def _process_purge(
        self, receipt_id: str, *, due_only: bool = False
    ) -> AuditReceipt:
        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            receipt = self.store.get_receipt(receipt_id, self.project_id)
            if not receipt.artifact_inventory_complete or not receipt.canonical_persisted:
                return receipt
            authorization = self.store.cleanup_authorization(receipt_id, self.project_id)
            if authorization is None or not authorization.canonical_persisted:
                return receipt
            targets = self.store.get_purge_targets(
                receipt_id,
                pending_only=True,
                project_id=self.project_id,
                due_only=due_only,
            )
            for artifact, _, _, _ in targets:
                self.store.begin_purge_attempt(
                    receipt_id, artifact.path, self.project_id
                )
                try:
                    # The store's transactional selector permits only unheld or
                    # explicitly released targets. Keep the immutable hold class
                    # on the receipt, but pass a purgeable reference to the adapter.
                    deleted = self.purger.purge(
                        ArtifactRef(
                            artifact.path,
                            artifact.sha256,
                            device_id=artifact.device_id,
                            inode_id=artifact.inode_id,
                            occurrence_id=artifact.occurrence_id,
                        )
                    )
                except (OSError, PurgeError, ValueError) as exc:
                    if isinstance(exc, PurgeError):
                        error_code = exc.code.value
                    elif isinstance(exc, OSError):
                        error_code = PurgeFailureCode.FILESYSTEM_ERROR.value
                    else:
                        error_code = PurgeFailureCode.INVALID_ARTIFACT.value
                    self.store.record_purge_result(
                        receipt_id,
                        artifact.path,
                        PurgeTargetResult(
                            status=ArtifactStatus.FAILED,
                            error=error_code,
                            outcome=(
                                PurgeOutcome.CHANGED
                                if error_code in {
                                    PurgeFailureCode.ARTIFACT_CHANGED.value,
                                    PurgeFailureCode.HASH_MISMATCH.value,
                                    PurgeFailureCode.PATH_CHANGED.value,
                                }
                                else PurgeOutcome.FAILED
                            ),
                        ),
                        self.project_id,
                    )
                else:
                    self.store.record_purge_result(
                        receipt_id,
                        artifact.path,
                        PurgeTargetResult(
                            status=ArtifactStatus.PURGED,
                            error=None,
                            outcome=(
                                PurgeOutcome.DELETED
                                if deleted
                                else PurgeOutcome.ALREADY_ABSENT
                            ),
                        ),
                        self.project_id,
                    )
            return self.store.get_receipt(receipt_id, self.project_id)

    def artifact_purge_status(
        self, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Report receipt and per-artifact purge state without masking failures."""

        receipt = self.store.get_receipt(receipt_id, self.project_id)
        now = datetime.now(UTC)
        targets = tuple(
            PurgeTargetStatus(
                artifact=item.artifact,
                status=item.status,
                attempts=item.attempts,
                error=item.error,
                created_at=item.created_at,
                last_attempt_at=item.last_attempt_at,
                next_attempt_at=item.next_attempt_at,
                next_attempt_in_seconds=_timestamp_delay_seconds(
                    item.next_attempt_at, now
                ),
                age_seconds=_timestamp_age_seconds(item.created_at, now),
                last_attempt_age_seconds=(
                    _timestamp_age_seconds(item.last_attempt_at, now)
                    if item.last_attempt_at is not None
                    else None
                ),
                safe_recovery_action=_purge_recovery_action(
                    receipt, item.status, item.approval_stale
                ),
                hold_created_at=item.hold_created_at,
                hold_created_by=item.hold_created_by,
                hold_released_at=item.hold_released_at,
                hold_released_by=item.hold_released_by,
                hold_release_rationale=item.hold_release_rationale,
                approval_stale=item.approval_stale,
                outcome=item.outcome,
            )
            for item in self.store.get_purge_target_records(
                receipt_id, project_id=self.project_id
            )
        )
        return receipt, targets

    def retry_pending_purges(self) -> tuple[AuditReceipt, ...]:
        """Explicitly retry all eligible manifests now, overriding backoff."""

        refreshed: list[AuditReceipt] = []
        for receipt in self.store.pending_receipts(self.project_id):
            if receipt.artifact_inventory_complete and receipt.canonical_persisted:
                refreshed.append(self._process_purge(receipt.receipt_id))
            else:
                refreshed.append(receipt)
        return tuple(refreshed)

    def retry_due_purges(self, limit: int = 100) -> tuple[AuditReceipt, ...]:
        """Process a bounded batch of reviewed purge targets whose backoff elapsed.

        This is an internal scheduler-facing operation. Human-authorized
        ``retry_pending_purges`` remains an immediate override.
        """

        if not is_exact_int(limit) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        refreshed: list[AuditReceipt] = []
        for receipt in self.store.due_pending_purge_receipts(
            self.project_id, limit
        ):
            refreshed.append(self._process_purge(receipt.receipt_id, due_only=True))
        return tuple(refreshed)
