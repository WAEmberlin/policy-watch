"""
Weekly Overview Generator for PolicyWatch

Generates a weekly summary of activity from:
- Congress API (bills, votes, hearings)
- Kansas Legislature RSS feeds

Creates a spoken-friendly summary and optionally generates audio via ElevenLabs.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

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
ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path("src/output")
DOCS_DIR = Path("docs")
WEEKLY_DIR = DOCS_DIR / "weekly"
HISTORY_FILE = OUTPUT_DIR / "history.json"
LEGISLATION_FILE = OUTPUT_DIR / "legislation.json"
FEDERAL_HEARINGS_FILE = OUTPUT_DIR / "federal_hearings.json"
HEARINGS_FILE = OUTPUT_DIR / "hearings.json"
CONFIG_PATH = ROOT_DIR / "config" / "states.yaml"
NORMALIZED_DIR = ROOT_DIR / "data" / "normalized"

VETERANS_EXTRA_KEYWORDS = ["armed services"]

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
    """Check if a date string is within the last 7 days (past only, not future)."""
    dt = parse_date(date_str)
    if not dt:
        return False
    
    # Make both timezone-aware for comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    
    seven_days_ago = now - timedelta(days=7)
    # Only include items from the past week, not future dates
    return seven_days_ago <= dt <= now


def load_state_config() -> Tuple[List[Dict[str, Any]], bool]:
    """Load enabled states and federal flag from config/states.yaml."""
    default_states = [
        {"code": "ks", "name": "Kansas", "enabled": True},
        {"code": "co", "name": "Colorado", "enabled": True},
        {"code": "az", "name": "Arizona", "enabled": True},
        {"code": "ut", "name": "Utah", "enabled": True},
        {"code": "me", "name": "Maine", "enabled": True},
        {"code": "ne", "name": "Nebraska", "enabled": True},
        {"code": "md", "name": "Maryland", "enabled": True},
        {"code": "pa", "name": "Pennsylvania", "enabled": True},
    ]
    federal_enabled = True

    if not CONFIG_PATH.exists() or yaml is None:
        return default_states, federal_enabled

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        print(f"Warning: Could not load {CONFIG_PATH}: {e}")
        return default_states, federal_enabled

    states = [s for s in config.get("states", default_states) if s.get("enabled", True)]
    federal_enabled = config.get("federal", {}).get("enabled", True)
    return states, federal_enabled


def load_veterans_keywords() -> List[str]:
    """Load veterans/military keywords from topic_dashboards in states.yaml."""
    keywords = ["veteran", "veterans", "va", "military", "armed forces"]
    if CONFIG_PATH.exists() and yaml is not None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            for dash in config.get("topic_dashboards", []):
                if dash.get("id") == "veterans":
                    keywords = list(dash.get("keywords") or keywords)
                    break
        except (OSError, yaml.YAMLError):
            pass

    merged = {kw.lower() for kw in keywords}
    merged.update(kw.lower() for kw in VETERANS_EXTRA_KEYWORDS)
    return sorted(merged)


def item_search_text(item: Dict[str, Any]) -> str:
    """Combine searchable text fields from a bill, event, or vote."""
    parts = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("description", ""),
        item.get("motion_text", ""),
        item.get("latest_action", ""),
        item.get("bill_number", ""),
        " ".join(item.get("committees") or []),
    ]
    return " ".join(str(p) for p in parts if p)


def matches_veterans_topic(text: str, keywords: List[str]) -> bool:
    """Return True if text matches veterans/military topic keywords."""
    text_lower = text.lower()
    for keyword in keywords:
        kw = keyword.lower()
        if kw == "va":
            if re.search(r"\bva\b", text_lower):
                return True
        elif kw in text_lower:
            return True
    return False


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load {path}: {e}")
        return []


def _normalized_bill_to_item(bill: Dict[str, Any]) -> Dict[str, Any]:
    bill_number = bill.get("bill_number", "")
    bill_type = ""
    bill_num = ""
    match = re.match(r"^([A-Za-z]+)\s*(\d+)$", str(bill_number).strip())
    if match:
        bill_type = match.group(1).upper()
        bill_num = match.group(2)

    return {
        "title": f"{bill_number}: {bill.get('title', '')}" if bill_number else bill.get("title", ""),
        "summary": bill.get("summary", "") or bill.get("latest_action", ""),
        "source": bill.get("source", ""),
        "published": bill.get("latest_action_date") or bill.get("updated_at", ""),
        "url": bill.get("url", ""),
        "bill_number": bill_num,
        "bill_type": bill_type,
        "category": "bill",
    }


def _normalized_event_to_item(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": event.get("title", "Legislative Event"),
        "summary": event.get("description", ""),
        "source": event.get("source", ""),
        "published": event.get("scheduled_date") or event.get("updated_at", ""),
        "scheduled_date": event.get("scheduled_date", ""),
        "url": event.get("url", ""),
        "committees": event.get("committees") or [],
        "category": "hearing",
    }


def _normalized_vote_to_item(vote: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": vote.get("bill_number") or vote.get("bill_id") or "Vote",
        "summary": vote.get("motion_text", "") or vote.get("action", ""),
        "source": vote.get("source", ""),
        "published": vote.get("date", ""),
        "url": vote.get("url", ""),
        "bill_number": vote.get("bill_number", ""),
        "category": "vote",
    }


def load_jurisdiction_items(now: datetime) -> Tuple[Dict[str, Dict[str, List[Dict]]], List[Dict[str, str]]]:
    """
    Load recent activity grouped by jurisdiction from normalized data,
    with legacy src/output fallback for Congress and Kansas.
    """
    states_config, federal_enabled = load_state_config()
    jurisdictions: Dict[str, Dict[str, List[Dict]]] = {}
    section_order: List[Dict[str, str]] = []

    if federal_enabled:
        jurisdictions["federal"] = {"bills": [], "events": [], "votes": []}
        section_order.append({"id": "federal", "label": "Congress / Federal"})

    for state_cfg in states_config:
        code = state_cfg["code"].lower()
        jurisdictions[code] = {"bills": [], "events": [], "votes": []}
        section_order.append({"id": code, "label": state_cfg.get("name", code.upper())})

    normalized_available = (NORMALIZED_DIR / "bills.json").exists()
    if normalized_available:
        bills = _load_json_list(NORMALIZED_DIR / "bills.json")
        events = _load_json_list(NORMALIZED_DIR / "events.json")
        votes = _load_json_list(NORMALIZED_DIR / "votes.json")

        for bill in bills:
            date_str = bill.get("latest_action_date") or bill.get("updated_at", "")
            if not is_within_last_7_days(date_str, now):
                continue
            if bill.get("level") == "federal" and "federal" in jurisdictions:
                jurisdictions["federal"]["bills"].append(_normalized_bill_to_item(bill))
            elif bill.get("state"):
                code = str(bill["state"]).lower()
                if code in jurisdictions:
                    jurisdictions[code]["bills"].append(_normalized_bill_to_item(bill))

        for event in events:
            date_str = event.get("scheduled_date") or event.get("updated_at", "")
            if not is_within_last_7_days(date_str, now):
                continue
            if event.get("level") == "federal" and "federal" in jurisdictions:
                jurisdictions["federal"]["events"].append(_normalized_event_to_item(event))
            elif event.get("state"):
                code = str(event["state"]).lower()
                if code in jurisdictions:
                    jurisdictions[code]["events"].append(_normalized_event_to_item(event))

        for vote in votes:
            date_str = vote.get("date", "")
            if not is_within_last_7_days(date_str, now):
                continue
            code = str(vote.get("state", "")).lower()
            if code in jurisdictions:
                jurisdictions[code]["votes"].append(_normalized_vote_to_item(vote))
    else:
        legacy = load_recent_items(now)
        if "federal" in jurisdictions:
            congress_items = legacy.get("congress", [])
            jurisdictions["federal"]["bills"] = [
                item for item in congress_items if item.get("category") != "hearing"
            ]
            jurisdictions["federal"]["events"] = [
                item for item in congress_items if item.get("category") == "hearing"
            ]
        if "ks" in jurisdictions:
            jurisdictions["ks"]["bills"] = legacy.get("kansas", [])

    return jurisdictions, section_order


def categorize_item(item: Dict) -> Optional[str]:
    """
    Categorize an item as 'congress' or 'kansas'.
    
    Returns None if item doesn't fit any category.
    """
    source = item.get("source", "").lower()
    
    # Congress/federal items
    if any(keyword in source for keyword in ["congress", "federal", "us congress"]):
        return "congress"
    
    # Kansas items
    if any(keyword in source for keyword in ["kansas", "ks legislature"]):
        return "kansas"
    
    return None


def load_recent_items(now: datetime) -> Dict[str, List[Dict]]:
    """
    Load items from the last 7 days and categorize them.
    
    Returns dict with keys: 'congress', 'kansas'
    """
    items = {
        "congress": [],
        "kansas": []
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
    
    # Sort items before returning
    # Congress bills: Group by type (HR, S, SRES, etc.), then sort numerically by bill number
    # Separate bills from hearings for sorting
    if items["congress"]:
        bills = [item for item in items["congress"] if item.get("category") != "hearing"]
        hearings = [item for item in items["congress"] if item.get("category") == "hearing"]
        
        def sort_congress_bill(item):
            bill_type = item.get("bill_type", "")
            bill_number = item.get("bill_number", "")
            # Extract numeric part of bill number for sorting
            try:
                num = int(bill_number) if bill_number and bill_number.isdigit() else 0
            except (ValueError, AttributeError):
                num = 0
            # Return tuple: (type, numeric_value) for stable sort
            # Empty types go last
            return (bill_type or "ZZZ", num)
        
        # Sort bills by type then number
        bills.sort(key=sort_congress_bill)
        
        # Sort hearings by scheduled date (most recent first)
        def sort_hearing(item):
            date_str = item.get("scheduled_date", "") or item.get("published", "")
            try:
                dt = parse_date(date_str)
                if dt:
                    # Convert to timestamp for sorting (most recent first = reverse)
                    return dt.timestamp() if dt.tzinfo else dt.replace(tzinfo=timezone.utc).timestamp()
            except:
                pass
            return 0
        
        hearings.sort(key=sort_hearing, reverse=True)
        
        # Recombine: bills first, then hearings
        items["congress"] = bills + hearings
    
    # Kansas items: Group by type (HB, SB, etc.), then sort numerically
    if items["kansas"]:
        def sort_kansas_item(item):
            title = item.get("title", "")
            # Extract bill type and number from title (e.g., "House: HB2416" or "Senate: SB301")
            bill_type = ""
            bill_number = ""
            
            # Try to extract from title
            match = re.search(r'(HB|SB|HR|SR|HCR|SCR|HJR|SJR)\s*(\d+)', title, re.IGNORECASE)
            if match:
                bill_type = match.group(1).upper()
                bill_number = match.group(2)
            
            # Extract numeric part for sorting
            try:
                num = int(bill_number) if bill_number.isdigit() else 0
            except (ValueError, AttributeError):
                num = 0
            
            return (bill_type, num, bill_number)
        
        items["kansas"].sort(key=sort_kansas_item)
    
    return items


def group_bills_by_theme(bills: List[Dict]) -> Dict[str, List[Dict]]:
    """Group bills by common themes/topics."""
    themes = {
        "immigration": [],
        "healthcare": [],
        "education": [],
        "economy": [],
        "defense": [],
        "environment": [],
        "technology": [],
        "tax": [],
        "infrastructure": [],
        "other": []
    }
    
    theme_keywords = {
        "immigration": ["immigration", "immigrant", "visa", "citizenship", "border", "h-1b", "h1b"],
        "healthcare": ["health", "medicare", "medicaid", "healthcare", "medical", "hospital", "pharmaceutical"],
        "education": ["education", "school", "student", "university", "college", "teacher"],
        "economy": ["economy", "economic", "business", "trade", "commerce", "financial", "bank"],
        "defense": ["defense", "military", "veteran", "armed forces", "national security"],
        "environment": ["environment", "climate", "energy", "renewable", "emission", "pollution"],
        "technology": ["technology", "tech", "cyber", "digital", "internet", "data", "privacy"],
        "tax": ["tax", "taxation", "irs", "revenue"],
        "infrastructure": ["infrastructure", "transportation", "highway", "bridge", "road", "rail"]
    }
    
    for bill in bills:
        title_lower = bill.get("title", "").lower()
        summary_lower = bill.get("summary", "").lower()
        text = f"{title_lower} {summary_lower}"
        
        categorized = False
        for theme, keywords in theme_keywords.items():
            if any(keyword in text for keyword in keywords):
                themes[theme].append(bill)
                categorized = True
                break
        
        if not categorized:
            themes["other"].append(bill)
    
    # Remove empty themes
    return {k: v for k, v in themes.items() if v}


def group_kansas_items(items: List[Dict]) -> Dict[str, List[Dict]]:
    """Group Kansas legislative items by type/action."""
    groups = {
        "introduced": [],
        "committee": [],
        "hearing": [],
        "vote": [],
        "other": []
    }
    
    for item in items:
        title_lower = item.get("title", "").lower()
        summary_lower = item.get("summary", "").lower()
        text = f"{title_lower} {summary_lower}"
        
        if "prefiled" in text or "introduction" in text or "introduced" in text:
            groups["introduced"].append(item)
        elif "committee" in text:
            groups["committee"].append(item)
        elif "hearing" in text or "scheduled" in text:
            groups["hearing"].append(item)
        elif "vote" in text or "passed" in text or "approved" in text:
            groups["vote"].append(item)
        else:
            groups["other"].append(item)
    
    return {k: v for k, v in groups.items() if v}


def clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean up multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_bill_title(title: str, bill_type: str = "", bill_number: str = "") -> str:
    """Extract clean bill title, removing duplicate bill IDs."""
    # If title already starts with bill type and number, remove it
    if bill_type and bill_number:
        prefix = f"{bill_type} {bill_number}:"
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
        elif title.startswith(f"{bill_type} {bill_number}"):
            title = title[len(f"{bill_type} {bill_number}"):].strip()
            if title.startswith(":"):
                title = title[1:].strip()
    return title


def truncate_summary(text: str, max_length: int = 100) -> str:
    """Truncate text to max length at word boundary, ensuring complete sentences."""
    if not text or len(text) <= max_length:
        return text
    
    # Try to find a sentence ending before max_length
    truncated = text[:max_length]
    # Look for sentence endings
    for punct in ['. ', '! ', '? ']:
        last_punct = truncated.rfind(punct)
        if last_punct > max_length * 0.5:  # Only use if we got at least half the length
            return text[:last_punct + 1].strip()
    
    # Fall back to word boundary
    truncated = text[:max_length].rsplit(' ', 1)[0]
    # Add ellipsis only if we actually truncated
    if len(text) > max_length:
        truncated += "..."
    return truncated


def clean_display_text(text: str, max_length: int = 140) -> str:
    """Normalize whitespace and truncate for display in highlights."""
    cleaned = re.sub(r"\s+", " ", clean_html(text or "")).strip()
    return truncate_summary(cleaned, max_length)


def build_veterans_highlight(
    activity: Dict[str, List[Dict]],
    keywords: List[str],
    max_items: int = 3,
) -> Optional[Dict[str, Any]]:
    """Build veterans/military highlight for a jurisdiction section."""
    matches: List[Dict[str, Any]] = []

    for item_type, items in (
        ("bill", activity.get("bills", [])),
        ("hearing", activity.get("events", [])),
        ("vote", activity.get("votes", [])),
    ):
        for item in items:
            if matches_veterans_topic(item_search_text(item), keywords):
                label = clean_display_text(item.get("title", "Untitled"))
                if item_type == "bill" and item.get("bill_type") and item.get("bill_number"):
                    title = extract_bill_title(item.get("title", ""), item.get("bill_type", ""), item.get("bill_number", ""))
                    label = clean_display_text(
                        f"{item['bill_type']} {item['bill_number']}: {title}"
                    )
                matches.append(
                    {
                        "type": item_type,
                        "title": label,
                        "url": item.get("url", ""),
                    }
                )

    if not matches:
        return None

    top_matches = matches[:max_items]
    summary_parts = [m["title"] for m in top_matches]
    remaining = len(matches) - len(top_matches)
    summary = "; ".join(summary_parts)
    if remaining > 0:
        summary += f"; plus {remaining} more"

    return {
        "summary": summary,
        "items": top_matches,
        "total_matches": len(matches),
    }


def build_jurisdiction_recap(
    activity: Dict[str, List[Dict]],
    label: str,
    is_federal: bool = False,
) -> List[str]:
    """Build recap lines for one jurisdiction."""
    lines: List[str] = []
    bills = activity.get("bills", [])
    events = activity.get("events", [])
    votes = activity.get("votes", [])
    total = len(bills) + len(events) + len(votes)

    if total == 0:
        lines.append(f"{label}: No new activity this week.")
        return lines

    lines.append(f"{label}:")

    if is_federal:
        if bills:
            top_bills = bills[:3]
            for bill in top_bills:
                bill_num = bill.get("bill_number", "")
                bill_type = bill.get("bill_type", "")
                bill_id = f"{bill_type} {bill_num}" if bill_num and bill_type else ""
                title = extract_bill_title(bill.get("title", "Untitled Bill"), bill_type, bill_num)
                summary = clean_html(bill.get("summary", ""))

                if bill_id:
                    lines.append(f"{bill_id}: {title}")
                else:
                    lines.append(title)

                if summary:
                    brief_summary = truncate_summary(summary, 100)
                    if brief_summary:
                        lines.append(f"   {brief_summary}")

            remaining = len(bills) - len(top_bills)
            if remaining > 0:
                bill_groups = group_bills_by_theme(bills[3:])
                group_summaries = []
                total_grouped = 0
                for theme, theme_bills in bill_groups.items():
                    if theme != "other" and theme_bills:
                        theme_names = {
                            "immigration": "immigration",
                            "healthcare": "healthcare",
                            "education": "education",
                            "economy": "economic",
                            "defense": "defense",
                            "environment": "environmental",
                            "technology": "technology",
                            "tax": "tax",
                            "infrastructure": "infrastructure",
                        }
                        count = len(theme_bills)
                        group_summaries.append(f"{count} {theme_names.get(theme, theme)}")
                        total_grouped += count

                other_count = remaining - total_grouped
                if group_summaries:
                    if other_count > 0:
                        lines.append(f"   Plus {', '.join(group_summaries)} bills, and {other_count} others.")
                    else:
                        lines.append(f"   Plus {', '.join(group_summaries)} bills.")
                else:
                    lines.append(f"   Plus {remaining} other bills.")

        if events:
            lines.append(f"{len(events)} hearings scheduled.")
    else:
        group_parts = []
        kansas_groups = group_kansas_items(bills) if bills else {}
        if "introduced" in kansas_groups:
            group_parts.append(f"{len(kansas_groups['introduced'])} bills introduced")
        if "committee" in kansas_groups:
            group_parts.append(f"{len(kansas_groups['committee'])} committee actions")
        if "hearing" in kansas_groups:
            group_parts.append(f"{len(kansas_groups['hearing'])} hearings")
        if "vote" in kansas_groups:
            group_parts.append(f"{len(kansas_groups['vote'])} votes")
        if not group_parts and bills:
            group_parts.append(f"{len(bills)} bills updated")
        if events:
            group_parts.append(f"{len(events)} hearings")
        if votes:
            group_parts.append(f"{len(votes)} votes")

        if group_parts:
            lines.append(f"   {', '.join(group_parts)}.")
        else:
            lines.append(f"   {total} items tracked.")

    return lines


def generate_summary(
    jurisdictions: Dict[str, Dict[str, List[Dict]]],
    section_order: List[Dict[str, str]],
    week_start: datetime,
    week_end: datetime,
    veterans_keywords: List[str],
) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
    """
    Generate weekly summary script, structured sections, and per-jurisdiction counts.
    """
    week_start_str = week_start.strftime("%B %d")
    week_end_str = week_end.strftime("%B %d")
    if week_start.year != week_end.year:
        week_start_str += f", {week_start.year}"
    week_end_str += f", {week_end.year}"

    lines = [f"PolicyWatch weekly overview for {week_start_str} through {week_end_str}.", ""]
    sections: List[Dict[str, Any]] = []
    item_counts: Dict[str, int] = {}

    for section_meta in section_order:
        section_id = section_meta["id"]
        label = section_meta["label"]
        activity = jurisdictions.get(section_id, {"bills": [], "events": [], "votes": []})
        is_federal = section_id == "federal"

        recap_lines = build_jurisdiction_recap(activity, label, is_federal=is_federal)
        veterans_highlight = build_veterans_highlight(activity, veterans_keywords)

        if veterans_highlight:
            highlight_line = f"Veterans & Military highlight: {truncate_summary(veterans_highlight['summary'], 220)}."
            recap_with_highlight = recap_lines[:]
            insert_at = 2 if len(recap_with_highlight) > 1 else len(recap_with_highlight)
            recap_with_highlight.insert(insert_at, highlight_line)
        else:
            recap_with_highlight = recap_lines

        lines.extend(recap_with_highlight)
        lines.append("")

        count = len(activity.get("bills", [])) + len(activity.get("events", [])) + len(activity.get("votes", []))
        item_counts[section_id] = count

        section_data: Dict[str, Any] = {
            "id": section_id,
            "label": label,
            "recap_lines": recap_lines,
            "item_count": count,
        }
        if veterans_highlight:
            section_data["veterans_highlight"] = veterans_highlight
        sections.append(section_data)

    lines.append("Explore full details at PolicyWatch.")
    return "\n".join(lines), sections, item_counts


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
    
    # Load recent items by jurisdiction
    print("Loading items from the last 7 days...")
    jurisdictions, section_order = load_jurisdiction_items(now)
    veterans_keywords = load_veterans_keywords()

    total_items = sum(
        len(a.get("bills", [])) + len(a.get("events", [])) + len(a.get("votes", []))
        for a in jurisdictions.values()
    )
    print(f"Found {total_items} items across {len(section_order)} jurisdictions")

    # Generate summary script and structured sections
    print("Generating summary script...")
    weekly_script, sections, item_counts = generate_summary(
        jurisdictions, section_order, week_start, week_end, veterans_keywords
    )
    
    # Save text file
    with open(WEEKLY_TEXT, "w", encoding="utf-8") as f:
        f.write(weekly_script)
    print(f"Saved text script: {WEEKLY_TEXT}")
    
    # Create metadata JSON
    metadata = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "item_counts": item_counts,
        "sections": sections,
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

