"""Bounded goal read models and compaction proposal records."""

from __future__ import annotations

from dataclasses import dataclass

from .content_safety import validate_safe_text
from .models import (
    MAX_FACT_COMPACTION_BATCH_FACTS,
    MAX_FACT_COMPACTION_SOURCE_BYTES,
    MAX_GOAL_STATUS_CANDIDATES,
    MAX_GOAL_STATUS_PURGE_RECEIPTS,
    AuditReceipt,
    CriterionStatus,
    Fact,
    GoalCard,
    SDECandidate,
    SDEStatus,
    SuccessCriterion,
)
from .record_validation import SHA256_RE as _SHA256_RE
from .validation import is_exact_int


@dataclass(frozen=True, slots=True)
class CriterionProgress:
    """Current verified/open state and proof links for one criterion."""

    criterion_id: str
    description: str
    status: CriterionStatus
    verification_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GoalCriteriaVersion:
    """Immutable snapshot of the original or amended goal contract."""

    revision: int
    criteria: tuple[SuccessCriterion, ...]
    reason: str
    created_at: str

    def __post_init__(self) -> None:
        validate_safe_text(self.reason, "criteria_version.reason")


@dataclass(frozen=True, slots=True)
class FactCapacity:  # pylint: disable=too-many-instance-attributes  # Capacity counters form one bounded read snapshot.
    """Current append budget; reaching it blocks capture without pruning facts."""

    goal_fact_count: int
    goal_fact_bytes: int
    goal_fact_count_limit: int
    goal_fact_bytes_limit: int
    goal_fact_count_remaining: int
    goal_fact_bytes_remaining: int
    project_fact_count: int
    project_fact_bytes: int
    project_fact_count_limit: int
    project_fact_bytes_limit: int
    project_fact_count_remaining: int
    project_fact_bytes_remaining: int
    append_available: bool
    open_gate: str | None = None


@dataclass(frozen=True, slots=True)
class FactCompactionProposal:
    """Exact routine facts proposed for reviewer-approved archival."""

    compaction_id: str
    project_id: str
    goal_id: str
    facts: tuple[Fact, ...]
    source_sha256: str
    source_bytes: int
    estimated_compressed_bytes: int

    def __post_init__(self) -> None:
        if not self.facts or len(self.facts) > MAX_FACT_COMPACTION_BATCH_FACTS:
            raise ValueError("compaction proposal must contain 1-64 facts")
        if len({fact.fact_id for fact in self.facts}) != len(self.facts):
            raise ValueError("compaction proposal fact IDs must be unique")
        if any(fact.goal_id != self.goal_id for fact in self.facts):
            raise ValueError("compaction proposal facts must share its goal")
        if not _SHA256_RE.fullmatch(self.source_sha256):
            raise ValueError("compaction source_sha256 must be lowercase SHA-256")
        if not 1 <= self.source_bytes <= MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ValueError("compaction source exceeds the bounded batch size")
        if not 1 <= self.estimated_compressed_bytes <= MAX_FACT_COMPACTION_SOURCE_BYTES:
            raise ValueError("compaction estimate exceeds the bounded batch size")


@dataclass(frozen=True, slots=True)
class GoalSnapshot:  # pylint: disable=too-many-instance-attributes  # Paginated goal summary fields form one read model.
    """Bounded read model combining a goal with its current ledger state."""

    goal: GoalCard
    facts: tuple[Fact, ...]
    sde_candidates: tuple[SDECandidate, ...]
    pending_purges: tuple[AuditReceipt, ...]
    criteria: tuple[CriterionProgress, ...] = ()
    criteria_history: tuple[GoalCriteriaVersion, ...] = ()
    fact_capacity: FactCapacity | None = None
    sde_candidate_total: int | None = None
    sde_candidate_offset: int = 0
    sde_candidate_next_offset: int | None = None
    sde_candidate_status_counts: tuple[tuple[str, int], ...] = ()
    pending_purge_total: int | None = None
    pending_purge_offset: int = 0
    pending_purge_next_offset: int | None = None

    def __post_init__(self) -> None:
        """Keep status detail pages bounded and pagination metadata consistent."""

        if len(self.sde_candidates) > MAX_GOAL_STATUS_CANDIDATES:
            raise ValueError("goal status contains too many SDE candidates")
        if len(self.pending_purges) > MAX_GOAL_STATUS_PURGE_RECEIPTS:
            raise ValueError("goal status contains too many pending purge receipts")
        for label, total, offset, records, next_offset in (
            (
                "SDE candidate",
                self.sde_candidate_total,
                self.sde_candidate_offset,
                self.sde_candidates,
                self.sde_candidate_next_offset,
            ),
            (
                "pending purge",
                self.pending_purge_total,
                self.pending_purge_offset,
                self.pending_purges,
                self.pending_purge_next_offset,
            ),
        ):
            if total is None:
                if next_offset is not None:
                    raise ValueError(f"{label} next offset requires a total")
                continue
            if not is_exact_int(total) or total < 0:
                raise ValueError(f"{label} total must be a non-negative integer")
            if not is_exact_int(offset) or offset < 0:
                raise ValueError(f"{label} offset must be a non-negative integer")
            expected_next = offset + len(records) if offset + len(records) < total else None
            if next_offset != expected_next:
                raise ValueError(f"{label} next offset does not match its page")
        valid_sde_states = {status.value for status in SDEStatus}
        if any(
            status not in valid_sde_states
            or not is_exact_int(count)
            or count < 0
            for status, count in self.sde_candidate_status_counts
        ):
            raise ValueError(
                "SDE status counts must contain known states and non-negative counts"
            )
