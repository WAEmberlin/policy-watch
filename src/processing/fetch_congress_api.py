"""
Fetch legislation from the Congress.gov API (https://api.data.gov/congress/v3/).

This script:
- Fetches bills from the specified Congress (default: 119th)
- Handles pagination to get all results
- Normalizes data into a structured format
- Deduplicates by bill URL to prevent duplicates on repeated runs
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

LEGISLATION_FILE = OUTPUT_DIR / "legislation.json"

# Congress.gov API configuration
API_BASE_URL = "https://api.congress.gov/v3"
CONGRESS_NUMBER = 119  # 119th Congress (2025-2026)
ITEMS_PER_PAGE = 250  # Max allowed by API

# Rate limiting: API allows 1000 requests per hour
# We'll be conservative and add small delays
REQUEST_DELAY = 0.1  # 100ms between requests


def get_api_key() -> str:
    """
    Get the Congress.gov API key from environment variable.
    
    To get an API key:
    1. Visit https://api.data.gov/signup/
    2. Sign up for a free API key
    3. Set it as an environment variable: CONGRESS_API_KEY
    """
    api_key = os.environ.get("CONGRESS_API_KEY")
    if not api_key:
        raise ValueError(
            "CONGRESS_API_KEY environment variable not set. "
            "Get a free API key from https://api.data.gov/signup/ "
            "and set it as an environment variable."
        )
    return api_key


def fetch_bills_page(api_key: str, congress: int, offset: int = 0, limit: int = ITEMS_PER_PAGE) -> Optional[Dict]:
    """
    Fetch one page of bills from the Congress.gov API.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number (e.g., 119)
        offset: Starting position for pagination
        limit: Number of items per page (max 250)
    
    Returns:
        API response as dict, or None if error
    """
    url = f"{API_BASE_URL}/bill/{congress}"
    
    params = {
        "api_key": api_key,
        "format": "json",
        "limit": min(limit, ITEMS_PER_PAGE),  # API max is 250
        "offset": offset
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Rate limiting: small delay between requests
        time.sleep(REQUEST_DELAY)
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching bills (offset {offset}): {e}")
        if hasattr(e.response, 'status_code'):
            if e.response.status_code == 429:
                print("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
            elif e.response.status_code == 403:
                print("API key may be invalid or missing permissions.")
        return None


# Cache for bill titles to avoid duplicate API calls
_bill_titles_cache: Dict[str, Dict[str, str]] = {}


def fetch_bill_titles(api_key: str, congress: int, bill_type: str, bill_number: str) -> Dict[str, str]:
    """
    Fetch all titles for a specific bill from the /titles endpoint.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number (e.g., 119)
        bill_type: Bill type (e.g., "hr", "s")
        bill_number: Bill number (e.g., "123")
    
    Returns:
        Dict with 'short_title' and 'official_title' keys (values may be empty strings)
    """
    cache_key = f"{congress}-{bill_type}-{bill_number}"
    
    # Check cache first
    if cache_key in _bill_titles_cache:
        return _bill_titles_cache[cache_key]
    
    result = {"short_title": "", "official_title": ""}
    
    try:
        url = f"{API_BASE_URL}/bill/{congress}/{bill_type.lower()}/{bill_number}/titles"
        params = {
            "api_key": api_key,
            "format": "json"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        
        data = response.json()
        titles = data.get("titles", [])
        
        for title_entry in titles:
            title_type = title_entry.get("titleType", "")
            title_text = title_entry.get("title", "").strip()
            
            if not title_text:
                continue
            
            # Look for Official Title
            if "Official Title" in title_type and not result["official_title"]:
                result["official_title"] = title_text
            
            # Look for Short Title
            elif "Short Title" in title_type and not result["short_title"]:
                result["short_title"] = title_text
        
        # Cache the result
        _bill_titles_cache[cache_key] = result
        return result
        
    except requests.exceptions.Timeout:
        print(f"Timeout fetching titles for {bill_type.upper()} {bill_number}")
        _bill_titles_cache[cache_key] = result
        return result
    except requests.exceptions.RequestException as e:
        # Don't print error for every bill - too noisy
        _bill_titles_cache[cache_key] = result
        return result
    except Exception as e:
        _bill_titles_cache[cache_key] = result
        return result


def enrich_bills_with_titles(api_key: str, bills: List[Dict], max_enrich: int = 50) -> List[Dict]:
    """
    Enrich bills with official_title and short_title from the titles endpoint.
    
    Only enriches bills that don't already have official_title set.
    Limited to max_enrich bills per run to avoid long execution times.
    
    Args:
        api_key: Congress.gov API key
        bills: List of bill dictionaries
        max_enrich: Maximum number of bills to enrich per run
    
    Returns:
        Updated bills list with titles enriched
    """
    enriched_count = 0
    skipped_count = 0
    
    for bill in bills:
        # Only enrich if missing official_title
        if bill.get("official_title"):
            continue
        
        # Limit enrichment per run
        if enriched_count >= max_enrich:
            skipped_count += 1
            continue
        
        congress = bill.get("congress", CONGRESS_NUMBER)
        bill_type = bill.get("bill_type", "")
        bill_number = bill.get("bill_number", "")
        
        if not bill_type or not bill_number:
            continue
        
        # Fetch titles
        titles = fetch_bill_titles(api_key, congress, bill_type, bill_number)
        
        if titles["official_title"]:
            bill["official_title"] = titles["official_title"]
            enriched_count += 1
        
        if titles["short_title"]:
            bill["short_title"] = titles["short_title"]
        elif not bill.get("short_title"):
            # Use display title as fallback for short_title
            bill["short_title"] = bill.get("title", "")
    
    if enriched_count > 0:
        print(f"Enriched {enriched_count} bills with official titles")
    if skipped_count > 0:
        print(f"  ({skipped_count} bills skipped - will enrich in future runs)")
    
    return bills


def normalize_bill(bill_data: Dict, congress: int) -> Optional[Dict]:
    """
    Normalize a bill from the API response into our standard format.
    
    Args:
        bill_data: Raw bill data from API
        congress: Congress number
    
    Returns:
        Normalized bill dict, or None if invalid
    """
    try:
        # Extract bill number and type
        bill_number = bill_data.get("number", "")
        bill_type = bill_data.get("type", "").upper()
        
        # Build Congress.gov URL
        # Format: https://www.congress.gov/bill/{congress}th-congress/{bill-type}/{bill-number}
        bill_type_lower = bill_type.lower()
        if bill_type_lower == "hr":
            bill_type_url = "house-bill"
        elif bill_type_lower == "s":
            bill_type_url = "senate-bill"
        elif bill_type_lower == "hjres":
            bill_type_url = "house-joint-resolution"
        elif bill_type_lower == "sjres":
            bill_type_url = "senate-joint-resolution"
        elif bill_type_lower == "hconres":
            bill_type_url = "house-concurrent-resolution"
        elif bill_type_lower == "sconres":
            bill_type_url = "senate-concurrent-resolution"
        elif bill_type_lower == "hres":
            bill_type_url = "house-resolution"
        elif bill_type_lower == "sres":
            bill_type_url = "senate-resolution"
        else:
            bill_type_url = f"{bill_type_lower}-bill"
        
        congress_url = f"{congress}th-congress"
        url = f"https://www.congress.gov/bill/{congress_url}/{bill_type_url}/{bill_number}"
        
        # Extract title
        title = bill_data.get("title", "").strip()
        if not title:
            title = f"{bill_type} {bill_number}"
        
        # Filter out reserved bills (e.g., "Reserved for the Speaker", "Reserved for the Minority Leader")
        if "Reserved for" in title:
            return None
        
        # Extract summary (may be in different fields)
        summary = ""
        if "summary" in bill_data and bill_data["summary"]:
            summary_text = bill_data["summary"]
            if isinstance(summary_text, str):
                summary = summary_text.strip()
            elif isinstance(summary_text, dict):
                summary = summary_text.get("text", "").strip()
        
        # Extract sponsor information
        sponsor_name = ""
        sponsor_party = ""
        sponsor_state = ""
        sponsor_district = ""
        cosponsors = []
        
        if "sponsors" in bill_data and bill_data["sponsors"]:
            sponsors = bill_data["sponsors"]
            if isinstance(sponsors, list) and len(sponsors) > 0:
                sponsor = sponsors[0]
                if isinstance(sponsor, dict):
                    sponsor_name = sponsor.get("fullName", sponsor.get("firstName", "") + " " + sponsor.get("lastName", "")).strip()
                    sponsor_party = sponsor.get("party", "")
                    sponsor_state = sponsor.get("state", "")
                    sponsor_district = sponsor.get("district", "")
        
        # Extract cosponsors
        if "cosponsors" in bill_data and bill_data["cosponsors"]:
            cosponsors_list = bill_data["cosponsors"]
            if isinstance(cosponsors_list, list):
                for cosponsor in cosponsors_list:
                    if isinstance(cosponsor, dict):
                        cosp_name = cosponsor.get("fullName", cosponsor.get("firstName", "") + " " + cosponsor.get("lastName", "")).strip()
                        cosp_party = cosponsor.get("party", "")
                        cosp_state = cosponsor.get("state", "")
                        cosponsors.append({
                            "name": cosp_name,
                            "party": cosp_party,
                            "state": cosp_state
                        })
        
        # Extract latest action
        latest_action = ""
        latest_action_date = ""
        
        if "latestAction" in bill_data and bill_data["latestAction"]:
            action = bill_data["latestAction"]
            if isinstance(action, dict):
                latest_action = action.get("text", "").strip()
                action_date = action.get("actionDate", "")
                if action_date:
                    try:
                        dt = datetime.fromisoformat(action_date.replace("Z", "+00:00"))
                        latest_action_date = dt.isoformat()
                    except (ValueError, AttributeError):
                        latest_action_date = action_date
        
        # Extract all actions
        actions = []
        if "actions" in bill_data and bill_data["actions"]:
            actions_list = bill_data["actions"]
            if isinstance(actions_list, list):
                for action in actions_list:
                    if isinstance(action, dict):
                        actions.append({
                            "text": action.get("text", "").strip(),
                            "actionDate": action.get("actionDate", ""),
                            "type": action.get("type", "")
                        })
        
        # Extract committee information
        committees = []
        if "committees" in bill_data and bill_data["committees"]:
            committees_list = bill_data["committees"]
            if isinstance(committees_list, list):
                for committee in committees_list:
                    if isinstance(committee, dict):
                        committees.append({
                            "name": committee.get("name", "").strip(),
                            "systemCode": committee.get("systemCode", "")
                        })
        
        # Extract policy areas/subjects
        policy_areas = []
        if "policyArea" in bill_data and bill_data["policyArea"]:
            policy_area = bill_data["policyArea"]
            if isinstance(policy_area, dict):
                policy_areas.append(policy_area.get("name", "").strip())
        
        if "subjects" in bill_data and bill_data["subjects"]:
            subjects_list = bill_data["subjects"]
            if isinstance(subjects_list, list):
                for subject in subjects_list:
                    if isinstance(subject, dict):
                        policy_areas.append(subject.get("name", "").strip())
        
        # Extract status
        status = ""
        if "latestAction" in bill_data and bill_data["latestAction"]:
            action = bill_data["latestAction"]
            if isinstance(action, dict):
                status = action.get("text", "").strip()
        
        # Extract votes information
        votes = []
        if "votes" in bill_data and bill_data["votes"]:
            votes_list = bill_data["votes"]
            if isinstance(votes_list, list):
                for vote in votes_list:
                    if isinstance(vote, dict):
                        votes.append({
                            "rollNumber": vote.get("rollNumber", ""),
                            "chamber": vote.get("chamber", ""),
                            "date": vote.get("date", ""),
                            "result": vote.get("result", "")
                        })
        
        # Use introduced date as published date if available
        published_date = latest_action_date
        introduced_date = ""
        if "introducedDate" in bill_data and bill_data["introducedDate"]:
            try:
                dt = datetime.fromisoformat(bill_data["introducedDate"].replace("Z", "+00:00"))
                published_date = dt.isoformat()
                introduced_date = dt.isoformat()
            except (ValueError, AttributeError):
                pass
        
        # If no date available, use current time
        if not published_date:
            published_date = datetime.now(timezone.utc).isoformat()
        
        return {
            "bill_number": bill_number,
            "bill_type": bill_type,
            "title": title,
            "summary": summary[:2000] if summary else "",  # Limit summary length
            "sponsor_name": sponsor_name,
            "sponsor_party": sponsor_party,
            "sponsor_state": sponsor_state,
            "sponsor_district": sponsor_district,
            "cosponsors": cosponsors,
            "latest_action": latest_action,
            "latest_action_date": latest_action_date,
            "actions": actions,
            "committees": committees,
            "policy_areas": policy_areas,
            "status": status,
            "votes": votes,
            "introduced_date": introduced_date,
            "url": url,
            "published": published_date,
            "source": "Congress.gov API",
            "congress": congress
        }
    except Exception as e:
        print(f"Error normalizing bill: {e}")
        return None


def fetch_all_bills(api_key: str, congress: int, days_back: int = 30) -> List[Dict]:
    """
    Fetch bills from the Congress.gov API with pagination.
    
    Optimized to only fetch bills updated in the last N days to speed up execution.
    Bills are typically sorted by latest action date, so we can stop early when we
    encounter old bills.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number
        days_back: Only fetch bills updated in the last N days (default: 30)
                  Set to None or 0 to fetch all bills
    
    Returns:
        List of normalized bill dictionaries
    """
    all_bills = []
    offset = 0
    page = 1
    
    # Calculate cutoff date for recent bills
    cutoff_date = None
    if days_back and days_back > 0:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        print(f"Fetching bills from {congress}th Congress updated in the last {days_back} days...")
    else:
        print(f"Fetching all bills from {congress}th Congress...")
    
    print(f"API Base URL: {API_BASE_URL}")
    
    # Track if we've found any recent bills
    recent_bills_found = False
    consecutive_old_bills = 0
    max_consecutive_old = 3  # Stop after 3 pages of old bills
    
    while True:
        print(f"Fetching page {page} (offset {offset})...")
        
        response_data = fetch_bills_page(api_key, congress, offset, ITEMS_PER_PAGE)
        
        if not response_data:
            print(f"Failed to fetch page {page}. Stopping.")
            break
        
        # Extract bills from response
        bills = response_data.get("bills", [])
        
        if not bills or len(bills) == 0:
            print("No more bills found.")
            break
        
        # Normalize and filter bills
        page_recent_count = 0
        for bill_data in bills:
            normalized = normalize_bill(bill_data, congress)
            if normalized:
                # If we're filtering by date, check if bill is recent
                if cutoff_date:
                    # Check latest_action_date or published date
                    action_date_str = normalized.get("latest_action_date", normalized.get("published", ""))
                    if action_date_str:
                        try:
                            action_date = datetime.fromisoformat(action_date_str.replace("Z", "+00:00"))
                            if action_date.tzinfo is None:
                                action_date = action_date.replace(tzinfo=timezone.utc)
                            
                            if action_date >= cutoff_date:
                                all_bills.append(normalized)
                                page_recent_count += 1
                                recent_bills_found = True
                                consecutive_old_bills = 0
                            else:
                                consecutive_old_bills += 1
                        except (ValueError, AttributeError):
                            # If date parsing fails, include it to be safe
                            all_bills.append(normalized)
                            page_recent_count += 1
                else:
                    # No date filtering, include all bills
                    all_bills.append(normalized)
                    page_recent_count += 1
        
        print(f"  Processed {len(bills)} bills from page {page}, {page_recent_count} recent (total: {len(all_bills)})")
        
        # If filtering by date and we've seen several pages of old bills, we can stop early
        if cutoff_date and consecutive_old_bills >= len(bills) * max_consecutive_old:
            print(f"  Stopping early: Found {max_consecutive_old} consecutive pages of old bills")
            break
        
        # Check if there are more pages
        pagination = response_data.get("pagination", {})
        total_count = pagination.get("count", 0)
        offset += len(bills)
        
        # Stop if we've fetched all items
        if offset >= total_count or len(bills) < ITEMS_PER_PAGE:
            break
        
        page += 1
        
        # Safety limit: don't fetch more than 50 pages (12,500 bills) even if filtering
        if page > 50:
            print(f"  Reached safety limit of 50 pages. Stopping.")
            break
    
    print(f"\nTotal bills fetched: {len(all_bills)}")
    if cutoff_date and not recent_bills_found:
        print(f"Warning: No bills found updated in the last {days_back} days.")
        print("Consider increasing days_back or fetching all bills.")
    
    return all_bills


def load_existing_legislation() -> List[Dict]:
    """Load existing legislation from file."""
    if not LEGISLATION_FILE.exists():
        return []
    
    try:
        with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "bills" in data:
                return data["bills"]
            else:
                print("Warning: legislation.json has unexpected format.")
                return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load existing legislation: {e}")
        return []


def deduplicate_bills(new_bills: List[Dict], existing_bills: List[Dict]) -> List[Dict]:
    """
    Merge new bills with existing bills, updating existing bills if they have newer actions.
    
    Args:
        new_bills: Newly fetched bills
        existing_bills: Existing bills from file
    
    Returns:
        Combined list with updates applied
    """
    # Create a dict of existing bills indexed by bill_id (type-number)
    existing_by_id: Dict[str, Dict] = {}
    for bill in existing_bills:
        bill_id = f"{bill.get('bill_type', '')}-{bill.get('bill_number', '')}"
        if bill_id and bill_id != "-":
            existing_by_id[bill_id] = bill
    
    print(f"Indexed {len(existing_by_id)} existing bills for merge")
    
    new_count = 0
    updated_count = 0
    unchanged_count = 0
    
    for new_bill in new_bills:
        bill_id = f"{new_bill.get('bill_type', '')}-{new_bill.get('bill_number', '')}"
        
        if bill_id and bill_id != "-" and bill_id in existing_by_id:
            existing_bill = existing_by_id[bill_id]
            
            # Check if the new bill has a more recent action date
            new_action_date = new_bill.get("latest_action_date", "")
            existing_action_date = existing_bill.get("latest_action_date", "")
            
            # Compare dates - update if new is more recent
            if new_action_date and new_action_date > existing_action_date:
                # Update the existing bill with new data, but preserve enriched fields
                preserved_fields = ["official_title", "short_title"]
                for key, value in new_bill.items():
                    if key not in preserved_fields or not existing_bill.get(key):
                        existing_bill[key] = value
                updated_count += 1
            else:
                unchanged_count += 1
        else:
            # New bill - add to existing
            if bill_id and bill_id != "-":
                existing_by_id[bill_id] = new_bill
            new_count += 1
    
    # Convert back to list
    combined = list(existing_by_id.values())
    
    print(f"Added {new_count} new bills")
    print(f"Updated {updated_count} existing bills with newer actions")
    print(f"Unchanged: {unchanged_count} bills")
    print(f"Total: {len(combined)} bills")
    
    return combined


def main():
    """Main function to fetch and save legislation."""
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    # Load existing legislation
    existing_bills = load_existing_legislation()
    print(f"Loaded {len(existing_bills)} existing bills from {LEGISLATION_FILE}")
    
    # Fetch recent bills from API (last 30 days for speed)
    # Change days_back to None or 0 to fetch all bills
    DAYS_BACK = 30  # Only fetch bills updated in last 30 days
    new_bills = fetch_all_bills(api_key, CONGRESS_NUMBER, days_back=DAYS_BACK)
    
    if not new_bills:
        print("No bills fetched. Exiting.")
        return
    
    # Deduplicate and combine
    all_bills = deduplicate_bills(new_bills, existing_bills)
    
    # Enrich bills with official titles (limit per run to avoid long execution)
    print("\nEnriching bills with official titles...")
    all_bills = enrich_bills_with_titles(api_key, all_bills, max_enrich=500)
    
    # Sort by latest action date (newest first)
    all_bills.sort(key=lambda x: x.get("latest_action_date", x.get("published", "")), reverse=True)
    
    # Save to file
    try:
        with open(LEGISLATION_FILE, "w", encoding="utf-8") as f:
            json.dump(all_bills, f, indent=2)
        print(f"\nSuccessfully saved {len(all_bills)} bills to {LEGISLATION_FILE}")
    except Exception as e:
        print(f"\nError saving legislation: {e}")
        raise
    
    # Fetch and save federal hearings
    # Note: Congress.gov API v3 may not have a direct hearings endpoint
    # This is attempted but may return empty if the API structure doesn't support it
    try:
        federal_hearings = fetch_hearings(api_key, CONGRESS_NUMBER)
        if federal_hearings:
            HEARINGS_FILE = OUTPUT_DIR / "federal_hearings.json"
            with open(HEARINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(federal_hearings, f, indent=2)
            print(f"\nSuccessfully saved {len(federal_hearings)} federal hearings to {HEARINGS_FILE}")
        else:
            print("\nNo federal hearings fetched (API may not support this endpoint).")
            print("Note: Congress.gov API v3 hearings endpoint structure may differ.")
            print("Federal hearings feature will be skipped until API structure is confirmed.")
    except Exception as e:
        print(f"\nError fetching/saving federal hearings: {e}")
        print("Note: This is expected if the API doesn't support the hearings endpoint.")
        # Don't fail the whole script if hearings fail


def fetch_hearings(api_key: str, congress: int) -> List[Dict]:
    """
    Fetch upcoming hearings from House and Senate committees using /hearing endpoint.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number
    
    Returns:
        List of normalized hearing dictionaries
    """
    hearings = []
    
    # Try fetching all hearings first (without chamber filter)
    print("Fetching federal hearings from Congress.gov API...")
    try:
        url = f"{API_BASE_URL}/hearing"
        params = {
            "api_key": api_key,
            "format": "json",
            "congress": congress,
            "limit": 250,
            "offset": 0
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        
        data = response.json()
        hearings_list = data.get("hearings", [])
        
        if hearings_list:
            print(f"  Found {len(hearings_list)} hearings (all chambers)")
            normalized_count = 0
            failed_count = 0
            
            for i, hearing_data in enumerate(hearings_list):
                # Extract chamber from hearing data
                chamber = hearing_data.get("chamber", "").lower()
                if not chamber:
                    # Try to infer from committee or other fields
                    chamber = "house"  # Default
                
                normalized = normalize_hearing(hearing_data, congress, chamber)
                if normalized:
                    hearings.append(normalized)
                    normalized_count += 1
                else:
                    failed_count += 1
                    # Debug: print first failed hearing to see structure
                    if failed_count == 1:
                        print(f"  Debug: First failed hearing - keys: {list(hearing_data.keys())}")
                        # Print a sample of the data (first 10 keys)
                        sample_data = {k: str(v)[:100] for k, v in list(hearing_data.items())[:10]}
                        print(f"  Debug: Sample data: {json.dumps(sample_data, indent=2)}")
            
            print(f"  Successfully normalized {normalized_count} of {len(hearings_list)} hearings")
            if failed_count > 0:
                print(f"  Failed to normalize {failed_count} hearings (check field names)")
        else:
            # If bulk fetch doesn't work, try per-chamber
            print("  Bulk fetch returned no results, trying per-chamber...")
            
            # Fetch House committee hearings
            print("  Fetching House committee hearings...")
            house_hearings = fetch_committee_hearings(api_key, congress, "house")
            hearings.extend(house_hearings)
            
            # Fetch Senate committee hearings
            print("  Fetching Senate committee hearings...")
            senate_hearings = fetch_committee_hearings(api_key, congress, "senate")
            hearings.extend(senate_hearings)
            
    except requests.exceptions.RequestException as e:
        print(f"  Error with bulk fetch: {e}")
        print("  Trying per-chamber approach...")
        
        # Fallback to per-chamber fetching
        try:
            house_hearings = fetch_committee_hearings(api_key, congress, "house")
            hearings.extend(house_hearings)
        except Exception as e2:
            print(f"  Error fetching House hearings: {e2}")
        
        try:
            senate_hearings = fetch_committee_hearings(api_key, congress, "senate")
            hearings.extend(senate_hearings)
        except Exception as e2:
            print(f"  Error fetching Senate hearings: {e2}")
    
    if len(hearings) == 0:
        print("No federal hearings fetched.")
        print("Note: Congress.gov API /hearing endpoint may have different structure.")
    else:
        print(f"Total federal hearings fetched: {len(hearings)}")
    
    return hearings


def fetch_committee_hearings(api_key: str, congress: int, chamber: str) -> List[Dict]:
    """
    Fetch hearings for a specific chamber (house or senate) using the /hearing endpoint.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number
        chamber: "house" or "senate"
    
    Returns:
        List of normalized hearing dictionaries
    """
    hearings = []
    offset = 0
    page = 1
    
    while True:
        # Use the /hearing endpoint with congress and chamber filters
        url = f"{API_BASE_URL}/hearing"
        
        params = {
            "api_key": api_key,
            "format": "json",
            "congress": congress,
            "chamber": chamber,
            "limit": 250,
            "offset": offset
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            
            data = response.json()
            hearings_list = data.get("hearings", [])
            
            if not hearings_list or len(hearings_list) == 0:
                break
            
            for hearing_data in hearings_list:
                normalized = normalize_hearing(hearing_data, congress, chamber)
                if normalized:
                    hearings.append(normalized)
            
            offset += len(hearings_list)
            
            # Check pagination
            pagination = data.get("pagination", {})
            total_count = pagination.get("count", 0)
            
            if offset >= total_count:
                break
            
            page += 1
            
        except requests.exceptions.RequestException as e:
            print(f"  Error fetching {chamber} hearings (offset {offset}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    print(f"  Note: /hearing endpoint may not be available in API v3")
                    print(f"  Trying alternative approach...")
                    # Try without chamber filter
                    break
            break
    
    return hearings


def normalize_hearing(hearing_data: Dict, congress: int, chamber: str) -> Optional[Dict]:
    """
    Normalize a hearing from the API response.
    
    Args:
        hearing_data: Raw hearing data from API
        congress: Congress number
        chamber: "house" or "senate" (may also be in hearing_data)
    
    Returns:
        Normalized hearing dict, or None if invalid
    """
    try:
        # Extract basic information - try multiple field names
        title = (hearing_data.get("title", "") or 
                hearing_data.get("hearingTitle", "") or
                hearing_data.get("name", "") or
                hearing_data.get("description", "") or
                hearing_data.get("subject", "")).strip()
        
        # If still no title, try to construct one from other fields
        if not title:
            # Try to build a title from committee and date
            committee_part = ""
            if "committee" in hearing_data:
                comm = hearing_data["committee"]
                if isinstance(comm, dict):
                    committee_part = comm.get("name", "") or comm.get("fullName", "")
                elif isinstance(comm, str):
                    committee_part = comm
            
            if committee_part:
                title = f"{committee_part} Hearing"
            else:
                # Last resort: use a generic title (don't return None - we want to show these)
                title = "Congressional Hearing"
        
        # Extract chamber from data if not provided
        hearing_chamber = hearing_data.get("chamber", chamber).lower()
        if not hearing_chamber:
            hearing_chamber = chamber.lower()
        
        # Extract date and time - try multiple possible field names
        scheduled_date = ""
        scheduled_time = ""
        
        # Try different possible date fields
        date_str = (hearing_data.get("date") or 
                   hearing_data.get("hearingDate") or 
                   hearing_data.get("scheduledDate") or
                   hearing_data.get("eventDate") or
                   hearing_data.get("startDate") or
                   hearing_data.get("dateTime") or
                   hearing_data.get("publishedDate"))
        if date_str:
            try:
                # Handle different date formats
                if isinstance(date_str, str):
                    # Try ISO format first
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    scheduled_date = dt.isoformat()
                else:
                    scheduled_date = str(date_str)
            except (ValueError, AttributeError):
                scheduled_date = str(date_str) if date_str else ""
        
        # Try different possible time fields
        scheduled_time = (hearing_data.get("time") or 
                         hearing_data.get("hearingTime") or 
                         hearing_data.get("scheduledTime") or
                         hearing_data.get("eventTime") or
                         hearing_data.get("startTime") or "")
        
        # Extract location
        location = (hearing_data.get("location", "") or 
                   hearing_data.get("room", "") or
                   hearing_data.get("venue", ""))
        
        # Extract committee information - try multiple structures
        committee_name = ""
        
        # Try committee field (single object)
        if "committee" in hearing_data:
            committee = hearing_data["committee"]
            if isinstance(committee, dict):
                committee_name = (committee.get("name", "") or 
                                  committee.get("fullName", "") or
                                  committee.get("committeeName", "") or
                                  committee.get("displayName", "")).strip()
            elif isinstance(committee, str):
                committee_name = committee.strip()
        
        # Try committees field (array)
        if not committee_name and "committees" in hearing_data:
            committees_list = hearing_data["committees"]
            if isinstance(committees_list, list) and len(committees_list) > 0:
                committee = committees_list[0]
                if isinstance(committee, dict):
                    committee_name = (committee.get("name", "") or 
                                    committee.get("fullName", "") or
                                    committee.get("committeeName", "") or
                                    committee.get("displayName", "")).strip()
                elif isinstance(committee, str):
                    committee_name = committee.strip()
        
        # Fallback committee name
        if not committee_name:
            committee_name = f"{hearing_chamber.capitalize()} Committee"
        
        # Extract URL
        url = (hearing_data.get("url", "") or 
              hearing_data.get("hearingUrl", "") or
              hearing_data.get("link", ""))
        if not url and "hearingNumber" in hearing_data:
            # Try to build URL from hearing number
            hearing_number = hearing_data.get("hearingNumber", "")
            if hearing_number:
                url = f"https://www.congress.gov/hearing/{congress}th-congress/{hearing_chamber}-committee/{hearing_number}"
        elif not url and "systemCode" in hearing_data:
            # Build URL from system code
            system_code = hearing_data["systemCode"]
            url = f"https://www.congress.gov/committee/{hearing_chamber}/{system_code}/{congress}"
        
        return {
            "title": title,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "location": location,
            "committee": committee_name,
            "chamber": hearing_chamber.capitalize(),
            "url": url,
            "source": "Federal (US Congress)",
            "congress": congress
        }
    except Exception as e:
        print(f"Error normalizing hearing: {e}")
        return None


if __name__ == "__main__":
    main()

