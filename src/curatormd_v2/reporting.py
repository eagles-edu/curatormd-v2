"""Bounded, user-readable goal reports built only from stored ledger records."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    AuditReceipt,
    CriterionProgress,
    CriterionStatus,
    Fact,
    FactCapacity,
    FactKind,
    GoalBullet,
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


def open_child_goals(children: tuple[GoalCard, ...]) -> tuple[GoalCard, ...]:
    """Select child goals that still require lifecycle work."""

    return tuple(
        child
        for child in children
        if child.status
        not in {GoalStatus.COMPLETE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED}
    )


def goal_bullet_projection(snapshot: GoalSnapshot) -> GoalBulletProjection:
    """Build a truth-labeled projection from one already-read goal snapshot."""

    verified_fact_ids = {
        fact_id
        for criterion in snapshot.criteria
        if criterion.status is CriterionStatus.VERIFIED
        for fact_id in criterion.verification_fact_ids
    }
    bullets: list[GoalBullet] = [
        GoalBullet(GoalBulletCategory.PROBLEM, snapshot.goal.problem)
    ]
    bullets.extend(_criterion_bullets(snapshot.criteria))
    bullets.extend(_fact_bullet(fact, verified_fact_ids) for fact in snapshot.facts)
    bullets.extend(_goal_state_bullets(snapshot.goal))
    bullets.extend(_pending_review_bullets(snapshot))
    bullets.extend(_pending_purge_bullets(snapshot))
    if snapshot.fact_capacity is not None:
        bullets.extend(_fact_capacity_bullets(snapshot.fact_capacity))
    if snapshot.goal.next_action:
        bullets.append(
            GoalBullet(GoalBulletCategory.NEXT, snapshot.goal.next_action)
        )
    return GoalBulletProjection(
        goal_id=snapshot.goal.goal_id,
        problem=snapshot.goal.problem,
        status=snapshot.goal.status,
        criteria=snapshot.criteria,
        bullets=tuple(bullets),
        next_action=snapshot.goal.next_action,
    )


def _criterion_bullets(criteria: tuple[CriterionProgress, ...]) -> list[GoalBullet]:
    bullets: list[GoalBullet] = []
    for criterion in criteria:
        bullets.append(
            GoalBullet(
                GoalBulletCategory.CRITERION,
                f"{criterion.criterion_id}: {criterion.status.value} — "
                f"{criterion.description}",
                criterion_id=criterion.criterion_id,
            )
        )
        if criterion.status is CriterionStatus.OPEN:
            bullets.append(
                GoalBullet(
                    GoalBulletCategory.OPEN,
                    "Required criterion remains unverified: "
                    f"{criterion.criterion_id} — {criterion.description}",
                    criterion_id=criterion.criterion_id,
                )
            )
    return bullets


def _fact_bullet(fact: Fact, verified_fact_ids: set[str]) -> GoalBullet:
    text = f"{fact.kind.value.replace('_', ' ').capitalize()}: {fact.bullet}"
    if fact.kind is FactKind.OPEN_GATE:
        category = GoalBulletCategory.RECORDED
        text = f"Prior gate fact: {fact.bullet}"
    elif fact.kind is FactKind.OUTCOME:
        category = GoalBulletCategory.RECORDED
        text = f"Outcome: {fact.bullet}"
    elif fact.kind is FactKind.COMPLETION_CLAIM:
        category = GoalBulletCategory.UNVERIFIED
    elif fact.kind is FactKind.VERIFICATION:
        category = (
            GoalBulletCategory.VERIFIED
            if fact.fact_id in verified_fact_ids
            else GoalBulletCategory.UNVERIFIED
        )
    else:
        category = GoalBulletCategory.RECORDED
    return GoalBullet(
        category,
        text,
        fact_id=fact.fact_id,
        criterion_id=fact.criterion_id,
        evidence=fact.evidence,
    )


def _goal_state_bullets(goal: GoalCard) -> list[GoalBullet]:
    if goal.status not in (
        GoalStatus.OPEN,
        GoalStatus.BLOCKED,
        GoalStatus.DEFERRED,
    ):
        return []
    status_gate = goal.status.value
    if goal.next_action:
        status_gate += f"; next action: {goal.next_action}"
    return [GoalBullet(GoalBulletCategory.OPEN, status_gate)]


def _pending_review_bullets(snapshot: GoalSnapshot) -> list[GoalBullet]:
    bullets = [
        GoalBullet(
            GoalBulletCategory.OPEN,
            f"SDE candidate {candidate.candidate_id} awaits human review",
        )
        for candidate in snapshot.sde_candidates
        if candidate.status is SDEStatus.PENDING_REVIEW
    ]
    pending_total = sum(
        count
        for status, count in snapshot.sde_candidate_status_counts
        if status == SDEStatus.PENDING_REVIEW.value
    )
    if pending_total > len(bullets):
        continuation = (
            f"; next page: goal_status(sde_offset={snapshot.sde_candidate_next_offset})"
            if snapshot.sde_candidate_next_offset is not None
            else ""
        )
        bullets.append(
            GoalBullet(
                GoalBulletCategory.OPEN,
                f"{pending_total} SDE candidate(s) await review overall; "
                f"this page shows {len(bullets)}{continuation}",
            )
        )
    return bullets


def _pending_purge_bullets(snapshot: GoalSnapshot) -> list[GoalBullet]:
    bullets = [
        GoalBullet(
            GoalBulletCategory.OPEN,
            f"Purge receipt {receipt.receipt_id} remains pending",
        )
        for receipt in snapshot.pending_purges
    ]
    if (
        snapshot.pending_purge_total is not None
        and snapshot.pending_purge_total > len(snapshot.pending_purges)
    ):
        continuation = (
            f"; next page: goal_status(purge_offset={snapshot.pending_purge_next_offset})"
            if snapshot.pending_purge_next_offset is not None
            else ""
        )
        bullets.append(
            GoalBullet(
                GoalBulletCategory.OPEN,
                f"{snapshot.pending_purge_total} purge receipt(s) remain pending; "
                f"this page shows {len(snapshot.pending_purges)}{continuation}",
            )
        )
    return bullets


def _fact_capacity_bullets(capacity: FactCapacity) -> list[GoalBullet]:
    if capacity.append_available:
        return []
    return [
        GoalBullet(
            GoalBulletCategory.OPEN,
            capacity.open_gate
            or "Fact capacity reached; new facts are not being accepted",
        )
    ]


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


@dataclass(frozen=True, slots=True)
class GoalReportData:
    """Bounded ledger pages consumed by one status renderer."""

    snapshot: GoalSnapshot
    projection: GoalBulletProjection
    children: tuple[GoalCard, ...]
    dependencies: tuple[GoalCard, ...]
    receipts: tuple[AuditReceipt, ...]


@dataclass(frozen=True, slots=True)
class GoalReportPage:
    """Independent offsets for the report's bounded detail sections."""

    fact_offset: int = 0
    fact_limit: int = MAX_GOAL_REPORT_FACTS
    child_offset: int = 0
    sde_offset: int = 0
    receipt_offset: int = 0


