"""Tests for email digest building."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing import email_digest
from processing.email_digest import (
    DIGEST_TITLE_MAX_LEN,
    VETERAN_BILL_NUMBER_STYLES,
    build_digest_html,
    format_digest_title,
    hearing_scheduled_date,
    infer_item_state,
    is_hearing_within_lookahead,
    is_within_window,
    item_recency_ts,
    iter_home_feed_items,
    load_digest_config,
    load_recent_items,
    load_state_names,
    partition_by_state,
    partition_hearings,
    render_hearing,
    render_item,
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
    assert "Kansas PolicyWatch" in html
    assert "Kansas PolicyWatch" in subject or "Kansas" in subject
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
    assert "All States" in subject or "PolicyWatch" in subject


def test_federal_only_digest():
    items = {
        "KS": [{"title": "KS", "link": "a", "published": "2026-01-01"}],
        "FEDERAL": [{"title": "HR 1", "link": "c", "published": "2026-01-01", "level": "federal"}],
    }
    html, subject, total = build_digest_html(
        "federal", items, {"FEDERAL": []}, {"KS": "Kansas"}
    )
    assert "Federal PolicyWatch" in html
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


def test_email_digests_cover_all_enabled_states():
    digest_ids = {d["id"] for d in load_digest_config()["digests"]}
    for code in load_state_names():
        assert code.lower() in digest_ids, f"missing digest for enabled state {code}"
    assert "federal" in digest_ids
    assert "all" in digest_ids
    assert "federal_vets" in digest_ids
    assert "all_vets" in digest_ids
    vets_meta = {d["id"]: d for d in load_digest_config()["digests"]}
    assert vets_meta["federal_vets"].get("veterans_only") is True
    assert vets_meta["all_vets"].get("veterans_only") is True
    for code in load_state_names():
        assert f"{code.lower()}_vets" in digest_ids, f"missing veteran digest for {code}"


def test_veteran_section_at_top_and_not_repeated():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "source": "Kansas Legislature",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            },
            {
                "title": "HB 42: Sales tax exemption for farm equipment",
                "summary": "Exempts certain farm machinery from state sales tax.",
                "source": "Kansas Legislature",
                "link": "https://example.com/hb42",
                "bill_number": "HB 42",
                "state": "KS",
                "published": "2026-03-15T11:00:00",
            },
        ],
        "FEDERAL": [
            {
                "title": "H.R. 9003: Take Care of America's Veterans Act",
                "summary": "Appropriations for veterans affairs healthcare.",
                "source": "Congress.gov API",
                "link": "https://example.com/hr9003",
                "bill_number": "H.R. 9003",
                "level": "federal",
                "published": "2026-03-15T09:00:00",
            },
        ],
    }
    html, _, total = build_digest_html(
        "ks", items, {"KS": [], "FEDERAL": []}, {"KS": "Kansas"}
    )
    assert total == 3
    assert "Veteran Legislation" in html
    assert html.index("Veteran Legislation") < html.index("Kansas — Updates")
    assert html.index("Veteran Legislation") < html.index("Federal — Updates")

    veteran_block = html[: html.index("Kansas — Updates")]
    rest = html[html.index("Kansas — Updates"):]
    assert "Veteran housing assistance" in veteran_block
    assert "Take Care of America's Veterans Act" in veteran_block
    assert "Veteran housing assistance" not in rest
    assert "Take Care of America's Veterans Act" not in rest
    assert "Sales tax exemption for farm equipment" in rest


def test_veteran_only_federal_digest_excludes_other_bills():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            }
        ],
        "FEDERAL": [
            {
                "title": "H.R. 9003: Take Care of America's Veterans Act",
                "summary": "Appropriations for veterans affairs healthcare.",
                "link": "https://example.com/hr9003",
                "bill_number": "H.R. 9003",
                "level": "federal",
                "published": "2026-03-15T09:00:00",
            },
            {
                "title": "HR 1: Tax reform",
                "link": "https://example.com/hr1",
                "bill_number": "HR 1",
                "level": "federal",
                "published": "2026-03-15T08:00:00",
            },
        ],
    }
    html, subject, total = build_digest_html(
        "federal_vets", items, {"FEDERAL": [{"title": "Armed Services hearing"}]}, {"KS": "Kansas"}
    )
    assert total == 1
    assert "Federal Veteran PolicyWatch" in html
    assert "Take Care of America's Veterans Act" in html
    assert "Veteran housing assistance" not in html
    assert "Tax reform" not in html
    assert "Armed Services hearing" not in html
    assert "Federal — Updates" not in html
    assert "1 update" in subject


def test_veteran_only_all_states_digest_excludes_non_veteran_and_hearings():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            },
            {
                "title": "HB 42: Sales tax exemption for farm equipment",
                "link": "https://example.com/hb42",
                "bill_number": "HB 42",
                "state": "KS",
                "published": "2026-03-15T11:00:00",
            },
        ],
        "FEDERAL": [
            {
                "title": "H.R. 9003: Take Care of America's Veterans Act",
                "summary": "Appropriations for veterans affairs healthcare.",
                "link": "https://example.com/hr9003",
                "bill_number": "H.R. 9003",
                "level": "federal",
                "published": "2026-03-15T09:00:00",
            },
        ],
    }
    html, subject, total = build_digest_html(
        "all_vets",
        items,
        {"KS": [{"title": "Tax committee"}], "FEDERAL": []},
        {"KS": "Kansas"},
    )
    assert total == 2
    assert "Veteran PolicyWatch" in subject or "Veteran Legislation" in html
    assert "Veteran housing assistance" in html
    assert "Take Care of America's Veterans Act" in html
    assert "Sales tax exemption" not in html
    assert "Tax committee" not in html
    assert "Kansas — Updates" not in html
    assert html.index("Kansas") < html.index("Federal")


def test_veteran_only_state_digest_is_that_state_only():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            },
            {
                "title": "HB 42: Sales tax exemption for farm equipment",
                "link": "https://example.com/hb42",
                "bill_number": "HB 42",
                "state": "KS",
                "published": "2026-03-15T11:00:00",
            },
        ],
        "MA": [
            {
                "title": "H 1: Veteran pension update",
                "link": "https://example.com/h1",
                "bill_number": "H 1",
                "state": "MA",
                "published": "2026-03-15T10:00:00",
            }
        ],
        "FEDERAL": [
            {
                "title": "H.R. 9003: Take Care of America's Veterans Act",
                "summary": "Appropriations for veterans affairs healthcare.",
                "link": "https://example.com/hr9003",
                "bill_number": "H.R. 9003",
                "level": "federal",
                "published": "2026-03-15T09:00:00",
            },
        ],
    }
    html, subject, total = build_digest_html(
        "ks_vets", items, {"KS": [], "FEDERAL": []}, {"KS": "Kansas", "MA": "Massachusetts"}
    )
    assert total == 1
    assert "Kansas Veteran PolicyWatch" in html
    assert "Veteran housing assistance" in html
    assert "Sales tax exemption" not in html
    assert "Veteran pension update" not in html
    assert "Take Care of America's Veterans Act" not in html
    assert "1 update" in subject


def test_no_veteran_section_without_veteran_bills():
    items = {
        "KS": [{"title": "KS Tax Bill", "link": "http://ks", "published": "2026-01-01"}],
        "FEDERAL": [
            {
                "title": "HR 1",
                "link": "http://congress",
                "published": "2026-01-01",
                "level": "federal",
            }
        ],
    }
    html, _, _ = build_digest_html(
        "ks", items, {"KS": [], "FEDERAL": []}, {"KS": "Kansas"}
    )
    assert "Veteran Legislation" not in html


def test_veteran_bill_numbers_use_site_impact_colors():
    red_html = render_item({
        "title": "HB 9001: Veteran housing assistance",
        "bill_number": "HB 9001",
        "link": "https://example.com/hb9001",
        "veteran_impact": {"level": "red"},
    })
    yellow_html = render_item({
        "title": "SB 9002: Establish a veterans court diversion program",
        "bill_number": "SB 9002",
        "link": "https://example.com/sb9002",
        "veteran_impact": {"level": "yellow"},
    })
    green_html = render_item({
        "title": "HR 9004: Honoring Post-9/11 Veterans memorial resolution",
        "bill_number": "HR 9004",
        "link": "https://example.com/hr9004",
        "veteran_impact": {"level": "green"},
    })
    assert VETERAN_BILL_NUMBER_STYLES["red"] in red_html
    assert "#fee2e2" in red_html and "#7f1d1d" in red_html
    assert VETERAN_BILL_NUMBER_STYLES["yellow"] in yellow_html
    assert "#fef3c7" in yellow_html and "#78350f" in yellow_html
    assert VETERAN_BILL_NUMBER_STYLES["green"] in green_html
    assert "#dcfce7" in green_html and "#14532d" in green_html
    assert "<span style=" in red_html


def test_classified_veteran_bill_number_is_colored_in_digest():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "source": "Kansas Legislature",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            }
        ],
        "FEDERAL": [],
    }
    html, _, _ = build_digest_html("ks", items, {"KS": [], "FEDERAL": []}, {"KS": "Kansas"})
    assert "Veteran Legislation" in html
    assert "#fee2e2" in html
    assert "HB 9001" in html


def test_all_digest_puts_veteran_section_first():
    items = {
        "KS": [
            {
                "title": "HB 9001: Veteran housing assistance",
                "summary": "Expands homeless veteran housing.",
                "link": "https://example.com/hb9001",
                "bill_number": "HB 9001",
                "state": "KS",
                "published": "2026-03-15T10:00:00",
            }
        ],
        "CO": [{"title": "CO Tax", "link": "b", "published": "2026-01-01"}],
        "FEDERAL": [{"title": "HR", "link": "c", "published": "2026-01-01", "level": "federal"}],
    }
    html, _, _ = build_digest_html(
        "all",
        items,
        {"KS": [], "CO": [], "FEDERAL": []},
        {"KS": "Kansas", "CO": "Colorado"},
    )
    assert html.index("Veteran Legislation") < html.index("<h2>Colorado</h2>")
    assert html.index("Veteran Legislation") < html.index("<h2>Kansas</h2>")
    assert html.index("Veteran Legislation") < html.index("Federal (U.S. Congress)")
    rest = html[html.index("<h2>Kansas</h2>"):]
    assert "Veteran housing assistance" not in rest


def test_utah_hearing_stays_out_of_veteran_section():
    hearing_day = datetime.now(timezone.utc).date() + timedelta(days=1)
    notice_date = hearing_day.strftime("%A, %B %d, %Y")
    items = {
        "UT": [
            {
                "title": "HB 50: Veteran housing - House Floor",
                "summary": "Homeless veteran housing hearing notice.",
                "link": "http://le.utah.gov/hearing",
                "published": "2026-01-01",
                "state": "UT",
                "feed": "utah_committee_rss",
                "bill_number": "HB 50",
                "notice_date": notice_date,
                "notice_time": "4:00 p.m.",
            }
        ],
        "FEDERAL": [],
    }
    html, _, total = build_digest_html("ut", items, {"UT": []}, {"UT": "Utah"})
    assert total == 1
    assert "Veteran Legislation" not in html
    assert "Utah — Hearing Updates" in html
    assert "Veteran housing" in html


def test_email_workflow_restores_openstates_bills_from_r2():
    workflow = (ROOT / ".github" / "workflows" / "daily_email.yml").read_text(encoding="utf-8")
    assert "boto3" in workflow
    assert "r2_sync.py download data/normalized/bills.json" in workflow
    assert "R2_ACCOUNT_ID" in workflow
    assert "R2_BUCKET_NAME" in workflow
    assert "continue-on-error: true" in workflow
    assert "--ops-alert" in workflow
    assert "wesley.a.emberlin@gmail.com" in workflow
    assert "EMAIL_OPS_ALERT" in workflow
    assert "R2 pipeline restore skipped/failed, continuing" not in workflow


def test_veteran_digest_recipients_come_from_json(monkeypatch):
    from processing.send_email import parse_recipient_config

    monkeypatch.setenv(
        "EMAIL_DIGEST_RECIPIENTS",
        '{"federal":["congress@example.com"],"all":["all@example.com"],'
        '"federal_vets":["fed-vets@example.com"],"all_vets":["all-vets@example.com"],'
        '"ks_vets":["kansas-vets@example.com"]}',
    )
    monkeypatch.delenv("EMAIL_RECIPIENTS_FEDERAL_VETS", raising=False)
    monkeypatch.delenv("EMAIL_RECIPIENTS_ALL_VETS", raising=False)
    monkeypatch.delenv("EMAIL_RECIPIENTS_KS_VETS", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    recipients = parse_recipient_config()
    assert recipients["federal"] == ["congress@example.com", "wesley.a.emberlin@gmail.com"]
    assert recipients["federal_vets"] == ["fed-vets@example.com", "wesley.a.emberlin@gmail.com"]
    assert recipients["all_vets"] == ["all-vets@example.com", "wesley.a.emberlin@gmail.com"]
    assert recipients["ks_vets"] == ["kansas-vets@example.com", "wesley.a.emberlin@gmail.com"]
    assert recipients["ma_vets"] == ["wesley.a.emberlin@gmail.com"]


def test_veteran_digest_recipient_override(monkeypatch):
    from processing.send_email import parse_recipient_config

    monkeypatch.setenv(
        "EMAIL_DIGEST_RECIPIENTS",
        '{"federal":["congress@example.com"],"federal_vets":["vets@example.com"]}',
    )
    monkeypatch.delenv("EMAIL_RECIPIENTS_FEDERAL_VETS", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    recipients = parse_recipient_config()
    assert recipients["federal_vets"] == ["vets@example.com", "wesley.a.emberlin@gmail.com"]


def test_operator_email_is_on_every_digest(monkeypatch):
    from processing.send_email import DEFAULT_DIGEST_RECIPIENT, parse_recipient_config

    monkeypatch.setenv("EMAIL_DIGEST_RECIPIENTS", '{"federal":["congress@example.com"]}')
    monkeypatch.delenv("EMAIL_TO", raising=False)
    recipients = parse_recipient_config()
    assert DEFAULT_DIGEST_RECIPIENT == "wesley.a.emberlin@gmail.com"
    assert recipients
    for digest_id, addrs in recipients.items():
        assert DEFAULT_DIGEST_RECIPIENT in addrs, digest_id


def test_ops_alert_defaults_to_wesley(monkeypatch, capsys):
    from processing.send_email import (
        DEFAULT_DIGEST_RECIPIENT,
        DEFAULT_OPS_ALERT,
        ops_alert_recipients,
        send_ops_alert,
    )

    monkeypatch.delenv("EMAIL_OPS_ALERT", raising=False)
    assert DEFAULT_OPS_ALERT == DEFAULT_DIGEST_RECIPIENT == "wesley.a.emberlin@gmail.com"
    assert ops_alert_recipients() == ["wesley.a.emberlin@gmail.com"]
    send_ops_alert("restore failed in test", dry_run=True)
    captured = capsys.readouterr().out
    assert "wesley.a.emberlin@gmail.com" in captured
    assert "restore failed in test" in captured


def test_iter_home_feed_items_flattens_state_updates():
    items = iter_home_feed_items({
        "years": {
            "2026": {
                "grouped": {
                    "2026-09-17": {
                        "State (Massachusetts)": [
                            {
                                "title": "H 5507: Fire district",
                                "bill_number": "H 5507",
                                "state": "MA",
                                "link": "https://example.com/h5507",
                            }
                        ],
                        "State (Iowa)": [
                            {
                                "title": "SJR 11: Constitutional amendment",
                                "bill_number": "SJR 11",
                                "state": "IA",
                                "published": "2026-09-17",
                            }
                        ],
                    }
                }
            }
        }
    })
    assert [item.get("state") for item in items] == ["MA", "IA"]
    assert items[0]["published"] == "2026-09-17"


def test_load_recent_items_includes_home_feed_when_bills_json_lacks_states(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    home_path = tmp_path / "home_feed.json"
    home_path.write_text(json.dumps({
        "years": {
            str(now.year): {
                "grouped": {
                    now.date().isoformat(): {
                        "State (Massachusetts)": [{
                            "title": "H 1: Test MA bill",
                            "bill_number": "H 1",
                            "state": "MA",
                            "level": "state",
                            "link": "https://example.com/ma-h1",
                            "published": now.isoformat(),
                            "latest_action_date": now.isoformat(),
                        }],
                        "State (Missouri)": [{
                            "title": "HR 2: Veto session",
                            "bill_number": "HR 2",
                            "state": "MO",
                            "level": "state",
                            "link": "https://example.com/mo-hr2",
                            "published": now.isoformat(),
                            "latest_action_date": now.isoformat(),
                        }],
                    }
                }
            }
        }
    }), encoding="utf-8")
    (tmp_path / "bills.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(email_digest, "HOME_FEED_FILE", home_path)
    monkeypatch.setattr(email_digest, "NORMALIZED_BILLS_FILE", tmp_path / "bills.json")
    monkeypatch.setattr(email_digest, "SEARCH_INDEX_FILE", tmp_path / "missing_search.json")
    monkeypatch.setattr(email_digest, "HISTORY_FILE", tmp_path / "missing_history.json")
    monkeypatch.setattr(email_digest, "LEGISLATION_FILE", tmp_path / "missing_leg.json")

    items = load_recent_items(window_hours=24)
    states = {item.get("state") for item in items}
    assert states == {"MA", "MO"}


def test_load_recent_items_uses_search_index_when_bills_json_missing(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    search_path = tmp_path / "search_index.json"
    search_path.write_text(json.dumps({
        "bills": [{
            "title": "Medal of Honor Access and Liaison Act",
            "bill_number": "SJR 11",
            "state": "IA",
            "level": "state",
            "url": "https://example.com/ia-sjr11",
            "latest_action_date": now.isoformat(),
            "latest_action": "Introduced",
        }]
    }), encoding="utf-8")
    monkeypatch.setattr(email_digest, "NORMALIZED_BILLS_FILE", tmp_path / "missing_bills.json")
    monkeypatch.setattr(email_digest, "SEARCH_INDEX_FILE", search_path)
    monkeypatch.setattr(email_digest, "HOME_FEED_FILE", tmp_path / "missing_home.json")
    monkeypatch.setattr(email_digest, "HISTORY_FILE", tmp_path / "missing_history.json")
    monkeypatch.setattr(email_digest, "LEGISLATION_FILE", tmp_path / "missing_leg.json")

    items = load_recent_items(window_hours=24)
    assert len(items) == 1
    assert items[0]["state"] == "IA"
    assert items[0]["bill_number"] == "SJR 11"
