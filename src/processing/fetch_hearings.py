"""
Fetch Congressional committee meetings (including hearings) from the Congress.gov API.

This module:
- Fetches from the /v3/committee-meeting/{congress} endpoint for SCHEDULED meetings
- Also fetches from /v3/hearing/{congress} for HISTORICAL published hearings
- Supports filtering by status (Scheduled, Canceled, Postponed, Rescheduled)
- Implements pagination using pagination.next URLs
- Normalizes data into CivicWatch schema
- Handles API rate limits and missing fields safely
"""
import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEARINGS_FILE = OUTPUT_DIR / "hearings.json"

# Congress.gov API configuration
API_BASE_URL = "https://api.congress.gov/v3"
CONGRESS_NUMBER = 119  # 119th Congress (2025-2026)

# Rate limiting: API allows 1000 requests per hour
REQUEST_DELAY = 0.1  # 100ms between requests


def get_api_key() -> str:
    """
    Get the Congress.gov API key from environment variable.
    """
    api_key = os.environ.get("CONGRESS_API_KEY")
    if not api_key:
        raise ValueError(
            "CONGRESS_API_KEY environment variable not set. "
            "Get a free API key from https://api.data.gov/signup/ "
            "and set it as an environment variable."
        )
    return api_key


def fetch_committee_meetings(
    api_key: str,
    congress: int = CONGRESS_NUMBER,
    chamber: Optional[str] = None,
    days_back: int = 30,
    days_forward: int = 90
) -> List[Dict]:
    """
    Fetch committee meetings (including scheduled hearings) from the Congress.gov API.
    
    Uses the endpoint: /v3/committee-meeting/{congress}
    Optional: /v3/committee-meeting/{congress}/house or /v3/committee-meeting/{congress}/senate
    
    This endpoint returns SCHEDULED meetings with status like "Scheduled", "Canceled", etc.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number (default: 119)
        chamber: Optional chamber filter ("house" or "senate")
        days_back: How many days back to look
        days_forward: How many days forward to look
    
    Returns:
        List of normalized meeting dictionaries
    """
    meetings = []
    
    # Build the base URL for committee-meeting endpoint
    if chamber:
        url = f"{API_BASE_URL}/committee-meeting/{congress}/{chamber.lower()}"
    else:
        url = f"{API_BASE_URL}/committee-meeting/{congress}"
    
    # Calculate date range for filtering (will filter after fetching details)
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).date()
    end_date = (now + timedelta(days=days_forward)).date()
    
    print(f"Fetching committee meetings from Congress.gov API...")
    print(f"  Endpoint: committee-meeting/{congress}")
    print(f"  Date range: {start_date} to {end_date}")
    if chamber:
        print(f"  Chamber: {chamber}")
    
    # Collect all meeting URLs first (list endpoint doesn't have dates)
    meeting_urls = []
    current_url = url
    page = 1
    max_pages = 20  # Reduced - we'll filter by date after fetching details
    
    while current_url and page <= max_pages:
        try:
            if "?" in current_url:
                request_url = f"{current_url}&api_key={api_key}&format=json&limit=250"
            else:
                request_url = f"{current_url}?api_key={api_key}&format=json&limit=250"
            
            print(f"  Fetching page {page}...")
            response = requests.get(request_url, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            
            data = response.json()
            meetings_list = data.get("committeeMeetings", [])
            
            if not meetings_list:
                print(f"  No meetings found on page {page}")
                break
            
            print(f"  Found {len(meetings_list)} meetings on page {page}")
            
            # Collect URLs for detail fetching
            for i, meeting in enumerate(meetings_list):
                if page == 1 and i == 0:
                    print(f"  Debug: First meeting keys: {list(meeting.keys())}")
                
                detail_url = meeting.get("url", "")
                event_id = meeting.get("eventId", "")
                meeting_chamber = meeting.get("chamber", "")
                
                if detail_url:
                    meeting_urls.append({
                        "url": detail_url,
                        "event_id": event_id,
                        "chamber": meeting_chamber
                    })
            
            pagination = data.get("pagination", {})
            current_url = pagination.get("next")
            
            if current_url:
                if "api_key=" in current_url:
                    current_url = current_url.split("api_key=")[0].rstrip("&?")
                page += 1
            else:
                print(f"  No more pages (reached end)")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching meetings (page {page}): {e}")
            break
        except Exception as e:
            print(f"  Unexpected error on page {page}: {e}")
            break
    
    print(f"  Collected {len(meeting_urls)} meeting URLs, fetching details...")
    
    # Fetch details for each meeting (with date filtering)
    in_range_count = 0
    out_of_range_count = 0
    error_count = 0
    
    for i, meeting_info in enumerate(meeting_urls):
        if (i + 1) % 50 == 0:
            print(f"    Processing {i + 1}/{len(meeting_urls)}... ({in_range_count} in range so far)")
        
        detail = fetch_meeting_detail_with_date_filter(
            api_key, 
            meeting_info["url"], 
            meeting_info["event_id"],
            meeting_info["chamber"],
            congress,
            start_date,
            end_date
        )
        
        if detail:
            if detail.get("_in_range"):
                meetings.append(detail)
                in_range_count += 1
            else:
                out_of_range_count += 1
        else:
            error_count += 1
        
        # Early stop if we're getting mostly out-of-range meetings
        # (API returns newest first, so old meetings mean we're past our range)
        if i > 100 and in_range_count == 0:
            print(f"    No in-range meetings found in first 100, stopping early")
            break
    
    print(f"  Fetched {in_range_count} meetings in date range ({out_of_range_count} out of range, {error_count} errors)")
    return meetings


def fetch_meeting_detail_with_date_filter(
    api_key: str, 
    detail_url: str, 
    event_id: str,
    chamber: str,
    congress: int,
    start_date,
    end_date
) -> Optional[Dict]:
    """
    Fetch full details for a committee meeting and filter by date.
    
    Returns meeting dict with _in_range=True if in date range, or _in_range=False if not.
    Returns None on error.
    """
    try:
        params = {"api_key": api_key, "format": "json"}
        response = requests.get(detail_url, params=params, timeout=30)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        
        data = response.json()
        meeting_data = data.get("committeeMeeting", data)
        
        # Extract date first for filtering
        meeting_date_str = meeting_data.get("date", "")
        if not meeting_date_str:
            return None
        
        # Parse the date
        try:
            if "T" in meeting_date_str:
                meeting_dt = datetime.fromisoformat(meeting_date_str.replace("Z", "+00:00"))
            else:
                meeting_dt = datetime.fromisoformat(meeting_date_str + "T00:00:00+00:00")
            
            meeting_date = meeting_dt.date()
            scheduled_date = meeting_date.isoformat()
            scheduled_time = meeting_dt.strftime("%H:%M") if meeting_dt.time() != datetime.min.time() else ""
            published = meeting_dt.isoformat()
        except (ValueError, AttributeError):
            return None
        
        # Check date range
        in_range = start_date <= meeting_date <= end_date
        
        # Extract title
        title = meeting_data.get("title", "").strip()
        if not title:
            title = "Committee Meeting"
        
        # Extract meeting type and status
        meeting_type = meeting_data.get("meetingType", "Meeting")
        meeting_status = meeting_data.get("meetingStatus", "Scheduled")
        
        # Add status to title if not Scheduled
        if meeting_status and meeting_status.lower() not in ["scheduled", ""]:
            title = f"[{meeting_status.upper()}] {title}"
        
        # Extract chamber
        chamber = meeting_data.get("chamber", chamber or "").capitalize()
        
        # Extract committee names
        committees_list = meeting_data.get("committees", [])
        committee_names = []
        for comm in committees_list:
            if isinstance(comm, dict):
                name = comm.get("name", "")
                if name:
                    committee_names.append(name)
            elif isinstance(comm, str):
                committee_names.append(comm)
        committee_str = ", ".join(committee_names) if committee_names else ""
        
        # Extract location
        location_parts = []
        location_data = meeting_data.get("location", {})
        if isinstance(location_data, dict):
            room = location_data.get("room", "")
            building = location_data.get("building", "")
            if room and room != "WEBEX":
                location_parts.append(f"Room {room}")
            if building and building != "----------":
                location_parts.append(building)
        location = ", ".join(location_parts) if location_parts else ""
        
        # Extract associated bills
        bills = []
        related_items = meeting_data.get("relatedItems", {})
        bills_data = related_items.get("bills", [])
        for bill in bills_data:
            if isinstance(bill, dict):
                bill_type = bill.get("type", "")
                bill_number = bill.get("number", "")
                if bill_type and bill_number:
                    bills.append(f"{bill_type} {bill_number}")
        bill_str = ", ".join(bills) if bills else ""
        
        # Build URL
        url = f"https://www.congress.gov/event/{congress}th-congress/committee-meeting/{event_id}"
        
        # Generate summary
        summary = f"Congressional {meeting_type.lower()} "
        if meeting_status.lower() not in ["scheduled", ""]:
            summary = f"{meeting_status} congressional {meeting_type.lower()} "
        if committee_str:
            summary += f"before the {committee_str}."
        else:
            summary += f"in the {chamber}." if chamber else "scheduled."
        
        return {
            "title": title,
            "summary": summary,
            "source": "Federal (US Congress)",
            "category": "hearing",
            "chamber": chamber,
            "committee": committee_names[0] if committee_names else "",
            "committees": committee_str,
            "published": published,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "url": url,
            "link": url,
            "congress": congress,
            "meeting_type": meeting_type,
            "meeting_status": meeting_status,
            "location": location,
            "bill": bill_str,
            "_in_range": in_range  # Flag for filtering
        }
    except Exception as e:
        return None


def fetch_historical_hearings(
    api_key: str,
    congress: int = CONGRESS_NUMBER,
    days_back: int = 90
) -> List[Dict]:
    """
    Fetch historical published hearings from the /v3/hearing endpoint.
    These are hearings with transcripts/documents that have been published.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number
        days_back: How many days back to fetch
    
    Returns:
        List of normalized hearing dictionaries
    """
    hearings = []
    url = f"{API_BASE_URL}/hearing/{congress}"
    
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).date()
    
    print(f"Fetching historical hearings from /v3/hearing endpoint...")
    print(f"  Looking back {days_back} days from {now.date()}")
    
    current_url = url
    page = 1
    max_pages = 20
    
    while current_url and page <= max_pages:
        try:
            if "?" in current_url:
                request_url = f"{current_url}&api_key={api_key}&format=json&limit=100"
            else:
                request_url = f"{current_url}?api_key={api_key}&format=json&limit=100"
            
            print(f"  Fetching page {page}...")
            response = requests.get(request_url, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            
            data = response.json()
            hearings_list = data.get("hearings", [])
            
            if not hearings_list:
                break
            
            print(f"  Found {len(hearings_list)} hearings on page {page}")
            
            in_range_count = 0
            for hearing_summary in hearings_list:
                # Check date from list response
                dates_array = hearing_summary.get("dates", [])
                if dates_array and len(dates_array) > 0:
                    first_date = dates_array[0]
                    if isinstance(first_date, dict):
                        date_str = first_date.get("date", "")
                    else:
                        date_str = str(first_date)
                    
                    if date_str:
                        try:
                            if "T" in date_str:
                                hearing_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
                            else:
                                hearing_date = datetime.fromisoformat(date_str).date()
                            
                            if hearing_date < start_date:
                                continue  # Skip old hearings
                            
                            in_range_count += 1
                        except:
                            continue
                
                # Fetch details
                detail_url = hearing_summary.get("url", "")
                if detail_url:
                    normalized = fetch_hearing_detail(api_key, detail_url, congress)
                    if normalized:
                        hearings.append(normalized)
            
            # Stop if we're getting too many old hearings
            if in_range_count == 0:
                print(f"  No hearings in date range on this page, stopping")
                break
            
            pagination = data.get("pagination", {})
            current_url = pagination.get("next")
            if current_url and "api_key=" in current_url:
                current_url = current_url.split("api_key=")[0].rstrip("&?")
            page += 1
            
        except Exception as e:
            print(f"  Error: {e}")
            break
    
    print(f"  Fetched {len(hearings)} historical hearings")
    return hearings


def fetch_hearing_detail(api_key: str, detail_url: str, congress: int) -> Optional[Dict]:
    """Fetch and normalize a single hearing detail."""
    try:
        params = {"api_key": api_key, "format": "json"}
        response = requests.get(detail_url, params=params, timeout=30)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        
        data = response.json()
        hearing_data = data.get("hearing", data)
        
        # Extract title
        title = hearing_data.get("title", "").strip()
        if not title:
            return None
        
        # Extract date
        dates_array = hearing_data.get("dates", [])
        hearing_date = None
        if dates_array and len(dates_array) > 0:
            first_date = dates_array[0]
            if isinstance(first_date, dict):
                hearing_date = first_date.get("date")
            elif isinstance(first_date, str):
                hearing_date = first_date
        
        if not hearing_date:
            return None
        
        # Parse date
        try:
            if "T" in hearing_date:
                dt = datetime.fromisoformat(hearing_date.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(hearing_date + "T00:00:00+00:00")
            scheduled_date = dt.date().isoformat()
            scheduled_time = dt.strftime("%H:%M") if dt.time() != datetime.min.time() else ""
            published = dt.isoformat()
        except:
            return None
        
        # Extract chamber and committee
        chamber = hearing_data.get("chamber", "").capitalize()
        committees_array = hearing_data.get("committees", [])
        committee_names = []
        for comm in committees_array:
            if isinstance(comm, dict):
                name = comm.get("name", "")
                if name:
                    committee_names.append(name)
        committee_str = ", ".join(committee_names) if committee_names else ""
        
        # Build URL from formats or construct one
        url = ""
        formats_array = hearing_data.get("formats", [])
        for fmt in formats_array:
            if isinstance(fmt, dict):
                fmt_url = fmt.get("url", "")
                if fmt_url and "congress.gov" in fmt_url:
                    url = fmt_url
                    break
        
        if not url:
            jacket = hearing_data.get("jacketNumber", "")
            if jacket:
                url = f"https://www.congress.gov/hearing/{congress}th-congress/{chamber.lower()}/{jacket}"
            else:
                url = "https://www.congress.gov/hearings"
        
        summary = f"Congressional hearing before the {committee_str}." if committee_str else "Congressional hearing."
        
        return {
            "title": title,
            "summary": summary,
            "source": "Federal (US Congress)",
            "category": "hearing",
            "chamber": chamber,
            "committee": committee_names[0] if committee_names else "",
            "committees": committee_str,
            "published": published,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "url": url,
            "link": url,
            "congress": congress,
            "meeting_type": "Hearing",
            "meeting_status": "Completed"
        }
    except Exception as e:
        return None


def load_existing_hearings() -> List[Dict]:
    """Load existing hearings from file if it exists."""
    if not HEARINGS_FILE.exists():
        return []
    
    try:
        with open(HEARINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "items" in data:
                return data["items"]
            elif isinstance(data, list):
                return data
            else:
                return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load existing hearings: {e}")
        return []


def merge_and_deduplicate(all_meetings: List[Dict]) -> List[Dict]:
    """
    Merge and deduplicate meetings/hearings.
    
    Args:
        all_meetings: Combined list of meetings from all sources
    
    Returns:
        Deduplicated list sorted by date
    """
    seen = set()
    unique = []
    
    for meeting in all_meetings:
        # Create unique key
        title = meeting.get("title", "")
        date = meeting.get("scheduled_date", "")
        url = meeting.get("url", "")
        
        key = url if url else f"{title}_{date}"
        
        if key and key not in seen:
            seen.add(key)
            unique.append(meeting)
    
    # Sort by date (newest first for display)
    unique.sort(key=lambda x: x.get("scheduled_date", ""), reverse=True)
    
    return unique


def main():
    """Main entry point for fetching hearings."""
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("=" * 60)
    print("Fetching Congressional hearings and committee meetings...")
    print("=" * 60)
    
    all_meetings = []
    
    # 1. Fetch SCHEDULED meetings from committee-meeting endpoint
    print("\n[1/2] Fetching scheduled committee meetings...")
    try:
        # The function now fetches details and filters by date internally
        meetings = fetch_committee_meetings(api_key, CONGRESS_NUMBER, days_back=30, days_forward=90)
        
        # Remove internal flags before adding to results
        for meeting in meetings:
            meeting.pop("_in_range", None)
        
        all_meetings.extend(meetings)
        print(f"  Added {len(meetings)} scheduled meetings")
    except Exception as e:
        print(f"  Error fetching committee meetings: {e}")
    
    # 2. Try per-chamber if no results
    if not all_meetings:
        print("\n  Trying per-chamber fetch...")
        for chamber_name in ["house", "senate"]:
            try:
                meetings = fetch_committee_meetings(api_key, CONGRESS_NUMBER, chamber_name, days_back=30, days_forward=90)
                for meeting in meetings:
                    meeting.pop("_in_range", None)
                all_meetings.extend(meetings)
            except Exception as e:
                print(f"  Error fetching {chamber_name} meetings: {e}")
    
    # 2. Fetch historical hearings (published transcripts)
    print("\n[2/2] Fetching historical published hearings...")
    try:
        historical = fetch_historical_hearings(api_key, CONGRESS_NUMBER, days_back=90)
        all_meetings.extend(historical)
    except Exception as e:
        print(f"  Error fetching historical hearings: {e}")
    
    # Merge and deduplicate
    print("\nMerging and deduplicating...")
    unique_meetings = merge_and_deduplicate(all_meetings)
    
    # Clean up very old items (keep last 2 years)
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=730)).date()
    cleaned = []
    for meeting in unique_meetings:
        date_str = meeting.get("scheduled_date", "")
        if date_str:
            try:
                meeting_date = datetime.fromisoformat(date_str).date()
                if meeting_date >= cutoff_date:
                    cleaned.append(meeting)
            except:
                cleaned.append(meeting)
        else:
            cleaned.append(meeting)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if cleaned:
        # Count by status/type
        today = datetime.now(timezone.utc).date()
        future = [m for m in cleaned if m.get("scheduled_date", "") >= today.isoformat()]
        past = [m for m in cleaned if m.get("scheduled_date", "") < today.isoformat()]
        scheduled = [m for m in cleaned if m.get("meeting_status", "").lower() == "scheduled"]
        
        print(f"Total hearings/meetings: {len(cleaned)}")
        print(f"  Future (scheduled): {len(future)}")
        print(f"  Past (completed): {len(past)}")
        
        if future:
            future_dates = sorted([m.get("scheduled_date", "") for m in future])
            print(f"  Next upcoming: {future_dates[0] if future_dates else 'N/A'}")
        
        # Save to file
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(cleaned),
            "items": cleaned
        }
        
        with open(HEARINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nSaved {len(cleaned)} items to {HEARINGS_FILE}")
    else:
        print("No hearings/meetings found.")


if __name__ == "__main__":
    main()
