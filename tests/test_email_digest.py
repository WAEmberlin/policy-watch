"""Tests for email digest building."""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.email_digest import (
    build_digest_html,
    infer_item_state,
    is_within_window,
    item_recency_ts,
    partition_by_state,
    partition_hearings,
)


def test_item_recency_prefers_last_synced_at():
    now = datetime.now(timezone.utc)
    item = {
        "latest_action_date": "2026-01-01T00:00:00",
        "last_synced_at": now.isoformat(),
    }
    assert is_within_window(item, now, window_hours=6)


def test_item_recency_uses_ks_api_enriched_at_for_state_bills():
    now = datetime.now(timezone.utc)
    item = {
        "type": "state_legislation",
        "bill_number": "HB 100",
        "published": "2026-04-01T15:00:00+00:00",
        "ks_api_enriched_at": now.isoformat(),
    }
    assert is_within_window(item, now, window_hours=6)


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
