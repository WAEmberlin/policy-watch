"""Tests for official bill URL resolution."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.bill_urls import resolve_official_bill_url


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
