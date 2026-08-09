"""Build slim hearings page artifact so hearings.html need not load site_data.json.

Writes docs/hearings.json with upcoming/historical hearings, kansas calendars,
enabled states (from states.yaml), and generated_at.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from processing.legislators_directory import load_enabled_states

HEARINGS_FEED_FILENAME = "hearings.json"
_ROOT = Path(__file__).resolve().parents[2]

STATE_HEARING_LABELS = {
    "KS": "State (Kansas)",
    "CO": "State (Colorado)",
    "AZ": "State (Arizona)",
    "UT": "State (Utah)",
    "ME": "State (Maine)",
    "NE": "State (Nebraska)",
    "MD": "State (Maryland)",
    "PA": "State (Pennsylvania)",
    "MA": "State (Massachusetts)",
    "WV": "State (West Virginia)",
    "TN": "State (Tennessee)",
    "NC": "State (North Carolina)",
    "MO": "State (Missouri)",
    "IA": "State (Iowa)",
}


def hearing_dedup_key(hearing: Dict[str, Any]) -> str:
    url = hearing.get("url") or hearing.get("link") or ""
    if url:
        return str(url)
    return (
        f"{hearing.get('title', '')}|{hearing.get('scheduled_date', '')}|"
        f"{hearing.get('state', '')}"
    )


def merge_hearing_lists(
    existing: Sequence[Dict[str, Any]],
    new_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seen = {hearing_dedup_key(h) for h in existing if isinstance(h, dict)}
    merged = [h for h in existing if isinstance(h, dict)]
    for hearing in new_items:
        if not isinstance(hearing, dict):
            continue
        key = hearing_dedup_key(hearing)
        if key not in seen:
            merged.append(hearing)
            seen.add(key)
    return merged


def normalized_event_to_hearing(event: Dict[str, Any]) -> Dict[str, Any]:
    """Map a normalized event row to the hearings page shape."""
    state = event.get("state")
    level = event.get("level", "")
    if level == "federal":
        source = "Federal (US Congress)"
    elif state:
        source = STATE_HEARING_LABELS.get(str(state), f"State ({state})")
    else:
        source = event.get("source", "Unknown")

    committees = event.get("committees") or []
    if isinstance(committees, list):
        committee_names = [
            c if isinstance(c, str) else (c.get("name", "") if isinstance(c, dict) else "")
            for c in committees
        ]
        committees_str = ", ".join(n for n in committee_names if n)
    else:
        committees_str = str(committees)

    return {
        "title": event.get("title", ""),
        "scheduled_date": event.get("scheduled_date", ""),
        "scheduled_time": event.get("scheduled_time", ""),
        "location": event.get("location", ""),
        "committees": committees_str,
        "committee": committees_str.split(",")[0].strip() if committees_str else "",
        "link": event.get("url", ""),
        "url": event.get("url", ""),
        "stream_url": event.get("stream_url", ""),
        "source": source,
        "state": state,
        "level": level,
        "chamber": event.get("chamber", ""),
        "description": event.get("description", ""),
    }


def classify_hearing_by_date(
    hearing: Dict[str, Any],
    today: Optional[datetime] = None,
) -> str:
    """Return 'upcoming' or 'historical'."""
    now = today or datetime.now(timezone.utc)
    scheduled = hearing.get("scheduled_date", "") or ""
    if not scheduled:
        return "upcoming"
    try:
        if "T" in scheduled:
            scheduled_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
        else:
            scheduled_dt = datetime.fromisoformat(scheduled + "T00:00:00+00:00")
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        if scheduled_dt.date() >= now.date():
            return "upcoming"
        return "historical"
    except (ValueError, TypeError):
        return "upcoming"


def hearings_from_normalized_events(
    events: Sequence[Dict[str, Any]],
    *,
    today: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Convert normalized events into upcoming/historical hearing lists.

    Skips congress / kansas_rss sources that summarize already covers elsewhere.
    """
    now = today or datetime.now(timezone.utc)
    upcoming: List[Dict[str, Any]] = []
    historical: List[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        source = event.get("source")
        if source in ("congress", "kansas_rss"):
            continue
        hearing = normalized_event_to_hearing(event)
        if classify_hearing_by_date(hearing, now) == "upcoming":
            upcoming.append(hearing)
        else:
            historical.append(hearing)
    return upcoming, historical


def resolve_hearings_states(
    states: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    config_path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """States for the hearings filters: prefer states.yaml over stale site_data.states.

    Unlike legislators, keep all enabled yaml states even when hearings are empty
    (new Open States jurisdictions often have zero events at first).
    """
    from_yaml = load_enabled_states(config_path)
    if from_yaml:
        return from_yaml

    resolved: List[Dict[str, str]] = []
    seen: set[str] = set()
    for row in states or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip().lower()
        if not code or code in seen:
            continue
        seen.add(code)
        resolved.append({"code": code, "name": str(row.get("name") or code.upper())})
    return resolved


def build_hearings_feed(
    *,
    upcoming_hearings: Optional[Sequence[Dict[str, Any]]] = None,
    historical_hearings: Optional[Sequence[Dict[str, Any]]] = None,
    kansas_calendars: Optional[Dict[str, Any]] = None,
    states: Optional[Sequence[Dict[str, Any]]] = None,
    generated_at: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the hearings page JSON payload (no full site_data)."""
    upcoming = [h for h in (upcoming_hearings or []) if isinstance(h, dict)]
    historical = [h for h in (historical_hearings or []) if isinstance(h, dict)]
    calendars = kansas_calendars if isinstance(kansas_calendars, dict) else {}
    resolved_states = resolve_hearings_states(states, config_path=config_path)
    return {
        "hearings_feed": True,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "states": resolved_states,
        "upcoming_hearings": upcoming,
        "historical_hearings": historical,
        "kansas_calendars": calendars,
        "stats": {
            "upcoming_count": len(upcoming),
            "historical_count": len(historical),
            "state_count": len(resolved_states),
            "kansas_calendar_dates": len(calendars),
        },
    }


def write_hearings_feed(docs_dir: str | Path, payload: Dict[str, Any]) -> Path:
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    out = docs / HEARINGS_FEED_FILENAME
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return out


def write_hearings_feed_artifacts(
    docs_dir: str | Path,
    *,
    upcoming_hearings: Optional[Sequence[Dict[str, Any]]] = None,
    historical_hearings: Optional[Sequence[Dict[str, Any]]] = None,
    kansas_calendars: Optional[Dict[str, Any]] = None,
    states: Optional[Sequence[Dict[str, Any]]] = None,
    generated_at: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> tuple[Path, Dict[str, Any]]:
    """Write docs/hearings.json and return (path, payload)."""
    payload = build_hearings_feed(
        upcoming_hearings=upcoming_hearings,
        historical_hearings=historical_hearings,
        kansas_calendars=kansas_calendars,
        states=states,
        generated_at=generated_at,
        config_path=config_path,
    )
    path = write_hearings_feed(docs_dir, payload)
    return path, payload


def prefer_hearings_from_normalized(
    site_upcoming: Sequence[Dict[str, Any]],
    site_historical: Sequence[Dict[str, Any]],
    *,
    normalized_events_path: Optional[Path] = None,
    today: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Merge normalized events into site_data hearings so stale archives gain new states."""
    upcoming = [h for h in site_upcoming if isinstance(h, dict)]
    historical = [h for h in site_historical if isinstance(h, dict)]
    path = normalized_events_path or (_ROOT / "data" / "normalized" / "events.json")
    if not path.is_file():
        return upcoming, historical
    try:
        events = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return upcoming, historical
    if not isinstance(events, list):
        return upcoming, historical
    extra_up, extra_hist = hearings_from_normalized_events(events, today=today)
    upcoming = merge_hearing_lists(upcoming, extra_up)
    historical = merge_hearing_lists(historical, extra_hist)
    upcoming.sort(key=lambda x: x.get("scheduled_date", "") or "")
    historical.sort(key=lambda x: x.get("scheduled_date", "") or "", reverse=True)
    return upcoming, historical
