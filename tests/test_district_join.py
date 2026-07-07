"""Tests for district GeoJSON ↔ legislator join logic."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.district_join import (  # noqa: E402
    build_district_legislator_index,
    extract_district_from_feature,
    is_house_legislator,
    list_legislators_for_chamber,
    lookup_legislators_for_feature,
    normalize_chamber,
    normalize_district,
)


def test_normalize_chamber_variants():
    assert normalize_chamber("Representative") == "house"
    assert normalize_chamber("lower") == "house"
    assert normalize_chamber("Senator") == "senate"
    assert normalize_chamber("legislature") == "senate"
    assert normalize_chamber("upper") == "senate"
    assert normalize_chamber("U.S. Representative") == "us_house"
    assert normalize_chamber("U.S. Senator") == "us_senate"


def test_normalize_district_strips_leading_zeros():
    assert normalize_district("086") == "86"
    assert normalize_district("80") == "80"
    assert normalize_district(120) == "120"
    assert normalize_district("01") == "1"


def test_extract_district_from_census_properties():
    props = {"GEOID": "20080", "SLDL": "080", "NAME": "State House District 80", "BASENAME": "80"}
    assert extract_district_from_feature(props) == "80"

    upper = {"GEOID": "20023", "SLDU": "023", "BASENAME": "23"}
    assert extract_district_from_feature(upper) == "23"

    cd = {"GEOID": "2001", "CD119": "01", "BASENAME": "1"}
    assert extract_district_from_feature(cd) == "1"


def test_build_index_and_lookup():
    legislators = [
        {"state": "KS", "chamber": "Representative", "district": "86", "name": "Abi Boatman", "party": "Democratic"},
        {"state": "KS", "chamber": "Senator", "district": "23", "name": "Adam Thomas", "party": "Republican"},
        {"state": "KS", "chamber": "U.S. Representative", "district": "3", "name": "Sharice Davids", "party": "Democratic"},
        {"state": "CO", "chamber": "Representative", "district": "1", "name": "Other", "party": "Democratic"},
    ]
    index = build_district_legislator_index(legislators, state="KS", chamber="house")
    assert "86" in index
    assert len(index["86"]) == 1
    assert index["86"][0]["name"] == "Abi Boatman"
    assert "23" not in index

    matched = lookup_legislators_for_feature({"SLDL": "086", "BASENAME": "86"}, index)
    assert len(matched) == 1
    assert matched[0]["name"] == "Abi Boatman"

    us_index = build_district_legislator_index(legislators, state="KS", chamber="us_house")
    assert us_index["3"][0]["name"] == "Sharice Davids"


def test_list_legislators_for_chamber_statewide():
    legislators = [
        {"state": "KS", "chamber": "U.S. Senator", "name": "Jerry Moran"},
        {"state": "KS", "chamber": "U.S. Senator", "name": "Roger Marshall"},
        {"state": "KS", "chamber": "U.S. Representative", "district": "1", "name": "Tracey Mann"},
    ]
    senators = list_legislators_for_chamber(legislators, state="KS", chamber="us_senate")
    assert len(senators) == 2
    assert {s["name"] for s in senators} == {"Jerry Moran", "Roger Marshall"}


def test_is_house_legislator():
    assert is_house_legislator({"state": "KS", "chamber": "Representative"})
    assert not is_house_legislator({"state": "KS", "chamber": "Senator"})
    assert not is_house_legislator({"state": "CO", "chamber": "Representative"})


def test_nebraska_legislature_chamber_join():
    legislators = [
        {"state": "NE", "chamber": "legislature", "district": "13", "name": "Ashlei Spivey"},
        {"state": "NE", "chamber": "legislature", "district": "40", "name": "Barry DeKay"},
    ]
    index = build_district_legislator_index(legislators, state="NE", chamber="senate")
    assert index["13"][0]["name"] == "Ashlei Spivey"
    assert index["40"][0]["name"] == "Barry DeKay"


def test_geojson_join_coverage_report():
    """Optional integration check when GeoJSON and site data are present."""
    site_path = ROOT / "docs" / "site_data.json"
    geo_dir = ROOT / "docs" / "data" / "geo"
    delegation_path = ROOT / "data" / "federal" / "delegation.json"
    if not site_path.exists() or not geo_dir.exists():
        return

    site = json.loads(site_path.read_text(encoding="utf-8"))
    legislators = list(site.get("search_index", {}).get("legislators", []))
    if delegation_path.exists():
        delegation = json.loads(delegation_path.read_text(encoding="utf-8"))
        seen = {leg.get("id") for leg in legislators if leg.get("id")}
        for member in delegation:
            member_id = member.get("id")
            if member_id and member_id in seen:
                continue
            legislators.append(member)
            if member_id:
                seen.add(member_id)

    layers = [
        ("ks", "sld-lower", "KS", "house"),
        ("ks", "sld-upper", "KS", "senate"),
        ("ks", "cd119", "KS", "us_house"),
    ]

    for prefix, suffix, state, chamber in layers:
        path = geo_dir / f"{prefix}-{suffix}.geojson"
        if not path.exists():
            continue
        geojson = json.loads(path.read_text(encoding="utf-8"))
        index = build_district_legislator_index(legislators, state=state, chamber=chamber)
        if not index:
            continue
        matched = sum(
            1
            for feature in geojson.get("features", [])
            if lookup_legislators_for_feature(feature.get("properties", {}), index)
        )
        assert matched > 0
