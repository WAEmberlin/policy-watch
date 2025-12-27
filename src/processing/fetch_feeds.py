import feedparser
import yaml
import json
from datetime import datetime, timezone

with open("src/feeds/feeds.yaml", "r") as f:
    config = yaml.safe_load(f)

results = []

for key, feed in config["feeds"].items():
    if "url" not in feed:
        continue

    parsed = feedparser.parse(feed["url"])

    for entry in parsed.entries:
        results.append({
            "source": feed["name"],
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")
        })

output = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "items": results
}

with open("src/output/daily.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2)

print(f"Collected {len(results)} items.")
