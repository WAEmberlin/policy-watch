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
HEARINGS_FILE = OUTPUT_DIR / "hearings.json"

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
    
    # Load federal hearings (try new hearings.json first, fallback to old file)
    hearings = []
    if HEARINGS_FILE.exists():
        try:
            with open(HEARINGS_FILE, "r", encoding="utf-8") as f:
                hearings_data = json.load(f)
                if isinstance(hearings_data, dict) and "items" in hearings_data:
                    hearings = hearings_data["items"]
                elif isinstance(hearings_data, list):
                    hearings = hearings_data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load hearings.json: {e}")
            hearings = []
    elif FEDERAL_HEARINGS_FILE.exists():
        try:
            with open(FEDERAL_HEARINGS_FILE, "r", encoding="utf-8") as f:
                hearings = json.load(f)
                if not isinstance(hearings, list):
                    hearings = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load federal_hearings.json: {e}")
            hearings = []
    
    for hearing in hearings:
        date_str = hearing.get("scheduled_date", "") or hearing.get("published", "")
        if is_within_last_7_days(date_str, now):
            normalized = {
                "title": hearing.get("title", "Congressional Hearing"),
                "summary": hearing.get("summary", f"Hearing scheduled for {hearing.get('scheduled_date', '')}"),
                "source": hearing.get("source", "Federal (US Congress)"),
                "published": date_str,
                "url": hearing.get("url", ""),
                "category": "hearing"
            }
            items["congress"].append(normalized)
    
    return items


def generate_summary(items: Dict[str, List[Dict]], week_start: datetime, week_end: datetime) -> str:
    """
    Generate an enhanced weekly summary with more detail and better content selection.
    
    Uses extractive summarization techniques (no GPU required) to create
    more informative summaries than the previous simple template approach.
    
    Returns a string suitable for text-to-speech (90-180 seconds when read).
    """
    # Try to use enhanced summary generator
    try:
        from src.processing.weekly_summary_enhanced import generate_enhanced_summary
        return generate_enhanced_summary(items, week_start, week_end, max_items_per_category=5)
    except ImportError:
        # Fall back to simple summary if enhanced module not available
        pass
    
    # Fallback: Improved version of original (better than before)
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
    
    # Congress section (including bills and hearings)
    congress_bills = [item for item in items["congress"] if item.get("category") != "hearing"]
    congress_hearings = [item for item in items["congress"] if item.get("category") == "hearing"]
    
    if congress_bills or congress_hearings:
        lines.append("=== CONGRESSIONAL ACTIVITY ===")
        lines.append("")
        
        if congress_bills:
            lines.append(f"**Bills ({len(congress_bills)} total):**")
            lines.append("")
            # Show top 3-5 bills with summaries
            for i, bill in enumerate(congress_bills[:5], 1):
                title = bill.get("title", "Untitled Bill")
                # Smart truncate at word boundary
                if len(title) > 120:
                    title = title[:117].rsplit(' ', 1)[0] + "..."
                
                summary = bill.get("summary", "")
                if summary and len(summary) > 30:
                    if len(summary) > 200:
                        summary = summary[:197].rsplit(' ', 1)[0] + "..."
                    lines.append(f"{i}. {title}")
                    lines.append(f"   {summary}")
                else:
                    lines.append(f"{i}. {title}")
                
                # Add bill number if available
                bill_num = bill.get("bill_number", "")
                bill_type = bill.get("bill_type", "")
                if bill_num and bill_type:
                    lines.append(f"   ({bill_type} {bill_num})")
                lines.append("")
            
            if len(congress_bills) > 5:
                lines.append(f"... and {len(congress_bills) - 5} more bills.")
                lines.append("")
        
        if congress_hearings:
            lines.append(f"**Hearings ({len(congress_hearings)} total):**")
            lines.append("")
            for i, hearing in enumerate(congress_hearings[:5], 1):
                title = hearing.get("title", "Congressional Hearing")
                if len(title) > 120:
                    title = title[:117].rsplit(' ', 1)[0] + "..."
                
                scheduled_date = hearing.get("scheduled_date", "")
                committee = hearing.get("committee", "")
                
                lines.append(f"{i}. {title}")
                if scheduled_date:
                    lines.append(f"   Scheduled: {scheduled_date}")
                if committee:
                    lines.append(f"   Committee: {committee}")
                lines.append("")
            
            if len(congress_hearings) > 5:
                lines.append(f"... and {len(congress_hearings) - 5} more hearings.")
                lines.append("")
    else:
        lines.append("=== CONGRESSIONAL ACTIVITY ===")
        lines.append("No new congressional activity was tracked this week.")
        lines.append("")
    
    # Kansas section
    if kansas_count > 0:
        lines.append("=== KANSAS LEGISLATURE ===")
        lines.append("")
        for i, item in enumerate(items["kansas"][:5], 1):
            title = item.get("title", "Legislative Item")
            if len(title) > 120:
                title = title[:117].rsplit(' ', 1)[0] + "..."
            
            summary = item.get("summary", "")
            if summary and len(summary) > 30:
                if len(summary) > 200:
                    summary = summary[:197].rsplit(' ', 1)[0] + "..."
                lines.append(f"{i}. {title}")
                lines.append(f"   {summary}")
            else:
                lines.append(f"{i}. {title}")
            lines.append("")
        
        if kansas_count > 5:
            lines.append(f"... and {kansas_count - 5} more items.")
            lines.append("")
    else:
        lines.append("=== KANSAS LEGISLATURE ===")
        lines.append("No new Kansas legislative activity was tracked this week.")
        lines.append("")
    
    # VA section
    if va_count > 0:
        lines.append("=== VETERANS AFFAIRS ===")
        lines.append("")
        for i, item in enumerate(items["va"][:5], 1):
            title = item.get("title", "VA News")
            if len(title) > 120:
                title = title[:117].rsplit(' ', 1)[0] + "..."
            
            summary = item.get("summary", "")
            if summary and len(summary) > 30:
                if len(summary) > 200:
                    summary = summary[:197].rsplit(' ', 1)[0] + "..."
                lines.append(f"{i}. {title}")
                lines.append(f"   {summary}")
            else:
                lines.append(f"{i}. {title}")
            lines.append("")
        
        if va_count > 5:
            lines.append(f"... and {va_count - 5} more items.")
            lines.append("")
    else:
        lines.append("=== VETERANS AFFAIRS ===")
        lines.append("No new veterans-related updates were tracked this week.")
        lines.append("")
    
    # Closing
    lines.append("---")
    lines.append("Explore full details and sources at CivicWatch.")
    
    return "\n".join(lines)


