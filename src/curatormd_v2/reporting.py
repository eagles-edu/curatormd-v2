"""Bounded, user-readable goal reports built only from stored ledger records."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AuditReceipt,
    GoalBulletCategory,
    GoalBulletProjection,
    GoalCard,
    GoalSnapshot,
    GoalStatus,
    PurgeStatus,
    SDEStatus,
)
from .validation import is_exact_int


MAX_GOAL_REPORT_FACTS = 16
MAX_GOAL_REPORT_CHILDREN = 32
MAX_GOAL_REPORT_RECEIPTS = 16
MAX_GOAL_REPORT_SDE_CANDIDATES = 16


@dataclass(frozen=True, slots=True)
class GoalReportContext:
    """Compact persisted intake metadata; never contains raw source payloads."""

    project_id: str
    owner: str | None
    checklist_id: str | None
    checklist_version: str | None
    initial_status: GoalStatus | None
    source_event_id: str | None


@dataclass(frozen=True, slots=True)
class GoalReportSummary:
    """Exact SQL aggregates accompanying bounded detail pages."""

    child_total: int
    open_child_total: int
    sde_status_counts: tuple[tuple[str, int], ...]
    pending_sde_total: int
    receipt_total: int
    pending_receipt_total: int
    purge_status_counts: tuple[tuple[str, int], ...]


def _inline(value: str, limit: int = 2000) -> str:
    """Keep user text on one Markdown line and escape inline syntax."""

    compact = " ".join(value.splitlines())[:limit]
    for marker in ("\\", "`", "*", "_", "[", "]", "<", ">", "|"):
        compact = compact.replace(marker, f"\\{marker}")
    return compact


def render_goal_report(
    snapshot: GoalSnapshot,
    projection: GoalBulletProjection,
    children: tuple[GoalCard, ...],
    dependencies: tuple[GoalCard, ...],
    receipts: tuple[AuditReceipt, ...],
    *,
    intake: GoalReportContext | None = None,
    summary: GoalReportSummary | None = None,
    fact_offset: int = 0,
    fact_limit: int = MAX_GOAL_REPORT_FACTS,
    child_offset: int = 0,
    sde_offset: int = 0,
    receipt_offset: int = 0,
) -> str:
    """Render a concise status-and-bullets report without inventing evidence."""

    if not is_exact_int(fact_offset) or fact_offset < 0:
        raise ValueError("fact_offset must be a non-negative integer")
    if not is_exact_int(fact_limit) or not 1 <= fact_limit <= MAX_GOAL_REPORT_FACTS:
        raise ValueError(f"fact_limit must be between 1 and {MAX_GOAL_REPORT_FACTS}")
    for name, value in (
        ("child_offset", child_offset),
        ("sde_offset", sde_offset),
        ("receipt_offset", receipt_offset),
    ):
        if not is_exact_int(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    goal = snapshot.goal
    fact_categories = {
        bullet.fact_id: bullet.category
        for bullet in projection.bullets
        if bullet.fact_id is not None
    }
    selected_facts = snapshot.facts[fact_offset : fact_offset + fact_limit]
    page_end = fact_offset + len(selected_facts)
    lines = [
        f"# Goal `{_inline(goal.goal_id, 256)}`",
        f"- Outcome: `{goal.status.value}` (lifecycle revision `{goal.lifecycle_revision}`)",
        f"- Problem: {_inline(goal.problem)}",
        (
            f"- Next action: {_inline(goal.next_action)}"
            if goal.next_action is not None
            else (
                "- Next action: none (goal is terminal)."
                if goal.status
                in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
                else "- Next action: not recorded; add a concrete next action."
            )
        ),
        "",
        "## Intake",
        f"- Project: `{_inline(intake.project_id if intake else goal.project_id, 128)}`",
        f"- Owner: {_inline(intake.owner or 'unassigned', 256) if intake else 'not recorded'}",
        (
            f"- Initial state: `{intake.initial_status.value}`"
            if intake is not None and intake.initial_status is not None
            else "- Initial state: not recorded (legacy goal)"
        ),
        (
            f"- Source event: `{_inline(intake.source_event_id, 256)}`"
            if intake is not None and intake.source_event_id is not None
            else "- Source event: not recorded"
        ),
        (
            f"- Checklist: `{_inline(intake.checklist_id, 128)}`"
            + (
                f" (revision `{intake.checklist_version[7:19]}`)"
                if intake.checklist_version is not None
                else ""
            )
            if intake is not None and intake.checklist_id is not None
            else "- Checklist: none"
        ),
        "",
        "## Success criteria",
    ]
    for criterion in snapshot.criteria:
        marker = "x" if criterion.status.value == "verified" else " "
        proof = (
            "; proof facts: "
            + ", ".join(
                f"`{_inline(item, 256)}`" for item in criterion.verification_fact_ids
            )
            if criterion.verification_fact_ids
            else ""
        )
        lines.append(
            f"- [{marker}] `{_inline(criterion.criterion_id, 128)}` — "
            f"{criterion.status.value}: {_inline(criterion.description)}{proof}"
        )

    lines.extend(
        [
            "",
            "## Facts to date (showing "
            f"{fact_offset + 1 if selected_facts else 0}–{page_end} "
            f"of {len(snapshot.facts)})",
        ]
    )
    if not selected_facts:
        lines.append("- No facts recorded.")
    grouped = (
        (GoalBulletCategory.VERIFIED, "Verified facts"),
        (GoalBulletCategory.RECORDED, "Recorded facts"),
        (GoalBulletCategory.UNVERIFIED, "Unverified claims or checks"),
    )
    for category, heading in grouped:
        matches = tuple(
            fact
            for fact in selected_facts
            if fact_categories.get(fact.fact_id) is category
        )
        if not matches:
            continue
        lines.append(f"### {heading}")
        for fact in matches:
            criterion = (
                f"; criterion `{_inline(fact.criterion_id, 128)}`"
                if fact.criterion_id
                else ""
            )
            evidence = (
                f"; {len(fact.evidence)} evidence reference(s)"
                if fact.evidence
                else ""
            )
            lines.append(
                f"- `{_inline(fact.fact_id, 256)}` — "
                f"{fact.kind.value.replace('_', ' ')}: {_inline(fact.bullet, 1000)}"
                f"{criterion}{evidence}"
            )
    if page_end < len(snapshot.facts):
        lines.append(
            f"- More facts available: request `fact_offset={page_end}`; "
            "full evidence locators and hashes are available from `goal_status`."
        )
    elif selected_facts:
        lines.append("- Full evidence locators and hashes are available from `goal_status`.")

    lines.extend(["", "## Open TODOs"])
    todos: list[str] = []
    for criterion in snapshot.criteria:
        if criterion.status.value != "verified":
            todos.append(
                f"Verify criterion `{_inline(criterion.criterion_id, 128)}`: "
                f"{_inline(criterion.description)}"
            )
    if (
        goal.status in {GoalStatus.PLANNED, GoalStatus.ACTIVE}
        and goal.next_action is None
    ):
        todos.append("Record a concrete next action for this goal")
    if goal.status in {GoalStatus.OPEN, GoalStatus.BLOCKED, GoalStatus.DEFERRED}:
        todos.append(
            f"{goal.status.value.capitalize()} goal next action: "
            f"{_inline(goal.next_action or 'record a concrete next action')}"
        )
    elif goal.status in {GoalStatus.PLANNED, GoalStatus.ACTIVE} and all(
        item.status.value == "verified" for item in snapshot.criteria
    ):
        todos.append(
            "Submit an evidence-backed finish evaluation using "
            f"lifecycle revision `{goal.lifecycle_revision}`"
        )
    open_children = tuple(
        child
        for child in children
        if child.status
        not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
    )
    for child in open_children:
        todos.append(
            f"Resolve child goal `{_inline(child.goal_id, 256)}` "
            f"(currently `{child.status.value}`)"
        )
    if summary is not None:
        if summary.open_child_total:
            todos.append(
                f"{summary.open_child_total} child goal(s) remain open overall; "
                f"request `child_offset={child_offset}` to inspect this page."
            )
    for dependency in dependencies:
        if dependency.status is not GoalStatus.COMPLETE:
            todos.append(
                f"Resolve dependency `{_inline(dependency.goal_id, 256)}` "
                f"(currently `{dependency.status.value}`)"
            )
    pending_candidates = tuple(
        candidate
        for candidate in snapshot.sde_candidates
        if candidate.status is SDEStatus.PENDING_REVIEW
    )
    for candidate in pending_candidates[:MAX_GOAL_REPORT_SDE_CANDIDATES]:
        todos.append(f"Review SDE candidate `{_inline(candidate.candidate_id, 256)}`")
    pending_candidate_total = (
        summary.pending_sde_total if summary is not None else len(pending_candidates)
    )
    if pending_candidate_total > sde_offset + len(pending_candidates):
        todos.append(
            f"Review {pending_candidate_total - sde_offset - len(pending_candidates)} "
            "additional pending SDE candidate(s); "
            f"request `sde_offset={sde_offset + len(pending_candidates)}`."
        )
    for receipt in receipts:
        if receipt.purge_status is PurgeStatus.PURGE_PENDING:
            todos.append(
                f"Resolve purge receipt `{_inline(receipt.receipt_id, 256)}` "
                f"(inventory complete: {str(receipt.artifact_inventory_complete).lower()}, "
                f"canonical write verified: {str(receipt.canonical_persisted).lower()})"
            )
    if summary is not None:
        remaining_pending_receipts = max(
            0, summary.pending_receipt_total - len(snapshot.pending_purges)
        )
        if remaining_pending_receipts:
            todos.append(
                f"Resolve {remaining_pending_receipts} additional purge-pending receipt(s); "
                "review the purge queue for this project."
            )
    if snapshot.fact_capacity is not None and not snapshot.fact_capacity.append_available:
        todos.append(snapshot.fact_capacity.open_gate or "Resolve the fact-history capacity gate")
    if not todos:
        lines.append("- None recorded for this goal.")
    else:
        lines.extend(f"- {todo}" for todo in todos)

    lines.extend(["", "## Child tasks"])
    if not children:
        lines.append("- None.")
    else:
        for child in children[:MAX_GOAL_REPORT_CHILDREN]:
            lines.append(
                f"- `{_inline(child.goal_id, 256)}` — `{child.status.value}`"
            )
    child_total = summary.child_total if summary is not None else len(children)
    if child_offset + len(children) < child_total:
        lines.append(
            f"- {child_total - child_offset - len(children)} additional child goal(s) "
            f"omitted; request `child_offset={child_offset + len(children)}`."
        )

    lines.extend(["", "## Dependencies"])
    if not dependencies:
        lines.append("- None.")
    else:
        lines.extend(
            f"- `{_inline(item.goal_id, 256)}` — `{item.status.value}`"
            for item in dependencies
        )

    lines.extend(["", "## SDE review"])
    if summary is not None and summary.sde_status_counts:
        lines.extend(
            f"- `{status}`: {count} candidate(s)"
            for status, count in summary.sde_status_counts
        )
    elif not snapshot.sde_candidates:
        lines.append("- No SDE candidates.")
    else:
        status_counts: dict[str, int] = {}
        for candidate in snapshot.sde_candidates:
            status_counts[candidate.status.value] = status_counts.get(candidate.status.value, 0) + 1
        lines.extend(
            f"- `{status}`: {count} candidate(s)"
            for status, count in sorted(status_counts.items())
        )

    lines.extend(["", "## Canonical write and artifact cleanup"])
    if not receipts:
        lines.append("- No SDE decision receipts.")
    else:
        for receipt in receipts[:MAX_GOAL_REPORT_RECEIPTS]:
            canonical = (
                f"verified at `{_inline(receipt.canonical_target or '', 256)}` "
                f"(sha256 `{(receipt.canonical_sha256 or '')[:12]}`)"
                if receipt.canonical_persisted
                else "not verified"
            )
            lines.append(
                f"- Receipt `{_inline(receipt.receipt_id, 256)}`: "
                f"decision `{receipt.decision.value}`; inventory complete "
                f"`{str(receipt.artifact_inventory_complete).lower()}`; "
                f"canonical write {canonical}; purge `{receipt.purge_status.value}`"
            )
    receipt_total = summary.receipt_total if summary is not None else len(receipts)
    if receipt_offset + len(receipts) < receipt_total:
        lines.append(
            f"- {receipt_total - receipt_offset - len(receipts)} additional receipt(s) "
            f"omitted; request `receipt_offset={receipt_offset + len(receipts)}`."
        )
    if summary is not None and summary.purge_status_counts:
        lines.extend(
            f"- Purge `{status}`: {count} receipt(s)"
            for status, count in summary.purge_status_counts
        )

    return "\n".join(lines)
