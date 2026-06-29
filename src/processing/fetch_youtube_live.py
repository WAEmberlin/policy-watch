"""
Poll YouTube Data API for live streams and write docs/live_status.json.

Also generates docs/live-streams-config.json from config/livestreams.yaml.
Run hourly via GitHub Actions (requires YOUTUBE_API_KEY secret).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.youtube_utils import resolve_embed_url, youtube_video_embed  # noqa: E402
CONFIG_PATH = ROOT / "config" / "livestreams.yaml"
DOCS_DIR = ROOT / "docs"
CONFIG_OUT = DOCS_DIR / "live-streams-config.json"
STATUS_OUT = DOCS_DIR / "live_status.json"

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
REQUEST_DELAY = 0.2


def load_livestreams_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_static_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    streams_out: List[Dict[str, Any]] = []
    for item in raw.get("streams") or []:
        channel_id = item.get("youtube_channel_id") or ""
        embed = resolve_embed_url(
            embed_url=item.get("embed_url") or "",
            youtube_channel_id=channel_id,
        )
        streams_out.append(
            {
                "id": item["id"],
                "title": item.get("title", item["id"]),
                "state": item.get("state", ""),
                "jurisdiction": item.get("jurisdiction", ""),
                "type": item.get("type", "floor"),
                "targetId": item.get("target_id", item["id"]),
                "tabPane": item.get("tab_pane", ""),
                "embedUrl": embed,
                "youtubeUrl": item.get("youtube_url") or item.get("external_url") or "",
                "youtubeChannelId": channel_id,
                "externalUrl": item.get("external_url") or "",
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "state_floor_stream": raw.get("state_floor_stream") or {},
        "streams": streams_out,
    }


def fetch_live_for_channel(api_key: str, channel_id: str) -> Optional[Dict[str, str]]:
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "eventType": "live",
        "type": "video",
        "maxResults": 1,
        "order": "date",
        "key": api_key,
    }
    try:
        resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") or []
        if not items:
            return None
        item = items[0]
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            return None
        snippet = item.get("snippet") or {}
        return {
            "videoId": video_id,
            "title": snippet.get("title", ""),
            "embedUrl": youtube_video_embed(video_id),
        }
    except requests.RequestException as exc:
        print(f"  Warning: YouTube API error for channel {channel_id}: {exc}")
        return None


def build_live_status(api_key: Optional[str], static_config: Dict[str, Any]) -> Dict[str, Any]:
    streams_status: Dict[str, Any] = {}
    checked_channels: Dict[str, Optional[Dict[str, str]]] = {}

    for stream in static_config.get("streams") or []:
        stream_id = stream["id"]
        channel_id = stream.get("youtubeChannelId") or ""
        if not channel_id or not api_key:
            streams_status[stream_id] = {"isLive": False}
            continue

        if channel_id not in checked_channels:
            checked_channels[channel_id] = fetch_live_for_channel(api_key, channel_id)
            time.sleep(REQUEST_DELAY)

        live = checked_channels[channel_id]
        if live:
            streams_status[stream_id] = {
                "isLive": True,
                "videoId": live["videoId"],
                "title": live["title"],
                "embedUrl": live["embedUrl"],
            }
            print(f"  LIVE: {stream.get('title')} ({live['videoId']})")
        else:
            streams_status[stream_id] = {"isLive": False}

    live_count = sum(1 for s in streams_status.values() if s.get("isLive"))
    print(f"Live streams detected: {live_count}")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "streams": streams_status,
    }


def main() -> None:
    print("Generating live streams config...")
    raw = load_livestreams_config()
    static_config = build_static_config(raw)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_OUT, "w", encoding="utf-8") as f:
        json.dump(static_config, f, indent=2)
    print(f"Wrote {CONFIG_OUT} ({len(static_config.get('streams', []))} streams)")

    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print("YOUTUBE_API_KEY not set — writing offline live_status.json")
    status = build_live_status(api_key or None, static_config)
    with open(STATUS_OUT, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    print(f"Wrote {STATUS_OUT}")


if __name__ == "__main__":
    main()
