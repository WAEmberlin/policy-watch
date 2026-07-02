#!/usr/bin/env python3
"""Report district map join coverage across states and chambers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.district_join import (  # noqa: E402
    build_district_legislator_index,
    list_legislators_for_chamber,
    lookup_legislators_for_feature,
)

LAYERS = [
    ("ks", "sld-lower", "KS", "house"),
    ("ks", "sld-upper", "KS", "senate"),
    ("ks", "cd119", "KS", "us_house"),
    ("ks", "state", "KS", "us_senate"),
    ("co", "sld-lower", "CO", "house"),
    ("co", "sld-upper", "CO", "senate"),
    ("co", "cd119", "CO", "us_house"),
    ("co", "state", "CO", "us_senate"),
    ("az", "sld-lower", "AZ", "house"),
    ("az", "sld-upper", "AZ", "senate"),
    ("az", "cd119", "AZ", "us_house"),
    ("az", "state", "AZ", "us_senate"),
    ("ut", "sld-lower", "UT", "house"),
    ("ut", "sld-upper", "UT", "senate"),
    ("ut", "cd119", "UT", "us_house"),
    ("ut", "state", "UT", "us_senate"),
    ("me", "sld-lower", "ME", "house"),
    ("me", "sld-upper", "ME", "senate"),
    ("me", "cd119", "ME", "us_house"),
    ("me", "state", "ME", "us_senate"),
]


def load_legislators() -> list:
    site_path = ROOT / "docs" / "site_data.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    legislators = list(site.get("search_index", {}).get("legislators", []))

    delegation_path = ROOT / "data" / "federal" / "delegation.json"
    if delegation_path.exists():
        delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
        seen = {leg.get("id") for leg in legislators if leg.get("id")}
        for member in delegation:
            member_id = member.get("id")
            if member_id and member_id in seen:
                continue
            legislators.append(
                {
                    "id": member.get("id"),
                    "name": member.get("name"),
                    "party": member.get("party"),
                    "state": member.get("state"),
                    "district": member.get("district"),
                    "chamber": member.get("chamber"),
                    "gender": member.get("gender"),
                    "birth_date": member.get("birth_date"),
                    "image": member.get("image"),
                    "url": member.get("url"),
                }
            )
            if member_id:
                seen.add(member_id)
    return legislators


def main() -> int:
    legislators = load_legislators()
    geo_dir = ROOT / "docs" / "data" / "geo"
    print(f"Legislators loaded: {len(legislators)}")
    print(f"{'State':<4} {'Layer':<12} {'Chamber':<10} {'Matched':>8} {'Total':>8}")
    print("-" * 50)

    for prefix, suffix, state, chamber in LAYERS:
        path = geo_dir / f"{prefix}-{suffix}.geojson"
        if not path.exists():
            print(f"{state:<4} {suffix:<12} {chamber:<10} {'MISSING':>8}")
            continue

        geojson = json.loads(path.read_text(encoding="utf-8"))
        features = geojson.get("features", [])
        if suffix == "state":
            matched = 1 if list_legislators_for_chamber(legislators, state=state, chamber=chamber) else 0
        else:
            index = build_district_legislator_index(legislators, state=state, chamber=chamber)
            matched = sum(
                1
                for feature in features
                if lookup_legislators_for_feature(feature.get("properties", {}), index)
            )
        print(f"{state:<4} {suffix:<12} {chamber:<10} {matched:>8} {len(features):>8}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
