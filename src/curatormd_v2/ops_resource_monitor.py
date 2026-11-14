"""Read resource limits and usage for the resident Curator operations service."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess  # nosec B404
import time
from typing import Any, cast
from zoneinfo import ZoneInfo

MAX_HISTORY_LINE_BYTES = 8192
HISTORY_FRESHNESS_SECONDS = 180


def _systemd_properties(service_name: str) -> dict[str, str] | None:
    """Fetch a bounded property snapshot for one exact user service."""
    try:
        result = subprocess.run(
            [
                "/usr/bin/systemctl",
                "--user",
                "show",
                service_name,
                "-p",
                "ActiveState",
                "-p",
                "ActiveEnterTimestampMonotonic",
                "-p",
                "CPUUsageNSec",
                "-p",
                "MemoryCurrent",
                "-p",
                "MemoryMax",
            ],  # nosec B603
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        if result.returncode != 0:
            return None
        properties: dict[str, str] = {}
        for line in result.stdout.decode("ascii", errors="replace").splitlines():
            name, separator, value = line.partition("=")
            if separator:
                properties[name] = value
        return properties
    except (OSError, subprocess.TimeoutExpired):
        return None


def monitor_status(service_name: str) -> dict[str, Any]:
    """Read service state and measured lifetime resource use from systemd."""
    properties = _systemd_properties(service_name)
    if properties is None:
        return {"status": "unknown"}
    try:
        if properties.get("ActiveState") != "active":
            return {"status": "inactive"}
        active_since_usec = int(properties["ActiveEnterTimestampMonotonic"])
        cpu_ns = int(properties["CPUUsageNSec"])
        memory_bytes = int(properties["MemoryCurrent"])
        memory_limit_bytes = int(properties["MemoryMax"])
        elapsed_seconds = max(
            0.0,
            (time.monotonic_ns() // 1000 - active_since_usec) / 1_000_000,
        )
        average_cpu_percent = (
            cpu_ns / (elapsed_seconds * 1_000_000_000) * 100 if elapsed_seconds > 0 else 0.0
        )
        average_cpu_status = (
            "warming_up"
            if elapsed_seconds < 300
            else "healthy"
            if average_cpu_percent <= 1.0
            else "over_target"
        )
        memory_status = "healthy" if memory_bytes <= memory_limit_bytes else "over_limit"
        healthy = memory_status == "healthy" and average_cpu_status != "over_target"
        return {
            "status": "healthy" if healthy else "degraded",
            "resource": {
                "elapsed_seconds": round(elapsed_seconds, 1),
                "average_cpu_percent": round(average_cpu_percent, 3),
                "average_cpu_status": average_cpu_status,
                "memory_current_bytes": memory_bytes,
                "memory_limit_bytes": memory_limit_bytes,
                "memory_status": memory_status,
            },
        }
    except (KeyError, ValueError):
        return {"status": "unknown"}


def unit_active_status(unit_name: str) -> dict[str, str]:
    """Return the live state of one fixed-name systemd user unit."""
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "--user", "is-active", unit_name],  # nosec B603
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        active = result.returncode == 0 and result.stdout.strip() == b"active"
        return {"status": "healthy" if active else "inactive"}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unknown"}


def record_check(result: dict[str, Any], state: Path, owner_uid: int) -> None:
    """Append a small private health/resource sample for 24-hour acceptance."""
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    sample = {
        "checked_at": result.get("checked_at"),
        "status": result.get("status"),
        "gates": result.get("gates", []),
        "incident_id": result.get("incident_id"),
        "monitor": result.get("components", {}).get("monitor", {}),
    }
    day = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    path = state / f"checks-{day}.jsonl"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        metadata = os.fstat(descriptor)
        if metadata.st_uid != owner_uid or metadata.st_mode & 0o077:
            raise PermissionError("health history must remain owner-private")
        payload = (json.dumps(sample, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with os.fdopen(descriptor, "ab", closefd=False) as stream:
            stream.write(payload)
    finally:
        os.close(descriptor)


def acceptance_history_status(
    state: Path,
    owner_uid: int,
    *,
    max_age_seconds: int = HISTORY_FRESHNESS_SECONDS,
    allow_missing: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate private daily acceptance history and its latest sample."""
    try:
        state_metadata = state.lstat()
    except FileNotFoundError:
        if allow_missing:
            return {
                "status": "healthy", "phase": "warming_up", "age_seconds": None,
                "samples_checked": 0,
            }
        return {"status": "missing", "reason": "history_directory_missing", "age_seconds": None}
    except OSError:
        return {"status": "unavailable", "reason": "history_directory_unavailable"}
    if (
        not stat.S_ISDIR(state_metadata.st_mode)
        or state.is_symlink()
        or state_metadata.st_uid != owner_uid
        or state_metadata.st_mode & 0o077
    ):
        return {"status": "permissions", "reason": "history_directory_permissions_invalid"}
    files = sorted(state.glob("checks-*.jsonl"))
    for path in files:
        if not re.fullmatch(r"checks-\d{4}-\d{2}-\d{2}\.jsonl", path.name):
            return {"status": "malformed", "reason": "history_filename_malformed"}
        try:
            metadata = path.lstat()
            if (
                not path.is_file()
                or path.is_symlink()
                or metadata.st_uid != owner_uid
                or metadata.st_mode & 0o077
            ):
                return {"status": "permissions", "reason": "history_permissions_invalid"}
        except OSError:
            return {"status": "unavailable", "reason": "history_stat_failed"}

    current = now or datetime.now(timezone.utc)
    local_day = current.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
    current_path = state / f"checks-{local_day}.jsonl"
    if current_path not in files:
        if allow_missing:
            return {
                "status": "healthy", "phase": "warming_up", "age_seconds": None,
                "samples_checked": 0,
            }
        return {"status": "missing", "reason": "history_missing", "age_seconds": None}

    latest: datetime | None = None
    samples_checked = 0
    try:
        descriptor = os.open(current_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != owner_uid
                or opened.st_mode & 0o077
            ):
                return {"status": "permissions", "reason": "history_permissions_invalid"}
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                while True:
                    line = stream.readline(MAX_HISTORY_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_HISTORY_LINE_BYTES or not line.endswith(b"\n"):
                        return {"status": "malformed", "reason": "history_line_invalid"}
                    try:
                        parsed: Any = json.loads(line)
                        if not isinstance(parsed, dict):
                            raise ValueError("sample is not an object")
                        sample = cast(dict[str, Any], parsed)
                        checked_at = datetime.fromisoformat(
                            str(sample["checked_at"]).replace("Z", "+00:00")
                        )
                        if checked_at.tzinfo is None:
                            raise ValueError("sample timestamp has no timezone")
                        if (
                            sample.get("status") not in {"healthy", "degraded"}
                            or not isinstance(sample.get("gates"), list)
                            or any(not isinstance(gate, str) for gate in sample["gates"])
                            or not isinstance(sample.get("monitor"), dict)
                            or sample.get("incident_id") is not None
                            and not isinstance(sample.get("incident_id"), str)
                            or latest is not None and checked_at < latest
                        ):
                            raise ValueError("sample fields are invalid")
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                        return {"status": "malformed", "reason": "history_sample_invalid"}
                    latest = checked_at
                    samples_checked += 1
        finally:
            os.close(descriptor)
    except OSError:
        return {"status": "unavailable", "reason": "history_read_failed"}

    if latest is None:
        return {"status": "malformed", "reason": "history_empty"}
    age = int((current.astimezone(timezone.utc) - latest.astimezone(timezone.utc)).total_seconds())
    if age < -5:
        return {"status": "malformed", "reason": "history_timestamp_in_future"}
    age = max(0, age)
    if age > max_age_seconds:
        return {
            "status": "stale",
            "reason": "history_stale",
            "age_seconds": age,
            "samples_checked": samples_checked,
        }
    return {
        "status": "healthy",
        "age_seconds": age,
        "checked_at": latest.isoformat(),
        "samples_checked": samples_checked,
    }
