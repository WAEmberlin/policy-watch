"""
Backfill script to populate history.json with items from RSS feeds.
This script fetches items from the last N days to rebuild history.
"""
import feedparser
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = OUTPUT_DIR / "history.json"

FEEDS = {
    "Kansas Legislature": "https://www.kslegislature.gov/li/rsshelp/",
    "US Congress": "https://www.congress.gov/rss/notification.xml",
    "VA News": "https://news.va.gov/feed/",
}

# How many days back to fetch (default: 30 days)
DAYS_BACK = 30

def backfill_history(days_back=DAYS_BACK):
    """Fetch items from RSS feeds going back N days."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days_back)
    
    print(f"Backfilling history for the last {days_back} days...")
    print(f"Fetching items published after {cutoff.isoformat()}")
    
    # Load existing history
    history = []
    existing_links = set()
    
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded_history = json.load(f)
                if isinstance(loaded_history, list):
                    history = loaded_history
                    existing_links = {item["link"] for item in history if "link" in item}
                    print(f"Loaded {len(history)} existing items from history.json")
        except Exception as e:
            print(f"Warning: Could not load existing history: {e}")
    
    new_items_count = 0
    
    # Fetch from each feed
    for source, url in FEEDS.items():
        print(f"\nFetching from {source}...")
        try:
            feed = feedparser.parse(url)
            
            if not feed.entries:
                print(f"  No entries found in feed")
                continue
            
            feed_items = 0
            for entry in feed.entries:
                published = None
                
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                else:
                    # If no date, use current time but mark it
                    published = now_utc
                
                # Skip items older than cutoff
                if published < cutoff:
                    continue
                
                link = entry.get("link", "").strip()
                if not link:
                    continue
                
                # Skip if we already have this item
                if link in existing_links:
                    continue
                
                # Extract summary/description
                summary = ""
                if hasattr(entry, "summary"):
                    summary = entry.summary
                elif hasattr(entry, "description"):
                    summary = entry.description
                
                item = {
                    "title": entry.get("title", "").strip() or "(no title)",
                    "link": link,
                    "summary": summary[:2000] if summary else "",
                    "source": source,
                    "published": published.isoformat(),
                }
                
                history.append(item)
                existing_links.add(link)
                feed_items += 1
                new_items_count += 1
            
            print(f"  Added {feed_items} new items from {source}")
            
        except Exception as e:
            print(f"  Error fetching from {source}: {e}")
            continue
    
    # Sort by published date (newest first)
    history.sort(key=lambda x: x.get("published", ""), reverse=True)
    
    # Save history
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        print(f"\nSuccessfully saved {len(history)} total items to history.json")
        print(f"  Added {new_items_count} new items in this run")
    except Exception as e:
        print(f"\nError saving history.json: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    # Allow custom days_back via command line
    days = DAYS_BACK
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print(f"Invalid days argument: {sys.argv[1]}. Using default: {DAYS_BACK}")
    
    backfill_history(days_back=days)

