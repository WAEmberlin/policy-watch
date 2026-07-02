"""Tests for veteran impact classification and CO import helpers."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.veteran_impact import (  # noqa: E402
    build_bill_lookup_key,
    build_veteran_impact_lookup,
    classify_veteran_impact,
    normalize_co_csv_bill_number,
    resolve_veteran_impact_for_item,
)


def test_normalize_co_csv_bill_number():
    assert normalize_co_csv_bill_number("HB26-1002") == ("HB26-1002", "HB 1002")
    assert normalize_co_csv_bill_number("sb26-047") == ("SB26-047", "SB 047")


def test_classify_red_from_gi_bill():
    result = classify_veteran_impact("Expand GI Bill education benefits for veterans")
    assert result is not None
    assert result["level"] == "red"
    assert "Benefits & Compensation" in result["factors"]


def test_classify_yellow_from_employment_preference():
    result = classify_veteran_impact("Veterans employment preference in state hiring")
    assert result is not None
    assert result["level"] == "yellow"


def test_classify_green_from_memorial():
    result = classify_veteran_impact("Honoring Post-9/11 Veterans memorial resolution")
    assert result is not None
    assert result["level"] == "green"


def test_csv_level_overrides_rules():
    result = classify_veteran_impact("Generic elections bill", csv_level="Red")
    assert result is not None
    assert result["level"] == "red"
    assert result["source"] == "csv"


def test_build_lookup_from_co_data():
    co_data = {
        "bills": {
            "HB26-1002": {
                "bill_number_csv": "HB26-1002",
                "bill_number_norm": "HB 1002",
                "title": "Honoring Post-9/11 Veterans",
                "veteran_related": True,
                "impact_level": "green",
                "status": "Became Law",
            }
        }
    }
    lookup = build_veteran_impact_lookup(co_data=co_data, normalized_bills=[])
    assert lookup["CO|HB26-1002"]["level"] == "green"
    assert lookup[build_bill_lookup_key("CO", "HB 1002")]["level"] == "green"


def test_resolve_veteran_impact_for_feed_item():
    lookup = {
        "CO|HB26-1002": {"level": "green", "factors": [], "source": "csv", "veteran_related": True},
    }
    item = {
        "title": "HB 1002: Honoring Post-9/11 Veterans",
        "bill_number": "HB 1002",
        "source": "State (Colorado)",
        "state": "CO",
    }
    impact = resolve_veteran_impact_for_item(item, lookup)
    assert impact is not None
    assert impact["level"] == "green"


def test_non_veteran_bill_returns_none():
    assert classify_veteran_impact("Property tax assessment reform") is None
