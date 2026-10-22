"""Shared typed parsing and safe result handling for Curator V2 MCP tools."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import wraps
import json
import logging
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from mcp.types import CallToolResult, TextContent

from .errors import safe_exception_label, to_api_error
from .models import (
    ArtifactRef,
    EvidenceOutcome,
    EvidenceRef,
    RetentionHoldKind,
    SuccessCriterion,
)

logger = logging.getLogger("curatormd_v2.mcp_server")

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

class ArtifactInput(TypedDict):
    """MCP artifact manifest entry with an optional explicit retention hold."""

    path: str
    sha256: str
    retention_hold: NotRequired[str | None]

def parse_criteria(values: list[dict[str, str]]) -> tuple[SuccessCriterion, ...]:
    """Parse the exact compact criterion objects accepted by MCP tools."""

    criteria: list[SuccessCriterion] = []
    for value in values:
        if set(value) != {"criterion_id", "description"}:
            raise ValueError("criteria require exactly criterion_id and description")
        criteria.append(SuccessCriterion(value["criterion_id"], value["description"]))
    return tuple(criteria)

def parse_evidence(values: list[dict[str, str]]) -> tuple[EvidenceRef, ...]:
    """Parse evidence references while rejecting extra fields."""

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

def parse_artifacts(values: list[ArtifactInput]) -> tuple[ArtifactRef, ...]:
    """Parse exact artifact paths, digests, and optional typed holds."""

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

def json_result(value: object) -> str:
    """Serialize one bounded domain result using the MCP wire representation."""

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
