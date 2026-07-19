"""Helpers for normalizing and displaying congressional hearing times."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    raw = str(value).strip()
    try:
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw + "T00:00:00+00:00")
    except ValueError:
        return None


def format_eastern_time(dt: datetime) -> str:
    """Format an aware datetime as a readable Eastern time for display."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    eastern = dt.astimezone(EASTERN)
    hour = eastern.hour % 12 or 12
    minute = eastern.minute
    ampm = "AM" if eastern.hour < 12 else "PM"
    return f"{hour}:{minute:02d} {ampm} ET"


def federal_datetime_fields(dt: datetime) -> Tuple[str, str, str]:
    """
    Return (scheduled_date, scheduled_time, published) for a federal hearing.

    scheduled_date uses the Eastern calendar date; published stays UTC ISO.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    eastern = dt.astimezone(EASTERN)
    scheduled_date = eastern.date().isoformat()
    scheduled_time = format_eastern_time(dt) if dt.time() != datetime.min.time() else ""
    published = dt.astimezone(timezone.utc).isoformat()
    return scheduled_date, scheduled_time, published


def format_federal_hearing_time(hearing: Dict[str, Any]) -> str:
    """Best-effort Eastern display time from a federal hearing record."""
    for field in ("published", "scheduled_date"):
        dt = parse_datetime(hearing.get(field) or "")
        if dt and dt.time() != datetime.min.time():
            return format_eastern_time(dt)

    raw_time = str(hearing.get("scheduled_time") or "").strip()
    if not raw_time:
        return ""

    # Legacy records stored UTC as HH:MM without timezone — re-interpret via published date.
    if raw_time[:2].isdigit() and len(raw_time) >= 4 and "T" in str(hearing.get("published") or ""):
        published = parse_datetime(hearing.get("published") or "")
        if published:
            return format_eastern_time(published)

    return raw_time
