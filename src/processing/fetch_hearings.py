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
    chamber: Optional[str] = None,
    days_back: int = 30,
    days_forward: int = 60
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
    
    # Calculate date range for filtering
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days_back)).date()
    end_date = (now + timedelta(days=days_forward)).date()
    
    print(f"Fetching hearings from Congress.gov API...")
    print(f"  Congress: {congress}")
    print(f"  Date range: {start_date} to {end_date}")
    if chamber:
        print(f"  Chamber: {chamber}")
    
    # Start with initial URL
    current_url = url
    page = 1
    consecutive_old_pages = 0  # Track consecutive pages with only old hearings (before start_date)
    consecutive_out_of_range = 0  # Track consecutive pages with no hearings in our date range
    MAX_CONSECUTIVE_OLD = 3  # Stop after 3 consecutive pages with only old dates (reduced for faster stopping)
    MAX_CONSECUTIVE_OUT_OF_RANGE = 2  # Stop after 2 consecutive pages with no in-range hearings (reduced for faster stopping)
    
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
            
            # Fetch full details for each hearing and normalize
            normalized_count = 0
            skipped_count = 0
            in_range_on_page = 0  # Count hearings in date range on this page
            
            for i, hearing_summary in enumerate(hearings_list):
                # Try to extract date from list response to filter early
                # This avoids unnecessary detail API calls for out-of-range hearings
                list_date = None
                dates_array = hearing_summary.get("dates", [])
                if dates_array and isinstance(dates_array, list) and len(dates_array) > 0:
                    first_date_obj = dates_array[0]
                    if isinstance(first_date_obj, dict):
                        list_date_str = first_date_obj.get("date")
                    elif isinstance(first_date_obj, str):
                        list_date_str = first_date_obj
                    else:
                        list_date_str = None
                    
                    if list_date_str:
                        try:
                            if "T" in list_date_str:
                                list_date = datetime.fromisoformat(list_date_str.replace("Z", "+00:00")).date()
                            else:
                                list_date = datetime.fromisoformat(list_date_str + "T00:00:00+00:00").date()
                            
                            # Skip if date is clearly out of range (before start_date or after end_date)
                            if list_date < start_date or list_date > end_date:
                                skipped_count += 1
                                continue
                        except (ValueError, AttributeError):
                            pass  # Continue to fetch details if date parsing fails
                
                # The list endpoint only returns minimal data (chamber, jacketNumber, url, etc.)
                # We need to fetch the full details using the URL
                detail_url = hearing_summary.get("url", "")
                if not detail_url:
                    # Try to construct URL from jacketNumber and chamber
                    jacket_number = hearing_summary.get("jacketNumber")
                    chamber_lower = hearing_summary.get("chamber", "").lower()
                    if jacket_number and chamber_lower:
                        detail_url = f"{API_BASE_URL}/hearing/{congress}/{chamber_lower}/{jacket_number}"
                
                if not detail_url:
                    skipped_count += 1
                    continue
                
                # Fetch full hearing details
                try:
                    detail_params = {"api_key": api_key, "format": "json"}
                    detail_response = requests.get(detail_url, params=detail_params, timeout=30)
                    detail_response.raise_for_status()
                    time.sleep(REQUEST_DELAY)  # Rate limiting
                    
                    detail_data = detail_response.json()
                    # The detail response should have a "hearing" key
                    hearing_data = detail_data.get("hearing", detail_data)
                    
                    # Debug: print first hearing structure
                    if page == 1 and i == 0:
                        print(f"  Debug: First hearing detail keys: {list(hearing_data.keys())}")
                        print(f"  Debug: Sample fields: hearingTitle={hearing_data.get('hearingTitle', 'MISSING')}, hearingDate={hearing_data.get('hearingDate', 'MISSING')}")
                    
                    normalized = normalize_hearing(hearing_data, congress)
                    if normalized:
                        # Check if hearing is in date range before adding
                        scheduled_date_str = normalized.get("scheduled_date", "")
                        if scheduled_date_str:
                            try:
                                hearing_date = datetime.fromisoformat(scheduled_date_str + "T00:00:00+00:00").date()
                                if start_date <= hearing_date <= end_date:
                                    hearings.append(normalized)
                                    normalized_count += 1
                                    in_range_on_page += 1
                                else:
                                    skipped_count += 1  # Outside date range
                            except (ValueError, AttributeError):
                                # Invalid date, skip it
                                skipped_count += 1
                        else:
                            # No date, skip it
                            skipped_count += 1
                    else:
                        skipped_count += 1
                        # Debug: print why first hearing was skipped
                        if page == 1 and i == 0:
                            print(f"  Debug: First hearing was skipped - checking why...")
                            print(f"    hearingTitle: {hearing_data.get('hearingTitle', 'MISSING')}")
                            print(f"    hearingDate: {hearing_data.get('hearingDate', 'MISSING')}")
                            print(f"    date: {hearing_data.get('date', 'MISSING')}")
                            print(f"    scheduledDate: {hearing_data.get('scheduledDate', 'MISSING')}")
                except requests.exceptions.RequestException as e:
                    skipped_count += 1
                    if page == 1 and i == 0:
                        print(f"  Debug: Error fetching first hearing detail: {e}")
                    continue
                except Exception as e:
                    skipped_count += 1
                    if page == 1 and i == 0:
                        print(f"  Debug: Unexpected error fetching first hearing: {e}")
                    continue
            
            if skipped_count > 0:
                print(f"  Normalized {normalized_count}, skipped {skipped_count} (check field names)")
            
            # Smart early stopping: use the in_range_on_page count we tracked
            # If we found no in-range hearings on this page, increment counter
            if in_range_on_page == 0:
                consecutive_out_of_range += 1
                if consecutive_out_of_range >= MAX_CONSECUTIVE_OUT_OF_RANGE:
                    print(f"  Stopping early: {consecutive_out_of_range} consecutive pages with no hearings in date range")
                    break
            else:
                consecutive_out_of_range = 0  # Reset if we found in-range hearings
                consecutive_old_pages = 0  # Reset old pages counter too
            
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
    
    # Deduplicate (date filtering already done during normalization)
    seen = set()
    unique_hearings = []
    for hearing in hearings:
        # All hearings in the list should already be within date range
        scheduled_date_str = hearing.get("scheduled_date", "")
        if not scheduled_date_str:
            continue  # Skip hearings without dates
        
        # Create unique key for deduplication
        key = hearing.get("url", "") or f"{hearing.get('title', '')}_{scheduled_date_str}"
        if key and key not in seen:
            seen.add(key)
            unique_hearings.append(hearing)
    
    print(f"  Fetched {len(unique_hearings)} unique hearings within date range ({start_date} to {end_date})")
    if unique_hearings:
        dates = [h.get("scheduled_date", "") for h in unique_hearings if h.get("scheduled_date")]
        if dates:
            dates.sort()
            print(f"  Date range of fetched hearings: {dates[0]} to {dates[-1]}")
            # Show count of future vs past
            today = datetime.now(timezone.utc).date()
            future = [d for d in dates if d >= today]
            print(f"  Future hearings: {len(future)}, Past hearings: {len(dates) - len(future)}")
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
        # Extract title - the field is "title" in the detail response
        title = hearing_data.get("title", "").strip()
        if not title:
            # Try alternative fields
            title = (hearing_data.get("hearingTitle", "") or
                    hearing_data.get("name", "") or
                    hearing_data.get("description", "") or
                    "").strip()
        
        if not title:
            return None  # Must have a title
        
        # Extract date from "dates" array - the structure is dates[0].date
        hearing_date = None
        dates_array = hearing_data.get("dates", [])
        if dates_array and isinstance(dates_array, list) and len(dates_array) > 0:
            first_date_obj = dates_array[0]
            if isinstance(first_date_obj, dict):
                hearing_date = first_date_obj.get("date")
            elif isinstance(first_date_obj, str):
                hearing_date = first_date_obj
        
        # Fallback: try other date fields
        if not hearing_date:
            hearing_date = (hearing_data.get("hearingDate") or
                           hearing_data.get("date") or
                           hearing_data.get("scheduledDate") or
                           hearing_data.get("eventDate") or
                           hearing_data.get("startDate") or
                           hearing_data.get("publishedDate"))
        
        if not hearing_date:
            # Skip items without date
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
        
        # Extract committee name from "committees" array - the structure is committees[0].name
        committee_name = ""
        committees_array = hearing_data.get("committees", [])
        if committees_array and isinstance(committees_array, list) and len(committees_array) > 0:
            first_committee = committees_array[0]
            if isinstance(first_committee, dict):
                committee_name = (first_committee.get("name", "") or
                                first_committee.get("fullName", "") or
                                first_committee.get("committeeName", "") or
                                first_committee.get("displayName", "")).strip()
            elif isinstance(first_committee, str):
                committee_name = first_committee.strip()
        
        # Fallback: try single committee object
        if not committee_name:
            committee_obj = hearing_data.get("committee", {})
            if isinstance(committee_obj, dict):
                committee_name = (committee_obj.get("name", "") or
                                committee_obj.get("fullName", "") or
                                committee_obj.get("committeeName", "") or
                                committee_obj.get("displayName", "")).strip()
            elif isinstance(committee_obj, str):
                committee_name = committee_obj.strip()
        
        # Extract URL - construct from citation or jacketNumber
        url = ""
        
        # Try to get public URL from formats array
        formats_array = hearing_data.get("formats", [])
        if formats_array and isinstance(formats_array, list):
            for fmt in formats_array:
                if isinstance(fmt, dict):
                    fmt_url = fmt.get("url", "")
                    if fmt_url and "congress.gov" in fmt_url:
                        # Prefer formatted text URL, but any congress.gov URL works
                        url = fmt_url
                        break
        
        # If no URL from formats, try to construct from citation
        if not url:
            citation = hearing_data.get("citation", "")
            if citation:
                # Citation format: H.Hrg.119-14 -> construct URL
                # Format: https://www.congress.gov/hearing/119th-congress/house-committee/[number]
                number = hearing_data.get("number", "")
                if number and chamber:
                    url = f"https://www.congress.gov/hearing/{congress}th-congress/{chamber}-committee/{number}"
        
        # Fallback: construct from jacketNumber
        if not url:
            jacket_number = hearing_data.get("jacketNumber", "")
            if jacket_number and chamber:
                url = f"https://www.congress.gov/hearing/{congress}th-congress/{chamber}-committee/{jacket_number}"
        
        # Last resort: generic hearings page
        if not url:
            url = f"https://www.congress.gov/hearings"
        
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


