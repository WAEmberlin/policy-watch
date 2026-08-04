"""Tests for email digest building."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.email_digest import (
    DIGEST_TITLE_MAX_LEN,
    build_digest_html,
    format_digest_title,
    hearing_scheduled_date,
    infer_item_state,
    is_hearing_within_lookahead,
    is_within_window,
    item_recency_ts,
    partition_by_state,
    partition_hearings,
    render_hearing,
    render_utah_hearing_update,
    split_omnibus_hearing_title,
    split_state_items,
)


def test_hearing_lookahead_excludes_beyond_tomorrow():
    today = datetime.now(timezone.utc).date()
    far = today + timedelta(days=10)
    assert is_hearing_within_lookahead({"notice_date": far.strftime("%A, %B %d, %Y")}, days=1) is False
    tomorrow = today + timedelta(days=1)
    assert is_hearing_within_lookahead({"notice_date": tomorrow.strftime("%A, %B %d, %Y")}, days=1) is True


def test_item_recency_uses_latest_action_date():
    now = datetime.now(timezone.utc)
    item = {
        "latest_action_date": now.isoformat(),
        "last_synced_at": "2026-01-01T00:00:00",
        "ks_api_enriched_at": now.isoformat(),
    }
    assert is_within_window(item, now, window_hours=6)


def test_enrichment_timestamp_does_not_qualify_stale_bill():
    now = datetime.now(timezone.utc)
    item = {
        "type": "state_legislation",
        "bill_number": "HB 100",
        "published": "2026-04-01T15:00:00+00:00",
        "latest_action_date": "2026-04-01T15:00:00+00:00",
        "ks_api_enriched_at": now.isoformat(),
        "last_synced_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    assert not is_within_window(item, now, window_hours=6)


def test_hearing_scheduled_date_prefers_notice_date_over_published():
    scheduled = hearing_scheduled_date({
        "published": "2026-01-01",
        "notice_date": "Tuesday, July 14, 2026",
    })
    assert scheduled == datetime(2026, 7, 14).date()


def test_midnight_action_date_counts_through_central_end_of_day():
    # Action dated today at midnight should still count near end of US day
    now = datetime(2026, 6, 28, 23, 0, tzinfo=timezone.utc)
    item = {"latest_action_date": "2026-06-28T00:00:00"}
    ts = item_recency_ts(item)
    assert ts is not None
    assert is_within_window(item, now, window_hours=6)


def test_infer_item_state():
    assert infer_item_state({"level": "federal", "source": "Congress.gov API"}) == "FEDERAL"
    assert infer_item_state({"state": "KS", "source": "Kansas Legislature"}) == "KS"
    assert infer_item_state({"state": "CO", "level": "state"}) == "CO"


def test_ks_digest_state_before_federal():
    items = {
        "KS": [{"title": "KS Bill", "link": "http://ks", "published": "2026-01-01"}],
        "FEDERAL": [{"title": "HR 1", "link": "http://congress", "published": "2026-01-01", "level": "federal"}],
    }
    hearings = {"KS": [], "FEDERAL": []}
    state_names = {"KS": "Kansas", "CO": "Colorado", "AZ": "Arizona", "UT": "Utah"}

    html, subject, total = build_digest_html("ks", items, hearings, state_names)
    assert "Kansas Policy Watch" in html
    assert "Kansas Policy Watch" in subject or "Kansas" in subject
    assert html.index("Kansas") < html.index("Federal")
    assert total == 2


def test_all_digest_alphabetical_then_federal():
    items = {
        "KS": [{"title": "KS", "link": "a", "published": "2026-01-01"}],
        "CO": [{"title": "CO", "link": "b", "published": "2026-01-01"}],
        "FEDERAL": [{"title": "HR", "link": "c", "published": "2026-01-01", "level": "federal"}],
    }
    hearings = {"KS": [], "CO": [], "FEDERAL": []}
    state_names = {"KS": "Kansas", "CO": "Colorado", "AZ": "Arizona", "UT": "Utah"}

    html, subject, _ = build_digest_html("all", items, hearings, state_names)
    assert "Colorado" in html
    assert html.index("Colorado") < html.index("Federal")
    assert html.index("Kansas") < html.index("Federal")
    assert "All States" in subject or "Policy Watch" in subject


def test_federal_only_digest():
    items = {
        "KS": [{"title": "KS", "link": "a", "published": "2026-01-01"}],
        "FEDERAL": [{"title": "HR 1", "link": "c", "published": "2026-01-01", "level": "federal"}],
    }
    html, subject, total = build_digest_html(
        "federal", items, {"FEDERAL": []}, {"KS": "Kansas"}
    )
    assert "Federal Policy Watch" in html
    assert "KS Bill" not in html and "KS" not in html or "Kansas" not in html.split("Federal")[0]
    assert total == 1


def test_utah_hearing_updates_separate_section():
    hearing_day = datetime.now(timezone.utc).date() + timedelta(days=1)
    notice_date = hearing_day.strftime("%A, %B %d, %Y")
    items = {
        "UT": [
            {"title": "HB 100", "link": "http://bill", "published": "2026-01-01", "state": "UT"},
            {
                "title": f"Legislative Audit Subcommittee — {hearing_day.month}/{hearing_day.day}/{hearing_day.year}",
                "link": "http://le.utah.gov/Interim/2026/html/00002131.htm",
                "published": "2026-01-01",
                "state": "UT",
                "feed": "utah_committee_rss",
                "notice_date": notice_date,
                "notice_time": "4:00 p.m.",
                "notice_place": "Room 445 State Capitol",
                "livestream_url": "https://le.utah.gov/committee/committee.jsp?year=2026&com=SPEAUD",
            },
        ],
        "FEDERAL": [],
    }
    updates, hearing_updates = split_state_items(items["UT"])
    assert len(updates) == 1
    assert len(hearing_updates) == 1

    html, _, total = build_digest_html("ut", items, {"UT": []}, {"UT": "Utah"})
    assert "Utah — Hearing Updates" in html
    assert html.index("Utah — Hearing Updates") < html.index("Federal")
    assert "NOTICE" not in html
    assert "Live stream options" in html
    assert total == 2


def test_render_utah_hearing_update_skips_notice_summary():
    html = render_utah_hearing_update({
        "title": "Legislative Audit Subcommittee — 12/8/2026",
        "link": "http://le.utah.gov/Interim/2026/html/00002131.htm",
        "summary": "NOTICE",
        "notice_date": "Tuesday, December 8, 2026",
        "notice_time": "4:00 p.m.",
        "notice_place": "Room 445 State Capitol",
        "livestream_url": "https://le.utah.gov/committee/committee.jsp?year=2026&com=SPEAUD",
    })
    assert "NOTICE" not in html
    assert "Date: Tuesday, December 8, 2026" in html
    assert "Live stream options" in html


def test_format_digest_title_keeps_short_titles():
    title = "Business meeting to consider S.239, Crow Tribe mineral interests"
    assert format_digest_title(title) == title


def test_format_digest_title_clause_truncates_long_non_omnibus():
    title = (
        "A very long hearing title without enough bill designations to treat as omnibus "
        "that keeps going with more descriptive text about the committee business day "
        "and procedural matters that would otherwise wrap poorly in email clients"
    )
    short = format_digest_title(title)
    assert short.endswith("…")
    assert len(short) <= DIGEST_TITLE_MAX_LEN


def test_split_omnibus_hearing_title_lists_each_measure():
    long_title = (
        "Business meeting to consider an original resolution regarding Contempt of Congress, "
        "S.2732, to strengthen employee cost savings initiatives at federal agencies, "
        "H.R.418, to rename the Main Street post office as the Firefighter Jane Doe Post Office, "
        "S.991, to rename the Oak Avenue post office, "
        "H.R.2201, to rename the Elm Street post office"
    )
    header, bullets = split_omnibus_hearing_title(long_title)
    assert "Business meeting to consider" in header
    assert any("Contempt of Congress" in b for b in bullets)
    assert any(b.startswith("S.2732") for b in bullets)
    assert any("H.R.418" in b and "Firefighter Jane Doe" in b for b in bullets)
    assert any(b.startswith("S.991") for b in bullets)
    assert any(b.startswith("H.R.2201") for b in bullets)
    assert len(bullets) >= 5


def test_render_hearing_omnibus_uses_sub_bullets_keeps_metadata():
    long_title = (
        "Hearings to examine S.1674, to modify the boundary of Mammoth Cave National Park, "
        "S.2498, to authorize lease extensions in National Park units, "
        "S.2767, to authorize Fire safety grants, "
        "H.R.5254, to rename a post office"
    )
    html = render_hearing({
        "title": long_title,
        "committee": "Committee on Energy and Natural Resources",
        "chamber": "Senate",
        "scheduled_time": "10:00 AM",
        "location": "SD-366",
        "url": "https://www.congress.gov/committee-schedule",
        "level": "federal",
    })
    assert "Hearings to examine" in html
    assert "<ul>" in html
    assert "<li>S.1674" in html
    assert "<li>S.2498" in html
    assert "<li>S.2767" in html
    assert "<li>H.R.5254" in html
    assert "Committee: Committee on Energy and Natural Resources" in html
    assert "Time: 10:00 AM" in html
    assert "Location: SD-366" in html
    assert 'href="https://www.congress.gov/committee-schedule"' in html
    assert "View on Congress.gov" in html


def test_render_hearing_omnibus_state_titles_use_sub_bullets():
    long_title = (
        "Joint hearing to consider HB 1001, relating to veterans services funding, "
        "SB 220, relating to military family tax credits, "
        "HB 330, relating to National Guard benefits, "
        "SB 440, relating to firefighter training"
    )
    header, bullets = split_omnibus_hearing_title(long_title)
    assert "Joint hearing to consider" in header
    assert any("HB 1001" in b for b in bullets)
    assert any("SB 220" in b for b in bullets)

    html = render_hearing({
        "title": long_title,
        "committee": "Veterans Affairs",
        "state": "KS",
        "scheduled_time": "1:30 PM",
        "location": "Room 112-N",
        "url": "https://example.state.ks.us/hearing",
    })
    assert "<ul>" in html
    assert "HB 1001" in html
    assert "SB 440" in html
    assert "Committee: Veterans Affairs" in html
    assert "View details" in html
    assert 'href="https://example.state.ks.us/hearing"' in html
