"""Bounded registration groups for the Curator V2 MCP tool surface."""

from __future__ import annotations

# MCP handler parameters define the explicit public JSON schema for each tool.
# Keep them as named parameters so MCP hosts can validate calls before dispatch.
# pylint: disable=too-many-arguments,too-many-positional-arguments

import hashlib
import re
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context as MCPContext
from mcp.types import ToolAnnotations

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI
from .events import (
    EventEnvelope,
    FactRecorded,
    GoalActivated,
    GoalBlocked,
    GoalCancelled,
    GoalCriteriaAmended,
    GoalDeferred,
    GoalFinishRequested,
    GoalReopened,
    GoalStarted,
    GoalSuperseded,
)
from .hermes_events import CodexGoalBinding, codex_hook_to_event
from .models import (
    FactKind,
    GoalStatus,
    Materiality,
    ReviewDecision,
    SDEQualityFeedbackLabel,
)
from .reporting import GoalReportPage
from .mcp_tool_support import (
    ArtifactInput,
    json_result,
    parse_artifacts,
    parse_criteria,
    parse_evidence,
    safe_tool_handler,
)

_HERMES_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}$")

class _McpToolRegistrar:
    """Capture trusted project context and share safe registration helpers."""

    def __init__(
        self,
        server: MCPServer,
        api: AuthenticatedCuratorAPI,
        caller: AuthenticatedCaller,
        project_id: str,
        source_id: str,
    ) -> None:
        self.server = server
        self.api = api
        self.caller = caller
        self.project_id = project_id
        self.source_id = source_id

    def safe_tool(self, *args: Any, **kwargs: Any) -> Any:
        """Register a tool behind the shared sanitized exception boundary."""

        register = self.server.tool(*args, **kwargs)

        def register_safe(handler: Any) -> Any:
            return register(safe_tool_handler(handler))

        return register_safe

    def read_tool(self) -> Any:
        """Advertise an idempotent, non-destructive Curator read."""

        return self.safe_tool(
            annotations=ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            )
        )

    def event(
        self, event_id: str, payload: Any, source_sequence: int | None = None
    ) -> EventEnvelope:
        """Build an event pinned to this producer and project."""

        return EventEnvelope(
            event_id=event_id,
            project_id=self.project_id,
            payload=payload,
            source_id=self.source_id,
            source_sequence=source_sequence,
        )

    def process(self, event: EventEnvelope) -> str:
        """Dispatch through the API already authorized for this project."""

        return json_result(
            self.api.process_event_json(
                self.caller, self.project_id, event.to_json()
            )
        )


def _register_status_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def event_queue_status() -> str:
        """Read project backlog, queue lag, and active/expired claim totals."""

        return json_result(api.event_queue_status(caller, project_id))

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    def project_activity_status() -> str:
        """Read retained event and SDE counts; this is not a health indicator."""

        return json_result(api.project_activity_status(caller, project_id))

    @_read_tool()
    def project_health() -> str:
        """Read observed project operations; unknown probes never show healthy."""

        return json_result(api.project_health(caller, project_id))

    @_read_tool()
    def project_metrics() -> str:
        """Render content-free Prometheus metrics for the bound project."""

        return api.project_prometheus_metrics(caller, project_id)

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def event_quarantine_retry(event_id: str) -> str:
        """Authorize and audit a retry of one quarantined event."""

        return json_result(
            api.retry_quarantined_event(caller, project_id, event_id)
        )


