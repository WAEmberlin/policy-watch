"""Stream / embed enrichment for hearing records shown on the hearings page."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from processing.youtube_utils import extract_youtube_video_id, is_youtube_url, resolve_embed_url

SOURCE_STATE_HINTS = {
    "kansas": "KS",
    "colorado": "CO",
    "arizona": "AZ",
    "utah": "UT",
    "maine": "ME",
    "nebraska": "NE",
    "maryland": "MD",
    "pennsylvania": "PA",
}

_STREAM_NOTE_HINTS = ("stream", "video", "live", "watch", "broadcast", "webcast")
_MEDIA_CLASS_HINTS = ("video", "live", "stream", "webcast")


def infer_hearing_state(hearing: dict) -> str:
    state = hearing.get("state")
    if state and str(state).upper() not in ("FEDERAL", ""):
        return str(state).upper()
    if hearing.get("level") == "federal":
        return "Federal"
    source = (hearing.get("source") or "").lower()
    if "federal" in source or "congress" in source:
        return "Federal"
    for hint, code in SOURCE_STATE_HINTS.items():
        if hint in source:
            return code
    return ""


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s&]", " ", (value or "").lower())).strip()


def _chamber_mismatch(committee_text: str, stream_title: str) -> bool:
    committee = committee_text.lower()
    title = stream_title.lower()
    if "house" in title and "senate" in committee and "house" not in committee:
        return True
    if "senate" in title and "house" in committee and "senate" not in committee:
        return True
    return False


def _committee_matches(committee_text: str, stream: dict) -> bool:
    if not committee_text:
        return False
    title = stream.get("title") or ""
    if _chamber_mismatch(committee_text, title):
        return False

    norm_committee = _normalize_match_text(committee_text)
    keywords = stream.get("committee_keywords") or []
    if keywords:
        return any(_normalize_match_text(kw) in norm_committee for kw in keywords)

    norm_title = _normalize_match_text(title)
    if not norm_title:
        return False
    if norm_title in norm_committee or norm_committee in norm_title:
        return True

    title_tokens = [t for t in norm_title.split() if len(t) > 3 and t not in {"house", "senate", "committee", "colorado", "utah", "arizona", "maine", "kansas", "maryland", "nebraska", "pennsylvania"}]
    return any(token in norm_committee for token in title_tokens)


def _stream_watch_url(stream: dict) -> str:
    return (
        stream.get("youtube_url")
        or stream.get("external_url")
        or stream.get("embed_url")
        or ""
    )


def _stream_embed_url(stream: dict) -> str:
    return resolve_embed_url(
        embed_url=stream.get("embed_url") or "",
        youtube_channel_id=stream.get("youtube_channel_id") or "",
    )


def match_stream_for_hearing(
    hearing: dict,
    streams: List[dict],
    state_floor_map: Dict[str, str],
) -> Optional[dict]:
    state_key = infer_hearing_state(hearing)
    if not state_key:
        return None

    committee_text = hearing.get("committee") or hearing.get("committees") or ""
    state_streams = [s for s in streams if (s.get("state") or "").upper() == state_key]

    committee_streams = [s for s in state_streams if s.get("type") == "committee"]
    best: Optional[dict] = None
    best_score = 0
    for stream in committee_streams:
        if not _committee_matches(committee_text, stream):
            continue
        keywords = stream.get("committee_keywords") or []
        score = max((len(_normalize_match_text(kw)) for kw in keywords), default=0)
        score += len(_normalize_match_text(stream.get("title") or ""))
        if score >= best_score:
            best = stream
            best_score = score
    if best:
        return best

    if state_key == "Federal":
        chamber = (hearing.get("chamber") or "").lower()
        floor_id = "us-senate-floor" if "senate" in chamber else state_floor_map.get("Federal", "us-house-floor")
    else:
        floor_id = state_floor_map.get(state_key)

    if not floor_id:
        return None
    return next((s for s in state_streams if s.get("id") == floor_id), None)


def enrich_hearing_stream(
    hearing: dict,
    *,
    state_floor_map: Dict[str, str],
    streams: Optional[List[dict]] = None,
) -> dict:
    """Add stream_url, embed_url, youtube_video_id, and livestream_id for the hearings UI."""
    enriched = dict(hearing)
    streams = streams or []
    stream_url = enriched.get("stream_url") or ""
    link = enriched.get("link") or enriched.get("url") or ""

    if not stream_url and is_youtube_url(link):
        stream_url = link
    if stream_url:
        enriched["stream_url"] = stream_url

    video_id = extract_youtube_video_id(stream_url) or extract_youtube_video_id(link)
    if video_id:
        enriched["youtube_video_id"] = video_id
        enriched["embed_url"] = resolve_embed_url(youtube_video_id=video_id)

    matched = match_stream_for_hearing(enriched, streams, state_floor_map)
    if matched:
        if not enriched.get("embed_url"):
            embed = _stream_embed_url(matched)
            if embed:
                enriched["embed_url"] = embed
        if not enriched.get("stream_url"):
            watch = _stream_watch_url(matched)
            if watch:
                enriched["stream_url"] = watch

        stream_id = matched.get("id") or ""
        if matched.get("type") == "committee" and not enriched.get("embed_url"):
            floor = match_stream_for_hearing(
                {**enriched, "committee": "", "committees": ""},
                streams,
                state_floor_map,
            )
            if floor:
                stream_id = floor.get("id") or stream_id
                floor_embed = _stream_embed_url(floor)
                if floor_embed:
                    enriched["embed_url"] = floor_embed
                if not enriched.get("stream_url"):
                    floor_watch = _stream_watch_url(floor)
                    if floor_watch:
                        enriched["stream_url"] = floor_watch
        enriched["livestream_id"] = stream_id

    if not enriched.get("state"):
        state_key = infer_hearing_state(enriched)
        if state_key and state_key != "Federal":
            enriched["state"] = state_key

    return enriched
