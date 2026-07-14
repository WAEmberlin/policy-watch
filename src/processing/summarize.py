import json
import os
import re
import sys
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.bill_action_utils import (  # noqa: E402
    ACTION_BADGES,
    build_vote_feed_events,
    enrich_bill_feed_item,
    inject_vote_events_into_grouped,
    is_bill_feed_item,
)
from processing.bill_urls import pick_best_bill_url, build_ks_bill_url  # noqa: E402
from processing.hearing_stream_utils import enrich_hearing_stream  # noqa: E402
from processing.veteran_impact import (  # noqa: E402
    build_veteran_impact_lookup,
    collect_feed_bills_for_veteran_lookup,
    load_co_bills,
)

# Handle timezone on Windows (fallback if zoneinfo not available)
try:
    from zoneinfo import ZoneInfo
    central = ZoneInfo("America/Chicago")
except (ImportError, Exception):
    # Fallback for Windows without tzdata
    try:
        import pytz
        central = pytz.timezone("America/Chicago")
    except ImportError:
        # Last resort: use UTC offset
        from datetime import timezone, timedelta
        central = timezone(timedelta(hours=-6))  # CST is UTC-6

OUTPUT_DIR = "src/output"
DOCS_DIR = "docs"
DATA_DIR = "data"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.json")
LEGISLATION_FILE = os.path.join(OUTPUT_DIR, "legislation.json")
FEDERAL_HEARINGS_FILE = os.path.join(OUTPUT_DIR, "federal_hearings.json")
HEARINGS_FILE = os.path.join(OUTPUT_DIR, "hearings.json")
KANSAS_CALENDARS_FILE = os.path.join(OUTPUT_DIR, "kansas_calendars.json")
DAILY_SUMMARIES_FILE = os.path.join(DATA_DIR, "daily_summaries.json")
SITE_DATA_FILE = os.path.join(DOCS_DIR, "site_data.json")

ITEMS_PER_PAGE = 50

# -------------------------
# Load history
# -------------------------
# Ensure docs directory exists
os.makedirs(DOCS_DIR, exist_ok=True)

if not os.path.exists(HISTORY_FILE):
    print("No history.json found — creating empty site data.")
    # Get current time in central timezone
    if hasattr(central, 'localize'):
        # pytz timezone
        now = datetime.now(central)
    else:
        # zoneinfo or timezone offset
        now = datetime.now(central)
    
    data = {
        "last_updated": now.isoformat(),
        "years": {}
    }
    with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    exit(0)

# Load history with error handling
try:
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    if not isinstance(history, list):
        print(f"Warning: history.json is not a list (type: {type(history)}). Treating as empty.")
        history = []
    elif len(history) == 0:
        print("Warning: history.json is empty. No items to display.")
    else:
        print(f"Loaded {len(history)} items from history.json")
except (json.JSONDecodeError, IOError) as e:
    print(f"Error loading history.json: {e}. Creating empty site data.")
    history = []

# -------------------------
# Group data
# -------------------------
grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

processed_count = 0
for item in history:
    try:
        # Handle different date formats
        published_str = item.get("published", "")
        if not published_str:
            continue
            
        # Try parsing ISO format
        try:
            dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            # Try parsing other formats if needed
            continue

        year = str(dt.year)
        date_str = dt.strftime("%Y-%m-%d")
        source = item.get("source", "Unknown")
        
        # Skip conference committee items - they go to hearings page only
        if item.get("feed") == "conference_committees":
            continue
        
        # For Kansas items, include category in source for better grouping
        if item.get("type") == "state_legislation" and item.get("category"):
            source = f"{source} - {item.get('category')}"
        
        if is_bill_feed_item(item):
            enrich_bill_feed_item(item)
        grouped[year][date_str][source].append(item)
        processed_count += 1
    except Exception as e:
        print(f"Warning: Skipping item due to error: {e}")
        continue

print(f"Processed {processed_count} items into grouped structure.")

# -------------------------
# Load and process legislation
# -------------------------
# First, build a set of URLs from history.json to deduplicate against
# This prevents showing the same bills from both RSS feed and API
existing_urls = set()
for year in grouped:
    for date_str in grouped[year]:
        for source in grouped[year][date_str]:
            for item in grouped[year][date_str][source]:
                url = item.get("link", "")
                if url:
                    existing_urls.add(url)

print(f"Indexed {len(existing_urls)} existing URLs for deduplication")

legislation = []
if os.path.exists(LEGISLATION_FILE):
    try:
        with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
            legislation = json.load(f)
            if not isinstance(legislation, list):
                print(f"Warning: legislation.json is not a list. Treating as empty.")
                legislation = []
            else:
                print(f"Loaded {len(legislation)} bills from legislation.json")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load legislation.json: {e}")

