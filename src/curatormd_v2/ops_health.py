"""Strictly validate project-bound health, queue, and freshness evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

HEALTH_NAMES = {
    "event_router",
    "purge_scheduler",
    "database_storage_adapter",
    "host_identity",
    "human_review",
    "alert_delivery",
    "artifact_producer_inventory",
}
OPERATIONAL_COUNT_NAMES = {
    "pending_review_count",
    "pending_purge_receipt_count",
    "pending_purge_artifact_count",
    "pending_expiry_purge_receipt_count",
    "pending_expiry_purge_artifact_count",
}
SHARED_FRESHNESS_SECONDS = 180
UNKNOWN_AGE_SECONDS = 2**31
JsonObject = dict[str, Any]


def _age(raw: Any) -> int:
    """Return age in seconds, treating missing, malformed, or future evidence as stale."""
    try:
        observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        return UNKNOWN_AGE_SECONDS if age < -5 else max(0, int(age))
    except (ValueError, TypeError):
        return UNKNOWN_AGE_SECONDS


def _nonnegative_integer(value: Any) -> bool:
    """Accept exact non-negative JSON integers, excluding booleans."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _queue_complete(health: JsonObject) -> bool:
    """Require complete event, operational, and staging queue evidence."""
    counts_value = health.get("operational_counts")
    if not isinstance(counts_value, dict):
        return False
    counts = cast(JsonObject, counts_value)
    event_count_names = (
        "event_received_count",
        "event_claimed_count",
        "event_failed_count",
        "event_quarantined_count",
        "event_expired_claim_count",
    )
    oldest_pending_age = health.get("oldest_pending_event_age_seconds")
    return (
        health.get("database_observation_complete") is True
        and health.get("staging_inventory_complete") is True
        and _age(health.get("database_observed_at")) <= SHARED_FRESHNESS_SECONDS
        and _age(health.get("staging_observed_at")) <= SHARED_FRESHNESS_SECONDS
        and set(counts) == OPERATIONAL_COUNT_NAMES
        and all(_nonnegative_integer(counts.get(name)) for name in OPERATIONAL_COUNT_NAMES)
        and all(_nonnegative_integer(health.get(name)) for name in event_count_names)
        and (
            oldest_pending_age is None or _nonnegative_integer(oldest_pending_age)
        )
        and _nonnegative_integer(health.get("staging_regular_file_count"))
    )


def _dependency_map(value: Any) -> tuple[dict[str, JsonObject], bool]:
    """Collect unique named dependency rows and flag malformed entries."""
    dependencies: dict[str, JsonObject] = {}
    malformed = not isinstance(value, list)
    if not isinstance(value, list):
        return dependencies, malformed
    for item in cast(list[Any], value):
        if not isinstance(item, dict):
            malformed = True
            continue
        dependency = cast(JsonObject, item)
        name_value = dependency.get("name")
        if not isinstance(name_value, str):
            malformed = True
            continue
        name = name_value
        if name in dependencies:
            malformed = True
        dependencies[name] = dependency
    return dependencies, malformed


def summarize_health(value: JsonObject, project_id: str) -> dict[str, Any]:
    """Validate identity, seven unique fresh dependencies, and complete snapshots."""
    health_value = value.get("health")
    if not isinstance(health_value, dict):
        return {
            "status": "degraded",
            "age_seconds": UNKNOWN_AGE_SECONDS,
            "dependencies": {},
            "gates": [],
            "queue_snapshot_complete": False,
        }
    health = cast(JsonObject, health_value)
    age = _age(health.get("observed_at"))
    dependencies, malformed = _dependency_map(health.get("dependencies"))
    dependency_rows = {
        name: {
            "status": dependencies.get(name, {}).get("status", "missing"),
            "age_seconds": _age(dependencies.get(name, {}).get("observed_at")),
        }
        for name in sorted(HEALTH_NAMES)
    }
    stale = any(
        name not in dependencies
        or dependencies[name].get("status") != "healthy"
        or _age(dependencies[name].get("observed_at")) > SHARED_FRESHNESS_SECONDS
        for name in HEALTH_NAMES
    )
    database_age = _age(health.get("database_observed_at"))
    staging_age = _age(health.get("staging_observed_at"))
    queue_complete = _queue_complete(health)
    identity_matches = (
        value.get("connected") is True
        and value.get("project_id") == project_id
        and health.get("project_id") == project_id
    )
    healthy = (
        identity_matches
        and health.get("status") == "healthy"
        and age <= SHARED_FRESHNESS_SECONDS
        and database_age <= SHARED_FRESHNESS_SECONDS
        and staging_age <= SHARED_FRESHNESS_SECONDS
        and not malformed
        and set(dependencies) == HEALTH_NAMES
        and not stale
        and queue_complete
    )
    return {
        "status": "healthy" if healthy else "degraded",
        "age_seconds": age,
        "database_age_seconds": database_age,
        "staging_age_seconds": staging_age,
        "dependencies": dependency_rows,
        "gates": health.get("gate_codes", []),
        "queue_snapshot_complete": queue_complete,
        "event_counts": {
            name: health.get(name)
            for name in (
                "event_received_count",
                "event_claimed_count",
                "event_failed_count",
                "event_quarantined_count",
                "event_expired_claim_count",
                "oldest_pending_event_age_seconds",
            )
        },
        "operational_counts": (
            dict(health["operational_counts"])
            if isinstance(health.get("operational_counts"), dict)
            else None
        ),
        "staging_regular_file_count": health.get("staging_regular_file_count"),
    }
