"""Fail-closed, transport-neutral API boundary for trusted host adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from functools import wraps
import re
import sqlite3
from threading import Lock
import time
from typing import Callable, Concatenate, Iterable, Mapping, ParamSpec, Protocol, TypeVar

from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventQueueStatus,
    MAX_EVENT_BYTES,
)
from .errors import RateLimitExceeded
from . import health_evaluation as _health_evaluation
from .health_evaluation import (
    ProjectDependencyReadiness,
    evaluate_dependencies,
    evaluate_local_health,
)
from .models import (
    ArtifactRef,
    AuditReceipt,
    CleanupAuthorizationReceipt,
    FactArchiveReceipt,
    FactCompactionProposal,
    GoalListPage,
    GoalSnapshot,
    GoalBulletProjection,
    GoalStatus,
    Materiality,
    ProjectActivitySnapshot,
    ProjectStorageUsage,
    ProjectHealthSnapshot,
    OperationalHealth,
    utc_now,
    StagingArtifactInventory,
    StagingExpirySnapshot,
    ExpiryPurgeReceipt,
    ReviewDecision,
    SDECandidate,
    SDECorrection,
    SDEQualityFeedback,
    SDEQualityFeedbackLabel,
    SDEQualityFeedbackSummary,
    SDEReviewDetail,
    SDEReviewPacket,
    SuccessCriterion,
)
from .markdown_persistence import (
    MarkdownProjectReconciliation,
    MarkdownProjectionResult,
    MarkdownReconciliationResult,
)
from .observability import render_project_metrics
from .project_plugin import ProjectPlugin
from .reporting import GoalReportPage
from .service import PurgeTargetStatus
from .store import NotFoundError
from .store_requests import ProjectDrainEffectContext


_SUBJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_PROJECT_ID_RE = _SUBJECT_ID_RE
MAX_TRACKED_CALLERS = 10_000
REQUIRED_HEALTH_DEPENDENCIES = _health_evaluation.REQUIRED_HEALTH_DEPENDENCIES
MAX_DEPENDENCY_PROBE_AGE_SECONDS = (
    _health_evaluation.MAX_DEPENDENCY_PROBE_AGE_SECONDS
)


class ProjectAction(StrEnum):
    """Authorization scopes required by the transport-neutral operations."""

    READ = "read"
    WRITE = "write"
    REVIEW = "review"
    PURGE_RETRY = "purge_retry"
    RETENTION_HOLD_RELEASE = "retention_hold_release"
    EVENT_RETRY = "event_retry"


@dataclass(frozen=True, slots=True)
class AuthenticatedCaller:
    """Opaque identity asserted by a trusted host authentication adapter.

    Constructing this value is not authentication. Network/MCP transports must
    obtain it from their verified session context and must never deserialize it
    directly from caller-controlled request data.
    """

    subject_id: str
    profile_id: str | None = None

    def __post_init__(self) -> None:
        if not _SUBJECT_ID_RE.fullmatch(self.subject_id):
            raise ValueError("subject_id must be a bounded opaque identifier")
        if self.profile_id is not None and not re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", self.profile_id
        ):
            raise ValueError("profile_id must be a bounded opaque identifier")


class ProjectAuthorizer(Protocol):
    """Host-owned authorization for an identity, project, and operation."""

    # pylint: disable=too-few-public-methods  # Protocol intentionally has one authorization operation.

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Return true only when the verified caller has this project scope."""
        ...


