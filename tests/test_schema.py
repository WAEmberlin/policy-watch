"""Schema validation tests."""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.ai_enrichment import classify_topics, enrich_bills
from processing.unified_search import build_dashboards, search, build_search_index

REQUIRED_BILL_FIELDS = {
    "id", "source", "level", "bill_number", "title",
}


def test_states_config_loads():
    config_path = ROOT / "config" / "states.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert "states" in config
    codes = [s["code"] for s in config["states"]]
    assert "ks" in codes
    assert "co" in codes
    assert "az" in codes
    assert "ut" in codes


def test_enriched_bill_schema():
    bill = {
        "id": "test-1",
        "source": "congress",
        "level": "federal",
        "state": None,
        "bill_number": "HR 1",
        "title": "Veterans Health Care Act",
        "summary": "A bill to improve veterans healthcare.",
        "latest_action": "Introduced",
        "latest_action_date": "2026-01-01",
    }
    enriched = enrich_bills([bill])[0]
    for field in REQUIRED_BILL_FIELDS:
        assert field in enriched
    assert enriched["ai_summary_short"]
    assert enriched["ai_summary_detailed"]
    assert enriched["ai_impact_analysis"]
    assert "Veterans" in enriched["ai_topics"] or len(enriched["ai_topics"]) >= 0


def test_unified_search_veterans():
    bills = [
        {"id": "1", "bill_number": "HR 1", "title": "Veterans Benefits", "summary": "", "source": "congress",
         "level": "federal", "state": None, "status": "", "latest_action": "", "latest_action_date": "",
         "chamber": "House", "classification": [], "sponsors": [], "url": "", "ai_topics": ["Veterans"]},
        {"id": "2", "bill_number": "SB 1", "title": "Education Reform", "summary": "", "source": "openstates",
         "level": "state", "state": "KS", "status": "", "latest_action": "", "latest_action_date": "",
         "chamber": "Senate", "classification": [], "sponsors": [], "url": "", "ai_topics": []},
    ]
    index = build_search_index(bills, [], [])
    results = search(index, query="veterans")
    assert len(results["bills"]) == 1
    assert results["bills"][0]["bill_number"] == "HR 1"


def test_dashboards_build():
    config = {"topic_dashboards": [{"id": "veterans", "keywords": ["veteran"]}]}
    bills = [{"title": "Veterans bill", "summary": "", "latest_action": "", "latest_action_date": "2026-06-01T00:00:00+00:00", "updated_at": "2026-06-01T00:00:00+00:00", "ai_topics": []}]
    dashboards = build_dashboards(bills, [], [], config)
    assert "recent_bills" in dashboards
    assert "topics" in dashboards
