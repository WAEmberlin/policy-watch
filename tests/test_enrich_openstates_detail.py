"""Tests for Open States detail enrichment."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.enrich_openstates_detail import enrich_all_openstates  # noqa: E402


def test_enrich_all_openstates_does_not_raise_name_error(monkeypatch):
    monkeypatch.setattr(
        "processing.enrich_openstates_detail.enrich_state",
        lambda *args, **kwargs: 0,
    )
    assert enrich_all_openstates(max_per_state=1, days_back=1) == 0