class RejectAllProjectAccess:
    """Safe default until Hermes supplies an authorization adapter."""

    # pylint: disable=too-few-public-methods  # Fail-closed policy implements the one-method protocol.

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Deny every request until a host-owned authorizer is configured."""

        del caller, project_id, action
        return False


class ProjectGrantAuthorizer:
    """Authorize exact verified-subject/project/action grants in this process.

    This is a reference policy adapter, not an identity provider or durable
    project registry. A trusted host must supply verified subjects and
    operator-managed grants; unknown triples always deny.
    """

    # pylint: disable=too-few-public-methods  # This exact-grant policy implements one authorization operation.

    def __init__(
        self,
        grants: Iterable[tuple[object, object, object]],
    ) -> None:
        checked: set[tuple[str, str, ProjectAction]] = set()
        for grant in grants:
            subject_id, project_id, action = grant
            if not isinstance(subject_id, str) or not _SUBJECT_ID_RE.fullmatch(
                subject_id
            ):
                raise ValueError("project grant subject must be a bounded opaque ID")
            if not isinstance(project_id, str) or not _PROJECT_ID_RE.fullmatch(
                project_id
            ):
                raise ValueError("project grant project must be a bounded opaque ID")
            if not isinstance(action, ProjectAction):
                raise ValueError("project grant action must be a known ProjectAction")
            checked.add((subject_id, project_id, action))
        self._grants = frozenset(checked)

    def authorize(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> bool:
        """Return true only for an exact subject, project, and action grant."""

        return (caller.subject_id, project_id, action) in self._grants


class RequestLimiter(Protocol):
    """Bound request rate by verified subject and project."""

    # pylint: disable=too-few-public-methods  # Protocol intentionally has one rate-limit operation.

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume one request token, if available."""
        ...


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float
    touched_at: float


