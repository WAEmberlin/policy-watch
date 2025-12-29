"""
Fetch and normalize Kansas Legislature RSS feeds.

This module handles:
- House Actions
- Senate Actions
- Committee Hearings
- Bill Introductions

All feeds are normalized into a unified schema consistent with the project.
"""
import feedparser
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = OUTPUT_DIR / "history.json"

# Kansas Legislature RSS feed definitions
KANSAS_FEEDS = {
    "house_actions": {
        "url": "https://kslegislature.gov/li/rss/house_action.xml",
        "name": "Kansas Legislature",
        "category": "House",
        "feed_key": "house_actions"
    },
    "senate_actions": {
        "url": "https://kslegislature.gov/li/rss/senate_action.xml",
        "name": "Kansas Legislature",
        "category": "Senate",
        "feed_key": "senate_actions"
    },
    "committee_hearings": {
        "url": "https://kslegislature.gov/li/rss/committee_hearings.xml",
        "name": "Kansas Legislature",
        "category": "Committee",
        "feed_key": "committee_hearings"
    },
    "bill_introductions": {
        "url": "https://kslegislature.gov/li/rss/bill_introductions.xml",
        "name": "Kansas Legislature",
        "category": "Bills",
        "feed_key": "bill_introductions"
    }
}


def normalize_kansas_item(entry: Dict, feed_config: Dict) -> Optional[Dict]:
    """
    Normalize a Kansas RSS feed entry into the unified schema.
    
    Args:
        entry: RSS feed entry from feedparser
        feed_config: Configuration for this feed (name, category, feed_key)
    
    Returns:
        Normalized item dict, or None if invalid
    """
    try:
        # Extract unique identifier (prefer entry id or link)
        item_id = entry.get("id", "") or entry.get("link", "").strip()
        if not item_id:
            return None
        
        # Extract title
        title = entry.get("title", "").strip()
        if not title:
            title = "(No title)"
        
        # Extract summary/description
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description
        summary = summary.strip() if summary else ""
        
        # Extract link
        link = entry.get("link", "").strip()
        if not link:
            return None  # Must have a link
        
        # Extract published date
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        else:
            # Use current time if no date available
            published = datetime.now(timezone.utc)
        
        # Build normalized item
        item = {
            "id": item_id,
            "title": title,
            "summary": summary[:2000] if summary else "",  # Limit summary length
            "link": link,
            "published": published.isoformat(),
            "source": feed_config["name"],  # "Kansas Legislature"
            "category": feed_config["category"],  # House, Senate, Committee, or Bills
            "type": "state_legislation",
            "state": "KS",
            "feed": feed_config["feed_key"]  # house_actions, senate_actions, etc.
        }
        
        return item
    except Exception as e:
        print(f"Error normalizing Kansas RSS item: {e}")
        return None


def fetch_kansas_feeds() -> List[Dict]:
    """
    Fetch all Kansas Legislature RSS feeds and normalize items.
    
    Returns:
        List of normalized items from all Kansas feeds
    """
    all_items = []
    
    for feed_key, feed_config in KANSAS_FEEDS.items():
        url = feed_config["url"]
        print(f"Fetching {feed_config['category']} feed: {url}")
        
        try:
            feed = feedparser.parse(url)
            
            if not feed.entries:
                print(f"  No entries found in {feed_key}")
                continue
            
            feed_items = 0
            for entry in feed.entries:
                normalized = normalize_kansas_item(entry, feed_config)
                if normalized:
                    all_items.append(normalized)
                    feed_items += 1
            
            print(f"  Processed {feed_items} items from {feed_key}")
            
        except Exception as e:
            print(f"  Error fetching {feed_key}: {e}")
            continue
    
    print(f"\nTotal Kansas Legislature items fetched: {len(all_items)}")
    return all_items


def merge_with_history(kansas_items: List[Dict]) -> List[Dict]:
    """
    Merge Kansas items with existing history, deduplicating by id or link.
    
    Args:
        kansas_items: New items from Kansas feeds
    
    Returns:
        Combined history with new Kansas items added
    """
    # Load existing history
    history = []
    existing_identifiers = set()
    
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded_history = json.load(f)
                if isinstance(loaded_history, list):
                    history = loaded_history
                    # Index by id and link for deduplication
                    for item in history:
                        if "id" in item and item["id"]:
                            existing_identifiers.add(item["id"])
                        if "link" in item and item["link"]:
                            existing_identifiers.add(item["link"])
                    print(f"Loaded {len(history)} existing items from history.json")
        except Exception as e:
            print(f"Warning: Could not load history.json: {e}")
    
    # Add new Kansas items that aren't duplicates
    new_count = 0
    for item in kansas_items:
        item_id = item.get("id", "")
        item_link = item.get("link", "")
        
        # Check if this item already exists
        if item_id and item_id in existing_identifiers:
            continue
        if item_link and item_link in existing_identifiers:
            continue
        
        # Add to history
        history.append(item)
        if item_id:
            existing_identifiers.add(item_id)
        if item_link:
            existing_identifiers.add(item_link)
        new_count += 1
    
    print(f"Added {new_count} new Kansas items to history (total: {len(history)})")
    return history


def main():
    """Main function to fetch Kansas feeds and merge with history."""
    print("Fetching Kansas Legislature RSS feeds...")
    
    # Fetch all Kansas feeds
    kansas_items = fetch_kansas_feeds()
    
    if not kansas_items:
        print("No Kansas items fetched.")
        return
    
    # Merge with existing history
    combined_history = merge_with_history(kansas_items)
    
    # Sort by published date (newest first)
    combined_history.sort(key=lambda x: x.get("published", ""), reverse=True)
    
    # Save updated history
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(combined_history, f, indent=2)
        print(f"\nSuccessfully saved {len(combined_history)} total items to {HISTORY_FILE}")
    except Exception as e:
        print(f"\nError saving history: {e}")
        raise


if __name__ == "__main__":
    main()

