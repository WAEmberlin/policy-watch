#!/usr/bin/env python3
"""
Fetch Kansas U.S. House and Senate delegation from the public congress-legislators dataset.

Source: https://github.com/unitedstates/congress-legislators
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "kansas" / "federal_delegation.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "kansas" / "federal_delegation.json"

SOURCE_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
STATE = "KS"


def _today() -> date:
    return date.today()


def _is_current_term(term: Dict[str, Any], *, today: date) -> bool:
    end = term.get("end")
    if not end:
        return True
    try:
        end_date = date.fromisoformat(str(end)[:10])
    except ValueError:
        return False
    return end_date >= today


def _display_name(entry: Dict[str, Any]) -> str:
    name = entry.get("name") or {}
    if name.get("official_full"):
        return str(name["official_full"])
    parts = [name.get("first"), name.get("last")]
    return " ".join(p for p in parts if p) or "Unknown"


def _profile_url(entry: Dict[str, Any], term: Dict[str, Any]) -> str:
    for key in ("url",):
        if term.get(key):
            return str(term[key])
    ids = entry.get("id") or {}
    bioguide = ids.get("bioguide")
    if bioguide:
        return f"https://www.congress.gov/member/{bioguide}"
    return ""


def _photo_url(entry: Dict[str, Any]) -> str:
    ids = entry.get("id") or {}
    bioguide = ids.get("bioguide")
    if bioguide:
        return f"https://bioguide.congress.gov/bioguide/photo/{bioguide[0]}/{bioguide}.jpg"
    return ""


def normalize_delegation(raw: List[Dict[str, Any]], *, state: str = STATE) -> Dict[str, Any]:
    today = _today()
    representatives: List[Dict[str, Any]] = []
    senators: List[Dict[str, Any]] = []

    for entry in raw:
        current_terms = [
            t
            for t in (entry.get("terms") or [])
            if t.get("state") == state and _is_current_term(t, today=today)
        ]
        if not current_terms:
            continue
        current = current_terms[-1]
        term_type = current.get("type")
        person = {
            "name": _display_name(entry),
            "party": current.get("party") or "",
            "url": _profile_url(entry, current),
            "image": _photo_url(entry),
            "level": "federal",
            "state": state,
        }
        if term_type == "sen":
            person["chamber"] = "Senator"
            senators.append(person)
        elif term_type == "rep":
            district = current.get("district")
            if district is None:
                continue
            person["chamber"] = "Representative"
            person["district"] = str(int(district))
            representatives.append(person)

    representatives.sort(key=lambda r: int(r.get("district") or 0))
    senators.sort(key=lambda r: r.get("name") or "")
    return {
        "_meta": {
            "source": SOURCE_URL,
            "state": state,
            "fetched_at": today.isoformat(),
        },
        "representatives": representatives,
        "senators": senators,
    }


def fetch_legislators() -> List[Dict[str, Any]]:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "policy-watch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> int:
    try:
        raw = fetch_legislators()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to download delegation: {exc}", file=sys.stderr)
        return 1

    payload = normalize_delegation(raw)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    for path in (OUTPUT, DOCS_OUTPUT):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    reps = len(payload["representatives"])
    sens = len(payload["senators"])
    print(f"Wrote Kansas federal delegation: {reps} representatives, {sens} senators")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
