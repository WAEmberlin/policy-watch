"""Tests for Open States per-session bill file splitting."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_bills import (  # noqa: E402
    load_state_bills,
    save_state_bills,
    session_slug,
)


def test_session_slug_sanitizes_path_chars():
    assert session_slug("107S1") == "107S1"
    assert session_slug("2025/26") == "2025-26"


def test_save_small_cache_uses_monolithic_file(tmp_path):
    bills = [
        {"id": "ocd-bill/a", "identifier": "HB 1", "legislative_session": "2026"},
        {"id": "ocd-bill/b", "identifier": "HB 2", "legislative_session": "2025"},
    ]
    saved = save_state_bills(tmp_path, bills)
    assert saved == ["bills.json"]
    assert (tmp_path / "bills.json").exists()
    assert not list(tmp_path.glob("bills_*.json"))
    assert len(load_state_bills(tmp_path)) == 2


def test_save_large_cache_splits_by_session(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "processing.openstates_bills.MAX_MONOLITHIC_BYTES",
        200,
    )
    bills = [
        {"id": f"ocd-bill/{i}", "identifier": f"HB {i}", "legislative_session": "2025", "title": "x" * 80}
        for i in range(5)
    ] + [
        {"id": f"ocd-bill/s{i}", "identifier": f"SB {i}", "legislative_session": "2024", "title": "y" * 80}
        for i in range(5)
    ]
    saved = save_state_bills(tmp_path, bills)
    assert saved == ["bills_2024.json", "bills_2025.json"]
    assert not (tmp_path / "bills.json").exists()
    loaded = load_state_bills(tmp_path)
    assert len(loaded) == 10
    assert {b["legislative_session"] for b in loaded} == {"2024", "2025"}


def test_load_merges_legacy_and_session_files(tmp_path):
    (tmp_path / "bills.json").write_text(
        json.dumps([{"id": "ocd-bill/legacy", "legislative_session": "2023"}]),
        encoding="utf-8",
    )
    (tmp_path / "bills_2024.json").write_text(
        json.dumps([{"id": "ocd-bill/new", "legislative_session": "2024"}]),
        encoding="utf-8",
    )
    loaded = load_state_bills(tmp_path)
    assert len(loaded) == 2
    assert {b["id"] for b in loaded} == {"ocd-bill/legacy", "ocd-bill/new"}
