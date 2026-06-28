"""Unit tests for source adapters."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from adapters.congress_source import CongressSource, fix_hearing_url
from adapters.kansas_rss_source import KansasRSSSource
from adapters.openstates_source import OpenStatesSource


def test_congress_normalize_bill():
    raw = [{
        "bill_type": "HR",
        "bill_number": "123",
        "title": "Test Bill",
        "congress": 119,
        "latest_action": "Introduced",
        "latest_action_date": "2026-01-15",
        "url": "https://www.congress.gov/bill/119th-congress/house-bill/123",
        "sponsor_name": "Rep. Smith",
        "sponsor_party": "D",
    }]
    adapter = CongressSource()
    result = adapter.normalize_bills(raw)
    assert len(result) == 1
    assert result[0].source == "congress"
    assert result[0].level == "federal"
    assert result[0].state is None
    assert result[0].bill_number == "HR 123"


def test_kansas_normalize_bill():
    raw = [{
        "id": "test-id",
        "title": "Senate: SB498: Introduced",
        "link": "https://www.kslegislature.gov/li/b2025_26/measures/SB498/",
        "published": "2026-02-06T19:45:48+00:00",
        "type": "state_legislation",
        "state": "KS",
        "bill_number": "SB 498",
        "category": "Events",
    }]
    adapter = KansasRSSSource()
    result = adapter.normalize_bills(raw)
    assert result[0].source == "kansas_rss"
    assert result[0].state == "KS"
    assert result[0].chamber == "Senate"


def test_openstates_normalize_bill():
    raw = [{
        "id": "ocd-bill/test",
        "identifier": "HB 1001",
        "title": "Education funding bill",
        "updated_at": "2026-01-20T00:00:00+00:00",
        "openstates_url": "https://openstates.org/bills/test",
        "actions": [{"description": "Passed House", "date": "2026-01-19"}],
        "sponsorships": [{"person": {"name": "Jane Doe", "party": "R"}, "primary": True}],
    }]
    adapter = OpenStatesSource("co", "ocd-jurisdiction/country:us/state:co/government")
    adapter.set_data(bills=raw)
    result = adapter.normalize_bills(raw)
    assert result[0].source == "openstates"
    assert result[0].state == "CO"
    assert result[0].latest_action == "Passed House"


def test_fix_hearing_url():
    hearing = {"event_id": "118840", "congress": 119, "chamber": "House", "url": ""}
    fix_hearing_url(hearing)
    assert "congress.gov/event" in hearing["url"]
    assert "118840" in hearing["url"]
