"""Classify bill actions and build vote feed events for the homepage timeline."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from processing.bill_urls import build_ks_bill_url, pick_best_bill_url, rewrite_congress_vote_url

# Signed/enacted patterns aligned with unified_search.py dashboards
_ENACTED_KEYWORDS = ("signed", "became public law", "enacted", "chaptered")
_ENACTED_RE = re.compile(
    r"act no\.|chapter \d+|delivered to secretary of state",
    re.I,
)
_VETOED_KEYWORDS = ("veto sustained", "vetoed", "veto override failed", "veto")
_DIED_KEYWORDS = (
    "died in",
    "died on",
    "failed of passage",
    "indefinitely postponed",
    "tabled indefinitely",
    " died",
)
_WITHDRAWN_KEYWORDS = ("withdrawn",)
_PRESENTED_KEYWORDS = ("presented to the president", "presented to president")
_PASSED_KEYWORDS = ("passed", "adopted", "agreed to", "was adopted")
_CALENDAR_RE = re.compile(
    r"placed on .{0,80}calendar"
    r"|legislative calendar"
    r"|under general orders"
    r"|on the union calendar"
    r"|placed on general orders"
    r"|orders of the day"
    r"|ordered to (?:a )?(?:second|third|2nd|3rd) reading"
    r"|on (?:2nd|3rd|second|third) reading"
    r"|calendar no\.?",
    re.I,
)
_REPORTED_RE = re.compile(
    r"ordered to be reported|ordered reported|re-?reported|"
    r"reported favorably|reported adversely|"
    r"reported with (?:an |a )?(?:amendment|substitute)",
    re.I,
)
_STUDY_RE = re.compile(r"accompanied a study order|study order", re.I)
_DRAFT_RE = re.compile(r"accompanied a new draft", re.I)
_TABLED_RE = re.compile(r"laid (?:up )?on the table|\btabled\b", re.I)
_HEARD_RE = re.compile(r"hearings?\s+held", re.I)
_INTRODUCED_RE = re.compile(
    r"\bintroduced\b|"
    r"\ba petition\b|"
    r"joint petition|"
    r"by representative|"
    r"by senator|"
    r"read (?:for the )?first time|"
    r"first reading|"
    r"prefiled",
    re.I,
)
_REFERRED_KEYWORDS = ("referred to", "referred", "re-committed", "recommitted")
# WV journal style: "To House Education", "To Judiciary" (no "referred").
_COMMITTEE_REFERRED_RE = re.compile(
    r"^\s*to (?:(?:house|senate)\s+)?(?!the\b)[a-z]",
    re.I,
)
_FILED_KEYWORDS = ("placed on file",)
_HEARING_SCHEDULED_RE = re.compile(
    r"hearing\s+scheduled|scheduled\s+(?:for\s+(?:a\s+)?)?hearing|"
    r"hearing:|misc_he_\d+",
    re.I,
)
# MA General Court files amendment vehicles as "Text of an amendment, see S1234".
_AMENDMENT_TEXT_RE = re.compile(
    r"text of (?:an |a further )?amendment",
    re.I,
)
_VOTE_KEYWORDS = ("roll call", "recorded vote", "vote on", " rc ")

_PASS_RESULT_KEYWORDS = ("pass", "passed", "adopted", "agreed", "yea", "yes")
_FAIL_RESULT_KEYWORDS = ("fail", "failed", "reject", "lost", "nay", "no")

ACTION_BADGES: Dict[str, Dict[str, str]] = {
    "passed": {"label": "Passed", "class": "bg-green-100 text-green-800"},
    "failed": {"label": "Failed", "class": "bg-red-100 text-red-800"},
    "vetoed": {"label": "Vetoed", "class": "bg-orange-100 text-orange-800"},
    "died": {"label": "Died", "class": "bg-slate-100 text-slate-700"},
    "enacted": {"label": "Enacted", "class": "bg-emerald-100 text-emerald-800"},
    "withdrawn": {"label": "Withdrawn", "class": "bg-slate-100 text-slate-600"},
    "referred": {"label": "Referred", "class": "bg-blue-100 text-blue-800"},
    "presented": {"label": "Presented", "class": "bg-amber-100 text-amber-800"},
    "calendar": {"label": "On Calendar", "class": "bg-amber-100 text-amber-800"},
    "filed": {"label": "On File", "class": "bg-amber-100 text-amber-800"},
    "scheduled": {"label": "Scheduled", "class": "bg-amber-100 text-amber-800"},
    "amendment": {"label": "Amendment", "class": "bg-amber-100 text-amber-800"},
    "reported": {"label": "Reported", "class": "bg-amber-100 text-amber-800"},
    "study": {"label": "Study Order", "class": "bg-amber-100 text-amber-800"},
    "draft": {"label": "New Draft", "class": "bg-amber-100 text-amber-800"},
    "introduced": {"label": "Introduced", "class": "bg-amber-100 text-amber-800"},
    "tabled": {"label": "Tabled", "class": "bg-amber-100 text-amber-800"},
    "heard": {"label": "Heard", "class": "bg-amber-100 text-amber-800"},
    "enrolled": {"label": "Enrolled", "class": "bg-amber-100 text-amber-800"},
    "vote": {"label": "Vote", "class": "bg-indigo-100 text-indigo-800"},
}

_BILL_NUMBER_RE = re.compile(r"^([A-Za-z]+)\s*(\d+)$")

# Homepage feed paginates in 14-day windows; cap vote events to keep site_data.json lean.
VOTE_FEED_DAYS_BACK = 365


def classify_action_type(text: str) -> str | None:
    """Return: passed, vetoed, died, enacted, withdrawn, presented, calendar, reported, filed, scheduled, amendment, study, introduced, referred, vote, or None."""
    lower = (text or "").lower()
    if not lower:
        return None

    if any(kw in lower for kw in _ENACTED_KEYWORDS) or _ENACTED_RE.search(lower):
        return "enacted"
    if any(kw in lower for kw in _VETOED_KEYWORDS):
        return "vetoed"
    if any(kw in lower for kw in _DIED_KEYWORDS) or "failed to pass" in lower:
        return "died"
    if re.search(r"\bfailed\b", lower):
        return "failed"
    if any(kw in lower for kw in _WITHDRAWN_KEYWORDS):
        return "withdrawn"
    if any(kw in lower for kw in _PRESENTED_KEYWORDS):
        return "presented"
    if re.search(r"\benrolled\b", lower):
        return "enrolled"
    if any(kw in lower for kw in _PASSED_KEYWORDS):
        return "passed"
    if _CALENDAR_RE.search(lower):
        return "calendar"
    if _REPORTED_RE.search(lower):
        return "reported"
    if any(kw in lower for kw in _REFERRED_KEYWORDS) or _COMMITTEE_REFERRED_RE.search(lower):
        return "referred"
    if any(kw in lower for kw in _FILED_KEYWORDS):
        return "filed"
    if _TABLED_RE.search(lower):
        return "tabled"
    if _HEARING_SCHEDULED_RE.search(lower):
        return "scheduled"
    if _AMENDMENT_TEXT_RE.search(lower):
        return "amendment"
    if _STUDY_RE.search(lower):
        return "study"
    if _DRAFT_RE.search(lower):
        return "draft"
    if _INTRODUCED_RE.search(lower):
        return "introduced"
    if _HEARD_RE.search(lower):
        return "heard"
    if any(kw in lower for kw in _VOTE_KEYWORDS):
        return "vote"
    return None


def action_badge_label(action_type: str) -> str:
    """Human label: Passed, Vetoed, Died, Enacted, etc."""
    entry = ACTION_BADGES.get(action_type or "")
    return entry["label"] if entry else (action_type or "").replace("_", " ").title()


def format_vote_tally(
    result: str,
    yeas: int | None,
    nays: int | None,
    yes_count: int | None = None,
    no_count: int | None = None,
) -> str:
    """Return e.g. 'Passed 220–210' or 'Failed 180–245'."""
    yea = yeas if yeas is not None else yes_count
    nay = nays if nays is not None else no_count
    outcome = classify_vote_outcome(result, yea, nay)
    label = "Passed" if outcome == "passed" else "Failed" if outcome == "failed" else "Vote"
    if yea is not None and nay is not None:
        return f"{label} {yea}–{nay}"
    return label


def classify_vote_outcome(result: str, yeas: int | None, nays: int | None) -> str:
    """Return passed, failed, or vote."""
    lower = (result or "").lower()
    if any(kw in lower for kw in _FAIL_RESULT_KEYWORDS):
        if not any(kw in lower for kw in _PASS_RESULT_KEYWORDS):
            return "failed"
    if any(kw in lower for kw in _PASS_RESULT_KEYWORDS):
        return "passed"
    if yeas is not None and nays is not None:
        if yeas > nays:
            return "passed"
        if nays > yeas:
            return "failed"
    return "vote"


def format_bill_display_number(bill_number: str) -> str:
    normalized = (bill_number or "").strip()
    match = _BILL_NUMBER_RE.match(normalized)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    return normalized


def enrich_bill_feed_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Add action_type and item_type to an existing bill card."""
    action_text = item.get("latest_action") or item.get("action") or ""
    item["action_type"] = classify_action_type(action_text)
    item["item_type"] = "bill_update"
    return item


