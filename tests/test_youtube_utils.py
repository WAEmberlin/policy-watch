"""Tests for YouTube URL parsing helpers."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.youtube_utils import (
    extract_youtube_video_id,
    is_youtube_url,
    resolve_embed_url,
    youtube_channel_live_embed,
    youtube_video_embed,
)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/abc123XYZ_-9", "abc123XYZ_-9"),
    ],
)
def test_extract_youtube_video_id(url, expected):
    assert extract_youtube_video_id(url) == expected


def test_is_youtube_url():
    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert not is_youtube_url("https://leg.colorado.gov/watch-and-listen")


def test_resolve_embed_url_priority():
    assert resolve_embed_url(youtube_video_id="vid123") == youtube_video_embed("vid123")
    assert resolve_embed_url(embed_url="https://live.house.gov/") == "https://live.house.gov/"
    assert resolve_embed_url(youtube_channel_id="UCabc") == youtube_channel_live_embed("UCabc")
