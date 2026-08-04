"""Tests for R2 sync helpers that do not require live credentials."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.r2_sync import write_data_config  # noqa: E402


def test_write_data_config_sets_public_base(monkeypatch, tmp_path):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://pub-example.r2.dev/")
    # Point ROOT docs via monkeypatch of module constant
    import processing.r2_sync as mod

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