class InMemoryTokenBucket:
    """Small per-process limiter for local adapters and tests.

    Production deployments with multiple workers must inject a shared limiter;
    this class does not claim cross-process enforcement.
    """

    # pylint: disable=too-few-public-methods  # The limiter contract is one token-consumption operation.

    def __init__(
        self,
        capacity: int = 120,
        refill_period_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity < 1 or refill_period_seconds <= 0:
            raise ValueError("rate limit capacity and refill period must be positive")
        self.capacity = capacity
        self.refill_rate = capacity / refill_period_seconds
        self.clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = Lock()

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume one token for the verified subject and project pair."""

        now = self.clock()
        key = (subject_id, project_id)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= MAX_TRACKED_CALLERS:
                    self._prune_idle(now)
                if len(self._buckets) >= MAX_TRACKED_CALLERS:
                    return False
                self._buckets[key] = _Bucket(self.capacity - 1, now, now)
                self._prune_idle(now)
                return True
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_rate)
            bucket.updated_at = now
            bucket.touched_at = now
            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            self._prune_idle(now)
            return True

    def _prune_idle(self, now: float) -> None:
        if len(self._buckets) <= MAX_TRACKED_CALLERS:
            return
        expiry = now - max(60.0, 2.0 / self.refill_rate)
        self._buckets = {
            bucket_key: entry
            for bucket_key, entry in self._buckets.items()
            if entry.touched_at >= expiry
        }


_P = ParamSpec("_P")
_R = TypeVar("_R")


class AuthenticatedCuratorAPI:
    """Expose project-scoped operations after host authentication/authorization.

    This facade is transport-neutral. A future MCP/HTTP layer should map each
    method to a named tool/route and supply only identity obtained from its
    trusted authenticated session. Direct access to a ``ProjectPlugin`` or
    ``CuratorService`` bypasses this boundary and must remain internal.
    """

    def __init__(
        self,
        plugins: Mapping[str, ProjectPlugin],
        authorizer: ProjectAuthorizer | None = None,
        limiter: RequestLimiter | None = None,
        dependency_readiness: ProjectDependencyReadiness | None = None,
    ) -> None:
        self._plugins = dict(plugins)
        for project_id, plugin in self._plugins.items():
            if not _PROJECT_ID_RE.fullmatch(project_id):
                raise ValueError("registered project ID must be bounded and opaque")
            if plugin.config.project_id != project_id:
                raise ValueError("plugin registry key must match configured project ID")
        self.authorizer = authorizer or RejectAllProjectAccess()
        self.limiter = limiter or InMemoryTokenBucket()
        self.dependency_readiness = dependency_readiness

    @staticmethod
    def _project_effect_fenced(
        action: ProjectAction,
    ) -> Callable[
        [
            Callable[
                Concatenate[AuthenticatedCuratorAPI, AuthenticatedCaller, str, _P],
                _R,
            ]
        ],
        Callable[
            Concatenate[AuthenticatedCuratorAPI, AuthenticatedCaller, str, _P], _R
        ],
    ]:
        """Fence one API effect against project suspension/revision cutover."""

        def decorate(
            method: Callable[
                Concatenate[AuthenticatedCuratorAPI, AuthenticatedCaller, str, _P], _R
            ],
        ) -> Callable[
            Concatenate[AuthenticatedCuratorAPI, AuthenticatedCaller, str, _P], _R
        ]:
            @wraps(method)
            def fenced(
                self: AuthenticatedCuratorAPI,
                caller: AuthenticatedCaller,
                project_id: str,
                *args: _P.args,
                **kwargs: _P.kwargs,
            ) -> _R:
                plugin = self._plugins.get(project_id)  # pylint: disable=protected-access  # Same-class decorator closure.
                if (
                    plugin is None
                    or not self.authorizer.authorize(caller, project_id, action)
                ):
                    return method(self, caller, project_id, *args, **kwargs)
                store = plugin.service.store
                try:
                    registration = store.get_project_registration(project_id)
                except NotFoundError:
                    registration = None
                if registration is None:
                    return method(self, caller, project_id, *args, **kwargs)
                with plugin.project_effect_lock():
                    with store.project_revision_fence(
                        project_id, registration.revision
                    ):
                        return method(self, caller, project_id, *args, **kwargs)

            return fenced

        return decorate

    def process_event_json(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        serialized: str,
        *,
        replay_only: bool = False,
    ) -> EventInboxReceipt:
        """Validate bounded event JSON, authorize scope, then process atomically."""

        invalid_utf8 = False
        try:
            encoded_size = len(serialized.encode("utf-8"))
        except UnicodeEncodeError:
            # UnicodeEncodeError retains the complete request in its ``object`` field.
            invalid_utf8 = True
            encoded_size = 0
        if invalid_utf8:
            raise ValueError("event must be valid UTF-8")
        if encoded_size > MAX_EVENT_BYTES:
            raise ValueError(f"event exceeds {MAX_EVENT_BYTES} byte limit")
        event = EventEnvelope.from_json(serialized)
        if event.project_id != project_id:
            raise PermissionError("event project does not match authorized project")
        plugin = self._plugins.get(project_id)
        if plugin is None:
            raise PermissionError("project is not authorized")
        registration = plugin.service.store.get_project_registration(project_id)
        binding = plugin.service.store.get_consumer_binding(project_id)
        if registration.status == "suspended":
            replay_receipt = (
                plugin.service.store.reconcile_suspended_processed_event(
                    event,
                    caller.subject_id,
                    plugin.config.repository_fingerprint,
                    plugin.config.config_sha256,
                    plugin.config.backend_api_version,
                )
            )
            if replay_receipt is not None:
                if not self.limiter.allow(caller.subject_id, project_id):
                    raise RateLimitExceeded("project request budget exceeded")
                return replay_receipt
        if (
            registration.status == "active"
            and binding.status in {"deregistered", "active"}
            and self.authorizer.authorize(caller, project_id, ProjectAction.WRITE)
        ):
            replay_receipt = (
                plugin.service.store.reconcile_deregistered_processed_event(
                    event
                )
            )
            if replay_receipt is not None:
                if not self.limiter.allow(caller.subject_id, project_id):
                    raise RateLimitExceeded("project request budget exceeded")
                return replay_receipt
        if replay_only:
            raise PermissionError("only an exact processed receipt may be reconciled")
        normally_authorized = self.authorizer.authorize(
            caller, project_id, ProjectAction.WRITE
        )
        if normally_authorized:
            if not self.limiter.allow(caller.subject_id, project_id):
                raise RateLimitExceeded("project request budget exceeded")
        else:
            if not self.limiter.allow(caller.subject_id, project_id):
                raise RateLimitExceeded("project request budget exceeded")
            if not plugin.service.store.consumer_drain_allows(
                caller.subject_id, caller.profile_id, event
            ):
                raise PermissionError("project is not authorized")
        with plugin.project_effect_lock():
            if normally_authorized and binding.status == "active":
                plugin.refresh_consumer_binding_revision(binding.revision)
            with plugin.service.store.project_revision_fence(
                project_id,
                registration.revision,
                drain=(
                    ProjectDrainEffectContext(
                        event, caller.subject_id, caller.profile_id
                    )
                    if not normally_authorized
                    else None
                ),
            ):
                return plugin.process_event(
                    event,
                    drain_caller=(caller.subject_id, caller.profile_id)
                    if not normally_authorized
                    else None,
                    expected_binding_revision=(
                        binding.revision if binding.status == "active" else None
                    ),
                )

    def event_queue_status(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> EventQueueStatus:
        """Read backlog, lag, and aggregate claim counts for one project."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).event_queue_status()

    def consumer_source_epoch(
        self, caller: AuthenticatedCaller, project_id: str,
        event_id: str | None = None,
    ) -> int:
        """Return the active writer's current consumer source epoch."""

        plugin = self._plugins.get(project_id)
        if plugin is None:
            raise PermissionError("project is not authorized")
        binding = plugin.service.store.get_consumer_binding(project_id)
        if binding.status == "active":
            if not self.limiter.allow(caller.subject_id, project_id):
                raise RateLimitExceeded("project request budget exceeded")
            if self.authorizer.authorize(caller, project_id, ProjectAction.WRITE):
                return binding.source_epoch
            if event_id is not None:
                replay_epoch = (
                    plugin.service.store.suspended_processed_event_source_epoch(
                        caller.subject_id,
                        project_id,
                        event_id,
                        plugin.config.repository_fingerprint,
                        plugin.config.config_sha256,
                        plugin.config.backend_api_version,
                    )
                )
                if replay_epoch is not None:
                    return replay_epoch
            raise PermissionError("project is not authorized")
        if binding.status == "deregistration_pending" and event_id is not None:
            drain_epoch = plugin.service.store.consumer_drain_epoch(
                project_id, caller.subject_id, caller.profile_id, event_id
            )
            if drain_epoch is not None:
                if not self.limiter.allow(caller.subject_id, project_id):
                    raise RateLimitExceeded("project request budget exceeded")
                return drain_epoch
        raise PermissionError("consumer binding is not active")

    def project_activity_status(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> ProjectActivitySnapshot:
        """Read project capture/curation activity separately from readiness."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).activity_status()

    def project_health(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> ProjectHealthSnapshot:
        """Aggregate local queues/capacity and trusted host probes fail-closed."""

        plugin = self._authorized_plugin(caller, project_id, ProjectAction.READ)
        return self._collect_project_health_snapshot(plugin, project_id)[0]

    def project_prometheus_metrics(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> str:
        """Render one authorized, content-free Prometheus project snapshot."""

        plugin = self._authorized_plugin(caller, project_id, ProjectAction.READ)
        health, usage = self._collect_project_health_snapshot(plugin, project_id)
        feedback = (
            plugin.sde_quality_feedback_summary() if usage is not None else None
        )
        return render_project_metrics(health, usage, feedback)

    def _collect_project_health_snapshot(
        self, plugin: ProjectPlugin, project_id: str
    ) -> tuple[ProjectHealthSnapshot, ProjectStorageUsage | None]:
        """Build health and storage observations from one project plugin read."""
        try:
            queue, counts, usage, scrub_count, database_observed_at = (
                plugin.operational_health_inputs()
            )
        except sqlite3.Error:
            dependencies = evaluate_dependencies(
                self.dependency_readiness, project_id, datetime.now(UTC)
            )
            snapshot = ProjectHealthSnapshot(
                project_id=project_id,
                observed_at=utc_now(),
                database_observed_at=None,
                database_observation_complete=False,
                status=(
                    OperationalHealth.DEGRADED
                    if dependencies.degraded
                    else OperationalHealth.UNKNOWN
                ),
                event_received_count=None,
                event_failed_count=None,
                event_quarantined_count=None,
                event_claimed_count=None,
                event_expired_claim_count=None,
                oldest_pending_event_age_seconds=None,
                operational_counts=None,
                fact_capacity_reached=None,
                event_capacity_available=None,
                staging_inventory_complete=None,
                staging_observed_at=None,
                staging_regular_file_count=None,
                dependencies=dependencies.dependencies,
                gate_codes=("database_observation_failed",) + dependencies.gates,
            )
            return snapshot, None
        local = evaluate_local_health(
            queue,
            counts,
            usage,
            scrub_count,
        )
        dependencies = evaluate_dependencies(
            self.dependency_readiness, project_id, datetime.now(UTC)
        )
        gates = local.gates + dependencies.gates
        staging_complete = usage.staging.inventory_complete if usage.staging else None
        staging_file_count = usage.staging.regular_file_count if usage.staging else None
        status = (
            OperationalHealth.DEGRADED
            if local.degraded or dependencies.degraded
            else OperationalHealth.UNKNOWN
            if local.unknown or dependencies.unknown
            else OperationalHealth.HEALTHY
        )
        snapshot = ProjectHealthSnapshot(
            project_id=project_id,
            observed_at=utc_now(),
            database_observed_at=database_observed_at,
            database_observation_complete=True,
            status=status,
            event_received_count=queue.received_count,
            event_failed_count=queue.failed_count,
            event_quarantined_count=queue.quarantined_count,
            event_claimed_count=queue.claimed_count,
            event_expired_claim_count=queue.expired_claim_count,
            oldest_pending_event_age_seconds=queue.oldest_pending_age_seconds,
            operational_counts=counts,
            fact_capacity_reached=usage.fact_capacity_reached,
            event_capacity_available=usage.global_event_inbox.can_accept_new_event,
            staging_inventory_complete=staging_complete,
            staging_observed_at=usage.staging.observed_at if usage.staging else None,
            staging_regular_file_count=staging_file_count,
            dependencies=dependencies.dependencies,
            gate_codes=gates,
        )
        return snapshot, usage

    @_project_effect_fenced(ProjectAction.EVENT_RETRY)
    def retry_quarantined_event(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        event_id: str,
    ) -> EventInboxReceipt:
        """Authorize, audit, and requeue one quarantined project event."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.EVENT_RETRY
        ).retry_quarantined_event(event_id, caller.subject_id)

    def goal_status(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        sde_offset: int = 0,
        purge_offset: int = 0,
    ) -> GoalSnapshot:
        """Return one bounded goal page and evidence-derived criterion progress."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_status(goal_id, sde_offset, purge_offset)

    def goal_bullet_projection(
        self, caller: AuthenticatedCaller, project_id: str, goal_id: str
    ) -> GoalBulletProjection:
        """Read compact bullets separating recorded truth from open claims."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_bullet_projection(goal_id)

    def goal_report(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        page: GoalReportPage | None = None,
    ) -> str:
        """Render a bounded report after project-scoped read authorization."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_report(goal_id, page)

    def fact_compaction_propose(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        max_facts: int = 32,
    ) -> FactCompactionProposal:
        """Preview exact routine-fact bullets for an authorized project read."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).fact_compaction_propose(goal_id, max_facts)

    @_project_effect_fenced(ProjectAction.REVIEW)
    def fact_compaction_approve(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        compaction_id: str,
        goal_id: str,
        fact_ids: tuple[str, ...],
        source_sha256: str,
        approval_reason: str,
    ) -> FactArchiveReceipt:
        """Review-authorized atomic archival bound to the authenticated caller."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).fact_compaction_approve(
            compaction_id,
            goal_id,
            fact_ids,
            source_sha256,
            caller.subject_id,
            approval_reason,
        )

    def fact_archive_receipts(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read a bounded, project-authorized archive audit view."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).fact_archive_receipts(goal_id, offset, limit)

    def goal_list(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> tuple[GoalSnapshot, ...]:
        """List goals only inside the authorized project binding."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_list(statuses)

    def goal_list_page(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """Read a bounded page of compact goal cards after project authorization."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_list_page(offset=offset, limit=limit, statuses=statuses)

    def goal_children(
        self, caller: AuthenticatedCaller, project_id: str, parent_goal_id: str
    ) -> tuple[GoalSnapshot, ...]:
        """List direct child goal cards in the authorized project."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_children(parent_goal_id)

    def goal_children_page(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        parent_goal_id: str,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """Read a bounded child-card page after project authorization."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_children_page(
            parent_goal_id,
            offset=offset,
            limit=limit,
            statuses=statuses,
        )

    @_project_effect_fenced(ProjectAction.WRITE)
    def goal_reopen(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        reason: str,
        next_action: str,
    ) -> GoalSnapshot:
        """Reopen a completed goal, preserving the project/action boundary."""

        plugin = self._authorized_plugin(caller, project_id, ProjectAction.WRITE)
        plugin.goal_reopen(goal_id, reason, next_action)
        return plugin.goal_status(goal_id)

    @_project_effect_fenced(ProjectAction.WRITE)
    def goal_amend_criteria(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        expected_revision: int,
        success_criteria: tuple[SuccessCriterion, ...],
        reason: str,
        next_action: str,
    ) -> GoalSnapshot:
        """Amend a goal contract under project write authorization."""

        plugin = self._authorized_plugin(caller, project_id, ProjectAction.WRITE)
        plugin.goal_amend_criteria(
            goal_id,
            expected_revision,
            success_criteria,
            reason,
            next_action,
        )
        return plugin.goal_status(goal_id)

    def project_storage_usage(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> ProjectStorageUsage:
        """Return authorized project usage without exposing other projects."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).storage_usage()

    def discover_artifact_inventory(
        self, caller: AuthenticatedCaller, project_id: str, goal_id: str
    ) -> StagingArtifactInventory:
        """Hash one goal's bounded staging directory for an authorized review."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).discover_staging_artifacts(goal_id)

    def discover_project_artifact_inventory(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> StagingArtifactInventory:
        """Hash the bounded project staging tree for an authorized review."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).discover_project_staging_artifacts()

    def discover_project_expiry_inventory(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> StagingExpirySnapshot:
        """Read record-ready or 72-hour-max expiry eligibility, without purge authority."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).discover_expired_staging_artifacts()

    @_project_effect_fenced(ProjectAction.REVIEW)
    def approve_project_expiry_inventory(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        artifacts: tuple[ArtifactRef, ...],
        manifest_sha256: str,
    ) -> ExpiryPurgeReceipt:
        """Record human-authorized expiry approval before exact cleanup."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).approve_expired_staging_inventory(
            artifacts,
            manifest_sha256,
            authenticated_subject=caller.subject_id,
        )

    @_project_effect_fenced(ProjectAction.REVIEW)
    def retry_expiry_purge(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        receipt_id: str,
    ) -> ExpiryPurgeReceipt:
        """Retry due targets from one previously approved expiry receipt."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).retry_expiry_purge(receipt_id)

    def sde_review_queue(
        self, caller: AuthenticatedCaller, project_id: str, limit: int = 100
    ) -> tuple[SDEReviewDetail, ...]:
        """Read a bounded project-scoped human review queue."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).sde_review_queue(limit)

    def sde_assess(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        materiality: Materiality,
        rationale: str,
        fact_ids: tuple[str, ...],
        impact: str | None = None,
        retrieval_value: str | None = None,
    ) -> SDECandidate | None:
        """Assess facts under write scope; proposals still require human review."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.WRITE
        ).sde_assess(
            goal_id, materiality, rationale, fact_ids, impact, retrieval_value
        )

    def sde_review_detail(
        self, caller: AuthenticatedCaller, project_id: str, candidate_id: str
    ) -> SDEReviewDetail:
        """Read the selected facts/evidence for one candidate."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).sde_review_detail(candidate_id)

    def sde_review_packet(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        candidate_id: str,
        review_artifacts: tuple[ArtifactRef, ...] | None = None,
    ) -> SDEReviewPacket:
        """Read candidate facts and a fresh staging manifest under review scope."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).sde_review_packet(candidate_id, review_artifacts)

    def sde_confirm(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        artifacts: tuple[ArtifactRef, ...],
        *,
        artifact_inventory_complete: bool,
        dependency_map_sha256: str | None = None,
        rationale: str | None = None,
    ) -> AuditReceipt:
        """Submit a review decision; plugin authorizer independently rechecks it."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).sde_confirm(
            candidate_id,
            decision,
            artifacts,
            artifact_inventory_complete=artifact_inventory_complete,
            dependency_map_sha256=dependency_map_sha256,
            rationale=rationale,
            authenticated_subject=caller.subject_id,
        )

    @_project_effect_fenced(ProjectAction.REVIEW)
    def sde_correction_record(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        correction_id: str,
        candidate_id: str,
        correction: str,
        rationale: str,
    ) -> SDECorrection:
        """Append an authenticated correction as a linked follow-up record."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).sde_correction_record(
            correction_id,
            candidate_id,
            correction,
            rationale,
            authenticated_subject=caller.subject_id,
        )

    @_project_effect_fenced(ProjectAction.REVIEW)
    def sde_quality_feedback_record(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        feedback_id: str,
        candidate_id: str,
        label: SDEQualityFeedbackLabel,
        rationale: str = "",
    ) -> SDEQualityFeedback:
        """Record feedback only from an authenticated project reviewer."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).sde_quality_feedback_record(
            feedback_id,
            candidate_id,
            label,
            rationale,
            authenticated_subject=caller.subject_id,
        )

    def sde_quality_feedback_summary(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> SDEQualityFeedbackSummary:
        """Return project-scoped aggregate labels without reviewer identities."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).sde_quality_feedback_summary()

    def persist_goal(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        target: str,
    ) -> MarkdownProjectionResult:
        """Persist one goal to a configured target before any eligible purge."""

        # The plugin fences each projection/receipt/purge effect after evidence
        # verification. Do not hold the API-wide SQLite fence while the verifier
        # runs; verifier adapters may consult external evidence sources.
        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).persist_goal(goal_id, target)

    def reconcile_goal(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        goal_id: str,
        target: str,
    ) -> MarkdownReconciliationResult:
        """Compare one configured Markdown projection with SQLite read-only."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).reconcile_goal(goal_id, target)

    def reconcile_project(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        target: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MarkdownProjectReconciliation:
        """Reconcile one configured Markdown target against a bounded goal page."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).reconcile_project(target, offset=offset, limit=limit)

    def artifact_inventory_complete(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        dependency_map_sha256: str,
    ) -> AuditReceipt:
        """Authorize completion of an exact review receipt's purge manifest."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).artifact_inventory_complete(
            receipt_id,
            artifacts,
            dependency_map_sha256,
            authenticated_subject=caller.subject_id,
        )

    def artifact_purge_status(
        self, caller: AuthenticatedCaller, project_id: str, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Read a receipt and its bounded per-artifact purge outcomes."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).artifact_purge_status(receipt_id)

    def authorize_artifact_cleanup(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        receipt_id: str,
        artifacts: tuple[ArtifactRef, ...],
        manifest_sha256: str,
        dependency_map_sha256: str,
        target: str,
    ) -> tuple[CleanupAuthorizationReceipt, AuditReceipt]:
        """Record a separate reviewer decision for one exact current manifest."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).authorize_artifact_cleanup(
            receipt_id,
            artifacts,
            manifest_sha256,
            dependency_map_sha256,
            target,
            authenticated_subject=caller.subject_id,
        )

    @_project_effect_fenced(ProjectAction.RETENTION_HOLD_RELEASE)
    def release_artifact_hold(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        receipt_id: str,
        path: str,
        rationale: str,
    ) -> AuditReceipt:
        """Require a dedicated host scope plus reviewer authorization to release."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.RETENTION_HOLD_RELEASE
        ).release_artifact_hold(
            receipt_id,
            path,
            rationale,
            authenticated_subject=caller.subject_id,
        )

    @_project_effect_fenced(ProjectAction.PURGE_RETRY)
    def retry_pending_purges(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> tuple[AuditReceipt, ...]:
        """Retry only reviewed, persisted manifests in the authorized project."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.PURGE_RETRY
        ).retry_pending_purges()

    def _authorized_plugin(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        action: ProjectAction,
    ) -> ProjectPlugin:
        if not _PROJECT_ID_RE.fullmatch(project_id):
            raise PermissionError("project is not authorized")
        plugin = self._plugins.get(project_id)
        if plugin is None or not self.authorizer.authorize(caller, project_id, action):
            raise PermissionError("project is not authorized")
        if not self.limiter.allow(caller.subject_id, project_id):
            raise RateLimitExceeded("project request budget exceeded")
        return plugin
