"""Project-bound Curator V2 operations, incident capture, and monitor loop."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import sqlite3
import stat
import subprocess  # nosec B404
import sys
import time
import uuid
from typing import Any, cast
import tomllib

from .schema_migrations import SQLITE_SCHEMA_VERSION
from .ops_resource_monitor import acceptance_history_status, monitor_status, record_check
from .ops_schedule import (
    maintenance_due,
    maintenance_timer_status,
    read_maintenance_timestamp,
)
from .ops_health import HEALTH_NAMES, summarize_health
from .ops_runtime import runtime_status, source_fingerprint

JsonObject = dict[str, Any]

PROJECT_ID = "curatormd-v2-dev-alpha"
PROFILE_ID = "curatormd-v2-dev-alpha"
ROOT = Path(__file__).resolve().parents[2]
UID = 1000
DATABASE = Path.home() / ".local/share/curatormd-v2-alpha/global.sqlite3"
MANIFEST = Path.home() / ".config/curatormd-v2/ops-curatormd-v2-dev-alpha.json"
STATE = Path.home() / ".local/state/curatormd-v2/curatormd-v2-dev-alpha/ops"
INCIDENTS = STATE / "incidents"
LOCK = STATE / "monitor.lock"
MAX_PROBE_SECONDS = 60
MAX_AI_SECONDS = 300
MAX_AI_TOKENS = 24000
AI_RETRY_BASE_SECONDS = 300
AI_RETRY_MAX_SECONDS = 21600
AI_RETRYABLE_STATUSES = frozenset({
    "failed",
    "timeout",
    "dispatch_failed",
    "codex_unavailable",
})
AI_BUDGET_WARNING_CODES = frozenset({
    "token_budget_exhausted",
    "token_budget_unobservable",
})
CODEX = Path.home() / ".nvm/versions/node/v24.21.0/bin/codex"
HERMES_CHECKOUT = Path.home() / ".hermes/hermes-agent"
HERMES_PYTHON = HERMES_CHECKOUT / ".venv/bin/python"
HERMES_PROBE_CODE = (
    "import sys; "
    f"sys.path.insert(0, {str(HERMES_CHECKOUT)!r}); "
    "from types import SimpleNamespace; "
    "from hermes_cli.mcp_test_command import cmd_mcp_test; "
    "raise SystemExit(cmd_mcp_test(SimpleNamespace("
    "name='curator_v2', json_output=True, probe_curator_status=True)))"
)
SOURCE_FINGERPRINT_AT_IMPORT = source_fingerprint(ROOT)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    """Hash a file with bounded memory use."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, mode)
    os.replace(temp, path)


def _load_object(data: str | bytes) -> JsonObject:
    parsed: Any = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError("expected JSON object")
    return cast(JsonObject, parsed)


def _manifest_expected() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_id": PROJECT_ID,
        "os_uid": UID,
        "repository_root": str(ROOT),
        "database": str(DATABASE),
        "hermes_profile": PROFILE_ID,
        "health_command": [
            str(HERMES_PYTHON),
            "-c",
            HERMES_PROBE_CODE,
        ],
        "maintenance_command": [str(ROOT / ".venv/bin/curatormd-v2-maintenance")],
        "maintenance_interval_seconds": 21600,
        "monitor_interval_seconds": 60,
        "monitor_memory_max_bytes": 67108864,
        "ai_timeout_seconds": MAX_AI_SECONDS,
        "ai_token_budget": MAX_AI_TOKENS,
        "codex_command": [str(CODEX)],
        "backup_retention_days": 30,
    }


def ensure_manifest() -> None:
    """Create initial binding authority once; never rewrite a conflicting one."""
    if MANIFEST.exists():
        return
    _json(MANIFEST, _manifest_expected())
    os.chmod(MANIFEST, 0o600)


def _read_manifest() -> tuple[dict[str, Any] | None, str | None]:
    try:
        st = MANIFEST.stat(follow_symlinks=False)
        if not MANIFEST.is_file() or st.st_uid != os.getuid() or st.st_mode & 0o077:
            return None, "manifest_permissions"
        value = _load_object(MANIFEST.read_text(encoding="utf-8"))
        expected = _manifest_expected()
        # AI runtime limits are bounded by this installed source, not by the
        # owner manifest. Older manifests may retain the former, looser limits;
        # treating those tuning values as project identity blocks health checks
        # even though execution already clamps to MAX_AI_SECONDS/MAX_AI_TOKENS.
        value_binding = {key: item for key, item in value.items() if key not in {
            "ai_timeout_seconds",
            "ai_token_budget",
        }}
        expected_binding = {key: item for key, item in expected.items() if key not in {
            "ai_timeout_seconds",
            "ai_token_budget",
        }}
        if value_binding != expected_binding:
            return value, "binding_conflict"
        if os.getuid() != UID:
            return value, "os_uid_mismatch"
        return value, None
    except FileNotFoundError:
        return None, "manifest_missing"
    except (OSError, ValueError, json.JSONDecodeError):
        return None, "manifest_malformed"


def _probe_database() -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unknown", "schema_version": None}
    if not DATABASE.is_file() or DATABASE.is_symlink():
        result["status"] = "database_missing"
        return result
    uri = f"file:{DATABASE.as_posix()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            schema = connection.execute("PRAGMA user_version").fetchone()[0]
        result.update(
            {
                "schema_version": schema,
                "integrity": "ok" if integrity == "ok" else "failed",
                "schema": "compatible" if schema == SQLITE_SCHEMA_VERSION else "mismatch",
            }
        )
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
                foreign = connection.execute("PRAGMA foreign_key_check").fetchmany(2)
        except sqlite3.OperationalError as exc:
            mismatch = "foreign key mismatch" in str(exc).lower()
            result["foreign_keys"] = "schema_mismatch" if mismatch else "failed"
            result["foreign_key_schema_mismatch"] = mismatch
        else:
            result["foreign_keys"] = "ok" if not foreign else "failed"
            result["foreign_key_violation_count"] = len(foreign)
        result["status"] = (
            "healthy"
            if result.get("integrity") == "ok"
            and result.get("foreign_keys") == "ok"
            and schema == SQLITE_SCHEMA_VERSION
            else "degraded"
        )
    except sqlite3.Error as exc:
        result["status"] = "database_error"
        result["error"] = getattr(exc, "sqlite_errorname", "SQLITE_ERROR")
    return result


