"""MCP tool server bound to one trusted caller and configured project."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import wraps
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from mcp.server import MCPServer
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver.context import Context as MCPContext
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI
from .events import (
    EventEnvelope,
    FactRecorded,
    GoalBlocked,
    GoalActivated,
    GoalCancelled,
    GoalDeferred,
    GoalFinishRequested,
    GoalCriteriaAmended,
    GoalSuperseded,
    GoalReopened,
    GoalStarted,
)
from .errors import safe_exception_label, to_api_error
from .hermes_events import CodexGoalBinding, codex_hook_to_event
from .models import (
    ArtifactRef,
    EvidenceOutcome,
    EvidenceRef,
    FactKind,
    GoalStatus,
    Materiality,
    ReviewDecision,
    RetentionHoldKind,
    SDEQualityFeedbackLabel,
    SuccessCriterion,
)

_SOURCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")
_HERMES_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,255}$")
logger = logging.getLogger(__name__)
SERVER_INSTRUCTIONS = """\
Curator V2 work protocol:
1. At intake, bind the exact user request or configured checklist item to this
   project. Before implementation, call goal_start with a concise problem and
   observable success criteria; use planned status until the work is accepted.
   Do not invent criteria or silently rewrite the source item. Once an existing
   goal is active, call hermes_goal_bind to validate an explicit current-session
   association; Hermes persists the host binding only after this succeeds.
2. At meaningful checkpoints, record deduplicated compact fact bullets with
   fact_record: distinguish research, advice, intent, change, verification,
   open gates, and outcomes. Verification needs evidence; claims, session end,
   and healthy readiness are not proof. Never store raw chats, transcripts,
   large command output, or source artifacts as canonical facts.
3. Reconcile with goal_report. Show verified criteria separately from open
   criteria, facts to date, TODOs, blocker/owner, and next action. Finish only
   when every criterion has passing evidence; otherwise leave the goal open,
   blocked, or deferred with the exact unmet work.
4. Keep SDE review, canonical persistence, and artifact cleanup separate from
   goal completion. Present selected facts and evidence for human review. Write
   approved compact bullets and the durable receipt before purging only a
   complete approved inventory. Keep incomplete or failed cleanup visibly
   pending; never equate a zero SDE count with failed capture or health.
