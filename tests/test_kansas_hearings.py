"""Tests for Kansas hearings schedule fetch."""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.fetch_kansas_hearings import (  # noqa: E402
    _has_matching_live_hearing,
    _is_adjourned,
    api_hearing_to_record,
    interim_committee_to_record,
    live_stream_to_hearing,
    synthesize_live_hearings,
)


def test_api_hearing_to_record_maps_fields():
    raw = {
        "committee_kpid": "ctte_s_wam_1",
        "committee_title": "Ways and Means",
        "chamber": "Senate",
        "hearing_date": "2026-03-18",
        "hearing_time": "11:30 AM",
        "hearing_datetime": "2026-03-18T11:30:00Z",
        "room": "548-S",
        "status": "scheduled",
        "hearing_type": "Hearing on:",
        "bill_numbers": ["HB2781"],
        "is_past": False,
        "streaming": "http://example.com/stream",
    }
    hearing = api_hearing_to_record(raw)

    assert hearing["state"] == "KS"
    assert hearing["committees"] == "Ways and Means"
    assert hearing["bill"] == "HB2781"
    assert "HB2781" in hearing["title"]
    assert hearing["scheduled_date"] == "2026-03-18T11:30:00Z"
    assert hearing["scheduled_time"] == "11:30 AM"
    assert hearing["location"] == "548-S"
    assert hearing["stream_url"] == "http://example.com/stream"
    assert "ctte_s_wam_1" in hearing["url"]


def test_is_adjourned_when_both_chambers_adjourned():
    snapshot = {
        "chambers": {
            "house": {"status": "Adjourned until Monday, January 11, 2027"},
            "senate": {"status": "Adjourned until Monday, January 11, 2027"},
        }
    }
    assert _is_adjourned(snapshot) is True


def test_is_adjourned_false_when_in_session():
    snapshot = {
        "chambers": {
            "house": {"status": "In Session"},
            "senate": {"status": "Adjourned until Monday"},
        }
    }
    assert _is_adjourned(snapshot) is False


def test_interim_committee_to_record_on_call():
    raw = {
        "kpid": "ctte_spc_2025_on_tax_1",
        "display_name": "2025 Special Committee on Taxation",
        "chamber": "Both",
        "committee_type": "Special",
        "mtg_time": "On Call",
        "mtg_room": "",
    }
    hearing = interim_committee_to_record(raw)

    assert hearing["state"] == "KS"
    assert hearing["status"] == "interim_on_call"
    assert hearing["interim_placeholder"] is True
    assert "On Call" in hearing["title"]
    assert hearing["committee_kpid"] == "ctte_spc_2025_on_tax_1"


def test_live_stream_to_hearing_includes_embed():
    stream = {
        "id": "ks-senate-judiciary",
        "title": "Kansas Senate Judiciary",
        "committee_kpid": "ctte_s_jud_1",
        "chamber": "Senate",
    }
    live_info = {
        "title": "Senate Judiciary Committee Hearing",
        "videoId": "abc123xyz",
        "embedUrl": "https://www.youtube.com/embed/abc123xyz",
    }
    hearing = live_stream_to_hearing(stream, live_info, today=date.today().isoformat())

    assert hearing["is_live_synthetic"] is True
    assert hearing["status"] == "live_now"
    assert hearing["youtube_video_id"] == "abc123xyz"
    assert hearing["livestream_id"] == "ks-senate-judiciary"
    assert hearing["embed_url"] == "https://www.youtube.com/embed/abc123xyz"


def test_has_matching_live_hearing_by_committee_kpid():
    today = date.today().isoformat()
    existing = [{"committee_kpid": "ctte_s_jud_1", "scheduled_date": today, "title": "Judiciary"}]
    assert _has_matching_live_hearing(
        existing,
        today=today,
        stream_id="ks-senate-judiciary",
        committee_kpid="ctte_s_jud_1",
        stream_title="Kansas Senate Judiciary",
        video_title="Senate Judiciary live",
    )


def test_has_matching_live_hearing_ignores_interim_placeholder():
    today = date.today().isoformat()
    existing = [
        {
            "committee_kpid": "ctte_s_jud_1",
            "scheduled_date": "",
            "title": "Judiciary (Interim — On Call)",
            "interim_placeholder": True,
        }
    ]
    assert not _has_matching_live_hearing(
        existing,
        today=today,
        stream_id="ks-senate-judiciary",
        committee_kpid="ctte_s_jud_1",
        stream_title="Kansas Senate Judiciary",
        video_title="Senate Judiciary live",
    )


def test_synthesize_live_hearings_from_status(tmp_path, monkeypatch):
    live_status = {
        "streams": {
            "ks-senate-judiciary": {
                "isLive": True,
                "videoId": "vid999",
                "title": "Senate Judiciary — Interim Study",
                "embedUrl": "https://www.youtube.com/embed/vid999",
            }
        }
    }
    livestreams = {
        "streams": [
            {
                "id": "ks-senate-judiciary",
                "title": "Kansas Senate Judiciary",
                "state": "KS",
                "type": "committee",
                "committee_kpid": "ctte_s_jud_1",
            }
        ]
    }

    status_path = tmp_path / "live_status.json"
    streams_path = tmp_path / "livestreams.yaml"
    status_path.write_text(json.dumps(live_status), encoding="utf-8")
    streams_path.write_text(
        "streams:\n"
        "  - id: ks-senate-judiciary\n"
        "    title: Kansas Senate Judiciary\n"
        "    state: KS\n"
        "    type: committee\n"
        "    committee_kpid: ctte_s_jud_1\n",
        encoding="utf-8",
    )

    import processing.fetch_kansas_hearings as mod

    monkeypatch.setattr(mod, "LIVE_STATUS_FILE", status_path)
    monkeypatch.setattr(mod, "LIVESTREAMS_FILE", streams_path)

    synthesized = synthesize_live_hearings([])
    assert len(synthesized) == 1
    assert synthesized[0]["is_live_synthetic"] is True
    assert synthesized[0]["youtube_video_id"] == "vid999"
