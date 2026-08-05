"""Tests for slim homepage feed generation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.home_feed import (  # noqa: E402
    HOME_FEED_MAX_DAYS,
    build_home_feed,
    compute_bill_counts,
    select_recent_feed_dates,
)


def _year(grouped):
    return {
        "2026": {
            "total_items": sum(len(i) for d in grouped.values() for i in d.values()),
            "pages": [],
            "grouped": grouped,
        }
    }


def test_select_recent_feed_dates_picks_two_most_recent_with_activity():
    site_years = _year(
        {
            "2026-08-04": {"Federal": [{"title": "A"}]},
            "2026-08-02": {"Federal": [{"title": "B"}]},
            "2026-08-01": {"Federal": [{"title": "C"}]},
        }
    )
    dates = select_recent_feed_dates(site_years, {}, max_days=2, today="2026-08-04")
    assert dates == ["2026-08-04", "2026-08-02"]


def test_select_recent_feed_dates_ignores_future_dates():
    site_years = _year(
        {
            "2026-12-08": {"Federal": [{"title": "Future"}]},
            "2026-08-03": {"Federal": [{"title": "Recent"}]},
            "2026-07-30": {"Federal": [{"title": "Older"}]},
        }
    )
    dates = select_recent_feed_dates(site_years, {}, max_days=2, today="2026-08-04")
    assert dates == ["2026-08-03", "2026-07-30"]


def test_select_recent_feed_dates_includes_search_index_only_days():
    site_years = _year({"2026-08-01": {"Federal": [{"title": "Old"}]}})
    search_index = {
        "bills": [
            {
                "bill_number": "HB 1",
                "title": "Recent CO",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2026-08-04T12:00:00",
                "latest_action": "Introduced",
                "url": "https://example.com/hb1",
            }
        ]
    }
    dates = select_recent_feed_dates(site_years, search_index, max_days=2, today="2026-08-04")
    assert dates[0] == "2026-08-04"
    assert "2026-08-01" in dates


def test_build_home_feed_excludes_full_search_index_and_injects_multi_state():
    site_years = _year(
        {
            "2026-08-04": {
                "Congress.gov API": [
                    {
                        "title": "Federal bill",
                        "bill_number": "HR 1",
                        "level": "federal",
                        "published": "2026-08-04T10:00:00",
                        "latest_action": "Passed House",
                        "item_type": "bill_update",
                        "action_type": "passed",
                    }
                ]
            },
            "2026-08-03": {
                "Congress.gov API": [
                    {
                        "title": "Older federal",
                        "bill_number": "HR 2",
                        "level": "federal",
                        "published": "2026-08-03T10:00:00",
                        "latest_action": "Introduced",
                        "item_type": "bill_update",
                    }
                ]
            },
        }
    )
    search_index = {
        "bills": [
            {
                "bill_number": "HB 10",
                "title": "Colorado update",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2026-08-04T15:00:00",
                "latest_action": "Referred to committee",
                "url": "https://example.com/co/hb10",
                "summary": "A bill",
                "classification": [],
                "ai_topics": ["veterans"],
            },
            {
                "bill_number": "HB 99",
                "title": "Old Colorado",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2026-01-01T15:00:00",
                "latest_action": "Introduced",
                "url": "https://example.com/co/hb99",
            },
            {
                "bill_number": "S 1",
                "title": "Federal indexed",
                "level": "federal",
                "latest_action_date": "2026-08-04T15:00:00",
            },
            {
                "bill_number": "HB 2",
                "title": "Kansas indexed",
                "state": "KS",
                "level": "state",
                "latest_action_date": "2026-08-04T15:00:00",
            },
        ]
    }

    feed = build_home_feed(
        last_updated="2026-08-04T12:00:00",
        site_years=site_years,
        search_index=search_index,
        states=[{"code": "co", "name": "Colorado"}],
        veteran_impact_lookup={
            "CO|HB 10": {"level": "green", "title": "Colorado update"},
            "CO|HB 99": {"level": "red", "title": "Old Colorado"},
        },
        kansas_vote_records={"HB 1": [{"motion": "Final"}]},
        max_days=HOME_FEED_MAX_DAYS,
        today="2026-08-04",
    )

    assert feed["home_feed"] is True
    assert feed["feed_window"]["dates"] == ["2026-08-04", "2026-08-03"]
    assert feed["search_index"]["bills"] == []
    assert feed["legislation"]["pages"] == []
    assert "CO|HB 10" in feed["veteran_impact"]["lookup"]
    assert "CO|HB 99" not in feed["veteran_impact"]["lookup"]

    grouped = feed["years"]["2026"]["grouped"]["2026-08-04"]
    assert "Congress.gov API" in grouped
    co_items = grouped.get("State (Colorado)") or []
    assert len(co_items) == 1
    assert co_items[0]["bill_number"] == "HB 10"
    assert co_items[0]["action_type"] == "referred"
    assert feed["stats"]["multi_state_injected"] == 1
    assert feed["bill_counts"]["CO"] == 2
    assert feed["bill_counts"]["Federal"] == 1


def test_compute_bill_counts():
    counts = compute_bill_counts(
        {
            "bills": [
                {"level": "federal"},
                {"state": "ks", "level": "state"},
                {"state": "CO", "level": "state"},
                {"state": "ZZ", "level": "state"},
            ]
        }
    )
    assert counts["Federal"] == 1
    assert counts["KS"] == 1
    assert counts["CO"] == 1
    assert "ZZ" not in counts


def test_r2_upload_list_includes_home_feed():
    from processing.r2_sync import DOCS_UPLOAD_FILES

    assert "home_feed.json" in DOCS_UPLOAD_FILES
