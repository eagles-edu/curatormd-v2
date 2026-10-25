"""Capture CLI emits only an owner-scoped browser evidence reference."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from project_fixtures import create_consumer_repo, write_consumer_config
from curatormd_v2.evidence_cli import main


class EvidenceCaptureCliTests(unittest.TestCase):
    """Keep browser output content-free and host config outside the consumer."""

    def test_browser_capture_prints_only_the_compact_evidence_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_root = create_consumer_repo(root / "project")
            write_consumer_config(project_root, "vhost-manager-alpha")
            (project_root / "docs" / "tasks.md").write_text("- [ ] local task\n")
            (project_root / "persistence" / "HISTORY.md").write_text("# History\n")
            browser = root / "system-browser-fixture"
            browser.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "sys.stdout.write('<main>PRIVATE_CAPTURE_CANARY</main>')\n",
                encoding="utf-8",
            )
            browser.chmod(0o700)
            host_config = root / "host-evidence.json"
            host_config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "project_id": "vhost-manager-alpha",
                        "browser_proof": {
                            "adapter_id": "local-browser",
                            "proof_id": "vhost-home",
                            "url": "http://127.0.0.1:8700/",
                            "executable": str(browser),
                        },
                    }
                ),
                encoding="utf-8",
            )
            host_config.chmod(0o600)
            output = StringIO()
            with patch("sys.stdout", output):
                status = main(
                    [
                        "browser",
                        "--project-root",
                        str(project_root),
                        "--host-config",
                        str(host_config),
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["evidence_kind"], "browser")
        self.assertEqual(payload["locator"], "browser-proof:vhost-home")
        self.assertEqual(payload["outcome"], "passed")
        self.assertNotIn("PRIVATE_CAPTURE_CANARY", output.getvalue())


if __name__ == "__main__":
    unittest.main()
