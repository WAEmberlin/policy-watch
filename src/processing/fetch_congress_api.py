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
import re
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

OUTPUT_DIR = Path("src/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LEGISLATION_FILE = OUTPUT_DIR / "legislation.json"
VOTES_FILE = OUTPUT_DIR / "congress_votes.json"

# Congress.gov API configuration
API_BASE_URL = "https://api.congress.gov/v3"
CONGRESS_NUMBER = 119  # 119th Congress (2025-2026)
ITEMS_PER_PAGE = 250  # Max allowed by API

# How far back the list endpoint should request updates (via fromDateTime).
# Override with CONGRESS_DAYS_BACK. Prior values of 30/90 missed quiet bills that
# never re-appeared in the rolling window (e.g. S.4877 / S.4871 / H.R.7976).
# 365-day window ≈ 16k bills for the 119th (~67 pages at 250/page); list fetch
# is minutes, not hours, because fromDateTime + sort bound pagination.
DEFAULT_DAYS_BACK = 365

# Safety cap on list pagination. 50 pages (12,500) is below a full-year count
# for the 119th; 100 pages covers ~25k bills with headroom for growth.
MAX_LIST_PAGES = 100

# Known gaps to always attempt by bill id (cheap: one GET each). Safe no-ops if present.
PRIORITY_BACKFILL_BILLS: List[Tuple[str, str]] = [
    ("s", "4877"),   # known gap from prior DAYS_BACK=30 window miss
    ("s", "4871"),   # Improving Personal Risk Assessments to Prevent Suicide
    ("hr", "7976"),  # Moral Injury Recognition and Restitution Act
]

# Rate limiting: API allows 1000 requests per hour
# We'll be conservative and add small delays
REQUEST_DELAY = 0.1  # 100ms between requests

# Senate roll-call votes are not available via house-vote API endpoints yet.
# We parse yeas/nays from action text when recordedVotes reference the Senate.
SENATE_VOTE_TEXT_RE = re.compile(
    r"(?:Yeas and Nays|Yea-Nay Vote)[:\s]*(?:\([^)]*\)\s*)?(?:Agreed to|Passed|Failed|Rejected)?[^0-9]*"
    r"(\d+)\s*[-–—]\s*(\d+)",
    re.IGNORECASE,
)
SENATE_ROLL_NUMBER_RE = re.compile(r"Roll no\.?\s*(\d+)|Record Vote Number:\s*(\d+)", re.IGNORECASE)

_house_vote_detail_cache: Dict[str, Dict] = {}


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


def fetch_bills_page(
    api_key: str,
    congress: int,
    offset: int = 0,
    limit: int = ITEMS_PER_PAGE,
    *,
    from_datetime: Optional[str] = None,
    sort: str = "updateDate+desc",
) -> Optional[Dict]:
    """
    Fetch one page of bills from the Congress.gov API.

    Args:
        api_key: Congress.gov API key
        congress: Congress number (e.g., 119)
        offset: Starting position for pagination
        limit: Number of items per page (max 250)
        from_datetime: Optional ISO cutoff (yyyy-MM-ddT00:00:00Z) for updateDate
        sort: Congress.gov sort param (default newest updates first)

    Returns:
        API response as dict, or None if error
    """
    url = f"{API_BASE_URL}/bill/{congress}"

    params = {
        "api_key": api_key,
        "format": "json",
        "limit": min(limit, ITEMS_PER_PAGE),  # API max is 250
        "offset": offset,
        "sort": sort,
    }
    if from_datetime:
        params["fromDateTime"] = from_datetime

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        # Rate limiting: small delay between requests
        time.sleep(REQUEST_DELAY)

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching bills (offset {offset}): {e}")
        if hasattr(e, "response") and e.response is not None:
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


def _congress_api_get(api_key: str, path: str, params: Optional[Dict] = None, timeout: int = 30) -> Optional[Dict]:
    """GET a Congress.gov API path with rate limiting."""
    url = f"{API_BASE_URL}/{path.lstrip('/')}"
    query = {"api_key": api_key, "format": "json"}
    if params:
        query.update(params)
    try:
        response = requests.get(url, params=query, timeout=timeout)
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {path}: {e}")
        return None


HEARINGS_FILE = OUTPUT_DIR / "hearings.json"

_BILL_REF_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"H\.?\s*R\.?\s*(\d+)", re.I), "HR"),
    (re.compile(r"S\.?\s*J\.?\s*RES\.?\s*(\d+)", re.I), "SJRES"),
    (re.compile(r"H\.?\s*J\.?\s*RES\.?\s*(\d+)", re.I), "HJRES"),
    (re.compile(r"H\.?\s*CON\.?\s*RES\.?\s*(\d+)", re.I), "HCONRES"),
    (re.compile(r"S\.?\s*CON\.?\s*RES\.?\s*(\d+)", re.I), "SCONRES"),
    (re.compile(r"H\.?\s*RES\.?\s*(\d+)", re.I), "HRES"),
    (re.compile(r"S\.?\s*RES\.?\s*(\d+)", re.I), "SRES"),
    (re.compile(r"\bS\.?\s+(\d+)\b", re.I), "S"),
]
_SIMPLE_BILL_FIELD_RE = re.compile(
    r"^(HR|S|HJRES|SJRES|HCONRES|SCONRES|HRES|SRES)\s*(\d+)$",
    re.I,
)


