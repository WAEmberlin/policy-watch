"""Build per-state and combined PolicyWatch email digests."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, time, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import yaml

from processing.veteran_impact import (
    IMPACT_LEVELS,
    build_veteran_impact_lookup,
    resolve_veteran_impact_for_item,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "email_digests.yaml"
STATES_PATH = ROOT / "config" / "states.yaml"

HISTORY_FILE = ROOT / "src" / "output" / "history.json"
LEGISLATION_FILE = ROOT / "src" / "output" / "legislation.json"
HEARINGS_FILE = ROOT / "src" / "output" / "hearings.json"
NORMALIZED_BILLS_FILE = ROOT / "data" / "normalized" / "bills.json"

FEDERAL_CODE = "FEDERAL"

# Inline bill-number pill styles matching docs/home.js VETERAN_IMPACT_BADGE
# (red-100/900/200, amber-100/900/200, green-100/900/200). Email clients strip
# most CSS, so these must stay inline.
VETERAN_BILL_NUMBER_STYLES = {
    "red": (
        "display:inline-block;padding:1px 8px;border-radius:4px;"
        "font-style:normal;font-weight:600;"
        "background:#fee2e2;color:#7f1d1d;border:1px solid #fecaca;"
    ),
    "yellow": (
        "display:inline-block;padding:1px 8px;border-radius:4px;"
        "font-style:normal;font-weight:600;"
        "background:#fef3c7;color:#78350f;border:1px solid #fde68a;"
    ),
    "green": (
        "display:inline-block;padding:1px 8px;border-radius:4px;"
        "font-style:normal;font-weight:600;"
        "background:#dcfce7;color:#14532d;border:1px solid #bbf7d0;"
    ),
}

# Email clients wrap poorly on multi-thousand-char omnibus hearing titles.
DIGEST_TITLE_MAX_LEN = 160
DIGEST_AGENDA_ITEM_MAX_LEN = 220
_DIGEST_TITLE_ELLIPSIS = "…"
_BILL_DESIGNATION_RE = re.compile(
    r"\b(?:"
    r"H\.J\.Res\.|S\.J\.Res\.|H\.Con\.Res\.|S\.Con\.Res\.|"
    r"H\.R\.|H\.B\.|S\.B\.|HB|SB|S\."
    r")\s*\d+",
    re.IGNORECASE,
)
_OMNIBUS_PREFIX_SPLIT_RE = re.compile(
    r"^(?P<header>.*?)\b(?P<connector>to consider|to examine|regarding)\b\s*(?P<preamble>.*)$",
    re.IGNORECASE,
)


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
    if "pennsylvania" in src:
        return "PA"
    if "massachusetts" in src:
        return "MA"
    if "west virginia" in src:
        return "WV"
    if "tennessee" in src:
        return "TN"
    if "north carolina" in src:
        return "NC"
    if "missouri" in src:
        return "MO"
    if "iowa" in src:
        return "IA"
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
    if "pennsylvania" in src:
        return "PA"
    if "massachusetts" in src:
        return "MA"
    if "west virginia" in src:
        return "WV"
    if "tennessee" in src:
        return "TN"
    if "north carolina" in src:
        return "NC"
    if "missouri" in src:
        return "MO"
    if "iowa" in src:
        return "IA"
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


def _clause_truncate(text: str, max_length: int, suffix: str = _DIGEST_TITLE_ELLIPSIS) -> str:
    """Truncate at a clause/word boundary; never mid-word when possible."""
    if len(text) <= max_length:
        return text
    budget = max(1, max_length - len(suffix))
    window = text[:budget]
    min_keep = int(budget * 0.45)

    # Prefer clause breaks. Avoid ". " — hearing titles use abbreviations (Jr., U.S.).
    for sep in ("; ", " — ", " – ", " - ", ", "):
        idx = window.rfind(sep)
        if idx >= min_keep:
            return window[:idx].rstrip(" ,;") + suffix

    idx = window.rfind(" ")
    if idx >= int(budget * 0.5):
        return window[:idx].rstrip(" ,;") + suffix
    return window.rstrip() + suffix


def format_digest_title(title: str, max_length: int = DIGEST_TITLE_MAX_LEN) -> str:
    """Shorten long single-line digest titles (bills / non-omnibus hearings)."""
    text = " ".join(str(title or "").split())
    if not text:
        return "(no title)"
    if len(text) <= max_length:
        return text
    return _clause_truncate(text, max_length)


def split_omnibus_hearing_title(title: str) -> Tuple[str, List[str]]:
    """
    Split laundry-list hearing titles into a short header + per-measure bullets.

    Congress business meetings often pack many bill designations into one title
    because that hearing covers all of them. Returns (header, []) when the title
    is not an omnibus list (≥3 bill designations).
    """
    text = " ".join(str(title or "").split())
    if not text:
        return "(no title)", []

    designations = list(_BILL_DESIGNATION_RE.finditer(text))
    if len(designations) < 3:
        return text, []

    prefix = text[: designations[0].start()].rstrip(" ,;")
    bullets: List[str] = []

    split = _OMNIBUS_PREFIX_SPLIT_RE.match(prefix)
    if split and split.group("preamble").strip():
        header = f"{split.group('header').strip()} {split.group('connector').strip()}".strip()
        preamble = split.group("preamble").strip(" ,;")
        if preamble:
            bullets.append(preamble[0].upper() + preamble[1:] if len(preamble) > 1 else preamble)
    else:
        header = prefix or "Hearing agenda"

    for i, match in enumerate(designations):
        start = match.start()
        end = designations[i + 1].start() if i + 1 < len(designations) else len(text)
        chunk = text[start:end].strip().rstrip(" ,;")
        if not chunk:
            continue
        if len(chunk) > DIGEST_AGENDA_ITEM_MAX_LEN:
            chunk = _clause_truncate(chunk, DIGEST_AGENDA_ITEM_MAX_LEN)
        bullets.append(chunk)

    return header or "Hearing agenda", bullets


def render_item(item: Dict[str, Any]) -> str:
    display_title = format_digest_title(item.get("short_title") or item.get("title", "(no title)"))
    html = f"<li><strong>{display_title}</strong><br>"
    bill_number = item.get("bill_number")
    if bill_number:
        html += _render_bill_number_line(str(bill_number), item)
    action = item.get("latest_action") or item.get("ks_api_latest_action")
    if action:
        html += f"<em>Latest action: {action}</em><br>"
    official = item.get("official_title", "")
    if official and official != display_title:
        html += (
            f"<em style='color:#666;font-size:0.9em;'>"
            f"Official: {format_digest_title(official)}</em><br>"
        )
    link = item.get("link") or item.get("url") or "#"
    html += f'<a href="{link}">{link}</a><br><p>{item.get("summary", "")}</p></li><hr>'
    return html


def _render_bill_number_line(bill_number: str, item: Dict[str, Any]) -> str:
    escaped = html_escape(bill_number)
    impact = item.get("veteran_impact") or {}
    level = str(impact.get("level") or "").strip().lower()
    style = VETERAN_BILL_NUMBER_STYLES.get(level)
    if style:
        return f'<em>Bill: <span style="{style}">{escaped}</span></em><br>'
    return f"<em>Bill: {escaped}</em><br>"


def _is_veteran_legislation_item(item: Dict[str, Any]) -> bool:
    """True for veteran bills that belong in the top-of-email veteran section."""
    if is_utah_hearing_feed_item(item):
        return False
    impact = item.get("veteran_impact") or {}
    return str(impact.get("level") or "").strip().lower() in IMPACT_LEVELS


def _split_veteran_legislation(
    items: List[Dict[str, Any]],
    lookup: Dict[str, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Annotate items with veteran impact; veteran bills are not duplicated later."""
    veteran_items: List[Dict[str, Any]] = []
    other_items: List[Dict[str, Any]] = []
    for item in items:
        annotated = dict(item)
        impact = resolve_veteran_impact_for_item(item, lookup)
        if impact:
            annotated["veteran_impact"] = impact
        if _is_veteran_legislation_item(annotated):
            veteran_items.append(annotated)
        else:
            other_items.append(annotated)
    return veteran_items, other_items