def get_voice_id(api_key: str, voice_name: str = "Austin Main") -> Optional[str]:
    """
    Get voice ID by name from ElevenLabs API.
    
    Args:
        api_key: ElevenLabs API key
        voice_name: Name of the voice to find
        
    Returns:
        Voice ID string or None if not found
    """
    # Known voice IDs (fallback if API lookup fails)
    # These are commonly available ElevenLabs voices
    KNOWN_VOICE_IDS = {
        "Austin Main": "pNInz6obpgDQGcFmaJgB",  # Austin Main voice ID
        "Rachel": "21m00Tcm4TlvDq8ikWAM",
    }
    
    # Try to look up from API first (if API key has permissions)
    try:
        import requests
        
        headers = {
            "xi-api-key": api_key.strip()
        }
        
        response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=10)
        response.raise_for_status()
        
        voices = response.json().get("voices", [])
        for voice in voices:
            if voice.get("name") == voice_name:
                voice_id = voice.get("voice_id")
                print(f"Found voice '{voice_name}' with ID: {voice_id}")
                return voice_id
        
        print(f"Warning: Voice '{voice_name}' not found in API response. Available voices: {[v.get('name') for v in voices]}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"Warning: API key authentication failed (401) - may not have voice list permissions. Using known voice ID for '{voice_name}' as fallback.")
        else:
            print(f"Warning: Could not fetch voice list (HTTP {e.response.status_code}): {e}")
    except Exception as e:
        print(f"Warning: Could not fetch voice list: {e}")
    
    # Fallback to known voice ID if lookup failed
    if voice_name in KNOWN_VOICE_IDS:
        print(f"Using known voice ID for '{voice_name}': {KNOWN_VOICE_IDS[voice_name]}")
        return KNOWN_VOICE_IDS[voice_name]
    
    print(f"Warning: No known voice ID for '{voice_name}' and API lookup failed")
    return None


def generate_audio(script: str, api_key: str) -> bool:
    """
    Generate MP3 audio using ElevenLabs API.
    
    Returns True if successful, False otherwise.
    """
    try:
        import requests
        
        # Get voice ID for Austin Main
        # Try lookup first, but fallback to known ID if API doesn't have voice list permissions
        voice_id = get_voice_id(api_key, "Austin Main")
        if not voice_id:
            # Use known Austin Main voice ID directly (API key may not have voice list permissions)
            # This is fine - text-to-speech doesn't require voice list access
            print("Using known Austin Main voice ID (API may not have voice list permissions, but TTS will work)")
            voice_id = "pNInz6obpgDQGcFmaJgB"  # Austin Main voice ID
        
        # ElevenLabs API endpoint for text-to-speech
        # Using Austin Main voice
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
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

