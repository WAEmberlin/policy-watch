#!/usr/bin/env python3
"""
Enrich Kansas bills using the official Kansas Legislature REST API.

RSS remains the primary ingest; this adds sponsors, status, history, votes,
documents, and hearing links from /api/v1/bill_status/ and related endpoints.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.kansas_api_client import KansasApiClient  # noqa: E402

HISTORY_FILE = ROOT / "src" / "output" / "history.json"
ENRICHMENTS_FILE = ROOT / "data" / "kansas" / "enrichments.json"
DEFAULT_MAX_PER_RUN = 75
DEFAULT_REENRICH_HOURS = 24


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def to_api_bill_no(bill_number: str) -> str:
    return bill_number.replace(" ", "").upper().strip()


def extract_bill_number_from_item(item: Dict[str, Any]) -> Optional[str]:
    if item.get("bill_number"):
        return to_api_bill_no(item["bill_number"])
    title = item.get("title", "")
    match = re.search(r"\b(HB|SB|HR|SR|HCR|SCR)\s*(\d+)\b", title, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()}{match.group(2)}"
    link = item.get("link") or item.get("bill_url") or ""
    match = re.search(r"/measures/([A-Z]+\d+)/?", link, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def collect_bill_numbers(priority_days: int = 30) -> List[str]:
    """Collect Kansas bill numbers from history, prioritizing recent items."""
    history = load_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=priority_days)
    recent: Set[str] = set()
    all_bills: Set[str] = set()

    for item in history:
        if item.get("type") != "state_legislation" or item.get("state") != "KS":
            continue
        if item.get("feed") == "conference_committees":
            continue

        bill_no = extract_bill_number_from_item(item)
        if not bill_no:
            continue

        all_bills.add(bill_no)
        published = item.get("published", "")
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                recent.add(bill_no)
        except ValueError:
            pass

    # Recent bills first, then remainder
    ordered = sorted(recent) + sorted(all_bills - recent)
    return ordered


def parse_bill_status(raw: Dict[str, Any], votes: List[Dict[str, Any]], hearings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert Kansas API bill_status payload to enrichment record."""
    history = raw.get("HISTORY") or raw.get("history") or []
    latest = history[0] if history else {}

    sponsors = []
    for name in raw.get("SPONSOR_NAMES") or raw.get("ORIGINAL_SPONSOR") or []:
        sponsors.append({"name": name, "role": "primary"})

    documents = []
    base = "https://kslegislature.gov"
    for version in raw.get("versions") or []:
        doc = version.get("document")
        if doc:
            documents.append(doc if doc.startswith("http") else f"{base}{doc}")
        assoc = version.get("associated_documents") or {}
        for url in assoc.values():
            if url:
                documents.append(url if str(url).startswith("http") else f"{base}{url}")

    committees = []
    for entry in history:
        for c in entry.get("committee_names") or []:
            if c not in committees:
                committees.append(c)

    vote_records = []
    for vote in votes[:10]:
        journal = vote.get("journal_element") or {}
        vote_records.append({
            "chamber": vote.get("chamber", ""),
            "result": journal.get("action_label") or vote.get("action_label", ""),
            "date": journal.get("occurred") or vote.get("occurred", ""),
            "tally": vote.get("vote_tally") or vote.get("tally", ""),
        })

    hearing_events = []
    for h in hearings[:5]:
        hearing_events.append({
            "title": h.get("committee") or h.get("title", "Committee hearing"),
            "scheduled_date": h.get("start") or h.get("date", ""),
            "location": h.get("room", ""),
            "url": h.get("stream_url") or h.get("url", ""),
        })

    return {
        "bill_number": raw.get("BILLNO") or raw.get("bill_no", ""),
        "short_title": raw.get("SHORTTITLE", ""),
        "long_title": raw.get("LONGTITLE", ""),
        "summary": raw.get("SHORTTITLE") or raw.get("LONGTITLE", ""),
        "status": raw.get("STATUS", ""),
        "measure_state": raw.get("measure_state", ""),
        "sponsors": sponsors,
        "history": history,
        "latest_action": latest.get("status", ""),
        "latest_action_date": latest.get("occurred_datetime") or latest.get("session_date", ""),
        "committees": [{"name": c} for c in committees],
        "votes": vote_records,
        "hearings": hearing_events,
        "document_urls": documents,
        "source": "kansas_api",
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def needs_refresh(existing: Dict[str, Any], max_age_hours: int) -> bool:
    if not existing:
        return True
    enriched_at = existing.get("enriched_at", "")
    if not enriched_at:
        return True
    try:
        dt = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt > timedelta(hours=max_age_hours)
    except ValueError:
        return True


def enrich_kansas_bills(
    max_per_run: int = DEFAULT_MAX_PER_RUN,
    reenrich_hours: int = DEFAULT_REENRICH_HOURS,
    force: bool = False,
) -> Dict[str, Any]:
    client = KansasApiClient()
    existing = load_json(ENRICHMENTS_FILE, {})
    if not isinstance(existing, dict):
        existing = {}

    candidates = collect_bill_numbers()
    to_fetch = []
    for bill_no in candidates:
        if force or needs_refresh(existing.get(bill_no, {}), reenrich_hours):
            to_fetch.append(bill_no)
        if len(to_fetch) >= max_per_run:
            break

    print(f"Kansas API enrichment: {len(to_fetch)} bills to fetch (of {len(candidates)} total)")

    enriched_count = 0
    errors = 0

    for bill_no in to_fetch:
        try:
            status = client.get_bill_status(bill_no)
            if not status:
                print(f"  No data for {bill_no}")
                continue

            votes = client.get_votes(bill_no)
            hearings = client.get_hearings(bill_no, upcoming=True)

            record = parse_bill_status(status, votes, hearings)
            existing[bill_no] = record
            enriched_count += 1
            print(f"  Enriched {bill_no}: {record.get('status', 'unknown status')}")

        except Exception as exc:
            errors += 1
            print(f"  ERROR enriching {bill_no}: {exc}")

    meta = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_bills": len(existing),
        "enriched_this_run": enriched_count,
        "errors": errors,
    }
    existing["_meta"] = meta
    save_json(ENRICHMENTS_FILE, existing)

    # Also patch history.json with key enrichment fields (additive only)
    patch_history_with_enrichments(existing)

    print(f"Kansas enrichment complete: {enriched_count} updated, {len(existing)-1} total cached")
    return meta


