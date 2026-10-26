"""Fail-closed aggregation of local and host dependency health inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping, Protocol, TypeAlias

from .events import EventQueueStatus
from .models import (
    DependencyHealth,
    DependencyProbeObservation,
    OperationalHealth,
    ProjectOperationalCounts,
    ProjectStorageUsage,
)
from .staging_models import StagingUsage


class ProjectDependencyReadiness(Protocol):
    """Trusted host adapter for required project-scoped service probes."""

    # pylint: disable=too-few-public-methods  # Protocol intentionally has one readiness operation.

    def readiness(self, project_id: str) -> Mapping[str, object]:
        """Return timestamped probe records; missing or malformed stays unknown."""
        ...


REQUIRED_HEALTH_DEPENDENCIES = (
    "event_router",
    "purge_scheduler",
    "database_storage_adapter",
    "host_identity",
    "human_review",
    "alert_delivery",
    "artifact_producer_inventory",
)
MAX_DEPENDENCY_PROBE_AGE_SECONDS = 60
MAX_DEPENDENCY_CLOCK_SKEW_SECONDS = 5
STAGING_BUDGET_WARNING_PERCENT = 75


@dataclass(frozen=True, slots=True)
class _HealthEvaluation:
    """Internal health decision fragments combined into one public snapshot."""

    gates: tuple[str, ...] = ()
    degraded: bool = False
    unknown: bool = False
    dependencies: tuple[DependencyHealth, ...] = ()


_ProbeEvaluation: TypeAlias = tuple[
    DependencyProbeObservation | None,
    OperationalHealth,
    int | None,
    tuple[str, ...],
    bool,
]


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


def evaluate_local_health(
    queue: EventQueueStatus,
    counts: ProjectOperationalCounts,
    usage: ProjectStorageUsage,
    event_payload_scrub_pending_count: int = 0,
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
        (event_payload_scrub_pending_count > 0, "sqlite_payload_scrub_pending"),
        (counts.pending_review_count > 0, "review_backlog"),
        (counts.pending_purge_receipt_count > 0, "purge_pending"),
        (counts.pending_purge_artifact_count > 0, "purge_artifacts_pending"),
        (counts.pending_expiry_purge_receipt_count > 0, "expiry_purge_pending"),
        (counts.pending_expiry_purge_artifact_count > 0, "expiry_purge_artifacts_pending"),
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
    if staging is not None and staging.observed_at is None:
        gates.append("staging_observation_time_unavailable")
        unknown = True
    _add_staging_budget_gate(staging, usage, gates)
    degraded = degraded or any(
        code in gates for code in ("staging_budget_warning", "staging_budget_reached")
    )
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


def _add_staging_budget_gate(
    staging: StagingUsage | None,
    usage: ProjectStorageUsage,
    gates: list[str],
) -> None:
    """Add one capacity gate only when a complete staging scan proves it."""

    if staging is None or staging.inventory_complete is not True:
        return
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
        return
    byte_limit_warning = _staging_budget_warning(
        staging.observed_file_bytes,
        usage.staging_project_byte_limit,
    )
    file_limit_warning = _staging_budget_warning(
        staging.regular_file_count,
        usage.staging_project_file_limit,
    )
    if byte_limit_warning or file_limit_warning:
        gates.append("staging_budget_warning")


def _staging_budget_warning(observed: int, limit: int | None) -> bool:
    """Warn at the approved 75% threshold without dividing or rounding."""

    return (
        limit is not None
        and limit > 0
        and observed < limit
        and observed * 100 >= limit * STAGING_BUDGET_WARNING_PERCENT
    )


def _evaluate_probe_value(
    name: str,
    raw: object,
    now: datetime,
) -> _ProbeEvaluation:
    """Validate a readiness value and preserve unknown/stale distinctions."""

    if raw is None:
        return None, OperationalHealth.UNKNOWN, None, (), True
    if not isinstance(raw, DependencyProbeObservation):
        return (
            None,
            OperationalHealth.UNKNOWN,
            None,
            (f"dependency_probe_invalid:{name}",),
            True,
        )
    checked_at = _parse_fresh_probe_time(raw.observed_at)
    if checked_at is None:
        return (
            raw,
            OperationalHealth.UNKNOWN,
            None,
            (f"dependency_probe_time_invalid:{name}",),
            True,
        )
    age = (now - checked_at).total_seconds()
    age_seconds = max(0, int(age))
    if (
        age > MAX_DEPENDENCY_PROBE_AGE_SECONDS
        or age < -MAX_DEPENDENCY_CLOCK_SKEW_SECONDS
    ):
        return (
            raw,
            OperationalHealth.UNKNOWN,
            age_seconds,
            (f"dependency_probe_stale:{name}",),
            True,
        )
    if raw.ready is True:
        state = OperationalHealth.HEALTHY
        unknown = False
    elif raw.ready is False:
        state = OperationalHealth.DEGRADED
        unknown = False
    else:
        state = OperationalHealth.UNKNOWN
        unknown = True
    return raw, state, age_seconds, (), unknown


def _evaluate_dependency(
    name: str,
    readiness: Mapping[str, object],
    probe_failed: bool,
    now: datetime,
) -> _DependencyEvaluation:
    """Interpret one timestamped readiness result without turning bad data green."""

    raw: object = None
    if not probe_failed:
        try:
            raw = readiness.get(name)
        # A host-supplied Mapping may raise adapter-defined exceptions on read.
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            probe_failed = True
    observation, state, age_seconds, probe_gates, probe_unknown = (
        _evaluate_probe_value(name, raw, now)
    )
    gates = list(probe_gates)
    degraded = False
    unknown = probe_unknown
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


def evaluate_dependencies(
    readiness_provider: ProjectDependencyReadiness | None,
    project_id: str,
    now: datetime,
) -> _HealthEvaluation:
    """Read required host probes and aggregate unknown/degraded results."""

    readiness: Mapping[str, object] = {}
    provider_failed = False
    if readiness_provider is not None:
        try:
            readiness = readiness_provider.readiness(project_id)
        # A readiness adapter may fail with any exception; unknown must not go green.
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            provider_failed = True

    dependencies: list[DependencyHealth] = []
    gates: list[str] = []
    degraded = False
    unknown = False
    dependency_probe_failed = provider_failed
    for name in REQUIRED_HEALTH_DEPENDENCIES:
        result = _evaluate_dependency(name, readiness, provider_failed, now)
        dependency_probe_failed = dependency_probe_failed or result.probe_failed
        dependencies.append(result.health)
        gates.extend(result.gates)
        degraded = degraded or result.degraded
        unknown = unknown or result.unknown
    if dependency_probe_failed:
        gates.append("dependency_probe_failed")
        unknown = True
    return _HealthEvaluation(tuple(gates), degraded, unknown, tuple(dependencies))
