"""Launch the editable V2 MCP entry point from the local plugin package."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


def _v2_mcp_path() -> Path | None:
    """Resolve the owner-configured or installed V2 executable."""

    configured = os.environ.get("CURATOR_V2_CODEX_MCP")
    if configured is not None:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() else None
    installed = shutil.which("curatormd-v2-codex-mcp")
    if installed is not None:
        return Path(installed)
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / ".venv" / "bin" / "curatormd-v2-codex-mcp"


def main() -> int:
    """Replace this wrapper with the configured local V2 MCP process."""

    v2_mcp = _v2_mcp_path()
    if v2_mcp is None or not v2_mcp.is_file() or not os.access(v2_mcp, os.X_OK):
        sys.stderr.write("Curator V2 local MCP launcher is unavailable.\n")
        return 2
    try:
        os.execv(str(v2_mcp), [str(v2_mcp), *sys.argv[1:]])
    except OSError:
        sys.stderr.write("Curator V2 local MCP launcher could not start.\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
