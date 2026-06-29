"""Tests for weekly overview jurisdiction sections and veterans highlighting."""

from datetime import datetime, timezone

from src.processing.weekly_overview import (
    build_veterans_highlight,
    generate_summary,
    matches_veterans_topic,
)


def test_matches_veterans_topic_keywords():
    keywords = ["veteran", "veterans", "va", "military", "armed forces", "armed services"]
    assert matches_veterans_topic("Veterans Benefits Expansion Act", keywords)
    assert matches_veterans_topic("Senate Armed Services hearing", keywords)
    assert matches_veterans_topic("Department of VA healthcare", keywords)
    assert not matches_veterans_topic("Property tax assessment reform", keywords)
    assert not matches_veterans_topic("Nevada tourism promotion", keywords)


def test_build_veterans_highlight_collects_matches():
    activity = {
        "bills": [
            {
                "title": "HR 6921: Veterans cemetery in Hawaii",
                "summary": "Secretary of Veterans Affairs",
                "bill_type": "HR",
                "bill_number": "6921",
                "url": "https://example.com/hr6921",
            },
            {"title": "HB 100: Road funding", "summary": "Transportation infrastructure"},
        ],
        "events": [
            {
                "title": "Armed Services personnel subcommittee",
                "summary": "Military readiness",
                "url": "https://example.com/hearing",
            }
        ],
        "votes": [],
    }
    keywords = ["veteran", "veterans", "armed services", "military"]
    highlight = build_veterans_highlight(activity, keywords)
    assert highlight is not None
    assert highlight["total_matches"] >= 2
    assert "Veterans cemetery" in highlight["summary"] or "HR 6921" in highlight["summary"]


def test_generate_summary_includes_all_jurisdictions():
    jurisdictions = {
        "federal": {
            "bills": [{"title": "HR 1: Test", "summary": "", "bill_type": "HR", "bill_number": "1"}],
            "events": [],
            "votes": [],
        },
        "ks": {"bills": [], "events": [], "votes": []},
        "co": {"bills": [], "events": [], "votes": []},
    }
    section_order = [
        {"id": "federal", "label": "Congress / Federal"},
        {"id": "ks", "label": "Kansas"},
        {"id": "co", "label": "Colorado"},
    ]
    now = datetime.now(timezone.utc)
    week_start = now.replace(day=1)
    week_end = now

    script, sections, counts = generate_summary(
        jurisdictions, section_order, week_start, week_end, ["veteran"]
    )

    assert len(sections) == 3
    assert counts["federal"] == 1
    assert counts["ks"] == 0
    assert "Kansas: No new activity this week." in script
    assert "Congress / Federal:" in script