def _split_items_by_state(
    items_by_state: Dict[str, List[Dict[str, Any]]],
    lookup: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    veteran_by_state: Dict[str, List[Dict[str, Any]]] = {}
    other_by_state: Dict[str, List[Dict[str, Any]]] = {}
    for code, items in items_by_state.items():
        veteran_items, other_items = _split_veteran_legislation(items, lookup)
        if veteran_items:
            veteran_by_state[code] = veteran_items
        other_by_state[code] = other_items
    return veteran_by_state, other_by_state


def _flatten_veteran_items(
    veteran_by_state: Dict[str, List[Dict[str, Any]]],
    codes_in_order: List[str],
) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    seen_codes = set()
    for code in codes_in_order:
        flattened.extend(veteran_by_state.get(code, []))
        seen_codes.add(code)
    for code, items in veteran_by_state.items():
        if code not in seen_codes:
            flattened.extend(items)
    return flattened


def _veteran_group_label(item: Dict[str, Any], state_names: Dict[str, str]) -> str:
    code = infer_item_state(item)
    if not code or code == FEDERAL_CODE:
        return "Federal"
    return state_names.get(code, code)


def _render_veteran_section(
    veteran_items: List[Dict[str, Any]],
    state_names: Dict[str, str],
) -> str:
    if not veteran_items:
        return ""

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in veteran_items:
        groups.setdefault(_veteran_group_label(item, state_names), []).append(item)

    ordered_labels: List[str] = []
    state_labels = sorted(
        [label for label in groups if label != "Federal"],
        key=lambda name: name.lower(),
    )
    ordered_labels.extend(state_labels)
    if "Federal" in groups:
        ordered_labels.append("Federal")
    for label in groups:
        if label not in ordered_labels:
            ordered_labels.append(label)

    html = (
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;'
        'border-radius:8px;padding:12px 16px;margin:0 0 20px;">'
        "<h2 style=\"margin-top:0;\">Veteran Legislation</h2>"
        "<p style=\"color:#475569;font-size:14px;margin:0 0 12px;\">"
        "Bills in this digest that may affect veterans. Bill numbers are highlighted "
        "red (high impact), yellow (moderate), or green (ceremonial / general), "
        "matching the Veteran Legislation cards on PolicyWatch."
        "</p>"
    )
    show_subheads = len(ordered_labels) > 1
    for label in ordered_labels:
        if show_subheads:
            html += f"<h3>{html_escape(label)}</h3>"
        html += "<ul>"
        for item in groups[label]:
            html += render_item(item)
        html += "</ul>"
    html += "</div>"
    return html


def render_utah_hearing_update(item: Dict[str, Any]) -> str:
    display_title = format_digest_title(item.get("title", "(no title)"))
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
    raw_title = hearing.get("title", "(no title)")
    header, agenda_items = split_omnibus_hearing_title(raw_title)
    if agenda_items:
        info = f"<strong>{header}</strong><ul>"
        for item in agenda_items:
            info += f"<li>{item}</li>"
        info += "</ul>"
    else:
        info = f"<strong>{format_digest_title(raw_title)}</strong>"

    committee = hearing.get("committee") or hearing.get("committees", "")
    chamber = hearing.get("chamber", "")
    time_str = hearing.get("scheduled_time", "")
    location = hearing.get("location", "")
    url = hearing.get("url") or hearing.get("link", "")
    is_federal = infer_hearing_state(hearing) == FEDERAL_CODE

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
    digest_id: state codes from config/email_digests.yaml, plus federal and all.
    Veteran legislation, when present, is listed in a section at the top and
    omitted from the regular Updates lists below.
    """
    lookup = build_veteran_impact_lookup()
    veteran_by_state, other_by_state = _split_items_by_state(items_by_state, lookup)

    federal_items = other_by_state.get(FEDERAL_CODE, [])
    federal_hearings = hearings_by_state.get(FEDERAL_CODE, [])
    cfg = load_digest_config()
    digest_meta = next((d for d in cfg["digests"] if d["id"] == digest_id), None)
    prefix = digest_meta["subject_prefix"] if digest_meta else "PolicyWatch"
    window = cfg.get("window_hours", 6)

    html = ""

    if digest_id == "all":
        display_name = "PolicyWatch — All States"
        html += f"<h1>{display_name}</h1>"
        html += f"<p>Legislative updates from the last {window} hours.</p>"

        state_codes = sorted(
            [c for c in items_by_state if c not in (FEDERAL_CODE, "OTHER")],
            key=lambda c: state_names.get(c, c),
        )
        veteran_items = _flatten_veteran_items(
            veteran_by_state, state_codes + [FEDERAL_CODE],
        )
        html += _render_veteran_section(veteran_items, state_names)

        total = 0
        for code in state_codes:
            name = state_names.get(code, code)
            state_items = other_by_state.get(code, [])
            state_hearings = hearings_by_state.get(code, [])
            total += (
                len(state_items)
                + len(veteran_by_state.get(code, []))
                + len(state_hearings)
            )
            html += f"<h2>{name}</h2>"
            html += _render_state_sections(name, state_items)
            html += _render_hearings_section(f"{name} — Hearings Today & Tomorrow", state_hearings)

        total += (
            len(federal_items)
            + len(veteran_by_state.get(FEDERAL_CODE, []))
            + len(federal_hearings)
        )
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
        display_name = "Federal PolicyWatch"
        html += f"<h1>{display_name}</h1>"
        html += f"<p>U.S. Congress updates from the last {window} hours.</p>"
        veteran_items = veteran_by_state.get(FEDERAL_CODE, [])
        html += _render_veteran_section(veteran_items, state_names)
        total = len(federal_items) + len(veteran_items) + len(federal_hearings)
        html += _render_items_section("Federal Legislation &amp; Congress Updates", federal_items)
        html += _render_hearings_section("Congressional Hearings Today & Tomorrow", federal_hearings)
        if total == 0:
            subject = f"{prefix} — No new updates"
        else:
            subject = f"{prefix} — {total} update{'s' if total != 1 else ''}"
        return html, subject, total

    # Per-state digest: veteran bills first, then state, then federal
    code = digest_id.upper()
    name = state_names.get(code, digest_id.title())
    state_items = other_by_state.get(code, [])
    state_veteran = veteran_by_state.get(code, [])
    federal_veteran = veteran_by_state.get(FEDERAL_CODE, [])
    state_hearings = hearings_by_state.get(code, [])
    total = (
        len(state_items)
        + len(state_veteran)
        + len(state_hearings)
        + len(federal_items)
        + len(federal_veteran)
        + len(federal_hearings)
    )

    html += f"<h1>{name} PolicyWatch</h1>"
    html += f"<p>{name} legislative updates from the last {window} hours, plus relevant federal activity.</p>"
    html += _render_veteran_section(state_veteran + federal_veteran, state_names)

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
        state_count = len(state_items) + len(state_veteran) + len(state_hearings)
        federal_count = len(federal_items) + len(federal_veteran) + len(federal_hearings)
        subject = f"{prefix} — {state_count} state + {federal_count} federal update{'s' if total != 1 else ''}"

    return html, subject, total