# Process legislation into the same grouped structure
legislation_count = 0
duplicate_count = 0
for bill in legislation:
    try:
        # Use latest_action_date or published date
        date_str = bill.get("latest_action_date", bill.get("published", ""))
        if not date_str:
            continue
        
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        
        # Check if this bill URL already exists in history (from RSS feed)
        bill_url = bill.get("url", "")
        if bill_url and bill_url in existing_urls:
            duplicate_count += 1
            continue  # Skip duplicate - already in history.json from RSS feed
        
        year = str(dt.year)
        date_str_formatted = dt.strftime("%Y-%m-%d")
        source = "Congress.gov API"
        
        # Use short_title if available for display title
        display_title = bill.get("short_title") or bill.get("title", "")
        
        # Create item in same format as RSS items for consistency
        item = {
            "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {display_title}",
            "link": bill.get("url", ""),
            "summary": bill.get("summary", ""),
            "source": source,
            "published": bill.get("published", date_str),
            # Additional legislation-specific fields
            "bill_number": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}".strip(),
            "bill_type": bill.get("bill_type", ""),
            "sponsor_name": bill.get("sponsor_name", ""),
            "latest_action": bill.get("latest_action", ""),
            "latest_action_date": bill.get("latest_action_date", ""),
            "congress": bill.get("congress", 119),
            # Include short_title and official_title for enhanced display
            "short_title": bill.get("short_title", ""),
            "official_title": bill.get("official_title", "")
        }
        enrich_bill_feed_item(item)

        grouped[year][date_str_formatted][source].append(item)
        if bill_url:
            existing_urls.add(bill_url)  # Track this URL to prevent future duplicates
        legislation_count += 1
    except Exception as e:
        print(f"Warning: Skipping legislation item due to error: {e}")
        continue

print(f"Processed {legislation_count} bills into grouped structure.")
if duplicate_count > 0:
    print(f"Skipped {duplicate_count} duplicate bills (already in history.json from RSS feed)")

# Enrich any bill rows not tagged during initial history pass
for year in grouped:
    for date_str in grouped[year]:
        for source in grouped[year][date_str]:
            for idx, item in enumerate(grouped[year][date_str][source]):
                if is_bill_feed_item(item) and not item.get("item_type"):
                    grouped[year][date_str][source][idx] = enrich_bill_feed_item(item)

vote_feed_events = build_vote_feed_events(ROOT)
vote_events_added = inject_vote_events_into_grouped(grouped, vote_feed_events)
print(f"Injected {vote_events_added} vote feed events from {len(vote_feed_events)} records.")

# Sort items within each date/source by published time (newest first)
for year in grouped:
    for date_str in grouped[year]:
        for source in grouped[year][date_str]:
            grouped[year][date_str][source].sort(
                key=lambda x: x.get("published", ""), 
                reverse=True
            )

# -------------------------
# Sort structure
# -------------------------
site_years = {}

for year in sorted(grouped.keys(), reverse=True):
    days_sorted = sorted(grouped[year].keys(), reverse=True)

    flat_items = []
    for day in days_sorted:
        for source in grouped[year][day]:
            for item in grouped[year][day][source]:
                flat_item = {
                    "date": day,
                    "source": source,
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "published": item.get("published"),
                    "summary": item.get("summary", "")  # Include summary for search
                }
                # Include short_title and bill_number for Kansas bills
                if item.get("short_title"):
                    flat_item["short_title"] = item.get("short_title")
                    flat_item["short_title_source"] = item.get("short_title_source", "rss")
                if item.get("bill_number"):
                    flat_item["bill_number"] = item.get("bill_number")
                if item.get("bill_url"):
                    flat_item["bill_url"] = item.get("bill_url")
                if item.get("item_type"):
                    flat_item["item_type"] = item.get("item_type")
                if item.get("action_type"):
                    flat_item["action_type"] = item.get("action_type")
                if item.get("vote_tally"):
                    flat_item["vote_tally"] = item.get("vote_tally")
                if item.get("motion"):
                    flat_item["motion"] = item.get("motion")
                if item.get("state"):
                    flat_item["state"] = item.get("state")
                if item.get("level"):
                    flat_item["level"] = item.get("level")
                flat_items.append(flat_item)

    # Pagination
    pages = []
    for i in range(0, len(flat_items), ITEMS_PER_PAGE):
        pages.append(flat_items[i:i + ITEMS_PER_PAGE])

    # Include full item data in grouped structure for search
    # This ensures summaries are available for search functionality
    site_years[year] = {
        "total_items": len(flat_items),
        "pages": pages,
        "grouped": grouped[year]  # Already contains full items with summaries
    }

