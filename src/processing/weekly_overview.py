"""
Weekly Overview Generator for CivicWatch

Generates a weekly summary of activity from:
- Congress API (bills, votes, hearings)
- Kansas Legislature RSS feeds
- VA-related items

Creates a spoken-friendly summary and optionally generates audio via ElevenLabs.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Handle timezone on Windows (fallback if zoneinfo not available)
try:
    from zoneinfo import ZoneInfo
    central = ZoneInfo("America/Chicago")
except (ImportError, Exception):
    try:
        import pytz
        central = pytz.timezone("America/Chicago")
    except ImportError:
        from datetime import timezone, timedelta
        central = timezone(timedelta(hours=-6))  # CST is UTC-6

# File paths
OUTPUT_DIR = Path("src/output")
DOCS_DIR = Path("docs")
WEEKLY_DIR = DOCS_DIR / "weekly"
HISTORY_FILE = OUTPUT_DIR / "history.json"
LEGISLATION_FILE = OUTPUT_DIR / "legislation.json"
FEDERAL_HEARINGS_FILE = OUTPUT_DIR / "federal_hearings.json"

# Output files
LATEST_JSON = WEEKLY_DIR / "latest.json"
WEEKLY_TEXT = WEEKLY_DIR / "weekly_overview.txt"
WEEKLY_MP3 = WEEKLY_DIR / "weekly_overview.mp3"

# Ensure directories exist
WEEKLY_DIR.mkdir(parents=True, exist_ok=True)


def get_central_time() -> datetime:
    """Get current time in Central timezone."""
    if hasattr(central, 'localize'):
        # pytz timezone
        return datetime.now(central)
    else:
        # zoneinfo or timezone offset
        return datetime.now(central)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string to datetime object."""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def is_within_last_7_days(date_str: str, now: datetime) -> bool:
    """Check if a date string is within the last 7 days."""
    dt = parse_date(date_str)
    if not dt:
        return False
    
    # Make both timezone-aware for comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    
    seven_days_ago = now - timedelta(days=7)
    return dt >= seven_days_ago


def categorize_item(item: Dict) -> Optional[str]:
    """
    Categorize an item as 'congress', 'kansas', or 'va'.
    
    Returns None if item doesn't fit any category.
    """
    source = item.get("source", "").lower()
    
    # Congress/federal items
    if any(keyword in source for keyword in ["congress", "federal", "us congress"]):
        return "congress"
    
    # Kansas items
    if any(keyword in source for keyword in ["kansas", "ks legislature"]):
        return "kansas"
    
    # VA items
    if any(keyword in source for keyword in ["va", "veterans", "veterans affairs"]):
        return "va"
    
    # Check title and summary for VA keywords
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    if any(keyword in title or keyword in summary for keyword in ["veteran", "va news", "veterans affairs"]):
        return "va"
    
    return None


def load_recent_items(now: datetime) -> Dict[str, List[Dict]]:
    """
    Load items from the last 7 days and categorize them.
    
    Returns dict with keys: 'congress', 'kansas', 'va'
    """
    items = {
        "congress": [],
        "kansas": [],
        "va": []
    }
    
    # Load history.json (RSS feeds, Kansas, VA)
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load history.json: {e}")
            history = []
        
        for item in history:
            published = item.get("published", "")
            if is_within_last_7_days(published, now):
                category = categorize_item(item)
                if category:
                    items[category].append(item)
    else:
        print("No history.json found.")
    
    # Load legislation.json (Congress bills)
    if LEGISLATION_FILE.exists():
        try:
            with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
                legislation = json.load(f)
                if not isinstance(legislation, list):
                    legislation = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load legislation.json: {e}")
            legislation = []
        
        for bill in legislation:
            # Use latest_action_date or published date
            date_str = bill.get("latest_action_date") or bill.get("published", "")
            if is_within_last_7_days(date_str, now):
                # Normalize bill to same format as other items
                normalized = {
                    "title": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}: {bill.get('title', '')}",
                    "summary": bill.get("summary", ""),
                    "source": bill.get("source", "Congress.gov API"),
                    "published": date_str,
                    "url": bill.get("url", ""),
                    "bill_number": bill.get("bill_number", ""),
                    "bill_type": bill.get("bill_type", "")
                }
                items["congress"].append(normalized)
    else:
        print("No legislation.json found.")
    
    # Load federal hearings
    if FEDERAL_HEARINGS_FILE.exists():
        try:
            with open(FEDERAL_HEARINGS_FILE, "r", encoding="utf-8") as f:
                hearings = json.load(f)
                if not isinstance(hearings, list):
                    hearings = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load federal_hearings.json: {e}")
            hearings = []
        
        for hearing in hearings:
            date_str = hearing.get("scheduled_date", "")
            if is_within_last_7_days(date_str, now):
                normalized = {
                    "title": hearing.get("title", "Congressional Hearing"),
                    "summary": f"Hearing scheduled for {hearing.get('scheduled_date', '')}",
                    "source": hearing.get("source", "Federal (US Congress)"),
                    "published": date_str,
                    "url": hearing.get("url", "")
                }
                items["congress"].append(normalized)
    else:
        print("No federal_hearings.json found.")
    
    return items


