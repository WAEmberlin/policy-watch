"""Build per-state and combined Policy Watch email digests."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    return None


def _parse_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def load_recent_items(window_hours: int = 6) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff = window_hours * 3600
    recent: List[Dict[str, Any]] = []
    seen_links: set = set()

    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)
        if isinstance(history, list):
            for item in history:
                ts = _parse_ts(item.get("published", ""))
                if ts and (now - ts).total_seconds() <= cutoff:
                    recent.append(dict(item))

    if LEGISLATION_FILE.exists():
        with open(LEGISLATION_FILE, encoding="utf-8") as f:
            legislation = json.load(f)
        if isinstance(legislation, list):
            for bill in legislation:
                date_str = bill.get("latest_action_date") or bill.get("published", "")
                ts = _parse_ts(date_str)
                if not ts or (now - ts).total_seconds() > cutoff:
                    continue
                display_title = bill.get("short_title") or bill.get("title", "")
                recent.append({
                    "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {display_title}".strip(": "),
                    "summary": bill.get("summary", ""),
                    "source": bill.get("source", "Congress.gov API"),
                    "published": date_str,
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
                date_str = bill.get("latest_action_date") or bill.get("updated_at", "")
                ts = _parse_ts(date_str)
                if not ts or (now - ts).total_seconds() > cutoff:
                    continue
                url = bill.get("url", "")
                if url and url in seen_links:
                    continue
                if url:
                    seen_links.add(url)
                display_title = bill.get("title", "")
                bill_num = bill.get("bill_number", "")
                recent.append({
                    "title": f"{bill_num}: {display_title}" if bill_num else display_title,
                    "summary": bill.get("summary") or bill.get("ai_summary_short", ""),
                    "source": bill.get("source", "openstates"),
                    "published": date_str,
                    "link": url,
                    "bill_number": bill_num,
                    "latest_action": bill.get("latest_action", ""),
                    "level": bill.get("level", ""),
                    "state": bill.get("state"),
                    "short_title": display_title,
                })

    recent.sort(key=lambda x: x.get("published", ""), reverse=True)
    return recent


def load_tomorrow_hearings() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
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
            if hdate == tomorrow:
                hearings.append(dict(hearing))
        except (ValueError, AttributeError):
            continue
    return hearings


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
            html += _render_items_section(f"{name} — Updates", state_items)
            html += _render_hearings_section(f"{name} — Hearings Tomorrow", state_hearings)

        total += len(federal_items) + len(federal_hearings)
        html += "<h2>Federal (U.S. Congress)</h2>"
        html += _render_items_section("Federal — Updates", federal_items)
        html += _render_hearings_section("Federal — Hearings Tomorrow", federal_hearings)

        if total == 0:
            subject = f"{prefix} — No new updates"
            html += "<p>No new legislative updates in the last 6 hours. Monitoring is active.</p>"
        else:
            subject = f"{prefix} — All States — {total} update{'s' if total != 1 else ''}"
        return html, subject, total

    if digest_id == "federal":
        display_name = "Federal Policy Watch"
        html += f"<h1>{display_name}</h1>"
        html += f"<p>U.S. Congress updates from the last {window} hours.</p>"
        total = len(federal_items) + len(federal_hearings)
        html += _render_items_section("Federal Legislation &amp; Congress Updates", federal_items)
        html += _render_hearings_section("Congressional Hearings Tomorrow", federal_hearings)
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
    html += _render_items_section(f"{name} — Updates", state_items)
    html += _render_hearings_section(f"{name} — Hearings Tomorrow", state_hearings)

    html += "<h2>Federal (U.S. Congress)</h2>"
    html += _render_items_section("Federal — Updates", federal_items)
    html += _render_hearings_section("Federal — Hearings Tomorrow", federal_hearings)

    if total == 0:
        subject = f"{prefix} — No new updates"
        html += "<p>No new updates in the last 6 hours. Monitoring is active.</p>"
    else:
        state_count = len(state_items) + len(state_hearings)
        subject = f"{prefix} — {state_count} state + {len(federal_items) + len(federal_hearings)} federal update{'s' if total != 1 else ''}"

    return html, subject, total