# -------------------------
# Write output
# -------------------------
# Get current time in central timezone
if hasattr(central, 'localize'):
    # pytz timezone
    now = datetime.now(central)
else:
    # zoneinfo or timezone offset
    now = datetime.now(central)

# Prepare legislation data separately for frontend with pagination
legislation_data = []
for bill in legislation:
    bill_data = {
        "bill_number": bill.get("bill_number", ""),
        "bill_type": bill.get("bill_type", ""),
        "title": bill.get("title", ""),
        "summary": bill.get("summary", ""),
        "sponsor_name": bill.get("sponsor_name", ""),
        "latest_action": bill.get("latest_action", ""),
        "latest_action_date": bill.get("latest_action_date", ""),
        "url": bill.get("url", ""),
        "published": bill.get("published", ""),
        "congress": bill.get("congress", 119)
    }
    # Include short_title and official_title if available
    if bill.get("short_title"):
        bill_data["short_title"] = bill.get("short_title")
    if bill.get("official_title"):
        bill_data["official_title"] = bill.get("official_title")
    legislation_data.append(bill_data)

# Paginate legislation (50 items per page, same as RSS feeds)
legislation_pages = []
for i in range(0, len(legislation_data), ITEMS_PER_PAGE):
    legislation_pages.append(legislation_data[i:i + ITEMS_PER_PAGE])

print(f"Prepared {len(legislation_data)} bills for frontend display.")
print(f"Split into {len(legislation_pages)} pages ({ITEMS_PER_PAGE} items per page)")

# -------------------------
# Extract upcoming and historical hearings from conference committees
# -------------------------
upcoming_hearings = []
historical_hearings = []
now_utc = datetime.now(timezone.utc) if hasattr(datetime.now(), 'tzinfo') else datetime.now()
today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

for item in history:
    # Check if this is a conference committee item with scheduled date
    if (item.get("feed") == "conference_committees" and 
        item.get("scheduled_date") and 
        not item.get("is_canceled", False)):
        try:
            scheduled_dt = datetime.fromisoformat(item["scheduled_date"].replace("Z", "+00:00"))
            hearing = {
                "title": item.get("title", ""),
                "scheduled_date": item.get("scheduled_date", ""),
                "scheduled_time": item.get("scheduled_time", ""),
                "location": item.get("location", ""),
                "committees": item.get("committees", ""),
                "bill": item.get("bill", ""),
                "link": item.get("link", ""),
                "published": item.get("published", ""),
                "source": "State (Kansas Legislature)",  # Mark as state hearing
                "state": "KS",
                "level": "state",
            }
            
            # Separate into upcoming (today or future) and historical (past)
            if scheduled_dt >= today_start:
                upcoming_hearings.append(hearing)
            else:
                historical_hearings.append(hearing)
        except (ValueError, KeyError) as e:
            # Skip items with invalid dates
            continue

# Sort upcoming hearings by scheduled date (soonest first)
upcoming_hearings.sort(key=lambda x: x.get("scheduled_date", ""))
# Sort historical hearings by scheduled date (most recent first - newest at top)
historical_hearings.sort(key=lambda x: x.get("scheduled_date", ""), reverse=True)

print(f"Found {len(upcoming_hearings)} upcoming conference committee hearings.")
print(f"Found {len(historical_hearings)} historical conference committee hearings.")

# -------------------------
# Load and process federal hearings
# -------------------------
federal_hearings = []

# Try new hearings.json file first (from fetch_hearings.py)
if os.path.exists(HEARINGS_FILE):
    try:
        with open(HEARINGS_FILE, "r", encoding="utf-8") as f:
            hearings_data = json.load(f)
            if isinstance(hearings_data, dict) and "items" in hearings_data:
                federal_hearings = hearings_data["items"]
                print(f"Loaded {len(federal_hearings)} federal hearings from {HEARINGS_FILE}")
            elif isinstance(hearings_data, list):
                federal_hearings = hearings_data
                print(f"Loaded {len(federal_hearings)} federal hearings from {HEARINGS_FILE}")
            else:
                print(f"Warning: hearings.json has unexpected format. Treating as empty.")
                federal_hearings = []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load hearings.json: {e}")

# Fallback to old federal_hearings.json if new file doesn't exist
if not federal_hearings and os.path.exists(FEDERAL_HEARINGS_FILE):
    try:
        with open(FEDERAL_HEARINGS_FILE, "r", encoding="utf-8") as f:
            federal_hearings = json.load(f)
            if not isinstance(federal_hearings, list):
                print(f"Warning: federal_hearings.json is not a list. Treating as empty.")
                federal_hearings = []
            else:
                print(f"Loaded {len(federal_hearings)} federal hearings from {FEDERAL_HEARINGS_FILE}")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load federal_hearings.json: {e}")

