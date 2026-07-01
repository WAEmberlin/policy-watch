#!/usr/bin/env python3
"""
Fetch per-member Kansas roll-call vote breakdowns from the official REST API.

List endpoint /votes/?bill_no= returns tallies; detail /votes/{apn}/ adds members.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.enrich_kansas_api import to_api_bill_no  # noqa: E402
from processing.kansas_api_client import KansasApiClient  # noqa: E402
from processing.kansas_votes import merge_vote_record, normalize_vote_detail, normalize_vote_summary  # noqa: E402

ENRICHMENTS_FILE = ROOT / "data" / "kansas" / "enrichments.json"
OUTPUT_FILE = ROOT / "data" / "kansas" / "vote_records.json"
DEFAULT_MAX_DETAIL_FETCHES = 40
DEFAULT_MAX_LIST_FETCHES = 40


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def index_existing(records: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Map apn -> vote record for quick lookup."""
    index: Dict[str, Dict[str, Any]] = {}
    for key, votes in records.items():
        if key == "_meta" or not isinstance(votes, list):
            continue
        for vote in votes:
            if not isinstance(vote, dict):
                continue
            apn = vote.get("apn")
            if apn:
                index[apn] = vote
    return index


def needs_member_detail(vote: Dict[str, Any]) -> bool:
    apn = vote.get("apn")
    if not apn:
        return False
    members = vote.get("members")
    if not isinstance(members, dict):
        return True
    return not any(members.get(key) for key in ("yea", "nay", "present", "absent", "not_voting"))


def collect_pending(
    enrichments: Dict[str, Any],
    existing: Dict[str, List[Dict[str, Any]]],
    client: KansasApiClient,
    max_list_fetches: int = DEFAULT_MAX_LIST_FETCHES,
) -> List[Dict[str, Any]]:
    pending: List[Dict[str, Any]] = []
    seen_apn: set = set()
    by_apn = index_existing(existing)
    list_fetches = 0

    bill_items = [
        (key, record)
        for key, record in enrichments.items()
        if key != "_meta" and isinstance(record, dict) and record.get("votes")
    ]
    bill_items.sort(
        key=lambda item: max((v.get("date") or "") for v in (item[1].get("votes") or [])),
        reverse=True,
    )

    for key, record in bill_items:
        bill_no = to_api_bill_no(record.get("bill_number") or key)
        votes = list(record.get("votes") or [])
        if votes and not any(v.get("apn") for v in votes):
            if list_fetches >= max_list_fetches:
                continue
            try:
                votes = client.get_votes(bill_no) or votes
                list_fetches += 1
            except Exception:
                pass
        for vote in votes:
            apn = vote.get("apn")
            if not apn or apn in seen_apn:
                continue
            seen_apn.add(apn)
            merged = merge_vote_record(by_apn.get(apn), normalize_vote_summary({**vote, "bill_no": bill_no}))
            if needs_member_detail(merged):
                pending.append(merged)

    pending.sort(key=lambda v: v.get("date") or "", reverse=True)
    return pending


def main(
    max_detail_fetches: int = DEFAULT_MAX_DETAIL_FETCHES,
    max_list_fetches: int = DEFAULT_MAX_LIST_FETCHES,
) -> None:
    client = KansasApiClient()
    enrichments = load_json(ENRICHMENTS_FILE, {})
    if not isinstance(enrichments, dict):
        enrichments = {}

    records: Dict[str, List[Dict[str, Any]]] = load_json(OUTPUT_FILE, {})
    if not isinstance(records, dict):
        records = {}
    records = {k: v for k, v in records.items() if k != "_meta" and isinstance(v, list)}

    pending = collect_pending(enrichments, records, client, max_list_fetches=max_list_fetches)
    print(f"Kansas vote details: {len(pending)} roll call(s) need member breakdown")

    fetched = 0
    for vote in pending:
        if fetched >= max_detail_fetches:
            break
        apn = vote.get("apn")
        if not apn:
            continue
        try:
            detail = client.get_vote_detail(apn)
            if not detail:
                print(f"  No detail for {apn}")
                continue
            normalized = normalize_vote_detail(detail)
            bill_no = to_api_bill_no(normalized.get("bill_number") or vote.get("bill_number") or "")
            if not bill_no:
                continue
            bucket = records.setdefault(bill_no, [])
            replaced = False
            for i, existing in enumerate(bucket):
                if existing.get("apn") == apn:
                    bucket[i] = merge_vote_record(existing, normalized)
                    replaced = True
                    break
            if not replaced:
                bucket.append(normalized)
            fetched += 1
            yea = len((normalized.get("members") or {}).get("yea") or [])
            nay = len((normalized.get("members") or {}).get("nay") or [])
            print(f"  {bill_no} RCS {normalized.get('rcs_num')}: {yea} yea, {nay} nay")
        except Exception as exc:
            print(f"  Failed {apn}: {exc}")

    payload = {
        "_meta": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "bills_with_votes": len(records),
            "source": "kansas_api",
        },
        **{k: records[k] for k in sorted(records.keys())},
    }
    save_json(OUTPUT_FILE, payload)
    print(f"Wrote {len(records)} bills with vote records to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
