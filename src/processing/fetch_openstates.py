#!/usr/bin/env python3
"""Fetch legislative data from Open States API for configured states."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def load_state_meta(code: str) -> Dict[str, Any]:
    return load_json(DATA_DIR / code / "meta.json", {})


def parse_meta_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def state_bill_count(code: str) -> int:
    meta = load_state_meta(code)
    counts = meta.get("counts") or {}
    if isinstance(counts.get("bills"), int):
        return counts["bills"]
    bills = load_json(DATA_DIR / code / "bills.json", [])
    return len(bills) if isinstance(bills, list) else 0


def state_priority(code: str, os_cfg: Dict[str, Any]) -> Tuple[int, int, str]:
    """
    Lower sort key = fetch first.
    Priority: never synced → incomplete backfill → fewest bills → alphabetical.
    """
    meta = load_state_meta(code)
    bills = state_bill_count(code)
    backfill_complete = bool(meta.get("backfill_complete"))
    last_fetch = parse_meta_datetime(meta.get("last_successful_fetch_at") or meta.get("fetched_at", ""))

    if bills == 0 and not last_fetch:
        return (0, 0, code)
    if not backfill_complete:
        return (1, bills, code)
    return (2, bills, code)


def sort_states_for_fetch(states: List[Dict[str, Any]], os_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not os_cfg.get("prioritize_incomplete", True):
        return states
    return sorted(states, key=lambda s: state_priority(s["code"], os_cfg))


def resolve_global_since(config: Dict[str, Any], args: argparse.Namespace) -> str:
    """Default since date from CLI flags (fallback for new states)."""
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


def resolve_state_since(
    code: str,
    global_since: str,
    args: argparse.Namespace,
    os_cfg: Dict[str, Any],
) -> str:
    """
    Per-state updated_since so we don't re-pull the same window every run.
    - New / empty state: initial_backfill_since (or global since)
    - Incremental: last successful fetch minus overlap
    - Full refresh: initial_backfill_since only if backfill not complete
    """
    meta = load_state_meta(code)
    backfill_since = os_cfg.get("initial_backfill_since", "2026-03-01")
    overlap_days = int(os_cfg.get("incremental_overlap_days", 1))
    bills = state_bill_count(code)
    last_fetch = parse_meta_datetime(meta.get("last_successful_fetch_at") or meta.get("fetched_at", ""))

    if args.since:
        return args.since.strip()

    if args.full_refresh:
        if meta.get("backfill_complete") and not args.force:
            # Already backfilled — incremental window only (saves quota)
            if last_fetch:
                since_dt = last_fetch - timedelta(days=overlap_days)
                return since_dt.strftime("%Y-%m-%d")
            return global_since
        return backfill_since

    # Incremental daily sync
    if last_fetch and bills > 0:
        since_dt = last_fetch - timedelta(days=overlap_days)
        return since_dt.strftime("%Y-%m-%d")

    if bills == 0:
        return backfill_since

    return global_since


def should_skip_state(code: str, args: argparse.Namespace, os_cfg: Dict[str, Any]) -> Optional[str]:
    """Return skip reason, or None to fetch."""
    if args.force:
        return None
    if args.states and code not in args.states:
        return f"not in --states filter"

    skip_hours = int(os_cfg.get("skip_if_fetched_within_hours", 20))
    meta = load_state_meta(code)
    last_fetch = parse_meta_datetime(meta.get("last_successful_fetch_at") or meta.get("fetched_at", ""))
    bills = state_bill_count(code)

    if args.full_refresh and not meta.get("backfill_complete"):
        return None  # always backfill incomplete states

    if last_fetch and bills > 0 and meta.get("backfill_complete"):
        age = datetime.now(timezone.utc) - last_fetch
        if age < timedelta(hours=skip_hours) and not args.states:
            return f"synced {int(age.total_seconds() // 3600)}h ago ({bills} bills cached)"

    return None


def reference_data_stale(code: str, os_cfg: Dict[str, Any], full_refresh: bool) -> bool:
    if full_refresh:
        return True
    committees = load_json(DATA_DIR / code / "committees.json", [])
    if not committees:
        return True
    meta = load_state_meta(code)
    last_fetch = parse_meta_datetime(meta.get("last_successful_fetch_at") or meta.get("fetched_at", ""))
    if not last_fetch:
        return True
    ttl_hours = int(os_cfg.get("reference_data_ttl_hours", 168))
    return datetime.now(timezone.utc) - last_fetch > timedelta(hours=ttl_hours)


def fetch_state(
    client: OpenStatesClient,
    state_cfg: Dict[str, Any],
    updated_since: str,
    full_refresh: bool,
    os_cfg: Dict[str, Any],
) -> bool:
    """Fetch one state. Returns True if completed without quota exhaustion."""
    code = state_cfg["code"]
    state_dir = DATA_DIR / code

    print(f"\n=== Fetching Open States data for {code.upper()} ===")

    since = updated_since
    print(f"  updated_since={since}")
    include = ["sponsorships", "actions", "versions"]
    jurisdiction_query = code.upper()
    existing_bills = load_json(state_dir / "bills.json", [])
    existing_events = load_json(state_dir / "events.json", [])
    existing_committees = load_json(state_dir / "committees.json", [])
    existing_legislators = load_json(state_dir / "legislators.json", [])
    had_bills = len(existing_bills)
    fetch_ok = True

    try:
        bills = client.fetch_bills(jurisdiction=jurisdiction_query, updated_since=since, include=include)
    except Exception as exc:
        print(f"WARNING: bills fetch failed for {code.upper()}, keeping {len(existing_bills)} cached: {exc}")
        bills = []
        fetch_ok = False
        if client.quota_exhausted:
            return False

    try:
        events = client.fetch_events(jurisdiction=jurisdiction_query, updated_since=since)
    except Exception as exc:
        print(f"WARNING: events fetch failed for {code.upper()}, keeping {len(existing_events)} cached: {exc}")
        events = []
        if client.quota_exhausted:
            fetch_ok = False
            return False

    if reference_data_stale(code, os_cfg, full_refresh):
        try:
            committees = client.fetch_committees(jurisdiction=jurisdiction_query)
        except Exception as exc:
            print(f"WARNING: committees fetch failed for {code.upper()}, keeping cached: {exc}")
            committees = existing_committees
            if client.quota_exhausted:
                return False
    else:
        committees = existing_committees
        print(f"Using cached committees for {code.upper()} ({len(committees)} records)")

    if reference_data_stale(code, os_cfg, full_refresh):
        try:
            legislators = client.fetch_legislators(jurisdiction=jurisdiction_query, updated_since=since)
        except Exception as exc:
            print(f"WARNING: legislators fetch failed for {code.upper()}, keeping cached: {exc}")
            legislators = existing_legislators
            if client.quota_exhausted:
                return False
    else:
        legislators = existing_legislators
        print(f"Using cached legislators for {code.upper()} ({len(legislators)} records)")

    bills = merge_by_id(existing_bills, bills)
    events = merge_by_id(existing_events, events)
    committees = merge_by_id(existing_committees, committees)
    legislators = merge_by_id(existing_legislators, legislators)

    save_json(state_dir / "bills.json", bills)
    save_json(state_dir / "events.json", events)
    save_json(state_dir / "committees.json", committees)
    save_json(state_dir / "legislators.json", legislators)

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

    backfill_since = os_cfg.get("initial_backfill_since", "2026-03-01")
    backfill_complete = bool(
        load_state_meta(code).get("backfill_complete")
        or (len(bills) > 0 and since <= backfill_since and fetch_ok)
    )

    meta = {
        "state": code.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "last_successful_fetch_at": datetime.now(timezone.utc).isoformat() if fetch_ok else load_state_meta(code).get("last_successful_fetch_at"),
        "updated_since": since,
        "backfill_complete": backfill_complete,
        "counts": {
            "bills": len(bills),
            "events": len(events),
            "committees": len(committees),
            "legislators": len(legislators),
            "votes": len(votes),
        },
    }
    if fetch_ok:
        print(f"  Added/updated bills this run: {max(0, len(bills) - had_bills)} (total {len(bills)})")
    save_json(state_dir / "meta.json", meta)
    return not client.quota_exhausted


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Open States legislative data")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Backfill states missing data from initial_backfill_since (2026-03-01)",
    )
    parser.add_argument("--days-back", type=int, default=None, help="Override days-back from config")
    parser.add_argument("--since", type=str, default=None, help="Fetch updates since YYYY-MM-DD")
    parser.add_argument(
        "--states",
        type=str,
        default=None,
        help="Comma-separated state codes to sync only (e.g. me,ut)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch even if recently synced; re-backfill completed states on full-refresh",
    )
    args = parser.parse_args()
    if args.states:
        args.states = [s.strip().lower() for s in args.states.split(",") if s.strip()]

    api_key = os.environ.get("OPENSTATES_API_KEY", "")
    if not api_key:
        print("WARNING: OPENSTATES_API_KEY not set. API may rate-limit or reject requests.")

    config = load_config()
    os_cfg = config.get("openstates", {})
    global_since = resolve_global_since(config, args)
    request_budget = int(os_cfg.get("daily_request_budget", 450))

    client = OpenStatesClient(
        api_key=api_key,
        base_url=os_cfg.get("base_url", "https://v3.openstates.org"),
        request_delay=float(os_cfg.get("request_delay_seconds", 6.0)),
        max_retries=int(os_cfg.get("max_retries", 6)),
        per_page=int(os_cfg.get("per_page", 20)),
        request_budget=request_budget,
    )
    print(f"Request budget: {request_budget} API calls this run")

    states = sort_states_for_fetch(get_enabled_states(config), os_cfg)
    if not states:
        print("No Open States states configured.")
        return

    print("Fetch order (neediest states first):", ", ".join(s["code"].upper() for s in states))

    for state_cfg in states:
        code = state_cfg["code"]
        skip_reason = should_skip_state(code, args, os_cfg)
        if skip_reason:
            print(f"\n=== Skipping {code.upper()} === ({skip_reason})")
            continue

        if client.quota_exhausted:
            print(f"\nStopping before {code.upper()}: API request budget exhausted")
            break

        state_since = resolve_state_since(code, global_since, args, os_cfg)
        try:
            ok = fetch_state(client, state_cfg, state_since, args.full_refresh, os_cfg)
            if not ok:
                print(f"\nStopping after {code.upper()}: quota exhausted ({client.request_count}/{request_budget} requests)")
                break
        except Exception as exc:
            print(f"ERROR fetching {code}: {exc}")
            if client.quota_exhausted:
                break

    print(f"\nOpen States fetch complete. API requests used: {client.request_count}/{request_budget}")
    if client.quota_exhausted:
        print("Tip: run again tomorrow, or use --states ut,me to sync remaining states only.")


if __name__ == "__main__":
    main()