def parse_bill_refs_from_text(text: str) -> List[Tuple[str, str]]:
    """Extract (bill_type, number) pairs from hearing titles or markup."""
    if not text:
        return []
    seen: set[Tuple[str, str]] = set()
    refs: List[Tuple[str, str]] = []
    for pattern, bill_type in _BILL_REF_PATTERNS:
        for match in pattern.finditer(text):
            number = match.group(1)
            key = (bill_type.upper(), number)
            if key not in seen:
                seen.add(key)
                refs.append(key)
    return refs


def parse_bill_refs_from_hearing(hearing: Dict) -> List[Tuple[str, str]]:
    """Collect bill references from a hearing record."""
    seen: set[Tuple[str, str]] = set()
    refs: List[Tuple[str, str]] = []

    def add_ref(bill_type: str, number: str) -> None:
        key = (bill_type.upper(), str(number))
        if key not in seen:
            seen.add(key)
            refs.append(key)

    for bill_type, number in parse_bill_refs_from_text(hearing.get("title", "")):
        add_ref(bill_type, number)

    bill_field = hearing.get("bill") or ""
    for part in re.split(r"[,;]+", bill_field):
        token = part.strip()
        if not token:
            continue
        match = _SIMPLE_BILL_FIELD_RE.match(token.replace(".", ""))
        if match:
            add_ref(match.group(1), match.group(2))
    return refs


def fetch_bill_detail(
    api_key: str,
    congress: int,
    bill_type: str,
    bill_number: str,
) -> Optional[Dict]:
    """Fetch a single bill by type/number from Congress.gov."""
    bill_type_lower = bill_type.lower()
    data = _congress_api_get(api_key, f"bill/{congress}/{bill_type_lower}/{bill_number}")
    if not data:
        return None
    bill_data = data.get("bill")
    if isinstance(bill_data, dict):
        return normalize_bill(bill_data, congress)
    return None


