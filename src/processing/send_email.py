import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

OUTPUT_FILE = "src/output/items.json"

EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO")

# Load items
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)
else:
    items = []

# Filter last 24 hours
now = datetime.now(timezone.utc)
recent_items = []

for item in items:
    try:
        ts = datetime.fromisoformat(item["published"].replace("Z", "+00:00"))
        if (now - ts).total_seconds() <= 86400:
            recent_items.append(item)
    except Exception:
        continue


# Build email content
if recent_items:
    html_body = "<h2>Policy Watch – Updates in the Last 24 Hours</h2><ul>"
    for item in recent_items:
        html_body += f"""
        <li>
          <strong>{item.get("title","(no title)")}</strong><br>
          <a href="{item.get("link")}">{item.get("link")}</a><br>
          <p>{item.get("summary","")}</p>
        </li>
        <hr>
        """
    html_body += "</ul>"
    subject = f"Policy Watch — {len(recent_items)} new updates"
else:
    html_body = """
    <h2>Policy Watch Daily Update</h2>
    <p>No new legislative or policy updates were published in the last 24 hours.</p>
    <p>Your monitoring system is running normally.</p>
    """
    subject = "Policy Watch — No new updates today"

# Build email
msg = MIMEMultipart("alternative")
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_TO
msg["Subject"] = subject

msg.attach(MIMEText(html_body, "html"))

# Send email
with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)

print("Email sent successfully.")
