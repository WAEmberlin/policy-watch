import os
import json
from datetime import datetime
from collections import defaultdict
import pytz

# Paths
OUTPUT_DIR = "src/output"
INPUT_FILE = os.path.join(OUTPUT_DIR, "items.json")
HTML_FILE = "docs/index.html"

# Ensure output directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("docs", exist_ok=True)

# Load items safely
if os.path.exists(INPUT_FILE):
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except json.JSONDecodeError:
        items = []
else:
    items = []

# Timezone setup
central = pytz.timezone("US/Central")
now_central = datetime.now(central)
last_updated = now_central.strftime("%B %d, %Y at %I:%M %p %Z")

# Group items by date → source
grouped = defaultdict(lambda: defaultdict(list))

for item in items:
    date = item.get("date", "Unknown Date")
    source = item.get("source", "Unknown Source")

    grouped[date][source].append(item)

# Sort dates newest → oldest (best effort)
def parse_date_safe(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime.min

sorted_dates = sorted(grouped.keys(), key=parse_date_safe, reverse=True)

# ---------- Build HTML ----------
html_parts = []

html_parts.append(f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Policy Watch</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 40px;
    background: #f9f9f9;
    color: #222;
}}

h1 {{
    margin-bottom: 5px;
}}

.updated {{
    color: #555;
    margin-bottom: 30px;
}}

.date-block {{
    margin-bottom: 40px;
    padding: 20px;
    background: white;
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}

.source-block {{
    margin-top: 15px;
    padding-left: 15px;
    border-left: 4px solid #ccc;
}}

ul {{
    margin-top: 8px;
}}

li {{
    margin-bottom: 8px;
}}

.empty {{
    font-style: italic;
    color: #777;
}}
</style>
</head>
<body>

<h1>Policy Watch</h1>
<p class="updated"><strong>Last updated:</strong> {last_updated}</p>
""")

# If no items at all
if not grouped:
    html_parts.append("""
    <div class="date-block">
        <p class="empty">No updates available yet.</p>
    </div>
    """)
else:
    for date in sorted_dates:
        html_parts.append(f"""
        <div class="date-block">
            <h2>{date}</h2>
        """)

        sources = grouped[date]

        for source, items_list in sources.items():
            html_parts.append(f"""
            <div class="source-block">
                <h3>{source}</h3>
            """)

            if not items_list:
                html_parts.append("<p class='empty'>No new updates for this date.</p>")
            else:
                html_parts.append("<ul>")
                for item in items_list:
                    title = item.get("title", "Untitled")
                    link = item.get("link", "#")
                    summary = item.get("summary", "")

                    html_parts.append(f"""
                    <li>
                        <a href="{link}" target="_blank"><strong>{title}</strong></a><br/>
                        <small>{summary}</small>
                    </li>
                    """)

                html_parts.append("</ul>")

            html_parts.append("</div>")

        html_parts.append("</div>")

# Close HTML
html_parts.append("""
</body>
</html>
""")

# Write file
with open(HTML_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(html_parts))

print("✅ Website HTML generated successfully.")
