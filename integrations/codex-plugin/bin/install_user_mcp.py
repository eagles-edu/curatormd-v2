"""Register the global Codex MCP server with the active workspace as cwd."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tomllib
from typing import Any


SERVER_NAME = "codex-intake"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PLUGIN_ROOT / "bin" / "launch-curator-mcp.py"
DEFAULT_DATABASE = (
    Path.home() / ".local" / "share" / "curatormd-v2-alpha" / "global.sqlite3"
)


def _expected_transport(database: Path) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": "python3",
        "args": [
            str(LAUNCHER),
            "--database",
            str(database),
            "--allow-write",
        ],
        "cwd": None,
    }


def _get_server() -> dict[str, Any] | None:
    result = subprocess.run(
        ["codex", "mcp", "get", SERVER_NAME, "--json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return None
    value: object = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("Codex returned an invalid MCP server record")
    return value


def _has_user_server() -> bool:
    """Check only user registrations; the plugin may expose the same name."""

    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    path = home / "config.toml"
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return False
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_size > 1024 * 1024
        ):
            raise ValueError("Codex user config is not an expected owner-owned file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024:
            raise ValueError("Codex user config exceeds its size limit")
        config = tomllib.loads(content.decode("utf-8"))
    finally:
        os.close(descriptor)
    servers = config.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("Codex user MCP configuration is invalid")
    return SERVER_NAME in servers


def _matches_expected(existing: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Compare launch fields while allowing Codex's default empty fields."""

    transport = existing.get("transport")
    if not isinstance(transport, dict):
        return False
    return (
        existing.get("enabled") is True
        and all(transport.get(key) == value for key, value in expected.items())
        and transport.get("env") is None
        and transport.get("env_vars") == []
    )


def install_user_mcp(database: Path | None = None) -> bool:
    """Add or verify the workspace-relative global server without overwrites."""

    selected_database = database or Path(
        os.environ.get("CURATOR_V2_DATABASE", str(DEFAULT_DATABASE))
    )
    if not selected_database.is_absolute():
        raise ValueError("Curator V2 database path must be absolute")
    selected_database = selected_database.expanduser()
    expected = _expected_transport(selected_database)
    if _has_user_server():
        existing = _get_server()
        if existing is None:
            raise ValueError("Codex user MCP server could not be read")
        if _matches_expected(existing, expected):
            return False
        raise ValueError(
            "Codex already has a different codex-intake user server; review it before replacing"
        )

    subprocess.run(
        [
            "codex",
            "mcp",
            "add",
            SERVER_NAME,
            "--",
            "python3",
            str(LAUNCHER),
            "--database",
            str(selected_database),
            "--allow-write",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    saved = _get_server()
    if saved is None or not _matches_expected(saved, expected):
        raise RuntimeError("Codex did not save the expected Curator V2 MCP server")
    return True


def main() -> int:
    """Install the account-level MCP entry without displaying config contents."""

    try:
        changed = install_user_mcp()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
        sys.stderr.write("Curator V2 Codex MCP installation failed safely.\n")
        return 2
    sys.stdout.write(
        "Curator V2 Codex MCP installed with active-workspace discovery.\n"
        if changed
        else "Curator V2 Codex MCP already installed for active-workspace discovery.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
