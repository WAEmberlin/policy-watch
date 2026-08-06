"""Build slim homepage feed artifacts so index.html need not load site_data.json.

Recent-window rule (documented for operators and home.js consumers):
  Take up to HOME_FEED_MAX_DAYS (default 2) most recent calendar dates on or
  before today (America/Chicago) that contain any feed activity (grouped
  history/legislation/votes OR multi-state search_index bill updates).
  Dates need not be consecutive — if yesterday is empty but today and three
  days ago have items, those two dates are used. Future-dated rows are ignored
  so sparse bad dates cannot empty the homepage.

Older history:
  Every activity date (same rule, unlimited) is also written to
  docs/home_feed_days/YYYY-MM-DD.json. The slim home_feed.json lists
  available_dates so the homepage can page backward and fetch one day at a time
  without parsing full site_data.json.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from processing.bill_action_utils import classify_action_type

HOME_FEED_MAX_DAYS = 2
# Search-index-only days (no grouped history) are browsable only within this lookback.
# Full grouped history remains available; avoids thousands of sparse day files from bill corpora.
HOME_FEED_SEARCH_LOOKBACK_DAYS = 120
HOME_FEED_FILENAME = "home_feed.json"
HOME_FEED_DAYS_DIRNAME = "home_feed_days"
# Compact bill list for on-demand homepage archive search (lazy-loaded by script.js).
HOME_SEARCH_BILLS_FILENAME = "home_search_bills.json"
HOME_SEARCH_SUMMARY_MAX = 160

try:
    from zoneinfo import ZoneInfo

    _CENTRAL = ZoneInfo("America/Chicago")
except Exception:  # pragma: no cover - Windows without tzdata
    _CENTRAL = timezone(timedelta(hours=-6))

_STATE_NAMES = {
    "KS": "Kansas",
    "CO": "Colorado",
    "AZ": "Arizona",
    "UT": "Utah",
    "ME": "Maine",
    "NE": "Nebraska",
    "MD": "Maryland",
    "PA": "Pennsylvania",
    "MA": "Massachusetts",
    "WV": "West Virginia",
    "TN": "Tennessee",
    "NC": "North Carolina",
    "MO": "Missouri",
    "IA": "Iowa",
}

_BILL_COUNT_KEYS = (
    "Federal",
    "KS",
    "CO",
    "AZ",
    "UT",
    "ME",
    "NE",
    "MD",
    "PA",
    "MA",
    "WV",
    "TN",
    "NC",
    "MO",
    "IA",
)

_BILL_NUM_RE = re.compile(r"^([A-Za-z]+)\s*(\d+[A-Za-z]?)$")


def _date_prefix(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""


def _today_central(today: Optional[str] = None) -> str:
    if today:
        return today
    now = datetime.now(_CENTRAL)
    return now.date().isoformat()


def _collect_grouped_dates(site_years: Dict[str, Any], *, on_or_before: str) -> Set[str]:
    dates: Set[str] = set()
    for year_data in (site_years or {}).values():
        grouped = (year_data or {}).get("grouped") or {}
        for date_str, sources in grouped.items():
            if not date_str or date_str > on_or_before:
                continue
            if not sources:
                continue
            if any(items for items in sources.values()):
                dates.add(date_str)
    return dates


def _collect_search_index_dates(search_index: Dict[str, Any], *, on_or_before: str) -> Set[str]:
    """Dates from non-KS state bill updates (appended client-side on the old homepage)."""
    dates: Set[str] = set()
    for bill in (search_index or {}).get("bills") or []:
        if (bill.get("level") or "") == "federal":
            continue
        state = (bill.get("state") or "").upper()
        if not state or state == "KS":
            continue
        day = _date_prefix(bill.get("latest_action_date") or "")
        if day and day <= on_or_before:
            dates.add(day)
    return dates


def _parse_iso_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def collect_recent_candidate_dates(
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    *,
    today: Optional[str] = None,
) -> List[str]:
    """All activity dates used to pick the slim recent window (grouped + search index)."""
    on_or_before = _today_central(today)
    dates = _collect_grouped_dates(site_years, on_or_before=on_or_before)
    dates |= _collect_search_index_dates(search_index or {}, on_or_before=on_or_before)
    return sorted(dates, reverse=True)


def collect_all_feed_dates(
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    *,
    today: Optional[str] = None,
    search_lookback_days: int = HOME_FEED_SEARCH_LOOKBACK_DAYS,
) -> List[str]:
    """Return browseable YYYY-MM-DD dates, newest first.

    Includes every grouped history day, plus search-index-only days within
    search_lookback_days (so recent multi-state-only days remain pageable without
    emitting thousands of sparse archive day files).
    """
    on_or_before = _today_central(today)
    dates = _collect_grouped_dates(site_years, on_or_before=on_or_before)
    search_dates = _collect_search_index_dates(search_index or {}, on_or_before=on_or_before)
    if search_lookback_days is None or int(search_lookback_days) < 0:
        dates |= search_dates
    else:
        cutoff = (_parse_iso_date(on_or_before) - timedelta(days=int(search_lookback_days))).isoformat()
        dates |= {d for d in search_dates if d >= cutoff}
    return sorted(dates, reverse=True)


def select_recent_feed_dates(
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    *,
    max_days: int = HOME_FEED_MAX_DAYS,
    today: Optional[str] = None,
) -> List[str]:
    """Return up to max_days most recent YYYY-MM-DD dates that have activity."""
    return collect_recent_candidate_dates(site_years, search_index, today=today)[
        : max(0, int(max_days))
    ]


def compute_bill_counts(search_index: Dict[str, Any]) -> Dict[str, int]:
    counts = {key: 0 for key in _BILL_COUNT_KEYS}
    for bill in (search_index or {}).get("bills") or []:
        if (bill.get("level") or "") == "federal" or not bill.get("state"):
            counts["Federal"] += 1
            continue
        st = str(bill.get("state") or "").upper()
        if st in counts:
            counts[st] += 1
    return counts


def _multi_state_feed_item(bill: Dict[str, Any], date: str) -> Dict[str, Any]:
    state = (bill.get("state") or "").upper()
    latest_action = bill.get("latest_action") or ""
    bill_number = bill.get("bill_number") or ""
    title = bill.get("title") or ""
    item = {
        "title": f"{bill_number}: {title}" if bill_number else title,
        "short_title": title,
        "link": bill.get("url") or "",
        "summary": bill.get("summary") or latest_action or "",
        "source": f"State ({_STATE_NAMES.get(state, state)})",
        "state": state,
        "level": "state",
        "published": bill.get("latest_action_date") or date,
        "latest_action": latest_action,
        "bill_number": bill_number,
        "classification": bill.get("classification") or [],
        "ai_topics": bill.get("ai_topics") or [],
        "item_type": bill.get("item_type") or "bill_update",
        "action_type": bill.get("action_type") or classify_action_type(latest_action),
    }
    if bill.get("vote_tally"):
        item["vote_tally"] = bill["vote_tally"]
    if bill.get("motion"):
        item["motion"] = bill["motion"]
    return item


def _inject_multi_state_bills(
    slim_years: Dict[str, Any],
    search_index: Dict[str, Any],
    feed_dates: Sequence[str],
) -> int:
    feed_set = set(feed_dates)
    added = 0
    for bill in (search_index or {}).get("bills") or []:
        if (bill.get("level") or "") == "federal":
            continue
        state = (bill.get("state") or "").upper()
        if not state or state == "KS":
            continue
        date = _date_prefix(bill.get("latest_action_date") or "")
        if date not in feed_set:
            continue
        year = date[:4]
        year_data = slim_years.setdefault(year, {"grouped": {}, "total_items": 0, "pages": []})
        grouped = year_data.setdefault("grouped", {})
        day = grouped.setdefault(date, {})
        source = f"State ({_STATE_NAMES.get(state, state)})"
        day.setdefault(source, []).append(_multi_state_feed_item(bill, date))
        added += 1
    return added


def _iter_feed_items(slim_years: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for year_data in (slim_years or {}).values():
        grouped = (year_data or {}).get("grouped") or {}
        for sources in grouped.values():
            for items in (sources or {}).values():
                for item in items or []:
                    yield item


def _veteran_impact_keys_for_item(item: Dict[str, Any]) -> List[str]:
    state = (item.get("state") or "").upper()
    if (item.get("level") or "") == "federal" or not state:
        state = "Federal"
    bill_number = (item.get("bill_number") or "").strip().upper()
    if not bill_number:
        title_match = re.match(r"^([A-Za-z]+\s*\d+[A-Za-z]?)\s*:", item.get("title") or "")
        if title_match:
            bill_number = title_match.group(1).strip().upper()
    if not bill_number:
        return []
    keys = [f"{state}|{bill_number}"]
    compact = re.sub(r"\s+", "", bill_number)
    keys.append(f"{state}|{compact}")
    match = _BILL_NUM_RE.match(bill_number)
    if match:
        keys.append(f"{state}|{match.group(1)} {match.group(2)}")
    # Colorado tracker slugs like HB26-1234
    if state == "CO":
        co = re.match(r"^([A-Z]+)26-(\d+)$", compact) or re.match(r"^([A-Z]+)(\d+)$", compact)
        if co:
            keys.append(f"CO|{co.group(1)}26-{co.group(2)}")
    return keys


def _slim_veteran_lookup(
    lookup: Dict[str, Any],
    slim_years: Dict[str, Any],
) -> Dict[str, Any]:
    if not lookup:
        return {}
    wanted: Set[str] = set()
    for item in _iter_feed_items(slim_years):
        wanted.update(_veteran_impact_keys_for_item(item))
    return {key: lookup[key] for key in wanted if key in lookup}


def _slim_kansas_votes(
    records: Dict[str, Any],
    slim_years: Dict[str, Any],
) -> Dict[str, Any]:
    if not records:
        return {}
    bill_nos: Set[str] = set()
    for item in _iter_feed_items(slim_years):
        state = (item.get("state") or "").upper()
        src = (item.get("source") or "").lower()
        if state and state != "KS" and "kansas" not in src:
            continue
        raw = (item.get("bill_number") or "").strip().upper()
        if not raw:
            continue
        bill_nos.add(re.sub(r"\s+", "", raw))
        bill_nos.add(raw)
        match = _BILL_NUM_RE.match(raw)
        if match:
            bill_nos.add(f"{match.group(1)} {match.group(2)}")
            bill_nos.add(f"{match.group(1)}{match.group(2)}")
    slim = {}
    for key, value in records.items():
        norm = re.sub(r"\s+", "", str(key).upper())
        if key in bill_nos or norm in bill_nos:
            slim[key] = value
    return slim


def _collect_sources_and_categories(slim_years: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    sources: Set[str] = set()
    categories: Set[str] = set()
    for year_data in (slim_years or {}).values():
        grouped = (year_data or {}).get("grouped") or {}
        for date_data in grouped.values():
            for source in date_data.keys():
                sources.add(source)
                if "Kansas Legislature" in source:
                    parts = source.split(" - ")
                    if len(parts) > 1:
                        categories.add(parts[1])
    return sorted(sources), sorted(categories)


def _slim_years_for_dates(site_years: Dict[str, Any], feed_dates: Sequence[str]) -> Dict[str, Any]:
    feed_set = set(feed_dates)
    slim: Dict[str, Any] = {}
    for year, year_data in (site_years or {}).items():
        grouped = (year_data or {}).get("grouped") or {}
        day_map = {}
        total = 0
        for date_str, sources in grouped.items():
            if date_str not in feed_set:
                continue
            # Deep copy so later multi-state injection cannot mutate site_data structures.
            copied = {src: deepcopy(items) for src, items in (sources or {}).items()}
            count = sum(len(items or []) for items in copied.values())
            if count == 0:
                continue
            day_map[date_str] = copied
            total += count
        if day_map:
            slim[year] = {
                "total_items": total,
                "pages": [],
                "grouped": day_map,
            }
    return slim


def _refresh_year_totals(slim_years: Dict[str, Any]) -> int:
    item_count = 0
    for year_data in slim_years.values():
        grouped = year_data.get("grouped") or {}
        total = sum(
            len(items or []) for sources in grouped.values() for items in sources.values()
        )
        year_data["total_items"] = total
        item_count += total
    return item_count


def build_day_feed(
    *,
    date: str,
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    veteran_impact_lookup: Optional[Dict[str, Any]] = None,
    kansas_vote_records: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a single-day homepage feed payload for on-demand older browsing."""
    search_index = search_index or {}
    feed_dates = [date]
    slim_years = _slim_years_for_dates(site_years, feed_dates)
    injected = _inject_multi_state_bills(slim_years, search_index, feed_dates)
    item_count = _refresh_year_totals(slim_years)
    sources, categories = _collect_sources_and_categories(slim_years)
    return {
        "home_feed_day": True,
        "date": date,
        "years": slim_years,
        "sources": sources,
        "categories": categories,
        "veteran_impact": {
            "lookup": _slim_veteran_lookup(veteran_impact_lookup or {}, slim_years),
        },
        "kansas_vote_records": _slim_kansas_votes(kansas_vote_records or {}, slim_years),
        "stats": {
            "feed_item_count": item_count,
            "multi_state_injected": injected,
        },
    }


