"""Tests for Arizona Cactus Watch and Utah committee RSS parsers."""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_arizona_cactus import (  # noqa: E402
    bill_to_history_item,
    normalize_az_bill_number,
)
from processing.fetch_utah_committee_rss import (  # noqa: E402
    enrich_hearing_from_notice,
    has_notice_enrichment,
    is_upcoming_hearing,
    normalize_notice_url,
    notice_cache_is_fresh,
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


def test_normalize_notice_url():
    assert normalize_notice_url(
        "http://le.utah.gov/Interim/2026/html/00002167.htm"
    ) == normalize_notice_url(
        "https://le.utah.gov/Interim/2026/html/00002167.htm"
    )


def test_has_notice_enrichment_accepts_livestream_only():
    assert has_notice_enrichment({
        "livestream_url": "https://le.utah.gov/committee/committee.jsp?year=2026&com=INTBUS",
    })


def test_notice_cache_is_fresh_for_enriched_or_recent_attempt():
    assert notice_cache_is_fresh({
        "notice_date": "Tuesday, December 8, 2026",
    })
    assert notice_cache_is_fresh({
        "notice_enriched_at": "2026-07-02T12:00:00+00:00",
    }, now=datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc))
    assert not notice_cache_is_fresh({
        "notice_enriched_at": "2026-07-01T12:00:00+00:00",
    }, now=datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc))


def test_enrich_hearing_reuses_cache_without_refetch(monkeypatch):
    notice_url = "https://le.utah.gov/Interim/2026/html/00002167.htm"
    hearing = {
        "link": notice_url,
        "scheduled_date": "2026-11-18T13:15:00+00:00",
        "committee_code": "INTBUS",
    }
    notice_cache = {
        notice_url: {
            "notice_date": "Tuesday, November 18, 2026",
            "notice_time": "1:15 p.m.",
            "notice_place": "120 Senate Building",
            "livestream_url": "https://le.utah.gov/committee/committee.jsp?year=2026&com=INTBUS",
            "notice_enriched_at": "2026-07-01T12:00:00+00:00",
        }
    }

    def fail_fetch(*args, **kwargs):
        raise AssertionError("should not fetch cached notice")

    monkeypatch.setattr(
        "processing.fetch_utah_committee_rss.fetch_notice_details",
        fail_fetch,
    )

    assert enrich_hearing_from_notice(hearing, notice_cache) is False
    assert hearing["notice_date"] == "Tuesday, November 18, 2026"
    assert "committee.jsp" in hearing["stream_url"]


def test_enrich_hearing_skips_fetch_for_past_uncached_notice(monkeypatch):
    notice_url = "https://le.utah.gov/Interim/2026/html/00002166.htm"
    hearing = {
        "link": notice_url,
        "scheduled_date": "2020-01-01T13:15:00+00:00",
        "committee_code": "INTBUS",
    }

    def fail_fetch(*args, **kwargs):
        raise AssertionError("should not fetch past uncached notice")

    monkeypatch.setattr(
        "processing.fetch_utah_committee_rss.fetch_notice_details",
        fail_fetch,
    )

    assert enrich_hearing_from_notice(hearing, {}) is False
    assert "notice_date" not in hearing


def test_is_upcoming_hearing():
    assert is_upcoming_hearing({"scheduled_date": "2099-01-01T12:00:00+00:00"})
    assert not is_upcoming_hearing({"scheduled_date": "2020-01-01T12:00:00+00:00"})