def is_bill_feed_item(item: Dict[str, Any]) -> bool:
    """True when a grouped feed row represents bill activity (not hearings)."""
    if item.get("item_type") == "vote_event":
        return False
    if item.get("type") == "state_hearing":
        return False
    if item.get("feed") == "conference_committees":
        return False
    return bool(
        item.get("bill_number")
        or item.get("latest_action")
        or item.get("type") == "state_legislation"
        or item.get("bill_type")
        or "congress.gov" in (item.get("link") or "").lower()
    )


def _parse_iso_date(value: str) -> Tuple[str, str]:
    """Return (YYYY-MM-DD, full ISO published string)."""
    if not value:
        return "", ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d"), dt.isoformat()
    except ValueError:
        if len(value) >= 10 and value[4] == "-":
            return value[:10], value
        return "", value


def _counts_from_openstates(counts: Iterable[Dict[str, Any]]) -> Tuple[int | None, int | None]:
    yes = no = None
    for row in counts or []:
        option = (row.get("option") or "").lower()
        value = row.get("value")
        if value is None:
            continue
        if option in ("yes", "yea"):
            yes = int(value)
        elif option in ("no", "nay"):
            no = int(value)
    return yes, no


def _counts_from_tally(tally: Dict[str, Any]) -> Tuple[int | None, int | None]:
    if not isinstance(tally, dict):
        return None, None
    yeas = tally.get("yea")
    nays = tally.get("nay")
    return (
        int(yeas) if yeas is not None else None,
        int(nays) if nays is not None else None,
    )


