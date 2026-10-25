"""Project-wide Markdown reconciliation behavior tests."""

from __future__ import annotations

import hashlib

from markdown_persistence_fixtures import MarkdownPersistenceFixture

from curatormd_v2 import MarkdownReconciliationStatus, SuccessCriterion


class MarkdownReconciliationTests(MarkdownPersistenceFixture):
    """Verify paginated, read-only project marker reconciliation."""

    def test_project_reconciliation_pages_goals_and_finds_orphaned_markers(self) -> None:
        second_goal = self.plugin.service.goal_start(
            "A second goal remains absent from Markdown",
            (SuccessCriterion("listed", "The second goal appears in its page"),),
        )
        self.plugin.persist_goal(self.goal.goal_id, self.target)
        orphan_goal_id = "orphaned-markdown-goal"
        orphan_marker_hash = hashlib.sha256(orphan_goal_id.encode("utf-8")).hexdigest()
        malformed_goal_id = "malformed-markdown-goal"
        malformed_marker_hash = hashlib.sha256(
            malformed_goal_id.encode("utf-8")
        ).hexdigest()
        orphan_block = (
            f"<!-- curatormd-v2:goal:{orphan_marker_hash}:start -->\n"
            f"### Goal `{orphan_goal_id}`\n"
            f"<!-- curatormd-v2:goal:{orphan_marker_hash}:end -->\n"
            f"<!-- curatormd-v2:goal:{malformed_marker_hash}:start -->\n"
        )
        existing = self.target.read_text(encoding="utf-8")
        self.target.write_text(existing + orphan_block, encoding="utf-8")
        with_orphan = self.target.read_text(encoding="utf-8")

        first_page = self.plugin.reconcile_project(self.target, offset=0, limit=1)
        second_page = self.plugin.reconcile_project(self.target, offset=1, limit=1)

        self.assertEqual(first_page.total_goals, 2)
        self.assertEqual(first_page.next_offset, 1)
        self.assertEqual(second_page.next_offset, None)
        results = {
            item.goal_id: item.status.value
            for item in first_page.goals + second_page.goals
        }
        self.assertEqual(results[self.goal.goal_id], "synced")
        self.assertEqual(results[second_goal.goal_id], "missing")
        self.assertEqual(first_page.orphan_marker_sha256, (orphan_marker_hash,))
        self.assertEqual(
            first_page.malformed_marker_sha256, (malformed_marker_hash,)
        )
        self.assertTrue(first_page.inventory_complete)
        self.assertEqual(first_page.malformed_marker_count, 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), with_orphan)

    def test_project_reconciliation_marks_over_limit_marker_inventory_incomplete(self) -> None:
        markers = "\n".join(
            "<!-- curatormd-v2:goal:unrecognized -->"
            for _ in range(5001)
        )
        self.target.write_text(markers, encoding="utf-8")

        report = self.plugin.reconcile_project(self.target)

        self.assertFalse(report.inventory_complete)
        self.assertEqual(report.unrecognized_marker_count, 5000)
        self.assertEqual(self.target.read_text(encoding="utf-8"), markers)

    def test_read_only_reconciliation_marks_malformed_markers(self) -> None:
        """Do not choose a side or mutate a projection with unsafe markers."""

        self.plugin.persist_goal(self.goal.goal_id, self.target)
        original = self.target.read_text()
        marker = next(
            line for line in original.splitlines() if line.endswith(":start -->")
        )
        self.target.write_text(original + f"prefix {marker}\n")
        malformed_content = self.target.read_text()

        result = self.plugin.reconcile_goal(self.goal.goal_id, self.target)

        self.assertEqual(result.status, MarkdownReconciliationStatus.MALFORMED)
        self.assertIsNone(result.actual_sha256)
        self.assertEqual(self.target.read_text(), malformed_content)
