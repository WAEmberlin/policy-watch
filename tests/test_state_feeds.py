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
from processing.utah_notice_utils import (  # noqa: E402
    filter_agenda_items,
    parse_notice_html,
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
    assert "NOTICE" not in hearings[0]["agenda_items"]
    assert hearings[0]["description"] != "NOTICE"
    assert len(history) == 1
    assert history[0]["feed"] == "utah_committee_rss"
    assert history[0]["summary"] != "NOTICE"


def test_parse_notice_html_extracts_meeting_details():
    html = """
    <html><body>
    <p>The chair(s) of the Legislative Audit Subcommittee have scheduled the following meeting:</p>
    <p>DATE: Tuesday, December 8, 2026</p>
    <p>TIME: 4:00 p.m.</p>
    <p>PLACE: Room 445 State Capitol</p>
    <p>Members of the public may participate remotely by visiting:
    <a href="https://le.utah.gov/committee/committee.jsp?year=2026&amp;com=SPEAUD">committee webpage</a></p>
    </body></html>
    """
    details = parse_notice_html(
        html,
        fallback_stream_url="https://le.utah.gov/committee/committee.jsp?year=2026&com=SPEAUD",
    )
    assert details["notice_date"] == "Tuesday, December 8, 2026"
    assert details["notice_time"] == "4:00 p.m."
    assert details["notice_place"] == "Room 445 State Capitol"
    assert "committee.jsp" in details["livestream_url"]


def test_filter_agenda_items_removes_notice():
    assert filter_agenda_items(["NOTICE", "Budget review"]) == ["Budget review"]
