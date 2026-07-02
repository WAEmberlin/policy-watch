#!/usr/bin/env python3
"""
Import Colorado Legislative Tracker CSVs into veteran impact data.

Reads:
  - CO Legislative Tracker - Bills.csv
  - CO Legislative Tracker - Status Log.csv (latest status per bill)
  - CO Legislative Tracker - Dashboard.csv (metadata only)

Writes:
  - data/veterans/co_bills.json

Colorado CSV is the source of truth for CO veteran impact tiers when present.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.veteran_impact import (  # noqa: E402
    classify_veteran_impact,
    normalize_co_csv_bill_number,
)

DEFAULT_BILLS_CSV = Path.home() / "Downloads" / "CO Legislative Tracker - Bills.csv"
DEFAULT_STATUS_CSV = Path.home() / "Downloads" / "CO Legislative Tracker - Status Log.csv"
DEFAULT_DASHBOARD_CSV = Path.home() / "Downloads" / "CO Legislative Tracker - Dashboard.csv"

OUTPUT_FILE = ROOT / "data" / "veterans" / "co_bills.json"
NORMALIZED_BILLS_FILE = ROOT / "data" / "normalized" / "bills.json"
OPENSTATES_CO_FILE = ROOT / "data" / "openstates" / "co" / "bills.json"

CO_URL_RE = re.compile(r"/bills/([A-Z0-9]+-\d+)", re.IGNORECASE)


def _clean(value: str) -> str:
    return html.unescape((value or "").strip())


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1", "y"}


def _parse_impact(value: str) -> str:
    level = (value or "").strip().lower()
    return level if level in {"red", "yellow", "green"} else ""


def load_status_log(path: Path) -> Dict[str, Dict[str, str]]:
    """Return latest status entry per bill from status log CSV."""
    if not path.exists():
        return {}

    latest: Dict[str, Dict[str, str]] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            bill = _clean(row.get("Bill Number", "")).upper()
            if not bill:
                continue
            change_date = _clean(row.get("Change Date", ""))
            existing = latest.get(bill)
            if not existing or change_date >= existing.get("change_date", ""):
                latest[bill] = {
                    "old_status": _clean(row.get("Old Status", "")),
                    "new_status": _clean(row.get("New Status", "")),
                    "change_date": change_date,
                }
    return latest


def build_openstates_slug_index(normalized_bills: List[dict]) -> Dict[str, dict]:
    index: Dict[str, dict] = {}
    for bill in normalized_bills:
        if bill.get("state") != "CO":
            continue
        for url in bill.get("document_urls") or []:
            match = CO_URL_RE.search(url)
            if match:
                index[match.group(1).upper()] = bill
    return index


def load_normalized_co_bills() -> List[dict]:
    if not NORMALIZED_BILLS_FILE.exists():
        return []
    with open(NORMALIZED_BILLS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def import_co_tracker(
    bills_csv: Path,
    status_csv: Path,
    dashboard_csv: Path,
    output: Path,
) -> Dict[str, Any]:
    if not bills_csv.exists():
        raise FileNotFoundError(f"Bills CSV not found: {bills_csv}")

    status_by_bill = load_status_log(status_csv)
    normalized = load_normalized_co_bills()
    slug_index = build_openstates_slug_index(normalized)

    bills_out: Dict[str, dict] = {}
    stats = Counter()
    gaps: List[str] = []

    with open(bills_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        bill_csv = _clean(row.get("Bill Number", "")).upper()
        if not bill_csv:
            continue

        veteran_related = _parse_bool(row.get("Veteran Related", ""))
        impact_level = _parse_impact(row.get("Impact Level", ""))
        if not veteran_related and not impact_level:
            continue

        stats["tracked_rows"] += 1
        slug, bill_norm = normalize_co_csv_bill_number(bill_csv)
        matched = slug_index.get(slug)
        if matched:
            stats["matched_openstates"] += 1
        else:
            stats["unmatched_openstates"] += 1
            gaps.append(bill_csv)

        title = _clean(row.get("Title", ""))
        committee = _clean(row.get("Committee", ""))
        notes = _clean(row.get("Notes", ""))
        text = " ".join(filter(None, [title, committee, notes, _clean(row.get("Last Action", ""))]))

        if impact_level:
            classified = classify_veteran_impact(text, csv_level=impact_level)
            stats[f"impact_{impact_level}"] += 1
        elif veteran_related:
            classified = classify_veteran_impact(text)
            stats["impact_classified_fallback"] += 1
            if classified:
                impact_level = classified["level"]
                stats[f"impact_{impact_level}"] += 1
        else:
            classified = None

        status = _clean(row.get("Status", ""))
        status_log = status_by_bill.get(bill_csv) or status_by_bill.get(slug)
        if status_log and status_log.get("new_status"):
            status = status_log["new_status"]

        record = {
            "bill_number_csv": bill_csv,
            "bill_number_norm": matched.get("bill_number") if matched else bill_norm,
            "title": title,
            "veteran_related": veteran_related,
            "impact_level": impact_level,
            "impact_source": classified.get("source") if classified else ("csv" if impact_level else ""),
            "scoring_factors": classified.get("factors", []) if classified else [],
            "endorsement": _clean(row.get("Endorsement", "")),
            "chamber": _clean(row.get("Chamber", "")),
            "sponsor": _clean(row.get("Sponsor", "")),
            "status": status,
            "last_action": _clean(row.get("Last Action", "")),
            "committee": committee,
            "introduced": _clean(row.get("Introduced", "")),
            "last_updated": _clean(row.get("Last Updated", "")),
            "notes": notes,
            "openstates_id": matched.get("id", "") if matched else "",
            "openstates_url": matched.get("url", "") if matched else "",
            "matched_openstates": bool(matched),
        }
        if status_log:
            record["status_log"] = status_log

        bills_out[slug] = record

    meta = {
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            "bills_csv": str(bills_csv),
            "status_csv": str(status_csv) if status_csv.exists() else "",
            "dashboard_csv": str(dashboard_csv) if dashboard_csv.exists() else "",
        },
        "stats": dict(stats),
        "gaps": gaps,
        "total_csv_rows": len(rows),
        "total_tracked": stats["tracked_rows"],
        "matched_openstates": stats["matched_openstates"],
        "unmatched_openstates": stats["unmatched_openstates"],
    }

    payload = {"_meta": meta, "bills": bills_out}
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Colorado veteran tracker CSVs")
    parser.add_argument("--bills-csv", type=Path, default=DEFAULT_BILLS_CSV)
    parser.add_argument("--status-csv", type=Path, default=DEFAULT_STATUS_CSV)
    parser.add_argument("--dashboard-csv", type=Path, default=DEFAULT_DASHBOARD_CSV)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()

    payload = import_co_tracker(
        bills_csv=args.bills_csv,
        status_csv=args.status_csv,
        dashboard_csv=args.dashboard_csv,
        output=args.output,
    )
    meta = payload["_meta"]
    print(f"Wrote {args.output}")
    print(f"  CSV rows: {meta['total_csv_rows']}")
    print(f"  Tracked veteran/impact bills: {meta['total_tracked']}")
    print(f"  Matched Open States: {meta['matched_openstates']}")
    print(f"  Unmatched: {meta['unmatched_openstates']}")
    if meta.get("gaps"):
        print(f"  Gap bill numbers: {', '.join(meta['gaps'][:20])}")
        if len(meta["gaps"]) > 20:
            print(f"    ... and {len(meta['gaps']) - 20} more")


if __name__ == "__main__":
    main()
