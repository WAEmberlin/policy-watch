"""Tests for Kansas roll-call vote normalization."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.kansas_votes import (  # noqa: E402
    KANSAS_BIENNIUM,
    member_profile_url,
    merge_vote_record,
    normalize_member_list,
    normalize_vote_detail,
    normalize_vote_summary,
)


def test_member_profile_url():
    assert member_profile_url("12345") == (
        f"https://www.kslegislature.gov/{KANSAS_BIENNIUM}/members/12345/"
    )
    assert member_profile_url("") == ""
    assert member_profile_url(None) == ""


def test_normalize_member_list_sorts_and_builds_urls():
    raw = [
        {"kpid": "2", "name": "Zeta Member"},
        {"kpid": "1", "name": "Alpha Member"},
        {"name": "No Kpid"},
        {"kpid": "3", "name": ""},
        "not a dict",
    ]
    members = normalize_member_list(raw)
    assert [m["name"] for m in members] == ["Alpha Member", "No Kpid", "Zeta Member"]
    assert members[0]["url"] == member_profile_url("1")
    assert members[1]["url"] == ""


def test_normalize_vote_summary_from_list_endpoint():
    raw = {
        "apn": "abc123",
        "bill_no": "HB2004",
        "chamber": "House",
        "rcs_num": "42",
        "journal_element": {
            "action_label": "Passed",
            "occurred": "2026-01-15T10:00:00",
        },
        "tally": {"yea": 85, "nay": 38, "present": 0, "absent": 2},
    }
    summary = normalize_vote_summary(raw)
    assert summary["apn"] == "abc123"
    assert summary["bill_number"] == "HB2004"
    assert summary["chamber"] == "house"
    assert summary["rcs_num"] == "42"
    assert summary["result"] == "Passed"
    assert summary["date"] == "2026-01-15T10:00:00"
    assert summary["tally"]["yea"] == 85
    assert summary["members"] is None


def test_normalize_vote_summary_fallback_fields():
    raw = {
        "bill_number": "SB498",
        "action_label": "Failed",
        "occurred": "2026-02-01",
        "vote_tally": {"nay": 21, "yea": 19},
        "motion": "Final Action",
    }
    summary = normalize_vote_summary(raw)
    assert summary["bill_number"] == "SB498"
    assert summary["result"] == "Failed"
    assert summary["tally"]["nay"] == 21


def test_normalize_vote_detail_includes_member_groups():
    raw = {
        "apn": "detail1",
        "bill_no": "HB2004",
        "chamber": "house",
        "rcs_num": "7",
        "journal_element": {"action_label": "Passed", "occurred": "2026-01-15"},
        "tally": {"yea": 2, "nay": 1},
        "members": {
            "yea": [{"kpid": "10", "name": "Yea Rep"}],
            "nay": [{"kpid": "20", "name": "Nay Rep"}],
            "present": [],
            "absent": [{"kpid": "30", "name": "Absent Rep"}],
            "not_voting": [],
        },
    }
    detail = normalize_vote_detail(raw)
    assert detail["members"]["yea"][0]["url"] == member_profile_url("10")
    assert detail["members"]["nay"][0]["name"] == "Nay Rep"
    assert detail["members"]["absent"][0]["name"] == "Absent Rep"
    assert detail["members"]["present"] == []


def test_merge_vote_record_preserves_members_and_fills_summary():
    existing = {
        "apn": "x1",
        "bill_number": "HB2004",
        "result": "Old result",
        "members": None,
    }
    new = normalize_vote_detail(
        {
            "apn": "x1",
            "bill_no": "HB2004",
            "journal_element": {"action_label": "Passed"},
            "members": {"yea": [{"kpid": "1", "name": "A"}], "nay": []},
        }
    )
    merged = merge_vote_record(existing, new)
    assert merged["result"] == "Passed"
    assert merged["members"]["yea"][0]["name"] == "A"

    # Empty member update should not wipe existing breakdown
    summary_only = normalize_vote_summary({"apn": "x1", "journal_element": {"action_label": "Updated"}})
    merged_again = merge_vote_record(merged, summary_only)
    assert merged_again["members"]["yea"][0]["name"] == "A"
    assert merged_again["result"] == "Updated"
