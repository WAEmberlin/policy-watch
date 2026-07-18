"""Build per-state and combined Policy Watch email digests."""

from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "email_digests.yaml"
STATES_PATH = ROOT / "config" / "states.yaml"

HISTORY_FILE = ROOT / "src" / "output" / "history.json"
LEGISLATION_FILE = ROOT / "src" / "output" / "legislation.json"
HEARINGS_FILE = ROOT / "src" / "output" / "hearings.json"
NORMALIZED_BILLS_FILE = ROOT / "data" / "normalized" / "bills.json"

FEDERAL_CODE = "FEDERAL"


def load_digest_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state_names() -> Dict[str, str]:
    with open(STATES_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {s["code"].upper(): s["name"] for s in cfg.get("states", []) if s.get("enabled")}


def infer_item_state(item: Dict[str, Any]) -> Optional[str]:
    """Return state code (KS, CO, ...) or FEDERAL."""
    level = item.get("level", "")
    if level == "federal":
        return FEDERAL_CODE
    state = item.get("state")
    if state:
        return str(state).upper()
    src = (item.get("source") or "").lower()
    if any(k in src for k in ("congress", "federal", "u.s. congress")):
        return FEDERAL_CODE
    if "kansas" in src:
        return "KS"
    if "colorado" in src:
        return "CO"
    if "arizona" in src:
        return "AZ"
    if "utah" in src:
        return "UT"
    if "maine" in src:
        return "ME"
    if "nebraska" in src:
        return "NE"
    if "maryland" in src:
        return "MD"
    if item.get("type") == "state_legislation" and item.get("state"):
        return str(item["state"]).upper()
    return None


def infer_hearing_state(hearing: Dict[str, Any]) -> Optional[str]:
    if hearing.get("level") == "federal":
        return FEDERAL_CODE
    if hearing.get("state"):
        return str(hearing["state"]).upper()
    src = (hearing.get("source") or "").lower()
    if "federal" in src or "congress" in src:
        return FEDERAL_CODE
    if "kansas" in src:
        return "KS"
    if "colorado" in src:
        return "CO"
    if "arizona" in src:
        return "AZ"
    if "utah" in src:
        return "UT"
    if "maine" in src:
        return "ME"
    if "nebraska" in src:
        return "NE"
    if "maryland" in src:
        return "MD"
    return None


def _parse_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            # Congress/Open States often store date-only actions at midnight UTC.
            # Treat as end of that calendar day in US Central so same-day actions
            # remain in the digest window through the evening.
            if ts.hour == 0 and ts.minute == 0 and ts.second == 0 and ts.microsecond == 0:
                central = ZoneInfo("America/Chicago")
                end_local = datetime.combine(ts.date(), time(23, 59, 59), tzinfo=central)
                return end_local.astimezone(timezone.utc)
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def _recency_fields_for_item(item: Dict[str, Any]) -> Tuple[str, ...]:
    """Fields that reflect legislative activity — not sync or enrichment timestamps."""
    return ("published", "latest_action_date")


def item_recency_ts(item: Dict[str, Any]) -> Optional[datetime]:
    """Best timestamp for whether a bill/item belongs in the digest window."""
    best: Optional[datetime] = None
    for field in _recency_fields_for_item(item):
        ts = _parse_ts(str(item.get(field) or ""))
        if ts and (best is None or ts > best):
            best = ts
    return best


def is_within_window(item: Dict[str, Any], now: datetime, window_hours: int) -> bool:
    ts = item_recency_ts(item)
    if not ts:
        return False
    delta = (now - ts).total_seconds()
    if delta < 0:
        # Future hearing dates fall out here; allow small forward skew from midnight→EOD adjustment.
        return -delta <= window_hours * 3600
    return delta <= window_hours * 3600


def hearing_scheduled_date(item: Dict[str, Any]) -> Optional[datetime.date]:
    notice_date = str(item.get("notice_date") or "").strip()
    if notice_date:
        for fmt in ("%A, %B %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(notice_date, fmt).date()
            except ValueError:
                continue

    for field in ("scheduled_date", "published"):
        raw = str(item.get(field) or "").strip()
        if not raw:
            continue
        try:
            if "T" in raw:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
            return datetime.fromisoformat(raw + "T00:00:00+00:00").date()
        except ValueError:
            continue
    return None


def is_hearing_within_lookahead(item: Dict[str, Any], days: int = 1) -> bool:
    hdate = hearing_scheduled_date(item)
    if not hdate:
        return False
    today = datetime.now(timezone.utc).date()
    return today <= hdate <= today + timedelta(days=days)


def load_recent_items(window_hours: int = 24, hearing_lookahead_days: int = 1) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    recent: List[Dict[str, Any]] = []
    seen_links: set = set()

    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)
        if isinstance(history, list):
            for item in history:
                if is_utah_hearing_feed_item(item):
                    if not is_hearing_within_lookahead(item, hearing_lookahead_days):
                        continue
                elif not is_within_window(item, now, window_hours):
                    continue
                entry = dict(item)
                ts = item_recency_ts(item)
                if ts:
                    entry["published"] = ts.isoformat()
                recent.append(entry)

    if LEGISLATION_FILE.exists():
        with open(LEGISLATION_FILE, encoding="utf-8") as f:
            legislation = json.load(f)
        if isinstance(legislation, list):
            for bill in legislation:
                if not is_within_window(bill, now, window_hours):
                    continue
                ts = item_recency_ts(bill)
                display_title = bill.get("short_title") or bill.get("title", "")
                recent.append({
                    "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {display_title}".strip(": "),
                    "summary": bill.get("summary", ""),
                    "source": bill.get("source", "Congress.gov API"),
                    "published": ts.isoformat() if ts else bill.get("latest_action_date", ""),
                    "link": bill.get("url", ""),
                    "bill_number": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}".strip(),
                    "official_title": bill.get("official_title", ""),
                    "short_title": bill.get("short_title", ""),
                    "latest_action": bill.get("latest_action", ""),
                    "level": "federal",
                })

    if NORMALIZED_BILLS_FILE.exists():
        with open(NORMALIZED_BILLS_FILE, encoding="utf-8") as f:
            normalized_bills = json.load(f)
        if isinstance(normalized_bills, list):
            for bill in normalized_bills:
                if not is_within_window(bill, now, window_hours):
                    continue
                url = bill.get("url", "")
                if url and url in seen_links:
                    continue
                if url:
                    seen_links.add(url)
                ts = item_recency_ts(bill)
                display_title = bill.get("title", "")
                bill_num = bill.get("bill_number", "")
                recent.append({
                    "title": f"{bill_num}: {display_title}" if bill_num else display_title,
                    "summary": bill.get("summary") or bill.get("ai_summary_short", ""),
                    "source": bill.get("source", "openstates"),
                    "published": ts.isoformat() if ts else bill.get("latest_action_date", ""),
                    "link": url,
                    "bill_number": bill_num,
                    "latest_action": bill.get("latest_action", ""),
                    "level": bill.get("level", ""),
                    "state": bill.get("state"),
                    "short_title": display_title,
                })

    recent.sort(key=lambda x: x.get("published", ""), reverse=True)
    return recent