"""


def safe_tool_handler(handler: Any) -> Any:
    """Convert expected and unexpected failures to stable, content-safe tool errors."""

    @wraps(handler)
    def invoke(*args: Any, **kwargs: Any) -> Any:
        try:
            return handler(*args, **kwargs)
        # Plugin and SDK failures must become sanitized tool results, never tracebacks.
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            error = to_api_error(exc)
            logger.warning(
                "Curator MCP tool failed with code=%s exception_type=%s",
                error.code,
                safe_exception_label(exc),
            )
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(error.to_dict(), sort_keys=True),
                    )
                ],
                is_error=True,
            )

    return invoke


def _hermes_identity_middleware(expected_profile_id: str):
    """Require the local Hermes host context on every tool call.

    The profile is pinned by the local launcher and must match the identity
    Hermes injects into request metadata. This is a host-context binding for a
    private stdio process, not cryptographic authentication for remote clients.
    """

    async def enforce_profile(
        ctx: ServerRequestContext[Any, Any], call_next: Any
    ) -> Any:
        if ctx.method != "tools/call":
            return await call_next(ctx)

        metadata = ctx.meta
        profile_id = (
            metadata.get("hermes/profile_id")
            if isinstance(metadata, Mapping)
            else None
        )
        session_id = (
            metadata.get("hermes/session_id")
            if isinstance(metadata, Mapping)
            else None
        )
        valid_session = (
            isinstance(session_id, str)
            and 1 <= len(session_id) <= 256
            and "\n" not in session_id
            and "\r" not in session_id
        )
        if profile_id != expected_profile_id or not valid_session:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "schema_version": 1,
                                "code": "unauthenticated",
                                "message": "Trusted Hermes profile context is required.",
                            },
                            sort_keys=True,
                        ),
                    )
                ],
                is_error=True,
            )
        return await call_next(ctx)

    return enforce_profile


class ArtifactInput(TypedDict):
    """MCP artifact manifest entry with an optional explicit retention hold."""

    path: str
    sha256: str
    retention_hold: NotRequired[str | None]


def build_mcp_server(
    api: AuthenticatedCuratorAPI,
    caller: AuthenticatedCaller,
    project_id: str,
    source_id: str,
    *,
    require_hermes_context: bool = False,
) -> MCPServer:
    """Build tools with trusted caller/project captured outside tool arguments.

    The host must authenticate the caller and authorize a configured project
    before calling this factory. MCP clients cannot switch projects or supply
    an identity through any registered tool parameter.
    """

    if not _SOURCE_ID_RE.fullmatch(source_id):
        raise ValueError("source_id must be a bounded opaque producer identifier")
    middleware = (
        [_hermes_identity_middleware(caller.subject_id)]
        if require_hermes_context
        else None
    )
    server = MCPServer(
        "CuratorMD V2",
        version="0.1.0",
        instructions=SERVER_INSTRUCTIONS,
        middleware=middleware,
    )

    register_tool = server.tool

    def _safe_tool(*args: Any, **kwargs: Any) -> Any:
        """Keep tool schemas from original signatures while sanitizing exceptions."""

        register = register_tool(*args, **kwargs)

        def register_safe(handler: Any) -> Any:
            return register(safe_tool_handler(handler))

        return register_safe

    def _event(event_id: str, payload: Any, source_sequence: int | None = None):
        return EventEnvelope(
            event_id=event_id,
            project_id=project_id,
            payload=payload,
            source_id=source_id,
            source_sequence=source_sequence,
        )

    def _process(event: EventEnvelope) -> str:
        return _json_result(
            api.process_event_json(caller, project_id, event.to_json())
        )

    @_safe_tool()
    def event_queue_status() -> str:
        """Read project backlog, queue lag, and active/expired claim totals."""

        return _json_result(api.event_queue_status(caller, project_id))

    @_safe_tool()
    def project_activity_status() -> str:
        """Read retained event and SDE counts; this is not a health indicator."""

        return _json_result(api.project_activity_status(caller, project_id))

    @_safe_tool()
    def project_health() -> str:
        """Read observed project operations; unknown probes never show healthy."""

        return _json_result(api.project_health(caller, project_id))

    @_safe_tool()
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

        return _json_result(
            api.retry_quarantined_event(caller, project_id, event_id)
        )

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
            success_criteria=_criteria(success_criteria),
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
        return _json_result(
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
        return _json_result(
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
            evidence=_evidence(evidence or []),
        )
        return _process(_event(event_id, payload, source_sequence))

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
                    _criteria(success_criteria),
                    reason,
                    next_action,
                    expected_lifecycle_revision,
                ),
                source_sequence,
            )
        )

    @_safe_tool()
    def event_ingest(event_json: str) -> str:
        """Ingest a validated version-1 event for this bound project only."""

        return _json_result(api.process_event_json(caller, project_id, event_json))

    @_safe_tool()
    def goal_status(
        goal_id: str, sde_offset: int = 0, purge_offset: int = 0
    ) -> str:
        """Read goal truth and one bounded SDE/purge page with exact totals."""

        return _json_result(
            api.goal_status(caller, project_id, goal_id, sde_offset, purge_offset)
        )

    @_safe_tool()
    def goal_bullet_projection(goal_id: str) -> str:
        """Read compact bullets separating verified facts, claims, and open gates."""

        return _json_result(
            api.goal_bullet_projection(caller, project_id, goal_id)
        )

    @_safe_tool()
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
            fact_offset,
            fact_limit,
            child_offset,
            sde_offset,
            receipt_offset,
        )

    @_safe_tool()
    def fact_compaction_propose(goal_id: str, max_facts: int = 32) -> str:
        """Preview exact eligible routine bullets without modifying the ledger."""

        return _json_result(
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

        return _json_result(
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

    @_safe_tool()
    def fact_archive_receipts(
        goal_id: str, offset: int = 0, limit: int = 50
    ) -> str:
        """Read bounded archive hashes, source fact IDs, and reviewer receipts."""

        return _json_result(
            api.fact_archive_receipts(
                caller, project_id, goal_id, offset, limit
            )
        )

    @_safe_tool()
    def goal_list(statuses: list[str] | None = None) -> str:
        """List up to 100 project goal snapshots for small projects."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return _json_result(api.goal_list(caller, project_id, parsed_statuses))

    @_safe_tool()
    def goal_list_page(
        offset: int = 0,
        limit: int = 50,
        statuses: list[str] | None = None,
    ) -> str:
        """List compact goal cards with total count and a next-page offset."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return _json_result(
            api.goal_list_page(
                caller,
                project_id,
                offset=offset,
                limit=limit,
                statuses=parsed_statuses,
            )
        )

    @_safe_tool()
    def goal_children(parent_goal_id: str) -> str:
        """List up to 100 full child snapshots for small parent tasks."""

        return _json_result(
            api.goal_children(caller, project_id, parent_goal_id)
        )

    @_safe_tool()
    def goal_children_page(
        parent_goal_id: str,
        offset: int = 0,
        limit: int = 50,
        statuses: list[str] | None = None,
    ) -> str:
        """List compact child cards with total count and a next-page offset."""

        parsed_statuses = tuple(GoalStatus(status) for status in statuses or [])
        return _json_result(
            api.goal_children_page(
                caller,
                project_id,
                parent_goal_id,
                offset=offset,
                limit=limit,
                statuses=parsed_statuses,
            )
        )

    @_safe_tool()
    def project_storage_usage() -> str:
        """Report this project's logical records and event-class byte usage."""

        return _json_result(api.project_storage_usage(caller, project_id))

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def goal_persist(goal_id: str, target: str) -> str:
        """Project a goal to a configured canonical Markdown target."""

        return _json_result(api.persist_goal(caller, project_id, goal_id, target))

    @_safe_tool()
    def goal_reconcile(goal_id: str, target: str) -> str:
        """Compare a configured Markdown block with SQLite without changing either."""

        return _json_result(
            api.reconcile_goal(caller, project_id, goal_id, target)
        )

    @_safe_tool()
    def project_reconcile(
        target: str, offset: int = 0, limit: int = 50
    ) -> str:
        """Read a bounded reconciliation page, including orphaned Markdown blocks."""

        return _json_result(
            api.reconcile_project(
                caller, project_id, target, offset=offset, limit=limit
            )
        )

    @_safe_tool()
    def sde_review_queue(limit: int = 100) -> str:
        """List a bounded queue of project-scoped SDE review packets."""

        return _json_result(api.sde_review_queue(caller, project_id, limit))

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
        return _json_result(candidate)

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def artifact_inventory_discover(goal_id: str) -> str:
        """Discover one goal's bounded staging manifest for human review."""

        return _json_result(
            api.discover_artifact_inventory(caller, project_id, goal_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def project_artifact_inventory_discover() -> str:
        """Discover this project's bounded staging manifest for human review."""

        return _json_result(
            api.discover_project_artifact_inventory(caller, project_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def project_expiry_inventory_discover() -> str:
        """Discover 72-hour staging candidates without authorizing deletion."""

        return _json_result(
            api.discover_project_expiry_inventory(caller, project_id)
        )

    @_safe_tool()
    def sde_review_detail(candidate_id: str) -> str:
        """Inspect the selected facts and evidence for a review candidate."""

        return _json_result(
            api.sde_review_detail(caller, project_id, candidate_id)
        )

    @_safe_tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        )
    )
    def sde_review_packet(candidate_id: str) -> str:
        """Present candidate provenance and current exact artifact inventory."""

        return _json_result(
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

        return _json_result(
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

        return _json_result(
            api.sde_quality_feedback_record(
                caller,
                project_id,
                feedback_id,
                candidate_id,
                SDEQualityFeedbackLabel(label),
                rationale,
            )
        )

    @_safe_tool()
    def sde_quality_feedback_summary() -> str:
        """Report aggregate reviewer labels without exposing identities."""

        return _json_result(
            api.sde_quality_feedback_summary(caller, project_id)
        )

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
        """Record an authorized decision and exact staged-artifact manifest."""

        return _json_result(
            api.sde_confirm(
                caller,
                project_id,
                candidate_id,
                ReviewDecision(decision),
                _artifacts(artifacts),
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

        return _json_result(
            api.artifact_inventory_complete(
                caller,
                project_id,
                receipt_id,
                _artifacts(artifacts),
            )
        )

    @_safe_tool()
    def artifact_purge_status(receipt_id: str) -> str:
        """Read receipt-level and per-artifact purge state and retry metadata."""

        return _json_result(api.artifact_purge_status(caller, project_id, receipt_id))

    @_safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def release_artifact_hold(receipt_id: str, path: str, rationale: str) -> str:
        """Audibly release one exact hold; eligible purge resumes immediately."""

        return _json_result(
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

        return _json_result(api.retry_pending_purges(caller, project_id))

    return server


def _criteria(values: list[dict[str, str]]) -> tuple[SuccessCriterion, ...]:
    criteria: list[SuccessCriterion] = []
    for value in values:
        if set(value) != {"criterion_id", "description"}:
            raise ValueError("criteria require exactly criterion_id and description")
        criteria.append(SuccessCriterion(value["criterion_id"], value["description"]))
    return tuple(criteria)


def _evidence(values: list[dict[str, str]]) -> tuple[EvidenceRef, ...]:
    evidence: list[EvidenceRef] = []
    for value in values:
        if set(value) != {"evidence_kind", "locator", "sha256", "outcome"}:
            raise ValueError("evidence requires kind, locator, sha256, and outcome")
        evidence.append(
            EvidenceRef(
                evidence_kind=value["evidence_kind"],
                locator=value["locator"],
                sha256=value["sha256"],
                outcome=EvidenceOutcome(value["outcome"]),
            )
        )
    return tuple(evidence)


def _artifacts(values: list[ArtifactInput]) -> tuple[ArtifactRef, ...]:
    artifacts: list[ArtifactRef] = []
    for value in values:
        if set(value) not in ({"path", "sha256"}, {"path", "sha256", "retention_hold"}):
            raise ValueError("artifacts require path and sha256, with optional retention_hold")
        hold_value = value.get("retention_hold")
        if hold_value is not None and not hold_value:
            raise ValueError("retention_hold must be omitted or legal/operational")
        hold = RetentionHoldKind(hold_value) if hold_value is not None else None
        artifacts.append(ArtifactRef(value["path"], value["sha256"], hold))
    return tuple(artifacts)


def _json_result(value: object) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    return json.dumps(value, default=_json_default, ensure_ascii=False, separators=(",", ":"))


def _json_default(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")
