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
from datetime import datetime, timezone
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
        
        # Extract sponsor
        sponsor_name = ""
        if "sponsors" in bill_data and bill_data["sponsors"]:
            sponsors = bill_data["sponsors"]
            if isinstance(sponsors, list) and len(sponsors) > 0:
                sponsor = sponsors[0]
                if isinstance(sponsor, dict):
                    sponsor_name = sponsor.get("fullName", sponsor.get("firstName", "") + " " + sponsor.get("lastName", "")).strip()
        
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
                        # Parse and format date
                        dt = datetime.fromisoformat(action_date.replace("Z", "+00:00"))
                        latest_action_date = dt.isoformat()
                    except (ValueError, AttributeError):
                        latest_action_date = action_date
        
        # Use introduced date as published date if available
        published_date = latest_action_date
        if "introducedDate" in bill_data and bill_data["introducedDate"]:
            try:
                dt = datetime.fromisoformat(bill_data["introducedDate"].replace("Z", "+00:00"))
                published_date = dt.isoformat()
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
            "latest_action": latest_action,
            "latest_action_date": latest_action_date,
            "url": url,
            "published": published_date,
            "source": "Congress.gov API",
            "congress": congress
        }
    except Exception as e:
        print(f"Error normalizing bill: {e}")
        return None


def fetch_all_bills(api_key: str, congress: int) -> List[Dict]:
    """
    Fetch all bills from the Congress.gov API with pagination.
    
    Args:
        api_key: Congress.gov API key
        congress: Congress number
    
    Returns:
        List of normalized bill dictionaries
    """
    all_bills = []
    offset = 0
    page = 1
    
    print(f"Fetching bills from {congress}th Congress...")
    print(f"API Base URL: {API_BASE_URL}")
    
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
        
        # Normalize each bill
        for bill_data in bills:
            normalized = normalize_bill(bill_data, congress)
            if normalized:
                all_bills.append(normalized)
        
        print(f"  Processed {len(bills)} bills from page {page} (total: {len(all_bills)})")
        
        # Check if there are more pages
        pagination = response_data.get("pagination", {})
        total_count = pagination.get("count", 0)
        offset += len(bills)
        
        # Stop if we've fetched all items
        if offset >= total_count or len(bills) < ITEMS_PER_PAGE:
            break
        
        page += 1
    
    print(f"\nTotal bills fetched: {len(all_bills)}")
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
    Remove duplicates by comparing URLs and bill identifiers.
    
    Args:
        new_bills: Newly fetched bills
        existing_bills: Existing bills from file
    
    Returns:
        Combined list without duplicates
    """
    # Create a set of existing bill identifiers (URL + bill number + type for safety)
    existing_identifiers = set()
    for bill in existing_bills:
        if "url" in bill and bill["url"]:
            existing_identifiers.add(bill["url"])
        # Also index by bill number + type as backup
        bill_id = f"{bill.get('bill_type', '')}-{bill.get('bill_number', '')}"
        if bill_id and bill_id != "-":
            existing_identifiers.add(bill_id)
    
    print(f"Indexed {len(existing_identifiers)} existing bill identifiers for deduplication")
    
    # Keep existing bills
    combined = existing_bills.copy()
    
    # Add new bills that aren't duplicates
    new_count = 0
    duplicate_count = 0
    for bill in new_bills:
        bill_url = bill.get("url", "")
        bill_id = f"{bill.get('bill_type', '')}-{bill.get('bill_number', '')}"
        
        # Check if this bill already exists
        is_duplicate = False
        if bill_url and bill_url in existing_identifiers:
            is_duplicate = True
        elif bill_id and bill_id != "-" and bill_id in existing_identifiers:
            is_duplicate = True
        
        if not is_duplicate:
            combined.append(bill)
            if bill_url:
                existing_identifiers.add(bill_url)
            if bill_id and bill_id != "-":
                existing_identifiers.add(bill_id)
            new_count += 1
        else:
            duplicate_count += 1
    
    print(f"Found {duplicate_count} duplicate bills")
    print(f"Added {new_count} new bills (total: {len(combined)})")
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
    
    # Fetch all bills from API
    new_bills = fetch_all_bills(api_key, CONGRESS_NUMBER)
    
    if not new_bills:
        print("No bills fetched. Exiting.")
        return
    
    # Deduplicate and combine
    all_bills = deduplicate_bills(new_bills, existing_bills)
    
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


if __name__ == "__main__":
    main()