def load_upcoming_hearings(max_days_ahead: int = 1) -> List[Dict[str, Any]]:
    """Hearings scheduled today through max_days_ahead (default: today + tomorrow)."""
    now = datetime.now(timezone.utc)
    today = now.date()
    end = today + timedelta(days=max_days_ahead)
    hearings: List[Dict[str, Any]] = []

    if not HEARINGS_FILE.exists():
        return hearings

    with open(HEARINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return hearings

    for hearing in items:
        scheduled = hearing.get("scheduled_date", "")
        if not scheduled:
            continue
        try:
            if "T" in scheduled:
                hdate = datetime.fromisoformat(scheduled.replace("Z", "+00:00")).date()
            else:
                hdate = datetime.fromisoformat(scheduled + "T00:00:00+00:00").date()
            if today <= hdate <= end:
                hearings.append(dict(hearing))
        except (ValueError, AttributeError):
            continue
    return hearings


def load_tomorrow_hearings() -> List[Dict[str, Any]]:
    """Backward-compatible alias — now returns today and tomorrow."""
    return load_upcoming_hearings(max_days_ahead=1)


def partition_by_state(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        code = infer_item_state(item) or "OTHER"
        buckets.setdefault(code, []).append(item)
    return buckets


def partition_hearings(hearings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for h in hearings:
        code = infer_hearing_state(h) or "OTHER"
        buckets.setdefault(code, []).append(h)
    return buckets


def is_utah_hearing_feed_item(item: Dict[str, Any]) -> bool:
    """Utah committee RSS notices belong in Hearing Updates, not general Updates."""
    if item.get("feed") == "utah_committee_rss":
        return True
    return item.get("type") == "state_hearing" and infer_item_state(item) == "UT"


def split_state_items(
    items: List[Dict[str, Any]],
    *,
    hearing_lookahead_days: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    updates = [item for item in items if not is_utah_hearing_feed_item(item)]
    hearing_updates = [
        item for item in items
        if is_utah_hearing_feed_item(item)
        and is_hearing_within_lookahead(item, hearing_lookahead_days)
    ]
    return updates, hearing_updates


def render_item(item: Dict[str, Any]) -> str:
    display_title = item.get("short_title") or item.get("title", "(no title)")
    html = f"<li><strong>{display_title}</strong><br>"
    if item.get("bill_number"):
        html += f"<em>Bill: {item.get('bill_number')}</em><br>"
    action = item.get("latest_action") or item.get("ks_api_latest_action")
    if action:
        html += f"<em>Latest action: {action}</em><br>"
    official = item.get("official_title", "")
    if official and official != display_title:
        html += f"<em style='color:#666;font-size:0.9em;'>Official: {official}</em><br>"
    link = item.get("link") or item.get("url") or "#"
    html += f'<a href="{link}">{link}</a><br><p>{item.get("summary", "")}</p></li><hr>'
    return html


def render_utah_hearing_update(item: Dict[str, Any]) -> str:
    display_title = item.get("title", "(no title)")
    html = f"<li><strong>{display_title}</strong><br>"

    notice_date = item.get("notice_date", "")
    notice_time = item.get("notice_time", "")
    notice_place = item.get("notice_place") or item.get("location", "")
    if notice_date:
        html += f"Date: {notice_date}<br>"
    if notice_time:
        html += f"Time: {notice_time}<br>"
    if notice_place:
        html += f"Place: {notice_place}<br>"

    link = item.get("link") or item.get("url") or ""
    if link:
        html += f'<a href="{link}">View notice</a><br>'

    stream_url = item.get("livestream_url") or item.get("stream_url") or ""
    if stream_url:
        html += f'<a href="{stream_url}">Live stream options</a><br>'

    agenda_items = [
        entry for entry in (item.get("agenda_items") or [])
        if str(entry).strip().upper() != "NOTICE"
    ]
    summary = item.get("summary", "")
    if summary and summary.strip().upper() != "NOTICE":
        if not agenda_items:
            html += f"<p>{summary}</p>"
    if agenda_items:
        html += f"<p>{'; '.join(agenda_items[:5])}</p>"

    return html + "</li><hr>"


def render_hearing(hearing: Dict[str, Any]) -> str:
    title = hearing.get("title", "(no title)")
    committee = hearing.get("committee") or hearing.get("committees", "")
    chamber = hearing.get("chamber", "")
    time_str = hearing.get("scheduled_time", "")
    location = hearing.get("location", "")
    url = hearing.get("url") or hearing.get("link", "")
    is_federal = infer_hearing_state(hearing) == FEDERAL_CODE

    info = f"<strong>{title}</strong>"
    if committee:
        info += f"<br>Committee: {committee}"
    if chamber:
        info += f" ({chamber})"
    if time_str:
        info += f"<br>Time: {time_str}"
    if location:
        info += f"<br>Location: {location}"
    if url:
        label = "View on Congress.gov" if is_federal else "View details"
        info += f'<br><a href="{url}">{label}</a>'
    return f"<li>{info}</li><hr>"


def _render_items_section(title: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return f"<h3>{title}</h3><p><em>No updates in this period.</em></p>"
    html = f"<h3>{title}</h3><ul>"
    for item in items:
        html += render_item(item)
    html += "</ul>"
    return html


def _render_hearing_updates_section(title: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    html = f"<h3>{title}</h3><ul>"
    for item in items:
        html += render_utah_hearing_update(item)
    html += "</ul>"
    return html


def _render_state_sections(name: str, state_items: List[Dict[str, Any]]) -> str:
    cfg = load_digest_config()
    lookahead = int(cfg.get("hearing_lookahead_days", 1))
    updates, hearing_updates = split_state_items(state_items, hearing_lookahead_days=lookahead)
    html = _render_items_section(f"{name} — Updates", updates)
    html += _render_hearing_updates_section(f"{name} — Hearing Updates", hearing_updates)
    return html


def _render_hearings_section(title: str, hearings: List[Dict[str, Any]]) -> str:
    if not hearings:
        return ""
    html = f"<h3>{title}</h3><ul>"
    for h in hearings:
        html += render_hearing(h)
    html += "</ul>"
    return html


def build_digest_html(
    digest_id: str,
    items_by_state: Dict[str, List[Dict[str, Any]]],
    hearings_by_state: Dict[str, List[Dict[str, Any]]],
    state_names: Dict[str, str],
) -> Tuple[str, str, int]:
    """
    Build HTML body, subject line, and total item count for a digest.
    digest_id: ks, co, az, ut, federal, all
    """
    federal_items = items_by_state.get(FEDERAL_CODE, [])
    federal_hearings = hearings_by_state.get(FEDERAL_CODE, [])
    cfg = load_digest_config()
    digest_meta = next((d for d in cfg["digests"] if d["id"] == digest_id), None)
    prefix = digest_meta["subject_prefix"] if digest_meta else "Policy Watch"
    window = cfg.get("window_hours", 6)

    html = ""

    if digest_id == "all":
        display_name = "Policy Watch — All States"
        html += f"<h1>{display_name}</h1>"
        html += f"<p>Legislative updates from the last {window} hours.</p>"

        total = 0
        # Alphabetical by state name
        state_codes = sorted(
            [c for c in items_by_state if c not in (FEDERAL_CODE, "OTHER")],
            key=lambda c: state_names.get(c, c),
        )
        for code in state_codes:
            name = state_names.get(code, code)
            state_items = items_by_state.get(code, [])
            state_hearings = hearings_by_state.get(code, [])
            total += len(state_items) + len(state_hearings)
            html += f"<h2>{name}</h2>"
            html += _render_state_sections(name, state_items)
            html += _render_hearings_section(f"{name} — Hearings Today & Tomorrow", state_hearings)

        total += len(federal_items) + len(federal_hearings)
        html += "<h2>Federal (U.S. Congress)</h2>"
        html += _render_items_section("Federal — Updates", federal_items)
        html += _render_hearings_section("Federal — Hearings Today & Tomorrow", federal_hearings)

        if total == 0:
            subject = f"{prefix} — No new updates"
            html += f"<p>No new legislative updates in the last {window} hours. Monitoring is active.</p>"
        else:
            subject = f"{prefix} — All States — {total} update{'s' if total != 1 else ''}"
        return html, subject, total

    if digest_id == "federal":
        display_name = "Federal Policy Watch"
        html += f"<h1>{display_name}</h1>"
        html += f"<p>U.S. Congress updates from the last {window} hours.</p>"
        total = len(federal_items) + len(federal_hearings)
        html += _render_items_section("Federal Legislation &amp; Congress Updates", federal_items)
        html += _render_hearings_section("Congressional Hearings Today & Tomorrow", federal_hearings)
        if total == 0:
            subject = f"{prefix} — No new updates"
        else:
            subject = f"{prefix} — {total} update{'s' if total != 1 else ''}"
        return html, subject, total

    # Per-state digest: state first, federal below
    code = digest_id.upper()
    name = state_names.get(code, digest_id.title())
    state_items = items_by_state.get(code, [])
    state_hearings = hearings_by_state.get(code, [])
    total = len(state_items) + len(state_hearings) + len(federal_items) + len(federal_hearings)

    html += f"<h1>{name} Policy Watch</h1>"
    html += f"<p>{name} legislative updates from the last {window} hours, plus relevant federal activity.</p>"

    html += f"<h2>{name}</h2>"
    html += _render_state_sections(name, state_items)
    html += _render_hearings_section(f"{name} — Hearings Today & Tomorrow", state_hearings)

    html += "<h2>Federal (U.S. Congress)</h2>"
    html += _render_items_section("Federal — Updates", federal_items)
    html += _render_hearings_section("Federal — Hearings Today & Tomorrow", federal_hearings)

    if total == 0:
        subject = f"{prefix} — No new updates"
        html += f"<p>No new updates in the last {window} hours. Monitoring is active.</p>"
    else:
        state_count = len(state_items) + len(state_hearings)
        subject = f"{prefix} — {state_count} state + {len(federal_items) + len(federal_hearings)} federal update{'s' if total != 1 else ''}"

    return html, subject, total