def _inline(value: str, limit: int = 2000) -> str:
    """Keep user text on one Markdown line and escape inline syntax."""

    compact = " ".join(value.splitlines())[:limit]
    for marker in ("\\", "`", "*", "_", "[", "]", "<", ">", "|"):
        compact = compact.replace(marker, f"\\{marker}")
    return compact


def _criterion_lines(
    snapshot: GoalSnapshot, intake: GoalReportContext | None
) -> list[str]:
    """Render each criterion with its proof or explicit open-gate context."""

    goal = snapshot.goal
    criterion_open_gates = {
        fact.criterion_id: fact.bullet
        for fact in snapshot.facts
        if fact.kind is FactKind.OPEN_GATE and fact.criterion_id is not None
    }
    lines: list[str] = []
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
        status_line = (
            f"- [{marker}] `{_inline(criterion.criterion_id, 128)}` — "
            f"{criterion.status.value}: {_inline(criterion.description)}{proof}"
        )
        if criterion.status.value != "verified":
            blocker = criterion_open_gates.get(
                criterion.criterion_id,
                "No current passing verification fact is linked to this criterion",
            )
            owner = (
                _inline(intake.owner or "unassigned", 128)
                if intake is not None
                else "unassigned"
            )
            goal_next_action = (
                _inline(goal.next_action, 500)
                if goal.next_action is not None
                else "not recorded"
            )
            suggested_action = (
                "Verify criterion `"
                f"{_inline(criterion.criterion_id, 128)}` against its stated acceptance condition"
            )
            status_line += (
                f"; blocker: {_inline(blocker, 500)}; owner: {owner}; "
                f"suggested next action: {suggested_action}; "
                f"goal next action: {goal_next_action}"
            )
        lines.append(status_line)
    return lines


