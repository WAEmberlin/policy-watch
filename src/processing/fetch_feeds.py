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
# Only fetch new items from feeds that are less than 365 days old
# But we preserve ALL existing history items regardless of age
feed_cutoff = now_utc - timedelta(days=365)
# Minimum retention: keep at least 30 days of history
min_retention_days = 30
min_retention_cutoff = now_utc - timedelta(days=min_retention_days)

# Load existing history
history = []
if HISTORY_FILE.exists():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            loaded_history = json.load(f)
            if isinstance(loaded_history, list):
                history = loaded_history
                print(f"Loaded {len(history)} existing history items.")
            else:
                print("Warning: history.json is not a list, starting fresh.")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load history.json: {e}. Starting fresh.")

# Index existing items by link for deduplication
existing_links = {item["link"] for item in history if "link" in item}
print(f"Found {len(existing_links)} unique items in history.")

# Track initial history count
initial_count = len(history)

new_items = []

# Fetch new items from feeds
for source, url in FEEDS.items():
    try:
        feed = feedparser.parse(url)
        print(f"Fetching from {source}...")
        
        for entry in feed.entries:
            published = None

            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            else:
                published = now_utc

            # Only skip if item is older than feed cutoff (for new items only)
            if published < feed_cutoff:
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
    except Exception as e:
        print(f"Error fetching from {source}: {e}")
        continue

# IMPORTANT: Preserve ALL existing history items
# We only filter VERY old items (older than 2 years) to prevent unbounded growth
# But we ALWAYS keep at least the last 30 days minimum
if len(history) > 0:
    # Parse dates and filter only items that are VERY old (beyond 2 years)
    # This prevents unbounded growth while preserving recent history
    two_year_cutoff = now_utc - timedelta(days=730)
    filtered_history = []
    items_removed = 0
    
    for item in history:
        try:
            # Handle different date formats
            published_str = item.get("published", "")
            if not published_str:
                # Keep items without dates to be safe
                filtered_history.append(item)
                continue
                
            item_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            
            # Keep ALL items that are:
            # 1. Within 2 years (generous retention)
            # 2. New items we just added
            # 3. Items we can't parse (to be safe)
            if item_date >= two_year_cutoff or item in new_items:
                filtered_history.append(item)
            else:
                items_removed += 1
        except (ValueError, KeyError, AttributeError):
            # If we can't parse the date, keep it to be safe
            filtered_history.append(item)
    
    # Only apply filtering if we're not removing too much
    # Safety check: if filtering would remove more than 10% of non-new items, don't filter
    non_new_items = [item for item in history if item not in new_items]
    if len(non_new_items) > 0 and items_removed > len(non_new_items) * 0.1:
        print(f"Warning: Filtering would remove {items_removed} items ({items_removed/len(non_new_items)*100:.1f}%). Keeping all items.")
        # Don't filter - keep everything
    else:
        history = filtered_history
        if items_removed > 0:
            print(f"Removed {items_removed} very old items (older than 2 years).")

# Sort newest first
history.sort(key=lambda x: x.get("published", ""), reverse=True)

# Validation: Ensure we didn't accidentally lose all history
if initial_count > 0 and len(history) < initial_count * 0.1:
    print(f"ERROR: History count dropped from {initial_count} to {len(history)}!")
    print("This might indicate a problem. History will be saved but please check.")
elif initial_count > len(history):
    print(f"Note: History reduced from {initial_count} to {len(history)} items (removed very old items).")

# Save history (preserving all items)
try:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    print(f"Saved {len(history)} total items to history.json")
except Exception as e:
    print(f"ERROR: Could not save history.json: {e}")
    raise

# Save "latest run" items
with open(ITEMS_FILE, "w", encoding="utf-8") as f:
    json.dump(new_items, f, indent=2)

print(f"Added {len(new_items)} new items.")
print(f"Total history items: {len(history)}")
