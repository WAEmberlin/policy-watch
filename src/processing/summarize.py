import json
import os
from datetime import datetime, timezone
from collections import defaultdict

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
HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.json")
LEGISLATION_FILE = os.path.join(OUTPUT_DIR, "legislation.json")
FEDERAL_HEARINGS_FILE = os.path.join(OUTPUT_DIR, "federal_hearings.json")
HEARINGS_FILE = os.path.join(OUTPUT_DIR, "hearings.json")
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
        
        # Create item in same format as RSS items for consistency
        item = {
            "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {bill.get('title', '')}",
            "link": bill.get("url", ""),
            "summary": bill.get("summary", ""),
            "source": source,
            "published": bill.get("published", date_str),
            # Additional legislation-specific fields
            "bill_number": bill.get("bill_number", ""),
            "bill_type": bill.get("bill_type", ""),
            "sponsor_name": bill.get("sponsor_name", ""),
            "latest_action": bill.get("latest_action", ""),
            "latest_action_date": bill.get("latest_action_date", ""),
            "congress": bill.get("congress", 119)
        }
        
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
                "source": "State (Kansas Legislature)"  # Mark as state hearing
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

# Separate federal hearings into upcoming and historical
federal_upcoming = []
federal_historical = []

for hearing in federal_hearings:
    # Ensure hearing has required fields for frontend
    if not hearing.get("url") and hearing.get("link"):
        hearing["url"] = hearing["link"]
    if not hearing.get("link") and hearing.get("url"):
        hearing["link"] = hearing["url"]
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

output = {
    "last_updated": now.isoformat(),
    "years": site_years,
    "legislation": {
        "total_items": len(legislation_data),
        "pages": legislation_pages  # Paginated legislation data
    },
    "upcoming_hearings": all_upcoming_hearings,  # Upcoming hearings (state + federal)
    "historical_hearings": all_historical_hearings  # Past hearings (state + federal)
}

# Ensure legislation key is always present
if "legislation" not in output:
    output["legislation"] = {"total_items": 0, "pages": []}

with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print("Site data generated successfully.")
print(f"Years available: {', '.join(site_years.keys())}")
print(f"Legislation items in output: {len(output.get('legislation', []))}")
