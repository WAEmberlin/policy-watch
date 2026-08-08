"""Tests for slim legislators directory generation."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.legislators_directory import (  # noqa: E402
    LEGISLATORS_DIRECTORY_FILENAME,
    build_legislators_directory,
    build_slim_legislators,
    slim_legislator,
    write_legislators_directory_artifacts,
)


def test_slim_legislator_drops_image_and_demographics():
    row = slim_legislator(
        {
            "id": "ocd-person/1",
            "name": "Ada",
            "party": "Democratic",
            "state": "KS",
            "chamber": "House",
            "district": "1",
            "url": "https://example.com/ada",
            "image": "https://example.com/ada.jpg",
            "gender": "Female",
            "birth_date": "1980-01-01",
        }
    )
    assert row == {
        "id": "ocd-person/1",
        "name": "Ada",
        "party": "Democratic",
        "state": "KS",
        "chamber": "House",
        "district": "1",
        "url": "https://example.com/ada",
    }
    assert "image" not in row
    assert "gender" not in row
    assert "birth_date" not in row


def test_build_slim_legislators_from_search_index():
    search_index = {
        "legislators": [
            {
                "id": "a",
                "name": "A",
                "party": "R",
                "state": "CO",
                "chamber": "Senate",
                "district": "2",
                "url": "https://example.com/a",
                "image": "https://example.com/a.jpg",
            }
        ]
    }
    rows = build_slim_legislators(search_index)
    assert len(rows) == 1
    assert rows[0]["name"] == "A"
    assert "image" not in rows[0]


def test_build_legislators_directory_payload_shape():
    search_index = {
        "legislators": [
            {
                "id": "x",
                "name": "X",
                "party": "Independent",
                "state": "AZ",
                "chamber": "House",
                "district": "10",
                "url": "",
            }
        ]
    }
    stats = {"by_state": {"AZ": {"total": 1}}, "data_notes": {}}
    states = [{"code": "az", "name": "Arizona"}]
    payload = build_legislators_directory(
        search_index=search_index,
        legislator_stats=stats,
        states=states,
        generated_at="2026-08-07T12:00:00+00:00",
    )
    assert payload["legislators_directory"] is True
    assert payload["generated_at"] == "2026-08-07T12:00:00+00:00"
    assert payload["states"] == states
    assert payload["legislator_stats"] == stats
    assert payload["stats"]["legislator_count"] == 1
    assert payload["legislators"][0]["id"] == "x"
    assert "image" not in payload["legislators"][0]
    # Must not embed full search_index / bills
    assert "search_index" not in payload
    assert "bills" not in payload
    assert "years" not in payload


def test_write_legislators_directory_artifacts(tmp_path):
    search_index = {
        "legislators": [
            {
                "id": "y",
                "name": "Y",
                "party": "Democratic",
                "state": "UT",
                "chamber": "Senate",
                "district": "3",
                "url": "https://example.com/y",
            }
        ]
    }
    path, payload = write_legislators_directory_artifacts(
        tmp_path,
        search_index=search_index,
        legislator_stats={"by_state": {}},
        states=[{"code": "ut", "name": "Utah"}],
        generated_at="2026-08-07T00:00:00+00:00",
    )
    assert path == tmp_path / LEGISLATORS_DIRECTORY_FILENAME
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["legislators_directory"] is True
    assert data["stats"]["legislator_count"] == 1
    assert data["legislators"][0]["name"] == "Y"
    assert payload["stats"]["legislator_count"] == 1


def test_r2_upload_list_includes_legislators_directory():
    from processing.r2_sync import DOCS_UPLOAD_FILES

    assert "legislators_directory.json" in DOCS_UPLOAD_FILES


def test_prefer_legislators_picks_fuller_list(tmp_path):
    from processing.r2_sync import prefer_legislators

    site = {
        "legislators": [
            {"id": "1", "name": "Site", "state": "KS"},
            {"id": "2", "name": "Federal", "state": "KS"},
        ]
    }
    preferred = {"legislators": [{"id": "1", "name": "Norm", "state": "KS"}]}
    missing_norm = tmp_path / "missing-legislators.json"
    chosen = prefer_legislators(
        site,
        preferred_index=preferred,
        normalized_legislators_path=missing_norm,
    )
    assert len(chosen) == 2
    assert chosen[1]["name"] == "Federal"


def test_prefer_legislators_prefers_normalized_state_coverage(tmp_path):
    from processing.r2_sync import prefer_legislators

    norm = tmp_path / "legislators.json"
    norm.write_text(
        json.dumps(
            [
                {"id": "a", "name": "A", "state": "KS"},
                {"id": "b", "name": "B", "state": "MA"},
                {"id": "c", "name": "C", "state": "IA"},
            ]
        ),
        encoding="utf-8",
    )
    site = {"legislators": [{"id": "a", "name": "A", "state": "KS"}]}
    preferred = {"legislators": [{"id": "a", "name": "A", "state": "KS"}]}
    chosen = prefer_legislators(
        site,
        preferred_index=preferred,
        normalized_legislators_path=norm,
    )
    assert len(chosen) == 3
    assert {row["state"] for row in chosen} == {"KS", "MA", "IA"}


def test_resolve_directory_states_uses_yaml_over_stale_site_states(tmp_path):
    from processing.legislators_directory import resolve_directory_states

    yaml_path = tmp_path / "states.yaml"
    yaml_path.write_text(
        "states:\n"
        "  - code: ks\n    name: Kansas\n    enabled: true\n"
        "  - code: ma\n    name: Massachusetts\n    enabled: true\n"
        "  - code: ia\n    name: Iowa\n    enabled: true\n",
        encoding="utf-8",
    )
    stale_site = [{"code": "ks", "name": "Kansas"}]
    legislators = [
        {"state": "KS"},
        {"state": "MA"},
        {"state": "IA"},
    ]
    resolved = resolve_directory_states(
        stale_site,
        legislators,
        config_path=yaml_path,
    )
    assert [s["code"] for s in resolved] == ["ks", "ma", "ia"]
    assert resolved[1]["name"] == "Massachusetts"


def test_prefer_legislator_stats_uses_normalized(tmp_path):
    from processing.r2_sync import prefer_legislator_stats

    normalized_dir = tmp_path / "normalized"
    normalized_dir.mkdir()
    (normalized_dir / "legislator_stats.json").write_text(
        json.dumps({"by_state": {"KS": {"total": 2}, "CO": {"total": 1}}}),
        encoding="utf-8",
    )
    chosen = prefer_legislator_stats(
        {"by_state": {"KS": {"total": 1}}},
        normalized_path=normalized_dir / "legislator_stats.json",
    )
    assert set(chosen["by_state"]) == {"KS", "CO"}