def _fix_hearing_url(hearing):
    """Rewrite API or wrong Congress.gov URLs to public event URLs."""
    url = hearing.get("url") or hearing.get("link") or ""
    if not url or ("www.congress.gov" in url and "api." not in url and "committee-meeting" not in url):
        return
    new_url = None
    # Fix committee-meeting -> chamber-event (Congress.gov expects house-event/senate-event)
    if "committee-meeting" in url:
        chamber = (hearing.get("chamber") or "house").lower()
        if chamber in ("house", "senate"):
            new_url = url.replace("committee-meeting", f"{chamber}-event")
    # Fix api.congress.gov hearing URL -> www.congress.gov event URL
    elif "api.congress.gov" in url and "/hearing/" in url:
        try:
            parts = [p for p in url.rstrip("/").split("/") if p]
            idx = next((i for i, p in enumerate(parts) if p == "hearing"), None)
            if idx is not None and len(parts) >= idx + 4:
                congress = parts[idx + 1]
                chamber = parts[idx + 2].lower()
                event_id = parts[idx + 3].split("?")[0]
                if chamber in ("house", "senate") and congress.isdigit():
                    new_url = f"https://www.congress.gov/event/{congress}th-congress/{chamber}-event/{event_id}"
        except Exception:
            pass
    if new_url:
        hearing["url"] = hearing["link"] = new_url


# Separate federal hearings into upcoming and historical
federal_upcoming = []
federal_historical = []

for hearing in federal_hearings:
    # Ensure hearing has required fields for frontend
    if not hearing.get("url") and hearing.get("link"):
        hearing["url"] = hearing["link"]
    if not hearing.get("link") and hearing.get("url"):
        hearing["link"] = hearing["url"]
    # Rewrite broken Congress.gov URLs to working event URLs
    _fix_hearing_url(hearing)
    # Map committee to committees for consistency with frontend
    if hearing.get("committee") and not hearing.get("committees"):
        hearing["committees"] = hearing["committee"]
    
    # Ensure source is set correctly
    if not hearing.get("source"):
        hearing["source"] = "Federal (US Congress)"
    
    scheduled_date = hearing.get("scheduled_date", "")
    if scheduled_date:
        try:
            # Handle both date-only and datetime formats
            if "T" in scheduled_date:
                scheduled_dt = datetime.fromisoformat(scheduled_date.replace("Z", "+00:00"))
            else:
                # Parse date-only format (YYYY-MM-DD)
                scheduled_dt = datetime.fromisoformat(scheduled_date + "T00:00:00+00:00")
            
            # Make sure scheduled_dt is timezone-aware
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
            
            # Compare dates (ignore time for date-only comparisons)
            scheduled_date_only = scheduled_dt.date()
            today_date_only = today_start.date()
            
            if scheduled_date_only >= today_date_only:
                federal_upcoming.append(hearing)
            else:
                federal_historical.append(hearing)
        except (ValueError, KeyError) as e:
            print(f"Warning: Could not parse scheduled_date '{scheduled_date}' for hearing '{hearing.get('title', 'Unknown')}': {e}")
            # If date parsing fails, include in upcoming by default
            federal_upcoming.append(hearing)
    else:
        # No scheduled_date - skip this hearing (don't include it)
        # Most hearings without dates are likely past or invalid
        continue

# Sort federal hearings
federal_upcoming.sort(key=lambda x: x.get("scheduled_date", ""))
federal_historical.sort(key=lambda x: x.get("scheduled_date", "") or "", reverse=True)  # Most recent first

# Combine state and federal hearings
all_upcoming_hearings = upcoming_hearings + federal_upcoming
all_historical_hearings = historical_hearings + federal_historical

# Sort combined lists
all_upcoming_hearings.sort(key=lambda x: x.get("scheduled_date", ""))
all_historical_hearings.sort(key=lambda x: x.get("scheduled_date", "") or "", reverse=True)  # Most recent first

print(f"Total upcoming hearings: {len(all_upcoming_hearings)} ({len(upcoming_hearings)} state, {len(federal_upcoming)} federal)")
print(f"Total historical hearings: {len(all_historical_hearings)} ({len(historical_hearings)} state, {len(federal_historical)} federal)")

