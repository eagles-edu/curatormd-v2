"""Content-free, bounded Prometheus exposition for one authorized project."""

from __future__ import annotations

import re

from .events import EventInboxStatus, EventKind
from .models import (
    OperationalHealth,
    ProjectHealthSnapshot,
    ProjectStorageUsage,
    StagingArtifactClass,
    SDEQualityFeedbackSummary,
)

_KNOWN_EVENT_TYPES = frozenset(item.value for item in EventKind) | {"legacy.unknown"}
_KNOWN_EVENT_STATUSES = frozenset(item.value for item in EventInboxStatus)
_SAFE_GATE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")


def _label(value: str) -> str:
    """Escape a Prometheus label value and prevent line injection."""

    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def _sample(name: str, labels: tuple[tuple[str, str], ...], value: int) -> str:
    """Render one integer gauge sample with deterministic label ordering."""

    rendered_labels = ",".join(
        f'{key}="{_label(label_value)}"' for key, label_value in labels
    )
    return f"{name}{{{rendered_labels}}} {value}"


def _metric(
    families: dict[str, tuple[str, list[str]]],
    name: str,
    help_text: str,
    labels: tuple[tuple[str, str], ...],
    value: int,
) -> None:
    """Collect one sample under a single consistent gauge-family header."""

    if name not in families:
        families[name] = (help_text, [])
    registered_help, samples = families[name]
    if registered_help != help_text:
        raise ValueError(f"metric family {name} has inconsistent help text")
    samples.append(_sample(name, labels, value))


