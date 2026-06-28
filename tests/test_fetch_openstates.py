"""Tests for Open States fetch scheduling and incremental since dates."""

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_openstates import (
    resolve_global_since,
    resolve_state_since,
    sort_states_for_fetch,
    state_priority,
)


def test_full_refresh_uses_initial_backfill_since():
    config = {"openstates": {"initial_backfill_since": "2026-03-01", "default_days_back": 7}}
    args = argparse.Namespace(since=None, full_refresh=True, days_back=None)
    assert resolve_global_since(config, args) == "2026-03-01"


def test_since_override():
    config = {"openstates": {"initial_backfill_since": "2026-03-01", "default_days_back": 7}}
    args = argparse.Namespace(since="2026-04-15", full_refresh=False, days_back=None)
    assert resolve_global_since(config, args) == "2026-04-15"


def test_incomplete_states_sort_first():
    os_cfg = {"prioritize_incomplete": True}
    states = [
        {"code": "az", "enabled": True, "sources": ["openstates"]},
        {"code": "me", "enabled": True, "sources": ["openstates"]},
    ]

    def fake_meta(code):
        if code == "az":
            return {"backfill_complete": True, "counts": {"bills": 900}, "last_successful_fetch_at": "2026-06-28T00:00:00+00:00"}
        return {}

    def fake_bills(code):
        return 900 if code == "az" else 0

    with patch("processing.fetch_openstates.load_state_meta", side_effect=fake_meta):
        with patch("processing.fetch_openstates.state_bill_count", side_effect=fake_bills):
            ordered = sort_states_for_fetch(states, os_cfg)
            assert ordered[0]["code"] == "me"


def test_resolve_state_since_uses_backfill_for_empty_state():
    os_cfg = {"initial_backfill_since": "2026-03-01", "incremental_overlap_days": 1}
    args = argparse.Namespace(since=None, full_refresh=False, force=False)
    with patch("processing.fetch_openstates.load_state_meta", return_value={}):
        with patch("processing.fetch_openstates.state_bill_count", return_value=0):
            assert resolve_state_since("me", "2026-06-21", args, os_cfg) == "2026-03-01"


def test_state_priority_never_synced_first():
    with patch("processing.fetch_openstates.load_state_meta", return_value={}):
        with patch("processing.fetch_openstates.state_bill_count", return_value=0):
            assert state_priority("me", {})[0] == 0
