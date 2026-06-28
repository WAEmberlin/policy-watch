#!/usr/bin/env python3
"""Fetch legislative data from Open States API for configured states."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

# Allow imports from src/
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_client import OpenStatesClient  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"
DATA_DIR = ROOT / "data" / "openstates"


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_enabled_states(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [s for s in config.get("states", []) if s.get("enabled") and "openstates" in (s.get("sources") or [])]


def merge_by_id(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]], id_field: str = "id") -> List[Dict[str, Any]]:
    index = {item.get(id_field): item for item in existing if item.get(id_field)}
    for item in new_items:
        key = item.get(id_field)
        if key:
            index[key] = item
    return list(index.values())


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {path} ({len(data) if isinstance(data, list) else 'object'})")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_updated_since(config: Dict[str, Any], args: argparse.Namespace) -> str:
    """Return YYYY-MM-DD filter for Open States updated_since."""
    os_cfg = config.get("openstates", {})
    if args.since:
        since = args.since.strip()
        print(f"Using --since {since}")
        return since
    if args.full_refresh:
        since = os_cfg.get("initial_backfill_since", "2026-03-01")
        print(f"Backfill mode: fetching records updated since {since}")
        return since
    days_back = args.days_back or os_cfg.get("default_days_back", 7)
    return (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")


def fetch_state(
    client: OpenStatesClient,
    state_cfg: Dict[str, Any],
    updated_since: str,
    full_refresh: bool,
) -> None:
    code = state_cfg["code"]
    state_dir = DATA_DIR / code

    print(f"\n=== Fetching Open States data for {code.upper()} ===")

    since = updated_since
    print(f"  updated_since={since}")
    # Light includes for list endpoint; votes/documents come from detail enrichment
    include = ["sponsorships", "actions", "versions"]
    # API accepts state codes (CO) more reliably than full OCD IDs for list queries
    jurisdiction_query = code.upper()
    existing_bills = load_json(state_dir / "bills.json", [])
    existing_events = load_json(state_dir / "events.json", [])
    existing_committees = load_json(state_dir / "committees.json", [])
    existing_legislators = load_json(state_dir / "legislators.json", [])

    try:
        bills = client.fetch_bills(jurisdiction=jurisdiction_query, updated_since=since, include=include)
    except Exception as exc:
        print(f"WARNING: bills fetch failed for {code.upper()}, keeping {len(existing_bills)} cached: {exc}")
        bills = []

    try:
        events = client.fetch_events(jurisdiction=jurisdiction_query, updated_since=since)
    except Exception as exc:
        print(f"WARNING: events fetch failed for {code.upper()}, keeping {len(existing_events)} cached: {exc}")
        events = []

    if full_refresh or not existing_committees:
        try:
            committees = client.fetch_committees(jurisdiction=jurisdiction_query)
        except Exception as exc:
            print(f"WARNING: committees fetch failed for {code.upper()}, keeping cached: {exc}")
            committees = existing_committees
    else:
        committees = existing_committees
        print(f"Using cached committees for {code.upper()} ({len(committees)} records)")

    if full_refresh or not existing_legislators:
        try:
            legislators = client.fetch_legislators(jurisdiction=jurisdiction_query, updated_since=since)
        except Exception as exc:
            print(f"WARNING: legislators fetch failed for {code.upper()}, keeping cached: {exc}")
            legislators = existing_legislators
    else:
        legislators = existing_legislators
        print(f"Using cached legislators for {code.upper()} ({len(legislators)} records)")

    # Merge with existing for incremental updates (never drop cached rows on empty fetch)
    bills = merge_by_id(existing_bills, bills)
    events = merge_by_id(existing_events, events)
    committees = merge_by_id(existing_committees, committees)
    legislators = merge_by_id(existing_legislators, legislators)

    save_json(state_dir / "bills.json", bills)
    save_json(state_dir / "events.json", events)
    save_json(state_dir / "committees.json", committees)
    save_json(state_dir / "legislators.json", legislators)

    # Votes extracted from bill vote events
    votes: List[Dict[str, Any]] = []
    for bill in bills:
        for action in bill.get("actions") or []:
            if action.get("classification") and "passage" in str(action.get("classification")).lower():
                votes.append({
                    "bill_id": bill.get("id"),
                    "bill_number": bill.get("identifier"),
                    "action": action.get("description"),
                    "date": action.get("date"),
                    "state": code.upper(),
                })
    votes = merge_by_id(load_json(state_dir / "votes.json", []), votes, id_field="bill_id")
    save_json(state_dir / "votes.json", votes)

    meta = {
        "state": code.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "updated_since": since,
        "counts": {
            "bills": len(bills),
            "events": len(events),
            "committees": len(committees),
            "legislators": len(legislators),
            "votes": len(votes),
        },
    }
    save_json(state_dir / "meta.json", meta)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Open States legislative data")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Backfill from initial_backfill_since in config (default 2026-03-01), not all history",
    )
    parser.add_argument("--days-back", type=int, default=None, help="Override days-back from config")
    parser.add_argument("--since", type=str, default=None, help="Fetch updates since YYYY-MM-DD")
    args = parser.parse_args()

    api_key = os.environ.get("OPENSTATES_API_KEY", "")
    if not api_key:
        print("WARNING: OPENSTATES_API_KEY not set. API may rate-limit or reject requests.")

    config = load_config()
    os_cfg = config.get("openstates", {})

    updated_since = resolve_updated_since(config, args)

    client = OpenStatesClient(
        api_key=api_key,
        base_url=os_cfg.get("base_url", "https://v3.openstates.org"),
        request_delay=float(os_cfg.get("request_delay_seconds", 0.5)),
        max_retries=int(os_cfg.get("max_retries", 3)),
        per_page=int(os_cfg.get("per_page", 20)),
    )

    states = get_enabled_states(config)
    if not states:
        print("No Open States states configured.")
        return

    for state_cfg in states:
        try:
            fetch_state(client, state_cfg, updated_since, args.full_refresh)
        except Exception as exc:
            print(f"ERROR fetching {state_cfg['code']}: {exc}")

    print("\nOpen States fetch complete.")


if __name__ == "__main__":
    main()
