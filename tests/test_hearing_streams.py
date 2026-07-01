"""Tests for hearing stream enrichment."""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from adapters.openstates_source import OpenStatesSource  # noqa: E402
from processing.hearing_stream_utils import enrich_hearing_stream, infer_hearing_state  # noqa: E402


def _load_livestreams():
    with open(ROOT / "config" / "livestreams.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("state_floor_stream") or {}, cfg.get("streams") or []


def test_infer_hearing_state_from_source_label():
    hearing = {"source": "State (Colorado)"}
    assert infer_hearing_state(hearing) == "CO"


def test_openstates_event_stream_url_from_media():
    raw = [{
        "id": "evt-1",
        "name": "House Judiciary Committee",
        "start_date": "2026-03-01",
        "participants": [{"name": "House Judiciary Committee"}],
        "links": [{"url": "https://leg.colorado.gov/agenda/123", "note": "Agenda"}],
        "media": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "classification": ["video"]}],
    }]
    adapter = OpenStatesSource("CO", "ocd-jurisdiction/country:us/state:co/government")
    event = adapter.normalize_events(raw)[0].to_dict()
    assert event["stream_url"].startswith("https://www.youtube.com/watch")


def test_colorado_hearing_gets_floor_embed_and_watch_link():
    state_floor_map, streams = _load_livestreams()
    hearing = {
        "title": "HB 1001 hearing",
        "source": "State (Colorado)",
        "state": "CO",
        "level": "state",
        "committee": "House Business Affairs & Labor",
        "committees": "House Business Affairs & Labor",
        "url": "https://leg.colorado.gov/agenda/example",
    }
    enriched = enrich_hearing_stream(hearing, state_floor_map=state_floor_map, streams=streams)

    assert enriched["livestream_id"] == "colorado-floor"
    assert enriched["embed_url"] == "https://coloradochannel.net/watch-meetings/"
    assert enriched["stream_url"] == "https://coloradochannel.net/watch-meetings/"


def test_utah_hearing_gets_youtube_embed():
    state_floor_map, streams = _load_livestreams()
    hearing = {
        "title": "Senate Education Committee",
        "source": "State (Utah)",
        "state": "UT",
        "level": "state",
        "committee": "Senate Education Committee",
    }
    enriched = enrich_hearing_stream(hearing, state_floor_map=state_floor_map, streams=streams)

    assert enriched["livestream_id"] == "utah-floor"
    assert "youtube.com/embed/live_stream" in enriched["embed_url"]
    assert enriched["stream_url"] == "https://www.youtube.com/user/UtahLegislature"


def test_colorado_judiciary_prefers_watch_page_stream_url():
    state_floor_map, streams = _load_livestreams()
    hearing = {
        "title": "Judiciary hearing",
        "source": "State (Colorado)",
        "state": "CO",
        "committee": "House Judiciary Committee",
    }
    enriched = enrich_hearing_stream(hearing, state_floor_map=state_floor_map, streams=streams)

    assert enriched["livestream_id"] == "colorado-floor"
    assert enriched["stream_url"] == "https://leg.colorado.gov/watch-and-listen"
    assert enriched["embed_url"] == "https://coloradochannel.net/watch-meetings/"