def patch_history_with_enrichments(enrichments: Dict[str, Any]) -> None:
    """Add enrichment fields to matching history items without removing RSS data."""
    history = load_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        return

    patched = 0
    for item in history:
        if item.get("type") != "state_legislation" or item.get("state") != "KS":
            continue
        bill_no = extract_bill_number_from_item(item)
        if not bill_no:
            continue
        enrichment = enrichments.get(bill_no)
        if not enrichment or bill_no == "_meta":
            continue

        if enrichment.get("short_title") and not item.get("short_title"):
            item["short_title"] = enrichment["short_title"]
            item["short_title_source"] = "kansas_api"

        if enrichment.get("status"):
            item["ks_api_status"] = enrichment["status"]
        if enrichment.get("latest_action"):
            item["ks_api_latest_action"] = enrichment["latest_action"]
        if enrichment.get("sponsors"):
            item["sponsors"] = enrichment["sponsors"]
        if enrichment.get("votes"):
            item["votes"] = enrichment["votes"]
        item["ks_api_enriched_at"] = enrichment.get("enriched_at", "")
        patched += 1

    if patched:
        save_json(HISTORY_FILE, history)
        print(f"Patched {patched} history items with Kansas API enrichment fields")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Kansas bills via official REST API")
    parser.add_argument("--max", type=int, default=DEFAULT_MAX_PER_RUN, help="Max bills per run")
    parser.add_argument("--force", action="store_true", help="Re-fetch all bills regardless of cache age")
    parser.add_argument("--reenrich-hours", type=int, default=DEFAULT_REENRICH_HOURS)
    args = parser.parse_args()

    enrich_kansas_bills(
        max_per_run=args.max,
        reenrich_hours=args.reenrich_hours,
        force=args.force,
    )


if __name__ == "__main__":
    main()
