"""Tests for email digest building."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.email_digest import (
    build_digest_html,
    infer_item_state,
    partition_by_state,
    partition_hearings,
)


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
