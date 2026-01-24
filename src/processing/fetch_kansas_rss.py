"""
Fetch and normalize Kansas Legislature RSS feeds.

This module handles:
- House Actions
- Senate Actions
- Committee Hearings
- Bill Introductions
- Events (general legislative events)
- Conference Committee Schedules

All feeds are normalized into a unified schema consistent with the project.
"""
import feedparser
import json
import re
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = OUTPUT_DIR / "history.json"

# Cache for short titles to avoid duplicate scraping
_short_title_cache: Dict[str, Optional[str]] = {}


def fetch_short_title(bill_url: str) -> str | None:
    """
    Fetches the 'Short Title' from a Kansas Legislature bill page.
    
    Locates the <h3> element with text "Short Title", then extracts text from
    the parent <div>'s <p class="truncated_text">, including hidden text in
    <span class="hide_remaining_text">. Removes (more) links and normalizes whitespace.
    
    Args:
        bill_url: URL to the Kansas Legislature bill page
        
    Returns:
        Short title text if found, None if unavailable or on error
    """
    # Check cache first
    if bill_url in _short_title_cache:
        return _short_title_cache[bill_url]
    
    try:
        # Fetch the page with timeout
        response = requests.get(bill_url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find the h3 element with text "Short Title"
        short_title_heading = None
        for h3 in soup.find_all("h3"):
            if h3.get_text(strip=True) == "Short Title":
                short_title_heading = h3
                break
        
        if not short_title_heading:
            # Short Title section not found
            _short_title_cache[bill_url] = None
            return None
        
        # Find the parent div
        parent_div = short_title_heading.find_parent("div")
        if not parent_div:
            _short_title_cache[bill_url] = None
            return None
        
        # Find the <p class="truncated_text"> within the parent div
        truncated_para = parent_div.find("p", class_="truncated_text")
        if not truncated_para:
            _short_title_cache[bill_url] = None
            return None
        
        # Remove all <a> tags (including (more) links)
        for a_tag in truncated_para.find_all("a"):
            a_tag.decompose()
        
        # Extract visible text
        visible_text = truncated_para.get_text(separator=" ", strip=False)
        
        # Find and extract hidden text from <span class="hide_remaining_text">
        hidden_span = truncated_para.find("span", class_="hide_remaining_text")
        hidden_text = ""
        if hidden_span:
            hidden_text = hidden_span.get_text(separator=" ", strip=False)
        
        # Combine visible and hidden text
        combined_text = visible_text + " " + hidden_text
        
        # Normalize whitespace: replace multiple spaces/newlines with single space
        normalized = re.sub(r'\s+', ' ', combined_text).strip()
        
        # Cache and return
        _short_title_cache[bill_url] = normalized if normalized else None
        return normalized if normalized else None
        
    except requests.exceptions.Timeout:
        print(f"Timeout fetching short title from {bill_url}")
        _short_title_cache[bill_url] = None
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching short title from {bill_url}: {e}")
        _short_title_cache[bill_url] = None
        return None
    except Exception as e:
        print(f"Error parsing short title from {bill_url}: {e}")
        _short_title_cache[bill_url] = None
        return None


def extract_bill_number_from_url(url: str) -> Optional[str]:
    """
    Extract bill number from a Kansas Legislature bill URL.
    
    Examples:
        https://www.kslegislature.gov/li/b2025_26/measures/HB2433/ -> "HB 2433"
        https://www.kslegislature.gov/li/b2025_26/measures/SB139/ -> "SB 139"
    
    Args:
        url: Kansas Legislature bill URL
        
    Returns:
        Bill number in format "HB 1234" or "SB 567", None if not found
    """
    # Pattern: /measures/HB2433/ or /measures/SB139/
    match = re.search(r'/measures/([A-Z]{1,3})(\d+)/', url, re.IGNORECASE)
    if match:
        bill_type = match.group(1).upper()
        bill_num = match.group(2)
        return f"{bill_type} {bill_num}"
    return None


def extract_bill_number_from_title(title: str) -> Optional[str]:
    """
    Extract bill number from RSS title.
    
    Examples:
        "House: HB2433: Prefiled for Introduction..." -> "HB 2433"
        "Senate: SB139: Some title" -> "SB 139"
    
    Args:
        title: RSS feed title
        
    Returns:
        Bill number in format "HB 1234" or "SB 567", None if not found
    """
    # Pattern: HB2433, SB139, etc.
    match = re.search(r'\b([A-Z]{1,3})(\d+)\b', title, re.IGNORECASE)
    if match:
        bill_type = match.group(1).upper()
        bill_num = match.group(2)
        return f"{bill_type} {bill_num}"
    return None

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
    },
    "events": {
        "url": "https://kslegislature.gov/li/data/feeds/rss/events/",
        "name": "Kansas Legislature",
        "category": "Events",
        "feed_key": "events"
    },
    "conference_committees": {
        "url": "https://kslegislature.gov/li/data/feeds/rss/confcomms/",
        "name": "Kansas Legislature",
        "category": "Conference",
        "feed_key": "conference_committees"
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
        
        # Fix links that have example.com - replace with kslegislature.gov
        # Preserve the rest of the URL path
        if "example.com" in link:
            # Extract the path (everything after example.com)
            # Match example.com and capture everything after it (including the path)
            match = re.search(r'https?://(?:www\.)?example\.com(/.*)?', link)
            if match:
                path = match.group(1) if match.group(1) else ""
                # Reconstruct with correct domain, preserving the path
                link = f"https://www.kslegislature.gov{path}"
            else:
                # Fallback: simple replace (shouldn't happen with proper URLs)
                link = link.replace("http://example.com", "https://www.kslegislature.gov")
                link = link.replace("https://example.com", "https://www.kslegislature.gov")
                link = link.replace("http://www.example.com", "https://www.kslegislature.gov")
                link = link.replace("https://www.example.com", "https://www.kslegislature.gov")
                link = link.replace("example.com", "www.kslegislature.gov")
                # Ensure https
                if link.startswith("http://"):
                    link = link.replace("http://", "https://", 1)
        
        # Extract published date
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        else:
            # Use current time if no date available
            published = datetime.now(timezone.utc)
        
        # Extract bill number if this is a bill-related item
        bill_number = None
        if "/measures/" in link.lower():
            # Try to extract from URL first
            bill_number = extract_bill_number_from_url(link)
            if not bill_number:
                # Fallback to title
                bill_number = extract_bill_number_from_title(title)
        
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
        
        # Add bill number if found
        if bill_number:
            item["bill_number"] = bill_number
            item["bill_url"] = link
        
        # For bill-related items, attempt to fetch short title
        if bill_number and "/measures/" in link.lower():
            short_title = fetch_short_title(link)
            if short_title:
                item["short_title"] = short_title
                item["short_title_source"] = "scraped"
            else:
                # Fallback to RSS title
                item["short_title"] = title
                item["short_title_source"] = "rss"
        
        # For conference committees, extract scheduled date/time/location
        if feed_config["feed_key"] == "conference_committees":
            hearing_info = parse_conference_hearing(summary, title)
            if hearing_info:
                item.update(hearing_info)
        
        return item
    except Exception as e:
        print(f"Error normalizing Kansas RSS item: {e}")
        return None


def parse_conference_hearing(description: str, title: str) -> Optional[Dict]:
    """
    Parse conference committee hearing information from description HTML.
    
    Extracts: date, time, location, committees, bill (if specified), is_canceled
    
    Args:
        description: HTML description from RSS feed
        title: Title from RSS feed
    
    Returns:
        Dict with hearing details, or None if parsing fails
    """
    try:
        # Decode HTML entities
        desc = html.unescape(description)
        
        # Check if canceled
        is_canceled = "MEETING CANCELED" in title.upper() or "MEETING CANCELED" in desc.upper()
        
        # Extract date (format: MM/DD/YYYY)
        date_match = re.search(r'<strong>Date:</strong>\s*(\d{1,2}/\d{1,2}/\d{4})', desc, re.IGNORECASE)
        scheduled_date = None
        if date_match:
            date_str = date_match.group(1)
            try:
                # Parse MM/DD/YYYY format
                scheduled_date = datetime.strptime(date_str, "%m/%d/%Y")
                # Set to UTC timezone (will adjust in frontend)
                scheduled_date = scheduled_date.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        
        # Extract time
        time_match = re.search(r'<strong>Time:</strong>\s*([^<]+)', desc, re.IGNORECASE)
        scheduled_time = time_match.group(1).strip() if time_match else ""
        
        # Extract location
        location_match = re.search(r'<strong>Location:</strong>\s*([^<]+)', desc, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else ""
        
        # Extract committees
        committees_match = re.search(r'<strong>Committees:</strong>\s*([^<]+)', desc, re.IGNORECASE)
        committees = committees_match.group(1).strip() if committees_match else ""
        
        # Extract bill number from title if present (e.g., "on SB139")
        bill_match = re.search(r'\b(?:on|for)\s+([A-Z]{1,3}\d+)', title, re.IGNORECASE)
        bill = bill_match.group(1) if bill_match else ""
        
        result = {
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
            "scheduled_time": scheduled_time,
            "location": location,
            "committees": committees,
            "bill": bill,
            "is_canceled": is_canceled
        }
        
        return result if scheduled_date else None
    except Exception as e:
        print(f"Error parsing conference hearing: {e}")
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
    
    IMPORTANT: This function preserves ALL existing history items and only adds new Kansas items.
    It does NOT remove or filter any existing items.
    
    Args:
        kansas_items: New items from Kansas feeds
    
    Returns:
        Combined history with new Kansas items added (all existing items preserved)
    """
    # Load existing history
    history = []
    existing_identifiers = set()
    initial_count = 0
    
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded_history = json.load(f)
                if isinstance(loaded_history, list):
                    history = loaded_history.copy()  # Make a copy to ensure we preserve everything
                    initial_count = len(history)
                    # Index by id and link for deduplication
                    for item in history:
                        if "id" in item and item["id"]:
                            existing_identifiers.add(item["id"])
                        if "link" in item and item["link"]:
                            existing_identifiers.add(item["link"])
                    print(f"Loaded {len(history)} existing items from history.json")
                else:
                    print(f"Warning: history.json is not a list (type: {type(loaded_history)}). Starting fresh.")
        except Exception as e:
            print(f"Warning: Could not load history.json: {e}. Starting fresh.")
    
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
    
    # Safety check: ensure we didn't lose any existing items
    if initial_count > 0 and len(history) < initial_count:
        print(f"ERROR: History count dropped from {initial_count} to {len(history)}!")
        print("This should not happen - all existing items should be preserved.")
        # Try to restore - this shouldn't happen but just in case
        raise ValueError(f"History preservation failed: lost {initial_count - len(history)} items")
    
    print(f"Added {new_count} new Kansas items to history (total: {len(history)}, preserved {initial_count} existing)")
    return history


def enrich_kansas_bills_with_short_titles(history: List[Dict]) -> List[Dict]:
    """
    Enrich existing Kansas bill items in history with short titles if missing.
    
    This function scans history for Kansas bill items that don't have short_title
    yet and attempts to scrape them. Useful for enriching existing data.
    
    Args:
        history: List of history items
        
    Returns:
        Updated history list with enriched short titles
    """
    enriched_count = 0
    skipped_count = 0
    
    for item in history:
        # Check if this is a Kansas bill item that needs enrichment
        if (item.get("type") == "state_legislation" and 
            item.get("state") == "KS" and
            "/measures/" in item.get("link", "").lower() and
            not item.get("short_title")):  # Only enrich if missing
            
            bill_url = item.get("link", "")
            if not bill_url:
                continue
            
            # Attempt to fetch short title
            short_title = fetch_short_title(bill_url)
            if short_title:
                item["short_title"] = short_title
                item["short_title_source"] = "scraped"
                enriched_count += 1
            else:
                # Fallback to RSS title if scraping fails
                if not item.get("short_title"):
                    item["short_title"] = item.get("title", "")
                    item["short_title_source"] = "rss"
                skipped_count += 1
    
    if enriched_count > 0 or skipped_count > 0:
        print(f"Enriched {enriched_count} Kansas bills with scraped short titles")
        if skipped_count > 0:
            print(f"  ({skipped_count} bills fell back to RSS title)")
    
    return history


def enrich_history_file():
    """
    Load history.json, enrich Kansas bills with short titles, and save back.
    This can be called independently to enrich existing data.
    """
    if not HISTORY_FILE.exists():
        print(f"History file not found: {HISTORY_FILE}")
        return
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if not isinstance(history, list):
            print(f"Warning: history.json is not a list. Skipping enrichment.")
            return
        
        print(f"Loading {len(history)} items from history.json for enrichment...")
        enriched_history = enrich_kansas_bills_with_short_titles(history)
        
        # Save enriched history
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(enriched_history, f, indent=2)
        
        print(f"Successfully enriched and saved history.json")
        
    except Exception as e:
        print(f"Error enriching history: {e}")
        raise


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
    
    # Enrich all Kansas bills (including existing ones) with short titles
    combined_history = enrich_kansas_bills_with_short_titles(combined_history)
    
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
    # Test the short title scraping function
    test_url = "https://www.kslegislature.org/li/b2025_26/measures/hb2467/"
    print(f"Testing short title scraping for: {test_url}")
    result = fetch_short_title(test_url)
    if result:
        print(f"✓ Successfully scraped short title:")
        print(f"  {result}")
    else:
        print("✗ Could not scrape short title (may not be available or page structure changed)")
    
    print("\nRunning main RSS fetch...")
    main()