# -------------------------
# Merge multi-state hearings (Open States + Kansas API enrichments)
# -------------------------
STATE_HEARING_LABELS = {
    "KS": "State (Kansas)",
    "CO": "State (Colorado)",
    "AZ": "State (Arizona)",
    "UT": "State (Utah)",
    "ME": "State (Maine)",
    "NE": "State (Nebraska)",
    "MD": "State (Maryland)",
}


def _hearing_dedup_key(hearing: dict) -> str:
    url = hearing.get("url") or hearing.get("link") or ""
    if url:
        return url
    return f"{hearing.get('title', '')}|{hearing.get('scheduled_date', '')}|{hearing.get('state', '')}"


def _merge_hearing_lists(existing: list, new_items: list) -> list:
    seen = {_hearing_dedup_key(h) for h in existing}
    merged = list(existing)
    for hearing in new_items:
        key = _hearing_dedup_key(hearing)
        if key not in seen:
            merged.append(hearing)
            seen.add(key)
    return merged


def _normalized_event_to_hearing(event: dict) -> dict:
    state = event.get("state")
    level = event.get("level", "")
    if level == "federal":
        source = "Federal (US Congress)"
    elif state:
        source = STATE_HEARING_LABELS.get(state, f"State ({state})")
    else:
        source = event.get("source", "Unknown")

    committees = event.get("committees") or []
    if isinstance(committees, list):
        committee_names = [
            c if isinstance(c, str) else c.get("name", "")
            for c in committees
        ]
        committees_str = ", ".join(n for n in committee_names if n)
    else:
        committees_str = str(committees)

    return {
        "title": event.get("title", ""),
        "scheduled_date": event.get("scheduled_date", ""),
        "scheduled_time": event.get("scheduled_time", ""),
        "location": event.get("location", ""),
        "committees": committees_str,
        "committee": committees_str.split(",")[0].strip() if committees_str else "",
        "link": event.get("url", ""),
        "url": event.get("url", ""),
        "stream_url": event.get("stream_url", ""),
        "source": source,
        "state": state,
        "level": level,
        "chamber": event.get("chamber", ""),
        "description": event.get("description", ""),
    }


def _classify_hearing_by_date(hearing: dict, today: datetime) -> str:
    """Return 'upcoming' or 'historical'."""
    scheduled = hearing.get("scheduled_date", "")
    if not scheduled:
        return "upcoming"
    try:
        if "T" in scheduled:
            scheduled_dt = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
        else:
            scheduled_dt = datetime.fromisoformat(scheduled + "T00:00:00+00:00")
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        if scheduled_dt.date() >= today.date():
            return "upcoming"
        return "historical"
    except (ValueError, TypeError):
        return "upcoming"


# Load normalized events for Open States hearings (CO, AZ, UT, KS committee events)
_normalized_events_path = os.path.join(DATA_DIR, "normalized", "events.json")
_extra_upcoming = []
_extra_historical = []

if os.path.exists(_normalized_events_path):
    try:
        with open(_normalized_events_path, "r", encoding="utf-8") as f:
            _norm_events = json.load(f)
        if isinstance(_norm_events, list):
            for event in _norm_events:
                # Congress events already come from fetch_hearings.py
                if event.get("source") == "congress":
                    continue
                # Kansas RSS conference committees already extracted from history above
                if event.get("source") == "kansas_rss":
                    continue
                hearing = _normalized_event_to_hearing(event)
                bucket = _classify_hearing_by_date(hearing, today_start)
                if bucket == "upcoming":
                    _extra_upcoming.append(hearing)
                else:
                    _extra_historical.append(hearing)
            print(f"Merged {len(_extra_upcoming)} upcoming + {len(_extra_historical)} historical Open States hearings")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load normalized events for hearings: {e}")

# Kansas API global hearings schedule (standing committees + /now/ snapshot)
_ks_hearings_path = os.path.join(DATA_DIR, "kansas", "hearings.json")
if os.path.exists(_ks_hearings_path):
    try:
        with open(_ks_hearings_path, "r", encoding="utf-8") as f:
            _ks_hearings_data = json.load(f)
        _ks_hearing_items = (
            _ks_hearings_data.get("items")
            if isinstance(_ks_hearings_data, dict)
            else _ks_hearings_data
        )
        if not isinstance(_ks_hearing_items, list):
            _ks_hearing_items = []
        ks_schedule_count = 0
        for hearing in _ks_hearing_items:
            if not isinstance(hearing, dict):
                continue
            hearing = dict(hearing)
            if not hearing.get("source"):
                hearing["source"] = STATE_HEARING_LABELS["KS"]
            bucket = _classify_hearing_by_date(hearing, today_start)
            if bucket == "upcoming":
                _extra_upcoming.append(hearing)
            else:
                _extra_historical.append(hearing)
            ks_schedule_count += 1
        if ks_schedule_count:
            print(f"Merged {ks_schedule_count} Kansas API schedule hearings")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load Kansas hearings schedule: {e}")