def _fact_item_line(fact: Fact) -> str:
    """Render one compact fact without its private evidence locator or digest."""

    criterion_id = fact.criterion_id
    evidence = fact.evidence
    source_event_id = fact.source_event_id
    bullet = fact.bullet
    kind = fact.kind
    criterion = (
        f"; criterion `{_inline(criterion_id, 128)}`" if criterion_id else ""
    )
    evidence_count = (
        f"; {len(evidence)} evidence reference(s)" if evidence else ""
    )
    source = (
        f"; source event `{_inline(source_event_id, 128)}`"
        if source_event_id is not None
        else ""
    )
    label = (
        f"Outcome: {_inline(bullet, 1000)}"
        if kind is FactKind.OUTCOME
        else f"{kind.value.replace('_', ' ')}: {_inline(bullet, 1000)}"
    )
    return (
        f"- `{_inline(fact.fact_id, 256)}` — {label}"
        f"{criterion}{evidence_count}{source}"
    )


def _fact_lines(
    data: GoalReportData, page: GoalReportPage
) -> list[str]:
    """Render one bounded fact page without exposing full evidence locators."""

    fact_categories = {
        bullet.fact_id: bullet.category
        for bullet in data.projection.bullets
        if bullet.fact_id is not None
    }
    selected_facts = data.snapshot.facts[
        page.fact_offset : page.fact_offset + page.fact_limit
    ]
    page_end = page.fact_offset + len(selected_facts)
    lines = [
        "",
        "## Facts to date (showing "
        f"{page.fact_offset + 1 if selected_facts else 0}–{page_end} "
        f"of {len(data.snapshot.facts)})",
    ]
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
        lines.extend(_fact_item_line(fact) for fact in matches)
    if page_end < len(data.snapshot.facts):
        lines.append(
            f"- More facts available: request `fact_offset={page_end}`; "
            "full evidence locators and hashes are available from `goal_status`."
        )
    elif selected_facts:
        lines.append("- Full evidence locators and hashes are available from `goal_status`.")
    return lines


def _status_todos(snapshot: GoalSnapshot) -> list[str]:
    """Return TODOs implied directly by this goal's own lifecycle state."""

    goal = snapshot.goal
    todos = [
        f"Verify criterion `{_inline(item.criterion_id, 128)}`: "
        f"{_inline(item.description)}"
        for item in snapshot.criteria
        if item.status.value != "verified"
    ]
    if goal.status in {GoalStatus.PLANNED, GoalStatus.ACTIVE} and goal.next_action is None:
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
    return todos


