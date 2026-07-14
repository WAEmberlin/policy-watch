"""Tests for bill action classification and vote feed helpers."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.bill_action_utils import (  # noqa: E402
    ACTION_BADGES,
    action_badge_label,
    build_vote_feed_events,
    classify_action_type,
    classify_vote_outcome,
    enrich_bill_feed_item,
    format_bill_display_number,
    format_vote_tally,
    inject_vote_events_into_grouped,
    is_bill_feed_item,
)


def test_classify_enacted_from_signed_keywords():
    assert classify_action_type("Signed by Governor") == "enacted"
    assert classify_action_type("Became Public Law 119-42") == "enacted"


def test_classify_vetoed_before_passed():
    assert classify_action_type("No motion to reconsider vetoed bill; Veto sustained") == "vetoed"


def test_classify_passed_adopted_referred_died():
    assert classify_action_type("Final Action - Passed;") == "passed"
    assert classify_action_type("Conference Committee Report was adopted;") == "passed"
    assert classify_action_type("Referred to Committee on Ways and Means") == "referred"
    assert classify_action_type("Died in House Committee") == "died"
    assert classify_action_type("Withdrawn from calendar") == "withdrawn"
    assert classify_action_type("Roll call vote on passage") == "vote"
    assert classify_action_type("") is None


def test_format_vote_tally_passed_and_failed():
    assert format_vote_tally("Passed", 27, 13) == "Passed 27–13"
    assert format_vote_tally("fail", None, None, yes_count=39, no_count=73) == "Failed 39–73"
    assert format_vote_tally("", None, None) == "Vote"


def test_classify_vote_outcome_from_counts():
    assert classify_vote_outcome("pass", 50, 20) == "passed"
    assert classify_vote_outcome("", 30, 40) == "failed"
    assert classify_vote_outcome("", None, None) == "vote"


def test_action_badge_label_and_config():
    assert action_badge_label("passed") == "Passed"
    assert action_badge_label("unknown_type") == "Unknown Type"
    assert ACTION_BADGES["enacted"]["class"].startswith("bg-")


def test_enrich_bill_feed_item_sets_fields():
    item = {"latest_action": "Signed by Governor", "title": "HB 1"}
    enriched = enrich_bill_feed_item(item)
    assert enriched["item_type"] == "bill_update"
    assert enriched["action_type"] == "enacted"


def test_is_bill_feed_item_skips_hearings():
    assert is_bill_feed_item({"type": "state_hearing", "title": "Committee"}) is False
    assert is_bill_feed_item({"bill_number": "HB 1", "latest_action": "Introduced"}) is True


def test_format_bill_display_number():
    assert format_bill_display_number("HB2312") == "HB 2312"
    assert format_bill_display_number("HB 2312") == "HB 2312"


def test_build_vote_feed_events_from_fixture(tmp_path):
    kansas_dir = tmp_path / "data" / "kansas"
    kansas_dir.mkdir(parents=True)
    (kansas_dir / "vote_records.json").write_text(
        json.dumps(
            {
                "HB2312": [
                    {
                        "bill_number": "HB2312",
                        "result": "Final Action - Passed;",
                        "date": "2026-07-01T15:00:00+00:00",
                        "tally": {"yea": 27, "nay": 13},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "data" / "normalized").mkdir(parents=True)
    (tmp_path / "data" / "normalized" / "votes.json").write_text("[]", encoding="utf-8")

    events = build_vote_feed_events(tmp_path)
    assert len(events) == 1
    event = events[0]
    assert event["item_type"] == "vote_event"
    assert event["bill_number"] == "HB 2312"
    assert event["vote_tally"] == "Passed 27–13"
    assert event["source"] == "Kansas Legislature"
    assert event["state"] == "KS"


def test_inject_vote_events_into_grouped():
    grouped = {}
    event = {
        "item_type": "vote_event",
        "published": "2026-07-01T15:00:00+00:00",
        "source": "Kansas Legislature",
        "title": "HB 2312: Final Action",
    }
    added = inject_vote_events_into_grouped(grouped, [event])
    assert added == 1
    assert grouped["2026"]["2026-07-01"]["Kansas Legislature"][0]["title"] == "HB 2312: Final Action"


def test_build_vote_feed_events_congress_bill_number(tmp_path):
    output_dir = tmp_path / "src" / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "congress_votes.json").write_text(
        json.dumps([{
            "bill_type": "HR",
            "bill_number": "123",
            "congress": 119,
            "date": "2026-07-01",
            "chamber": "House",
            "result": "Passed",
            "yeas": 220,
            "nays": 210,
            "tally_text": "Passed 220–210",
            "motion": "On Passage",
            "url": "https://www.congress.gov/roll-call-vote/119th-congress/1st-session/house/1",
        }]),
        encoding="utf-8",
    )
    (tmp_path / "data" / "kansas").mkdir(parents=True)
    (tmp_path / "data" / "kansas" / "vote_records.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "normalized").mkdir(parents=True)
    (tmp_path / "data" / "normalized" / "votes.json").write_text("[]", encoding="utf-8")

    events = build_vote_feed_events(tmp_path)
    assert len(events) == 1
    assert events[0]["bill_number"] == "HR 123"
    assert events[0]["source"] == "Congress.gov"
