"""Tests for email digest building."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.email_digest import (
    build_digest_html,
    hearing_scheduled_date,
    infer_item_state,
    is_within_window,
    item_recency_ts,
    partition_by_state,
    partition_hearings,
    render_utah_hearing_update,
    split_state_items,
)


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
    hearing_day = datetime.now(timezone.utc).date() + timedelta(days=7)
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
