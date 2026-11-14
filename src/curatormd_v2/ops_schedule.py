"""Six-hour schedule checks for the project-bound operations wrapper."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .ops_resource_monitor import unit_active_status


def read_maintenance_timestamp(state: Path) -> Any:
    """Read the last successful maintenance marker without exposing its contents."""
    try:
        return json.loads((state / "last-maintenance.json").read_text(encoding="utf-8")).get(
            "completed_at"
        )
    except (OSError, ValueError):
        return None


def maintenance_timer_status(project_id: str) -> dict[str, str]:
    """Check the exact project timer used by the Hermes readiness probe."""
    return unit_active_status(f"curatormd-v2-maintenance@{project_id}.timer")


def maintenance_due(current: datetime, last_value: Any) -> bool:
    """Check whether a six-hour local maintenance slot lacks a successful pass."""
    if current.tzinfo is None:
        raise ValueError("maintenance clock must include a timezone")
    if not last_value:
        return True
    try:
        last = datetime.fromisoformat(str(last_value).replace("Z", "+00:00"))
    except ValueError:
        return True
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    local_now = current.astimezone(zone)
    for day_offset in (0, 1):
        date = local_now.date() + timedelta(days=day_offset)
        for hour in (0, 6, 12, 18):
            candidate = datetime(date.year, date.month, date.day, hour, tzinfo=zone)
            if last < candidate <= current:
                return True
    return False
