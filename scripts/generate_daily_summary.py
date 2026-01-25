#!/usr/bin/env python3
"""
Daily Summary Generator for CivicWatch

Generates factual daily legislative summaries using Ollama with phi-3:mini.
Summaries are jurisdiction-separated (Kansas Legislature vs U.S. Congress)
and appear at the top of each day's section on the website.

This script runs after midnight to generate summaries for the previous day.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# Prompt version for tracking
PROMPT_VERSION = "v1"

# File paths
OUTPUT_DIR = Path("src/output")
DATA_DIR = Path("data")
HISTORY_FILE = OUTPUT_DIR / "history.json"
LEGISLATION_FILE = OUTPUT_DIR / "legislation.json"
DAILY_SUMMARIES_FILE = DATA_DIR / "daily_summaries.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# System prompt for the model
SYSTEM_PROMPT = """You are generating a factual daily legislative summary.

Jurisdictions must remain separated.
Kansas Legislature and U.S. Congress must never be combined.

Rules:
- Do NOT use ellipses (...)
- Do NOT speculate or editorialize
- Do NOT omit key actions or dates
- Each bullet must be a complete sentence
- Reduce adjectives, not facts
- Preserve bill numbers and actions exactly
- Keep summaries concise - this is for a single day"""


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string to datetime object."""
    if not date_str:
        return None
    try:
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def is_on_date(date_str: str, target_date: str) -> bool:
    """Check if a date string matches the target date (YYYY-MM-DD format)."""
    if not date_str:
        return False
    try:
        # Extract just the date part
        item_date = date_str.split("T")[0]
        return item_date == target_date
    except (ValueError, AttributeError):
        return False


