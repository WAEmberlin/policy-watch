#!/usr/bin/env python3
"""
Deepen Open States bill records for CO, AZ, UT (and KS overlap).

Open States is already the primary source for these states. This script
re-fetches individual bill detail for records missing sponsors or votes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_bills import load_state_bills, save_state_bills  # noqa: E402
from processing.openstates_client import OpenStatesClient  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"
OPENSTATES_DIR = ROOT / "data" / "openstates"
ENRICHMENTS_DIR = ROOT / "data" / "openstates" / "enrichments"
DEFAULT_MAX_PER_STATE = 40


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def bill_needs_detail(bill: Dict[str, Any]) -> bool:
    if not bill.get("sponsorships"):
        return True
    if not bill.get("actions"):
        return True
    if not bill.get("votes") and not bill.get("versions"):
        return True
    return False


def fetch_bill_detail(client: OpenStatesClient, bill: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch full bill detail by Open States ID or jurisdiction path."""
    bill_id = bill.get("id", "")
    if bill_id.startswith("ocd-bill/"):
        path = f"/bills/ocd-bill/{bill_id.split('/', 1)[-1]}"
    else:
        jurisdiction = bill.get("jurisdiction", {}).get("id") or bill.get("jurisdiction_id", "")
        session = bill.get("session", bill.get("legislative_session", ""))
        identifier = bill.get("identifier", "").replace(" ", "")
        if jurisdiction and session and identifier:
            path = f"/bills/{jurisdiction}/{session}/{identifier}"
        else:
            return bill

    params = {"include": ["sponsorships", "actions", "versions", "votes", "documents"]}
    try:
        data = client._request("GET", path, params)
        return data if isinstance(data, dict) and data.get("id") else bill
    except Exception as exc:
        print(f"  Detail fetch failed for {bill.get('identifier')}: {exc}")
        return bill


def enrich_state(client: OpenStatesClient, state_code: str, max_bills: int, days_back: int) -> int:
    bills = load_state_bills(OPENSTATES_DIR / state_code)
    if not bills:
        print(f"No Open States bills for {state_code.upper()}, skipping detail enrichment")
        return 0

    enrichments = load_json(ENRICHMENTS_DIR / f"{state_code}.json", {})
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    candidates = []
    for bill in bills:
        updated = bill.get("updated_at", "")
        try:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            dt = cutoff
        if dt >= cutoff and bill_needs_detail(bill):
            candidates.append(bill)

    candidates.sort(key=lambda b: b.get("updated_at", ""), reverse=True)
    candidates = candidates[:max_bills]

    print(f"{state_code.upper()}: enriching {len(candidates)} bills with detail fetch")
    enriched = 0

    for bill in candidates:
        detail = fetch_bill_detail(client, bill)
        if detail.get("id"):
            enrichments[detail["id"]] = {
                "identifier": detail.get("identifier"),
                "sponsorships": detail.get("sponsorships"),
                "actions": detail.get("actions"),
                "votes": detail.get("votes"),
                "versions": detail.get("versions"),
                "documents": detail.get("documents"),
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            }
            # Update bills list in place
            for i, b in enumerate(bills):
                if b.get("id") == detail.get("id"):
                    bills[i] = {**b, **detail}
                    break
            enriched += 1

    save_state_bills(OPENSTATES_DIR / state_code, bills)
    enrichments["_meta"] = {
        "state": state_code.upper(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "enriched_this_run": enriched,
    }
    save_json(ENRICHMENTS_DIR / f"{state_code}.json", enrichments)
    return enriched


def enrich_all_openstates(max_per_state: int = DEFAULT_MAX_PER_STATE, days_back: int = 7) -> int:
    """Enrich all Open States states configured for detail enrichment."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    os_cfg = config.get("openstates", {})
    client = OpenStatesClient(
        api_key=os.environ.get("OPENSTATES_API_KEY", ""),
        base_url=os_cfg.get("base_url", "https://v3.openstates.org"),
        request_delay=float(os_cfg.get("request_delay_seconds", 0.5)),
    )

    detail_states = set(config.get("enrichment", {}).get("openstates_detail", []))
    total = 0
    for state_cfg in config.get("states", []):
        if not state_cfg.get("enabled"):
            continue
        code = state_cfg["code"]
        if code not in detail_states and state_cfg.get("enrichment") != "openstates_detail":
            continue
        if state_cfg.get("enrichment") == "kansas_api":
            continue
        total += enrich_state(client, code, max_per_state, days_back)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Open States bills with detail fetches")
    parser.add_argument("--max-per-state", type=int, default=DEFAULT_MAX_PER_STATE)
    parser.add_argument("--days-back", type=int, default=7)
    args = parser.parse_args()

    total = enrich_all_openstates(args.max_per_state, args.days_back)
    print(f"Open States detail enrichment complete: {total} bills updated")


if __name__ == "__main__":
    main()