def _event_failure_status() -> dict[str, Any]:
    """Inventory bounded failed-event metadata without reading event payloads."""
    if not DATABASE.is_file() or DATABASE.is_symlink():
        return {"status": "unavailable", "count": None, "events": []}
    uri = f"file:{DATABASE.as_posix()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
            count = connection.execute(
                """SELECT COUNT(*) FROM event_inbox
                   WHERE project_id = ? AND status IN ('failed', 'quarantined')""",
                (PROJECT_ID,),
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT event_id, status, event_type, source_id,
                          source_sequence, payload_sha256, attempts, last_error
                   FROM event_inbox WHERE project_id = ?
                     AND status IN ('failed', 'quarantined')
                   ORDER BY received_at, event_id LIMIT 50""",
                (PROJECT_ID,),
            ).fetchall()
        events = []
        for row in rows:
            event_id = (
                row[0] if isinstance(row[0], str) and len(row[0]) <= 128
                else "invalid"
            )
            event_type = (
                row[2] if isinstance(row[2], str) and len(row[2]) <= 128
                else "invalid"
            )
            source_id = (
                row[3] if isinstance(row[3], str) and len(row[3]) <= 128
                else "invalid"
            )
            payload_hash = (
                row[5] if isinstance(row[5], str)
                and re.fullmatch(r"[0-9a-f]{64}", row[5]) else None
            )
            raw_error = row[7]
            error_code = (
                raw_error[:64]
                if isinstance(raw_error, str)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", raw_error)
                else "unclassified"
            )
            events.append({
                "event_id": event_id,
                "status": row[1],
                "event_type": event_type,
                "source_id": source_id,
                "source_sequence": row[4],
                "payload_sha256": payload_hash,
                "attempts": row[6],
                "error_code": error_code,
            })
        return {
            "status": "healthy" if count == 0 else "degraded",
            "count": count,
            "inventory_complete": count <= len(events),
            "events": events,
        }
    except (OSError, sqlite3.Error, TypeError, IndexError):
        return {"status": "unavailable", "count": None, "events": []}


def _dashboard_telemetry_status() -> dict[str, Any]:
    """Read the content-free, profile-bound VS Code dashboard handoff."""
    path = STATE / "dashboard-telemetry.json"
    try:
        directory = STATE.stat(follow_symlinks=False)
        metadata = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != UID
            or directory.st_mode & 0o077
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != UID
            or metadata.st_mode & 0o077
            or metadata.st_size > 32768
        ):
            return {"status": "unavailable", "reason": "permissions_or_size"}
        snapshot = _load_object(path.read_text(encoding="utf-8"))
        age = _age(snapshot.get("observed_at"))
        nodes = snapshot.get("nodes")
        if (
            snapshot.get("schema_version") != 1
            or snapshot.get("project_id") != PROJECT_ID
            or snapshot.get("profile_id") != PROFILE_ID
            or age > 180
            or not isinstance(nodes, dict)
            or len(nodes) > 16
            or any(
                not isinstance(name, str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
                or not isinstance(node, dict)
                or node.get("status") not in {"healthy", "degraded", "unknown", "unavailable"}
                for name, node in nodes.items()
            )
        ):
            return {"status": "stale_or_invalid", "age_seconds": age}
        return {
            "status": (
                "healthy"
                if all(node["status"] == "healthy" for node in nodes.values())
                else "degraded"
            ),
            "age_seconds": age,
            "nodes": {name: {"status": node["status"]} for name, node in sorted(nodes.items())},
            "active_error_keys": sorted(
                key for key in snapshot.get("active_error_keys", [])
                if isinstance(key, str) and re.fullmatch(r"[a-z][a-z0-9:_-]{0,63}", key)
            )[:16],
        }
    except FileNotFoundError:
        return {"status": "unavailable", "reason": "no_dashboard_snapshot"}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable", "reason": "read_failed"}


def _binding_status(manifest_error: str | None) -> dict[str, Any]:
    reasons = [manifest_error] if manifest_error else []
    try:
        config = tomllib.loads((ROOT / ".curatormd-v2.toml").read_text(encoding="utf-8"))
        if config.get("project_id") != PROJECT_ID:
            reasons.append("project_id_mismatch")
    except (OSError, tomllib.TOMLDecodeError):
        reasons.append("project_config_missing_or_malformed")
    if os.getuid() != UID:
        reasons.append("os_uid_mismatch")
    if Path(os.path.realpath(ROOT)) != ROOT or not ROOT.is_dir():
        reasons.append("repository_root_mismatch")
    try:
        bindings_path = Path.home() / ".config/curatormd-v2/database-bindings.json"
        bindings = _load_object(bindings_path.read_text(encoding="utf-8"))
        projects = cast(JsonObject, bindings.get("projects", {}))
        if projects.get(PROJECT_ID) != str(DATABASE):
            reasons.append("database_binding_mismatch")
    except (OSError, ValueError):
        reasons.append("database_binding_missing_or_malformed")
    profile_config = Path.home() / ".hermes/profiles" / PROFILE_ID / "config.yaml"
    try:
        profile_text = profile_config.read_text(encoding="utf-8")
        if (
            f"hermes_project_id: {PROFILE_ID}" not in profile_text
            or str(DATABASE) not in profile_text
            or str(ROOT) not in profile_text
        ):
            reasons.append("hermes_profile_binding_mismatch")
    except OSError:
        reasons.append("hermes_profile_missing")
    return {"status": "healthy" if not reasons else "degraded", "reason": reasons or None}


def _summarize_health(value: JsonObject) -> dict[str, Any]:
    """Validate one profile-bound snapshot, including all dependency ages."""
    return summarize_health(value, PROJECT_ID)


def _probe_health(manifest: dict[str, Any]) -> dict[str, Any]:
    """Run the profile probe in its own resource-limited transient unit."""
    env = _probe_environment()
    try:
        runner = shutil.which("systemd-run")
        if not runner:
            raise OSError("isolated probe runner unavailable")
        command = cast(list[str], manifest["health_command"])
        isolated = [
            runner,
            "--user",
            "--quiet",
            "--pipe",
            "--wait",
            "--collect",
            "--unit=curatormd-v2-ops-probe-" + uuid.uuid4().hex[:12],
            "--property=MemoryMax=512M",
            "--property=CPUQuota=50%",
            f"--property=RuntimeMaxSec={MAX_PROBE_SECONDS}s",
            "--setenv=HOME=" + str(Path.home()),
            "--setenv=HERMES_HOME=" + env["HERMES_HOME"],
            "--setenv=PATH=" + env["PATH"],
            *(
                ["--setenv=XDG_RUNTIME_DIR=" + env["XDG_RUNTIME_DIR"]]
                if "XDG_RUNTIME_DIR" in env
                else []
            ),
            *(
                ["--setenv=DBUS_SESSION_BUS_ADDRESS=" + env["DBUS_SESSION_BUS_ADDRESS"]]
                if "DBUS_SESSION_BUS_ADDRESS" in env
                else []
            ),
            *command,
        ]  # nosec B603
        completed = subprocess.run(  # nosec B603
            isolated,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=MAX_PROBE_SECONDS + 3,
            check=False,
        )
        wire = completed.stdout[:262144].decode("utf-8", errors="replace")
        value = _load_object(wire) if completed.returncode == 0 else {}
        return _summarize_health(value)
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
        return {
            "status": "probe_failed",
            "age_seconds": None,
            "dependencies": {
                name: {"status": "unknown", "age_seconds": None} for name in sorted(HEALTH_NAMES)
            },
            "gates": [],
        }


def _probe_environment() -> dict[str, str]:
    """Build the minimal environment for the pinned Hermes profile probe."""
    env = {
        "HOME": str(Path.home()),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HERMES_HOME": str(Path.home() / ".hermes/profiles" / PROFILE_ID),
        "PYTHONUNBUFFERED": "1",
        "LANG": "C",
        "LC_ALL": "C",
    }
    runtime = Path(f"/run/user/{os.getuid()}")
    if (runtime / "bus").exists():
        env["XDG_RUNTIME_DIR"] = str(runtime)
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime / 'bus'}"
    return env


def _age(raw: Any) -> int:
    try:
        observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        age = (_now() - observed).total_seconds()
        return 2**31 if age < -5 else max(0, int(age))
    except (ValueError, TypeError):
        return 2**31


def check(*, dispatch: bool = True, manage_incidents: bool = False) -> dict[str, Any]:
    """Return component health and create one incident for each stable fault."""
    # One-shot checks use a fresh process and cannot authoritatively reconcile
    # the resident monitor's loaded source identity or close its incidents.
    if manage_incidents:
        _reconcile_abandoned_ai_runs()
    manifest, manifest_error = _read_manifest()
    monitor = _monitor_status()
    components: dict[str, Any] = {
        "binding": _binding_status(manifest_error),
        "database": _probe_database(),
        "runtime": _runtime_status(),
        "backup": _backup_status(),
        "backup_retention": _backup_retention_status(),
        "monitor": monitor,
        "acceptance_history": _acceptance_history_status(monitor),
        "maintenance_timer": _maintenance_timer_status(),
        "maintenance": _maintenance_status(),
        "event_failures": _event_failure_status(),
        "dashboard_telemetry": _dashboard_telemetry_status(),
        "health": {"status": "unknown"},
    }
    if manifest is not None and not manifest_error:
        components["health"] = _probe_health(manifest)
    bad = [name for name, item in components.items() if item.get("status") != "healthy"]
    fingerprint = _incident_fingerprint(components)
    incident_id = _incident(fingerprint, components) if bad and dispatch else None
    return {
        "project_id": PROJECT_ID,
        "checked_at": _iso(),
        "status": "healthy" if not bad else "degraded",
        "components": components,
        "gates": bad,
        "warnings": _recent_ai_warnings(),
        "incident_id": incident_id,
        "next_action": (
            "none"
            if not bad
            else "inspect incident; identity and deployment changes require owner approval"
        ),
    }


def _incident_fingerprint(components: dict[str, Any]) -> str:
    """Hash stable fault classes, excluding probe timestamps and evidence ages."""
    stable: dict[str, Any] = {}
    for name, component in components.items():
        stable_item: dict[str, Any] = {"status": component.get("status")}
        for key in (
            "reason",
            "error",
            "schema",
            "integrity",
            "foreign_keys",
            "gates",
            "queue_snapshot_complete",
            "count",
            "inventory_complete",
            "active_error_keys",
        ):
            if key in component:
                stable_item[key] = component[key]
        if name == "event_failures" and isinstance(component.get("events"), list):
            stable_item["event_ids"] = [
                item.get("event_id") for item in component["events"]
                if isinstance(item, dict) and isinstance(item.get("event_id"), str)
            ]
        if name == "dashboard_telemetry" and isinstance(component.get("nodes"), dict):
            stable_item["nodes"] = {
                key: item.get("status") for key, item in component["nodes"].items()
                if isinstance(item, dict)
            }
        if isinstance(component.get("dependencies"), dict):
            stable_item["dependencies"] = {
                key: item.get("status") for key, item in component["dependencies"].items()
            }
        stable[name] = stable_item
    wire = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(wire).hexdigest()


def _close_recovered_incidents() -> None:
    """Close recovered incidents only after diagnosis has reached a terminal state."""
    for path in INCIDENTS.glob("*.json"):
        try:
            incident = _load_object(path.read_text(encoding="utf-8"))
            if incident.get("status") == "open" and incident.get("ai_status") in {
                "completed",
                "failed",
                "timeout",
                "dispatch_failed",
                "codex_unavailable",
                "warning",
                "token_budget_exhausted",
                "token_budget_unobservable",
            }:
                incident["status"] = "closed"
                incident["closed_at"] = _iso()
                incident["recovery"] = "all current checks healthy"
                _json(path, incident)
        except (OSError, ValueError):
            continue


def _ai_unit_active(incident_id: str) -> bool | None:
    """Return whether the incident's transient diagnosis unit is still active."""
    runner = shutil.which("systemctl")
    if runner is None:
        return None
    unit = "curatormd-v2-ops-ai-" + incident_id[:12]
    try:
        result = subprocess.run(  # nosec B603
            [runner, "--user", "is-active", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.returncode == 0 and result.stdout.strip() == "active"


def _reconcile_abandoned_ai_runs() -> None:
    """Make timed-out or vanished transient diagnoses reach a terminal state."""
    for path in INCIDENTS.glob("*.json"):
        try:
            incident = _load_object(path.read_text(encoding="utf-8"))
            if incident.get("status") != "open" or incident.get("ai_status") not in {
                "queued",
                "dispatching",
                "running",
            }:
                continue
            if _age(incident.get("ai_last_attempt_at") or incident.get("created_at")) <= MAX_AI_SECONDS + 15:
                continue
            incident_id = incident.get("incident_id")
            if not isinstance(incident_id, str):
                continue
            active = _ai_unit_active(incident_id)
            if active is not False:
                continue
            incident["ai_status"] = (
                "timeout" if incident.get("ai_status") == "running" else "dispatch_failed"
            )
            _finish_ai_attempt(incident)
            _json(path, incident)
        except (OSError, ValueError):
            continue


def _journal_record(result: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded, content-free journal event from one check result."""
    summaries: dict[str, Any] = {}
    for name, value in result.get("components", {}).items():
        summary: dict[str, Any] = {"status": value.get("status", "unknown")}
        for key in (
            "age_seconds",
            "database_age_seconds",
            "staging_age_seconds",
            "queue_snapshot_complete",
            "dependencies",
            "resource",
            "event_counts",
            "operational_counts",
            "staging_regular_file_count",
            "count",
            "inventory_complete",
            "nodes",
            "active_error_keys",
        ):
            if key in value:
                summary[key] = value[key]
        summaries[name] = summary
    return {
        "event": "curatormd_v2_ops_check",
        "checked_at": result.get("checked_at"),
        "project_id": result.get("project_id"),
        "status": result.get("status"),
        "gates": result.get("gates", []),
        "warnings": result.get("warnings", []),
        "incident_id": result.get("incident_id"),
        "next_action": result.get("next_action"),
        "components": summaries,
    }


def _backup_status() -> dict[str, Any]:
    directory = DATABASE.parent / "backups"
    today = _now().astimezone().date().isoformat()
    path = directory / f"curator-v2-{today}.sqlite3"
    age: int | None = None
    permissions_ok = False
    try:
        if path.exists() and not path.is_symlink():
            file_stat = path.stat(follow_symlinks=False)
            directory_stat = directory.stat(follow_symlinks=False)
            age = max(0, int(time.time() - file_stat.st_mtime))
            permissions_ok = (
                file_stat.st_uid == UID
                and not (file_stat.st_mode & 0o077)
                and directory_stat.st_uid == UID
                and not (directory_stat.st_mode & 0o077)
            )
    except OSError:
        age = None
    maintenance = _maintenance_status()
    receipt_valid = maintenance.get("backup_receipt") is True
    return {
        "status": (
            "healthy"
            if age is not None and age < 86400 and permissions_ok and receipt_valid
            else "stale_or_unverified"
        ),
        "age_seconds": age,
        "permissions": "private" if permissions_ok else "invalid_or_unknown",
        "creation_receipt": "verified" if receipt_valid else "missing_or_stale",
    }


def _maintenance_status() -> dict[str, Any]:
    marker = STATE / "last-maintenance.json"
    try:
        value = _load_object(marker.read_text(encoding="utf-8"))
        age = _age(value.get("completed_at"))
        try:
            output = _load_object(str(value.get("stdout", "")))
            backup_receipt = output.get("backup_status") == "verified"
        except ValueError:
            backup_receipt = False
        return {
            "status": (
                "healthy"
                if age < 21600 + 900 and value.get("exit_code") == 0
                else "stale_or_failed"
            ),
            "age_seconds": age,
            "backup_receipt": backup_receipt,
        }
    except (OSError, ValueError):
        return {"status": "unknown", "age_seconds": None}


def _monitor_status() -> dict[str, Any]:
    """Read measured lifetime resource use for the exact resident service."""
    return monitor_status(f"curatormd-v2-ops@{PROJECT_ID}.service")


def _acceptance_history_status(monitor: dict[str, Any]) -> dict[str, Any]:
    """Check monitor samples, allowing only the resident startup grace period."""
    elapsed = monitor.get("resource", {}).get("elapsed_seconds")
    return acceptance_history_status(
        STATE,
        UID,
        allow_missing=(
            monitor.get("status") == "healthy"
            and isinstance(elapsed, (int, float))
            and elapsed < 120
        ),
    )


def _maintenance_timer_status() -> dict[str, Any]:
    """Read the exact six-hour scheduler required by the Hermes readiness probe."""
    return maintenance_timer_status(PROJECT_ID)


def _runtime_status() -> dict[str, Any]:
    """Check package metadata, source parity, and both installed entrypoints."""
    return runtime_status(ROOT, Path(__file__), SOURCE_FINGERPRINT_AT_IMPORT, SQLITE_SCHEMA_VERSION)


def _incident(fingerprint: str, components: dict[str, Any]) -> str:
    INCIDENTS.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = sorted(INCIDENTS.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in files:
        try:
            incident = _load_object(path.read_text(encoding="utf-8"))
            if incident.get("fingerprint") == fingerprint and incident.get("status") != "closed":
                legacy_budget_status = incident.get("ai_status")
                if legacy_budget_status in AI_BUDGET_WARNING_CODES:
                    _mark_ai_budget_warning(incident, legacy_budget_status)
                    _json(path, incident)
                if _ai_retry_due(incident):
                    _dispatch_ai(path)
                return str(incident["incident_id"])
        except (OSError, ValueError, KeyError):
            continue
    incident_id = str(uuid.uuid4())
    path = INCIDENTS / f"{incident_id}.json"
    _json(
        path,
        {
            "schema_version": 1,
            "incident_id": incident_id,
            "project_id": PROJECT_ID,
            "created_at": _iso(),
            "fingerprint": fingerprint,
            "status": "open",
            "components": components,
            "troubleshooting": {
                "algorithm": "failure-node-snapshot-v1",
                "started_at": _iso(),
                "nodes_inspected": sorted(components),
                "event_failure_inventory_complete": (
                    components.get("event_failures", {}).get("inventory_complete") is True
                ),
                "dashboard_telemetry_status": components.get(
                    "dashboard_telemetry", {}
                ).get("status", "unknown"),
            },
            "ai_status": "queued",
        },
    )
    _dispatch_ai(path)
    return incident_id


def _mark_ai_budget_warning(incident: JsonObject, code: str) -> None:
    """Record expected budget stops as visible, non-retryable warnings."""
    if code not in AI_BUDGET_WARNING_CODES:
        return
    incident["ai_status"] = "warning"
    incident["ai_warning_code"] = code
    incident["ai_warning"] = (
        "AI diagnosis stopped at its configured token budget; component health "
        "and incident recovery remain independent."
    )
    incident["ai_next_attempt_at"] = None


def _recent_ai_warnings() -> list[dict[str, str]]:
    """Expose recent AI budget warnings without adding project-health gates."""
    try:
        paths = sorted(
            INCIDENTS.glob("*.json"),
            key=lambda path: path.stat(follow_symlinks=False).st_mtime,
            reverse=True,
        )[:50]
    except OSError:
        return []
    warnings: list[dict[str, str]] = []
    for path in paths:
        try:
            metadata = path.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != UID
                or metadata.st_mode & 0o077
                or metadata.st_size > 65536
            ):
                continue
            incident = _load_object(path.read_text(encoding="utf-8"))
            incident_id = incident.get("incident_id")
            ai_status = incident.get("ai_status")
            code = incident.get("ai_warning_code")
            if code not in AI_BUDGET_WARNING_CODES and ai_status in AI_BUDGET_WARNING_CODES:
                code = ai_status
            if (
                ai_status != "warning" and ai_status not in AI_BUDGET_WARNING_CODES
                or code not in AI_BUDGET_WARNING_CODES
                or not isinstance(incident_id, str)
                or _age(incident.get("ai_finished_at")) > 86400
            ):
                continue
            warnings.append({
                "severity": "warning",
                "code": code,
                "incident_id": incident_id,
                "message": (
                    "AI diagnosis stopped at its configured token budget; "
                    "component health is unaffected."
                ),
            })
            if len(warnings) >= 10:
                break
        except (OSError, ValueError, TypeError):
            continue
    return warnings


def _dispatch_ai(incident_path: Path) -> None:
    """Dispatch one bounded local Codex diagnosis in an isolated worktree."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    incident = _load_object(incident_path.read_text(encoding="utf-8"))
    prior_attempts = incident.get("ai_attempt_count", 0)
    if not isinstance(prior_attempts, int) or isinstance(prior_attempts, bool) or prior_attempts < 0:
        prior_attempts = 0
    incident["ai_attempt_count"] = prior_attempts + 1
    incident["ai_last_attempt_at"] = _iso()
    incident["ai_next_attempt_at"] = None
    incident["ai_status"] = "queued"
    _json(incident_path, incident)
    runner = shutil.which("systemd-run")
    if runner:
        try:
            unit = "curatormd-v2-ops-ai-" + incident["incident_id"][:12]
            subprocess.run(  # nosec B603
                [
                    runner,
                    "--user",
                    "--quiet",
                    "--collect",
                    "--unit=" + unit,
                    "--property=MemoryMax=1G",
                    "--property=CPUQuota=20%",
                    f"--property=RuntimeMaxSec={MAX_AI_SECONDS + 5}s",
                    "--setenv=HOME=" + str(Path.home()),
                    "--setenv=PATH="
                    + str(CODEX.parent)
                    + ":/home/eaglesvn/.local/bin:/usr/local/bin:/usr/bin:/bin",
                    sys.executable,
                    "-m",
                    "curatormd_v2.ops_cli",
                    "diagnose",
                    str(incident_path),
                ],  # nosec B603
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
            )
            incident = _load_object(incident_path.read_text(encoding="utf-8"))
            if incident.get("ai_status") == "queued":
                incident["ai_status"] = "dispatching"
            _json(incident_path, incident)
            return
        except (OSError, subprocess.SubprocessError):
            pass
    incident["ai_status"] = "dispatch_failed"
    _finish_ai_attempt(incident)
    _json(incident_path, incident)


def _retry_delay_seconds(attempt_count: int) -> int:
    """Back off repeated diagnosis failures, capped at one attempt every six hours."""
    attempts = max(1, min(attempt_count, 16))
    return min(AI_RETRY_BASE_SECONDS * (2 ** (attempts - 1)), AI_RETRY_MAX_SECONDS)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _ai_retry_due(incident: JsonObject, now: datetime | None = None) -> bool:
    """Retry queued work when released, and terminal transient failures after backoff."""
    current = now or _now()
    status = incident.get("ai_status")
    if status == "queued":
        retry_at = incident.get("ai_next_attempt_at")
        return retry_at is None or (
            (parsed_retry := _parse_timestamp(retry_at)) is not None and parsed_retry <= current
        )
    if status not in AI_RETRYABLE_STATUSES:
        return False
    finished = _parse_timestamp(
        incident.get("ai_finished_at")
        or incident.get("ai_last_attempt_at")
        or incident.get("created_at")
    )
    if finished is None:
        return False
    attempts = incident.get("ai_attempt_count", 1)
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        attempts = 1
    return (current - finished).total_seconds() >= _retry_delay_seconds(attempts)


def _finish_ai_attempt(incident: JsonObject) -> None:
    """Record terminal time and the next bounded retry for transient failures."""
    now = _now()
    incident["ai_finished_at"] = _iso()
    if incident.get("ai_status") in AI_RETRYABLE_STATUSES:
        attempts = incident.get("ai_attempt_count", 1)
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            attempts = 1
        incident["ai_next_attempt_at"] = (
            now + timedelta(seconds=_retry_delay_seconds(attempts))
        ).isoformat().replace("+00:00", "Z")
    else:
        incident["ai_next_attempt_at"] = None


def _diagnose(incident_path: Path) -> int:
    lock_path = STATE / "ai.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            queued = _load_object(incident_path.read_text(encoding="utf-8"))
            queued["ai_status"] = "queued"
            queued["ai_next_attempt_at"] = (
                _now() + timedelta(seconds=AI_RETRY_BASE_SECONDS)
            ).isoformat().replace("+00:00", "Z")
            _json(incident_path, queued)
            return 0
        incident = _load_object(incident_path.read_text(encoding="utf-8"))
        incident["ai_status"] = "running"
        _json(incident_path, incident)
        prompt = (
            "Run the Curator V2 failure-troubleshooting algorithm for this local-alpha "
            "incident. Establish the state of every supplied component node, including "
            "the dashboard telemetry handoff and bounded event failure inventory. "
            "Identify the first failing node, dependencies, evidence gaps, and their "
            "relationship; do not infer health from unavailable telemetry. Inspect the "
            "smallest relevant source/test set. Use at most 8 tool "
            "calls; do not run a full test suite, delegate, spawn subagents, or scan "
            "unrelated repositories. Keep each command output bounded. If source code is "
            "implicated, create a tested candidate only in Codex's managed worktree. "
            "Before changing each worktree file, record its private before-image, "
            "SHA-256, and restore path. "
            "Never install, deploy, modify identity/grants, create purge approvals, "
            "or alter active data. Stop after one diagnosis and one bounded fix proposal. "
            "Report evidence, one focused test result if needed, and exact owner recovery "
            "steps in at most 300 words.\nIncident:\n"
            + json.dumps(
                {
                    "incident_id": incident["incident_id"],
                    "troubleshooting": incident.get("troubleshooting", {}),
                    "components": incident["components"],
                },
                sort_keys=True,
            )
        )
        if not CODEX.is_file() or not os.access(CODEX, os.X_OK):
            incident["ai_status"] = "codex_unavailable"
            _finish_ai_attempt(incident)
            _json(incident_path, incident)
            return 2
        try:
            command = _codex_command(prompt)
            returncode, output, tokens, exhausted, unobservable = _run_codex_bounded(command)
            if unobservable or exhausted:
                _mark_ai_budget_warning(
                    incident,
                    "token_budget_unobservable" if unobservable else "token_budget_exhausted",
                )
            else:
                incident["ai_status"] = "completed" if returncode == 0 else "failed"
            incident["ai_exit_code"] = returncode
            incident["ai_tokens_observed"] = tokens
            incident["ai_output_sha256"] = hashlib.sha256(output.encode()).hexdigest()
            incident["ai_output_bytes"] = len(output.encode())
            incident["ai_summary"] = _safe_ai_summary(output)
        except TimeoutError:
            incident["ai_status"] = "timeout"
        except (OSError, subprocess.SubprocessError):
            incident["ai_status"] = "dispatch_failed"
        _finish_ai_attempt(incident)
        _json(incident_path, incident)
        return 0


def _safe_ai_summary(output: str) -> str:
    """Extract a short final report without retaining Codex's raw transcript."""
    reports: list[str] = []
    for line in output.splitlines():
        try:
            event = _load_object(line)
        except ValueError:
            continue
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        message = cast(JsonObject, item)
        report = message.get("text")
        if message.get("type") == "agent_message" and isinstance(report, str):
            reports.append(report)
    if not reports:
        return "Codex produced no final summary."
    summary = reports[-1]
    summary = re.sub(r"/(?:home|tmp|var|mnt)/[^\s\"'`<>]+", "<local-path>", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    return summary[:2000]


def _codex_command(prompt: str) -> list[str]:
    """Build a low-context, low-output, nondelegating Codex diagnosis command."""
    return [
        str(CODEX),
        "--disable",
        "multi_agent",
        "--config",
        "model_context_window=8192",
        "--config",
        "model_auto_compact_token_limit=6144",
        "--config",
        "tool_output_token_limit=2048",
        "--config",
        'models.new_thread.model_reasoning_effort="low"',
        "exec",
        "--worktree",
        "--sandbox",
        "workspace-write",
        "--json",
        "--cd",
        str(ROOT),
        prompt,
    ]


def _run_codex_bounded(command: list[str]) -> tuple[int, str, int, bool, bool]:
    """Stream Codex events and stop when reported token use reaches the cap."""
    with subprocess.Popen(  # nosec B603
        command,
        cwd=ROOT,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    ) as process:
        if process.stdout is None:
            process.kill()
            return 2, "codex_output_unavailable", 0, False, True
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + MAX_AI_SECONDS
        pending: bytes = b""
        output = bytearray()
        tokens = 0
        exhausted = False
        unobservable = False
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    raise TimeoutError
                if not selector.select(min(remaining, 1.0)):
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 65536:
                    del output[:-65536]
                pending += chunk
                while (newline := pending.find(b"\n")) >= 0:
                    line = pending[:newline]
                    pending = pending[newline + 1 :]
                    completed_turn, turn_tokens = _reported_token_count(line)
                    if completed_turn and turn_tokens is None:
                        unobservable = True
                        process.kill()
                        break
                    tokens += turn_tokens or 0
                    if tokens >= MAX_AI_TOKENS:
                        exhausted = True
                        process.kill()
                        break
                if exhausted or unobservable:
                    break
            if pending and not (exhausted or unobservable):
                completed_turn, turn_tokens = _reported_token_count(pending)
                if completed_turn and turn_tokens is None:
                    unobservable = True
                    process.kill()
                elif completed_turn:
                    tokens += turn_tokens or 0
                    if tokens >= MAX_AI_TOKENS:
                        exhausted = True
                        process.kill()
            return (
                process.wait(timeout=5),
                output.decode("utf-8", errors="replace"),
                tokens,
                exhausted,
                unobservable,
            )
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()


def _reported_token_count(line: bytes) -> tuple[bool, int | None]:
    """Return completed-turn state and reported usage from a Codex event."""
    try:
        event = _load_object(line)
        if event.get("type") not in {"turn.completed", "turn_complete"}:
            return False, 0
        message = cast(JsonObject, event.get("msg", {}))
        raw_usage = event.get("usage", message.get("usage"))
        if not isinstance(raw_usage, dict):
            return True, None
        usage = cast(JsonObject, raw_usage)
        # Cached input is already included in input_tokens by Codex. Counting
        # it again can exhaust the budget during a short successful run.
        keys = ("input_tokens", "output_tokens")
        if any(not isinstance(usage.get(key), int) for key in keys if key in usage):
            return True, None
        if not any(key in usage for key in keys):
            return True, None
        if any(key not in usage for key in keys):
            return True, None
        return True, int(usage["input_tokens"]) + int(usage["output_tokens"])
    except (ValueError, TypeError, AttributeError):
        return False, 0


def maintain() -> int:
    """Run a snapshot-backed maintenance pass for already approved work."""
    manifest, error = _read_manifest()
    if manifest is None or error:
        print(json.dumps({"status": "refused", "reason": error}), file=sys.stderr)
        return 2
    database_health = _probe_database()
    if database_health.get("integrity") != "ok":
        print("Refusing maintenance while database checks are not healthy.", file=sys.stderr)
        return 2
    try:
        if not _prepare_database(database_health):
            return 2
        command = [
            *manifest["maintenance_command"],
            "--project-root",
            str(ROOT),
            "--database",
            str(DATABASE),
            "--batch-limit",
            "100",
            "--execute-due-purges",
        ]  # nosec B603
        proc = subprocess.run(  # nosec B603
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        post_health = _probe_database()
        retention = _run_backup_retention(manifest)
        exit_code = (
            proc.returncode
            if post_health.get("status") == "healthy" and retention.get("status") == "healthy"
            else 2
        )
        _json(
            STATE / "last-maintenance.json",
            {
                "completed_at": _iso(),
                "exit_code": exit_code,
                "stdout": proc.stdout[-4096:].decode("utf-8", "replace"),
            },
        )
        return exit_code
    except (OSError, subprocess.TimeoutExpired, sqlite3.Error) as exc:
        _json(
            STATE / "last-maintenance.json",
            {"completed_at": _iso(), "exit_code": 2, "error": type(exc).__name__},
        )
        return 2


def _prepare_database(database_health: dict[str, Any]) -> bool:
    """Apply only source-defined additive migrations after a verified snapshot."""
    if database_health.get("foreign_key_schema_mismatch") is True:
        if database_health.get("schema_version", SQLITE_SCHEMA_VERSION) >= SQLITE_SCHEMA_VERSION:
            print(
                "Refusing foreign-key mismatch without an older additive migration.",
                file=sys.stderr,
            )
            return False
        _snapshot_for_migration(database_health)
        # Importing the store lazily keeps the resident health monitor light.
        from .store import CuratorStore  # pylint: disable=import-outside-toplevel

        with CuratorStore(DATABASE):
            pass
        migrated = _probe_database()
        if migrated.get("integrity") != "ok" or migrated.get("foreign_keys") != "ok":
            print("Additive migration did not restore both SQLite checks.", file=sys.stderr)
            return False
        return True
    if database_health.get("foreign_keys") != "ok":
        print("Refusing maintenance while SQLite reports foreign-key violations.", file=sys.stderr)
        return False
    return True


def _snapshot_for_migration(database_health: dict[str, Any]) -> None:
    """Save a private consistent DB before-image and record the FK check state."""
    directory = STATE / "incident-backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{PROJECT_ID}-{_now().strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    source_uri = f"file:{DATABASE.as_posix()}?mode=ro"
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    os.close(descriptor)
    try:
        with (
            closing(sqlite3.connect(source_uri, uri=True, timeout=10)) as source,
            closing(sqlite3.connect(target, timeout=10)) as destination,
        ):
            source.backup(destination)
            integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
            try:
                foreign_count = len(destination.execute("PRAGMA foreign_key_check").fetchmany(100))
                foreign_error = None
            except sqlite3.OperationalError as exc:
                foreign_count = None
                foreign_error = (
                    "foreign_key_schema_mismatch"
                    if "foreign key mismatch" in str(exc).lower()
                    else "sqlite_error"
                )
        if integrity != "ok":
            raise sqlite3.DatabaseError("snapshot integrity check failed")
        digest = _sha256_file(target)
        _json(
            target.with_suffix(".json"),
            {
                "project_id": PROJECT_ID,
                "incident_id": _active_database_incident_id(),
                "created_at": _iso(),
                "database_sha256": digest,
                "integrity_check": integrity,
                "foreign_key_check": "failed_before_migration",
                "foreign_key_violation_count": foreign_count,
                "foreign_key_error_class": foreign_error,
                "database_health_before": database_health,
                "restore": (
                    "Owner recovery only: stop the monitor and restore this snapshot "
                    "offline after verifying its hash."
                ),
            },
        )
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _active_database_incident_id() -> str | None:
    """Bind a migration snapshot to the open database incident when identifiable."""
    candidates: list[tuple[str, str]] = []
    for path in INCIDENTS.glob("*.json"):
        try:
            incident = _load_object(path.read_text(encoding="utf-8"))
            raw_components = incident.get("components")
            components = cast(JsonObject, raw_components) if isinstance(raw_components, dict) else {}
            raw_database = components.get("database")
            database = cast(JsonObject, raw_database) if isinstance(raw_database, dict) else None
            if (
                incident.get("project_id") == PROJECT_ID
                and incident.get("status") == "open"
                and isinstance(incident.get("incident_id"), str)
                and isinstance(database, dict)
                and database.get("status") != "healthy"
            ):
                candidates.append((str(incident.get("created_at", "")), incident["incident_id"]))
        except (OSError, ValueError, KeyError):
            continue
    return max(candidates)[1] if candidates else None


def _backup_retention_status() -> dict[str, Any]:
    """Report the last private retention audit and its evidence age."""
    receipt_path = STATE / "last-backup-retention.json"
    try:
        receipt = _load_object(receipt_path.read_text(encoding="utf-8"))
        age = _age(receipt.get("completed_at"))
        status = receipt.get("status")
        counts = (receipt.get("deleted"), receipt.get("retained_uncertain"))
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
            return {"status": "malformed"}
        if status != "healthy":
            return {"status": "degraded", "evidence_age_seconds": age}
        if age > 86400:
            return {"status": "stale", "evidence_age_seconds": age}
        return {
            "status": "healthy",
            "evidence_age_seconds": age,
            "retained_uncertain": receipt.get("retained_uncertain", 0),
        }
    except (OSError, ValueError):
        return {"status": "missing_or_malformed"}


def _run_backup_retention(manifest: dict[str, Any]) -> dict[str, Any]:
    """Prune only verified snapshots whose linked incident closed 30+ days ago."""
    receipt_path = STATE / "last-backup-retention.json"
    try:
        previous = _load_object(receipt_path.read_text(encoding="utf-8"))
        previous_status = _backup_retention_status()
        age = previous_status.get("evidence_age_seconds", 2**31)
        if previous_status.get("status") == "healthy" and age <= 86400:
            return previous
        if previous.get("status") != "healthy" and age <= 3600:
            return previous
    except (OSError, ValueError):
        pass
    try:
        result = _prune_incident_backups(
            int(manifest["backup_retention_days"]), now=_now()
        )
        receipt = {"completed_at": _iso(), **result}
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
        receipt = {"completed_at": _iso(), "status": "error"}
    _json(receipt_path, receipt)
    return receipt


def _prune_incident_backups(
    retention_days: int, *, now: datetime
) -> dict[str, Any]:
    """Delete only hash-verified snapshots tied to incidents closed past retention."""
    if retention_days < 1 or retention_days > 3650:
        raise ValueError("invalid snapshot retention period")
    directory = STATE / "incident-backups"
    if not directory.exists():
        return {"status": "healthy", "deleted": 0, "retained_uncertain": 0}
    metadata = directory.stat(follow_symlinks=False)
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
    ):
        raise ValueError("incident backup directory is not private and owner-owned")
    candidates = sorted(directory.glob("*.sqlite3"))
    if len(candidates) > 256:
        return {"status": "inventory_incomplete", "deleted": 0, "retained_uncertain": len(candidates)}
    deleted = retained_uncertain = 0
    for snapshot in candidates:
        sidecar = snapshot.with_suffix(".json")
        try:
            snapshot_stat = snapshot.stat(follow_symlinks=False)
            sidecar_stat = sidecar.stat(follow_symlinks=False)
            if (
                snapshot.is_symlink()
                or sidecar.is_symlink()
                or not snapshot.is_file()
                or not sidecar.is_file()
                or snapshot_stat.st_uid != os.getuid()
                or sidecar_stat.st_uid != os.getuid()
                or snapshot_stat.st_mode & 0o077
                or sidecar_stat.st_mode & 0o077
            ):
                retained_uncertain += 1
                continue
            record = _load_object(sidecar.read_text(encoding="utf-8"))
            incident_id = record.get("incident_id")
            if (
                record.get("project_id") != PROJECT_ID
                or not isinstance(incident_id, str)
                or record.get("database_sha256") != _sha256_file(snapshot)
            ):
                retained_uncertain += 1
                continue
            incident_id = str(uuid.UUID(incident_id))
            incident_path = INCIDENTS / f"{incident_id}.json"
            incident_stat = incident_path.stat(follow_symlinks=False)
            if (
                incident_path.is_symlink()
                or not incident_path.is_file()
                or incident_stat.st_uid != os.getuid()
                or incident_stat.st_mode & 0o077
            ):
                retained_uncertain += 1
                continue
            incident = _load_object(incident_path.read_text(encoding="utf-8"))
            if incident.get("incident_id") != incident_id or incident.get("status") != "closed":
                continue
            closed_at = datetime.fromisoformat(str(incident["closed_at"]).replace("Z", "+00:00"))
            if closed_at.tzinfo is None or now < closed_at + timedelta(days=retention_days):
                continue
            snapshot.unlink()
            sidecar.unlink()
            deleted += 1
        except FileNotFoundError:
            retained_uncertain += 1
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            retained_uncertain += 1
    return {
        "status": "healthy" if retained_uncertain == 0 else "evidence_uncertain",
        "deleted": deleted,
        "retained_uncertain": retained_uncertain,
    }


def _report_persistence_failure(result: dict[str, Any], component: str, reason: str) -> None:
    """Keep a failed monitor write visible and dispatch a bounded incident."""
    components = result["components"]
    prior = components.get(component, {})
    already_failed = prior.get("status", "healthy") != "healthy"
    if already_failed:
        prior["write_status"] = "failed"
    else:
        components[component] = {"status": "unavailable", "reason": reason}
    if component not in result["gates"]:
        result["gates"].append(component)
    result["status"] = "degraded"
    result["next_action"] = "inspect incident; identity and deployment changes require owner approval"
    if not already_failed or not result.get("incident_id"):
        try:
            result["incident_id"] = _incident(_incident_fingerprint(components), components)
        except OSError:
            result["incident_id"] = None
            result["next_action"] = "inspect journal; incident recording failed"


def monitor() -> int:
    """Run the single resident local-alpha coordinator loop."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOCK.open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        while True:
            started = time.monotonic()
            manifest, error = _read_manifest()
            if manifest is not None and error is None:
                _run_backup_retention(manifest)
            result = check(dispatch=True, manage_incidents=True)
            try:
                record_check(result, STATE, UID)
            except OSError:
                _report_persistence_failure(result, "acceptance_history", "history_write_failed")
            try:
                _json(STATE / "last-check.json", result)
            except OSError:
                _report_persistence_failure(result, "last_check", "last_check_write_failed")
            if result["status"] == "healthy":
                _close_recovered_incidents()
            print(json.dumps(_journal_record(result), sort_keys=True), flush=True)
            timer = result["components"]["maintenance_timer"]["status"]
            if _maintenance_due() and timer != "healthy":
                _dispatch_maintenance()
            time.sleep(max(0, 60 - (time.monotonic() - started)))


def _maintenance_due(now: datetime | None = None) -> bool:
    """Keep maintenance aligned to the existing local 00/06/12/18 cadence."""
    return maintenance_due(now or _now(), read_maintenance_timestamp(STATE))


def _dispatch_maintenance() -> None:
    """Run maintenance outside the resident monitor resource group."""
    runner = shutil.which("systemd-run")
    if not runner:
        _json(
            STATE / "last-maintenance.json",
            {"completed_at": _iso(), "exit_code": 2, "error": "isolated_runner_unavailable"},
        )
        return
    command = [
        runner,
        "--user",
        "--quiet",
        "--wait",
        "--collect",
        "--unit=curatormd-v2-ops-maintain-" + uuid.uuid4().hex[:12],
        "--property=MemoryMax=1G",
        "--property=CPUQuota=20%",
        "--property=RuntimeMaxSec=5min",
        "--working-directory=" + str(ROOT),
        str(ROOT / ".venv/bin/curatormd-v2-ops"),
        "maintain",
    ]  # nosec B603
    try:
        result = subprocess.run(  # nosec B603
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=310,
            check=False,
        )
        if result.returncode != 0:
            _json(
                STATE / "last-maintenance.json",
                {
                    "completed_at": _iso(),
                    "exit_code": result.returncode,
                    "error": "maintenance_unit_failed",
                },
            )
    except (OSError, subprocess.SubprocessError):
        _json(
            STATE / "last-maintenance.json",
            {"completed_at": _iso(), "exit_code": 2, "error": "maintenance_dispatch_failed"},
        )


def main(argv: list[str] | None = None) -> int:
    """Dispatch one public operations subcommand."""
    parser = argparse.ArgumentParser(prog="curatormd-v2-ops")
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--json", action="store_true")
    sub.add_parser("initialize-manifest")
    sub.add_parser("maintain")
    sub.add_parser("monitor")
    diagnosis = sub.add_parser("diagnose")
    diagnosis.add_argument("incident", type=Path)
    args = parser.parse_args(argv)
    if args.command == "initialize-manifest":
        ensure_manifest()
        print(str(MANIFEST))
        return 0
    if args.command == "check":
        result = check()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "healthy" else 1
    if args.command == "maintain":
        return maintain()
    if args.command == "diagnose":
        return _diagnose(args.incident)
    return monitor()


if __name__ == "__main__":
    raise SystemExit(main())
