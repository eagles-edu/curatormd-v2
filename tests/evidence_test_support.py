"""Shared local-evidence fixture builders for the CLI and config tests."""

from __future__ import annotations


def local_service_probe_config(
    *,
    source_subject: str,
    command: list[str],
    working_directory: str,
) -> dict[str, object]:
    """Build the common host-owned service-probe fixture shape."""

    return {
        "schema_version": 1,
        "project_id": "vhost-manager-alpha",
        "probe": {
            "adapter_id": "local-readiness",
            "probe_id": "readiness",
            "source_subject": source_subject,
            "command": command,
            "working_directory": working_directory,
        },
    }