# Kansas API enrichment hearings (stream URLs, committee details)
_ks_enrichments_path = os.path.join(DATA_DIR, "kansas", "enrichments.json")
if os.path.exists(_ks_enrichments_path):
    try:
        with open(_ks_enrichments_path, "r", encoding="utf-8") as f:
            _ks_enrich = json.load(f)
        ks_hearing_count = 0
        for key, record in _ks_enrich.items():
            if key == "_meta" or not isinstance(record, dict):
                continue
            for h in record.get("hearings") or []:
                stream_url = h.get("stream_url") or h.get("url", "")
                page_url = h.get("url", "") or stream_url
                hearing = {
                    "title": h.get("title") or f"Hearing on {record.get('bill_number', key)}",
                    "scheduled_date": h.get("scheduled_date", ""),
                    "scheduled_time": "",
                    "location": h.get("location", ""),
                    "committees": h.get("title", ""),
                    "committee": h.get("title", ""),
                    "bill": record.get("bill_number", key),
                    "stream_url": stream_url,
                    "link": page_url,
                    "url": page_url,
                    "source": STATE_HEARING_LABELS["KS"],
                    "state": "KS",
                    "level": "state",
                }
                bucket = _classify_hearing_by_date(hearing, today_start)
                if bucket == "upcoming":
                    _extra_upcoming.append(hearing)
                else:
                    _extra_historical.append(hearing)
                ks_hearing_count += 1
        if ks_hearing_count:
            print(f"Merged {ks_hearing_count} Kansas API enrichment hearings")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load Kansas enrichments for hearings: {e}")

# Utah committee RSS hearing schedules
_ut_hearings_path = os.path.join(DATA_DIR, "utah", "committee_hearings.json")
if os.path.exists(_ut_hearings_path):
    try:
        with open(_ut_hearings_path, "r", encoding="utf-8") as f:
            _ut_hearings_data = json.load(f)
        _ut_items = _ut_hearings_data.get("items") if isinstance(_ut_hearings_data, dict) else _ut_hearings_data
        if not isinstance(_ut_items, list):
            _ut_items = []
        ut_count = 0
        for hearing in _ut_items:
            if not isinstance(hearing, dict):
                continue
            hearing = dict(hearing)
            if not hearing.get("source"):
                hearing["source"] = STATE_HEARING_LABELS["UT"]
            if not hearing.get("state"):
                hearing["state"] = "UT"
            bucket = _classify_hearing_by_date(hearing, today_start)
            if bucket == "upcoming":
                _extra_upcoming.append(hearing)
            else:
                _extra_historical.append(hearing)
            ut_count += 1
        if ut_count:
            print(f"Merged {ut_count} Utah committee RSS hearings")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load Utah committee hearings: {e}")

all_upcoming_hearings = _merge_hearing_lists(all_upcoming_hearings, _extra_upcoming)
all_historical_hearings = _merge_hearing_lists(all_historical_hearings, _extra_historical)
all_upcoming_hearings.sort(key=lambda x: x.get("scheduled_date", ""))
all_historical_hearings.sort(key=lambda x: x.get("scheduled_date", "") or "", reverse=True)

print(f"After multi-state merge: {len(all_upcoming_hearings)} upcoming, {len(all_historical_hearings)} historical")

# -------------------------
# Enrich hearings with stream/embed metadata for the hearings page
# -------------------------
livestreams_meta = {"state_floor_stream": {}, "streams": []}
try:
    import yaml

    livestreams_path = os.path.join("config", "livestreams.yaml")
    if os.path.exists(livestreams_path):
        with open(livestreams_path, "r", encoding="utf-8") as f:
            ls_cfg = yaml.safe_load(f) or {}
            livestreams_meta["state_floor_stream"] = ls_cfg.get("state_floor_stream") or {}
            livestreams_meta["streams"] = ls_cfg.get("streams") or []
except Exception as e:
    print(f"Warning: Could not load livestreams config: {e}")

_state_floor_map = livestreams_meta["state_floor_stream"]
_livestreams = livestreams_meta["streams"]
all_upcoming_hearings = [
    enrich_hearing_stream(h, state_floor_map=_state_floor_map, streams=_livestreams)
    for h in all_upcoming_hearings
]
all_historical_hearings = [
    enrich_hearing_stream(h, state_floor_map=_state_floor_map, streams=_livestreams)
    for h in all_historical_hearings
]

