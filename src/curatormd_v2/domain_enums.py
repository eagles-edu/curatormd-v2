"""Persisted lifecycle and status enums shared across V2 domain records."""

from __future__ import annotations

from enum import StrEnum


class GoalStatus(StrEnum):
    """Persisted lifecycle states for a goal and its open work."""

    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETE = "complete"
    OPEN = "open"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class CriterionStatus(StrEnum):
    """Verification state of one success criterion."""

    VERIFIED = "verified"
    OPEN = "open"


class GoalBulletCategory(StrEnum):
    """Truth labels for the compact user-facing goal projection."""

    PROBLEM = "problem"
    CRITERION = "criterion"
    RECORDED = "recorded_fact"
    VERIFIED = "verified_fact"
    UNVERIFIED = "unverified_claim"
    OPEN = "open_gate"
    NEXT = "next_action"


class FactKind(StrEnum):
    """Typed development facts that may be appended to a goal ledger."""

    INTENT = "intent"
    RESEARCH = "research"
    ADVICE = "advice"
    PROPOSAL = "proposal"
    CHANGE = "change"
    VERIFICATION = "verification"
    OPEN_GATE = "open_gate"
    COMPLETION_CLAIM = "completion_claim"
    OUTCOME = "outcome"
    REOPENED = "reopened"
    CRITERIA_AMENDED = "criteria_amended"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class EvidenceOutcome(StrEnum):
    """Observed result attached to a bounded evidence reference."""

    PASSED = "passed"
    FAILED = "failed"
    OBSERVED = "observed"


class Materiality(StrEnum):
    """Reason category used to assess significant development events."""

    IMPLEMENTATION = "implementation"
    DECISION = "decision"
    RECOVERY = "recovery"
    VERIFIED_LESSON = "verified_lesson"
    ROUTINE = "routine"


class SDEStatus(StrEnum):
    """Review state of a significant development event candidate."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    """Human disposition recorded for an SDE candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


class SDEQualityFeedbackLabel(StrEnum):
    """Explicit human QA labels; they are not inferred or model predictions."""

    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    INACCURATE = "inaccurate"
    DUPLICATE = "duplicate"


class PurgeStatus(StrEnum):
    """Overall purge state attached to an auditable review receipt."""

    PURGE_PENDING = "purge_pending"
    COMPLETE = "complete"


class OperationalHealth(StrEnum):
    """Conservative aggregate state for one project's observed operations."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ArtifactStatus(StrEnum):
    """Purge state of one inventoried transient artifact."""

    PENDING = "pending"
    PURGED = "purged"
    FAILED = "failed"
    HELD = "held"


class PurgeOutcome(StrEnum):
    """Observed result of one artifact cleanup target."""

    DELETED = "deleted"
    ALREADY_ABSENT = "already_absent"
    HELD = "held"
    CHANGED = "changed"
    FAILED = "failed"


class PurgeFailureCode(StrEnum):
    """Content-free reasons for retryable artifact purge failures."""

    RETENTION_HOLD = "retention_hold"
    INVALID_PATH = "invalid_path"
    OUTSIDE_STAGING_ROOT = "outside_staging_root"
    STAGING_ROOT = "staging_root"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    NOT_REGULAR_FILE = "not_regular_file"
    ARTIFACT_CHANGED = "artifact_changed"
    HASH_MISMATCH = "hash_mismatch"
    PATH_CHANGED = "path_changed"
    FILESYSTEM_ERROR = "filesystem_error"
    INVALID_ARTIFACT = "invalid_artifact"
    LEGACY_FAILURE_DETAIL_REDACTED = "legacy_failure_detail_redacted"


class RetentionHoldKind(StrEnum):
    """Reason class for an explicit, reviewer-visible artifact retention hold."""

    LEGAL = "legal"
    OPERATIONAL = "operational"


class ReacquisitionAction(StrEnum):
    """Reviewer decision for an artifact that may be removed after review."""

    NOT_RECORDED = "not_recorded"
    NOT_REQUIRED = "not_required"
    REACQUIRE_FROM_SOURCE = "reacquire_from_source"
    RETAIN_UNDER_HOLD = "retain_under_hold"
