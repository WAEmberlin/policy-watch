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
    assert classify_action_type("To House Education") == "referred"
    assert classify_action_type("To House Agriculture and Natural Resources") == "referred"
    assert classify_action_type("To Judiciary") == "referred"
    assert classify_action_type("To Education then Finance") == "referred"
    assert classify_action_type("To the Governor") is None
    assert classify_action_type("Died in House Committee") == "died"
    assert classify_action_type("Withdrawn from calendar") == "withdrawn"
    assert classify_action_type("Roll call vote on passage") == "vote"
    assert classify_action_type("Presented to the President") == "presented"
    assert classify_action_type("Presented to President") == "presented"
    assert classify_action_type("Placed on the Union Calendar. Calendar No. 694.") == "calendar"
    assert classify_action_type("Received in the Senate and placed on the Legislative Calendar") == "calendar"
    assert classify_action_type("Placed on General Orders") == "calendar"
    assert classify_action_type("Read second and ordered to a third reading") == "calendar"
    assert classify_action_type("Read, rules suspended, read second and ordered to a third reading") == "calendar"
    assert classify_action_type("On 2nd reading, House Calendar") == "calendar"
    assert classify_action_type("Read third and passed to be engrossed") == "passed"
    assert classify_action_type("Placed on file") == "filed"
    assert classify_action_type("Hearing scheduled for 09/15/2026 from 01:00 PM-05:00 PM in A-2") == "scheduled"
    assert classify_action_type("Scheduled for hearing") == "scheduled"
    assert classify_action_type(
        "House: HB2036: Hearing: Thursday, March 12, 2026, 3:30 PM Room 346-S"
    ) == "scheduled"
    assert classify_action_type(
        "House: HB2615: Hearing: Tuesday, February 10, 2026, 1:30 PM Room 582-N, Action Code: misc_he_200"
    ) == "scheduled"
    assert classify_action_type(
        "House: HB2214: Hearing: Tuesday, February 3, 2026, 9:00 AM Room 281-N, "
        "Action Code: misc_he_200, Occurred: 01/28/2026 10:44:55AM"
    ) == "scheduled"
    assert classify_action_type("Subcommittee Hearings Held") == "heard"
    assert classify_action_type("Hearing canceled") is None
    assert classify_action_type("Text of an amendment, see S2957") == "amendment"
    assert classify_action_type("Text of a further amendment, offered by Mr. Walsh of Peabody") == "amendment"
    assert classify_action_type(
        "Resolution agreed to in Senate with an amendment and an amended preamble by Voice Vote. "
        "(text of amendment in the nature of a substitute: CR S7976)"
    ) == "passed"
    assert classify_action_type("Accompanied a study order, see H5596") == "study"
    assert classify_action_type(
        "Placed on Senate Legislative Calendar under General Orders. Calendar No. 499."
    ) == "calendar"
    assert classify_action_type(
        "Committee on Homeland Security and Governmental Affairs. "
        "Ordered to be reported with an amendment in the nature of a substitute favorably."
    ) == "reported"
    assert classify_action_type("Re-reported as committed") == "reported"
    assert classify_action_type(
        "Received in the Senate. Read twice. Placed on Senate Legislative Calendar "
        "under General Orders. Calendar No. 458."
    ) == "calendar"
    assert classify_action_type(
        "By Representative Stanley of Waltham, a petition (subject to Joint Rule 12) "
        "of Thomas M. Stanley that the Division of Capital Asset Management and Maintenance "
        "be authorized to"
    ) == "introduced"
    assert classify_action_type("Accompanied a new draft, see H5567") == "draft"
    assert classify_action_type("Act No. 38 of 2026") == "enacted"
    assert classify_action_type("Chapter 227, Acts, Regular Session, 2026") == "enacted"
    assert classify_action_type("Delivered to Secretary of State (G)") == "enacted"
    assert classify_action_type("Laid on the table (Pursuant to House Rule 71)") == "tabled"
    assert classify_action_type("Re-committed to Appropriations") == "referred"
    assert classify_action_type("Committee on Energy and Natural Resources Subcommittee on National Parks. Hearings held.") == "heard"
    assert classify_action_type(
        "House: HR6047: Enrolled on Monday, April 13, 2026, Action Code: ee_enrb_226, Occurred: 04/13/2026 10:36:11AM"
    ) == "enrolled"
    assert classify_action_type("Enrolled on Monday, April 13, 2026") == "enrolled"
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
    assert action_badge_label("presented") == "Presented"
    assert action_badge_label("calendar") == "On Calendar"
    assert action_badge_label("filed") == "On File"
    assert action_badge_label("scheduled") == "Scheduled"
    assert action_badge_label("amendment") == "Amendment"
    assert action_badge_label("reported") == "Reported"
    assert action_badge_label("study") == "Study Order"
    assert action_badge_label("draft") == "New Draft"
    assert action_badge_label("introduced") == "Introduced"
    assert action_badge_label("tabled") == "Tabled"
    assert action_badge_label("heard") == "Heard"
    assert action_badge_label("enrolled") == "Enrolled"
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
    assert events[0]["link"] == "https://www.congress.gov/votes/house/119-1/1"
