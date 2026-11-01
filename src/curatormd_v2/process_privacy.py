"""Process-level privacy controls for local Curator V2 command entrypoints."""

from __future__ import annotations

import ctypes
import os
import sys


_PR_SET_DUMPABLE = 4


def _disable_linux_dumpability() -> bool:
    """Disable kernel core collection when Linux pipes dumps to a handler."""

    if not sys.platform.startswith("linux"):
        return True
    try:
        prctl = ctypes.CDLL(None, use_errno=True).prctl
    except (AttributeError, OSError):
        return False
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    prctl.restype = ctypes.c_int
    return prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) == 0


def disable_core_dumps() -> bool:
    """Disable core dumps before a command handles ledger or artifact data."""

    if os.name != "posix":
        return False
    try:
        import resource
    except ImportError:
        return False
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (OSError, ValueError):
        return False
    return _disable_linux_dumpability()


def protect_process_data() -> bool:
    """Disable core dumps and make newly created files owner-only."""

    if not disable_core_dumps():
        return False
    try:
        os.umask(0o077)
    except (OSError, ValueError):
        return False
    return True
