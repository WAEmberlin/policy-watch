"""Tests for R2 sync helpers that do not require live credentials."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.r2_sync import prefer_search_index, write_data_config  # noqa: E402
import processing.r2_sync as mod  # noqa: E402


def test_write_data_config_sets_public_base(monkeypatch, tmp_path):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://pub-example.r2.dev/")
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    out = write_data_config()
    text = out.read_text(encoding="utf-8")
    assert "https://pub-example.r2.dev" in text
    assert "window.POLICYWATCH_DATA_BASE" in text
    assert "window.CIVICWATCH_DATA_BASE = window.POLICYWATCH_DATA_BASE" in text
    # trailing slash stripped
    assert "https://pub-example.r2.dev/" not in text.replace("https://pub-example.r2.dev';", "")


def test_prefer_search_index_uses_larger_normalized_corpus(tmp_path):
    normalized_dir = tmp_path / "data" / "normalized"
    normalized_dir.mkdir(parents=True)
    (normalized_dir / "search_index.json").write_text(
        json.dumps({"bills": [{"bill_number": "A"}, {"bill_number": "B"}, {"bill_number": "C"}]}),
        encoding="utf-8",
    )
    chosen = prefer_search_index(
        {"bills": [{"bill_number": "A"}]},
        normalized_path=normalized_dir / "search_index.json",
    )
    assert len(chosen["bills"]) == 3


def test_prefer_search_index_keeps_site_when_larger(tmp_path):
    normalized_dir = tmp_path / "data" / "normalized"
    normalized_dir.mkdir(parents=True)
    (normalized_dir / "search_index.json").write_text(
        json.dumps({"bills": [{"bill_number": "A"}]}),
        encoding="utf-8",
    )
    site = {"bills": [{"bill_number": "A"}, {"bill_number": "B"}]}
    chosen = prefer_search_index(site, normalized_path=normalized_dir / "search_index.json")
    assert chosen is site


def test_validate_docs_upload_rejects_incomplete_home_search(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    normalized = tmp_path / "data" / "normalized"
    normalized.mkdir(parents=True)
    (normalized / "meta.json").write_text(
        json.dumps({"counts": {"bills": 1000}}),
        encoding="utf-8",
    )
    home_feed = docs / "home_feed.json"
    home_feed.write_text(
        json.dumps({"home_feed": True, "available_dates": ["2026-08-04"]}),
        encoding="utf-8",
    )
    search = docs / "home_search_bills.json"
    search.write_text(
        json.dumps({"home_search_bills": True, "bills": [{"bill_number": "A"}] * 10}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="home_search_bills"):
        mod._validate_docs_upload(
            [
                (home_feed, "home_feed.json"),
                (search, "home_search_bills.json"),
            ]
        )
