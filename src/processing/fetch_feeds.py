import feedparser
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# -------------------------
# Configuration
# -------------------------

FEEDS = [
    {
        "name": "Congress.gov",
        "url": "https://www.congress.gov/rss/most-viewed.xml",
    },
    {
        "name": "Federal Register",
        "url": "https://www.federalregister.gov/articles/search.rss",
    },
]

OUTPUT_DIR = "src/output"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.json")
ITEMS_FILE = os.path.join(OUTPUT_DIR, "items.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

central = ZoneInfo("America/Chicago")

# -------------------------
# Helpers
# -------------------------

def load_json_safe(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def normalize_date(entry):
    """
    Convert feedparser dates → ISO format
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=central).isoformat()

    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=central).isoformat()

    return datetime.now(central).isoformat()

# -------------------------
# Fetch feeds
# -------------------------

items = []

for feed in FEEDS:
    parsed = feedparser.parse(feed["url"])

    for entry in parsed.entries:
        item = {
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", "").strip(),
            "source": feed["name"],
            "published": normalize_date(entry),
        }

        if item["title"] and item["link"]:
            items.append(item)

# -------------------------
# Load existing history
# -------------------------

history = load_json_safe(HISTORY_FILE)

# Combine new + old
combined = history + items

# Deduplicate by link
seen = set()
deduped = []

for item in sorted(combined, key=lambda x: x.get("published", ""), reverse=True):
    link = item.get("link")
    if link and link not in seen:
        seen.add(link)
        deduped.append(item)

# -------------------------
# Keep only last 365 days
# -------------------------

cutoff = datetime.now(central) - timedelta(days=365)
filtered = []

for item in deduped:
    try:
        dt = datetime.fromisoformat(item["published"])
        if dt >= cutoff:
            filtered.append(item)
    except Exception:
        continue

# -------------------------
# Save full history
# -------------------------

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(filtered, f, indent=2)

# -------------------------
# Save last 24 hours for email
# -------------------------

now = datetime.now(central)
recent = []

for item in filtered:
    try:
        dt = datetime.fromisoformat(item["published"])
        if (now - dt).total_seconds() <= 86400:
            recent.append(item)
    except Exception:
        continue

with open(ITEMS_FILE, "w", encoding="utf-8") as f:
    json.dump(recent, f, indent=2)

# -------------------------
# Summary output
# -------------------------

print("Fetch complete.")
print(f"Total stored (last 365 days): {len(filtered)}")
print(f"Items in last 24 hours: {len(recent)}")
