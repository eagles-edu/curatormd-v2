"""Install Curator V2's native Codex hooks in the local user configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from typing import Any


MAX_CONFIG_BYTES = 64 * 1024
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOKS_FILE = PLUGIN_ROOT / "hooks" / "hooks.json"
_HOOK_SCRIPTS = frozenset({
    "user_prompt_submit.py",
    "lifecycle_pre_tool.py",
    "lifecycle_post_tool.py",
    "lifecycle_stop.py",
})


def _read_config(path: Path) -> dict[str, Any]:
    """Read a bounded owner-only hook file, preserving unrelated hooks."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
            or metadata.st_size > MAX_CONFIG_BYTES
        ):
            raise ValueError("Codex hook file must be a private owner-owned file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("Codex hook file exceeds its size limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Codex hook file must contain a JSON object")
    return value


def _ensure_data_directory(codex_home: Path) -> Path:
    """Create an owner-only directory for V2's bounded per-turn hook state."""

    directory = codex_home / "curator-v2-data"
    directory.mkdir(mode=0o700, exist_ok=True)
    metadata = directory.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ValueError("Curator V2 hook state directory must be private")
    return directory


def _hook_groups(data_directory: Path) -> dict[str, list[dict[str, Any]]]:
    """Load the plugin's four hook definitions for native Codex CLI use."""

    decoded = json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict) or not isinstance(decoded.get("hooks"), dict):
        raise ValueError("Curator V2 hook definitions are invalid")
    groups = decoded["hooks"]
    result: dict[str, list[dict[str, Any]]] = {}
    for event_name, entries in groups.items():
        if not isinstance(event_name, str) or not isinstance(entries, list):
            raise ValueError("Curator V2 hook definitions are invalid")
        native_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise ValueError("Curator V2 hook definitions are invalid")
            native_entry = dict(entry)
            handlers: list[dict[str, Any]] = []
            for handler in entry["hooks"]:
                if (
                    not isinstance(handler, dict)
                    or not isinstance(handler.get("command"), str)
                ):
                    raise ValueError("Curator V2 hook definitions are invalid")
                native_handler = dict(handler)
                command = native_handler["command"]
                matched_script = next(
                    (name for name in _HOOK_SCRIPTS if command.endswith(f"/hooks/{name}")),
                    None,
                )
                if matched_script is None:
                    raise ValueError("Curator V2 hook command is not recognized")
                script = PLUGIN_ROOT / "hooks" / matched_script
                native_handler["command"] = (
                    f"PLUGIN_DATA={shlex.quote(str(data_directory))} "
                    f"python3 {shlex.quote(str(script.resolve()))}"
                )
                handlers.append(native_handler)
            native_entry["hooks"] = handlers
            native_entries.append(native_entry)
        result[event_name] = native_entries
    return result


def _is_v2_handler(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = handler.get("command")
    return isinstance(command, str) and any(
        f"/hooks/{name}" in command for name in _HOOK_SCRIPTS
    )


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    """Replace only the hook JSON with an owner-only atomic write."""

    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".curator-v2-hooks-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def install_user_hook(codex_home: Path | None = None) -> bool:
    """Install all native V2 hooks; preserve unrelated handlers and be repeatable."""

    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    home = home.expanduser().resolve(strict=True)
    if not home.is_dir() or home.stat().st_uid != os.geteuid():
        raise ValueError("Codex home must be an owner-owned directory")
    data_directory = _ensure_data_directory(home)
    path = home / "hooks.json"
    if path.exists() or path.is_symlink():
        config = _read_config(path)
    else:
        config = {}
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Codex hook configuration has an invalid hooks field")
    before = json.dumps(config, sort_keys=True, separators=(",", ":"))
    definitions = _hook_groups(data_directory)
    for event_name, new_groups in definitions.items():
        old_groups = hooks.setdefault(event_name, [])
        if not isinstance(old_groups, list) or any(
            not isinstance(group, dict) or not isinstance(group.get("hooks", []), list)
            for group in old_groups
        ):
            raise ValueError(f"Codex {event_name} hook configuration is invalid")
        preserved: list[dict[str, Any]] = []
        for old_group in old_groups:
            handlers = old_group.get("hooks", [])
            remaining = [handler for handler in handlers if not _is_v2_handler(handler)]
            if remaining:
                preserved.append({**old_group, "hooks": remaining})
        hooks[event_name] = preserved + new_groups
    after = json.dumps(config, sort_keys=True, separators=(",", ":"))
    if before == after:
        return False
    _atomic_write(path, config)
    return True


def main() -> int:
    """Install the current checkout's hook without echoing configuration."""

    try:
        changed = install_user_hook()
    except (OSError, ValueError, json.JSONDecodeError):
        sys.stderr.write("Curator V2 Codex hook installation failed safely.\n")
        return 2
    sys.stdout.write(
        "Curator V2 Codex hooks installed.\n"
        if changed
        else "Curator V2 Codex hooks already installed.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
