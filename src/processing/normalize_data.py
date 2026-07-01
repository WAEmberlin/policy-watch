#!/usr/bin/env python3
"""Normalize data from all sources into unified schema."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from adapters.congress_source import CongressSource  # noqa: E402
from adapters.kansas_rss_source import KansasRSSSource  # noqa: E402
from adapters.openstates_source import OpenStatesSource  # noqa: E402
from processing.ai_enrichment import enrich_bills  # noqa: E402
from processing.unified_search import build_search_index, build_dashboards  # noqa: E402
from processing.enrichment_utils import apply_enrichments_to_bills  # noqa: E402
from processing.import_openstates_bulk import fetch_legislators_csv  # noqa: E402
from processing.legislator_stats import build_legislator_stats  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"
DATA_DIR = ROOT / "data"
NORMALIZED_DIR = DATA_DIR / "normalized"
OPENSTATES_DIR = DATA_DIR / "openstates"
CONGRESS_DIR = DATA_DIR / "congress"
KANSAS_DIR = DATA_DIR / "kansas"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def dedupe_bills(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate bills; prefer congress > openstates > kansas_rss for same bill_number+state."""
    priority = {"congress": 3, "openstates": 2, "kansas_rss": 1}
    index: Dict[str, Dict[str, Any]] = {}

    for bill in bills:
        key = f"{bill.get('level')}:{bill.get('state') or 'US'}:{bill.get('bill_number', '').upper()}:{bill.get('id', '')}"
        if not bill.get("bill_number") and bill.get("id"):
            key = bill["id"]

        existing = index.get(key)
        if not existing or priority.get(bill.get("source", ""), 0) >= priority.get(existing.get("source", ""), 0):
            index[key] = bill

    return list(index.values())


def enrich_legislators_with_csv(raw_legislators: List[Dict[str, Any]], state_code: str) -> List[Dict[str, Any]]:
    """Merge Open States bulk CSV demographics and profile links into cached API records."""
    csv_rows = fetch_legislators_csv(state_code)
    if not csv_rows:
        return raw_legislators

    csv_by_id = {row.get("id"): row for row in csv_rows if row.get("id")}
    merged: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for leg in raw_legislators:
        leg_id = leg.get("id", "")
        csv = csv_by_id.get(leg_id, {})
        record = {**leg}
        for field in ("links", "sources", "gender", "birth_date", "image", "name", "party"):
            if csv.get(field) and not record.get(field):
                record[field] = csv[field]
        if csv.get("current_role") and not record.get("current_role"):
            record["current_role"] = csv["current_role"]
        merged.append(record)
        if leg_id:
            seen.add(leg_id)

    for csv in csv_rows:
        leg_id = csv.get("id", "")
        if leg_id and leg_id not in seen:
            merged.append(csv)

    return merged


def normalize_all(skip_ai: bool = False) -> Dict[str, Any]:
    config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))

    all_bills: List[Dict[str, Any]] = []
    all_events: List[Dict[str, Any]] = []
    all_legislators: List[Dict[str, Any]] = []
    all_votes: List[Dict[str, Any]] = []

    # Congress (existing pipeline — read-only)
    congress = CongressSource()
    congress_bills = congress.normalize_bills(congress.fetch_bills())
    congress_events = congress.normalize_events(congress.fetch_events())
    all_bills.extend(b.to_dict() for b in congress_bills)
    all_events.extend(e.to_dict() for e in congress_events)

    # Also persist raw congress copies under data/congress/
    save_json(CONGRESS_DIR / "bills.json", [b.to_dict() for b in congress_bills])
    save_json(CONGRESS_DIR / "events.json", [e.to_dict() for e in congress_events])

    # Kansas RSS (existing pipeline — read-only)
    kansas = KansasRSSSource()
    ks_bills = kansas.normalize_bills(kansas.fetch_bills())
    ks_events = kansas.normalize_events(kansas.fetch_events())
    all_bills.extend(b.to_dict() for b in ks_bills)
    all_events.extend(e.to_dict() for e in ks_events)

    save_json(KANSAS_DIR / "bills.json", [b.to_dict() for b in ks_bills])
    save_json(KANSAS_DIR / "events.json", [e.to_dict() for e in ks_events])

    # Open States (new pipeline)
    for state_cfg in config.get("states", []):
        if not state_cfg.get("enabled") or "openstates" not in (state_cfg.get("sources") or []):
            continue
        code = state_cfg["code"]
        state_dir = OPENSTATES_DIR / code
        if not state_dir.exists():
            continue

        os_source = OpenStatesSource(code, state_cfg["openstates_jurisdiction"])
        legislators_raw = enrich_legislators_with_csv(
            load_json(state_dir / "legislators.json", []),
            code,
        )
        os_source.set_data(
            bills=load_json(state_dir / "bills.json", []),
            events=load_json(state_dir / "events.json", []),
            committees=load_json(state_dir / "committees.json", []),
            legislators=legislators_raw,
        )

        os_bills = os_source.normalize_bills(os_source.fetch_bills())
        os_events = os_source.normalize_events(os_source.fetch_events())
        os_legislators = os_source.normalize_legislators(os_source.fetch_legislators())

        all_bills.extend(b.to_dict() for b in os_bills)
        all_events.extend(e.to_dict() for e in os_events)
        all_legislators.extend(l.to_dict() for l in os_legislators)
        all_votes.extend(load_json(state_dir / "votes.json", []))

    # Apply Kansas official API enrichments (RSS remains primary; this adds depth)
    ks_enrichments = load_json(KANSAS_DIR / "enrichments.json", {})
    if isinstance(ks_enrichments, dict) and ks_enrichments:
        ks_enrichments = {k: v for k, v in ks_enrichments.items() if k != "_meta"}
        all_bills = apply_enrichments_to_bills(all_bills, ks_enrichments, state="KS")
        print(f"Applied Kansas API enrichments for {len(ks_enrichments)} bills")

    all_bills = dedupe_bills(all_bills)

    if not skip_ai:
        all_bills = enrich_bills(all_bills)

    save_json(NORMALIZED_DIR / "bills.json", all_bills)
    save_json(NORMALIZED_DIR / "events.json", all_events)
    save_json(NORMALIZED_DIR / "legislators.json", all_legislators)
    save_json(NORMALIZED_DIR / "votes.json", all_votes)

    search_index = build_search_index(all_bills, all_events, all_legislators)
    dashboards = build_dashboards(all_bills, all_events, all_votes, config)
    legislator_stats = build_legislator_stats(all_legislators)

    save_json(NORMALIZED_DIR / "search_index.json", search_index)
    save_json(NORMALIZED_DIR / "dashboards.json", dashboards)
    save_json(NORMALIZED_DIR / "legislator_stats.json", legislator_stats)

    meta = {
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "bills": len(all_bills),
            "events": len(all_events),
            "legislators": len(all_legislators),
            "votes": len(all_votes),
        },
    }
    save_json(NORMALIZED_DIR / "meta.json", meta)

    print(f"Normalized {len(all_bills)} bills, {len(all_events)} events, {len(all_legislators)} legislators")
    return meta


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ai", action="store_true")
    args = parser.parse_args()
    normalize_all(skip_ai=args.skip_ai)
