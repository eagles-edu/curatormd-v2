"""Build bounded goal reports, archives, and list pages."""

from __future__ import annotations

from dataclasses import replace

__all__ = (
    "_GoalReadMixin",
)

from .models import (
    FactArchiveReceipt,
    FactCompactionProposal,
    GoalBulletProjection,
    GoalCard,
    GoalChildrenPageRequest,
    GoalListPage,
    GoalSnapshot,
    GoalStatus,
    PurgeStatus,
    SDEStatus,
)
from .reporting import (
    MAX_GOAL_REPORT_CHILDREN,
    MAX_GOAL_REPORT_RECEIPTS,
    MAX_GOAL_REPORT_SDE_CANDIDATES,
    GoalReportData,
    GoalReportPage,
    GoalReportSummary,
    goal_bullet_projection,
    render_goal_report,
)
from .store import FactCompactionApprovalRequest

from .service_types import (
    _GoalReportRelations,
    _GoalReportSnapshot,
)
from .service_goal_lifecycle import _GoalLifecycleMixin


class _GoalReadMixin(_GoalLifecycleMixin):
    """Build bounded goal reports, archives, and list pages."""

    def goal_bullet_projection(self, goal_id: str) -> GoalBulletProjection:
        """Build compact bullets with evidence-derived truth labels and open gates."""

        return goal_bullet_projection(self.goal_status(goal_id))

    def _goal_report_snapshot(
        self, goal_id: str, page: GoalReportPage
    ) -> _GoalReportSnapshot:
        """Load goal-local report facts and their bounded review pages."""

        goal = self.store.get_goal(goal_id, self.project_id)
        facts = self.store.list_facts(goal_id, self.project_id)
        pending_sde_total, pending_sdes = self.store.list_sde_candidate_page(
            goal_id,
            self.project_id,
            page.sde_offset,
            MAX_GOAL_REPORT_SDE_CANDIDATES,
            SDEStatus.PENDING_REVIEW,
        )
        pending_receipt_total, pending_receipts = self.store.pending_receipt_page_for_goal(
            goal_id, self.project_id, 0, MAX_GOAL_REPORT_RECEIPTS
        )
        snapshot = GoalSnapshot(
            goal=goal,
            facts=facts,
            sde_candidates=pending_sdes,
            pending_purges=pending_receipts,
            criteria=(),
            criteria_history=self.store.list_goal_criteria_versions(
                goal_id, self.project_id
            ),
            fact_capacity=self.store.goal_fact_capacity(goal_id, self.project_id),
        )
        return _GoalReportSnapshot(
            snapshot=snapshot,
            projection=goal_bullet_projection(snapshot),
            pending_sde_total=pending_sde_total,
            pending_receipt_total=pending_receipt_total,
        )

    def _goal_report_relations(
        self, goal_id: str, goal: GoalCard, page: GoalReportPage
    ) -> _GoalReportRelations:
        """Load bounded related-goal and receipt pages with exact totals."""

        child_total, children = self.store.list_child_goal_page(
            goal_id,
            self.project_id,
            page.child_offset,
            MAX_GOAL_REPORT_CHILDREN,
        )
        child_status_counts = self.store.child_goal_status_counts(
            goal_id, self.project_id
        )
        terminal_child_statuses = {
            GoalStatus.COMPLETE.value,
            GoalStatus.CANCELLED.value,
            GoalStatus.SUPERSEDED.value,
        }
        open_child_total = sum(
            count
            for status, count in child_status_counts.items()
            if status not in terminal_child_statuses
        )
        dependencies = tuple(
            self.store.get_goal(dependency_id, self.project_id)
            for dependency_id in goal.depends_on_goal_ids
        )
        receipt_total, receipts = self.store.receipt_page_for_goal(
            goal_id,
            self.project_id,
            page.receipt_offset,
            MAX_GOAL_REPORT_RECEIPTS,
        )
        purge_status_counts = self.store.receipt_purge_status_counts(
            goal_id, self.project_id
        )
        return _GoalReportRelations(
            child_total=child_total,
            children=children,
            open_child_total=open_child_total,
            dependencies=dependencies,
            receipt_total=receipt_total,
            receipts=receipts,
            purge_status_counts=tuple(sorted(purge_status_counts.items())),
        )

    def _goal_report_summary(
        self,
        goal_id: str,
        local: _GoalReportSnapshot,
        related: _GoalReportRelations,
    ) -> GoalReportSummary:
        """Join SQL aggregates for one bounded report without loading extra pages."""

        pending_total = related.purge_status_counts
        pending_by_status = dict(pending_total)
        return GoalReportSummary(
            child_total=related.child_total,
            open_child_total=related.open_child_total,
            sde_status_counts=tuple(
                sorted(
                    self.store.sde_candidate_status_counts(
                        goal_id, self.project_id
                    ).items()
                )
            ),
            pending_sde_total=local.pending_sde_total,
            receipt_total=related.receipt_total,
            pending_receipt_total=pending_by_status.get(
                PurgeStatus.PURGE_PENDING.value,
                local.pending_receipt_total,
            ),
            purge_status_counts=related.purge_status_counts,
        )

    def goal_report(
        self,
        goal_id: str,
        page: GoalReportPage | None = None,
    ) -> str:
        """Render one bounded read without holding a write lock during evidence checks."""
        selected_page = page or GoalReportPage()
        with self.store.read_snapshot():
            local = self._goal_report_snapshot(goal_id, selected_page)
            related = self._goal_report_relations(
                goal_id, local.snapshot.goal, selected_page
            )
            summary = self._goal_report_summary(goal_id, local, related)
            intake = self.store.goal_report_context(goal_id, self.project_id)

        snapshot = replace(
            local.snapshot,
            criteria=tuple(
                self._criterion_progress(local.snapshot.goal, criterion, local.snapshot.facts)
                for criterion in local.snapshot.goal.success_criteria
            ),
        )
        local = replace(
            local,
            snapshot=snapshot,
            projection=goal_bullet_projection(snapshot),
        )
        return render_goal_report(
            GoalReportData(
                snapshot=local.snapshot,
                projection=local.projection,
                children=related.children,
                dependencies=related.dependencies,
                receipts=related.receipts,
            ),
            intake=intake,
            summary=summary,
            page=selected_page,
        )

    def fact_compaction_propose(
        self, goal_id: str, max_facts: int = 32
    ) -> FactCompactionProposal:
        """Prepare a content-hashed preview; this never changes active facts."""

        return self.store.propose_fact_compaction(
            goal_id, self.project_id, max_facts
        )

    def fact_compaction_approve(
        self,
        approval: FactCompactionApprovalRequest,
    ) -> FactArchiveReceipt:
        """Archive only the exact preview approved by a scoped reviewer."""

        expected_effect_revision = self._capture_effect_revision()
        with self._effect_fence(expected_effect_revision):
            return self.store.approve_fact_compaction(
                FactCompactionApprovalRequest(
                    compaction_id=approval.compaction_id,
                    goal_id=approval.goal_id,
                    project_id=self.project_id,
                    fact_ids=approval.fact_ids,
                    source_sha256=approval.source_sha256,
                    reviewer_id=approval.reviewer_id,
                    approval_reason=approval.approval_reason,
                )
            )

    def fact_archive_receipts(
        self, goal_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[FactArchiveReceipt, ...]:
        """Read immutable archive audit receipts for a project-scoped goal."""

        return self.store.list_fact_archive_receipts(
            goal_id, self.project_id, offset=offset, limit=limit
        )

    def goal_list(
        self, statuses: tuple[GoalStatus, ...] = ()
    ) -> tuple[GoalSnapshot, ...]:
        """Return a bounded compatibility listing; use goal_list_page for scale."""

        return tuple(
            self.goal_status(goal.goal_id)
            for goal in self.store.list_goals(statuses, self.project_id)
        )

    def goal_list_page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """Return bounded goal cards without loading per-goal facts or reviews."""

        total, goals = self.store.list_goal_page(
            self.project_id, offset, limit, statuses
        )
        next_offset = offset + len(goals) if offset + len(goals) < total else None
        return GoalListPage(
            project_id=self.project_id,
            total=total,
            offset=offset,
            limit=limit,
            goals=goals,
            next_offset=next_offset,
        )

    def goal_children(self, parent_goal_id: str) -> tuple[GoalSnapshot, ...]:
        """Return a bounded compatibility view of child snapshots."""

        self.store.get_goal(parent_goal_id, self.project_id)
        return tuple(
            self.goal_status(child.goal_id)
            for child in self.store.list_child_goals_compat(
                parent_goal_id, self.project_id
            )
        )

    def goal_children_page(
        self,
        request: GoalChildrenPageRequest,
    ) -> GoalListPage:
        """Return compact direct-child cards without loading fact histories."""

        self.store.get_goal(request.parent_goal_id, self.project_id)
        total, goals = self.store.list_child_goal_page(
            request.parent_goal_id,
            self.project_id,
            request.offset,
            request.limit,
            request.statuses,
        )
        next_offset = (
            request.offset + len(goals)
            if request.offset + len(goals) < total
            else None
        )
        return GoalListPage(
            project_id=self.project_id,
            total=total,
            offset=request.offset,
            limit=request.limit,
            goals=goals,
            next_offset=next_offset,
        )
