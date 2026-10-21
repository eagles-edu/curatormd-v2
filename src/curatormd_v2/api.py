"""Fail-closed, transport-neutral API boundary for trusted host adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import re
from threading import Lock
import time
from typing import Callable, Iterable, Mapping, Protocol

from .events import (
    EventEnvelope,
    EventInboxReceipt,
    EventQueueStatus,
    MAX_EVENT_BYTES,
)
from .errors import RateLimitExceeded
from .models import (
    ArtifactRef,
    AuditReceipt,
    FactArchiveReceipt,
    FactCompactionProposal,
    GoalListPage,
    GoalSnapshot,
    GoalBulletProjection,
    GoalStatus,
    Materiality,
    ProjectActivitySnapshot,
    ProjectOperationalCounts,
    ProjectStorageUsage,
    ProjectHealthSnapshot,
    OperationalHealth,
    DependencyHealth,
    DependencyProbeObservation,
    utc_now,
    StagingArtifactInventory,
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
from .service import PurgeTargetStatus


_SUBJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_PROJECT_ID_RE = _SUBJECT_ID_RE
MAX_TRACKED_CALLERS = 10_000


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

    def __post_init__(self) -> None:
        if not _SUBJECT_ID_RE.fullmatch(self.subject_id):
            raise ValueError("subject_id must be a bounded opaque identifier")


class ProjectAuthorizer(Protocol):
    """Host-owned authorization for an identity, project, and operation."""

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

    def allow(self, subject_id: str, project_id: str) -> bool:
        """Consume one request token, if available."""
        ...


class ProjectDependencyReadiness(Protocol):
    """Trusted host adapter for required project-scoped service probes."""

    def readiness(self, project_id: str) -> Mapping[str, object]:
        """Return timestamped probe records; missing or malformed stays unknown."""
        ...


REQUIRED_HEALTH_DEPENDENCIES = (
    "event_router",
    "purge_scheduler",
    "host_identity",
    "human_review",
    "artifact_producer_inventory",
)
MAX_DEPENDENCY_PROBE_AGE_SECONDS = 60
MAX_DEPENDENCY_CLOCK_SKEW_SECONDS = 5


@dataclass(frozen=True, slots=True)
class _HealthEvaluation:
    """Internal health decision fragments combined into one public snapshot."""

    gates: tuple[str, ...] = ()
    degraded: bool = False
    unknown: bool = False
    dependencies: tuple[DependencyHealth, ...] = ()


@dataclass(frozen=True, slots=True)
class _DependencyEvaluation:
    """One dependency result plus its fail-closed gate effects."""

    health: DependencyHealth
    gates: tuple[str, ...]
    degraded: bool
    unknown: bool
    probe_failed: bool


def _parse_fresh_probe_time(value: object) -> datetime | None:
    """Parse a bounded timezone-aware ISO timestamp without trusting raw input."""

    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _evaluate_local_health(
    queue: EventQueueStatus,
    counts: ProjectOperationalCounts,
    usage: ProjectStorageUsage,
) -> _HealthEvaluation:
    """Turn local queue, review, purge, capacity, and staging state into gates."""
    gates: list[str] = []
    degraded = False
    unknown = False
    conditions = (
        (queue.received_count > 0, "event_backlog"),
        (queue.failed_count > 0, "event_failures"),
        (queue.quarantined_count > 0, "event_quarantine"),
        (queue.expired_claim_count > 0, "expired_event_claims"),
        (counts.pending_review_count > 0, "review_backlog"),
        (counts.pending_purge_receipt_count > 0, "purge_pending"),
        (counts.pending_purge_artifact_count > 0, "purge_artifacts_pending"),
        (not usage.global_event_inbox.can_accept_new_event, "event_capacity_exhausted"),
        (usage.fact_capacity_reached, "fact_capacity_exhausted"),
    )
    for condition, code in conditions:
        if condition:
            gates.append(code)
            degraded = True

    staging = usage.staging
    staging_complete = staging.inventory_complete if staging is not None else None
    staging_count = staging.regular_file_count if staging is not None else None
    if staging is not None and staging_complete is True:
        byte_limit_reached = (
            usage.staging_project_byte_limit is not None
            and staging.observed_file_bytes >= usage.staging_project_byte_limit
        )
        file_limit_reached = (
            usage.staging_project_file_limit is not None
            and staging.regular_file_count >= usage.staging_project_file_limit
        )
        if byte_limit_reached or file_limit_reached:
            gates.append("staging_budget_reached")
            degraded = True
    if staging_complete is False:
        gates.append("staging_inventory_incomplete")
        degraded = True
        if staging is not None and staging.error_code in {
            "root_invalid",
            "root_unavailable",
            "permission_denied",
            "unsupported_platform",
            "staging_root_unavailable",
            "staging_lock_unavailable",
        }:
            gates.append("staging_adapter_unavailable")
    elif staging_complete is None:
        gates.append("staging_inventory_unavailable")
        unknown = True
    if staging_count is not None and staging_count > 0:
        gates.append("staged_artifacts_present")
        degraded = True
    return _HealthEvaluation(tuple(gates), degraded, unknown)


def _evaluate_dependency(
    name: str,
    readiness: Mapping[str, object],
    probe_failed: bool,
    now: datetime,
) -> _DependencyEvaluation:
    """Interpret one timestamped readiness result without turning bad data green."""
    observation: DependencyProbeObservation | None = None
    age_seconds: int | None = None
    gates: list[str] = []
    degraded = False
    unknown = False
    state = OperationalHealth.UNKNOWN

    if not probe_failed:
        try:
            raw = readiness.get(name)
        except Exception:  # noqa: BLE001 - malformed host data is not readiness
            probe_failed = True
            raw = None
        if raw is None:
            state = OperationalHealth.UNKNOWN
        elif not isinstance(raw, DependencyProbeObservation):
            gates.append(f"dependency_probe_invalid:{name}")
            unknown = True
        else:
            observation = raw
            checked_at = _parse_fresh_probe_time(raw.observed_at)
            if checked_at is None:
                gates.append(f"dependency_probe_time_invalid:{name}")
                unknown = True
            else:
                age = (now - checked_at).total_seconds()
                age_seconds = max(0, int(age))
                if (
                    age > MAX_DEPENDENCY_PROBE_AGE_SECONDS
                    or age < -MAX_DEPENDENCY_CLOCK_SKEW_SECONDS
                ):
                    gates.append(f"dependency_probe_stale:{name}")
                    unknown = True
                elif raw.ready is True:
                    state = OperationalHealth.HEALTHY
                elif raw.ready is False:
                    state = OperationalHealth.DEGRADED
                else:
                    unknown = True

    if state is OperationalHealth.DEGRADED:
        gates.append(f"dependency_unavailable:{name}")
        degraded = True
    elif state is OperationalHealth.UNKNOWN:
        gates.append(f"dependency_unknown:{name}")
        unknown = True
    dependency = DependencyHealth(
        name=name,
        status=state,
        observed_at=observation.observed_at if observation else None,
        age_seconds=age_seconds,
    )
    return _DependencyEvaluation(
        dependency, tuple(gates), degraded, unknown, probe_failed
    )


def _evaluate_dependencies(
    readiness_provider: ProjectDependencyReadiness | None,
    project_id: str,
    now: datetime,
) -> _HealthEvaluation:
    """Read required host probes and aggregate unknown/degraded results."""
    readiness: Mapping[str, object] = {}
    probe_failed = False
    if readiness_provider is not None:
        try:
            readiness = readiness_provider.readiness(project_id)
        except Exception:  # noqa: BLE001 - health must degrade to unknown, not green
            probe_failed = True

    dependencies: list[DependencyHealth] = []
    gates: list[str] = []
    degraded = False
    unknown = False
    for name in REQUIRED_HEALTH_DEPENDENCIES:
        result = _evaluate_dependency(name, readiness, probe_failed, now)
        probe_failed = result.probe_failed
        dependencies.append(result.health)
        gates.extend(result.gates)
        degraded = degraded or result.degraded
        unknown = unknown or result.unknown
    if probe_failed:
        gates.append("dependency_probe_failed")
        unknown = True
    return _HealthEvaluation(
        tuple(gates), degraded, unknown, tuple(dependencies)
    )


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

    def process_event_json(
        self, caller: AuthenticatedCaller, project_id: str, serialized: str
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
        plugin = self._authorized_plugin(caller, project_id, ProjectAction.WRITE)
        event = EventEnvelope.from_json(serialized)
        if event.project_id != project_id:
            raise PermissionError("event project does not match authorized project")
        return plugin.process_event(event)

    def event_queue_status(
        self, caller: AuthenticatedCaller, project_id: str
    ) -> EventQueueStatus:
        """Read backlog, lag, and aggregate claim counts for one project."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).event_queue_status()

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
        feedback = plugin.sde_quality_feedback_summary()
        return render_project_metrics(health, usage, feedback)

    def _collect_project_health_snapshot(
        self, plugin: ProjectPlugin, project_id: str
    ) -> tuple[ProjectHealthSnapshot, ProjectStorageUsage]:
        """Build health and storage observations from one project plugin read."""
        queue, counts, usage = plugin.operational_health_inputs()
        local = _evaluate_local_health(queue, counts, usage)
        dependencies = _evaluate_dependencies(
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
            staging_regular_file_count=staging_file_count,
            dependencies=dependencies.dependencies,
            gate_codes=gates,
        )
        return snapshot, usage

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
        fact_offset: int = 0,
        fact_limit: int = 16,
        child_offset: int = 0,
        sde_offset: int = 0,
        receipt_offset: int = 0,
    ) -> str:
        """Render a bounded report after project-scoped read authorization."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).goal_report(
            goal_id,
            fact_offset=fact_offset,
            fact_limit=fact_limit,
            child_offset=child_offset,
            sde_offset=sde_offset,
            receipt_offset=receipt_offset,
        )

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
    ) -> SDECandidate | None:
        """Assess facts under write scope; proposals still require human review."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.WRITE
        ).sde_assess(goal_id, materiality, rationale, fact_ids)

    def sde_review_detail(
        self, caller: AuthenticatedCaller, project_id: str, candidate_id: str
    ) -> SDEReviewDetail:
        """Read the selected facts/evidence for one candidate."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).sde_review_detail(candidate_id)

    def sde_review_packet(
        self, caller: AuthenticatedCaller, project_id: str, candidate_id: str
    ) -> SDEReviewPacket:
        """Read candidate facts and a fresh staging manifest under review scope."""

        plugin = self._authorized_plugin(caller, project_id, ProjectAction.REVIEW)
        detail = plugin.sde_review_detail(candidate_id)
        return SDEReviewPacket(
            detail=detail,
            artifact_inventory=plugin.discover_staging_artifacts(
                detail.candidate.goal_id
            ),
        )

    def sde_confirm(
        self,
        caller: AuthenticatedCaller,
        project_id: str,
        candidate_id: str,
        decision: ReviewDecision,
        artifacts: tuple[ArtifactRef, ...],
        *,
        artifact_inventory_complete: bool,
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
            rationale=rationale,
            authenticated_subject=caller.subject_id,
        )

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
    ) -> AuditReceipt:
        """Authorize completion of an exact review receipt's purge manifest."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.REVIEW
        ).artifact_inventory_complete(
            receipt_id,
            artifacts,
            authenticated_subject=caller.subject_id,
        )

    def artifact_purge_status(
        self, caller: AuthenticatedCaller, project_id: str, receipt_id: str
    ) -> tuple[AuditReceipt, tuple[PurgeTargetStatus, ...]]:
        """Read a receipt and its bounded per-artifact purge outcomes."""

        return self._authorized_plugin(
            caller, project_id, ProjectAction.READ
        ).artifact_purge_status(receipt_id)

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
