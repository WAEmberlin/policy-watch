"""
YouTube URL parsing and live-stream helpers for PolicyWatch.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com")


def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return any(host == h.replace("www.", "") or host.endswith("." + h.replace("www.", "")) for h in YOUTUBE_HOSTS)
    except Exception:
        return "youtube.com" in url.lower() or "youtu.be" in url.lower()


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Return a YouTube video ID from common URL formats."""
    if not url:
        return None
    url = url.strip()
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None

    if "youtube.com" in host:
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2] or None
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/")[2] or None
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            return qs["v"][0]
        # /watch/v/VIDEO_ID style
        m = re.search(r"/(?:v|embed|live)/([A-Za-z0-9_-]{6,})", parsed.path)
        if m:
            return m.group(1)

    return None


def youtube_channel_live_embed(channel_id: str) -> str:
    return f"https://www.youtube.com/embed/live_stream?channel={channel_id}"


def youtube_video_embed(video_id: str) -> str:
    return f"https://www.youtube.com/embed/{video_id}"


def resolve_embed_url(
    *,
    embed_url: str = "",
    youtube_channel_id: str = "",
    youtube_video_id: str = "",
) -> str:
    if youtube_video_id:
        return youtube_video_embed(youtube_video_id)
    if embed_url:
        return embed_url
    if youtube_channel_id:
        return youtube_channel_live_embed(youtube_channel_id)
    return ""
