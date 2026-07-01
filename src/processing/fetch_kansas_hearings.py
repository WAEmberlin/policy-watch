#!/usr/bin/env python3
"""
Fetch Kansas committee hearings from the official REST API.

During session, /api/v1/hearings/ and /api/v1/now/ cover standing committee
schedules. Between sessions the API often returns zero upcoming rows even though
special/select committees still meet and stream on YouTube. This module also:

- Scans paginated /hearings/ for future-dated rows the upcoming flag misses
- Lists active special/select committees marked On Call (interim authority)
- Synthesizes live hearing cards from docs/live_status.json + livestreams.yaml
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.kansas_api_client import KansasApiClient  # noqa: E402

KANSAS_BIENNIUM = "b2025_26"
OUTPUT_FILE = ROOT / "data" / "kansas" / "hearings.json"
LIVE_STATUS_FILE = ROOT / "docs" / "live_status.json"
LIVESTREAMS_FILE = ROOT / "config" / "livestreams.yaml"
PAGE_SIZE = 100
MAX_PAGES = 20
INTERIM_COMMITTEE_TYPES = frozenset({"Special", "Select"})


def _committee_page_url(committee_kpid: str) -> str:
    if not committee_kpid:
        return "https://www.kslegislature.gov/"
    return f"https://www.kslegislature.gov/{KANSAS_BIENNIUM}/committees/{committee_kpid}/"


def _hearing_dedupe_key(hearing: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        hearing.get("title"),
        (hearing.get("scheduled_date") or "")[:10],
        hearing.get("committee_kpid") or hearing.get("committees"),
    )


def _merge_hearings(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: Set[Tuple[Any, ...]] = set()
    for group in groups:
        for hearing in group:
            key = _hearing_dedupe_key(hearing)
            if key in seen:
                continue
            seen.add(key)
            merged.append(hearing)
    merged.sort(key=lambda h: h.get("scheduled_date") or "")
    return merged


def api_hearing_to_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map Kansas API hearing payload to site_data hearing shape."""
    bills = raw.get("bill_numbers") or []
    bill_str = ", ".join(bills) if bills else ""
    committee = raw.get("committee_title") or raw.get("committee") or "Committee hearing"
    hearing_type = (raw.get("hearing_type") or "").strip().rstrip(":")
    title_parts = [p for p in [hearing_type, bill_str or committee] if p]
    title = " ".join(title_parts) if title_parts else committee

    hearing_date = raw.get("hearing_date") or ""
    hearing_time = raw.get("hearing_time") or ""
    scheduled_date = raw.get("hearing_datetime") or hearing_date
    if scheduled_date and "T" not in scheduled_date and hearing_date:
        scheduled_date = hearing_date

    stream_url = raw.get("stream_url") or raw.get("streaming") or ""
    committee_kpid = raw.get("committee_kpid") or ""
    page_url = raw.get("url") or _committee_page_url(committee_kpid)

    return {
        "title": title,
        "scheduled_date": scheduled_date,
        "scheduled_time": hearing_time,
        "location": raw.get("room") or raw.get("location") or "",
        "committees": committee,
        "committee": committee,
        "bill": bill_str,
        "link": page_url,
        "url": page_url,
        "stream_url": stream_url,
        "source": "State (Kansas Legislature)",
        "state": "KS",
        "level": "state",
        "chamber": raw.get("chamber") or "",
        "status": raw.get("status") or "",
        "is_past": raw.get("is_past"),
        "committee_kpid": committee_kpid,
    }


