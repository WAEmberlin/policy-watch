import json
import os
from datetime import datetime
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

        grouped[year][date_str][source].append(item)
        processed_count += 1
    except Exception as e:
        print(f"Warning: Skipping item due to error: {e}")
        continue

print(f"Processed {processed_count} items into grouped structure.")

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
                flat_items.append({
                    "date": day,
                    "source": source,
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "published": item.get("published"),
                    "summary": item.get("summary", "")  # Include summary for search
                })

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

output = {
    "last_updated": now.isoformat(),
    "years": site_years
}

with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print("Site data generated successfully.")
print(f"Years available: {', '.join(site_years.keys())}")
