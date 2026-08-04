#!/usr/bin/env python3
"""
Fetch current U.S. House and Senate members for configured states.

Source: unitedstates/congress-legislators (legislators-current.json)
  https://github.com/unitedstates/congress-legislators

Writes:
  - data/federal/delegation.json (canonical, all target states)
  - data/federal/delegation_{state}.json (per-state convenience copies)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

TARGET_STATES = ["KS", "CO", "AZ", "UT", "ME", "NE", "MD", "PA"]

LEGISLATORS_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/"
    "gh-pages/legislators-current.json"
)

PARTY_MAP = {
    "Democrat": "Democratic",
    "Republican": "Republican",
    "Independent": "Independent",
    "Libertarian": "Libertarian",
}


def _fetch_current_legislators() -> List[dict]:
    req = urllib.request.Request(LEGISLATORS_URL, headers={"User-Agent": "policy-watch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _current_term(person: dict) -> dict:
    terms = person.get("terms") or []
    return terms[-1] if terms else {}


def _profile_url(bioguide: str) -> str:
    return f"https://www.congress.gov/member/{bioguide}"


def _image_url(bioguide: str) -> str:
    return f"https://theunitedstates.io/images/congress/225x275/{bioguide}.jpg"


def normalize_delegation(raw_legislators: List[dict], states: Iterable[str]) -> List[dict]:
    target = {state.upper() for state in states}
    delegation: List[dict] = []

    for person in raw_legislators:
        term = _current_term(person)
        state = (term.get("state") or "").upper()
        if state not in target:
            continue

        term_type = term.get("type")
        if term_type == "rep":
            chamber = "U.S. Representative"
            district = str(term.get("district") or "")
        elif term_type == "sen":
            chamber = "U.S. Senator"
            district = ""
        else:
            continue

        ids = person.get("id") or {}
        bioguide = ids.get("bioguide") or ""
        name = (person.get("name") or {}).get("official_full") or ""
        party = PARTY_MAP.get(term.get("party") or "", term.get("party") or "")
        bio = person.get("bio") or {}

        record = {
            "id": f"bioguide/{bioguide}" if bioguide else person.get("id"),
            "source": "congress-legislators",
            "level": "federal",
            "state": state,
            "name": name,
            "party": party,
            "district": district,
            "chamber": chamber,
            "url": term.get("url") or (_profile_url(bioguide) if bioguide else ""),
            "gender": bio.get("gender", ""),
            "birth_date": bio.get("birthday", ""),
            "image": _image_url(bioguide) if bioguide else "",
        }
        delegation.append(record)

    delegation.sort(key=lambda item: (item["state"], item["chamber"], item.get("district") or "0", item["name"]))
    return delegation


def write_outputs(delegation: List[dict], states: Iterable[str]) -> None:
    output_dirs = [
        ROOT / "data" / "federal",
        ROOT / "docs" / "data" / "federal",
    ]
    for federal_dir in output_dirs:
        federal_dir.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(delegation, indent=2, ensure_ascii=False)
    for federal_dir in output_dirs:
        combined_path = federal_dir / "delegation.json"
        combined_path.write_text(payload, encoding="utf-8")
        print(f"Wrote {combined_path} ({len(delegation)} members)")

    by_state: Dict[str, List[dict]] = {}
    for member in delegation:
        by_state.setdefault(member["state"], []).append(member)

    for state in states:
        state_code = state.upper()
        members = by_state.get(state_code, [])
        state_payload = json.dumps(members, indent=2, ensure_ascii=False)
        for federal_dir in output_dirs:
            path = federal_dir / f"delegation_{state_code.lower()}.json"
            path.write_text(state_payload, encoding="utf-8")
        reps = sum(1 for m in members if m["chamber"] == "U.S. Representative")
        sens = sum(1 for m in members if m["chamber"] == "U.S. Senator")
        print(f"Wrote delegation_{state_code.lower()}.json ({reps} reps, {sens} senators)")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch U.S. congressional delegations")
    parser.add_argument(
        "--states",
        default=",".join(s.lower() for s in TARGET_STATES),
        help="Comma-separated state codes",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    if not states:
        print("ERROR: No states specified", file=sys.stderr)
        return 1

    try:
        raw = _fetch_current_legislators()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: Failed to download congress-legislators data: {exc}", file=sys.stderr)
        return 1

    delegation = normalize_delegation(raw, states)
    if not delegation:
        print("ERROR: No delegation members found for requested states", file=sys.stderr)
        return 1

    write_outputs(delegation, states)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