def _now_committee_to_record(entry: Dict[str, Any], *, kind: str) -> Optional[Dict[str, Any]]:
    """Convert /now/ committee or conference entry to a hearing record."""
    committee = entry.get("committee_title") or entry.get("title") or entry.get("name") or ""
    if not committee and kind == "conference":
        committee = entry.get("committees") or "Conference Committee"
    if not committee:
        return None

    today = date.today().isoformat()
    hearing_time = entry.get("time") or entry.get("hearing_time") or entry.get("mtg_time") or ""
    room = entry.get("room") or entry.get("location") or ""
    stream_url = entry.get("stream_url") or entry.get("streaming") or ""
    committee_kpid = entry.get("committee_kpid") or entry.get("kpid") or ""
    bills = entry.get("bill_numbers") or entry.get("bills") or []
    bill_str = ", ".join(bills) if isinstance(bills, list) else str(bills or "")

    title = committee
    if bill_str:
        title = f"{committee} — {bill_str}"

    return {
        "title": title,
        "scheduled_date": today,
        "scheduled_time": hearing_time,
        "location": room,
        "committees": committee,
        "committee": committee,
        "bill": bill_str,
        "link": entry.get("url") or _committee_page_url(committee_kpid),
        "url": entry.get("url") or _committee_page_url(committee_kpid),
        "stream_url": stream_url,
        "source": "State (Kansas Legislature)",
        "state": "KS",
        "level": "state",
        "chamber": entry.get("chamber") or "",
        "status": "in_session",
        "now_snapshot": True,
        "committee_kpid": committee_kpid,
    }


def _is_adjourned(now_snapshot: Dict[str, Any]) -> bool:
    chambers = now_snapshot.get("chambers") or {}
    statuses = [
        (chambers.get(ch, {}).get("status") or "").lower()
        for ch in ("house", "senate")
        if isinstance(chambers.get(ch), dict)
    ]
    if not statuses:
        return False
    return all("adjourn" in s for s in statuses)


def fetch_upcoming_hearings(client: KansasApiClient) -> List[Dict[str, Any]]:
    """Paginate /hearings/ for upcoming and near-future schedules."""
    today = date.today()
    horizon = today + timedelta(days=45)
    seen_ids: set = set()
    records: List[Dict[str, Any]] = []

    def ingest_page(params: Dict[str, Any]) -> int:
        added = 0
        for page in range(MAX_PAGES):
            payload = client.list_hearings(limit=PAGE_SIZE, offset=page * PAGE_SIZE, **params)
            batch = payload.get("results") or []
            if not batch:
                break
            for raw in batch:
                key = (
                    raw.get("committee_kpid"),
                    raw.get("hearing_datetime") or raw.get("hearing_date"),
                    tuple(raw.get("bill_numbers") or []),
                )
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                record = api_hearing_to_record(raw)
                if raw.get("is_past") is True:
                    continue
                scheduled = record.get("scheduled_date") or ""
                if scheduled and scheduled[:10] < today.isoformat():
                    continue
                records.append(record)
                added += 1
            if len(batch) < PAGE_SIZE:
                break
        return added

    upcoming_count = ingest_page({"upcoming": True})
    range_count = ingest_page({"from_date": today.isoformat(), "to_date": horizon.isoformat()})
    print(f"Kansas API hearings: {upcoming_count} upcoming flag, {range_count} in date range, {len(records)} unique")
    return records


