"""Keep malformed command-line values out of every V2 CLI error."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
from typing import Callable, TextIO
import unittest

from curatormd_v2.access_cli import main as access_main
from curatormd_v2.evidence_cli import main as evidence_main
from curatormd_v2.hosted_mcp import main as hosted_mcp_main
from curatormd_v2.maintenance_cli import main as maintenance_main
from curatormd_v2.producer_cli import main as producer_main
from curatormd_v2.review_cli import main as review_main
from curatormd_v2.router_cli import main as router_main
from curatormd_v2.storage_cli import main as storage_main


def _run_evidence(argv: list[str], errors: TextIO) -> int:
    with redirect_stderr(errors):
        return evidence_main(argv)


def _run_hosted_mcp(argv: list[str], errors: TextIO) -> int:
    with redirect_stderr(errors):
        return hosted_mcp_main(argv)


class CliArgumentPrivacyTests(unittest.TestCase):
    """Reject malformed argv without reflecting its caller-controlled text."""

    def test_every_v2_cli_uses_a_fixed_error_for_malformed_arguments(self) -> None:
        marker = "credential-canary-argument-value"
        argv = [f"--unrecognized={marker}"]
        commands: tuple[tuple[str, Callable[[list[str], TextIO], int]], ...] = (
            ("access", lambda args, err: access_main(args, stderr=err)),
            ("evidence", _run_evidence),
            ("hosted-mcp", _run_hosted_mcp),
            ("maintenance", lambda args, err: maintenance_main(args, stderr=err)),
            ("producer", lambda args, err: producer_main(args, stderr=err)),
            ("review", lambda args, err: review_main(args, stderr=err)),
            ("router", lambda args, err: router_main(args, stderr=err)),
            ("storage", lambda args, err: storage_main(args, stderr=err)),
        )

        for name, run in commands:
            with self.subTest(command=name):
                errors = StringIO()
                self.assertEqual(run(argv, errors), 2)
                self.assertNotIn(marker, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
