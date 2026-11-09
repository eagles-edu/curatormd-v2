"""Project-bound MCP registration for reviewed artifact cleanup tools."""

from __future__ import annotations

# MCP parameters are the public JSON schema; keep each named argument explicit.
# pylint: disable=too-many-arguments,too-many-positional-arguments

from typing import Any, Protocol

from mcp.types import ToolAnnotations

from .models import (
    ArtifactCleanupAuthorizationRequest,
    ReviewDecision,
    SDEConfirmationRequest,
)
from .mcp_tool_support import ArtifactInput, json_result, parse_artifacts
from .sde_review_draft import SDEReviewDraft

from .api import AuthenticatedCaller, AuthenticatedCuratorAPI


class _CleanupToolRegistrar(Protocol):
    """Minimum trusted registrar surface needed by cleanup tool handlers."""

    api: AuthenticatedCuratorAPI
    caller: AuthenticatedCaller
    project_id: str

    def safe_tool(self, *args: Any, **kwargs: Any) -> Any:
        """Wrap a destructive operation in the shared error boundary."""

    def read_tool(self) -> Any:
        """Mark an idempotent query as read-only."""


def register_cleanup_tools(registrar: _CleanupToolRegistrar) -> None:
    """Register project-scoped disposition, hold, and purge tools."""

    api, caller, project_id = registrar.api, registrar.caller, registrar.project_id
    safe_tool, read_tool = registrar.safe_tool, registrar.read_tool

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def sde_confirm(
        candidate_id: str,
        decision: str,
        artifacts: list[ArtifactInput],
        artifact_inventory_complete: bool,
        dependency_map_sha256: str,
        rationale: str | None = None,
        review_draft_json: str = "",
        expected_review_binding_sha256: str | None = None,
        confirm_significance_five: bool = False,
    ) -> str:
        """Record disposition, optionally binding an edited decision and exact inventory."""

        return json_result(
            api.sde_confirm(
                caller,
                project_id,
                SDEConfirmationRequest(
                    candidate_id=candidate_id,
                    decision=ReviewDecision(decision),
                    artifacts=parse_artifacts(artifacts),
                    artifact_inventory_complete=artifact_inventory_complete,
                    dependency_map_sha256=dependency_map_sha256,
                    rationale=rationale,
                    review_draft=(
                        SDEReviewDraft.from_json(review_draft_json)
                        if review_draft_json
                        else None
                    ),
                    expected_review_binding_sha256=expected_review_binding_sha256,
                    confirm_significance_five=confirm_significance_five,
                ),
            )
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def sde_withdraw_candidates(candidate_ids: list[str], rationale: str) -> str:
        """Withdraw exact stale pending proposals, retaining facts and audit receipts."""

        return json_result(
            api.sde_withdraw_candidates(
                caller,
                project_id,
                tuple(candidate_ids),
                rationale,
            )
        )

    @read_tool()
    def sde_prepare_review_binding(
        candidate_id: str,
        decision: str,
        artifacts: list[ArtifactInput],
        artifact_inventory_complete: bool,
        dependency_map_sha256: str,
        rationale: str,
        review_draft_json: str,
        confirm_significance_five: bool = False,
    ) -> str:
        """Prepare the exact edited decision binding before owner confirmation."""

        request = SDEConfirmationRequest(
            candidate_id=candidate_id,
            decision=ReviewDecision(decision),
            artifacts=parse_artifacts(artifacts),
            artifact_inventory_complete=artifact_inventory_complete,
            dependency_map_sha256=dependency_map_sha256,
            rationale=rationale,
            review_draft=SDEReviewDraft.from_json(review_draft_json),
            confirm_significance_five=confirm_significance_five,
        )
        binding = api.prepare_sde_review_binding(caller, project_id, request)
        return json_result({"binding": binding, "sha256": binding.sha256()})

    @read_tool()
    def sde_review_projection_status(receipt_id: str) -> str:
        """Read exact selected destination states for the original reviewer."""

        return json_result(
            api.sde_review_projection_status(caller, project_id, receipt_id)
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def sde_project_review_target(
        receipt_id: str, target: str, prepare_only: bool,
    ) -> str:
        """Prepare or write one previously approved SDE destination."""

        return json_result(
            api.sde_project_review_target(
                caller, project_id, receipt_id, target, prepare_only=prepare_only
            )
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def sde_finalize_review_projection(receipt_id: str) -> str:
        """Finalize approved destinations before cleanup can proceed."""

        return json_result(
            api.sde_finalize_review_projection(caller, project_id, receipt_id)
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def artifact_inventory_complete(
        receipt_id: str,
        artifacts: list[ArtifactInput],
        dependency_map_sha256: str,
    ) -> str:
        """Finalize an exact artifact inventory after review authorization."""

        return json_result(
            api.artifact_inventory_complete(
                caller,
                project_id,
                receipt_id,
                parse_artifacts(artifacts),
                dependency_map_sha256,
            )
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def artifact_cleanup_approve(
        receipt_id: str,
        artifacts: list[ArtifactInput],
        manifest_sha256: str,
        dependency_map_sha256: str,
        target: str,
    ) -> str:
        """Record compatibility cleanup approval for an exact manifest."""

        authorization, receipt = api.authorize_artifact_cleanup(
            caller,
            project_id,
            ArtifactCleanupAuthorizationRequest(
                receipt_id=receipt_id,
                artifacts=parse_artifacts(artifacts),
                manifest_sha256=manifest_sha256,
                dependency_map_sha256=dependency_map_sha256,
                target=target,
            ),
        )
        return json_result({"authorization": authorization, "receipt": receipt})

    @read_tool()
    def artifact_purge_status(receipt_id: str) -> str:
        """Read receipt-level and per-artifact purge state and retry metadata."""

        return json_result(api.artifact_purge_status(caller, project_id, receipt_id))

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def release_artifact_hold(receipt_id: str, path: str, rationale: str) -> str:
        """Audibly release one exact hold; eligible purge resumes immediately."""

        return json_result(
            api.release_artifact_hold(caller, project_id, receipt_id, path, rationale)
        )

    @safe_tool(
        annotations=ToolAnnotations(
            destructive_hint=True, idempotent_hint=True, open_world_hint=False
        )
    )
    def retry_pending_purges() -> str:
        """Retry only project-local reviewed and canonically persisted manifests."""

        return json_result(api.retry_pending_purges(caller, project_id))