# -------------------------
# Load Kansas Legislature calendars (by date for hearings page)
# -------------------------
kansas_calendars = {}
if os.path.exists(KANSAS_CALENDARS_FILE):
    try:
        with open(KANSAS_CALENDARS_FILE, "r", encoding="utf-8") as f:
            kansas_calendars = json.load(f)
            if not isinstance(kansas_calendars, dict):
                kansas_calendars = {}
            else:
                print(f"Loaded Kansas calendars for {len(kansas_calendars)} dates from {KANSAS_CALENDARS_FILE}")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load kansas_calendars.json: {e}")

# Kansas roll-call vote records (per-member breakdown from official API)
kansas_vote_records = {}
_kansas_votes_path = os.path.join(DATA_DIR, "kansas", "vote_records.json")
if os.path.exists(_kansas_votes_path):
    try:
        with open(_kansas_votes_path, "r", encoding="utf-8") as f:
            _votes_data = json.load(f)
        if isinstance(_votes_data, dict):
            kansas_vote_records = {k: v for k, v in _votes_data.items() if k != "_meta" and isinstance(v, list)}
            print(f"Loaded Kansas vote records for {len(kansas_vote_records)} bills")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load Kansas vote_records.json: {e}")

# -------------------------
# Load daily summaries
# -------------------------
daily_summaries = {}
if os.path.exists(DAILY_SUMMARIES_FILE):
    try:
        with open(DAILY_SUMMARIES_FILE, "r", encoding="utf-8") as f:
            daily_summaries = json.load(f)
            if not isinstance(daily_summaries, dict):
                print(f"Warning: daily_summaries.json is not a dict. Treating as empty.")
                daily_summaries = {}
            else:
                print(f"Loaded {len(daily_summaries)} daily summaries from {DAILY_SUMMARIES_FILE}")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load daily_summaries.json: {e}")

# -------------------------
# Load unified normalized data (expansion layer — additive, does not replace existing)
# -------------------------
normalized_bills = []
normalized_events = []
normalized_legislators = []
normalized_dashboards = {}
normalized_search_index = {}
weekly_digests = {}
configured_states = []

def _load_expansion_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if data is not None else default
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load {path}: {e}")
        return default

normalized_bills = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "bills.json"), [])
normalized_events = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "events.json"), [])
normalized_legislators = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "legislators.json"), [])
normalized_dashboards = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "dashboards.json"), {})
normalized_search_index = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "search_index.json"), {})
normalized_legislator_stats = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "legislator_stats.json"), {})
normalized_legislator_votes = _load_expansion_json(os.path.join(DATA_DIR, "normalized", "legislator_votes.json"), {})
weekly_digests = _load_expansion_json(os.path.join(DATA_DIR, "digests", "weekly.json"), {})
federal_delegation = _load_expansion_json(os.path.join(DATA_DIR, "federal", "delegation.json"), [])

if federal_delegation:
    search_legislators = list((normalized_search_index or {}).get("legislators") or [])
    seen_ids = {leg.get("id") for leg in search_legislators if leg.get("id")}
    added = 0
    for member in federal_delegation:
        member_id = member.get("id")
        if member_id and member_id in seen_ids:
            continue
        search_legislators.append(
            {
                "id": member.get("id"),
                "name": member.get("name"),
                "party": member.get("party"),
                "state": member.get("state"),
                "district": member.get("district"),
                "chamber": member.get("chamber"),
                "gender": member.get("gender"),
                "birth_date": member.get("birth_date"),
                "image": member.get("image"),
                "url": member.get("url"),
            }
        )
        if member_id:
            seen_ids.add(member_id)
        added += 1
    normalized_search_index = {**(normalized_search_index or {}), "legislators": search_legislators}
    if added:
        print(f"Merged {added} federal delegation members into search_index")

try:
    import yaml
    states_config_path = os.path.join("config", "states.yaml")
    if os.path.exists(states_config_path):
        with open(states_config_path, "r", encoding="utf-8") as f:
            states_cfg = yaml.safe_load(f)
            configured_states = [
                {"code": s["code"], "name": s.get("name", s["code"].upper())}
                for s in states_cfg.get("states", []) if s.get("enabled")
            ]
except Exception as e:
    print(f"Warning: Could not load states config: {e}")

if normalized_bills:
    print(f"Loaded {len(normalized_bills)} normalized bills from expansion layer")

# -------------------------
# Veteran impact lookup (CO CSV + rule-based fallback)
# -------------------------
co_veteran_data = load_co_bills()
feed_bills_for_veteran = collect_feed_bills_for_veteran_lookup(history, legislation)
veteran_impact_lookup = build_veteran_impact_lookup(
    co_data=co_veteran_data,
    normalized_bills=normalized_bills,
    feed_items=feed_bills_for_veteran,
)
co_meta = co_veteran_data.get("_meta") or {}
if veteran_impact_lookup:
    print(
        f"Built veteran impact lookup with {len(veteran_impact_lookup)} entries "
        f"({co_meta.get('matched_openstates', 0)} CO CSV bills matched Open States)"
    )