def generate_summary(items: Dict[str, List[Dict]], week_start: datetime, week_end: datetime) -> str:
    """
    Generate a spoken-friendly weekly summary.
    
    Returns a string suitable for text-to-speech (45-90 seconds when read).
    """
    congress_count = len(items["congress"])
    kansas_count = len(items["kansas"])
    va_count = len(items["va"])
    
    # Format week range
    week_start_str = week_start.strftime("%B %d")
    week_end_str = week_end.strftime("%B %d")
    if week_start.year != week_end.year:
        week_start_str += f", {week_start.year}"
    week_end_str += f", {week_end.year}"
    
    # Build summary
    lines = []
    
    # Intro
    lines.append(f"Here is your CivicWatch weekly overview for the week of {week_start_str} through {week_end_str}.")
    lines.append("")
    
    # Congress section
    if congress_count > 0:
        # Get a sample item for context
        sample = items["congress"][0]
        title = sample.get("title", "legislative activity")
        # Truncate long titles
        if len(title) > 80:
            title = title[:77] + "..."
        
        if congress_count == 1:
            lines.append(f"In Congress, one item was tracked this week: {title}.")
        elif congress_count < 5:
            lines.append(f"In Congress, {congress_count} items were tracked this week, including {title}.")
        else:
            lines.append(f"In Congress, {congress_count} items were tracked this week, including {title} and others.")
    else:
        lines.append("In Congress, no new activity was tracked this week.")
    
    lines.append("")
    
    # Kansas section
    if kansas_count > 0:
        sample = items["kansas"][0]
        title = sample.get("title", "legislative activity")
        if len(title) > 80:
            title = title[:77] + "..."
        
        if kansas_count == 1:
            lines.append(f"In Kansas, one legislative item was tracked this week: {title}.")
        elif kansas_count < 5:
            lines.append(f"In Kansas, {kansas_count} legislative items were tracked this week, including {title}.")
        else:
            lines.append(f"In Kansas, {kansas_count} legislative items were tracked this week, including {title} and others.")
    else:
        lines.append("In Kansas, no new legislative activity was tracked this week.")
    
    lines.append("")
    
    # VA section
    if va_count > 0:
        sample = items["va"][0]
        title = sample.get("title", "news update")
        if len(title) > 80:
            title = title[:77] + "..."
        
        if va_count == 1:
            lines.append(f"Veterans-related updates this week included {title}.")
        elif va_count < 5:
            lines.append(f"Veterans-related updates this week included {va_count} items, including {title}.")
        else:
            lines.append(f"Veterans-related updates this week included {va_count} items, including {title} and others.")
    else:
        lines.append("No veterans-related updates were tracked this week.")
    
    lines.append("")
    
    # Closing
    lines.append("You can explore full details and sources at CivicWatch.")
    
    return "\n".join(lines)


