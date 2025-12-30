"""
Fetch Congressional hearings from the Congress.gov API.

This module:
- Fetches hearings from the /v3/hearing/{congress} endpoint
- Supports optional /house and /senate paths
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


def fetch_hearings(
    api_key: str,
    congress: int = CONGRESS_NUMBER,
    chamber: Optional[str] = None
) -> List[Dict]:
    """
    Fetch hearings from the Congress.gov API.
    
    Uses the correct endpoint: /v3/hearing/{congress}
    Optional: /v3/hearing/{congress}/house or /v3/hearing/{congress}/senate
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number (default: 119)
        chamber: Optional chamber filter ("house" or "senate")
    
    Returns:
        List of normalized hearing dictionaries
    """
    hearings = []
    
    # Build the base URL
    if chamber:
        url = f"{API_BASE_URL}/hearing/{congress}/{chamber.lower()}"
    else:
        url = f"{API_BASE_URL}/hearing/{congress}"
    
    print(f"Fetching hearings from Congress.gov API...")
    print(f"  Congress: {congress}")
    if chamber:
        print(f"  Chamber: {chamber}")
    
    # Start with initial URL
    current_url = url
    page = 1
    
    while current_url:
        try:
            # Add API key to URL
            if "?" in current_url:
                request_url = f"{current_url}&api_key={api_key}&format=json"
            else:
                request_url = f"{current_url}?api_key={api_key}&format=json"
            
            print(f"  Fetching page {page}...")
            response = requests.get(request_url, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            
            data = response.json()
            
            # Extract hearings from response (key is "hearings", not "results")
            hearings_list = data.get("hearings", [])
            
            if not hearings_list:
                print(f"  No hearings found on page {page}")
                break
            
            print(f"  Found {len(hearings_list)} hearings on page {page}")
            
            # Normalize each hearing
            for hearing_data in hearings_list:
                normalized = normalize_hearing(hearing_data, congress)
                if normalized:
                    hearings.append(normalized)
            
            # Get next page URL from pagination
            pagination = data.get("pagination", {})
            current_url = pagination.get("next")
            
            if current_url:
                # Remove API key from next URL if present (we'll add it fresh)
                if "api_key=" in current_url:
                    current_url = current_url.split("api_key=")[0].rstrip("&?")
                page += 1
            else:
                print(f"  No more pages (reached end)")
                break
            
            # Safety limit
            if page > 100:
                print(f"  Reached safety limit of 100 pages, stopping")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching hearings (page {page}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    print(f"  Note: Endpoint may not be available")
            break
        except Exception as e:
            print(f"  Unexpected error on page {page}: {e}")
            break
    
    # Deduplicate by URL or title+date
    seen = set()
    unique_hearings = []
    for hearing in hearings:
        # Only include hearings with valid published date (hearingDate)
        if not hearing.get("published"):
            continue
        
        # Create unique key
        key = hearing.get("url", "") or f"{hearing.get('title', '')}_{hearing.get('published', '')}"
        if key and key not in seen:
            seen.add(key)
            unique_hearings.append(hearing)
    
    print(f"  Fetched {len(unique_hearings)} unique hearings with valid dates")
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
        # Extract title (field is "hearingTitle")
        title = hearing_data.get("hearingTitle", "").strip()
        if not title:
            # Try alternative fields
            title = (hearing_data.get("title", "") or
                    hearing_data.get("name", "") or
                    hearing_data.get("description", "")).strip()
        
        if not title:
            return None  # Must have a title
        
        # Extract published date (field is "hearingDate") - REQUIRED
        hearing_date = hearing_data.get("hearingDate")
        if not hearing_date:
            # Skip items without hearingDate
            return None
        
        # Parse the date
        published = ""
        scheduled_date = ""
        scheduled_time = ""
        
        try:
            if isinstance(hearing_date, str):
                hearing_date = hearing_date.strip()
                if not hearing_date:
                    return None
                
                # Try ISO format
                if "T" in hearing_date:
                    dt = datetime.fromisoformat(hearing_date.replace("Z", "+00:00"))
                    scheduled_date = dt.date().isoformat()
                    scheduled_time = dt.time().strftime("%H:%M") if dt.time() else ""
                    published = dt.isoformat()
                # Try date-only format (YYYY-MM-DD)
                elif len(hearing_date) >= 10 and hearing_date[4] == "-" and hearing_date[7] == "-":
                    dt = datetime.fromisoformat(hearing_date + "T00:00:00+00:00")
                    scheduled_date = dt.date().isoformat()
                    published = dt.isoformat()
                else:
                    # Invalid format
                    return None
            else:
                return None
        except (ValueError, AttributeError):
            # Invalid date format
            return None
        
        # Extract chamber
        chamber = hearing_data.get("chamber", "").lower()
        
        # Extract committee name (nested: committee.name)
        committee_name = ""
        committee_obj = hearing_data.get("committee", {})
        if isinstance(committee_obj, dict):
            committee_name = (committee_obj.get("name", "") or
                            committee_obj.get("fullName", "") or
                            committee_obj.get("committeeName", "") or
                            committee_obj.get("displayName", "")).strip()
        elif isinstance(committee_obj, str):
            committee_name = committee_obj.strip()
        
        # Extract URL
        url = hearing_data.get("url", "")
        if not url:
            # Try to build URL from hearing number if available
            hearing_number = hearing_data.get("hearingNumber", "")
            if hearing_number:
                chamber_part = chamber or "house"
                url = f"https://www.congress.gov/hearing/{congress}th-congress/{chamber_part}-committee/{hearing_number}"
        
        # Extract summary/description
        summary = (hearing_data.get("summary", "") or
                  hearing_data.get("description", "") or
                  "").strip()
        
        if not summary:
            # Generate a placeholder summary
            if committee_name:
                summary = f"Congressional hearing scheduled before the {committee_name}."
            else:
                summary = "Congressional hearing scheduled."
        
        return {
            "title": title,
            "summary": summary,
            "source": "Federal (US Congress)",
            "category": "hearing",
            "chamber": chamber.capitalize() if chamber else "",
            "committee": committee_name,
            "committees": committee_name,  # For frontend compatibility
            "published": published,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "url": url or f"https://www.congress.gov/hearings",
            "link": url or f"https://www.congress.gov/hearings",  # For frontend compatibility
            "congress": congress
        }
    except Exception as e:
        print(f"  Error normalizing hearing: {e}")
        return None


def filter_hearings_by_date_range(
    hearings: List[Dict],
    start_date: datetime,
    end_date: datetime
) -> List[Dict]:
    """
    Filter hearings to only those within the specified date range.
    
    Args:
        hearings: List of hearing dictionaries
        start_date: Start of date range (inclusive)
        end_date: End of date range (exclusive)
    
    Returns:
        Filtered list of hearings
    """
    filtered = []
    
    for hearing in hearings:
        published = hearing.get("published", "")
        if not published:
            continue
        
        try:
            # Parse published date
            if "T" in published:
                hearing_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            else:
                hearing_dt = datetime.fromisoformat(published + "T00:00:00+00:00")
            
            # Make timezone-aware
            if hearing_dt.tzinfo is None:
                hearing_dt = hearing_dt.replace(tzinfo=timezone.utc)
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            # Check if within range (start <= date < end)
            if start_date <= hearing_dt < end_date:
                filtered.append(hearing)
        except (ValueError, AttributeError):
            continue
    
    return filtered


def main():
    """Main entry point for fetching hearings."""
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("Fetching Congressional hearings...")
    
    # Fetch all hearings (we'll filter by date later if needed)
    all_hearings = []
    
    # Try fetching all chambers first
    try:
        hearings = fetch_hearings(api_key, CONGRESS_NUMBER)
        all_hearings.extend(hearings)
    except Exception as e:
        print(f"Error fetching all hearings: {e}")
    
    # If no results, try per-chamber
    if not all_hearings:
        print("  No results from bulk fetch, trying per-chamber...")
        
        # Try House
        try:
            house_hearings = fetch_hearings(api_key, CONGRESS_NUMBER, "house")
            all_hearings.extend(house_hearings)
        except Exception as e:
            print(f"  Error fetching House hearings: {e}")
        
        # Try Senate
        try:
            senate_hearings = fetch_hearings(api_key, CONGRESS_NUMBER, "senate")
            all_hearings.extend(senate_hearings)
        except Exception as e:
            print(f"  Error fetching Senate hearings: {e}")
    
    if all_hearings:
        # Save to file
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(all_hearings),
            "items": all_hearings
        }
        
        with open(HEARINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nSuccessfully saved {len(all_hearings)} hearings to {HEARINGS_FILE}")
    else:
        print("\nNo hearings fetched. This may be normal if no hearings are scheduled.")


if __name__ == "__main__":
    main()
