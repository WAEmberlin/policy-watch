import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

OUTPUT_DIR = "src/output"
DOCS_DIR = "docs"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.json")
SITE_DATA_FILE = os.path.join(DOCS_DIR, "site_data.json")

ITEMS_PER_PAGE = 50
central = ZoneInfo("America/Chicago")

# -------------------------
# Load history
# -------------------------
# Ensure docs directory exists
os.makedirs(DOCS_DIR, exist_ok=True)

if not os.path.exists(HISTORY_FILE):
    print("No history.json found — creating empty site data.")
    data = {
        "last_updated": datetime.now(central).isoformat(),
        "years": {}
    }
    with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    exit(0)

with open(HISTORY_FILE, "r", encoding="utf-8") as f:
    history = json.load(f)

# -------------------------
# Group data
# -------------------------
grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

for item in history:
    try:
        dt = datetime.fromisoformat(item["published"])
    except Exception:
        continue

    year = str(dt.year)
    date_str = dt.strftime("%Y-%m-%d")
    source = item.get("source", "Unknown")

    grouped[year][date_str][source].append(item)

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
                    "published": item.get("published")
                })

    # Pagination
    pages = []
    for i in range(0, len(flat_items), ITEMS_PER_PAGE):
        pages.append(flat_items[i:i + ITEMS_PER_PAGE])

    site_years[year] = {
        "total_items": len(flat_items),
        "pages": pages,
        "grouped": grouped[year]
    }

# -------------------------
# Write output
# -------------------------
output = {
    "last_updated": datetime.now(central).isoformat(),
    "years": site_years
}

with open(SITE_DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print("Site data generated successfully.")
print(f"Years available: {', '.join(site_years.keys())}")
