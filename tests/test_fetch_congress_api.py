"""Tests for Congress.gov API fetch and roll-call vote enrichment."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_congress_api import (  # noqa: E402
    _extract_votes_from_actions,
    _parse_senate_tally_from_text,
    _sum_house_vote_totals,
    build_house_vote_public_url,
    deduplicate_bills,
    enrich_bills_with_votes_and_actions,
    fetch_bill_actions,
    fetch_house_vote_detail,
    fetch_recent_house_votes,
    load_existing_congress_votes,
    merge_congress_vote_feeds,
)

MOCK_ACTIONS_PAGE_1 = {
    "actions": [
        {
            "actionDate": "2025-09-08",
            "actionTime": "18:56:43",
            "recordedVotes": [
                {
                    "chamber": "House",
                    "congress": 119,
                    "date": "2025-09-08T22:56:43Z",
                    "rollNumber": 240,
                    "sessionNumber": 1,
                }
            ],
            "text": "On motion to suspend the rules and pass the bill Agreed to by the Yeas and Nays: (2/3 required): 397 - 1 (Roll no. 240).",
            "type": "Floor",
        }
    ],
    "pagination": {"count": 2},
}

MOCK_ACTIONS_PAGE_2 = {
    "actions": [
        {
            "actionDate": "2025-09-01",
            "text": "Introduced in House",
            "type": "IntroReferral",
        }
    ],
    "pagination": {"count": 2},
}

MOCK_HOUSE_VOTE_DETAIL = {
    "houseRollCallVote": {
        "congress": 119,
        "rollCallNumber": 240,
        "sessionNumber": 1,
        "result": "Passed",
        "startDate": "2025-09-08T18:56:00-04:00",
        "voteQuestion": "On Motion to Suspend the Rules and Pass",
        "votePartyTotal": [
            {"yeaTotal": 202, "nayTotal": 0},
            {"yeaTotal": 195, "nayTotal": 1},
        ],
    }
}

MOCK_HOUSE_VOTE_LIST = {
    "houseRollCallVotes": [
        {
            "congress": 119,
            "rollCallNumber": 240,
            "sessionNumber": 1,
            "legislationType": "HR",
            "legislationNumber": "3424",
            "result": "Passed",
            "startDate": "2025-09-08T18:56:00-04:00",
        }
    ],
    "pagination": {"count": 1},
}

SENATE_ACTION_TEXT = (
    "Passed Senate without amendment by Yea-Nay Vote. 79 - 19. Record Vote Number: 71."
)


def test_parse_senate_tally_from_text():
    yeas, nays, roll = _parse_senate_tally_from_text(SENATE_ACTION_TEXT)
    assert yeas == 79
    assert nays == 19
    assert roll == 71


def test_sum_house_vote_totals():
    yeas, nays = _sum_house_vote_totals([
        {"yeaTotal": 202, "nayTotal": 0},
        {"yeaTotal": 195, "nayTotal": 1},
    ])
    assert yeas == 397
    assert nays == 1


def test_build_house_vote_public_url():
    url = build_house_vote_public_url(119, 1, 240)
    assert url == "https://www.congress.gov/roll-call-vote/119th-congress/1st-session/house/240"


@patch("processing.fetch_congress_api._congress_api_get")
def test_fetch_bill_actions_paginates(mock_get):
    mock_get.side_effect = [MOCK_ACTIONS_PAGE_1, MOCK_ACTIONS_PAGE_2]
    actions = fetch_bill_actions("key", 119, "hr", "3424")
    assert len(actions) == 2
    assert actions[0]["recordedVotes"][0]["rollNumber"] == 240
    assert mock_get.call_count == 2


@patch("processing.fetch_congress_api.fetch_house_vote_detail")
@patch("processing.fetch_congress_api._congress_api_get")
def test_fetch_recent_house_votes(mock_get, mock_detail):
    mock_get.return_value = MOCK_HOUSE_VOTE_LIST
    mock_detail.return_value = MOCK_HOUSE_VOTE_DETAIL["houseRollCallVote"]

    votes = fetch_recent_house_votes("key", 119, limit=1)
    assert len(votes) == 1
    assert votes[0]["bill_type"] == "HR"
    assert votes[0]["bill_number"] == "3424"
    assert votes[0]["yeas"] == 397
    assert votes[0]["nays"] == 1
    assert votes[0]["tally_text"] == "Passed 397–1"
    assert votes[0]["chamber"] == "House"


@patch("processing.fetch_congress_api._congress_api_get")
def test_fetch_house_vote_detail(mock_get):
    mock_get.return_value = MOCK_HOUSE_VOTE_DETAIL
    detail = fetch_house_vote_detail("key", 119, 1, 240)
    assert detail["rollCallNumber"] == 240
    assert detail["voteQuestion"] == "On Motion to Suspend the Rules and Pass"


@patch("processing.fetch_congress_api.fetch_house_vote_detail")
def test_extract_votes_from_actions_house(mock_detail):
    mock_detail.return_value = MOCK_HOUSE_VOTE_DETAIL["houseRollCallVote"]
    bill = {"bill_type": "HR", "bill_number": "3424", "congress": 119}
    actions = [{"text": "vote action", "actionDate": "2025-09-08", "recordedVotes": [
        {"chamber": "House", "congress": 119, "rollNumber": 240, "sessionNumber": 1}
    ]}]

    bill_votes, feed_votes = _extract_votes_from_actions("key", bill, actions)
    assert len(bill_votes) == 1
    assert bill_votes[0]["yeas"] == 397
    assert feed_votes[0]["motion"] == "On Motion to Suspend the Rules and Pass"


def test_extract_votes_from_actions_senate_text():
    bill = {"bill_type": "S", "bill_number": "1", "congress": 119}
    actions = [{"text": SENATE_ACTION_TEXT, "actionDate": "2025-08-01"}]

    bill_votes, feed_votes = _extract_votes_from_actions("key", bill, actions)
    assert len(bill_votes) == 1
    assert bill_votes[0]["chamber"] == "Senate"
    assert bill_votes[0]["yeas"] == 79
    assert bill_votes[0]["nays"] == 19
    assert feed_votes[0]["tally_text"] == "Passed 79–19"


def test_deduplicate_preserves_enriched_votes():
    existing = [{
        "bill_type": "HR",
        "bill_number": "100",
        "latest_action_date": "2026-06-01T00:00:00",
        "votes": [{"rollNumber": 10, "yeas": 220, "nays": 210}],
        "actions": [{"text": "Passed"}],
        "official_title": "Existing Title",
    }]
    new_bills = [{
        "bill_type": "HR",
        "bill_number": "100",
        "latest_action_date": "2026-07-01T00:00:00",
        "votes": [],
        "actions": [],
        "latest_action": "Updated action",
    }]

    merged = deduplicate_bills(new_bills, existing)
    bill = merged[0]
    assert bill["latest_action"] == "Updated action"
    assert bill["official_title"] == "Existing Title"
    assert bill["votes"][0]["yeas"] == 220
    assert bill["actions"][0]["text"] == "Passed"


@patch("processing.fetch_congress_api.fetch_bill_actions")
@patch("processing.fetch_congress_api.fetch_house_vote_detail")
def test_enrich_bills_with_votes_and_actions(mock_detail, mock_actions):
    # Keep inside the 30-day enrich window regardless of when CI runs.
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    recent_iso = recent.strftime("%Y-%m-%dT%H:%M:%S")
    recent_date = recent.strftime("%Y-%m-%d")

    mock_actions.return_value = [{
        "text": "House vote",
        "actionDate": recent_date,
        "recordedVotes": [{"chamber": "House", "congress": 119, "rollNumber": 5, "sessionNumber": 1}],
    }]
    mock_detail.return_value = {
        "result": "Passed",
        "voteQuestion": "On Passage",
        "votePartyTotal": [{"yeaTotal": 220, "nayTotal": 0}, {"yeaTotal": 0, "nayTotal": 210}],
    }

    bills = [{
        "bill_type": "HR",
        "bill_number": "123",
        "congress": 119,
        "latest_action_date": recent_iso,
    }]
    updated, feed = enrich_bills_with_votes_and_actions("key", bills, max_enrich=10)

    assert len(updated[0]["actions"]) == 1
    assert updated[0]["votes"][0]["yeas"] == 220
    assert updated[0]["votes"][0]["nays"] == 210
    assert feed[0]["bill_number"] == "123"
    assert feed[0]["tally_text"] == "Passed 220–210"


def test_merge_congress_vote_feeds_deduplicates():
    feed_a = [{
        "congress": 119, "chamber": "House", "session": 1, "roll_number": 1,
        "bill_type": "HR", "bill_number": "1", "date": "2026-07-01",
    }]
    feed_b = [{
        "congress": 119, "chamber": "House", "session": 1, "roll_number": 1,
        "bill_type": "HR", "bill_number": "1", "date": "2026-07-01", "yeas": 220,
    }]
    merged = merge_congress_vote_feeds(feed_a, feed_b)
    assert len(merged) == 1
    assert merged[0]["yeas"] == 220


def test_load_existing_congress_votes(tmp_path, monkeypatch):
    from processing import fetch_congress_api as mod

    votes_path = tmp_path / "congress_votes.json"
    votes_path.write_text('[{"bill_type": "HR", "bill_number": "1"}]', encoding="utf-8")
    monkeypatch.setattr(mod, "VOTES_FILE", votes_path)

    loaded = mod.load_existing_congress_votes()
    assert len(loaded) == 1
    assert loaded[0]["bill_number"] == "1"


def test_parse_bill_refs_from_hearing_title():
    from processing.fetch_congress_api import parse_bill_refs_from_hearing

    refs = parse_bill_refs_from_hearing({
        "title": "H.R. 9237 – Take Care of America's Veterans Act; H.R. 1181 – Privacy Act",
        "bill": "",
    })
    numbers = {num for _type, num in refs}
    assert "9237" in numbers
    assert "1181" in numbers


def test_parse_bill_refs_from_hearing_bill_field():
    from processing.fetch_congress_api import parse_bill_refs_from_hearing

    refs = parse_bill_refs_from_hearing({
        "title": "",
        "bill": "HR 9022, HR 8595, HR 1181, HR 9237",
    })
    assert ("HR", "9237") in refs