def _register_goal_intake_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_safe_tool()
    def goal_start(
        event_id: str,
        goal_id: str,
        problem: str,
        success_criteria: list[dict[str, str]],
        owner: str | None = None,
        checklist_id: str | None = None,
        checklist_version: str | None = None,
        checklist_source_text: str | None = None,
        parent_goal_id: str | None = None,
        depends_on_goal_ids: list[str] | None = None,
        initial_status: str = "planned",
        next_action: str | None = None,
        source_sequence: int | None = None,
    ) -> str:
        """Capture a goal as planned by default or active when already accepted."""

        payload = GoalStarted(
            goal_id=goal_id,
            problem=problem,
            success_criteria=parse_criteria(success_criteria),
            owner=owner,
            checklist_id=checklist_id,
            checklist_version=checklist_version,
            checklist_source_text=checklist_source_text,
            parent_goal_id=parent_goal_id,
            depends_on_goal_ids=tuple(depends_on_goal_ids or ()),
            initial_status=GoalStatus(initial_status),
            next_action=next_action,
        )
        return _process(_event(event_id, payload, source_sequence))

    @_safe_tool()
    def goal_activate(
        event_id: str,
        goal_id: str,
        reason: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Explicitly accept planned work for execution at its current revision."""

        return _process(
            _event(
                event_id,
                GoalActivated(goal_id, reason, expected_lifecycle_revision),
                source_sequence,
            )
        )

    @_safe_tool()
    def hermes_goal_bind(goal_id: str, ctx: MCPContext) -> str:
        """Validate an active goal for the host-owned current Hermes session binding."""
        metadata = ctx.request_context.meta
        profile_id = metadata.get("hermes/profile_id") if isinstance(metadata, dict) else None
        session_id = metadata.get("hermes/session_id") if isinstance(metadata, dict) else None
        if not isinstance(profile_id, str) or profile_id != caller.subject_id:
            raise PermissionError("trusted Hermes profile context is unavailable or mismatched")
        if (
            not isinstance(session_id, str)
            or not session_id
            or len(session_id) > 256
            or "\n" in session_id
            or "\r" in session_id
        ):
            raise PermissionError("trusted Hermes session context is unavailable")
        snapshot = api.goal_status(caller, project_id, goal_id)
        if snapshot.goal.status is not GoalStatus.ACTIVE:
            raise ValueError("only an active project goal can be bound to a Hermes session")
        return json_result(
            {
                "binding": "validated",
                "project_id": project_id,
                "goal_id": goal_id,
                "profile_id": profile_id,
            }
        )

    @_safe_tool()
    def hermes_codex_event(
        event_type: str,
        goal_id: str,
        event_id: str,
        source_sequence: int,
        occurred_at: str,
        context: dict[str, str],
        ctx: MCPContext,
    ) -> str:
        """Translate one exact host-outbox event for the active session goal."""
        metadata = ctx.request_context.meta
        profile_id = metadata.get("hermes/profile_id") if isinstance(metadata, dict) else None
        session_id = metadata.get("hermes/session_id") if isinstance(metadata, dict) else None
        durable_event = metadata.get("hermes/durable_event") if isinstance(metadata, dict) else None
        if not isinstance(profile_id, str) or profile_id != caller.subject_id:
            raise PermissionError("trusted Hermes profile context is unavailable or mismatched")
        if durable_event is not True:
            raise PermissionError(
                "Codex lifecycle ingestion requires a host-dispatched durable event"
            )
        if not isinstance(session_id, str) or not _HERMES_SESSION_ID_RE.fullmatch(session_id):
            raise PermissionError("trusted Hermes session context is unavailable")
        source_id = "hermes-" + hashlib.sha256(
            f"{profile_id}\0{project_id}".encode("utf-8")
        ).hexdigest()
        binding = CodexGoalBinding(
            profile_id=profile_id,
            project_id=project_id,
            session_id=session_id,
            goal_id=goal_id,
            source_id=source_id,
        )
        event = codex_hook_to_event(
            event_type,
            context,
            binding,
            source_sequence=source_sequence,
            occurred_at=occurred_at,
        )
        if event.event_id != event_id or event.source_id != source_id:
            raise ValueError("durable Hermes event identity does not match its bound source")
        return json_result(
            api.process_event_json(caller, project_id, event.to_json())
        )

    @_safe_tool()
    def fact_record(
        event_id: str,
        goal_id: str,
        fact_id: str,
        kind: str,
        bullet: str,
        criterion_id: str | None = None,
        evidence: list[dict[str, str]] | None = None,
        source_sequence: int | None = None,
    ) -> str:
        """Append a compact typed fact; verification requires evidence."""

        payload = FactRecorded(
            goal_id=goal_id,
            fact_id=fact_id,
            kind=FactKind(kind),
            bullet=bullet,
            criterion_id=criterion_id,
            evidence=parse_evidence(evidence or []),
        )
        return _process(_event(event_id, payload, source_sequence))


def _register_goal_lifecycle_tools(registrar: _McpToolRegistrar) -> None:
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_safe_tool()
    def goal_finish(
        event_id: str,
        goal_id: str,
        completion_claim: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Evaluate a completion claim against criteria, children, and evidence."""

        return _process(
            _event(
                event_id,
                GoalFinishRequested(
                    goal_id, completion_claim, expected_lifecycle_revision
                ),
                source_sequence,
            )
        )

    @_safe_tool()
    def goal_defer(
        event_id: str,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Record a deferred goal with a concrete follow-up action."""

        return _process(
            _event(
                event_id,
                GoalDeferred(goal_id, reason, next_action, expected_lifecycle_revision),
                source_sequence,
            )
        )

    @_safe_tool()
    def goal_block(
        event_id: str,
        goal_id: str,
        dependency: str,
        recovery: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Record an exact blocking dependency and its recovery path."""

        return _process(
            _event(
                event_id,
                GoalBlocked(goal_id, dependency, recovery, expected_lifecycle_revision),
                source_sequence,
            )
        )

    @_safe_tool()
    def goal_cancel(
        event_id: str,
        goal_id: str,
        reason: str,
        source_sequence: int | None = None,
    ) -> str:
        """Cancel unfinished work with a durable reason; cancellation is not success."""

        return _process(
            _event(event_id, GoalCancelled(goal_id, reason), source_sequence)
        )

    @_safe_tool()
    def goal_supersede(
        event_id: str,
        goal_id: str,
        replacement_goal_id: str,
        reason: str,
        source_sequence: int | None = None,
    ) -> str:
        """Replace unfinished work with an existing same-project goal."""

        return _process(
            _event(
                event_id,
                GoalSuperseded(goal_id, replacement_goal_id, reason),
                source_sequence,
            )
        )

    @_safe_tool()
    def goal_reopen(
        event_id: str,
        goal_id: str,
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Reopen a completed goal as a new evidence epoch."""

        return _process(
            _event(
                event_id,
                GoalReopened(
                    goal_id, reason, next_action, expected_lifecycle_revision
                ),
                source_sequence,
            )
        )

    @_safe_tool()
    def goal_amend_criteria(
        event_id: str,
        goal_id: str,
        expected_revision: int,
        success_criteria: list[dict[str, str]],
        reason: str,
        next_action: str,
        expected_lifecycle_revision: int,
        source_sequence: int | None = None,
    ) -> str:
        """Explicitly amend a goal contract; old evidence will not carry forward."""

        return _process(
            _event(
                event_id,
                GoalCriteriaAmended(
                    goal_id,
                    expected_revision,
                    parse_criteria(success_criteria),
                    reason,
                    next_action,
                    expected_lifecycle_revision,
                ),
                source_sequence,
            )
        )

def _register_event_ingest_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool = registrar.safe_tool

    @_safe_tool()
    def event_ingest(event_json: str) -> str:
        """Ingest a validated version-1 event for this bound project only."""

        return json_result(api.process_event_json(caller, project_id, event_json))


def _register_goal_reads_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def goal_status(
        goal_id: str, sde_offset: int = 0, purge_offset: int = 0
    ) -> str:
        """Read goal truth and one bounded SDE/purge page with exact totals."""

        return json_result(
            api.goal_status(caller, project_id, goal_id, sde_offset, purge_offset)
        )

    @_read_tool()
    def goal_bullet_projection(goal_id: str) -> str:
        """Read compact bullets separating verified facts, claims, and open gates."""

        return json_result(
            api.goal_bullet_projection(caller, project_id, goal_id)
        )

    @_read_tool()
    def goal_report(
        goal_id: str,
        fact_offset: int = 0,
        fact_limit: int = 16,
        child_offset: int = 0,
        sde_offset: int = 0,
        receipt_offset: int = 0,
    ) -> str:
        """Read a concise problem/criteria/facts/TODO/review/purge Markdown report."""

        return api.goal_report(
            caller,
            project_id,
            goal_id,
            GoalReportPage(
                fact_offset=fact_offset,
                fact_limit=fact_limit,
                child_offset=child_offset,
                sde_offset=sde_offset,
                receipt_offset=receipt_offset,
            ),
        )

    @_read_tool()
    def fact_compaction_propose(goal_id: str, max_facts: int = 32) -> str:
        """Preview exact eligible routine bullets without modifying the ledger."""

        return json_result(
            api.fact_compaction_propose(caller, project_id, goal_id, max_facts)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def fact_compaction_approve(
        compaction_id: str,
        goal_id: str,
        fact_ids: list[str],
        source_sha256: str,
        approval_reason: str,
    ) -> str:
        """Approve and archive only exact hash-matched routine facts as reviewer."""

        return json_result(
            api.fact_compaction_approve(
                caller,
                project_id,
                compaction_id,
                goal_id,
                tuple(fact_ids),
                source_sha256,
                approval_reason,
            )
        )


def _register_goal_lists_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def fact_archive_receipts(
        goal_id: str, offset: int = 0, limit: int = 50
    ) -> str:
        """Read bounded archive hashes, source fact IDs, and reviewer receipts."""

        return json_result(
            api.fact_archive_receipts(
                caller, project_id, goal_id, offset, limit
            )
        )

    @_read_tool()
    def goal_list(statuses: list[str] | None = None) -> str:
        """List up to 100 project goal snapshots for small projects."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return json_result(api.goal_list(caller, project_id, parsed_statuses))

    @_read_tool()
    def goal_list_page(
        offset: int = 0,
        limit: int = 50,
        statuses: list[str] | None = None,
    ) -> str:
        """List compact goal cards with total count and a next-page offset."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return json_result(
            api.goal_list_page(
                caller,
                project_id,
                offset=offset,
                limit=limit,
                statuses=parsed_statuses,
            )
        )

    @_read_tool()
    def goal_children(parent_goal_id: str) -> str:
        """List up to 100 full child snapshots for small parent tasks."""

        return json_result(
            api.goal_children(caller, project_id, parent_goal_id)
        )

    @_read_tool()
    def goal_children_page(
        parent_goal_id: str,
        offset: int = 0,
        limit: int = 50,
        statuses: list[str] | None = None,
    ) -> str:
        """List compact child cards with total count and a next-page offset."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return json_result(
            api.goal_children_page(
                caller,
                project_id,
                parent_goal_id,
                offset=offset,
                limit=limit,
                statuses=parsed_statuses,
            )
        )


def _register_project_persistence_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def project_storage_usage() -> str:
        """Report this project's logical records and event-class byte usage."""

        return json_result(api.project_storage_usage(caller, project_id))

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def goal_persist(goal_id: str, target: str) -> str:
        """Project a goal to a configured canonical Markdown target."""

        return json_result(api.persist_goal(caller, project_id, goal_id, target))

    @_read_tool()
    def goal_reconcile(goal_id: str, target: str) -> str:
        """Compare a configured Markdown block with SQLite without changing either."""

        return json_result(
            api.reconcile_goal(caller, project_id, goal_id, target)
        )

    @_read_tool()
    def project_reconcile(
        target: str, offset: int = 0, limit: int = 50
    ) -> str:
        """Read a bounded reconciliation page, including orphaned Markdown blocks."""

        return json_result(
            api.reconcile_project(
                caller, project_id, target, offset=offset, limit=limit
            )
        )


def _register_review_discovery_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def sde_review_queue(limit: int = 100) -> str:
        """List a bounded queue of project-scoped SDE review packets."""

        return json_result(api.sde_review_queue(caller, project_id, limit))

    @_safe_tool()
    def sde_assess(
        goal_id: str,
        materiality: str,
        rationale: str,
        fact_ids: list[str],
        impact: str | None = None,
        retrieval_value: str | None = None,
    ) -> str:
        """Assess selected facts; a candidate remains pending human review."""

        candidate = api.sde_assess(
            caller,
            project_id,
            goal_id,
            Materiality(materiality),
            rationale,
            tuple(fact_ids),
            impact,
            retrieval_value,
        )
        return json_result(candidate)

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def artifact_inventory_discover(goal_id: str) -> str:
        """Discover one goal's bounded staging manifest for human review."""

        return json_result(
            api.discover_artifact_inventory(caller, project_id, goal_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def project_artifact_inventory_discover() -> str:
        """Discover this project's bounded staging manifest for human review."""

        return json_result(
            api.discover_project_artifact_inventory(caller, project_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def project_expiry_inventory_discover() -> str:
        """Discover record-ready or 72-hour-max staging candidates, without deletion authority."""

        return json_result(
            api.discover_project_expiry_inventory(caller, project_id)
        )


def _register_review_records_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_read_tool()
    def sde_review_detail(candidate_id: str) -> str:
        """Inspect the selected facts and evidence for a review candidate."""

        return json_result(
            api.sde_review_detail(caller, project_id, candidate_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def sde_review_packet(candidate_id: str) -> str:
        """Present candidate provenance and current exact artifact inventory."""

        return json_result(
            api.sde_review_packet(caller, project_id, candidate_id)
        )

    @_safe_tool()
    def sde_correction_record(
        correction_id: str,
        candidate_id: str,
        correction: str,
        rationale: str,
    ) -> str:
        """Record an authenticated, immutable correction linked to a decided SDE."""

        return json_result(
            api.sde_correction_record(
                caller,
                project_id,
                correction_id,
                candidate_id,
                correction,
                rationale,
            )
        )

    @_safe_tool()
    def sde_quality_feedback_record(
        feedback_id: str,
        candidate_id: str,
        label: str,
        rationale: str = "",
    ) -> str:
        """Record an explicit human QA label after SDE disposition."""

        return json_result(
            api.sde_quality_feedback_record(
                caller,
                project_id,
                feedback_id,
                candidate_id,
                SDEQualityFeedbackLabel(label),
                rationale,
            )
        )

    @_read_tool()
    def sde_quality_feedback_summary() -> str:
        """Report aggregate reviewer labels without exposing identities."""

        return json_result(
            api.sde_quality_feedback_summary(caller, project_id)
        )


def _register_cleanup_tools(registrar: _McpToolRegistrar) -> None:
    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    _safe_tool, _read_tool = registrar.safe_tool, registrar.read_tool
    _event, _process = registrar.event, registrar.process

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def sde_confirm(
        candidate_id: str,
        decision: str,
        artifacts: list[ArtifactInput],
        artifact_inventory_complete: bool,
        rationale: str | None = None,
    ) -> str:
        """Record disposition and authorize purge of its exact complete manifest."""

        return json_result(
            api.sde_confirm(
                caller,
                project_id,
                candidate_id,
                ReviewDecision(decision),
                parse_artifacts(artifacts),
                artifact_inventory_complete=artifact_inventory_complete,
                rationale=rationale,
            )
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def artifact_inventory_complete(
        receipt_id: str, artifacts: list[ArtifactInput]
    ) -> str:
        """Finalize an exact artifact inventory after review authorization."""

        return json_result(
            api.artifact_inventory_complete(
                caller,
                project_id,
                receipt_id,
                parse_artifacts(artifacts),
            )
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def artifact_cleanup_approve(
        receipt_id: str,
        artifacts: list[ArtifactInput],
        manifest_sha256: str,
        target: str,
    ) -> str:
        """Record compatibility cleanup approval for an exact manifest."""

        authorization, receipt = api.authorize_artifact_cleanup(
            caller,
            project_id,
            receipt_id,
            parse_artifacts(artifacts),
            manifest_sha256,
            target,
        )
        return json_result(
            {"authorization": authorization, "receipt": receipt}
        )

    @_read_tool()
    def artifact_purge_status(receipt_id: str) -> str:
        """Read receipt-level and per-artifact purge state and retry metadata."""

        return json_result(api.artifact_purge_status(caller, project_id, receipt_id))

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def release_artifact_hold(receipt_id: str, path: str, rationale: str) -> str:
        """Audibly release one exact hold; eligible purge resumes immediately."""

        return json_result(
            api.release_artifact_hold(
                caller, project_id, receipt_id, path, rationale
            )
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def retry_pending_purges() -> str:
        """Retry only project-local reviewed and canonically persisted manifests."""

        return json_result(api.retry_pending_purges(caller, project_id))


def register_mcp_tools(
    server: MCPServer,
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    project_id: str,
    source_id: str,
) -> None:
    """Register every project-bound tool on the already-configured server."""

    registrar = _McpToolRegistrar(server, api, caller, project_id, source_id)
    _register_status_tools(registrar)
    _register_goal_intake_tools(registrar)
    _register_goal_lifecycle_tools(registrar)
    _register_event_ingest_tools(registrar)
    _register_goal_reads_tools(registrar)
    _register_goal_lists_tools(registrar)
    _register_project_persistence_tools(registrar)
    _register_review_discovery_tools(registrar)
    _register_review_records_tools(registrar)
    _register_cleanup_tools(registrar)
