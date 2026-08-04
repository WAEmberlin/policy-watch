#!/usr/bin/env python3
"""Import Open States bulk JSON exports into data/openstates/{state}/."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_bills import load_state_bills, save_state_bills  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"
DEFAULT_BULK_DIRS = [
    ROOT / "data" / "historic",
    ROOT / "data" / "nebraska",
    ROOT / "data" / "maryland",
    ROOT / "data" / "pennsylvania",
    ROOT / "data" / "massachusetts",
    ROOT / "data" / "west_virginia",
    ROOT / "data" / "tennessee",
    ROOT / "data" / "north_carolina",
    ROOT / "data" / "missouri",
    ROOT / "data" / "iowa",
]
OUTPUT_DIR = ROOT / "data" / "openstates"
SKIP_STATE_CODES = {"US"}

CHAMBER_NAMES = {
    "lower": "House",
    "upper": "Senate",
    "house": "House",
    "senate": "Senate",
}


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, list) else "object"
    print(f"Saved {path} ({count})")


def merge_by_id(existing: List[Dict[str, Any]], new_items: List[Dict[str, Any]], id_field: str = "id") -> List[Dict[str, Any]]:
    index = {item.get(id_field): item for item in existing if item.get(id_field)}
    for item in new_items:
        key = item.get(id_field)
        if key:
            index[key] = item
    return list(index.values())


def bill_latest_action_date(bill: Dict[str, Any]) -> str:
    dates = [(action.get("date") or "")[:10] for action in bill.get("actions") or [] if action.get("date")]
    return max(dates) if dates else ""


def bill_openstates_url(bill: Dict[str, Any], state_code: str) -> str:
    bill_id = bill.get("id") or ""
    if bill_id.startswith("ocd-bill/"):
        return f"https://openstates.org/bills/{bill_id.split('/', 1)[1]}/"
    identifier = (bill.get("identifier") or "").replace(" ", "")
    session = bill.get("legislative_session") or ""
    if identifier and session:
        return f"https://openstates.org/bills/{state_code.lower()}/{session}/{identifier}/"
    return ""


def bill_abstract(bill: Dict[str, Any]) -> str:
    for entry in bill.get("abstracts") or []:
        if isinstance(entry, dict):
            text = entry.get("abstract") or entry.get("note") or ""
        else:
            text = str(entry)
        if text:
            return text[:2000]
    return ""


def convert_sponsorships(bill: Dict[str, Any]) -> List[Dict[str, Any]]:
    sponsorships: List[Dict[str, Any]] = []
    for sponsor in bill.get("sponsors") or []:
        name = sponsor.get("name", "")
        sponsorships.append(
            {
                "name": name,
                "primary": bool(sponsor.get("primary")),
                "classification": sponsor.get("classification", ""),
                "person": {"name": name, "party": sponsor.get("party", "")},
            }
        )
    return sponsorships


def from_organization(bill: Dict[str, Any]) -> Dict[str, Any]:
    chamber = (bill.get("chamber") or "").lower()
    label = CHAMBER_NAMES.get(chamber, bill.get("chamber") or "")
    if label:
        return {"name": label}
    org_name = bill.get("organization__name") or bill.get("jurisdiction_name") or ""
    return {"name": org_name}


def convert_bulk_bill(bill: Dict[str, Any], state_code: str) -> Dict[str, Any]:
    latest = bill_latest_action_date(bill)
    return {
        "id": bill.get("id"),
        "identifier": bill.get("identifier", ""),
        "title": bill.get("title", ""),
        "abstract": bill_abstract(bill),
        "classification": bill.get("classification") or [],
        "subject": bill.get("subject") or [],
        "actions": bill.get("actions") or [],
        "sponsorships": convert_sponsorships(bill),
        "versions": bill.get("versions") or [],
        "documents": bill.get("documents") or [],
        "related_bills": bill.get("related_bills") or [],
        "from_organization": from_organization(bill),
        "updated_at": latest or bill.get("updated_at") or "",
        "openstates_url": bill.get("openstates_url") or bill_openstates_url(bill, state_code),
        "legislative_session": bill.get("legislative_session"),
        "sources": bill.get("sources") or [],
        "votes": bill.get("votes") or [],
    }


def extract_votes(bills: Iterable[Dict[str, Any]], state_code: str) -> List[Dict[str, Any]]:
    votes: List[Dict[str, Any]] = []
    for bill in bills:
        bill_id = bill.get("id")
        for vote in bill.get("votes") or []:
            vote_id = vote.get("id") or f"{bill_id}:{vote.get('start_date')}:{vote.get('motion_text', '')[:40]}"
            votes.append(
                {
                    "id": vote_id,
                    "bill_id": bill_id,
                    "bill_number": bill.get("identifier"),
                    "state": state_code.upper(),
                    "motion_text": vote.get("motion_text", ""),
                    "result": vote.get("result", ""),
                    "date": vote.get("start_date", ""),
                    "organization": vote.get("organization__classification", ""),
                    "counts": vote.get("counts") or [],
                    "votes": vote.get("votes") or [],
                }
            )
    return votes


def parse_state_from_bills_path(path: Path) -> Optional[str]:
    name = path.name
    if name.endswith("_bills.json"):
        return name.split("_", 1)[0].lower()
    return None


def discover_bill_files(bulk_dirs: Iterable[Path]) -> List[Tuple[str, Path, Path]]:
    """Return (state_code, bill_file_path, bulk_root) for each bulk export."""
    discovered: List[Tuple[str, Path, Path]] = []
    seen_paths: Set[str] = set()
    for bulk_dir in bulk_dirs:
        if not bulk_dir.exists():
            continue
        for path in sorted(bulk_dir.rglob("*_bills.json")):
            key = str(path.resolve())
            if key in seen_paths:
                continue
            state_code = parse_state_from_bills_path(path)
            if not state_code or state_code.upper() in SKIP_STATE_CODES:
                continue
            seen_paths.add(key)
            discovered.append((state_code, path, bulk_dir))
    return discovered


def fetch_legislators_csv(state_code: str) -> List[Dict[str, Any]]:
    url = f"https://data.openstates.org/people/current/{state_code.lower()}.csv"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            text = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"WARNING: could not fetch legislators for {state_code.upper()}: {exc}")
        return []

    legislators: List[Dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(text)):
        legislators.append(
            {
                "id": row.get("id", ""),
                "name": row.get("name", ""),
                "party": row.get("current_party", ""),
                "current_role": {
                    "district": row.get("current_district", ""),
                    "title": row.get("current_chamber", ""),
                },
                "gender": row.get("gender", ""),
                "birth_date": row.get("birth_date", ""),
                "image": row.get("image", ""),
                "links": row.get("links", ""),
                "sources": row.get("sources", ""),
                "openstates_url": "",
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            }
        )
    return legislators


def import_state(
    state_code: str,
    bill_files: List[Tuple[Path, Path]],
    since: str,
    include_all: bool,
    fetch_legislators: bool,
) -> Dict[str, int]:
    converted: List[Dict[str, Any]] = []
    raw_count = 0
    for path, _bulk_root in bill_files:
        raw_bills = load_json(path, [])
        if not isinstance(raw_bills, list):
            print(f"WARNING: skipping {path} (expected list of bills)")
            continue
        raw_count += len(raw_bills)
        for bill in raw_bills:
            if not include_all and since:
                latest = bill_latest_action_date(bill)
                if latest and latest < since:
                    continue
            converted.append(convert_bulk_bill(bill, state_code))

    state_dir = OUTPUT_DIR / state_code
    existing_bills = load_state_bills(state_dir)
    bills = merge_by_id(existing_bills, converted)
    votes = merge_by_id(load_json(state_dir / "votes.json", []), extract_votes(bills, state_code))

    legislators = load_json(state_dir / "legislators.json", [])
    if fetch_legislators or not legislators:
        legislators = fetch_legislators_csv(state_code)

    bill_files_saved = save_state_bills(state_dir, bills)
    save_json(state_dir / "events.json", load_json(state_dir / "events.json", []))
    save_json(state_dir / "committees.json", load_json(state_dir / "committees.json", []))
    save_json(state_dir / "legislators.json", legislators)
    save_json(state_dir / "votes.json", votes)

    meta = {
        "state": state_code.upper(),
        "source": "bulk_import",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "last_successful_fetch_at": datetime.now(timezone.utc).isoformat(),
        "updated_since": since if not include_all else None,
        "import_mode": "full" if include_all else "since_filter",
        "backfill_complete": True,
        "bulk_files": [
            str(path.relative_to(bulk_root)).replace("\\", "/")
            for path, bulk_root in bill_files
        ],
        "bill_files": bill_files_saved,
        "counts": {
            "bills": len(bills),
            "events": len(load_json(state_dir / "events.json", [])),
            "committees": len(load_json(state_dir / "committees.json", [])),
            "legislators": len(legislators),
            "votes": len(votes),
        },
    }
    save_json(state_dir / "meta.json", meta)

    kept = len(converted)
    filter_note = "all bills imported" if include_all else f"filtered since {since}"
    print(
        f"{state_code.upper()}: {raw_count} raw bills across {len(bill_files)} file(s) -> "
        f"{kept} imported ({filter_note}) -> {len(bills)} total in cache"
    )
    return {"raw": raw_count, "kept": kept, "total": len(bills)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Open States bulk JSON into data/openstates/")
    parser.add_argument(
        "--bulk-dir",
        action="append",
        dest="bulk_dirs",
        type=Path,
        help="Directory containing extracted Open States bulk JSON folders (repeatable; default: data/historic, data/nebraska, data/maryland, data/pennsylvania, data/massachusetts, data/west_virginia, data/tennessee, data/north_carolina, data/missouri, data/iowa)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Optional YYYY-MM-DD cutoff (latest action date). Default: import every bill in the bulk files.",
    )
    parser.add_argument("--states", type=str, default=None, help="Comma-separated state codes (default: configured Open States states found in bulk dir)")
    parser.add_argument("--skip-legislators", action="store_true", help="Do not download legislator CSV files")
    args = parser.parse_args()

    config = load_config()
    include_all = not args.since
    since = args.since or ""
    configured_states = {
        s["code"]
        for s in config.get("states", [])
        if s.get("enabled") and "openstates" in (s.get("sources") or [])
    }

    if args.states:
        target_states = {s.strip().lower() for s in args.states.split(",") if s.strip()}
    else:
        target_states = configured_states

    bulk_dirs = args.bulk_dirs or DEFAULT_BULK_DIRS
    existing_dirs = [path for path in bulk_dirs if path.exists()]
    if not existing_dirs:
        searched = ", ".join(str(path) for path in bulk_dirs)
        print(f"No bulk directories found (looked in: {searched})")
        sys.exit(1)

    discovered = discover_bill_files(existing_dirs)
    if not discovered:
        searched = ", ".join(str(path) for path in existing_dirs)
        print(f"No *_bills.json files found under: {searched}")
        sys.exit(1)

    by_state: Dict[str, List[Tuple[Path, Path]]] = {}
    for state_code, path, bulk_root in discovered:
        by_state.setdefault(state_code, []).append((path, bulk_root))

    imported: Set[str] = set()
    for state_code in sorted(by_state):
        if state_code not in target_states:
            print(f"Skipping {state_code.upper()} (not in target states)")
            continue
        import_state(
            state_code,
            by_state[state_code],
            since=since,
            include_all=include_all,
            fetch_legislators=not args.skip_legislators,
        )
        imported.add(state_code)

    missing = sorted(target_states - imported)
    if missing:
        print("No bulk files found for:", ", ".join(code.upper() for code in missing))

    print(f"\nBulk import complete for: {', '.join(sorted(code.upper() for code in imported)) or 'none'}")
    print("Next: python src/processing/normalize_data.py")


if __name__ == "__main__":
    main()