def enrich_legislation_from_hearings(
    api_key: str,
    bills: List[Dict],
    hearings_path: Path = HEARINGS_FILE,
    congress: int = CONGRESS_NUMBER,
    max_fetch: int = 40,
) -> Tuple[List[Dict], int]:
    """
    Fetch federal bills referenced in committee hearings but missing from legislation.json.
    Covers bills like HR 9237 that appear in hearing titles but not the rolling list window.
    """
    if not hearings_path.exists():
        return bills, 0

    try:
        with open(hearings_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return bills, 0

    items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return bills, 0

    existing_ids = {
        f"{b.get('bill_type', '')}-{b.get('bill_number', '')}"
        for b in bills
        if b.get("bill_type") and b.get("bill_number")
    }
    queued: set[Tuple[str, str]] = set()
    refs_to_fetch: List[Tuple[str, str]] = []

    for hearing in items:
        if not isinstance(hearing, dict):
            continue
        for bill_type, number in parse_bill_refs_from_hearing(hearing):
            bill_id = f"{bill_type}-{number}"
            key = (bill_type, number)
            if bill_id in existing_ids or key in queued:
                continue
            queued.add(key)
            refs_to_fetch.append(key)

    fetched = 0
    for bill_type, number in refs_to_fetch[:max_fetch]:
        detail = fetch_bill_detail(api_key, congress, bill_type, number)
        if not detail:
            continue
        bills = deduplicate_bills([detail], bills)
        existing_ids.add(f"{bill_type}-{number}")
        fetched += 1

    if fetched:
        print(f"Enriched legislation from hearings: fetched {fetched} missing bill(s)")
    elif refs_to_fetch:
        print(f"Hearing bill refs found ({len(refs_to_fetch)}), none newly fetched this run")

    return bills, fetched


def _parse_iso_date(value: str) -> str:
    """Normalize API date/datetime strings to YYYY-MM-DD."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except (ValueError, AttributeError):
        return value[:10] if len(value) >= 10 else value


def _bill_type_url_segment(bill_type: str) -> str:
    """Map bill type code to Congress.gov URL segment."""
    bill_type_lower = bill_type.lower()
    mapping = {
        "hr": "house-bill",
        "s": "senate-bill",
        "hjres": "house-joint-resolution",
        "sjres": "senate-joint-resolution",
        "hconres": "house-concurrent-resolution",
        "sconres": "senate-concurrent-resolution",
        "hres": "house-resolution",
        "sres": "senate-resolution",
    }
    return mapping.get(bill_type_lower, f"{bill_type_lower}-bill")


def build_bill_public_url(congress: int, bill_type: str, bill_number: str) -> str:
    """Build public Congress.gov bill URL."""
    congress_url = f"{congress}th-congress"
    segment = _bill_type_url_segment(bill_type)
    return f"https://www.congress.gov/bill/{congress_url}/{segment}/{bill_number}"


def build_house_vote_public_url(congress: int, session: int, roll_number: int) -> str:
    """Build public Congress.gov House roll call vote URL."""
    session_suffix = "1st" if session == 1 else "2nd"
    return (
        f"https://www.congress.gov/roll-call-vote/{congress}th-congress/"
        f"{session_suffix}-session/house/{roll_number}"
    )


def _sum_house_vote_totals(vote_party_total: List[Dict]) -> Tuple[int, int]:
    yeas = sum(int(party.get("yeaTotal") or 0) for party in vote_party_total)
    nays = sum(int(party.get("nayTotal") or 0) for party in vote_party_total)
    return yeas, nays


def _build_tally_text(result: str, yeas: Optional[int], nays: Optional[int]) -> str:
    if yeas is not None and nays is not None:
        return f"{result} {yeas}–{nays}"
    return result or ""


def _normalize_action(action: Dict) -> Dict:
    """Normalize a bill action from the actions endpoint."""
    normalized = {
        "text": (action.get("text") or "").strip(),
        "actionDate": action.get("actionDate", ""),
        "type": action.get("type", ""),
    }
    if action.get("actionTime"):
        normalized["actionTime"] = action["actionTime"]
    if action.get("actionCode"):
        normalized["actionCode"] = action["actionCode"]
    recorded = action.get("recordedVotes") or []
    if recorded:
        normalized["recordedVotes"] = recorded
    return normalized


def _parse_senate_tally_from_text(text: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse Senate yeas, nays, and roll number from action text."""
    yeas = nays = roll_number = None
    match = SENATE_VOTE_TEXT_RE.search(text or "")
    if match:
        yeas = int(match.group(1))
        nays = int(match.group(2))
    roll_match = SENATE_ROLL_NUMBER_RE.search(text or "")
    if roll_match:
        roll_number = int(roll_match.group(1) or roll_match.group(2))
    return yeas, nays, roll_number


def _vote_dedup_key(vote: Dict) -> str:
    return (
        f"{vote.get('congress')}-{vote.get('chamber')}-"
        f"{vote.get('session', vote.get('sessionNumber', ''))}-"
        f"{vote.get('roll_number', vote.get('rollNumber', ''))}-"
        f"{vote.get('bill_type', '')}-{vote.get('bill_number', '')}"
    )


def fetch_bill_actions(
    api_key: str,
    congress: int,
    bill_type: str,
    bill_number: str,
) -> List[Dict]:
    """
    Fetch all actions for a bill from /bill/{congress}/{type}/{number}/actions.

    Handles pagination and returns normalized action dicts.
    """
    actions: List[Dict] = []
    offset = 0
    limit = 250

    while True:
        data = _congress_api_get(
            api_key,
            f"bill/{congress}/{bill_type.lower()}/{bill_number}/actions",
            {"limit": limit, "offset": offset},
        )
        if not data:
            break

        page_actions = data.get("actions") or []
        if not page_actions:
            break

        for action in page_actions:
            if isinstance(action, dict):
                actions.append(_normalize_action(action))

        pagination = data.get("pagination") or {}
        total_count = pagination.get("count", 0)
        offset += len(page_actions)
        if total_count:
            if offset >= total_count:
                break
        elif len(page_actions) < limit:
            break

    return actions


def fetch_house_vote_detail(
    api_key: str,
    congress: int,
    session: int,
    roll_number: int,
) -> Optional[Dict]:
    """Fetch item-level House roll call vote with party totals."""
    cache_key = f"{congress}-{session}-{roll_number}"
    if cache_key in _house_vote_detail_cache:
        return _house_vote_detail_cache[cache_key]

    data = _congress_api_get(
        api_key,
        f"house-vote/{congress}/{session}/{roll_number}",
    )
    if not data:
        return None

    vote = data.get("houseRollCallVote")
    if vote:
        _house_vote_detail_cache[cache_key] = vote
    return vote


def fetch_recent_house_votes(api_key: str, congress: int, limit: int = 100) -> List[Dict]:
    """
    Fetch recent House roll call votes for a congress with pagination.

    Returns normalized vote dicts including yeas/nays from the item-level endpoint.
    Senate roll calls are not available from this API (118th/119th House only).
    """
    votes: List[Dict] = []
    offset = 0
    page_limit = min(limit, 250)

    while len(votes) < limit:
        data = _congress_api_get(
            api_key,
            f"house-vote/{congress}",
            {"limit": min(page_limit, limit - len(votes)), "offset": offset},
        )
        if not data:
            break

        page_votes = data.get("houseRollCallVotes") or []
        if not page_votes:
            break

        for vote_data in page_votes:
            if not isinstance(vote_data, dict):
                continue

            session = int(vote_data.get("sessionNumber") or 1)
            roll_number = int(vote_data.get("rollCallNumber") or 0)
            if not roll_number:
                continue

            detail = fetch_house_vote_detail(api_key, congress, session, roll_number) or vote_data
            party_totals = detail.get("votePartyTotal") or []
            yeas, nays = _sum_house_vote_totals(party_totals) if party_totals else (None, None)

            bill_type = (detail.get("legislationType") or vote_data.get("legislationType") or "").upper()
            bill_number = str(detail.get("legislationNumber") or vote_data.get("legislationNumber") or "")
            result = detail.get("result") or vote_data.get("result") or ""
            date = _parse_iso_date(detail.get("startDate") or vote_data.get("startDate") or "")

            votes.append({
                "bill_type": bill_type,
                "bill_number": bill_number,
                "congress": congress,
                "date": date,
                "chamber": "House",
                "result": result,
                "yeas": yeas,
                "nays": nays,
                "tally_text": _build_tally_text(result, yeas, nays),
                "motion": detail.get("voteQuestion") or "",
                "roll_number": roll_number,
                "session": session,
                "url": build_house_vote_public_url(congress, session, roll_number),
            })

            if len(votes) >= limit:
                break

        pagination = data.get("pagination") or {}
        total_count = pagination.get("count", 0)
        offset += len(page_votes)
        if offset >= total_count or len(page_votes) < page_limit:
            break

    return votes


def _normalize_bill_vote_record(
    *,
    bill: Dict,
    chamber: str,
    result: str,
    date: str,
    yeas: Optional[int],
    nays: Optional[int],
    motion: str,
    roll_number: Optional[int],
    session: Optional[int],
    url: str,
) -> Dict:
    bill_type = bill.get("bill_type", "")
    bill_number = str(bill.get("bill_number", ""))
    congress = bill.get("congress", CONGRESS_NUMBER)
    record = {
        "bill_type": bill_type,
        "bill_number": bill_number,
        "congress": congress,
        "date": date,
        "chamber": chamber,
        "result": result,
        "yeas": yeas,
        "nays": nays,
        "tally_text": _build_tally_text(result, yeas, nays),
        "motion": motion,
        "url": url or build_bill_public_url(congress, bill_type, bill_number),
    }
    if roll_number is not None:
        record["roll_number"] = roll_number
    if session is not None:
        record["session"] = session
    return record


def _extract_votes_from_actions(
    api_key: str,
    bill: Dict,
    actions: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse roll-call references from bill actions.

    Returns (bill_votes embedded on bill, feed-friendly vote records).
    Senate votes use action text tallies — no Senate vote API yet.
    """
    bill_votes: List[Dict] = []
    feed_votes: List[Dict] = []
    seen_keys = set()

    for action in actions:
        text = action.get("text", "")
        action_date = _parse_iso_date(action.get("actionDate", ""))
        recorded_votes = action.get("recordedVotes") or []

        if recorded_votes:
            for rv in recorded_votes:
                if not isinstance(rv, dict):
                    continue
                chamber = rv.get("chamber", "")
                roll_number = rv.get("rollNumber")
                session = rv.get("sessionNumber")
                congress = rv.get("congress") or bill.get("congress", CONGRESS_NUMBER)
                vote_date = _parse_iso_date(rv.get("date") or action_date)

                if chamber == "House" and roll_number and session:
                    detail = fetch_house_vote_detail(
                        api_key, int(congress), int(session), int(roll_number)
                    )
                    party_totals = (detail or {}).get("votePartyTotal") or []
                    yeas, nays = _sum_house_vote_totals(party_totals) if party_totals else (None, None)
                    result = (detail or {}).get("result") or ""
                    motion = (detail or {}).get("voteQuestion") or text
                    url = build_house_vote_public_url(int(congress), int(session), int(roll_number))
                elif chamber == "Senate":
                    yeas, nays, senate_roll = _parse_senate_tally_from_text(text)
                    roll_number = roll_number or senate_roll
                    result = ""
                    if "agreed to" in text.lower() or "passed" in text.lower():
                        result = "Passed"
                    elif "failed" in text.lower() or "rejected" in text.lower():
                        result = "Failed"
                    motion = text
                    url = build_bill_public_url(
                        int(congress),
                        bill.get("bill_type", ""),
                        str(bill.get("bill_number", "")),
                    )
                else:
                    continue

                vote_key = _vote_dedup_key({
                    "congress": congress,
                    "chamber": chamber,
                    "session": session,
                    "roll_number": roll_number,
                    "bill_type": bill.get("bill_type"),
                    "bill_number": bill.get("bill_number"),
                })
                if vote_key in seen_keys:
                    continue
                seen_keys.add(vote_key)

                embedded = {
                    "rollNumber": roll_number,
                    "chamber": chamber,
                    "date": vote_date,
                    "result": result,
                    "yeas": yeas,
                    "nays": nays,
                    "motion": motion,
                    "tally_text": _build_tally_text(result, yeas, nays),
                }
                bill_votes.append(embedded)

                feed_votes.append(_normalize_bill_vote_record(
                    bill=bill,
                    chamber=chamber,
                    result=result,
                    date=vote_date,
                    yeas=yeas,
                    nays=nays,
                    motion=motion,
                    roll_number=int(roll_number) if roll_number else None,
                    session=int(session) if session else None,
                    url=url,
                ))
        elif "Record Vote Number" in text or "Roll no." in text:
            yeas, nays, senate_roll = _parse_senate_tally_from_text(text)
            if yeas is None and nays is None:
                continue
            result = "Passed" if "passed" in text.lower() or "agreed to" in text.lower() else ""
            if "failed" in text.lower() or "rejected" in text.lower():
                result = "Failed"
            vote_key = _vote_dedup_key({
                "congress": bill.get("congress", CONGRESS_NUMBER),
                "chamber": "Senate",
                "session": "",
                "roll_number": senate_roll or "",
                "bill_type": bill.get("bill_type"),
                "bill_number": bill.get("bill_number"),
            })
            if vote_key in seen_keys:
                continue
            seen_keys.add(vote_key)

            embedded = {
                "rollNumber": senate_roll,
                "chamber": "Senate",
                "date": action_date,
                "result": result,
                "yeas": yeas,
                "nays": nays,
                "motion": text,
                "tally_text": _build_tally_text(result, yeas, nays),
            }
            bill_votes.append(embedded)
            feed_votes.append(_normalize_bill_vote_record(
                bill=bill,
                chamber="Senate",
                result=result,
                date=action_date,
                yeas=yeas,
                nays=nays,
                motion=text,
                roll_number=senate_roll,
                session=None,
                url=build_bill_public_url(
                    bill.get("congress", CONGRESS_NUMBER),
                    bill.get("bill_type", ""),
                    str(bill.get("bill_number", "")),
                ),
            ))

    return bill_votes, feed_votes


def _bill_updated_within_days(bill: Dict, days: int = 30) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    date_str = bill.get("latest_action_date") or bill.get("published", "")
    if not date_str:
        return False
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except (ValueError, AttributeError):
        return False


def enrich_bills_with_votes_and_actions(
    api_key: str,
    bills: List[Dict],
    max_enrich: int = 100,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Enrich recent bills with actions and roll-call votes.

    For bills updated in the last 30 days (up to max_enrich):
    - Fetches /actions and stores on bill.actions[]
    - Parses recordedVotes; fetches house-vote detail for House roll calls
    - Senate roll calls use action text (no Senate vote API yet)

    Returns:
        (updated bills list, feed-friendly congress vote records)
    """
    enriched_count = 0
    all_feed_votes: List[Dict] = []
    feed_keys = set()

    for bill in bills:
        if not _bill_updated_within_days(bill, days=30):
            continue
        if enriched_count >= max_enrich:
            break

        congress = bill.get("congress", CONGRESS_NUMBER)
        bill_type = bill.get("bill_type", "")
        bill_number = bill.get("bill_number", "")
        if not bill_type or not bill_number:
            continue

        actions = fetch_bill_actions(api_key, congress, bill_type, bill_number)
        if actions:
            bill["actions"] = actions

        bill_votes, feed_votes = _extract_votes_from_actions(api_key, bill, actions)
        if bill_votes:
            existing = {v.get("rollNumber"): v for v in bill.get("votes") or []}
            for vote in bill_votes:
                key = vote.get("rollNumber")
                if key and key in existing:
                    existing[key].update({k: v for k, v in vote.items() if v is not None})
                elif key:
                    existing[key] = vote
                else:
                    existing[f"_{len(existing)}"] = vote
            bill["votes"] = list(existing.values())

        for vote in feed_votes:
            key = _vote_dedup_key(vote)
            if key not in feed_keys:
                feed_keys.add(key)
                all_feed_votes.append(vote)

        enriched_count += 1

    if enriched_count > 0:
        print(f"Enriched {enriched_count} bills with actions and votes")
        print(f"  Extracted {len(all_feed_votes)} roll-call vote record(s)")

    return bills, all_feed_votes


def merge_congress_vote_feeds(*feeds: List[Dict]) -> List[Dict]:
    """Deduplicate and sort congress vote feed records newest first."""
    merged: Dict[str, Dict] = {}
    for feed in feeds:
        for vote in feed:
            key = _vote_dedup_key(vote)
            merged[key] = vote
    return sorted(merged.values(), key=lambda v: v.get("date", ""), reverse=True)


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
        
        # Extract votes information (list endpoint does not include votes; filled by enrichment)
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


def fetch_all_bills(api_key: str, congress: int, days_back: int = DEFAULT_DAYS_BACK) -> List[Dict]:
    """
    Fetch bills from the Congress.gov API with pagination.

    Uses fromDateTime + sort=updateDate+desc so the API returns bills updated in
    the last N days (not a client-side scan of an unsorted list that can miss
    quiet introductions once they age out of a short window).

    Args:
        api_key: Congress.gov API key
        congress: Congress number
        days_back: Only fetch bills updated in the last N days (default: 365).
                   Set to None or 0 to fetch all bills.

    Returns:
        List of normalized bill dictionaries
    """
    all_bills = []
    offset = 0
    page = 1

    from_datetime = None
    if days_back and days_back > 0:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        from_datetime = cutoff_date.strftime("%Y-%m-%dT00:00:00Z")
        print(
            f"Fetching bills from {congress}th Congress updated since {from_datetime} "
            f"(last {days_back} days)..."
        )
    else:
        print(f"Fetching all bills from {congress}th Congress...")

    print(f"API Base URL: {API_BASE_URL}")

    while True:
        print(f"Fetching page {page} (offset {offset})...")

        response_data = fetch_bills_page(
            api_key,
            congress,
            offset,
            ITEMS_PER_PAGE,
            from_datetime=from_datetime,
            sort="updateDate+desc",
        )

        if not response_data:
            print(f"Failed to fetch page {page}. Stopping.")
            break

        bills = response_data.get("bills", [])

        if not bills or len(bills) == 0:
            print("No more bills found.")
            break

        page_count = 0
        for bill_data in bills:
            normalized = normalize_bill(bill_data, congress)
            if normalized:
                all_bills.append(normalized)
                page_count += 1

        print(
            f"  Processed {len(bills)} bills from page {page}, "
            f"{page_count} normalized (total: {len(all_bills)})"
        )

        pagination = response_data.get("pagination", {})
        total_count = pagination.get("count", 0)
        offset += len(bills)

        if offset >= total_count or len(bills) < ITEMS_PER_PAGE:
            break

        page += 1

        # Safety limit: don't paginate forever if count is wrong/missing
        if page > MAX_LIST_PAGES:
            print(
                f"  Reached safety limit of {MAX_LIST_PAGES} pages "
                f"({MAX_LIST_PAGES * ITEMS_PER_PAGE} bills). Stopping."
            )
            break

    print(f"\nTotal bills fetched: {len(all_bills)}")
    if from_datetime and not all_bills:
        print(f"Warning: No bills found updated in the last {days_back} days.")
        print("Consider increasing days_back or fetching all bills.")

    return all_bills


def parse_bill_ref(ref: str) -> Optional[Tuple[str, str]]:
    """Parse 's-4877', 'S.4877', 'H.R.7976', 'hr 7976', etc. into (bill_type, number)."""
    raw = re.sub(r"[^a-z0-9]", "", str(ref or "").strip().lower())
    if not raw:
        return None
    m = re.match(r"^(hjres|sjres|hconres|sconres|hres|sres|hr|s)(\d+)$", raw)
    if not m:
        return None
    return m.group(1), m.group(2)


def fetch_bills_by_refs(
    api_key: str,
    congress: int,
    refs: List[Tuple[str, str]],
) -> List[Dict]:
    """Fetch specific bills by (type, number); skip failures quietly."""
    fetched: List[Dict] = []
    for bill_type, number in refs:
        detail = fetch_bill_detail(api_key, congress, bill_type, number)
        if detail:
            fetched.append(detail)
            print(f"  Backfilled {bill_type.upper()}.{number}")
        else:
            print(f"  Could not fetch {bill_type.upper()}.{number} (missing or API error)")
    return fetched


def resolve_days_back(cli_value: Optional[int] = None) -> int:
    """Resolve days_back from CLI, CONGRESS_DAYS_BACK env, or DEFAULT_DAYS_BACK."""
    if cli_value is not None:
        return max(0, int(cli_value))
    env_val = os.environ.get("CONGRESS_DAYS_BACK")
    if env_val is not None and str(env_val).strip() != "":
        try:
            return max(0, int(env_val))
        except ValueError:
            print(f"Warning: invalid CONGRESS_DAYS_BACK={env_val!r}; using {DEFAULT_DAYS_BACK}")
    return DEFAULT_DAYS_BACK


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


def load_existing_congress_votes() -> List[Dict]:
    """Load existing congress_votes.json feed records."""
    if not VOTES_FILE.exists():
        return []
    try:
        with open(VOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                items = data.get("items") or data.get("votes") or []
                return items if isinstance(items, list) else []
            print("Warning: congress_votes.json has unexpected format.")
            return []
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load existing congress votes: {e}")
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
    sync_ts = datetime.now(timezone.utc).isoformat()

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
                preserve_if_empty = ["votes", "actions"]
                for key, value in new_bill.items():
                    if key in preserved_fields and existing_bill.get(key):
                        continue
                    if key in preserve_if_empty and not value and existing_bill.get(key):
                        continue
                    existing_bill[key] = value
                existing_bill["last_synced_at"] = sync_ts
                updated_count += 1
            else:
                unchanged_count += 1
        else:
            # New bill - add to existing
            if bill_id and bill_id != "-":
                new_bill["last_synced_at"] = sync_ts
                existing_by_id[bill_id] = new_bill
            new_count += 1
    
    # Convert back to list
    combined = list(existing_by_id.values())
    
    print(f"Added {new_count} new bills")
    print(f"Updated {updated_count} existing bills with newer actions")
    print(f"Unchanged: {unchanged_count} bills")
    print(f"Total: {len(combined)} bills")
    
    return combined


def main(argv: Optional[List[str]] = None):
    """Main function to fetch and save legislation."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch Congress.gov legislation")
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help=f"Only fetch bills updated in the last N days (default: {DEFAULT_DAYS_BACK}, "
        "or CONGRESS_DAYS_BACK; 0 = all)",
    )
    parser.add_argument(
        "--backfill",
        type=str,
        default="",
        help="Comma-separated bill refs to force-fetch (e.g. s-4877,s-4871,hr-7976)",
    )
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="Skip the rolling list fetch; only merge --backfill / priority IDs into legislation.json",
    )
    args = parser.parse_args(argv)

    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        return

    # Load existing legislation
    existing_bills = load_existing_legislation()
    print(f"Loaded {len(existing_bills)} existing bills from {LEGISLATION_FILE}")

    days_back = resolve_days_back(args.days_back)
    new_bills: List[Dict] = []
    if not args.backfill_only:
        # Fetch recent bills from API (fromDateTime + updateDate sort)
        new_bills = fetch_all_bills(api_key, CONGRESS_NUMBER, days_back=days_back)

    if new_bills:
        all_bills = deduplicate_bills(new_bills, existing_bills)
    elif existing_bills:
        if not args.backfill_only:
            print("No new bills fetched from API; continuing with existing legislation.")
        all_bills = existing_bills
    else:
        print("No bills fetched and no existing legislation. Exiting.")
        return

    # Priority + optional CLI backfill (covers quiet bills that fell out of the window)
    extra_refs: List[Tuple[str, str]] = list(PRIORITY_BACKFILL_BILLS)
    for part in (args.backfill or "").split(","):
        parsed = parse_bill_ref(part)
        if parsed and parsed not in extra_refs:
            extra_refs.append(parsed)
    existing_ids = {
        f"{b.get('bill_type', '')}-{b.get('bill_number', '')}".lower()
        for b in all_bills
        if b.get("bill_type") and b.get("bill_number")
    }
    missing_refs = [
        (bt, num) for bt, num in extra_refs
        if f"{bt}-{num}".lower() not in existing_ids
    ]
    if missing_refs:
        print(f"\nBackfilling {len(missing_refs)} priority/CLI bill(s)...")
        backfilled = fetch_bills_by_refs(api_key, CONGRESS_NUMBER, missing_refs)
        if backfilled:
            all_bills = deduplicate_bills(backfilled, all_bills)
    else:
        print("\nPriority backfill bills already present.")

    # Enrich bills with official titles (limit per run to avoid long execution)
    print("\nEnriching bills with official titles...")
    all_bills = enrich_bills_with_titles(api_key, all_bills, max_enrich=500)

    # Enrich recent bills with actions and roll-call votes
    print("\nEnriching bills with actions and roll-call votes...")
    all_bills, bill_vote_feed = enrich_bills_with_votes_and_actions(api_key, all_bills, max_enrich=100)

    # Supplement with recent House roll calls (Senate not in API yet)
    print("\nFetching recent House roll call votes...")
    recent_house_votes = fetch_recent_house_votes(api_key, CONGRESS_NUMBER, limit=100)
    existing_votes = load_existing_congress_votes()
    congress_votes = merge_congress_vote_feeds(existing_votes, bill_vote_feed, recent_house_votes)
    
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

    try:
        with open(VOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(congress_votes, f, indent=2)
        print(f"Successfully saved {len(congress_votes)} roll-call votes to {VOTES_FILE}")
    except Exception as e:
        print(f"\nError saving congress votes: {e}")
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