def generate_audio(script: str, api_key: str) -> bool:
    """
    Generate MP3 audio using ElevenLabs API.
    
    Returns True if successful, False otherwise.
    """
    try:
        import requests
        
        # ElevenLabs API endpoint for text-to-speech
        # Using a standard voice available on free tier (Rachel - neutral, professional)
        # Voice ID: 21m00Tcm4TlvDq8ikWAM (Rachel)
        # You can change this to other available voices if desired
        # Note: Model updated to eleven_turbo_v2_5 (eleven_monolingual_v1 is no longer on free tier)
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        
        # Clean the API key (remove any whitespace)
        api_key_clean = api_key.strip()
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key_clean
        }
        
        data = {
            "text": script,
            "model_id": "eleven_flash_v2_5",  # Free tier model - Eleven Flash v2.5
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=60)
        
        # Check for specific error codes
        if response.status_code == 401:
            print("Error: 401 Unauthorized - API key is invalid or missing")
            print("Please check:")
            print("  1. The API key is correct (no extra spaces or quotes)")
            print("  2. The API key is active in your ElevenLabs account")
            print("  3. The API key has text-to-speech permissions")
            print("  4. For local testing, set ELEVENLABS_API_KEY environment variable")
            print("  5. For GitHub Actions, check the secret is set correctly")
            # Try to get more info from the response
            try:
                error_detail = response.json()
                if "detail" in error_detail:
                    print(f"   API Error Detail: {error_detail.get('detail', {}).get('message', 'Unknown error')}")
                elif "message" in error_detail:
                    print(f"   API Error Message: {error_detail.get('message', 'Unknown error')}")
            except:
                pass
            return False
        elif response.status_code == 429:
            print("Error: 429 Rate Limit - You've exceeded your character limit")
            print("Free tier allows 10,000 characters per month")
            return False
        
        response.raise_for_status()
        
        # Save MP3 file
        with open(WEEKLY_MP3, "wb") as f:
            f.write(response.content)
        
        print(f"Successfully generated audio: {WEEKLY_MP3}")
        return True
        
    except ImportError:
        print("Warning: requests library not available. Install with: pip install requests")
        return False
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            status_code = e.response.status_code
            if status_code == 401:
                print(f"Error: 401 Unauthorized - API key is invalid or missing")
                print("Please verify your ElevenLabs API key is correct and active.")
            elif status_code == 429:
                print(f"Error: 429 Rate Limit - Character limit exceeded")
            else:
                print(f"Error generating audio with ElevenLabs: {e}")
                print(f"Status code: {status_code}")
        else:
            print(f"Error generating audio with ElevenLabs: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error generating audio: {e}")
        return False


def main():
    """Main entry point for weekly overview generation."""
    print("Generating weekly overview...")
    
    # Get current time in Central timezone
    now = get_central_time()
    
    # Calculate week range (last 7 days)
    week_end = now
    week_start = week_end - timedelta(days=7)
    
    # Load recent items
    print("Loading items from the last 7 days...")
    items = load_recent_items(now)
    
    congress_count = len(items["congress"])
    kansas_count = len(items["kansas"])
    va_count = len(items["va"])
    
    print(f"Found {congress_count} Congress items, {kansas_count} Kansas items, {va_count} VA items")
    
    # Generate summary script
    print("Generating summary script...")
    weekly_script = generate_summary(items, week_start, week_end)
    
    # Save text file
    with open(WEEKLY_TEXT, "w", encoding="utf-8") as f:
        f.write(weekly_script)
    print(f"Saved text script: {WEEKLY_TEXT}")
    
    # Create metadata JSON
    metadata = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "item_counts": {
            "congress": congress_count,
            "kansas": kansas_count,
            "va": va_count
        },
        "script": weekly_script,
        "generated_at": now.isoformat()
    }
    
    # Save JSON metadata
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata: {LATEST_JSON}")
    
    # Generate audio if API key is available
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if api_key:
        # Debug: Check if key looks valid (without exposing the actual key)
        api_key_clean = api_key.strip()
        if len(api_key_clean) != len(api_key):
            print("Warning: API key has leading/trailing whitespace - trimming it")
            api_key = api_key_clean
        
        print(f"Generating audio with ElevenLabs...")
        print(f"API key length: {len(api_key)} characters")
        print(f"API key starts with: {api_key[:4]}...")  # Show first 4 chars for debugging
        success = generate_audio(weekly_script, api_key)
        if success:
            metadata["audio_available"] = True
            metadata["audio_file"] = "weekly/weekly_overview.mp3"
        else:
            metadata["audio_available"] = False
            metadata["audio_file"] = None
    else:
        print("ELEVENLABS_API_KEY not set, skipping audio generation")
        metadata["audio_available"] = False
        metadata["audio_file"] = None
    
    # Update JSON with audio info
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    print("Weekly overview generation complete!")


if __name__ == "__main__":
    main()