def fetch_future_hearings_scan(client: KansasApiClient) -> List[Dict[str, Any]]:
    """Scan all /hearings/ pages for future-dated rows (API omits upcoming=true off-session)."""
    today = date.today().isoformat()
    seen_ids: set = set()
    records: List[Dict[str, Any]] = []

    for page in range(MAX_PAGES):
        payload = client.list_hearings(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
        batch = payload.get("results") or []
        if not batch:
            break
        for raw in batch:
            if raw.get("is_past") is True:
                continue
            hearing_date = raw.get("hearing_date") or (raw.get("hearing_datetime") or "")[:10]
            if hearing_date and hearing_date < today:
                continue
            key = (
                raw.get("committee_kpid"),
                raw.get("hearing_datetime") or raw.get("hearing_date"),
                tuple(raw.get("bill_numbers") or []),
            )
            if key in seen_ids:
                continue
            seen_ids.add(key)
            records.append(api_hearing_to_record(raw))
        total = payload.get("count") or 0
        if len(batch) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= total:
            break

    if records:
        print(f"Kansas API future scan: {len(records)} non-past hearing(s)")
    return records


def interim_committee_to_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map an active special/select On Call committee to an interim placeholder."""
    committee = raw.get("display_name") or raw.get("title") or "Interim committee"
    committee_kpid = raw.get("kpid") or ""
    mtg_time = (raw.get("mtg_time") or "On Call").strip()
    page_url = _committee_page_url(committee_kpid)

    return {
        "title": f"{committee} (Interim — On Call)",
        "scheduled_date": "",
        "scheduled_time": mtg_time,
        "location": raw.get("mtg_room") or "",
        "committees": committee,
        "committee": committee,
        "bill": "",
        "link": page_url,
        "url": page_url,
        "stream_url": "",
        "source": "State (Kansas Legislature)",
        "state": "KS",
        "level": "state",
        "chamber": raw.get("chamber") or "",
        "status": "interim_on_call",
        "committee_kpid": committee_kpid,
        "interim_placeholder": True,
    }


def fetch_interim_committees(client: KansasApiClient, now_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Active special/select committees authorized to meet between sessions."""
    if not _is_adjourned(now_snapshot):
        return []

    payload = client.list_committees(status="Active", limit=100)
    records: List[Dict[str, Any]] = []
    for raw in payload.get("results") or []:
        if raw.get("committee_type") not in INTERIM_COMMITTEE_TYPES:
            continue
        mtg_time = (raw.get("mtg_time") or "").strip().lower()
        if mtg_time != "on call":
            continue
        records.append(interim_committee_to_record(raw))

    if records:
        print(f"Kansas interim committees: {len(records)} active On Call special/select committee(s)")
    return records


def fetch_now_hearings(client: KansasApiClient) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Same-day committees/conference meetings from /now/."""
    snapshot = client.get_now()
    if not snapshot:
        return [], {}

    records: List[Dict[str, Any]] = []
    for entry in snapshot.get("committees_in_session") or []:
        if isinstance(entry, dict):
            rec = _now_committee_to_record(entry, kind="committee")
            if rec:
                records.append(rec)

    for entry in snapshot.get("conference_committees_today") or []:
        if isinstance(entry, dict):
            rec = _now_committee_to_record(entry, kind="conference")
            if rec:
                records.append(rec)

    if records:
        print(f"Kansas /now/ snapshot: {len(records)} same-day hearing(s)")
    return records, snapshot


def _load_livestreams() -> List[Dict[str, Any]]:
    if not LIVESTREAMS_FILE.exists():
        return []
    try:
        import yaml

        with open(LIVESTREAMS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return list(data.get("streams") or [])
    except Exception as exc:
        print(f"Warning: Could not load livestreams config: {exc}")
        return []


def _load_live_status() -> Dict[str, Any]:
    if not LIVE_STATUS_FILE.exists():
        return {}
    try:
        with open(LIVE_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: Could not load live_status.json: {exc}")
        return {}


def _text_overlap(a: str, b: str) -> bool:
    a_norm = a.lower().strip()
    b_norm = b.lower().strip()
    if not a_norm or not b_norm:
        return False
    return a_norm in b_norm or b_norm in a_norm


def _has_matching_live_hearing(
    existing: List[Dict[str, Any]],
    *,
    today: str,
    stream_id: str,
    committee_kpid: str,
    stream_title: str,
    video_title: str,
) -> bool:
    for hearing in existing:
        if hearing.get("interim_placeholder"):
            continue
        scheduled = (hearing.get("scheduled_date") or "")[:10]
        if scheduled and scheduled != today and not hearing.get("is_live_synthetic"):
            continue
        if hearing.get("livestream_id") == stream_id:
            return True
        if committee_kpid and hearing.get("committee_kpid") == committee_kpid:
            return True
        committee = hearing.get("committee") or hearing.get("committees") or ""
        if _text_overlap(committee, video_title) or _text_overlap(committee, stream_title):
            return True
        if _text_overlap(stream_title, hearing.get("title") or ""):
            return True
    return False


def live_stream_to_hearing(
    stream: Dict[str, Any],
    live_info: Dict[str, Any],
    *,
    today: str,
) -> Dict[str, Any]:
    """Build a synthetic hearing card for a Kansas stream that is live on YouTube."""
    video_title = (live_info.get("title") or "").strip()
    stream_title = (stream.get("title") or stream.get("id") or "Kansas Legislature").strip()
    committee_kpid = stream.get("committee_kpid") or ""
    title = video_title or f"{stream_title} — Live now"

    embed_url = live_info.get("embedUrl") or ""
    video_id = live_info.get("videoId") or ""
    watch_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""

    return {
        "title": title,
        "scheduled_date": today,
        "scheduled_time": "Live now",
        "location": "",
        "committees": stream_title,
        "committee": stream_title,
        "bill": "",
        "link": watch_url or _committee_page_url(committee_kpid),
        "url": _committee_page_url(committee_kpid) if committee_kpid else watch_url,
        "stream_url": watch_url,
        "embed_url": embed_url,
        "youtube_video_id": video_id,
        "livestream_id": stream.get("id") or "",
        "source": "State (Kansas Legislature)",
        "state": "KS",
        "level": "state",
        "chamber": stream.get("chamber") or "",
        "status": "live_now",
        "committee_kpid": committee_kpid,
        "is_live_synthetic": True,
    }


def synthesize_live_hearings(existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create hearing records when YouTube shows a KS stream live but no card exists."""
    live_status = _load_live_status()
    streams = _load_livestreams()
    if not live_status or not streams:
        return []

    today = date.today().isoformat()
    stream_status = live_status.get("streams") or {}
    live_by_video: Dict[str, Dict[str, Any]] = {}

    for stream in streams:
        if (stream.get("state") or "").upper() != "KS":
            continue
        stream_id = stream.get("id") or ""
        live_info = stream_status.get(stream_id) or {}
        if not live_info.get("isLive"):
            continue
        video_id = live_info.get("videoId") or stream_id
        current = live_by_video.get(video_id)
        if not current:
            live_by_video[video_id] = {"stream": stream, "live": live_info}
            continue
        # Prefer committee stream metadata over floor when sharing one YouTube channel.
        if stream.get("type") == "committee" and current["stream"].get("type") != "committee":
            live_by_video[video_id] = {"stream": stream, "live": live_info}

    synthesized: List[Dict[str, Any]] = []
    for entry in live_by_video.values():
        stream = entry["stream"]
        live_info = entry["live"]
        stream_id = stream.get("id") or ""
        committee_kpid = stream.get("committee_kpid") or ""
        stream_title = stream.get("title") or stream_id
        video_title = live_info.get("title") or ""

        if _has_matching_live_hearing(
            existing + synthesized,
            today=today,
            stream_id=stream_id,
            committee_kpid=committee_kpid,
            stream_title=stream_title,
            video_title=video_title,
        ):
            continue

        synthesized.append(live_stream_to_hearing(stream, live_info, today=today))

    if synthesized:
        print(f"Kansas live synthesis: {len(synthesized)} hearing(s) from YouTube live status")
    return synthesized


def main() -> None:
    client = KansasApiClient()
    upcoming = fetch_upcoming_hearings(client)
    future_scan = fetch_future_hearings_scan(client)
    now_today, now_snapshot = fetch_now_hearings(client)
    interim = fetch_interim_committees(client, now_snapshot)

    base = _merge_hearings(upcoming, future_scan, now_today, interim)
    live_synthetic = synthesize_live_hearings(base)
    merged = _merge_hearings(base, live_synthetic)

    payload = {
        "_meta": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": "kansas_api",
            "upcoming_count": len(merged),
            "live_synthetic_count": len(live_synthetic),
            "interim_on_call_count": len(interim),
        },
        "items": merged,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(merged)} Kansas hearings to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