output = {
    "last_updated": now.isoformat(),
    "years": site_years,
    "legislation": {
        "total_items": len(legislation_data),
        "pages": legislation_pages  # Paginated legislation data
    },
    "upcoming_hearings": all_upcoming_hearings,  # Upcoming hearings (state + federal)
    "historical_hearings": all_historical_hearings,  # Past hearings (state + federal)
    "daily_summaries": daily_summaries,  # Daily AI-generated summaries by date
    "kansas_calendars": kansas_calendars,  # Kansas House/Senate calendar links by date (YYYY-MM-DD)
    "kansas_vote_records": kansas_vote_records,
    # Expansion layer (additive — existing frontend ignores these keys until updated)
    "normalized": {
        "bills_count": len(normalized_bills),
        "events_count": len(normalized_events),
        "legislators_count": len(normalized_legislators),
    },
    "states": configured_states,
    "dashboards": normalized_dashboards,
    "search_index": normalized_search_index,
    "legislator_stats": normalized_legislator_stats,
    "legislator_votes": {},
    "weekly_digests": weekly_digests,
    "livestreams": livestreams_meta,
    "veteran_impact": {
        "lookup": veteran_impact_lookup,
        "co_stats": co_meta.get("stats", {}),
        "co_matched": co_meta.get("matched_openstates", 0),
        "co_tracked": co_meta.get("total_tracked", 0),
        "co_gaps": co_meta.get("gaps", []),
    },
    "action_badges": ACTION_BADGES,
}

# Ensure legislation key is always present
if "legislation" not in output:
    output["legislation"] = {"total_items": 0, "pages": []}

with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

legislator_votes_file = os.path.join(DOCS_DIR, "legislator_votes.json")
with open(legislator_votes_file, "w", encoding="utf-8") as f:
    json.dump(normalized_legislator_votes, f, indent=2)
legislator_vote_counts = {
    leg_id: len(votes)
    for leg_id, votes in (normalized_legislator_votes or {}).items()
    if votes
}
legislator_vote_counts_file = os.path.join(DOCS_DIR, "legislator_vote_counts.json")
with open(legislator_vote_counts_file, "w", encoding="utf-8") as f:
    json.dump(legislator_vote_counts, f, indent=2)
legislator_vote_count = sum(len(v) for v in (normalized_legislator_votes or {}).values())
print(
    f"Wrote {len(normalized_legislator_votes or {})} legislators with "
    f"{legislator_vote_count} total votes to {legislator_votes_file}"
)
print(f"Wrote {len(legislator_vote_counts)} legislator vote counts to {legislator_vote_counts_file}")

bill_title_lookup = {}
bill_url_lookup = {}
bill_url_candidates = {}
for bill in normalized_bills:
    state = (bill.get("state") or "").upper()
    if not state:
        continue
    bill_number = re.sub(r"\s+", "", bill.get("bill_number") or "").upper()
    title = (bill.get("title") or bill.get("short_title") or "").strip()
    url = (bill.get("url") or "").strip()
    if not bill_number:
        continue
    key = f"{state}:{bill_number}"
    if title:
        bill_title_lookup[key] = title
    if url:
        bill_url_candidates.setdefault(key, []).append(url)

for key, candidates in bill_url_candidates.items():
    state, bill_number = key.split(":", 1)
    best = pick_best_bill_url(candidates, state, bill_number)
    if best:
        bill_url_lookup[key] = best
    elif state == "KS":
        built = build_ks_bill_url(bill_number)
        if built:
            bill_url_lookup[key] = built
bill_title_lookup_file = os.path.join(DOCS_DIR, "bill_title_lookup.json")
with open(bill_title_lookup_file, "w", encoding="utf-8") as f:
    json.dump(bill_title_lookup, f)
print(f"Wrote {len(bill_title_lookup)} bill titles to {bill_title_lookup_file}")
bill_url_lookup_file = os.path.join(DOCS_DIR, "bill_url_lookup.json")
with open(bill_url_lookup_file, "w", encoding="utf-8") as f:
    json.dump(bill_url_lookup, f)
print(f"Wrote {len(bill_url_lookup)} bill URLs to {bill_url_lookup_file}")

print("Site data generated successfully.")
print(f"Years available: {', '.join(site_years.keys())}")
print(f"Legislation items in output: {len(output.get('legislation', []))}")
