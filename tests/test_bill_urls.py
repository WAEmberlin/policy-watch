"""Tests for official bill URL resolution."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.bill_urls import (  # noqa: E402
    build_ks_bill_url,
    normalize_bill_url,
    pick_best_bill_url,
    resolve_official_bill_url,
)


def test_prefers_state_legislature_over_openstates():
    bill = {
        "openstates_url": "https://openstates.org/bills/example/",
        "sources": [{"url": "https://leg.colorado.gov/bills/HB26-1247"}],
        "versions": [{"links": [{"url": "https://leg.colorado.gov/bill_files/112194/download"}]}],
    }
    assert resolve_official_bill_url(bill) == "https://leg.colorado.gov/bills/HB26-1247"


def test_falls_back_to_openstates_when_no_official_source():
    bill = {"openstates_url": "https://openstates.org/bills/example/", "sources": []}
    assert "openstates.org" in resolve_official_bill_url(bill)


def test_build_ks_bill_url_for_house_bill():
    assert build_ks_bill_url("HB 2535") == "https://www.kslegislature.gov/b2025_26/bills/HB2535"


def test_build_ks_bill_url_for_resolution():
    assert build_ks_bill_url("HCR 5008") == "https://www.kslegislature.gov/b2025_26/resolutions/HCR5008/"


def test_normalize_stale_ks_url():
    stale = "http://kslegislature.org/li/b2023_24/measures/hb2535/"
    fixed = normalize_bill_url(stale, "KS", "HB 2535")
    assert fixed == "https://www.kslegislature.gov/b2025_26/bills/HB2535"


def test_pick_best_bill_url_prefers_current_session():
    stale = "http://kslegislature.org/li/b2023_24/measures/hcr5008/"
    current = "https://www.kslegislature.gov/b2025_26/resolutions/HCR5008/"
    chosen = pick_best_bill_url([stale, current], "KS", "HCR 5008")
    assert chosen == current