def build_home_feed(
    *,
    last_updated: str,
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    states: Optional[List[Dict[str, Any]]] = None,
    veteran_impact_lookup: Optional[Dict[str, Any]] = None,
    kansas_vote_records: Optional[Dict[str, Any]] = None,
    action_badges: Optional[Dict[str, Any]] = None,
    max_days: int = HOME_FEED_MAX_DAYS,
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the homepage JSON payload (no full search_index / history dump)."""
    search_index = search_index or {}
    as_of = _today_central(today)
    feed_dates = select_recent_feed_dates(
        site_years, search_index, max_days=max_days, today=as_of
    )
    available_dates = collect_all_feed_dates(site_years, search_index, today=as_of)
    # Recent window days must always be browseable even if search-only outside lookback.
    if feed_dates:
        available_set = set(available_dates)
        available_set.update(feed_dates)
        available_dates = sorted(available_set, reverse=True)
    slim_years = _slim_years_for_dates(site_years, feed_dates)
    injected = _inject_multi_state_bills(slim_years, search_index, feed_dates)
    item_count = _refresh_year_totals(slim_years)

    sources, categories = _collect_sources_and_categories(slim_years)
    bill_counts = compute_bill_counts(search_index)

    return {
        "last_updated": last_updated,
        # Marker so the homepage can skip full site_data.json on first paint.
        "home_feed": True,
        # See module docstring: up to N most recent calendar days with activity.
        "feed_window": {
            "max_days": max_days,
            "as_of": as_of,
            "dates": feed_dates,
            "rule": (
                f"Up to {max_days} most recent calendar dates on or before {as_of} "
                "(America/Chicago) that contain feed activity "
                "(history/legislation/votes or multi-state bill updates)."
            ),
        },
        # Full activity calendar for older-day pagination (filenames under home_feed_days/).
        "available_dates": available_dates,
        "bill_counts": bill_counts,
        "states": states or [],
        "sources": sources,
        "categories": categories,
        "years": slim_years,
        # Empty stubs keep older client helpers from throwing; do not ship the corpus.
        "search_index": {"bills": [], "events": [], "legislators": []},
        "legislation": {"total_items": 0, "pages": []},
        "veteran_impact": {
            "lookup": _slim_veteran_lookup(veteran_impact_lookup or {}, slim_years),
        },
        "kansas_vote_records": _slim_kansas_votes(kansas_vote_records or {}, slim_years),
        "action_badges": action_badges or {},
        "stats": {
            "feed_item_count": item_count,
            "multi_state_injected": injected,
            "feed_day_count": len(feed_dates),
            "available_day_count": len(available_dates),
        },
    }


def build_home_search_bills(search_index: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Compact bill rows for lazy homepage archive search (not full search_index)."""
    rows: List[Dict[str, Any]] = []
    for bill in (search_index or {}).get("bills") or []:
        summary = str(bill.get("summary") or "")
        if len(summary) > HOME_SEARCH_SUMMARY_MAX:
            summary = summary[: HOME_SEARCH_SUMMARY_MAX - 1].rstrip() + "…"
        row = {
            "bill_number": bill.get("bill_number") or "",
            "title": bill.get("title") or "",
            "state": bill.get("state") or "",
            "level": bill.get("level") or "",
            "latest_action": bill.get("latest_action") or "",
            "latest_action_date": bill.get("latest_action_date") or "",
            "url": bill.get("url") or "",
            "item_type": bill.get("item_type") or "bill_update",
            "action_type": bill.get("action_type") or "",
        }
        if summary:
            row["summary"] = summary
        motion = bill.get("motion") or ""
        if motion:
            row["motion"] = motion
        vote_tally = bill.get("vote_tally") or ""
        if vote_tally:
            row["vote_tally"] = vote_tally
        rows.append(row)
    return rows


def write_home_search_bills(docs_dir: str | Path, search_index: Optional[Dict[str, Any]] = None) -> Path:
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    out = docs / HOME_SEARCH_BILLS_FILENAME
    payload = {
        "home_search_bills": True,
        "bills": build_home_search_bills(search_index),
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return out


def write_home_feed(docs_dir: str | Path, payload: Dict[str, Any]) -> Path:
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    out = docs / HOME_FEED_FILENAME
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return out


def home_feed_day_path(docs_dir: str | Path, date: str) -> Path:
    return Path(docs_dir) / HOME_FEED_DAYS_DIRNAME / f"{date}.json"


def write_home_feed_day(docs_dir: str | Path, payload: Dict[str, Any]) -> Path:
    date = payload.get("date") or ""
    if not date:
        raise ValueError("day feed payload missing date")
    out = home_feed_day_path(docs_dir, date)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return out


def write_home_feed_days(
    docs_dir: str | Path,
    *,
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    veteran_impact_lookup: Optional[Dict[str, Any]] = None,
    kansas_vote_records: Optional[Dict[str, Any]] = None,
    today: Optional[str] = None,
    dates: Optional[Sequence[str]] = None,
) -> Tuple[List[str], List[Path]]:
    """Write one JSON file per activity date; remove stale day files."""
    search_index = search_index or {}
    feed_dates = list(dates) if dates is not None else collect_all_feed_dates(
        site_years, search_index, today=today
    )
    days_dir = Path(docs_dir) / HOME_FEED_DAYS_DIRNAME
    days_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    keep = set(feed_dates)
    for date in feed_dates:
        payload = build_day_feed(
            date=date,
            site_years=site_years,
            search_index=search_index,
            veteran_impact_lookup=veteran_impact_lookup,
            kansas_vote_records=kansas_vote_records,
        )
        written.append(write_home_feed_day(docs_dir, payload))

    for path in days_dir.glob("*.json"):
        if path.stem not in keep:
            path.unlink()

    return feed_dates, written


def write_home_feed_artifacts(
    docs_dir: str | Path,
    *,
    last_updated: str,
    site_years: Dict[str, Any],
    search_index: Optional[Dict[str, Any]] = None,
    states: Optional[List[Dict[str, Any]]] = None,
    veteran_impact_lookup: Optional[Dict[str, Any]] = None,
    kansas_vote_records: Optional[Dict[str, Any]] = None,
    action_badges: Optional[Dict[str, Any]] = None,
    max_days: int = HOME_FEED_MAX_DAYS,
    today: Optional[str] = None,
) -> Tuple[Path, List[Path], Dict[str, Any]]:
    """Write slim home_feed.json plus per-day files under home_feed_days/."""
    payload = build_home_feed(
        last_updated=last_updated,
        site_years=site_years,
        search_index=search_index,
        states=states,
        veteran_impact_lookup=veteran_impact_lookup,
        kansas_vote_records=kansas_vote_records,
        action_badges=action_badges,
        max_days=max_days,
        today=today,
    )
    search_bills = build_home_search_bills(search_index)
    payload.setdefault("stats", {})["home_search_bill_count"] = len(search_bills)
    home_path = write_home_feed(docs_dir, payload)
    search_path = Path(docs_dir) / HOME_SEARCH_BILLS_FILENAME
    search_path.parent.mkdir(parents=True, exist_ok=True)
    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(
            {"home_search_bills": True, "bills": search_bills},
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    _, day_paths = write_home_feed_days(
        docs_dir,
        site_years=site_years,
        search_index=search_index,
        veteran_impact_lookup=veteran_impact_lookup,
        kansas_vote_records=kansas_vote_records,
        today=today,
        dates=payload.get("available_dates") or [],
    )
    return home_path, day_paths, payload


def build_home_feed_from_site_data(
    site_data: Dict[str, Any],
    *,
    max_days: int = HOME_FEED_MAX_DAYS,
    today: Optional[str] = None,
    search_index: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience for one-off rebuilds from an existing site_data.json dict."""
    veteran = site_data.get("veteran_impact") or {}
    return build_home_feed(
        last_updated=site_data.get("last_updated") or datetime.now().isoformat(),
        site_years=site_data.get("years") or {},
        search_index=search_index if search_index is not None else (site_data.get("search_index") or {}),
        states=site_data.get("states") or [],
        veteran_impact_lookup=veteran.get("lookup") or {},
        kansas_vote_records=site_data.get("kansas_vote_records") or {},
        action_badges=site_data.get("action_badges") or {},
        max_days=max_days,
        today=today,
    )
