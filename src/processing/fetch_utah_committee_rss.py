#!/usr/bin/env python3
"""
Fetch Utah Legislature committee hearing schedules via the official committee RSS feed.

The feed is built from committee IDs configured in config/state_feeds.yaml:
  https://le.utah.gov/asp/billtrack/comrssfeed.asp?com=INTBUS|HSTBUS|...

When a hearing links to an interim notice page, fetches DATE/TIME/PLACE and the
committee livestream page during the RSS pull (cached in committee_hearings.json).

Writes:
  - data/utah/committee_hearings.json
  - src/output/history.json (upcoming committee meeting notices)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import feedparser
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.feed_history_utils import merge_with_history, save_history  # noqa: E402
from processing.utah_notice_utils import (  # noqa: E402
    agenda_preview,
    fetch_notice_details,
    filter_agenda_items,
    is_interim_notice_url,
)

CONFIG_PATH = ROOT / "config" / "state_feeds.yaml"
OUTPUT_FILE = ROOT / "data" / "utah" / "committee_hearings.json"

NOTICE_ENRICHMENT_FIELDS = (
    "notice_date",
    "notice_time",
    "notice_place",
    "livestream_url",
    "stream_url",
)
NOTICE_CACHE_FIELDS = NOTICE_ENRICHMENT_FIELDS + ("notice_enriched_at",)
NOTICE_FETCH_RETRY_HOURS = 24

SESSION_BLOCK_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*-\s*(?P<location>.+)$",
    re.IGNORECASE,
)
COMMITTEE_CODE_RE = re.compile(r"[?&]com=([A-Z0-9]+)")
SESSION_YEAR_RE = re.compile(r"/Interim/(\d{4})/", re.IGNORECASE)


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("utah_committee_rss", {})


def build_feed_url(cfg: Dict[str, Any]) -> str:
    committee_ids = cfg.get("committee_ids") or []
    com_param = "|".join(committee_ids)
    feed_path = cfg.get("feed_path", "https://le.utah.gov/asp/billtrack/comrssfeed.asp")
    return f"{feed_path}?com={com_param}"


def parse_committee_code(link: str) -> str:
    match = COMMITTEE_CODE_RE.search(link or "")
    return match.group(1) if match else ""


def session_year_from_urls(*urls: str) -> str:
    for url in urls:
        match = SESSION_YEAR_RE.search(url or "")
        if match:
            return match.group(1)
    return str(datetime.now().year)


def parse_session_block(header_text: str) -> Optional[Tuple[str, str, str]]:
    text = " ".join(header_text.split())
    match = SESSION_BLOCK_RE.match(text)
    if not match:
        return None
    date_part = match.group("date")
    time_part = match.group("time")
    location = match.group("location").strip()
    try:
        dt = datetime.strptime(f"{date_part} {time_part}", "%m/%d/%Y %I:%M:%S %p")
        scheduled_iso = dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        try:
            dt = datetime.strptime(date_part, "%m/%d/%Y")
            scheduled_iso = dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            scheduled_iso = ""
    return scheduled_iso, location, date_part


def normalize_notice_url(url: str) -> str:
    """Normalize notice URLs so http/https variants share one cache entry."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
    netloc = parsed.netloc.lower()
    path = parsed.path or ""
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def extract_notice_enrichment(item: Dict[str, Any]) -> Dict[str, str]:
    livestream = item.get("livestream_url") or item.get("stream_url") or ""
    return {
        "notice_date": item.get("notice_date", ""),
        "notice_time": item.get("notice_time", ""),
        "notice_place": item.get("notice_place", ""),
        "livestream_url": livestream,
        "stream_url": item.get("stream_url") or livestream,
        "notice_enriched_at": item.get("notice_enriched_at", ""),
    }


def has_notice_enrichment(details: Dict[str, str]) -> bool:
    return any(details.get(field) for field in NOTICE_ENRICHMENT_FIELDS)


def parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_upcoming_hearing(hearing: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    scheduled = hearing.get("scheduled_date") or ""
    scheduled_dt = parse_iso_datetime(scheduled)
    if scheduled_dt is None:
        return True
    current = now or datetime.now(timezone.utc)
    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
    return scheduled_dt.date() >= current.date()


def notice_cache_is_fresh(
    cached: Dict[str, str],
    *,
    now: Optional[datetime] = None,
    retry_hours: int = NOTICE_FETCH_RETRY_HOURS,
) -> bool:
    if has_notice_enrichment(cached):
        return True
    enriched_at = parse_iso_datetime(cached.get("notice_enriched_at", ""))
    if enriched_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    return current - enriched_at < timedelta(hours=retry_hours)


def apply_notice_enrichment(hearing: Dict[str, Any], details: Dict[str, str]) -> None:
    for field in NOTICE_CACHE_FIELDS:
        if details.get(field):
            hearing[field] = details[field]
    stream_url = details.get("livestream_url") or details.get("stream_url") or ""
    if stream_url:
        hearing["stream_url"] = stream_url


def load_notice_cache() -> Dict[str, Dict[str, str]]:
    if not OUTPUT_FILE.exists():
        return {}
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        payload = json.load(f)
    cache: Dict[str, Dict[str, str]] = {}
    for item in payload.get("items", []):
        notice_url = normalize_notice_url(item.get("link") or item.get("url") or "")
        if not notice_url:
            continue
        details = extract_notice_enrichment(item)
        if not has_notice_enrichment(details) and not details.get("notice_enriched_at"):
            continue
        existing = cache.get(notice_url, {})
        if has_notice_enrichment(details) or not existing:
            cache[notice_url] = details
    return cache


def enrich_hearing_from_notice(
    hearing: Dict[str, Any],
    notice_cache: Dict[str, Dict[str, str]],
    *,
    fetch_missing: bool = True,
    now: Optional[datetime] = None,
) -> bool:
    """Apply cached notice details or fetch interim pages for new upcoming hearings."""
    notice_url = normalize_notice_url(hearing.get("link") or hearing.get("url") or "")
    if not notice_url:
        return False

    current = now or datetime.now(timezone.utc)
    cached = notice_cache.get(notice_url, {})
    if notice_cache_is_fresh(cached, now=current):
        apply_notice_enrichment(hearing, cached)
        return False

    if not fetch_missing or not is_interim_notice_url(notice_url):
        if cached:
            apply_notice_enrichment(hearing, cached)
        return False

    if not is_upcoming_hearing(hearing, now=current):
        if cached:
            apply_notice_enrichment(hearing, cached)
        return False

    committee_code = hearing.get("committee_code", "")
    session_year = session_year_from_urls(notice_url, hearing.get("committee_link", ""))
    details = extract_notice_enrichment(
        fetch_notice_details(
            notice_url,
            committee_code=committee_code,
            session_year=session_year,
        )
    )
    details["notice_enriched_at"] = current.isoformat()
    apply_notice_enrichment(hearing, details)
    notice_cache[notice_url] = details
    return True


def apply_hearing_fields_to_history(hearing: Dict[str, Any], history_item: Dict[str, Any]) -> None:
    preview = agenda_preview(
        hearing.get("agenda_items") or [],
        fallback=hearing.get("description", ""),
    )
    history_item["summary"] = preview
    history_item["agenda_items"] = hearing.get("agenda_items") or []
    for field in ("notice_date", "notice_time", "notice_place", "livestream_url", "stream_url", "location"):
        if hearing.get(field):
            history_item[field] = hearing[field]
    if hearing.get("livestream_url"):
        history_item["stream_url"] = hearing["livestream_url"]


def parse_committee_entry(entry: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (hearing records, history feed items) for one RSS entry."""
    committee = entry.get("title", "Utah Committee").strip()
    committee_link = entry.get("link", "")
    committee_code = parse_committee_code(committee_link)
    summary_html = entry.get("summary") or entry.get("description") or ""

    hearings: List[Dict[str, Any]] = []
    history_items: List[Dict[str, Any]] = []

    if not summary_html.strip():
        return hearings, history_items

    soup = BeautifulSoup(summary_html, "html.parser")
    for bold in soup.find_all("b"):
        block = parse_session_block(bold.get_text(" ", strip=True))
        if not block:
            continue
        scheduled_iso, location, date_part = block
        ul = bold.find_next_sibling("ul")
        raw_agenda_items: List[str] = []
        notice_url = committee_link
        if ul:
            for li in ul.find_all("li"):
                text = li.get_text(" ", strip=True)
                anchor = li.find("a", href=True)
                if anchor and "NOTICE" in text.upper():
                    notice_url = anchor["href"]
                    continue
                if text:
                    raw_agenda_items.append(text)

        agenda_items = filter_agenda_items(raw_agenda_items)
        description = agenda_preview(agenda_items, fallback="Committee meeting scheduled")
        title = f"{committee} — {date_part}"
        hearing = {
            "title": title,
            "scheduled_date": scheduled_iso,
            "scheduled_time": "",
            "location": location,
            "committees": committee,
            "committee": committee,
            "committee_code": committee_code,
            "committee_link": committee_link,
            "link": notice_url or committee_link,
            "url": notice_url or committee_link,
            "stream_url": "",
            "source": "State (Utah)",
            "state": "UT",
            "level": "state",
            "description": description,
            "agenda_items": agenda_items,
            "feed": "utah_committee_rss",
            "notice_date": "",
            "notice_time": "",
            "notice_place": "",
            "livestream_url": "",
        }
        hearings.append(hearing)

        digest = md5(f"{committee_code}|{scheduled_iso}|{description}".encode()).hexdigest()[:12]
        item_id = f"ut-rss:{committee_code}:{scheduled_iso}:{digest}"
        history_item = {
            "id": item_id,
            "title": title,
            "summary": description,
            "link": notice_url or committee_link,
            "published": scheduled_iso or datetime.now(timezone.utc).isoformat(),
            "source": "State (Utah)",
            "category": "Committee",
            "type": "state_hearing",
            "state": "UT",
            "feed": "utah_committee_rss",
            "committee": committee,
            "location": location,
            "agenda_items": agenda_items,
        }
        history_items.append(history_item)

    return hearings, history_items


def main() -> None:
    cfg = load_config()
    feed_url = build_feed_url(cfg)
    print(f"Fetching Utah committee RSS ({len(cfg.get('committee_ids') or [])} committees)...")

    feed = feedparser.parse(feed_url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"Utah RSS parse error: {feed.bozo_exception}")

    notice_cache = load_notice_cache()
    cached_notice_urls = set(notice_cache)
    all_hearings: List[Dict[str, Any]] = []
    all_history: List[Dict[str, Any]] = []
    fetched_notices = 0
    reused_notices = 0
    now = datetime.now(timezone.utc)

    for entry in feed.entries:
        entry_dict = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary") or entry.get("description") or "",
        }
        hearings, history_items = parse_committee_entry(entry_dict)
        for hearing, history_item in zip(hearings, history_items):
            notice_url = normalize_notice_url(hearing.get("link") or hearing.get("url") or "")
            was_cached = notice_url in cached_notice_urls and notice_cache_is_fresh(
                notice_cache.get(notice_url, {}),
                now=now,
            )
            if enrich_hearing_from_notice(hearing, notice_cache, now=now):
                fetched_notices += 1
            elif was_cached:
                reused_notices += 1
            apply_hearing_fields_to_history(hearing, history_item)
        all_hearings.extend(hearings)
        all_history.extend(history_items)

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "last_fetched": now,
        "feed_url": feed_url,
        "entry_count": len(feed.entries),
        "hearing_count": len(all_hearings),
        "items": all_hearings,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(
        f"Parsed {len(all_hearings)} Utah committee hearing blocks from {len(feed.entries)} RSS entries"
    )
    if reused_notices or fetched_notices:
        print(
            f"Notice enrichment: {reused_notices} reused from cache, "
            f"{fetched_notices} newly fetched"
        )

    if all_history:
        combined = merge_with_history(all_history)
        combined.sort(key=lambda x: x.get("published", ""), reverse=True)
        save_history(combined)

    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