def _dependency_todos(
    children: tuple[GoalCard, ...],
    dependencies: tuple[GoalCard, ...],
    summary: GoalReportSummary | None,
    child_offset: int,
) -> list[str]:
    """Return open child/dependency TODOs from bounded related-goal pages."""

    open_children = open_child_goals(children)
    todos = [
        f"Resolve child goal `{_inline(child.goal_id, 256)}` "
        f"(currently `{child.status.value}`)"
        for child in open_children
    ]
    if summary is not None and summary.open_child_total:
        todos.append(
            f"{summary.open_child_total} child goal(s) remain open overall; "
            f"request `child_offset={child_offset}` to inspect this page."
        )
    todos.extend(
        f"Resolve dependency `{_inline(item.goal_id, 256)}` "
        f"(currently `{item.status.value}`)"
        for item in dependencies
        if item.status is not GoalStatus.COMPLETE
    )
    return todos


def _review_cleanup_todos(
    snapshot: GoalSnapshot,
    receipts: tuple[AuditReceipt, ...],
    summary: GoalReportSummary | None,
    sde_offset: int,
) -> list[str]:
    """Return review and purge TODOs from bounded SDE/receipt details."""

    pending = tuple(
        candidate
        for candidate in snapshot.sde_candidates
        if candidate.status is SDEStatus.PENDING_REVIEW
    )
    todos = [
        f"Review SDE candidate `{_inline(candidate.candidate_id, 256)}`"
        for candidate in pending[:MAX_GOAL_REPORT_SDE_CANDIDATES]
    ]
    pending_total = summary.pending_sde_total if summary is not None else len(pending)
    if pending_total > sde_offset + len(pending):
        todos.append(
            f"Review {pending_total - sde_offset - len(pending)} "
            "additional pending SDE candidate(s); "
            f"request `sde_offset={sde_offset + len(pending)}`."
        )
    todos.extend(
        f"Resolve purge receipt `{_inline(receipt.receipt_id, 256)}` "
        f"(inventory complete: {str(receipt.artifact_inventory_complete).lower()}, "
        f"canonical write verified: {str(receipt.canonical_persisted).lower()})"
        for receipt in receipts
        if receipt.purge_status is PurgeStatus.PURGE_PENDING
    )
    if summary is not None:
        remaining = max(0, summary.pending_receipt_total - len(snapshot.pending_purges))
        if remaining:
            todos.append(
                f"Resolve {remaining} additional purge-pending receipt(s); "
                "review the purge queue for this project."
            )
    return todos


def _todo_lines(
    data: GoalReportData,
    summary: GoalReportSummary | None,
    page: GoalReportPage,
) -> list[str]:
    """Build honest current TODOs from bounded goal, review, and purge state."""

    snapshot = data.snapshot
    todos = _status_todos(snapshot)
    todos.extend(
        _dependency_todos(data.children, data.dependencies, summary, page.child_offset)
    )
    todos.extend(
        _review_cleanup_todos(snapshot, data.receipts, summary, page.sde_offset)
    )
    if snapshot.fact_capacity is not None and not snapshot.fact_capacity.append_available:
        todos.append(snapshot.fact_capacity.open_gate or "Resolve the fact-history capacity gate")
    return todos


def _child_lines(
    children: tuple[GoalCard, ...], summary: GoalReportSummary | None, child_offset: int
) -> list[str]:
    """Render one bounded child-goal page and its remaining count."""

    lines = ["", "## Child tasks"]
    if not children:
        lines.append("- None.")
    else:
        lines.extend(
            f"- `{_inline(child.goal_id, 256)}` — `{child.status.value}`"
            for child in children[:MAX_GOAL_REPORT_CHILDREN]
        )
    total = summary.child_total if summary is not None else len(children)
    if child_offset + len(children) < total:
        lines.append(
            f"- {total - child_offset - len(children)} additional child goal(s) "
            f"omitted; request `child_offset={child_offset + len(children)}`."
        )
    return lines


def _dependency_lines(dependencies: tuple[GoalCard, ...]) -> list[str]:
    """Render dependencies without inventing state for omitted pages."""

    lines = ["", "## Dependencies"]
    if not dependencies:
        lines.append("- None.")
    else:
        lines.extend(
            f"- `{_inline(item.goal_id, 256)}` — `{item.status.value}`"
            for item in dependencies
        )
    return lines


