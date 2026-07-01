"""Tests for district GeoJSON ↔ legislator join logic."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.district_join import (  # noqa: E402
    build_congressional_index,
    build_district_legislator_index,
    extract_district_from_feature,
    is_house_legislator,
    lookup_legislators_for_feature,
    normalize_chamber,
    normalize_district,
)


def test_normalize_chamber_variants():
    assert normalize_chamber("Representative") == "house"
    assert normalize_chamber("lower") == "house"
    assert normalize_chamber("Senator") == "senate"
    assert normalize_chamber("upper") == "senate"


def test_normalize_district_strips_leading_zeros():
    assert normalize_district("086") == "86"
    assert normalize_district("80") == "80"
    assert normalize_district(120) == "120"


def test_extract_district_from_census_properties():
    props = {"GEOID": "20080", "SLDL": "080", "NAME": "State House District 80", "BASENAME": "80"}
    assert extract_district_from_feature(props) == "80"


def test_build_index_and_lookup():
    legislators = [
        {"state": "KS", "chamber": "Representative", "district": "86", "name": "Abi Boatman", "party": "Democratic"},
        {"state": "KS", "chamber": "Senator", "district": "23", "name": "Adam Thomas", "party": "Republican"},
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


def test_is_house_legislator():
    assert is_house_legislator({"state": "KS", "chamber": "Representative"})
    assert not is_house_legislator({"state": "KS", "chamber": "Senator"})
    assert not is_house_legislator({"state": "CO", "chamber": "Representative"})


def test_extract_district_from_senate_and_congress_properties():
    senate_props = {"GEOID": "20023", "SLDU": "023", "NAME": "State Senate District 23", "BASENAME": "23"}
    assert extract_district_from_feature(senate_props, layer="senate") == "23"

    congress_props = {"GEOID": "2003", "CD119": "03", "NAME": "Congressional District 3", "BASENAME": "3"}
    assert extract_district_from_feature(congress_props, layer="congress") == "3"


def test_build_congressional_index_and_lookup():
    delegation = {
        "representatives": [
            {"district": "1", "name": "Rep One", "party": "Republican", "chamber": "Representative"},
            {"district": "3", "name": "Rep Three", "party": "Democratic", "chamber": "Representative"},
        ],
        "senators": [{"name": "Sen One", "party": "Republican", "chamber": "Senator"}],
    }
    index = build_congressional_index(delegation)
    matched = lookup_legislators_for_feature({"CD119": "03", "BASENAME": "3"}, index, layer="congress")
    assert len(matched) == 1
    assert matched[0]["name"] == "Rep Three"
