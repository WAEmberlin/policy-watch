import json
from datetime import datetime, timezone
from pathlib import Path
import html

INPUT = Path("src/output/daily.json")
OUTPUT = Path("src/output/index.html")

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

grouped = {}
for item in data["items"]:
    grouped.setdefault(item["source"], []).append(item)

html_parts = []

html_parts.append(f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Policy Watch Daily Digest</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{
  font-family: system-ui, sans-serif;
  margin: 2rem;
  background: #f7f7f7;
}}
h1 {{ color: #2c3e50; }}
h2 {{ margin-top: 2rem; color: #34495e; }}
.item {{
  background: white;
  padding: 1rem;
  margin: 0.75rem 0;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
a {{ text-decoration: none; color: #1a73e8; }}
.date {{ color: #666; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Policy Watch — Daily Digest</h1>
<p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
""")

for source, items in grouped.items():
    html_parts.append(f"<h2>{html.escape(source)}</h2>")
    for item in items:
        html_parts.append(f"""
        <div class="item">
          <a href="{html.escape(item['link'])}" target="_blank">
            <strong>{html.escape(item['title'])}</strong>
          </a>
          <div class="date">{html.escape(item.get("published",""))}</div>
          <div>{item.get("summary","")}</div>
        </div>
        """)

html_parts.append("</body></html>")

OUTPUT.write_text("\n".join(html_parts), encoding="utf-8")

print("HTML digest generated.")