def _sde_lines(
    snapshot: GoalSnapshot, summary: GoalReportSummary | None
) -> list[str]:
    """Render aggregate SDE states without exposing unselected candidate data."""

    lines = ["", "## SDE review"]
    if summary is not None and summary.sde_status_counts:
        lines.extend(
            f"- `{status}`: {count} candidate(s)"
            for status, count in summary.sde_status_counts
        )
    elif not snapshot.sde_candidates:
        lines.append("- No SDE candidates.")
    else:
        counts: dict[str, int] = {}
        for candidate in snapshot.sde_candidates:
            status = candidate.status.value
            counts[status] = counts.get(status, 0) + 1
        lines.extend(
            f"- `{status}`: {count} candidate(s)"
            for status, count in sorted(counts.items())
        )
    return lines


def _cleanup_lines(
    receipts: tuple[AuditReceipt, ...],
    summary: GoalReportSummary | None,
    receipt_offset: int,
) -> list[str]:
    """Render bounded canonical-write/purge receipts and exact remaining totals."""

    lines = ["", "## Canonical write and artifact cleanup"]
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
    return lines


def _goal_header_lines(
    goal: GoalCard, intake: GoalReportContext | None
) -> list[str]:
    """Render the compact goal and intake header."""

    return [
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
        (
            f"- Checklist item (captured): {_inline(goal.checklist_source_text, 4000)}"
            if goal.checklist_source_text is not None
            else "- Checklist item: not recorded"
        ),
        "",
        "## Success criteria",
    ]


def _open_gate_lines(projection: GoalBulletProjection) -> list[str]:
    """Render only explicitly recorded open-gate bullets."""

    gates = tuple(
        bullet.text
        for bullet in projection.bullets
        if bullet.category is GoalBulletCategory.OPEN
    )
    lines = ["", "## Current open gates"]
    if gates:
        lines.extend(f"- {_inline(gate)}" for gate in gates)
    else:
        lines.append("- None recorded.")
    return lines


def _validate_page(page: GoalReportPage) -> None:
    """Reject malformed offsets and an overlarge fact page before rendering."""

    if not is_exact_int(page.fact_offset) or page.fact_offset < 0:
        raise ValueError("fact_offset must be a non-negative integer")
    if not is_exact_int(page.fact_limit) or not 1 <= page.fact_limit <= MAX_GOAL_REPORT_FACTS:
        raise ValueError(f"fact_limit must be between 1 and {MAX_GOAL_REPORT_FACTS}")
    for name, value in (
        ("child_offset", page.child_offset),
        ("sde_offset", page.sde_offset),
        ("receipt_offset", page.receipt_offset),
    ):
        if not is_exact_int(value) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")


def render_goal_report(
    data: GoalReportData,
    *,
    intake: GoalReportContext | None = None,
    summary: GoalReportSummary | None = None,
    page: GoalReportPage | None = None,
) -> str:
    """Render a concise status-and-bullets report without inventing evidence."""

    selected_page = page or GoalReportPage()
    _validate_page(selected_page)
    lines = _goal_header_lines(data.snapshot.goal, intake)
    lines.extend(_criterion_lines(data.snapshot, intake))
    lines.extend(_fact_lines(data, selected_page))
    lines.extend(_open_gate_lines(data.projection))

    lines.extend(["", "## Open TODOs"])
    todos = _todo_lines(data, summary, selected_page)
    if not todos:
        lines.append("- None recorded for this goal.")
    else:
        lines.extend(f"- {todo}" for todo in todos)

    lines.extend(_child_lines(data.children, summary, selected_page.child_offset))
    lines.extend(_dependency_lines(data.dependencies))
    lines.extend(_sde_lines(data.snapshot, summary))
    lines.extend(_cleanup_lines(data.receipts, summary, selected_page.receipt_offset))
    return "\n".join(lines)
