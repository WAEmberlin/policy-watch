"""Tests for Arizona Cactus Watch and Utah committee RSS parsers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_arizona_cactus import (  # noqa: E402
    bill_to_history_item,
    normalize_az_bill_number,
)
from processing.fetch_utah_committee_rss import (  # noqa: E402
    parse_committee_entry,
    parse_session_block,
)


def test_normalize_az_bill_number():
    assert normalize_az_bill_number("HB2839") == "HB 2839"
    assert normalize_az_bill_number("sb 1010") == "SB 1010"


def test_bill_to_history_item():
    item = bill_to_history_item({
        "number": "HB2839",
        "short_title": "Veterans employment preference",
        "last_action": "Passed House",
        "last_action_date": "2026-03-01T12:00:00",
        "azleg_url": "https://apps.azleg.gov/BillStatus/BillOverview/123",
    })
    assert item is not None
    assert item["bill_number"] == "HB 2839"
    assert item["state"] == "AZ"
    assert item["feed"] == "arizona_cactus"


def test_parse_session_block():
    parsed = parse_session_block("11/18/2026 1:15:00 PM - 120 Senate Building")
    assert parsed is not None
    scheduled_iso, location, date_part = parsed
    assert "2026-11-18" in scheduled_iso
    assert location == "120 Senate Building"
    assert date_part == "11/18/2026"


def test_parse_committee_entry():
    hearings, history = parse_committee_entry({
        "title": "House Judiciary Committee",
        "link": "http://le.utah.gov/committee/committee.jsp?year=2026&com=HSTJUD",
        "summary": (
            "<b>11/18/2026 1:15:00 PM - 120 Senate Building</b>"
            "<ul><li><a href=\"http://le.utah.gov/Interim/2026/html/00002167.htm\">NOTICE</a></li>"
            "<li>Veterans treatment court funding</li></ul>"
        ),
    })
    assert len(hearings) == 1
    assert hearings[0]["committee_code"] == "HSTJUD"
    assert hearings[0]["state"] == "UT"
    assert "Veterans treatment court funding" in hearings[0]["description"]
    assert len(history) == 1
    assert history[0]["feed"] == "utah_committee_rss"
