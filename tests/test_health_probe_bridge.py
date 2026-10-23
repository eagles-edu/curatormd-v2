"""Trust-boundary tests for host-injected health observations."""

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