def extract_bill_number(item: Dict) -> str:
    """Extract bill number from Kansas item."""
    title = item.get("title", "")
    match = re.search(r'\b(H[BR]|S[BR]|HCR|SCR|HR|SR)\s*(\d+)', title, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    
    link = item.get("link", "")
    match = re.search(r'/measures/([A-Za-z]+)(\d+)/', link)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    
    return ""


def extract_action(item: Dict) -> str:
    """Extract action from Kansas item."""
    title = item.get("title", "")
    parts = title.split(":")
    if len(parts) >= 3:
        return parts[-1].strip()
    return title


def get_chamber_from_kansas_bill(bill_number: str) -> str:
    """Determine chamber from Kansas bill number."""
    if not bill_number:
        return "Other"
    bill_upper = bill_number.upper()
    if bill_upper.startswith("HB") or bill_upper.startswith("HCR") or bill_upper.startswith("HR"):
        return "House"
    elif bill_upper.startswith("SB") or bill_upper.startswith("SCR") or bill_upper.startswith("SR"):
        return "Senate"
    return "Other"


def get_chamber_from_congress_bill(bill_type: str) -> str:
    """Determine chamber from Congress bill type."""
    if not bill_type:
        return "Other"
    bill_upper = bill_type.upper()
    if bill_upper in ["HR", "HRES", "HJRES", "HCONRES"]:
        return "House"
    elif bill_upper in ["S", "SRES", "SJRES", "SCONRES"]:
        return "Senate"
    return "Other"


def load_kansas_bills_for_date(target_date: str) -> Dict[str, List[Dict]]:
    """Load Kansas Legislature bills for a specific date."""
    bills = {
        "House": [],
        "Senate": []
    }
    
    if not HISTORY_FILE.exists():
        return bills
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if not isinstance(history, list):
            return bills
        
        seen_bills = set()
        
        for item in history:
            if item.get("type") != "state_legislation":
                continue
            if item.get("state") != "KS":
                continue
            
            # Skip VA items
            source = item.get("source", "").lower()
            if "va" in source or "veteran" in source:
                continue
            
            # Check if on target date
            published = item.get("published", "")
            if not is_on_date(published, target_date):
                continue
            
            bill_number = extract_bill_number(item)
            if not bill_number:
                continue
            
            bill_key = f"{bill_number}-{published}"
            if bill_key in seen_bills:
                continue
            seen_bills.add(bill_key)
            
            chamber = get_chamber_from_kansas_bill(bill_number)
            if chamber not in bills:
                continue
            
            bill_obj = {
                "bill": bill_number,
                "short_title": item.get("short_title", "") or item.get("title", ""),
                "action": extract_action(item),
                "url": item.get("link", "")
            }
            
            bills[chamber].append(bill_obj)
        
    except Exception as e:
        print(f"Error loading Kansas bills: {e}")
    
    return bills


def load_congress_bills_for_date(target_date: str) -> Dict[str, List[Dict]]:
    """Load U.S. Congress bills for a specific date."""
    bills = {
        "House": [],
        "Senate": []
    }
    
    if not LEGISLATION_FILE.exists():
        return bills
    
    try:
        with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
            legislation = json.load(f)
        
        if not isinstance(legislation, list):
            return bills
        
        for item in legislation:
            date_str = item.get("latest_action_date") or item.get("published", "")
            if not is_on_date(date_str, target_date):
                continue
            
            bill_type = item.get("bill_type", "")
            chamber = get_chamber_from_congress_bill(bill_type)
            if chamber not in bills:
                continue
            
            bill_number = f"{bill_type} {item.get('bill_number', '')}"
            
            bill_obj = {
                "bill": bill_number,
                "short_title": item.get("short_title", "") or item.get("title", ""),
                "action": item.get("latest_action", ""),
                "url": item.get("url", "")
            }
            
            bills[chamber].append(bill_obj)
        
    except Exception as e:
        print(f"Error loading Congress bills: {e}")
    
    return bills


# Ollama availability check
_ollama_checked = False
_ollama_available = False


def is_ollama_available() -> bool:
    """Check if Ollama is installed and available."""
    global _ollama_checked, _ollama_available
    
    if _ollama_checked:
        return _ollama_available
    
    _ollama_checked = True
    
    import shutil
    if shutil.which("ollama") is None:
        print("Ollama not found in PATH")
        _ollama_available = False
        return False
    
    try:
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": 5,
            "encoding": "utf-8",
            "errors": "replace"
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(["ollama", "--version"], **kwargs)
        _ollama_available = result.returncode == 0
        print(f"Ollama available: {_ollama_available}")
        return _ollama_available
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        print(f"Ollama check failed: {e}")
        _ollama_available = False
        return False
    except Exception as e:
        print(f"Ollama check error: {e}")
        _ollama_available = False
        return False


def call_ollama(prompt: str, model: str = "phi3:mini") -> Optional[str]:
    """Call Ollama with the given prompt."""
    if not is_ollama_available():
        return None
    
    try:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        
        kwargs = {
            "input": full_prompt,
            "capture_output": True,
            "text": True,
            "timeout": 60,  # Shorter timeout for daily summaries
            "encoding": "utf-8",
            "errors": "replace"
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(["ollama", "run", model], **kwargs)
        
        if result.returncode != 0:
            print(f"Ollama error: {result.stderr}")
            return None
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        print("Ollama call timed out")
        return None
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


def generate_daily_summary_text(kansas_bills: Dict, congress_bills: Dict, target_date: str) -> str:
    """Generate a summary text for all activity on a given date."""
    
    kansas_house_count = len(kansas_bills.get("House", []))
    kansas_senate_count = len(kansas_bills.get("Senate", []))
    congress_house_count = len(congress_bills.get("House", []))
    congress_senate_count = len(congress_bills.get("Senate", []))
    
    total_count = kansas_house_count + kansas_senate_count + congress_house_count + congress_senate_count
    
    if total_count == 0:
        return "No legislative activity recorded for this date."
    
    # Try to generate with Ollama
    bills_data = {
        "date": target_date,
        "kansas": {
            "house": kansas_bills.get("House", [])[:10],  # Limit to avoid too long prompts
            "senate": kansas_bills.get("Senate", [])[:10]
        },
        "congress": {
            "house": congress_bills.get("House", [])[:10],
            "senate": congress_bills.get("Senate", [])[:10]
        }
    }
    
    user_prompt = f"""Generate a brief, factual summary of legislative activity for {target_date}.

Bills data:
{json.dumps(bills_data, indent=2)}

Requirements:
- Start with total count overview
- Summarize Kansas Legislature activity (if any)
- Summarize U.S. Congress activity (if any)
- Keep each jurisdiction separate
- Use complete sentences
- No ellipses
- Maximum 3-4 sentences total

Output the summary as plain text (not JSON)."""

    response = call_ollama(user_prompt)
    
    if response and len(response) > 20 and "..." not in response:
        return response
    
    # Fallback to simple summary
    return generate_fallback_daily_summary(kansas_bills, congress_bills, target_date)


def generate_fallback_daily_summary(kansas_bills: Dict, congress_bills: Dict, target_date: str) -> str:
    """Generate a simple fallback summary without LLM."""
    parts = []
    
    kansas_house = len(kansas_bills.get("House", []))
    kansas_senate = len(kansas_bills.get("Senate", []))
    congress_house = len(congress_bills.get("House", []))
    congress_senate = len(congress_bills.get("Senate", []))
    
    total = kansas_house + kansas_senate + congress_house + congress_senate
    
    if total == 0:
        return "No legislative activity recorded for this date."
    
    parts.append(f"{total} legislative items recorded.")
    
    if kansas_house > 0 or kansas_senate > 0:
        kansas_parts = []
        if kansas_house > 0:
            kansas_parts.append(f"{kansas_house} House bill{'s' if kansas_house != 1 else ''}")
        if kansas_senate > 0:
            kansas_parts.append(f"{kansas_senate} Senate bill{'s' if kansas_senate != 1 else ''}")
        parts.append(f"Kansas Legislature: {' and '.join(kansas_parts)}.")
    
    if congress_house > 0 or congress_senate > 0:
        congress_parts = []
        if congress_house > 0:
            congress_parts.append(f"{congress_house} House bill{'s' if congress_house != 1 else ''}")
        if congress_senate > 0:
            congress_parts.append(f"{congress_senate} Senate bill{'s' if congress_senate != 1 else ''}")
        parts.append(f"U.S. Congress: {' and '.join(congress_parts)}.")
    
    return " ".join(parts)


def load_existing_summaries() -> Dict[str, Dict]:
    """Load existing daily summaries from file."""
    if not DAILY_SUMMARIES_FILE.exists():
        return {}
    
    try:
        with open(DAILY_SUMMARIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading existing summaries: {e}")
        return {}


def save_summaries(summaries: Dict[str, Dict]) -> bool:
    """Save daily summaries to file."""
    try:
        with open(DAILY_SUMMARIES_FILE, "w", encoding="utf-8") as f:
            json.dump(summaries, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving summaries: {e}")
        return False


def generate_summary_for_date(target_date: str) -> Optional[Dict]:
    """Generate a summary for a specific date."""
    print(f"Generating summary for {target_date}...")
    
    # Load bills for this date
    kansas_bills = load_kansas_bills_for_date(target_date)
    congress_bills = load_congress_bills_for_date(target_date)
    
    # Count items
    kansas_house_count = len(kansas_bills.get("House", []))
    kansas_senate_count = len(kansas_bills.get("Senate", []))
    congress_house_count = len(congress_bills.get("House", []))
    congress_senate_count = len(congress_bills.get("Senate", []))
    
    total = kansas_house_count + kansas_senate_count + congress_house_count + congress_senate_count
    
    print(f"  Found {total} items (KS House: {kansas_house_count}, KS Senate: {kansas_senate_count}, "
          f"Congress House: {congress_house_count}, Congress Senate: {congress_senate_count})")
    
    # Generate summary text
    summary_text = generate_daily_summary_text(kansas_bills, congress_bills, target_date)
    
    # Build summary object
    summary = {
        "date": target_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "phi-3:mini" if is_ollama_available() else "fallback",
        "prompt_version": PROMPT_VERSION,
        "summary": summary_text,
        "counts": {
            "total": total,
            "kansas_house": kansas_house_count,
            "kansas_senate": kansas_senate_count,
            "congress_house": congress_house_count,
            "congress_senate": congress_senate_count
        }
    }
    
    return summary


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate daily legislative summaries")
    parser.add_argument("--date", help="Specific date to generate summary for (YYYY-MM-DD)")
    parser.add_argument("--yesterday", action="store_true", help="Generate summary for yesterday")
    parser.add_argument("--backfill", type=int, help="Backfill summaries for the last N days")
    args = parser.parse_args()
    
    print("=" * 60)
    print("CivicWatch Daily Summary Generator")
    print(f"Prompt Version: {PROMPT_VERSION}")
    print("=" * 60)
    
    # Determine which date(s) to process
    dates_to_process = []
    
    if args.date:
        dates_to_process.append(args.date)
    elif args.backfill:
        now = datetime.now(timezone.utc)
        for i in range(1, args.backfill + 1):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            dates_to_process.append(date)
    else:
        # Default: yesterday (since this runs after midnight)
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        dates_to_process.append(yesterday)
    
    # Load existing summaries
    summaries = load_existing_summaries()
    
    # Process each date
    for target_date in dates_to_process:
        # Check if we already have a summary for this date
        if target_date in summaries and not args.backfill:
            print(f"Summary already exists for {target_date}, skipping...")
            continue
        
        summary = generate_summary_for_date(target_date)
        if summary:
            summaries[target_date] = summary
            print(f"  Generated: {summary['summary'][:100]}...")
    
    # Save all summaries
    if save_summaries(summaries):
        print(f"\nSaved {len(summaries)} summaries to {DAILY_SUMMARIES_FILE}")
    else:
        print("\nERROR: Failed to save summaries")
        sys.exit(1)
    
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
