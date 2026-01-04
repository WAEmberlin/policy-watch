import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

HISTORY_FILE = "src/output/history.json"
LEGISLATION_FILE = "src/output/legislation.json"
HEARINGS_FILE = "src/output/hearings.json"

EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO")

# Load items from history.json (RSS feeds, Kansas, VA)
now = datetime.now(timezone.utc)
recent_items = []

# Load history.json (main source for RSS feeds)
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            if not isinstance(history, list):
                history = []
            
            # Filter last 6 hours
            for item in history:
                try:
                    published_str = item.get("published", "")
                    if not published_str:
                        continue
                    ts = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    if (now - ts).total_seconds() <= 21600:  # 6 hours = 21600 seconds
                        recent_items.append(item)
                except Exception:
                    continue
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load history.json: {e}")

# Load legislation.json (Congress bills)
if os.path.exists(LEGISLATION_FILE):
    try:
        with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
            legislation = json.load(f)
            if not isinstance(legislation, list):
                legislation = []
            
            # Filter last 6 hours from bills
            for bill in legislation:
                try:
                    # Use latest_action_date or published date
                    date_str = bill.get("latest_action_date") or bill.get("published", "")
                    if not date_str:
                        continue
                    ts = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if (now - ts).total_seconds() <= 21600:  # 6 hours = 21600 seconds
                        # Normalize bill to same format as other items
                        normalized = {
                            "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {bill.get('title', '')}",
                            "summary": bill.get("summary", ""),
                            "source": bill.get("source", "Congress.gov API"),
                            "published": date_str,
                            "link": bill.get("url", "")
                        }
                        recent_items.append(normalized)
                except Exception:
                    continue
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load legislation.json: {e}")

# Sort by published date (newest first)
recent_items.sort(key=lambda x: x.get("published", ""), reverse=True)


# Load and filter hearings for next calendar day
tomorrow_hearings = []
if os.path.exists(HEARINGS_FILE):
    try:
        with open(HEARINGS_FILE, "r", encoding="utf-8") as f:
            hearings_data = json.load(f)
            hearings_list = hearings_data.get("items", []) if isinstance(hearings_data, dict) else hearings_data
            
            # Get tomorrow's date
            tomorrow = (now + timedelta(days=1)).date()
            
            for hearing in hearings_list:
                scheduled_date = hearing.get("scheduled_date", "")
                if scheduled_date:
                    try:
                        # Parse date (handle ISO format)
                        if "T" in scheduled_date:
                            hearing_date = datetime.fromisoformat(scheduled_date.replace("Z", "+00:00")).date()
                        else:
                            hearing_date = datetime.fromisoformat(scheduled_date + "T00:00:00+00:00").date()
                        
                        if hearing_date == tomorrow:
                            tomorrow_hearings.append(hearing)
                    except (ValueError, AttributeError):
                        continue
    except (json.JSONDecodeError, IOError):
        pass

# Build email content
html_body = ""

if recent_items:
    html_body += "<h2>Policy Watch – Updates in the Last 6 Hours</h2><ul>"
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
    html_body += """
    <h2>Policy Watch Update</h2>
    <p>No new legislative or policy updates were published in the last 6 hours.</p>
    <p>Your monitoring system is running normally.</p>
    """
    subject = "Policy Watch — No new updates"

# Add hearings section
if tomorrow_hearings:
    html_body += f"<h2>📘 Congressional Hearings Scheduled for Tomorrow</h2><ul>"
    for hearing in tomorrow_hearings:
        title = hearing.get("title", "(no title)")
        committee = hearing.get("committee", "")
        chamber = hearing.get("chamber", "")
        time_str = hearing.get("scheduled_time", "")
        location = hearing.get("location", "")
        url = hearing.get("url", "")
        
        hearing_info = f"<strong>{title}</strong>"
        if committee:
            hearing_info += f"<br>Committee: {committee}"
        if chamber:
            hearing_info += f" ({chamber})"
        if time_str:
            hearing_info += f"<br>Time: {time_str}"
        if location:
            hearing_info += f"<br>Location: {location}"
        if url:
            hearing_info += f"<br><a href=\"{url}\">View on Congress.gov</a>"
        
        html_body += f"<li>{hearing_info}</li><hr>"
    html_body += "</ul>"
    
    if recent_items:
        subject += f" + {len(tomorrow_hearings)} hearing{'s' if len(tomorrow_hearings) != 1 else ''} tomorrow"
    else:
        subject = f"Policy Watch — {len(tomorrow_hearings)} hearing{'s' if len(tomorrow_hearings) != 1 else ''} scheduled tomorrow"

# Build email
msg = MIMEMultipart("alternative")
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_TO
msg["Subject"] = subject

msg.attach(MIMEText(html_body, "html"))

# Send email
try:
    if not all([EMAIL_HOST, EMAIL_USER, EMAIL_PASS, EMAIL_TO]):
        missing = [k for k, v in {
            "EMAIL_HOST": EMAIL_HOST,
            "EMAIL_USER": EMAIL_USER,
            "EMAIL_PASS": EMAIL_PASS,
            "EMAIL_TO": EMAIL_TO
        }.items() if not v]
        raise ValueError(f"Missing required email configuration: {', '.join(missing)}")
    
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    
    print(f"Email sent successfully to {EMAIL_TO}")
    print(f"Subject: {subject}")
    print(f"Recent items: {len(recent_items)}, Tomorrow hearings: {len(tomorrow_hearings)}")
except Exception as e:
    print(f"ERROR: Failed to send email: {e}")
    raise  # Re-raise so workflow shows failure
