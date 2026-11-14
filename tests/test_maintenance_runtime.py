"""Check runtime selection without opening a writable project ledger."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy/systemd/user/maintenance-runtime.py"


class MaintenanceRuntimeTests(unittest.TestCase):
    def test_stale_runtime_uses_compatible_fallback_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "ledger.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.execute("PRAGMA user_version=48")
            def runtime(name: str, version: int) -> str:
                folder = root / name / "bin"
                folder.mkdir(parents=True)
                python = folder / "python"
                python.write_text(f"#!/bin/sh\necho {version}\n")
                python.chmod(0o755)
                binary = folder / "curatormd-v2-maintenance"
                binary.write_text("#!/bin/sh\nprintf 'selected:%s\\n' \"$1\"\n")
                binary.chmod(0o755)
                return str(binary)
            env = dict(os.environ, CURATORMD_V2_DATABASE=str(database),
                       CURATORMD_V2_MAINTENANCE_BIN=runtime("old", 47),
                       CURATORMD_V2_MAINTENANCE_FALLBACK_BIN=runtime("new", 48))
            command = [sys.executable, str(SCRIPT), "--execute-due-purges"]
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "selected:--execute-due-purges")
            self.assertIn("fallback runtime", result.stderr)
            env["CURATORMD_V2_MAINTENANCE_FALLBACK_BIN"] = env["CURATORMD_V2_MAINTENANCE_BIN"]
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("no compatible runtime", result.stderr)


if __name__ == "__main__":
    unittest.main()
