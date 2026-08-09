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


def test_validate_docs_upload_rejects_home_search_absolute_shortfall(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    normalized = tmp_path / "data" / "normalized"
    normalized.mkdir(parents=True)
    monkeypatch.setattr(mod, "HOME_SEARCH_MAX_ABS_SHORTFALL", 50)
    # 90% coverage passes the relative bar; absolute shortfall must still refuse.
    expected = 1000
    search_n = 900
    (normalized / "meta.json").write_text(
        json.dumps({"counts": {"bills": expected}}),
        encoding="utf-8",
    )
    home_feed = docs / "home_feed.json"
    home_feed.write_text(
        json.dumps({"home_feed": True, "available_dates": ["2026-08-04"]}),
        encoding="utf-8",
    )
    search = docs / "home_search_bills.json"
    search.write_text(
        json.dumps({"home_search_bills": True, "bills": [{"bill_number": "A"}] * search_n}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="shortfall"):
        mod._validate_docs_upload(
            [
                (home_feed, "home_feed.json"),
                (search, "home_search_bills.json"),
            ]
        )


def test_counts_diverge_relative_and_absolute():
    assert not mod._counts_diverge(1000, 1000)
    assert not mod._counts_diverge(100_000, 96_000)  # 4% < 10%, gap < 5k? 4000 < 5000
    assert mod._counts_diverge(100_000, 80_000)  # 20% relative
    assert mod._counts_diverge(100_000, 94_000)  # abs gap 6000 > 5000


def test_validate_normalized_upload_accepts_consistent_counts(tmp_path):
    normalized = tmp_path / "data" / "normalized"
    normalized.mkdir(parents=True)
    bills = [{"id": f"b{i}"} for i in range(100)]
    meta = normalized / "meta.json"
    bills_path = normalized / "bills.json"
    search_path = normalized / "search_index.json"
    meta.write_text(json.dumps({"counts": {"bills": 100}}), encoding="utf-8")
    bills_path.write_text(json.dumps(bills), encoding="utf-8")
    search_path.write_text(json.dumps({"bills": bills}), encoding="utf-8")

    kept = mod._validate_normalized_upload(
        [
            (meta, "data/normalized/meta.json"),
            (bills_path, "data/normalized/bills.json"),
            (search_path, "data/normalized/search_index.json"),
        ]
    )
    assert len(kept) == 3


def test_validate_normalized_upload_refuses_truncated_bills(tmp_path):
    normalized = tmp_path / "data" / "normalized"
    normalized.mkdir(parents=True)
    meta = normalized / "meta.json"
    bills_path = normalized / "bills.json"
    search_path = normalized / "search_index.json"
    meta.write_text(json.dumps({"counts": {"bills": 10_000}}), encoding="utf-8")
    bills_path.write_text(json.dumps([{"id": "x"}] * 100), encoding="utf-8")
    search_path.write_text(
        json.dumps({"bills": [{"id": "x"}] * 10_000}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="truncated/inconsistent normalized"):
        mod._validate_normalized_upload(
            [
                (meta, "data/normalized/meta.json"),
                (bills_path, "data/normalized/bills.json"),
                (search_path, "data/normalized/search_index.json"),
            ]
        )


def test_validate_normalized_upload_skips_when_no_critical_keys(tmp_path):
    other = tmp_path / "docs" / "live_status.json"
    other.parent.mkdir(parents=True)
    other.write_text("{}", encoding="utf-8")
    kept = mod._validate_normalized_upload([(other, "live_status.json")])
    assert kept == [(other, "live_status.json")]
