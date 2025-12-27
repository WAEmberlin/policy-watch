import json
import smtplib
import os
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load feed data
with open("src/output/daily.json", "r", encoding="utf-8") as f:
    data = json.load(f)

now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)

items = []
for item in data["items"]:
    try:
        published = datetime.fromisoformat(item["published"])
        if published >= cutoff:
            items.append(item)
    except Exception:
        continue

if not items:
    print("No new items in last 24 hours.")
    exit(0)

# Build HTML email
html_parts = []
html_parts.append("<h2>Policy Watch — Last 24 Hours</h2>")

grouped = {}
for item in items:
    grouped.setdefault(item["source"], []).append(item)

for source, entries in grouped.items():
    html_parts.append(f"<h3>{source}</h3><ul>")
    for e in entries:
        html_parts.append(
            f"<li><a href='{e['link']}'>{e['title']}</a></li>"
        )
    html_parts.append("</ul>")

html_body = "\n".join(html_parts)

msg = MIMEMultipart("alternative")
msg["Subject"] = "Policy Watch – Daily Legislative Update"
msg["From"] = os.environ["EMAIL_USER"]
msg["To"] = os.environ["EMAIL_TO"]

msg.attach(MIMEText(html_body, "html"))

# Send email
server = smtplib.SMTP(os.environ["EMAIL_HOST"], int(os.environ["EMAIL_PORT"]))
server.starttls()
server.login(os.environ["EMAIL_USER"], os.environ["EMAIL_PASS"])
server.send_message(msg)
server.quit()

print("Email sent successfully.")