def merge_hearings(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    """
    Merge new hearings with existing ones, deduplicating by URL or title+date.
    
    Args:
        existing: List of existing hearing dictionaries
        new: List of newly fetched hearing dictionaries
    
    Returns:
        Merged and deduplicated list of hearings
    """
    # Create a set of keys from existing hearings
    seen = set()
    merged = []
    
    # Add existing hearings first
    for hearing in existing:
        scheduled_date = hearing.get("scheduled_date", "")
        key = hearing.get("url", "") or f"{hearing.get('title', '')}_{scheduled_date}"
        if key:
            seen.add(key)
            merged.append(hearing)
    
    # Add new hearings that aren't duplicates
    new_count = 0
    for hearing in new:
        scheduled_date = hearing.get("scheduled_date", "")
        key = hearing.get("url", "") or f"{hearing.get('title', '')}_{scheduled_date}"
        if key and key not in seen:
            seen.add(key)
            merged.append(hearing)
            new_count += 1
    
    print(f"  Merged {new_count} new hearings with {len(existing)} existing")
    return merged


def main():
    """Main entry point for fetching hearings."""
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("Fetching Congressional hearings...")
    
    # Load existing hearings
    existing_hearings = load_existing_hearings()
    print(f"Loaded {len(existing_hearings)} existing hearings from {HEARINGS_FILE}")
    
    # Determine date range based on existing hearings
    # If we have existing hearings, check the latest date
    latest_existing_date = None
    if existing_hearings:
        existing_dates = [h.get("scheduled_date", "") for h in existing_hearings if h.get("scheduled_date")]
        if existing_dates:
            try:
                latest_existing_date = max([datetime.fromisoformat(d + "T00:00:00+00:00").date() for d in existing_dates if d])
            except (ValueError, AttributeError):
                pass
    
    # Fetch only recent hearings (last 30 days, next 60 days)
    # This is much faster than fetching all 400+ hearings
    new_hearings = []
    
    # Try fetching all chambers first
    try:
        hearings = fetch_hearings(api_key, CONGRESS_NUMBER, days_back=30, days_forward=60)
        new_hearings.extend(hearings)
    except Exception as e:
        print(f"Error fetching all hearings: {e}")
    
    # If no results, try per-chamber
    if not new_hearings:
        print("  No results from bulk fetch, trying per-chamber...")
        
        # Try House
        try:
            house_hearings = fetch_hearings(api_key, CONGRESS_NUMBER, "house", days_back=30, days_forward=60)
            new_hearings.extend(house_hearings)
        except Exception as e:
            print(f"  Error fetching House hearings: {e}")
        
        # Try Senate
        try:
            senate_hearings = fetch_hearings(api_key, CONGRESS_NUMBER, "senate", days_back=30, days_forward=60)
            new_hearings.extend(senate_hearings)
        except Exception as e:
            print(f"  Error fetching Senate hearings: {e}")
    
    # Merge new hearings with existing
    all_hearings = merge_hearings(existing_hearings, new_hearings)
    
    # Clean up very old hearings (older than 2 years) to keep file size manageable
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=730)).date()
    cleaned_hearings = []
    removed_count = 0
    
    for hearing in all_hearings:
        scheduled_date_str = hearing.get("scheduled_date", "")
        if scheduled_date_str:
            try:
                hearing_date = datetime.fromisoformat(scheduled_date_str + "T00:00:00+00:00").date()
                if hearing_date >= cutoff_date:
                    cleaned_hearings.append(hearing)
                else:
                    removed_count += 1
            except (ValueError, AttributeError):
                # Keep hearings with invalid dates (better safe than sorry)
                cleaned_hearings.append(hearing)
        else:
            # Keep hearings without dates
            cleaned_hearings.append(hearing)
    
    if removed_count > 0:
        print(f"  Removed {removed_count} hearings older than 2 years")
    
    if cleaned_hearings:
        # Save merged hearings to file
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(cleaned_hearings),
            "items": cleaned_hearings
        }
        
        with open(HEARINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        
        print(f"\nSuccessfully saved {len(cleaned_hearings)} total hearings to {HEARINGS_FILE}")
        print(f"  ({len(new_hearings)} newly fetched, {len(existing_hearings)} existing, {removed_count} removed)")
    else:
        print("\nNo hearings to save.")


if __name__ == "__main__":
    main()
