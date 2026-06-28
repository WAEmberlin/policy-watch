"""Tests for Open States fetch date resolution."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_openstates import resolve_updated_since


def test_full_refresh_uses_initial_backfill_since():
    config = {"openstates": {"initial_backfill_since": "2026-03-01", "default_days_back": 7}}
    args = argparse.Namespace(since=None, full_refresh=True, days_back=None)
    assert resolve_updated_since(config, args) == "2026-03-01"


def test_since_override():
    config = {"openstates": {"initial_backfill_since": "2026-03-01", "default_days_back": 7}}
    args = argparse.Namespace(since="2026-04-15", full_refresh=False, days_back=None)
    assert resolve_updated_since(config, args) == "2026-04-15"