def _extract_motion(result: str, motion: str = "") -> str:
    if motion:
        return motion.strip()
    text = (result or "").strip().rstrip(";")
    if " - " in text:
        return text.split(" - ", 1)[0].strip()
    if " was " in text.lower():
        return text.split(" was ", 1)[0].strip()
    return text or "Roll call vote"


def _vote_dedup_key(bill_number: str, date: str, motion: str) -> Tuple[str, str, str]:
    return (
        re.sub(r"\s+", "", (bill_number or "")).upper(),
        (date or "")[:10],
        (motion or "").strip().lower(),
    )


def _resolve_vote_link(state: str, bill_number: str, url: str = "", bill_url_lookup: Dict[str, str] | None = None) -> str:
    if url:
        return rewrite_congress_vote_url(url)
    lookup = bill_url_lookup or {}
    normalized_number = re.sub(r"\s+", "", bill_number).upper()
    key = f"{state.upper()}:{normalized_number}"
    if key in lookup:
        return lookup[key]
    if state.upper() == "KS":
        return build_ks_bill_url(bill_number)
    return ""


def _build_vote_event(
    *,
    bill_number: str,
    state: str,
    level: str,
    source: str,
    result: str,
    motion: str,
    date: str,
    yeas: int | None,
    nays: int | None,
    link: str = "",
    bill_url_lookup: Dict[str, str] | None = None,
) -> Dict[str, Any] | None:
    date_key, published = _parse_iso_date(date)
    if not date_key:
        return None

    display_bill = format_bill_display_number(bill_number)
    motion_label = _extract_motion(result, motion)
    outcome = classify_vote_outcome(result, yeas, nays)
    tally = format_vote_tally(result, yeas, nays)

    return {
        "item_type": "vote_event",
        "action_type": outcome,
        "title": f"{display_bill}: {motion_label}",
        "bill_number": display_bill,
        "state": state,
        "vote_tally": tally,
        "motion": motion_label,
        "summary": f"Roll call vote — {tally}",
        "published": published,
        "link": _resolve_vote_link(state, bill_number, link, bill_url_lookup),
        "source": source,
        "level": level,
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _events_from_kansas_votes(
    records: Dict[str, List[Dict[str, Any]]],
    seen: Set[Tuple[str, str, str]],
    bill_url_lookup: Dict[str, str] | None,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for _bill_key, votes in (records or {}).items():
        if not isinstance(votes, list):
            continue
        for vote in votes:
            if not isinstance(vote, dict):
                continue
            bill_number = vote.get("bill_number") or _bill_key
            result = vote.get("result") or ""
            motion = vote.get("motion") or ""
            yeas, nays = _counts_from_tally(vote.get("tally") or {})
            motion_label = _extract_motion(result, motion)
            date_key, _ = _parse_iso_date(vote.get("date") or "")
            dedup = _vote_dedup_key(bill_number, date_key, motion_label)
            if dedup in seen:
                continue
            event = _build_vote_event(
                bill_number=bill_number,
                state="KS",
                level="state",
                source="Kansas Legislature",
                result=result,
                motion=motion,
                date=vote.get("date") or "",
                yeas=yeas,
                nays=nays,
                bill_url_lookup=bill_url_lookup,
            )
            if event:
                seen.add(dedup)
                events.append(event)
    return events


def _events_from_openstates_votes(
    votes: List[Dict[str, Any]],
    seen: Set[Tuple[str, str, str]],
    bill_url_lookup: Dict[str, str] | None,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for vote in votes or []:
        if not isinstance(vote, dict):
            continue
        bill_number = vote.get("bill_number") or ""
        state = (vote.get("state") or "").upper()
        if not bill_number or not state:
            continue
        motion = vote.get("motion_text") or vote.get("result") or ""
        result = vote.get("result") or motion
        yeas, nays = _counts_from_openstates(vote.get("counts") or [])
        date_key, _ = _parse_iso_date(vote.get("date") or "")
        motion_label = _extract_motion(motion, vote.get("motion_text") or "")
        dedup = _vote_dedup_key(bill_number, date_key, motion_label)
        if dedup in seen:
            continue
        event = _build_vote_event(
            bill_number=bill_number,
            state=state,
            level="state",
            source="Open States",
            result=result,
            motion=vote.get("motion_text") or "",
            date=vote.get("date") or "",
            yeas=yeas,
            nays=nays,
            link=vote.get("url") or "",
            bill_url_lookup=bill_url_lookup,
        )
        if event:
            seen.add(dedup)
            events.append(event)
    return events


def _format_congress_bill_number(vote: Dict[str, Any]) -> str:
    """Combine bill_type + bill_number when stored separately (e.g. HR + 123)."""
    bill_number = (vote.get("bill_number") or "").strip()
    bill_type = (vote.get("bill_type") or "").strip().upper()
    if bill_type and bill_number:
        prefix = bill_type.upper()
        if bill_number.isdigit() or not bill_number.upper().startswith(prefix):
            return f"{bill_type} {bill_number}".strip()
    if not bill_number:
        bill_num = vote.get("number") or vote.get("bill_num") or ""
        return f"{bill_type} {bill_num}".strip()
    return bill_number


def _events_from_congress_votes(
    votes: List[Dict[str, Any]],
    seen: Set[Tuple[str, str, str]],
    bill_url_lookup: Dict[str, str] | None,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for vote in votes or []:
        if not isinstance(vote, dict):
            continue
        bill_number = _format_congress_bill_number(vote)
        if not bill_number:
            continue
        motion = vote.get("motion") or vote.get("question") or vote.get("description") or ""
        result = vote.get("result") or motion
        yeas = vote.get("yeas")
        nays = vote.get("nays")
        if yeas is None:
            yeas = vote.get("yes_count")
        if nays is None:
            nays = vote.get("no_count")
        try:
            yeas = int(yeas) if yeas is not None else None
        except (TypeError, ValueError):
            yeas = None
        try:
            nays = int(nays) if nays is not None else None
        except (TypeError, ValueError):
            nays = None
        date_key, _ = _parse_iso_date(vote.get("date") or vote.get("published") or "")
        motion_label = _extract_motion(result, motion)
        dedup = _vote_dedup_key(bill_number, date_key, motion_label)
        if dedup in seen:
            continue
        event = _build_vote_event(
            bill_number=bill_number,
            state="Federal",
            level="federal",
            source="Congress.gov",
            result=result,
            motion=motion,
            date=vote.get("date") or vote.get("published") or "",
            yeas=yeas,
            nays=nays,
            link=vote.get("url") or vote.get("link") or "",
            bill_url_lookup=bill_url_lookup,
        )
        if event:
            seen.add(dedup)
            events.append(event)
    return events


def build_vote_feed_events(
    root: Path,
    bill_url_lookup: Dict[str, str] | None = None,
) -> List[Dict[str, Any]]:
    """Merge Kansas, Open States, and Congress vote records into feed events."""
    seen: Set[Tuple[str, str, str]] = set()
    events: List[Dict[str, Any]] = []

    kansas_path = root / "data" / "kansas" / "vote_records.json"
    kansas_data = _load_json(kansas_path, {})
    if isinstance(kansas_data, dict):
        kansas_records = {k: v for k, v in kansas_data.items() if k != "_meta" and isinstance(v, list)}
        events.extend(_events_from_kansas_votes(kansas_records, seen, bill_url_lookup))

    os_votes = _load_json(root / "data" / "normalized" / "votes.json", [])
    if isinstance(os_votes, list):
        events.extend(_events_from_openstates_votes(os_votes, seen, bill_url_lookup))

    congress_votes = _load_json(root / "src" / "output" / "congress_votes.json", [])
    if isinstance(congress_votes, list):
        events.extend(_events_from_congress_votes(congress_votes, seen, bill_url_lookup))
    elif isinstance(congress_votes, dict):
        items = congress_votes.get("items") or congress_votes.get("votes") or []
        if isinstance(items, list):
            events.extend(_events_from_congress_votes(items, seen, bill_url_lookup))

    cutoff = datetime.now(timezone.utc) - timedelta(days=VOTE_FEED_DAYS_BACK)
    recent: List[Dict[str, Any]] = []
    for event in events:
        date_key, _ = _parse_iso_date(event.get("published") or "")
        if not date_key:
            continue
        try:
            event_dt = datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if event_dt >= cutoff:
            recent.append(event)

    recent.sort(key=lambda e: e.get("published", ""), reverse=True)
    return recent


def inject_vote_events_into_grouped(
    grouped: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]],
    events: Iterable[Dict[str, Any]],
) -> int:
    """Insert vote events into grouped[year][date][source]; return count added."""
    added = 0
    for event in events:
        published = event.get("published") or ""
        date_key, _ = _parse_iso_date(published)
        if not date_key:
            continue
        year = date_key[:4]
        source = event.get("source") or "Votes"
        grouped.setdefault(year, {}).setdefault(date_key, {}).setdefault(source, []).append(event)
        added += 1
    return added
