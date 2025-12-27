import feedparser
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ITEMS_FILE = OUTPUT_DIR / "items.json"
HISTORY_FILE = OUTPUT_DIR / "history.json"

FEEDS = {
    "Kansas Legislature": "https://www.kslegislature.gov/li/rsshelp/",
    "US Congress": "https://www.congress.gov/rss/notification.xml",
    "VA News": "https://news.va.gov/feed/",
}

now_utc = datetime.now(timezone.utc)
cutoff = now_utc - timedelta(days=365)

# Load existing history
if HISTORY_FILE.exists():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
else:
    history = []

# Index existing items by link for deduplication
existing_links = {item["link"] for item in history if "link" in item}

new_items = []

for source, url in FEEDS.items():
    feed = feedparser.parse(url)

    for entry in feed.entries:
        published = None

        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        else:
            published = now_utc

        if published < cutoff:
            continue

        link = entry.get("link", "").strip()
        if not link or link in existing_links:
            continue

        item = {
            "title": entry.get("title", "").strip(),
            "link": link,
            "summary": entry.get("summary", "")[:2000],
            "source": source,
            "published": published.isoformat(),
        }

        history.append(item)
        new_items.append(item)
        existing_links.add(link)

# Sort newest first
history.sort(key=lambda x: x.get("published", ""), reverse=True)

# Save history
with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(history, f, indent=2)

# Save "latest run" items
with open(ITEMS_FILE, "w", encoding="utf-8") as f:
    json.dump(new_items, f, indent=2)

print(f"Added {len(new_items)} new items.")
