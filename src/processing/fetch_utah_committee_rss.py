#!/usr/bin/env python3
"""
Fetch Utah Legislature committee hearing schedules via the official committee RSS feed.

The feed is built from committee IDs configured in config/state_feeds.yaml:
  https://le.utah.gov/asp/billtrack/comrssfeed.asp?com=INTBUS|HSTBUS|...

Writes:
  - data/utah/committee_hearings.json
  - src/output/history.json (upcoming committee meeting notices)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import feedparser
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.feed_history_utils import merge_with_history, save_history  # noqa: E402

CONFIG_PATH = ROOT / "config" / "state_feeds.yaml"
OUTPUT_FILE = ROOT / "data" / "utah" / "committee_hearings.json"

SESSION_BLOCK_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<time>\d{1,2}:\d{2}:\d{2}\s*[AP]M)\s*-\s*(?P<location>.+)$",
    re.IGNORECASE,
)
COMMITTEE_CODE_RE = re.compile(r"[?&]com=([A-Z0-9]+)")


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
        agenda_items: List[str] = []
        notice_url = committee_link
        if ul:
            for li in ul.find_all("li"):
                text = li.get_text(" ", strip=True)
                if text:
                    agenda_items.append(text)
                anchor = li.find("a", href=True)
                if anchor and "NOTICE" in text.upper():
                    notice_url = anchor["href"]

        agenda_preview = "; ".join(agenda_items[:3]) if agenda_items else "Committee meeting scheduled"
        title = f"{committee} — {date_part}"
        hearing = {
            "title": title,
            "scheduled_date": scheduled_iso,
            "scheduled_time": "",
            "location": location,
            "committees": committee,
            "committee": committee,
            "committee_code": committee_code,
            "link": notice_url or committee_link,
            "url": notice_url or committee_link,
            "stream_url": "",
            "source": "State (Utah)",
            "state": "UT",
            "level": "state",
            "description": agenda_preview,
            "agenda_items": agenda_items,
            "feed": "utah_committee_rss",
        }
        hearings.append(hearing)

        digest = md5(f"{committee_code}|{scheduled_iso}|{agenda_preview}".encode()).hexdigest()[:12]
        item_id = f"ut-rss:{committee_code}:{scheduled_iso}:{digest}"
        history_items.append({
            "id": item_id,
            "title": title,
            "summary": agenda_preview,
            "link": notice_url or committee_link,
            "published": scheduled_iso or datetime.now(timezone.utc).isoformat(),
            "source": "State (Utah)",
            "category": "Committee",
            "type": "state_hearing",
            "state": "UT",
            "feed": "utah_committee_rss",
            "committee": committee,
            "location": location,
        })

    return hearings, history_items


def main() -> None:
    cfg = load_config()
    feed_url = build_feed_url(cfg)
    print(f"Fetching Utah committee RSS ({len(cfg.get('committee_ids') or [])} committees)...")

    feed = feedparser.parse(feed_url)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"Utah RSS parse error: {feed.bozo_exception}")

    all_hearings: List[Dict[str, Any]] = []
    all_history: List[Dict[str, Any]] = []
    for entry in feed.entries:
        entry_dict = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary") or entry.get("description") or "",
        }
        hearings, history_items = parse_committee_entry(entry_dict)
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

    print(f"Parsed {len(all_hearings)} Utah committee hearing blocks from {len(feed.entries)} RSS entries")

    if all_history:
        combined = merge_with_history(all_history)
        combined.sort(key=lambda x: x.get("published", ""), reverse=True)
        save_history(combined)

    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
