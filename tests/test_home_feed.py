"""Tests for slim homepage feed generation."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.home_feed import (  # noqa: E402
    HOME_FEED_DAYS_DIRNAME,
    HOME_FEED_MAX_DAYS,
    build_day_feed,
    build_home_feed,
    collect_all_feed_dates,
    compute_bill_counts,
    select_recent_feed_dates,
    write_home_feed_artifacts,
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


def test_collect_all_feed_dates_includes_older_grouped_days():
    site_years = _year(
        {
            "2026-08-04": {"Federal": [{"title": "A"}]},
            "2026-08-02": {"Federal": [{"title": "B"}]},
            "2026-08-01": {"Federal": [{"title": "C"}]},
        }
    )
    dates = collect_all_feed_dates(site_years, {}, today="2026-08-04")
    assert dates == ["2026-08-04", "2026-08-02", "2026-08-01"]


def test_collect_all_feed_dates_limits_search_index_only_lookback():
    site_years = _year({"2026-08-04": {"Federal": [{"title": "A"}]}})
    search_index = {
        "bills": [
            {
                "bill_number": "HB 1",
                "title": "Recent CO",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2026-07-31T12:00:00",
            },
            {
                "bill_number": "HB 2",
                "title": "Old CO",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2025-01-01T12:00:00",
            },
        ]
    }
    dates = collect_all_feed_dates(
        site_years, search_index, today="2026-08-04", search_lookback_days=120
    )
    assert "2026-08-04" in dates
    assert "2026-07-31" in dates
    assert "2025-01-01" not in dates


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
    # 2026-01-01 is search-index-only and outside the lookback window.
    assert feed["available_dates"] == ["2026-08-04", "2026-08-03"]
    assert feed["stats"]["available_day_count"] == 2
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


def test_build_day_feed_is_single_day_and_injects_multi_state():
    site_years = _year(
        {
            "2026-08-04": {"Congress.gov API": [{"title": "A", "bill_number": "HR 1"}]},
            "2026-08-01": {"Congress.gov API": [{"title": "B", "bill_number": "HR 2"}]},
        }
    )
    search_index = {
        "bills": [
            {
                "bill_number": "HB 10",
                "title": "Colorado update",
                "state": "CO",
                "level": "state",
                "latest_action_date": "2026-08-01T15:00:00",
                "latest_action": "Introduced",
                "url": "https://example.com/co/hb10",
            }
        ]
    }
    day = build_day_feed(
        date="2026-08-01",
        site_years=site_years,
        search_index=search_index,
        veteran_impact_lookup={"CO|HB 10": {"level": "green"}},
    )
    assert day["home_feed_day"] is True
    assert day["date"] == "2026-08-01"
    assert set(day["years"]["2026"]["grouped"].keys()) == {"2026-08-01"}
    assert "State (Colorado)" in day["years"]["2026"]["grouped"]["2026-08-01"]
    assert "CO|HB 10" in day["veteran_impact"]["lookup"]


def test_write_home_feed_artifacts_writes_day_files_and_prunes_stale(tmp_path):
    site_years = _year(
        {
            "2026-08-04": {"Federal": [{"title": "A"}]},
            "2026-08-02": {"Federal": [{"title": "B"}]},
            "2026-08-01": {"Federal": [{"title": "C"}]},
        }
    )
    stale_dir = tmp_path / HOME_FEED_DAYS_DIRNAME
    stale_dir.mkdir()
    stale = stale_dir / "2020-01-01.json"
    stale.write_text("{}", encoding="utf-8")

    home_path, day_paths, payload = write_home_feed_artifacts(
        tmp_path,
        last_updated="2026-08-04T12:00:00",
        site_years=site_years,
        search_index={},
        today="2026-08-04",
    )
    assert home_path.is_file()
    assert payload["available_dates"] == ["2026-08-04", "2026-08-02", "2026-08-01"]
    assert len(day_paths) == 3
    assert not stale.exists()
    for date in payload["available_dates"]:
        day_file = tmp_path / HOME_FEED_DAYS_DIRNAME / f"{date}.json"
        assert day_file.is_file()
        data = json.loads(day_file.read_text(encoding="utf-8"))
        assert data["date"] == date
        assert data["home_feed_day"] is True


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


def test_r2_upload_list_includes_home_feed_and_day_glob():
    from processing.r2_sync import DOCS_UPLOAD_FILES, DOCS_UPLOAD_GLOBS

    assert "home_feed.json" in DOCS_UPLOAD_FILES
    assert "home_search_bills.json" in DOCS_UPLOAD_FILES
    assert "home_feed_days/*.json" in DOCS_UPLOAD_GLOBS
    assert "search_shards/*.json" in DOCS_UPLOAD_GLOBS


def test_veteran_legislation_page_is_in_nav_and_veterans_only():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "veterans.html").read_text(encoding="utf-8")
    shell = (root / "docs" / "shell.js").read_text(encoding="utf-8")
    assert 'data-veterans-only="true"' in html
    assert 'data-cw-page="veterans"' in html
    assert "veterans.html" in shell
    assert "Veteran Legislation" in shell
    assert "index.html" in html  # homepage still linked for full bill list


def test_veterans_page_blank_dates_and_fifty_item_pages():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "veterans.html").read_text(encoding="utf-8")
    script = (root / "docs" / "script.js").read_text(encoding="utf-8")
    from_input = re.search(r'<input type="date" id="search-date-from"[^>]*>', html)
    to_input = re.search(r'<input type="date" id="search-date-to"[^>]*>', html)
    assert from_input, "missing From date input"
    assert to_input, "missing To date input"
    assert "value=" not in from_input.group(0)
    assert "value=" not in to_input.group(0)
    assert "VETERANS_PAGE_FEED_ITEM_LIMIT = 50" in script
    assert "if (isVeteransOnlyPage()) return;" in script
    assert "loadVeteransHomeFeedItems" in script
    assert "usesVeteransItemFeed" in script


def test_loading_overlay_is_wired_for_search_and_first_paint():
    root = Path(__file__).resolve().parents[1]
    theme = (root / "docs" / "theme.css").read_text(encoding="utf-8")
    shell = (root / "docs" / "shell.js").read_text(encoding="utf-8")
    script = (root / "docs" / "script.js").read_text(encoding="utf-8")
    home = (root / "docs" / "index.html").read_text(encoding="utf-8")
    veterans = (root / "docs" / "veterans.html").read_text(encoding="utf-8")
    assert ".cw-loading-overlay" in theme
    assert ".cw-loading-overlay--open" in theme
    assert ".cw-loading-overlay[hidden]" in theme
    assert "@keyframes cw-spin" in theme
    assert "PolicyWatchLoading" in shell
    assert "setAttribute('hidden'" in shell
    assert "keepBusy" in script
    assert 'setContentBusy(true, "Searching…")' in script
    for html in (home, veterans):
        assert 'id="cw-loading-overlay"' in html
        assert "cw-loading-spinner" in html
        assert "cw-loading-overlay--open" in html
        assert 'class="cw-loading-overlay" hidden' in html


def test_write_home_feed_artifacts_writes_search_bills(tmp_path):
    site_years = _year({"2026-08-04": {"Federal": [{"title": "A"}]}})
    search_index = {
        "bills": [
            {
                "bill_number": "HB 10",
                "title": "Colorado update",
                "state": "CO",
                "level": "state",
                "latest_action": "Introduced",
                "latest_action_date": "2026-08-04T15:00:00",
                "url": "https://example.com/co/hb10",
                "summary": "x" * 400,
            }
        ]
    }
    home_path, day_paths, payload = write_home_feed_artifacts(
        tmp_path,
        last_updated="2026-08-04T12:00:00",
        site_years=site_years,
        search_index=search_index,
        today="2026-08-04",
    )
    assert home_path.is_file()
    assert payload["stats"]["home_search_bill_count"] == 1
    search_file = tmp_path / "home_search_bills.json"
    assert search_file.is_file()
    data = json.loads(search_file.read_text(encoding="utf-8"))
    assert data["home_search_bills"] is True
    assert len(data["bills"]) == 1
    assert data["bills"][0]["bill_number"] == "HB 10"
    assert len(data["bills"][0]["summary"]) <= 160
    assert len(day_paths) >= 1
    meta = json.loads((tmp_path / "search_shards" / "meta.json").read_text(encoding="utf-8"))
    assert meta["search_shards"] is True
    assert "CO" in meta["shards"]
    shard = json.loads((tmp_path / "search_shards" / "CO.json").read_text(encoding="utf-8"))
    assert shard["bills"][0]["n"] == "HB 10"
    assert shard["bills"][0]["t"] == "Colorado update"