def render_project_metrics(
    health: ProjectHealthSnapshot,
    usage: ProjectStorageUsage,
    feedback: SDEQualityFeedbackSummary | None = None,
) -> str:
    """Render authorized project metrics; never include text or artifact paths."""

    if health.project_id != usage.project_id:
        raise ValueError("health and usage snapshots must belong to the same project")
    project = (("project_id", health.project_id),)
    families: dict[str, tuple[str, list[str]]] = {}
    for state in OperationalHealth:
        _metric(
            families,
            "curatormd_project_health_state",
            "One-hot operational health state for this project.",
            project + (("state", state.value),),
            int(health.status is state),
        )
    for gate_code in health.gate_codes:
        safe_gate = gate_code if _SAFE_GATE_RE.fullmatch(gate_code) else "other"
        _metric(
            families,
            "curatormd_project_open_gate",
            "Currently observed open health gate; value is always one.",
            project + (("gate", safe_gate),),
            1,
        )

    queue_metrics = (
        ("event_queue_received", health.event_received_count, "Received events."),
        ("event_queue_failed", health.event_failed_count, "Failed events."),
        ("event_queue_quarantined", health.event_quarantined_count, "Quarantined events."),
        ("event_queue_claimed", health.event_claimed_count, "Live claimed events."),
        (
            "event_queue_expired_claims",
            health.event_expired_claim_count,
            "Expired event claims.",
        ),
        (
            "event_queue_oldest_pending_age_seconds",
            health.oldest_pending_event_age_seconds
            if health.oldest_pending_event_age_seconds is not None
            else -1,
            "Oldest pending event age in seconds; -1 means no pending event.",
        ),
        (
            "review_queue_pending",
            health.operational_counts.pending_review_count,
            "Pending SDE human reviews.",
        ),
        (
            "purge_receipts_pending",
            health.operational_counts.pending_purge_receipt_count,
            "Pending purge receipts.",
        ),
        (
            "purge_artifacts_pending",
            health.operational_counts.pending_purge_artifact_count,
            "Pending purge artifact targets.",
        ),
    )
    for suffix, value, help_text in queue_metrics:
        _metric(
            families,
            f"curatormd_{suffix}",
            help_text,
            project,
            value,
        )

    for dependency in health.dependencies:
        _metric(
            families,
            "curatormd_dependency_readiness",
            "One-hot observed readiness for a required host dependency.",
            project + (("dependency", dependency.name), ("state", dependency.status.value)),
            1,
        )
        _metric(
            families,
            "curatormd_dependency_probe_age_seconds",
            "Age of the host dependency observation; -1 means unknown or invalid.",
            project + (("dependency", dependency.name),),
            dependency.age_seconds if dependency.age_seconds is not None else -1,
        )

    for item in usage.goal_statuses:
        _metric(
            families,
            "curatormd_goals",
            "Project goal count by lifecycle status.",
            project + (("status", item.status.value),),
            item.count,
        )

    storage_metrics = (
        ("facts", usage.fact_count, "Active compact facts in this project."),
        ("facts_bytes", usage.fact_record_bytes, "UTF-8 bytes in active project facts."),
        (
            "sde_quality_feedback",
            usage.sde_quality_feedback_count,
            "Explicit SDE reviewer feedback records in this project.",
        ),
        (
            "sde_quality_feedback_bytes",
            usage.sde_quality_feedback_record_bytes,
            "UTF-8 bytes in project SDE reviewer feedback records.",
        ),
        ("fact_count_limit", usage.fact_count_limit, "Configured project fact count limit."),
        (
            "fact_bytes_limit",
            usage.fact_record_bytes_limit,
            "Configured project fact UTF-8 byte limit.",
        ),
        (
            "fact_archive_bytes_remaining",
            usage.fact_archive_bytes_remaining,
            "Remaining project fact archive logical byte capacity.",
        ),
        (
            "logical_record_bytes",
            usage.logical_record_bytes,
            "Project-attributed logical UTF-8 record bytes.",
        ),
        ("event_receipts", usage.event_receipt_count, "Retained project event receipts."),
        (
            "event_payload_bytes_received",
            usage.event_payload_bytes_received,
            "Original event payload bytes received by this project.",
        ),
        (
            "event_payload_bytes_retained",
            usage.event_payload_bytes_retained,
            "Event payload bytes currently retained for this project.",
        ),
        (
            "fact_capacity_reached",
            int(usage.fact_capacity_reached),
            "Whether the project fact-history capacity gate is reached.",
        ),
        (
            "event_capacity_available",
            int(usage.global_event_inbox.can_accept_new_event),
            "Whether the global inbox can accept another event ID.",
        ),
    )
    for suffix, value, help_text in storage_metrics:
        _metric(families, f"curatormd_{suffix}", help_text, project, value)

    if feedback is not None:
        if feedback.project_id != health.project_id:
            raise ValueError("feedback summary must belong to the health project")
        for label, count in feedback.counts:
            _metric(
                families,
                "curatormd_sde_reviewer_feedback_total",
                "Explicit human reviewer labels; not model output or ground truth.",
                project + (("label", label.value),),
                count,
            )

    staging = usage.staging
    staging_metrics = (
        (
            "staging_project_byte_limit",
            usage.staging_project_byte_limit
            if usage.staging_project_byte_limit is not None
            else -1,
            "Configured project staging byte budget; -1 means unset.",
        ),
        (
            "staging_project_file_limit",
            usage.staging_project_file_limit
            if usage.staging_project_file_limit is not None
            else -1,
            "Configured project staging file-count budget; -1 means unset.",
        ),
        (
            "staging_regular_files",
            staging.regular_file_count if staging is not None else -1,
            "Regular files in the bounded project staging scan; -1 means unavailable.",
        ),
        (
            "staging_bytes",
            staging.observed_file_bytes if staging is not None else -1,
            "Bytes in regular files observed by the bounded project staging scan.",
        ),
        (
            "staging_inventory_complete",
            int(staging.inventory_complete) if staging is not None else -1,
            "Complete staging inventory: one true, zero false, -1 unavailable.",
        ),
    )
    for suffix, value, help_text in staging_metrics:
        _metric(families, f"curatormd_{suffix}", help_text, project, value)

    staging_by_class = (
        {item.artifact_class: item for item in staging.classes}
        if staging is not None
        else {}
    )
    for artifact_class in StagingArtifactClass:
        class_usage = staging_by_class.get(artifact_class)
        unavailable = -1 if staging is None else 0
        _metric(
            families,
            "curatormd_staging_class_files",
            "Observed regular staging files by fixed temporary artifact class.",
            project + (("class", artifact_class.value),),
            class_usage.regular_file_count if class_usage is not None else unavailable,
        )
        _metric(
            families,
            "curatormd_staging_class_bytes",
            "Observed staging bytes by fixed temporary artifact class.",
            project + (("class", artifact_class.value),),
            class_usage.observed_file_bytes
            if class_usage is not None
            else unavailable,
        )

    for item in usage.event_classes:
        event_type = (
            item.event_type if item.event_type in _KNOWN_EVENT_TYPES else "other"
        )
        status = item.status if item.status in _KNOWN_EVENT_STATUSES else "other"
        _metric(
            families,
            "curatormd_event_records",
            "Project event receipt count by bounded event type and processing status.",
            project + (("event_type", event_type), ("status", status)),
            item.count,
        )
    for item in usage.event_failures:
        _metric(
            families,
            "curatormd_event_failures",
            "Current failed or quarantined event receipts by fixed failure "
            "category; not lifetime attempts.",
            project + (("category", item.category.value),),
            item.count,
        )
    lines: list[str] = []
    for name, (help_text, samples) in families.items():
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge"))
        lines.extend(samples)
    return "\n".join(lines) + "\n"
