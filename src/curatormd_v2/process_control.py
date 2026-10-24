"""Shared bounded subprocess cleanup for local evidence adapters."""

from __future__ import annotations

import os
import signal
import subprocess  # nosec B404


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Kill one runner and its children, falling back to the direct process."""

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        try:
            process.kill()
        except OSError:
            pass
