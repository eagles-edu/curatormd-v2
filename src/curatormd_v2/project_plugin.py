"""Thin repository-bound plugin adapter over the Curator V2 global service."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import os
from threading import RLock, local
from typing import Generator

from .evidence import EvidenceVerifier
from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventInboxStatus,
    EventQueueStatus,
    GoalCriteriaAmended,
    GoalStarted,
)
from .models import (
    AuditReceipt,
    ChecklistGoalStartRequest,
    GoalCard,
    GoalSubtaskStartRequest,
    GoalStatus,
    EventReceiptCompactionProposal,
    ProjectActivitySnapshot,
    SuccessCriterion,
)
from .project_config import ProjectConfig, ProjectConfigError
from .purge import ArtifactPurger
from .reviews import ReviewAuthorizer
from .service import CuratorService
from .store import ConflictError, CuratorStore, NotFoundError
from .store_requests import ProjectDrainEffectContext
from .staging_models import MAX_STAGING_SCAN_ENTRIES
from .project_plugin_review import ProjectReviewMixin
from .project_plugin_views import ProjectGoalReadMixin
from .project_plugin_staging import (
    MAX_GOAL_STAGING_BYTES,
    MAX_GOAL_STAGING_FILES,
    MAX_STAGED_ARTIFACT_BYTES,
    MAX_STAGING_HASH_BYTES,
)

__all__ = [
    "MAX_GOAL_STAGING_BYTES",
    "MAX_GOAL_STAGING_FILES",
    "MAX_STAGED_ARTIFACT_BYTES",
    "MAX_STAGING_HASH_BYTES",
    "MAX_STAGING_SCAN_ENTRIES",
    "ProjectPlugin",
]

_DRAIN_EFFECT_CONTEXT: ContextVar[
    tuple[str, str | None, EventEnvelope] | None
] = ContextVar("curator_v2_drain_effect_context", default=None)



















class ProjectPlugin(ProjectReviewMixin, ProjectGoalReadMixin):
    """Expose only configured project paths and project-scoped goal operations."""

    def __init__(self, config: ProjectConfig, service: CuratorService) -> None:
        if service.project_id != config.project_id:
            raise ProjectConfigError("service project does not match repository config")
        self.config = config
        self.service = service
        try:
            binding = service.store.get_consumer_binding(config.project_id)
        except NotFoundError:
            self._consumer_binding_revision: int | None = None
        else:
            self._consumer_binding_revision = binding.revision
        self._staging_thread_lock = RLock()
        self._staging_lock_state = local()

    @contextmanager
    def _locked_staging_root(self) -> Generator[int, None, None]:
        """Serialize supported plugin operations on this staging directory."""

        with self._staging_thread_lock:
            existing_fd = getattr(self._staging_lock_state, "root_fd", None)
            if existing_fd is not None:
                self._staging_lock_state.depth += 1
                try:
                    yield existing_fd
                finally:
                    self._staging_lock_state.depth -= 1
                return

            no_follow = getattr(os, "O_NOFOLLOW", None)
            directory_flag = getattr(os, "O_DIRECTORY", None)
            if no_follow is None or directory_flag is None:
                raise ProjectConfigError("platform lacks safe staging lock primitives")
            root = self.config.validated_staging_root()
            root_open_failed = False
            root_fd = -1
            try:
                root_fd = os.open(root, os.O_RDONLY | directory_flag | no_follow)
            except OSError:
                root_open_failed = True
            if root_open_failed:
                raise ProjectConfigError("staging root cannot be opened safely")
            try:
                fcntl.flock(root_fd, fcntl.LOCK_EX)
                self._staging_lock_state.root_fd = root_fd
                self._staging_lock_state.depth = 1
                try:
                    yield root_fd
                finally:
                    del self._staging_lock_state.root_fd
                    del self._staging_lock_state.depth
            finally:
                try:
                    fcntl.flock(root_fd, fcntl.LOCK_UN)
                finally:
                    os.close(root_fd)

    @contextmanager
    def project_effect_lock(self) -> Generator[None, None, None]:
        """Acquire the repository staging lock before an API revision fence."""

        with self._locked_staging_root():
            yield

    @contextmanager
    def _active_project_revision_fence(self) -> Generator[None, None, None]:
        """Fence an effect to this config's currently active revision."""

        revision = self._capture_active_project_revision()
        with self._project_revision_fence(revision):
            yield

    def _capture_active_project_revision(self) -> int:
        """Capture the active revision before an external verification phase."""

        registration = self.service.store.get_project_registration(
            self.config.project_id
        )
        if (
            registration.repository_fingerprint,
            registration.config_sha256,
            registration.backend_api_version,
        ) != (
            self.config.repository_fingerprint,
            self.config.config_sha256,
            self.config.backend_api_version,
        ):
            raise ConflictError("maintenance project binding changed")
        if self._consumer_binding_revision is None:
            raise ConflictError("consumer binding was not active when plugin bound")
        if registration.status != "active":
            raise ConflictError("project lifecycle changed before the effect")
        return registration.revision

    def refresh_consumer_binding_revision(self, expected_revision: int) -> None:
        """Refresh a re-enrolled binding after the API authorizes its writer."""

        binding = self.service.store.get_consumer_binding(self.config.project_id)
        if binding.status != "active" or binding.revision != expected_revision:
            raise ConflictError("consumer binding changed before the effect")
        self._consumer_binding_revision = binding.revision

    @contextmanager
    def _project_revision_fence(
        self,
        expected_revision: int,
        *,
        drain_event: EventEnvelope | None = None,
        caller_subject: str | None = None,
        caller_profile: str | None = None,
        expected_binding_revision: int | None = None,
    ) -> Generator[None, None, None]:
        """Fence an effect to a previously captured project revision."""

        inherited_drain = _DRAIN_EFFECT_CONTEXT.get()
        if drain_event is None and inherited_drain is not None:
            caller_subject, caller_profile, drain_event = inherited_drain

        with self.service.store.project_revision_fence(
            self.config.project_id,
            expected_revision,
            drain=(
                ProjectDrainEffectContext(
                    drain_event, caller_subject, caller_profile
                )
                if drain_event is not None and caller_subject is not None
                else None
            ),
            expected_binding_revision=(
                self._consumer_binding_revision
                if expected_binding_revision is None
                else expected_binding_revision
            ),
        ):
            yield

    @classmethod
    def bind(
        cls,
        config: ProjectConfig,
        store: CuratorStore,
        evidence_verifier: EvidenceVerifier | None = None,
        review_authorizer: ReviewAuthorizer | None = None,
    ) -> ProjectPlugin:
        """Bind config to the global store without mixing project state."""

        staging_root = config.validated_staging_root()
        service = CuratorService(
            store,
            ArtifactPurger(staging_root),
            evidence_verifier,
            review_authorizer,
            project_id=config.project_id,
        )
        plugin = cls(config, service)
        service.bind_project_effect_boundary(
            plugin._capture_active_project_revision,
            plugin._project_revision_fence,
        )
        return plugin








    def process_event(
        self,
        event: EventEnvelope,
        *,
        drain_caller: tuple[str, str | None] | None = None,
        expected_binding_revision: int | None = None,
    ) -> EventInboxReceipt:
        """Apply an event only inside this plugin's project binding.

        Checklist snapshots are revalidated at the repository boundary so a
        generic event/MCP caller cannot invent a checklist line or revision.
        Successfully processed retries remain idempotent after the source file
        later changes; the store still rejects changed payload reuse.
        """

        if event.project_id != self.config.project_id:
            raise PermissionError("event project does not match this plugin")
        with self._locked_staging_root():
            expected_revision = self._capture_active_project_revision()
            token = (
                _DRAIN_EFFECT_CONTEXT.set(
                    (drain_caller[0], drain_caller[1], event)
                )
                if drain_caller is not None
                else None
            )
            try:
                return self._process_event_locked(
                    event,
                    expected_revision,
                    drain_caller,
                    expected_binding_revision,
                )
            finally:
                if token is not None:
                    _DRAIN_EFFECT_CONTEXT.reset(token)

    def _process_event_locked(
        self,
        event: EventEnvelope,
        expected_revision: int,
        drain_caller: tuple[str, str | None] | None = None,
        expected_binding_revision: int | None = None,
    ) -> EventInboxReceipt:
        """Validate repository-bound fields, then fence durable event effects."""

        payload = event.payload
        if isinstance(payload, GoalStarted) and payload.checklist_id is not None:
            try:
                prior_receipt = self.service.store.event_receipt(
                    self.config.project_id, event.event_id
                )
            except NotFoundError:
                prior_receipt = None
            if (
                prior_receipt is None
                or prior_receipt.status is not EventInboxStatus.PROCESSED
            ):
                version, source_text = self.config.checklist_snapshot(
                    payload.checklist_id, payload.checklist_source_text or ""
                )
                if (
                    version != payload.checklist_version
                    or source_text != payload.checklist_source_text
                ):
                    raise ProjectConfigError(
                        "checklist snapshot does not match the configured source revision"
                    )

        def effect_fence():
            return self._project_revision_fence(
                expected_revision,
                drain_event=event if drain_caller is not None else None,
                caller_subject=drain_caller[0] if drain_caller is not None else None,
                caller_profile=drain_caller[1] if drain_caller is not None else None,
                expected_binding_revision=expected_binding_revision,
            )

        return self.service.process_event(
            event,
            effect_fence=effect_fence,
            override_project_fence=drain_caller is not None,
        )

    def event_queue_status(self) -> EventQueueStatus:
        """Return event backlog metrics for this project's authorized binding."""

        return self.service.store.event_queue_status(self.config.project_id)

    def propose_event_receipt_compaction(
        self, offset: int = 0, limit: int = 50
    ) -> EventReceiptCompactionProposal:
        """List a bounded review inventory without changing retained receipts."""

        return self.service.store.propose_event_receipt_compaction(
            self.config.project_id, offset, limit
        )

    def activity_status(self) -> ProjectActivitySnapshot:
        """Return retained event, goal, fact, and SDE totals for this project."""

        return self.service.store.project_activity_status(self.config.project_id)

    def retry_quarantined_event(
        self, event_id: str, actor_id: str
    ) -> EventInboxReceipt:
        """Audit and retry one quarantined event within this project only."""

        with self._active_project_revision_fence():
            return self.service.store.retry_quarantined_event(
                self.config.project_id, event_id, actor_id
            )

    def goal_start_from_request(
        self,
        problem: str,
        success_criteria: tuple[SuccessCriterion, ...],
        *,
        owner: str | None = None,
        next_action: str | None = None,
        source_event_id: str | None = None,
    ) -> GoalCard:
        """Start a user-request goal without deriving or rewriting criteria.

        Callers must pass the agreed problem and observable success criteria.
        The model validates and stores those values unchanged; an empty criteria
        set is rejected rather than synthesized from the problem statement.
        """

        with self._active_project_revision_fence():
            return self.service.goal_start(
                problem,
                success_criteria,
                owner=owner,
                initial_status=GoalStatus.PLANNED,
                next_action=next_action,
                source_event_id=source_event_id,
            )

    def goal_start_subtask(
        self,
        request: GoalSubtaskStartRequest,
    ) -> GoalCard:
        """Start an explicitly accepted child task with its own criteria.

        This adapter does not turn a proposal into accepted work on its own:
        invocation is the caller's explicit acceptance, and the parent remains
        the provenance link. The service enforces same-project parent and
        dependency rules and rejects missing criteria.
        """

        with self._active_project_revision_fence():
            return self.service.goal_start(
                request.problem,
                request.success_criteria,
                owner=request.owner,
                parent_goal_id=request.parent_goal_id,
                depends_on_goal_ids=request.depends_on_goal_ids,
                initial_status=GoalStatus.PLANNED,
                next_action=request.next_action,
                source_event_id=request.source_event_id,
            )

    def goal_start_from_checklist(
        self,
        request: ChecklistGoalStartRequest,
    ) -> GoalCard:
        """Start a goal with an exact checklist line and source-file revision."""

        with self._active_project_revision_fence():
            source_version, source_text = self.config.checklist_snapshot(
                request.checklist_id, request.exact_item_text
            )
            return self.service.goal_start(
                request.problem,
                request.success_criteria,
                owner=request.options.owner,
                checklist_id=request.checklist_id,
                checklist_version=source_version,
                checklist_source_text=source_text,
                parent_goal_id=request.options.parent_goal_id,
                depends_on_goal_ids=request.options.depends_on_goal_ids,
                initial_status=request.options.initial_status,
                next_action=request.options.next_action,
                source_event_id=request.options.source_event_id,
            )


    def goal_activate(
        self, goal_id: str, reason: str, expected_lifecycle_revision: int
    ) -> GoalCard:
        """Activate one planned goal under this plugin's project binding."""

        with self._active_project_revision_fence():
            return self.service.goal_activate(
                goal_id, reason, expected_lifecycle_revision
            )


































    def goal_reopen(self, goal_id: str, reason: str, next_action: str) -> GoalCard:
        """Reopen one completed goal within this project's scope."""

        with self._active_project_revision_fence():
            return self.service.goal_reopen(goal_id, reason, next_action)

    def goal_amend_criteria(
        self,
        request: GoalCriteriaAmended,
    ) -> GoalCard:
        """Amend criteria through this repository's project-bound service."""

        with self._active_project_revision_fence():
            return self.service.goal_amend_criteria(request)













    def retry_due_purges(self, limit: int = 100) -> tuple[AuditReceipt, ...]:
        """Run one bounded scheduler pass for due, already-authorized purges."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.retry_due_purges(limit)

    def retry_pending_purges(self) -> tuple[AuditReceipt, ...]:
        """Retry only reviewed, persisted, project-scoped pending manifests."""

        with self._locked_staging_root():
            with self._active_project_revision_fence():
                return self.service.retry_pending_purges()
