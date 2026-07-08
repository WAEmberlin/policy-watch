"""Tests for legislator vote index building."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.legislator_votes import (  # noqa: E402
    build_legislator_vote_index,
    chamber_key,
    kpid_from_url,
)


def test_kpid_from_url():
    assert kpid_from_url("https://www.kslegislature.gov/b2025_26/members/rep_boatman_abi_1/") == "rep_boatman_abi_1"
    assert kpid_from_url("https://www.kslegislature.gov/legislators/rep_wilson_greg_1/") == "rep_wilson_greg_1"


def test_chamber_key_maps_house_and_senate():
    assert chamber_key("Representative") == "lower"
    assert chamber_key("Senator") == "upper"
    assert chamber_key(organization="lower") == "lower"


def test_build_legislator_vote_index_matches_kansas_kpid_legislators_url():
    legislators = [{
        "id": "ocd-person/wilson",
        "state": "KS",
        "name": "Greg Wilson",
        "family_name": "Wilson",
        "chamber": "Representative",
        "url": "https://www.kslegislature.gov/legislators/rep_wilson_greg_1/",
    }]
    kansas_records = {
        "HB2004": [{
            "bill_number": "HB2004",
            "date": "2026-03-26T22:18:32+00:00",
            "result": "Final Action - Yea",
            "chamber": "house",
            "members": {"yea": [{"kpid": "rep_wilson_greg_1", "name": "Greg Wilson"}]},
        }],
    }
    index = build_legislator_vote_index(legislators, [], kansas_records)
    assert len(index["ocd-person/wilson"]) == 1


def test_build_legislator_vote_index_matches_kansas_kpid():
    legislators = [{
        "id": "ocd-person/test",
        "state": "KS",
        "name": "Adam Smith",
        "family_name": "Smith",
        "chamber": "Representative",
        "url": "https://www.kslegislature.gov/b2025_26/members/rep_smith_adam_1/",
    }]
    kansas_records = {
        "HB2004": [{
            "bill_number": "HB2004",
            "date": "2026-03-26T22:18:32+00:00",
            "result": "Conference Committee Report was adopted;",
            "chamber": "house",
            "rcs_num": "0353",
            "members": {
                "yea": [{"kpid": "rep_smith_adam_1", "name": "Adam Smith"}],
            },
        }],
    }
    index = build_legislator_vote_index(legislators, [], kansas_records)
    assert len(index["ocd-person/test"]) == 1
    assert index["ocd-person/test"][0]["option"] == "Yes"
    assert index["ocd-person/test"][0]["bill_number"] == "HB2004"


def test_build_legislator_vote_index_trims_at_max():
    legislators = [{
        "id": "ocd-person/trim",
        "state": "KS",
        "name": "Trim Test",
        "family_name": "Test",
        "chamber": "Representative",
        "url": "https://www.kslegislature.gov/b2025_26/members/rep_trim_test_1/",
    }]
    kansas_records = {
        "HB2004": [
            {
                "bill_number": "HB2004",
                "date": f"2026-03-{day:02d}T12:00:00+00:00",
                "result": f"Motion {day}",
                "chamber": "house",
                "members": {"yea": [{"kpid": "rep_trim_test_1", "name": "Trim Test"}]},
            }
            for day in range(1, 1005)
        ],
    }
    index = build_legislator_vote_index(legislators, [], kansas_records, max_per_legislator=1000)
    assert len(index["ocd-person/trim"]) == 1000


def test_build_legislator_vote_index_matches_maine_surname_format():
    legislators = [{
        "id": "ocd-person/me",
        "state": "ME",
        "name": "Donna Bailey",
        "family_name": "Bailey",
        "chamber": "Senator",
    }]
    votes = [{
        "state": "ME",
        "organization": "upper",
        "bill_number": "LD 2182",
        "date": "2026-02-12",
        "motion_text": "Final vote",
        "votes": [{"voter_name": "BAILEY of York", "option": "yes"}],
    }]
    index = build_legislator_vote_index(legislators, votes, {})
    assert len(index["ocd-person/me"]) == 1


def test_build_legislator_vote_index_matches_colorado_full_name():
    legislators = [{
        "id": "ocd-person/co",
        "state": "CO",
        "name": "Andy Boesenecker",
        "family_name": "Boesenecker",
        "chamber": "Representative",
    }]
    votes = [{
        "state": "CO",
        "organization": "lower",
        "bill_number": "HB 24-1001",
        "date": "2024-02-01",
        "motion_text": "Third Reading",
        "votes": [{"voter_name": "Andrew Boesenecker", "option": "yes"}],
    }]
    index = build_legislator_vote_index(legislators, votes, {})
    assert len(index["ocd-person/co"]) == 1


def test_build_legislator_vote_index_matches_openstates_name():
    legislators = [{
        "id": "ocd-person/co",
        "state": "CO",
        "name": "Jane Doe",
        "family_name": "Doe",
        "chamber": "Representative",
    }]
    votes = [{
        "state": "CO",
        "organization": "lower",
        "bill_number": "HB 24-1001",
        "date": "2024-02-01",
        "motion_text": "Third Reading",
        "votes": [{"voter_name": "Doe", "option": "yes"}],
    }]
    index = build_legislator_vote_index(legislators, votes, {})
    assert len(index["ocd-person/co"]) == 1
    assert index["ocd-person/co"][0]["option"] == "Yes"
