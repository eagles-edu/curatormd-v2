"""The stdio launcher forwards host-only evidence config to its builder."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from curatormd_v2 import hosted_mcp


class HostedMcpEvidenceConfigCliTests(
    unittest.TestCase
):  # pylint: disable=too-few-public-methods
    """CLI config reaches the host builder without starting a real server."""

    def test_main_forwards_evidence_config_and_closes_runtime(self) -> None:
        evidence_config = Path("/home/test/.hermes/curator-evidence.json")
        server = Mock()
        close = Mock()
        runtime = SimpleNamespace(server=server, close=close)
        arguments = [
            "--project-root",
            "/tmp/consumer",
            "--database",
            "/tmp/curator.sqlite3",
            "--profile-id",
            "test-profile",
            "--evidence-config",
            str(evidence_config),
        ]

        with patch.object(
            hosted_mcp, "build_local_profile_mcp", return_value=runtime
        ) as builder:
            exit_code = hosted_mcp.main(arguments)

        self.assertEqual(exit_code, 0)
        self.assertEqual(builder.call_args.kwargs["evidence_config"], evidence_config)
        server.run.assert_called_once_with()
        close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
