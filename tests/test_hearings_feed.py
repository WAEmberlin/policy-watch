"""Tests for slim hearings feed generation."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.hearings_feed import (  # noqa: E402
    HEARINGS_FEED_FILENAME,
    build_hearings_feed,
    hearings_from_normalized_events,
    prefer_hearings_from_normalized,
    resolve_hearings_states,
    write_hearings_feed_artifacts,
)


def test_build_hearings_feed_payload_shape(tmp_path):
    yaml_path = tmp_path / "states.yaml"
    yaml_path.write_text(
        "states:\n"
        "  - code: ks\n    name: Kansas\n    enabled: true\n"
        "  - code: ma\n    name: Massachusetts\n    enabled: true\n"
        "  - code: ia\n    name: Iowa\n    enabled: true\n",
        encoding="utf-8",
    )
    upcoming = [
        {
            "title": "Hearing A",
            "scheduled_date": "2099-01-01",
            "state": "KS",
            "level": "state",
        }
    ]
    historical = [
        {
            "title": "Hearing B",
            "scheduled_date": "2020-01-01",
            "state": "MA",
            "level": "state",
        }
    ]
    calendars = {"2026-01-13": [{"chamber": "House", "title": "Calendar", "link": "https://x"}]}
    payload = build_hearings_feed(
        upcoming_hearings=upcoming,
        historical_hearings=historical,
        kansas_calendars=calendars,
        states=[{"code": "ks", "name": "Kansas"}],  # stale/short list
        generated_at="2026-08-08T12:00:00+00:00",
        config_path=yaml_path,
    )
    assert payload["hearings_feed"] is True
    assert payload["generated_at"] == "2026-08-08T12:00:00+00:00"
    assert [s["code"] for s in payload["states"]] == ["ks", "ma", "ia"]
    assert payload["upcoming_hearings"][0]["title"] == "Hearing A"
    assert payload["historical_hearings"][0]["title"] == "Hearing B"
    assert payload["kansas_calendars"] == calendars
    assert payload["stats"]["upcoming_count"] == 1
    assert payload["stats"]["historical_count"] == 1
    assert payload["stats"]["state_count"] == 3
    assert "search_index" not in payload
    assert "years" not in payload


def test_resolve_hearings_states_keeps_empty_new_states(tmp_path):
    yaml_path = tmp_path / "states.yaml"
    yaml_path.write_text(
        "states:\n"
        "  - code: ks\n    name: Kansas\n    enabled: true\n"
        "  - code: ia\n    name: Iowa\n    enabled: true\n",
        encoding="utf-8",
    )
    resolved = resolve_hearings_states(
        [{"code": "ks", "name": "Kansas"}],
        config_path=yaml_path,
    )
    assert [s["code"] for s in resolved] == ["ks", "ia"]


def test_hearings_from_normalized_events_skips_congress():
    today = datetime(2026, 8, 8, tzinfo=timezone.utc)
    events = [
        {
            "title": "Fed",
            "scheduled_date": "2099-01-01",
            "source": "congress",
            "level": "federal",
            "state": None,
        },
        {
            "title": "IA Committee",
            "scheduled_date": "2099-02-01",
            "source": "openstates",
            "level": "state",
            "state": "IA",
            "url": "https://example.com/ia",
            "committees": [{"name": "House Ways"}],
        },
        {
            "title": "Past MA",
            "scheduled_date": "2020-03-01",
            "source": "openstates",
            "level": "state",
            "state": "MA",
            "url": "https://example.com/ma",
        },
    ]
    upcoming, historical = hearings_from_normalized_events(events, today=today)
    assert len(upcoming) == 1
    assert upcoming[0]["state"] == "IA"
    assert upcoming[0]["committees"] == "House Ways"
    assert len(historical) == 1
    assert historical[0]["state"] == "MA"


def test_prefer_hearings_from_normalized_merges(tmp_path):
    events_path = tmp_path / "events.json"
    events_path.write_text(
        json.dumps(
            [
                {
                    "title": "New State Hearing",
                    "scheduled_date": "2099-06-01",
                    "source": "openstates",
                    "level": "state",
                    "state": "WV",
                    "url": "https://example.com/wv",
                }
            ]
        ),
        encoding="utf-8",
    )
    site_upcoming = [
        {
            "title": "Old KS",
            "scheduled_date": "2099-01-01",
            "state": "KS",
            "url": "https://example.com/ks",
        }
    ]
    upcoming, historical = prefer_hearings_from_normalized(
        site_upcoming,
        [],
        normalized_events_path=events_path,
        today=datetime(2026, 8, 8, tzinfo=timezone.utc),
    )
    assert len(upcoming) == 2
    assert {h["state"] for h in upcoming} == {"KS", "WV"}


def test_write_hearings_feed_artifacts(tmp_path):
    path, payload = write_hearings_feed_artifacts(
        tmp_path,
        upcoming_hearings=[{"title": "U", "scheduled_date": "2099-01-01", "state": "KS"}],
        historical_hearings=[],
        kansas_calendars={},
        states=[{"code": "ks", "name": "Kansas"}],
        generated_at="2026-08-08T00:00:00+00:00",
        config_path=tmp_path / "missing.yaml",
    )
    assert path == tmp_path / HEARINGS_FEED_FILENAME
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["hearings_feed"] is True
    assert data["stats"]["upcoming_count"] == 1
    assert payload["stats"]["upcoming_count"] == 1


def test_r2_upload_list_includes_hearings_json():
    from processing.r2_sync import DOCS_UPLOAD_FILES

    assert "hearings.json" in DOCS_UPLOAD_FILES
