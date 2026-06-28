"""Unified search and dashboard builders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def build_search_index(
    bills: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    legislators: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a lightweight search index for frontend queries."""
    return {
        "bills": [
            {
                "id": b.get("id"),
                "bill_number": b.get("bill_number"),
                "title": b.get("title"),
                "summary": b.get("summary", "")[:500],
                "source": b.get("source"),
                "level": b.get("level"),
                "state": b.get("state"),
                "status": b.get("status"),
                "latest_action": b.get("latest_action"),
                "latest_action_date": b.get("latest_action_date"),
                "chamber": b.get("chamber"),
                "classification": b.get("classification", []),
                "sponsors": [s.get("name", "") for s in (b.get("sponsors") or [])],
                "url": b.get("url"),
                "ai_topics": b.get("ai_topics", []),
            }
            for b in bills
        ],
        "events": [
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "source": e.get("source"),
                "level": e.get("level"),
                "state": e.get("state"),
                "scheduled_date": e.get("scheduled_date"),
                "chamber": e.get("chamber"),
                "url": e.get("url"),
            }
            for e in events
        ],
        "legislators": [
            {
                "id": l.get("id"),
                "name": l.get("name"),
                "party": l.get("party"),
                "state": l.get("state"),
                "district": l.get("district"),
                "chamber": l.get("chamber"),
                "url": l.get("url"),
            }
            for l in legislators
        ],
    }


def search(
    index: Dict[str, Any],
    query: str = "",
    state: str = "",
    level: str = "",
    status: str = "",
    committee: str = "",
    topic: str = "",
    sponsor: str = "",
) -> Dict[str, List[Dict[str, Any]]]:
    """Search across normalized index."""
    q = query.lower().strip()
    results = {"bills": [], "events": [], "legislators": []}

    for bill in index.get("bills", []):
        if state and (bill.get("state") or "").upper() != state.upper() and level != "federal":
            if level == "state" and bill.get("state") != state.upper():
                continue
        if state and bill.get("level") == "state" and (bill.get("state") or "").upper() != state.upper():
            continue
        if level and bill.get("level") != level:
            continue
        if status and status.lower() not in (bill.get("status") or "").lower():
            continue
        if committee and not any(committee.lower() in str(c).lower() for c in (bill.get("classification") or [])):
            if committee.lower() not in (bill.get("latest_action") or "").lower():
                continue
        if sponsor and not any(sponsor.lower() in s.lower() for s in (bill.get("sponsors") or [])):
            continue

        haystack = " ".join([
            bill.get("title", ""),
            bill.get("summary", ""),
            bill.get("bill_number", ""),
            bill.get("latest_action", ""),
            " ".join(bill.get("ai_topics") or []),
        ]).lower()

        if topic and topic.lower() not in haystack:
            continue
        if q and q not in haystack:
            continue

        results["bills"].append(bill)

    for event in index.get("events", []):
        haystack = f"{event.get('title', '')} {event.get('scheduled_date', '')}".lower()
        if state and event.get("level") == "state" and (event.get("state") or "").upper() != state.upper():
            continue
        if level and event.get("level") != level:
            continue
        if q and q not in haystack:
            continue
        results["events"].append(event)

    for leg in index.get("legislators", []):
        haystack = f"{leg.get('name', '')} {leg.get('party', '')} {leg.get('district', '')}".lower()
        if state and (leg.get("state") or "").upper() != state.upper():
            continue
        if q and q not in haystack:
            continue
        results["legislators"].append(leg)

    return results


def build_dashboards(
    bills: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    votes: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build dashboard slices for frontend."""
    now = datetime.now(timezone.utc)
    today = now.date()
    week_ago = now - timedelta(days=7)

    def is_recent(item: Dict[str, Any], date_field: str) -> bool:
        dt = _parse_date(item.get(date_field, ""))
        return dt is not None and dt >= week_ago

    def is_today(item: Dict[str, Any], date_field: str) -> bool:
        dt = _parse_date(item.get(date_field, ""))
        return dt is not None and dt.date() == today

    whats_new = [b for b in bills if is_today(b, "latest_action_date") or is_today(b, "updated_at")]
    recent_bills = sorted(
        [b for b in bills if is_recent(b, "latest_action_date") or is_recent(b, "updated_at")],
        key=lambda x: x.get("latest_action_date", ""),
        reverse=True,
    )[:50]

    upcoming_hearings = sorted(
        [e for e in events if _parse_date(e.get("scheduled_date", "")) and _parse_date(e["scheduled_date"]) >= now],
        key=lambda x: x.get("scheduled_date", ""),
    )[:50]

    recent_votes = sorted(votes, key=lambda x: x.get("date", ""), reverse=True)[:50]

    signed_into_law = [
        b for b in bills
        if any(kw in (b.get("latest_action") or "").lower() for kw in ["signed", "became public law", "enacted"])
    ][:50]

    topic_dashboards: Dict[str, List[Dict[str, Any]]] = {}
    for dash in config.get("topic_dashboards", []):
        keywords = [k.lower() for k in dash.get("keywords", [])]
        matched = []
        for bill in bills:
            haystack = " ".join([
                bill.get("title", ""),
                bill.get("summary", ""),
                bill.get("latest_action", ""),
                " ".join(bill.get("ai_topics") or []),
            ]).lower()
            if any(kw in haystack for kw in keywords):
                matched.append(bill)
        topic_dashboards[dash["id"]] = matched[:30]

    by_state: Dict[str, List[Dict[str, Any]]] = {}
    for bill in recent_bills:
        key = bill.get("state") or "Federal"
        by_state.setdefault(key, []).append(bill)

    return {
        "whats_new_today": whats_new[:30],
        "recent_bills": recent_bills,
        "upcoming_hearings": upcoming_hearings,
        "recent_votes": recent_votes,
        "signed_into_law": signed_into_law,
        "by_state": by_state,
        "topics": topic_dashboards,
    }
