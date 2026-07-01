"""
Fetch Kansas Legislature House and Senate calendar RSS feeds.

Produces a list of calendar entries by date for display on the hearings page.
RSS feeds: https://www.kslegislature.gov/li/data/feeds/rss/calendar/house/
           https://www.kslegislature.gov/li/data/feeds/rss/calendar/senate/
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import feedparser

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CALENDARS_FILE = OUTPUT_DIR / "kansas_calendars.json"

# Kansas Legislature calendar RSS feeds (2025-26 biennium paths)
CALENDAR_FEEDS = {
    "house": "https://www.kslegislature.gov/b2025_26/feeds/rss/calendar/house/",
    "senate": "https://www.kslegislature.gov/b2025_26/feeds/rss/calendar/senate/",
}


def parse_calendar_date_from_title(title: str, link: str) -> Optional[str]:
    """
    Extract YYYY-MM-DD from calendar title or link.
    Title examples: "House Calendar for Monday January 13, 2025"
    Link examples: http://kslegislature.org/li/chamber/house/calendar/2025/1/13/
    """
    # Prefer link: .../calendar/YEAR/MONTH/DAY/
    link_match = re.search(r"/calendar/(\d{4})/(\d{1,2})/(\d{1,2})", link)
    if link_match:
        y, m, d = link_match.group(1), link_match.group(2), link_match.group(3)
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # Fallback: parse title "House Calendar for Monday January 13, 2025"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    title_lower = title.lower()
    year_match = re.search(r"\b(20\d{2})\b", title)
    if not year_match:
        return None
    year = year_match.group(1)
    for name, num in months.items():
        if name in title_lower:
            # Find day number (e.g. "13," or "13")
            day_match = re.search(rf"{name}\s+(\d{{1,2}})", title_lower)
            if day_match:
                return f"{year}-{num:02d}-{int(day_match.group(1)):02d}"
    return None


def normalize_calendar_link(link: str) -> str:
    """Use www.kslegislature.gov for consistency; calendar page may link to PDF."""
    if not link:
        return link
    link = link.strip()
    if link.startswith("http://kslegislature.org"):
        link = link.replace("http://kslegislature.org", "https://www.kslegislature.gov", 1)
    elif link.startswith("https://kslegislature.gov"):
        link = link.replace("https://kslegislature.gov", "https://www.kslegislature.gov", 1)
    return link


def fetch_calendar_feed(url: str, chamber: str) -> List[Dict]:
    """Fetch one calendar RSS feed and return normalized entries."""
    entries = []
    try:
        parsed = feedparser.parse(url)
        for entry in parsed.get("entries", []):
            title = (entry.get("title") or "").strip()
            link = entry.get("link") or ""
            if not title or not link:
                continue
            date_str = parse_calendar_date_from_title(title, link)
            if not date_str:
                continue
            link = normalize_calendar_link(link)
            entries.append({
                "date": date_str,
                "title": title,
                "link": link,
                "chamber": chamber,
            })
    except Exception as e:
        print(f"Error fetching {chamber} calendar: {e}")
    return entries


def fetch_all_calendars() -> Dict[str, List[Dict]]:
    """
    Fetch House and Senate calendar feeds and return by date.
    Returns: { "2025-01-13": [ { date, title, link, chamber }, ... ], ... }
    """
    by_date = {}
    for chamber, url in CALENDAR_FEEDS.items():
        chamber_name = chamber.capitalize()
        print(f"Fetching {chamber_name} calendar RSS...")
        entries = fetch_calendar_feed(url, chamber_name)
        print(f"  Got {len(entries)} {chamber_name} calendar entries")
        for e in entries:
            d = e["date"]
            if d not in by_date:
                by_date[d] = []
            # Dedupe by chamber for this date
            if not any(x.get("chamber") == chamber_name for x in by_date[d]):
                by_date[d].append(e)
    return by_date


def main():
    by_date = fetch_all_calendars()
    # Sort keys for stable output
    out = {k: by_date[k] for k in sorted(by_date.keys(), reverse=True)}
    with open(CALENDARS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(out)} dates to {CALENDARS_FILE}")


if __name__ == "__main__":
    main()
