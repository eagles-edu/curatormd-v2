"""Repository path and goal read adapters for a bound Curator project."""

from __future__ import annotations

from pathlib import Path
from .markdown_persistence import (
    MarkdownPersistenceAdapter,
    MarkdownProjectReconciliation,
    MarkdownProjectionResult,
    MarkdownReconciliationResult,
)
from .models import (
    GoalChildrenPageRequest,
    GoalListPage,
    GoalBulletProjection,
    GoalSnapshot,
    GoalStatus,
)
from .reporting import (
    GoalFactEvidence,
    GoalReportPage,
)
from .project_plugin_staging import ProjectStagingMixin


class ProjectRepositoryMixin(ProjectStagingMixin):  # pylint: disable=abstract-method
    """Configured repository paths and canonical Markdown operations."""

    @property
    def repository_root(self) -> Path:
        """Return this plugin's validated consumer repository root."""

        return self.config.project_root

    @property
    def persistence_targets(self) -> tuple[Path, ...]:
        """Return the explicitly configured canonical Markdown targets."""

        return self.config.persistence_targets

    def persist_goal(self, goal_id: str, target: str | Path) -> MarkdownProjectionResult:
        """Project one scoped goal to an explicitly selected configured target.

        Projection is deliberately explicit and never approves an SDE. For an
        already reviewed receipt, a successful Markdown write records its
        target/hash in SQLite and releases the purge gate; purge errors remain
        visible on the receipt and are reflected by the follow-up projection.
        """

        with self._locked_staging_root():
            expected_revision = self._capture_active_project_revision()

            def effect_fence():
                """Fence each durable projection effect to the captured revision."""

                return self._project_revision_fence(expected_revision)

            adapter = MarkdownPersistenceAdapter(
                self.config,
                self.service.store,
                target,
                self.service.evidence_verifier,
            )
            projection = adapter.persist_goal(goal_id, effect_fence=effect_fence)
            unpersisted = tuple(
                receipt
                for receipt in self.service.store.receipts_for_goal(
                    goal_id, self.config.project_id
                )
                if not receipt.canonical_persisted
            )
            for receipt in unpersisted:
                adapter.verify_projection(projection)
                with effect_fence():
                    self.service.mark_canonical_persisted(
                        receipt.receipt_id,
                        projection.target.relative_to(
                            self.config.project_root
                        ).as_posix(),
                        projection.sha256,
                    )
            cleanup_unpersisted = tuple(
                receipt
                for receipt in self.service.store.receipts_for_goal(
                    goal_id, self.config.project_id
                )
                if receipt.cleanup_authorized
                and not receipt.cleanup_canonical_persisted
            )
            for receipt in cleanup_unpersisted:
                adapter.verify_projection(projection)
                with effect_fence():
                    self.service.mark_cleanup_authorization_canonical_persisted(
                        receipt.receipt_id,
                        projection.target.relative_to(
                            self.config.project_root
                        ).as_posix(),
                        projection.sha256,
                    )
            if unpersisted or cleanup_unpersisted:
                projection = adapter.persist_goal(
                    goal_id, effect_fence=effect_fence
                )
            return projection

    def reconcile_goal(
        self, goal_id: str, target: str | Path
    ) -> MarkdownReconciliationResult:
        """Compare configured Markdown with the structured record read-only."""

        adapter = MarkdownPersistenceAdapter(
            self.config,
            self.service.store,
            target,
            self.service.evidence_verifier,
        )
        return adapter.reconcile_goal(goal_id)

    def reconcile_project(
        self,
        target: str | Path,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> MarkdownProjectReconciliation:
        """Return a bounded per-goal and orphan-marker reconciliation page."""

        adapter = MarkdownPersistenceAdapter(
            self.config,
            self.service.store,
            target,
            self.service.evidence_verifier,
        )
        return adapter.reconcile_project(offset=offset, limit=limit)

    def checklist_path(self, checklist_id: str) -> Path:
        """Resolve a checklist only when its ID is bound in repository config."""

        return self.config.checklist_path(checklist_id)

    def resolve_read_path(self, relative_path: str) -> Path:
        """Return a path inside the config's read-only repository allowlist."""

        return self.config.resolve_read_path(relative_path)


class ProjectGoalReadMixin(ProjectStagingMixin):  # pylint: disable=abstract-method
    """Bound project goal status and pagination reads."""

    def goal_status(
        self, goal_id: str, sde_offset: int = 0, purge_offset: int = 0
    ) -> GoalSnapshot:
        """Read one bounded status page from this plugin's project scope."""

        return self.service.goal_status(
            goal_id, sde_offset=sde_offset, purge_offset=purge_offset
        )

    def goal_bullet_projection(self, goal_id: str) -> GoalBulletProjection:
        """Return compact truth-labeled bullets inside this project boundary."""

        return self.service.goal_bullet_projection(goal_id)

    def goal_report(
        self,
        goal_id: str,
        page: GoalReportPage | None = None,
    ) -> str:
        """Render a bounded, user-readable report inside this project scope."""

        return self.service.goal_report(goal_id, page)

    def goal_fact_evidence(
        self,
        goal_id: str,
        fact_id: str,
        page: GoalReportPage | None = None,
    ) -> GoalFactEvidence:
        """Read bounded evidence references for one fact on a report page."""

        return self.service.goal_fact_evidence(goal_id, fact_id, page)

    def goal_list(
        self, statuses: tuple[GoalStatus, ...] = ()
    ) -> tuple[GoalSnapshot, ...]:
        """List only goals belonging to this plugin's bound project."""

        return self.service.goal_list(statuses)

    def goal_list_page(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        statuses: tuple[GoalStatus, ...] = (),
    ) -> GoalListPage:
        """List compact project goal cards with bounded pagination."""

        return self.service.goal_list_page(
            offset=offset, limit=limit, statuses=statuses
        )

    def goal_children(self, parent_goal_id: str) -> tuple[GoalSnapshot, ...]:
        """List only direct child tasks of a goal in this project."""

        return self.service.goal_children(parent_goal_id)

    def goal_children_page(
        self,
        request: GoalChildrenPageRequest,
    ) -> GoalListPage:
        """List compact, paginated child cards in this project's boundary."""

        return self.service.goal_children_page(request)
