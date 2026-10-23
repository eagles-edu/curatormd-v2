"""Trust-boundary tests for host-injected health observations."""

import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path

from mcp import Client
from mcp.types import TextContent

from project_fixtures import bind_test_project, configure_stdio_consumer

from curatormd_v2 import CuratorStore
from curatormd_v2.hosted_mcp import build_local_profile_mcp
from curatormd_v2.mcp_server import (
    RequestHostReadiness,
    host_readiness_context,
    validate_host_readiness,
)
from curatormd_v2.models import DependencyProbeObservation

def test_trusted_host_readiness_metadata_is_bounded_and_request_local():
    timestamp = "2026-10-23T00:00:00+00:00"
    readiness = validate_host_readiness(
        {
            "hermes/readiness": {
                "event_router": {"ready": True, "observed_at": timestamp},
                "purge_scheduler": {"ready": False, "observed_at": timestamp},
                "unexpected": {"ready": True, "observed_at": timestamp},
                "human_review": {"ready": "yes", "observed_at": timestamp},
            }
        }
    )
    token = host_readiness_context.set(readiness)
    try:
        current = RequestHostReadiness().readiness("mcp-project")
        assert set(current) == {"event_router", "purge_scheduler"}
        router = current["event_router"]
        scheduler = current["purge_scheduler"]
        assert isinstance(router, DependencyProbeObservation)
        assert isinstance(scheduler, DependencyProbeObservation)
        assert router.ready is True
        assert scheduler.ready is False
    finally:
        host_readiness_context.reset(token)
    assert RequestHostReadiness().readiness("mcp-project") == {}


def test_health_tool_uses_all_host_probes_and_reports_degraded_not_unknown(
    tmp_path: Path,
):
    project_root = tmp_path / "consumer"
    configure_stdio_consumer(project_root, "mcp-project")
    database = tmp_path / "global.sqlite3"
    setup_store = CuratorStore(database)
    bind_test_project(setup_store, project_root, "profile-a")
    setup_store.close()
    runtime = build_local_profile_mcp(
        project_root=project_root,
        database=database,
        profile_id="profile-a",
    )
    observed_at = datetime.now(UTC).isoformat()
    readiness = {
        name: {"ready": name not in {"purge_scheduler", "alert_delivery"},
               "observed_at": observed_at}
        for name in (
            "event_router",
            "purge_scheduler",
            "database_storage_adapter",
            "alert_delivery",
            "host_identity",
            "human_review",
            "artifact_producer_inventory",
        )
    }

    async def call_health():
        async with Client(runtime.server, raise_exceptions=True) as client:
            return await client.call_tool(
                "project_health",
                {},
                meta={
                    "hermes/profile_id": "profile-a",
                    "hermes/session_id": "health-probe-session",
                    "hermes/readiness": readiness,
                },
            )

    try:
        result = asyncio.run(call_health())
    finally:
        runtime.close()

    assert not result.is_error
    content = result.content[0]
    assert isinstance(content, TextContent)
    health = json.loads(content.text)
    assert health["status"] == "degraded"
    assert "dependency_unavailable:purge_scheduler" in health["gate_codes"]
    assert "dependency_unavailable:alert_delivery" in health["gate_codes"]
    assert not any(code.startswith("dependency_unknown:") for code in health["gate_codes"])
