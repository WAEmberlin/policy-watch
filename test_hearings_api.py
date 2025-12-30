"""
Quick test script to inspect the Congress.gov hearings API response structure.
This helps identify the correct field names for normalization.
"""
import os
import json
import requests
from datetime import datetime

API_KEY = os.environ.get("CONGRESS_API_KEY")
if not API_KEY:
    print("ERROR: CONGRESS_API_KEY environment variable not set.")
    print("\nTo set it in PowerShell, run:")
    print('  $env:CONGRESS_API_KEY = "YOUR_API_KEY_HERE"')
    print("\nThen run this script again.")
    exit(1)

API_BASE_URL = "https://api.congress.gov/v3"
CONGRESS = 119

# Fetch first page
url = f"{API_BASE_URL}/hearing/{CONGRESS}"
params = {
    "api_key": API_KEY,
    "format": "json"
}

print(f"Fetching from: {url}")
print("=" * 60)

try:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    
    # Show pagination info
    pagination = data.get("pagination", {})
    print(f"\nPagination:")
    print(f"  Count: {pagination.get('count', 'N/A')}")
    print(f"  Next: {pagination.get('next', 'N/A')}")
    
    # Get first hearing
    hearings = data.get("hearings", [])
    print(f"\nTotal hearings in response: {len(hearings)}")
    
    if hearings:
        first_hearing = hearings[0]
        print(f"\n{'='*60}")
        print("FIRST HEARING STRUCTURE:")
        print(f"{'='*60}")
        print(json.dumps(first_hearing, indent=2, default=str))
        
        print(f"\n{'='*60}")
        print("FIELD ANALYSIS:")
        print(f"{'='*60}")
        print(f"Keys: {list(first_hearing.keys())}")
        print(f"\nTitle fields:")
        print(f"  hearingTitle: {first_hearing.get('hearingTitle', 'MISSING')}")
        print(f"  title: {first_hearing.get('title', 'MISSING')}")
        print(f"  name: {first_hearing.get('name', 'MISSING')}")
        
        print(f"\nDate fields:")
        print(f"  hearingDate: {first_hearing.get('hearingDate', 'MISSING')}")
        print(f"  date: {first_hearing.get('date', 'MISSING')}")
        print(f"  scheduledDate: {first_hearing.get('scheduledDate', 'MISSING')}")
        print(f"  eventDate: {first_hearing.get('eventDate', 'MISSING')}")
        print(f"  startDate: {first_hearing.get('startDate', 'MISSING')}")
        
        print(f"\nCommittee fields:")
        committee = first_hearing.get('committee', {})
        if isinstance(committee, dict):
            print(f"  committee (dict): {list(committee.keys())}")
            print(f"    name: {committee.get('name', 'MISSING')}")
            print(f"    fullName: {committee.get('fullName', 'MISSING')}")
        else:
            print(f"  committee: {committee}")
        
        print(f"\nOther fields:")
        print(f"  chamber: {first_hearing.get('chamber', 'MISSING')}")
        print(f"  url: {first_hearing.get('url', 'MISSING')}")
        print(f"  jacketNumber: {first_hearing.get('jacketNumber', 'MISSING')}")
        print(f"  number: {first_hearing.get('number', 'MISSING')}")
        print(f"  updateDate: {first_hearing.get('updateDate', 'MISSING')}")
        
        # Try fetching the full hearing details using the URL
        detail_url = first_hearing.get('url', '')
        if detail_url:
            print(f"\n{'='*60}")
            print("FETCHING FULL HEARING DETAILS:")
            print(f"{'='*60}")
            print(f"URL: {detail_url}")
            
            try:
                detail_params = {"api_key": API_KEY, "format": "json"}
                detail_response = requests.get(detail_url, params=detail_params, timeout=30)
                detail_response.raise_for_status()
                detail_data = detail_response.json()
                
                # The detail response might have a different structure
                print(f"\nDetail response keys: {list(detail_data.keys())}")
                
                # Look for hearing object
                hearing_detail = detail_data.get("hearing", {})
                if hearing_detail:
                    print(f"\nFull hearing detail structure:")
                    print(json.dumps(hearing_detail, indent=2, default=str))
                    
                    print(f"\nDetail field analysis:")
                    print(f"  hearingTitle: {hearing_detail.get('hearingTitle', 'MISSING')}")
                    print(f"  hearingDate: {hearing_detail.get('hearingDate', 'MISSING')}")
                    print(f"  committee: {hearing_detail.get('committee', 'MISSING')}")
                else:
                    print(f"\nFull detail response:")
                    print(json.dumps(detail_data, indent=2, default=str)[:2000])
                    
            except Exception as e:
                print(f"Error fetching detail: {e}")
        
    else:
        print("\nNo hearings found in response!")
        
except requests.exceptions.RequestException as e:
    print(f"ERROR: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Status code: {e.response.status_code}")
        try:
            print(f"Response: {e.response.text[:500]}")
        except:
            pass

