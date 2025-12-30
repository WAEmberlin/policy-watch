"""
Fetch Congressional hearings from the Congress.gov API.

This module:
- Fetches hearings from the /v3/hearing endpoint
- Supports filtering by congress, chamber, and date range
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
ITEMS_PER_PAGE = 250  # Max allowed by API

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


def fetch_hearings(
    api_key: str,
    congress: int = CONGRESS_NUMBER,
    chamber: Optional[str] = None,
    days_back: int = 7,
    days_forward: int = 30
) -> List[Dict]:
    """
    Fetch hearings from the Congress.gov API.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number (default: 119)
        chamber: Optional chamber filter ("house" or "senate")
        days_back: Number of days in the past to fetch (default: 7)
        days_forward: Number of days in the future to fetch (default: 30)
    
    Returns:
        List of normalized hearing dictionaries
    """
    hearings = []
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_forward)).strftime("%Y-%m-%d")
    
    print(f"Fetching hearings from Congress.gov API...")
    print(f"  Congress: {congress}")
    print(f"  Date range: {start_date} to {end_date}")
    if chamber:
        print(f"  Chamber: {chamber}")
    
    # Try fetching all hearings first (without chamber filter if chamber not specified)
    try:
        url = f"{API_BASE_URL}/hearing"
        params = {
            "api_key": api_key,
            "format": "json",
            "congress": congress,
            "limit": ITEMS_PER_PAGE,
            "offset": 0
        }
        
        # Add date filters if API supports them
        # Note: Congress.gov API may not support date filtering directly
        # We'll filter after fetching
        
        # Add chamber filter if specified
        if chamber:
            params["chamber"] = chamber.lower()
        
        offset = 0
        page = 1
        
        while True:
            params["offset"] = offset
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                time.sleep(REQUEST_DELAY)
                
                data = response.json()
                hearings_list = data.get("hearings", [])
                
                if not hearings_list or len(hearings_list) == 0:
                    break
                
                # Normalize and filter by date
                for hearing_data in hearings_list:
                    normalized = normalize_hearing(hearing_data, congress)
                    if normalized:
                        # Filter by date range
                        hearing_date = normalized.get("scheduled_date", "")
                        if hearing_date:
                            try:
                                # Parse date (handle ISO format)
                                if "T" in hearing_date:
                                    hearing_dt = datetime.fromisoformat(hearing_date.replace("Z", "+00:00"))
                                else:
                                    hearing_dt = datetime.fromisoformat(hearing_date + "T00:00:00+00:00")
                                
                                # Check if within date range
                                start_dt = datetime.fromisoformat(start_date + "T00:00:00+00:00")
                                end_dt = datetime.fromisoformat(end_date + "T23:59:59+00:00")
                                
                                if start_dt <= hearing_dt <= end_dt:
                                    hearings.append(normalized)
                            except (ValueError, AttributeError):
                                # If date parsing fails, include it anyway
                                hearings.append(normalized)
                        else:
                            # No date - include it (might be upcoming)
                            hearings.append(normalized)
                
                # Check pagination
                pagination = data.get("pagination", {})
                total_count = pagination.get("count", 0)
                
                if offset + len(hearings_list) >= total_count or len(hearings_list) < ITEMS_PER_PAGE:
                    break
                
                offset += len(hearings_list)
                page += 1
                
                # Safety limit
                if page > 50:
                    print(f"  Reached safety limit of 50 pages, stopping")
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"  Error fetching hearings (offset {offset}): {e}")
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 404:
                        print(f"  Note: /hearing endpoint may not be available")
                        break
                break
        
        # If no results and chamber not specified, try per-chamber
        if len(hearings) == 0 and not chamber:
            print("  No results from bulk fetch, trying per-chamber...")
            
            # Try House
            try:
                house_hearings = fetch_hearings(api_key, congress, "house", days_back, days_forward)
                hearings.extend(house_hearings)
            except Exception as e:
                print(f"  Error fetching House hearings: {e}")
            
            # Try Senate
            try:
                senate_hearings = fetch_hearings(api_key, congress, "senate", days_back, days_forward)
                hearings.extend(senate_hearings)
            except Exception as e:
                print(f"  Error fetching Senate hearings: {e}")
        
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching hearings: {e}")
        return []
    
    # Deduplicate by URL or title+date
    seen = set()
    unique_hearings = []
    for hearing in hearings:
        # Create unique key
        key = hearing.get("url", "") or f"{hearing.get('title', '')}_{hearing.get('scheduled_date', '')}"
        if key and key not in seen:
            seen.add(key)
            unique_hearings.append(hearing)
    
    print(f"  Fetched {len(unique_hearings)} unique hearings")
    return unique_hearings


def normalize_hearing(hearing_data: Dict, congress: int) -> Optional[Dict]:
    """
    Normalize a hearing from the API response into CivicWatch schema.
    
    Args:
        hearing_data: Raw hearing data from API
        congress: Congress number
    
    Returns:
        Normalized hearing dict, or None if invalid
    """
    try:
        # Extract title - try multiple field names
        title = (hearing_data.get("hearingTitle", "") or
                hearing_data.get("title", "") or
                hearing_data.get("name", "") or
                hearing_data.get("description", "") or
                hearing_data.get("subject", "")).strip()
        
        # If no title, generate placeholder
        if not title:
            committee_name = ""
            if "committee" in hearing_data:
                comm = hearing_data["committee"]
                if isinstance(comm, dict):
                    committee_name = comm.get("name", "") or comm.get("fullName", "") or comm.get("committeeName", "")
                elif isinstance(comm, str):
                    committee_name = comm
            
            if committee_name:
                title = f"Congressional hearing scheduled before the {committee_name}."
            else:
                title = "Congressional hearing scheduled."
        
        # Extract summary
        summary = hearing_data.get("summary", "") or hearing_data.get("description", "") or ""
        if not summary:
            summary = f"Congressional hearing scheduled before the {hearing_data.get('committee', {}).get('name', 'Committee')}."
        
        # Extract chamber
        chamber = hearing_data.get("chamber", "").lower()
        if not chamber:
            # Try to infer from committee
            if "committee" in hearing_data:
                comm = hearing_data["committee"]
                if isinstance(comm, dict):
                    comm_name = comm.get("name", "") or comm.get("fullName", "")
                    if "house" in comm_name.lower():
                        chamber = "house"
                    elif "senate" in comm_name.lower():
                        chamber = "senate"
        
        # Extract committee name
        committee_name = ""
        if "committee" in hearing_data:
            comm = hearing_data["committee"]
            if isinstance(comm, dict):
                committee_name = (comm.get("name", "") or
                                comm.get("fullName", "") or
                                comm.get("committeeName", "") or
                                comm.get("displayName", "")).strip()
            elif isinstance(comm, str):
                committee_name = comm.strip()
        
        # Try committees array
        if not committee_name and "committees" in hearing_data:
            committees_list = hearing_data["committees"]
            if isinstance(committees_list, list) and len(committees_list) > 0:
                comm = committees_list[0]
                if isinstance(comm, dict):
                    committee_name = (comm.get("name", "") or
                                    comm.get("fullName", "") or
                                    comm.get("committeeName", "") or
                                    comm.get("displayName", "")).strip()
                elif isinstance(comm, str):
                    committee_name = comm.strip()
        
        # Extract date
        published = ""
        scheduled_date = ""
        scheduled_time = ""
        
        # Try different date fields
        date_str = (hearing_data.get("date") or
                   hearing_data.get("hearingDate") or
                   hearing_data.get("scheduledDate") or
                   hearing_data.get("eventDate") or
                   hearing_data.get("startDate") or
                   hearing_data.get("dateTime"))
        
        if date_str:
            try:
                if isinstance(date_str, str):
                    # Try ISO format
                    if "T" in date_str:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        scheduled_date = dt.date().isoformat()
                        scheduled_time = dt.time().strftime("%H:%M") if dt.time() else ""
                        published = dt.isoformat()
                    else:
                        scheduled_date = date_str
                        published = date_str + "T00:00:00+00:00"
                else:
                    scheduled_date = str(date_str)
                    published = str(date_str) + "T00:00:00+00:00"
            except (ValueError, AttributeError):
                scheduled_date = str(date_str) if date_str else ""
                published = str(date_str) + "T00:00:00+00:00" if date_str else ""
        
        # Extract time if separate
        if not scheduled_time:
            scheduled_time = (hearing_data.get("time", "") or
                            hearing_data.get("hearingTime", "") or
                            hearing_data.get("scheduledTime", "") or
                            hearing_data.get("eventTime", "") or
                            hearing_data.get("startTime", ""))
        
        # Extract URL
        url = (hearing_data.get("url", "") or
              hearing_data.get("hearingUrl", "") or
              hearing_data.get("link", ""))
        
        if not url:
            # Try to build URL from hearing number
            hearing_number = hearing_data.get("hearingNumber", "")
            if hearing_number:
                chamber_part = chamber or "house"
                url = f"https://www.congress.gov/hearing/{congress}th-congress/{chamber_part}-committee/{hearing_number}"
            elif "systemCode" in hearing_data:
                system_code = hearing_data["systemCode"]
                chamber_part = chamber or "house"
                url = f"https://www.congress.gov/committee/{chamber_part}/{system_code}/{congress}"
        
        # Extract location
        location = (hearing_data.get("location", "") or
                   hearing_data.get("room", "") or
                   hearing_data.get("venue", "") or
                   hearing_data.get("address", ""))
        
        return {
            "title": title,
            "summary": summary,
            "source": "Federal (US Congress)",
            "category": "hearing",
            "chamber": chamber.capitalize() if chamber else "",
            "committee": committee_name,
            "published": published or scheduled_date + "T00:00:00+00:00" if scheduled_date else datetime.now(timezone.utc).isoformat(),
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "location": location,
            "url": url or f"https://www.congress.gov/hearings",
            "congress": congress
        }
    except Exception as e:
        print(f"  Error normalizing hearing: {e}")
        return None


def main():
    """Main entry point for fetching hearings."""
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("Fetching Congressional hearings...")
    
    # Fetch hearings (last 7 days, next 30 days)
    hearings = fetch_hearings(api_key, CONGRESS_NUMBER, days_back=7, days_forward=30)
    
    if hearings:
        # Save to file
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(hearings),
            "items": hearings
        }
        
        with open(HEARINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nSuccessfully saved {len(hearings)} hearings to {HEARINGS_FILE}")
    else:
        print("\nNo hearings fetched. This may be normal if no hearings are scheduled.")


if __name__ == "__main__":
    main()

