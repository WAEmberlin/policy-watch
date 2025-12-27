import json
from datetime import datetime
from collections import defaultdict
from zoneinfo import ZoneInfo

INPUT_FILE = "src/output/items.json"
OUTPUT_FILE = "docs/index.html"

CENTRAL = ZoneInfo("America/Chicago")

# Load items
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    items = json.load(f)

# Normalize + group by date and source
grouped = defaultdict(lambda: defaultdict(list))

for item in items:
    try:
        published = datetime.fromisoformat(
            item["published"].replace("Z", "+00:00")
        ).astimezone(CENTRAL)

        date_key = published.strftime("%Y-%m-%d")
        source = item.get("source", "Other")

        grouped[date_key][source].append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "summary": item.get("summary", "")
        })

    except Exception:
        continue


# Sort dates newest → oldest
sorted_dates = sorted(grouped.keys(), reverse=True)

# Timestamp for header
last_updated = datetime.now(CENTRAL).strftime("%B %d, %Y at %I:%M %p %Z")

# Known sources (order matters)
KNOWN_SOURCES = [
    "Kansas Legislature",
    "US Congress",
    "VA News"
]

html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Policy Watch</title>
<style>
body {{
    font-family: Arial, sans-serif;
    max-width: 900px;
    margin: auto;
    padding: 20px;
    background: #fafafa;
}}

h1 {{
    margin-bottom: 0;
}}

.updated {{
    color: #555;
    margin-bottom: 30px;
}}

.date-block {{
    margin-top: 40px;
}}

.source-block {{
    margin-left: 20px;
    margin-bottom: 20px;
}}

.item {{
    margin-left: 20px;
    margin-bottom: 10px;
}}

a {{
    text-decoration: none;
    color: #1a4fb3;
}}

a:hover {{
    text-decoration: underline;
}}

hr {{
    margin-top: 40px;
}}
</style>
</head>
<body>

<h1>Policy Watch</h1>
<div class="updated"><strong>Last updated:</strong> {last_updated}</div>
"""

for date in sorted_dates:
    readable_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")

    html += f"<div class='date-block'>"
    html += f"<h2>📅 {readable_date}</h2>"

    for source in KNOWN_SOURCES:
        html += f"<div class='source-block'>"
        html += f"<h3>{source}</h3>"

        items_for_source = grouped[date].get(source, [])

        if not items_for_source:
            html += "<p><em>No new updates for this date.</em></p>"
        else:
            for item in items_for_source:
                html += f"""
                <div class="item">
                    <a href="{item['link']}" target="_blank">
                        <strong>{item['title']}</strong>
                    </a>
                    <div>{item['summary']}</div>
                </div>
                """

        html += "</div>"

    html += "</div><hr>"

html += """
</body>
</html>
"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("HTML digest generated.")
