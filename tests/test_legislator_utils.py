"""Tests for legislator URL resolution and stats."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.legislator_stats import build_legislator_stats  # noqa: E402
from processing.legislator_urls import resolve_legislator_profile_url  # noqa: E402


def test_resolve_kansas_profile_from_links():
    leg = {
        "state": "KS",
        "links": "https://ballotpedia.org/foo;https://www.kslegislature.gov/li/b2025_26/members/rep_boatman_abi_1/",
    }
    url = resolve_legislator_profile_url(leg)
    assert "kslegislature.gov" in url
    assert "members" in url


def test_resolve_colorado_profile():
    leg = {
        "state": "CO",
        "links": "https://leg.colorado.gov/legislators/adrienne-benavidez",
    }
    assert resolve_legislator_profile_url(leg) == "https://leg.colorado.gov/legislators/adrienne-benavidez"


def test_build_legislator_stats_party_and_gender():
    stats = build_legislator_stats([
        {"state": "KS", "party": "Republican", "gender": "Male", "chamber": "lower", "birth_date": "1980-01-01"},
        {"state": "KS", "party": "Democratic", "gender": "Female", "chamber": "upper"},
    ])
    ks = stats["by_state"]["KS"]
    assert ks["total"] == 2
    assert ks["party"]["Republican"] == 1
    assert ks["party"]["Democratic"] == 1
    assert ks["gender"]["Male"] == 1
    assert ks["gender"]["Female"] == 1
    assert ks["race_available"] is False
