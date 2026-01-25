#!/usr/bin/env python3
"""
Weekly Summary Generator for CivicWatch

Generates factual weekly legislative summaries using Ollama with phi-3:mini.
Summaries are jurisdiction-separated (Kansas Legislature vs U.S. Congress)
and chamber-separated (House vs Senate).

Output follows a strict JSON schema for consumption by the GitHub Pages frontend.
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
WEEKLY_SUMMARY_FILE = DATA_DIR / "weekly_summary.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# System prompt for the model - EXACT as specified
SYSTEM_PROMPT = """You are generating a factual weekly legislative summary.

Jurisdictions must remain separated.
Kansas Legislature and U.S. Congress must never be combined.

Rules:
- Do NOT use ellipses (...)
- Do NOT speculate or editorialize
- Do NOT omit key actions or dates
- Each bullet must be a complete sentence
- Reduce adjectives, not facts
- Preserve bill numbers and actions exactly"""


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string to datetime object."""
    if not date_str:
        return None
    try:
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def is_within_last_7_days(date_str: str, now: datetime) -> bool:
    """Check if a date string is within the last 7 days."""
    dt = parse_date(date_str)
    if not dt:
        return False
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    
    seven_days_ago = now - timedelta(days=7)
    return seven_days_ago <= dt <= now


def extract_bill_number(item: Dict) -> str:
    """Extract bill number from Kansas item."""
    # Try to extract from title (e.g., "House: HB2538: Introduced")
    title = item.get("title", "")
    match = re.search(r'\b(H[BR]|S[BR]|HCR|SCR|HR|SR)\s*(\d+)', title, re.IGNORECASE)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    
    # Try from link
    link = item.get("link", "")
    match = re.search(r'/measures/([A-Za-z]+)(\d+)/', link)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}"
    
    return ""


def extract_action(item: Dict) -> str:
    """Extract action from Kansas item."""
    title = item.get("title", "")
    # Pattern: "House: HB2538: Introduced" -> "Introduced"
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
        return "House of Representatives"
    elif bill_upper in ["S", "SRES", "SJRES", "SCONRES"]:
        return "U.S. Senate"
    return "Other"


def load_kansas_bills(now: datetime) -> Dict[str, List[Dict]]:
    """Load and categorize Kansas Legislature bills from the last 7 days."""
    bills = {
        "House": [],
        "Senate": []
    }
    
    if not HISTORY_FILE.exists():
        print("Warning: history.json not found")
        return bills
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if not isinstance(history, list):
            return bills
        
        seen_bills = set()  # Track unique bills to avoid duplicates
        
        for item in history:
            # Skip non-Kansas items
            if item.get("type") != "state_legislation":
                continue
            if item.get("state") != "KS":
                continue
            
            # Skip VA items
            source = item.get("source", "").lower()
            if "va" in source or "veteran" in source:
                continue
            
            # Check date
            published = item.get("published", "")
            if not is_within_last_7_days(published, now):
                continue
            
            # Extract bill info
            bill_number = extract_bill_number(item)
            if not bill_number:
                continue
            
            # Skip duplicates
            bill_key = f"{bill_number}-{item.get('published', '')}"
            if bill_key in seen_bills:
                continue
            seen_bills.add(bill_key)
            
            # Get chamber
            chamber = get_chamber_from_kansas_bill(bill_number)
            if chamber not in bills:
                continue
            
            # Parse date for output
            dt = parse_date(published)
            date_str = dt.strftime("%Y-%m-%d") if dt else ""
            
            # Build bill object
            bill_obj = {
                "bill": bill_number,
                "short_title": item.get("short_title", "") or item.get("title", ""),
                "action": extract_action(item),
                "date": date_str,
                "url": item.get("link", "")
            }
            
            bills[chamber].append(bill_obj)
        
        # Sort by date (newest first)
        for chamber in bills:
            bills[chamber].sort(key=lambda x: x.get("date", ""), reverse=True)
        
        print(f"Loaded {len(bills['House'])} Kansas House bills, {len(bills['Senate'])} Kansas Senate bills")
        
    except Exception as e:
        print(f"Error loading Kansas bills: {e}")
    
    return bills


def load_congress_bills(now: datetime) -> Dict[str, List[Dict]]:
    """Load and categorize U.S. Congress bills from the last 7 days."""
    bills = {
        "House of Representatives": [],
        "U.S. Senate": []
    }
    
    if not LEGISLATION_FILE.exists():
        print("Warning: legislation.json not found")
        return bills
    
    try:
        with open(LEGISLATION_FILE, "r", encoding="utf-8") as f:
            legislation = json.load(f)
        
        if not isinstance(legislation, list):
            return bills
        
        for item in legislation:
            # Check date
            date_str = item.get("latest_action_date") or item.get("published", "")
            if not is_within_last_7_days(date_str, now):
                continue
            
            # Get chamber
            bill_type = item.get("bill_type", "")
            chamber = get_chamber_from_congress_bill(bill_type)
            if chamber not in bills:
                continue
            
            # Parse date for output
            dt = parse_date(date_str)
            formatted_date = dt.strftime("%Y-%m-%d") if dt else ""
            
            # Build bill number
            bill_number = f"{bill_type} {item.get('bill_number', '')}"
            
            # Build bill object
            bill_obj = {
                "bill": bill_number,
                "short_title": item.get("short_title", "") or item.get("title", ""),
                "action": item.get("latest_action", ""),
                "date": formatted_date,
                "url": item.get("url", "")
            }
            
            bills[chamber].append(bill_obj)
        
        # Sort by date (newest first)
        for chamber in bills:
            bills[chamber].sort(key=lambda x: x.get("date", ""), reverse=True)
        
        print(f"Loaded {len(bills['House of Representatives'])} Congress House bills, {len(bills['U.S. Senate'])} Congress Senate bills")
        
    except Exception as e:
        print(f"Error loading Congress bills: {e}")
    
    return bills


# Ollama availability - checked lazily
_ollama_checked = False
_ollama_available = False


def is_ollama_available() -> bool:
    """Check if Ollama is installed and available. Cached after first check."""
    global _ollama_checked, _ollama_available
    
    if _ollama_checked:
        return _ollama_available
    
    _ollama_checked = True
    
    # Quick check using shutil.which
    import shutil
    if shutil.which("ollama") is None:
        print("Ollama not found in PATH")
        _ollama_available = False
        return False
    
    # Try a quick command
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
    """
    Call Ollama with the given prompt using the specified model.
    
    Returns the model's response text, or None on error.
    """
    if not is_ollama_available():
        print("Ollama not available, using fallback summary generation")
        return None
    
    try:
        # Build the full prompt with system instruction
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        
        # Call ollama via subprocess
        kwargs = {
            "input": full_prompt,
            "capture_output": True,
            "text": True,
            "timeout": 120,  # 2 minute timeout per call
            "encoding": "utf-8",
            "errors": "replace"  # Replace undecodable chars
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(["ollama", "run", model], **kwargs)
        
        if result.returncode != 0:
            print(f"Ollama error (exit code {result.returncode}): {result.stderr}")
            return None
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        print("Ollama call timed out after 2 minutes")
        return None
    except FileNotFoundError:
        print("Ollama not found. Please install Ollama: https://ollama.ai")
        return None
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None


def generate_section_summary(bills: List[Dict], jurisdiction: str, chamber: str) -> List[str]:
    """
    Generate summary bullets for a section using Ollama.
    
    Falls back to simple bullet points if model fails.
    """
    if not bills:
        return [f"No {chamber} bills with activity this week."]
    
    # Limit to top 20 bills to avoid overwhelming the model
    bills_to_summarize = bills[:20]
    
    # Build structured input for the model
    bills_json = json.dumps(bills_to_summarize, indent=2)
    
    user_prompt = f"""Generate a factual summary of the following {jurisdiction} {chamber} legislative activity.

Input bills (JSON):
{bills_json}

Requirements:
- Output ONLY a JSON array of strings (summary bullets)
- Each bullet must be one complete sentence
- Include bill numbers, actions, and dates
- Do not use ellipses (...)
- Do not editorialize or speculate

Output format:
["First summary bullet.", "Second summary bullet.", ...]"""

    response = call_ollama(user_prompt)
    
    if response:
        # Try to extract JSON array from response
        try:
            # Try direct JSON parse
            summaries = json.loads(response)
            if isinstance(summaries, list) and all(isinstance(s, str) for s in summaries):
                # Validate: no ellipses
                summaries = [s for s in summaries if "..." not in s]
                if summaries:
                    return summaries
        except json.JSONDecodeError:
            # Try to find JSON array in response
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                try:
                    summaries = json.loads(match.group())
                    if isinstance(summaries, list) and all(isinstance(s, str) for s in summaries):
                        summaries = [s for s in summaries if "..." not in s]
                        if summaries:
                            return summaries
                except json.JSONDecodeError:
                    pass
    
    # Fallback: generate simple summary without LLM
    print(f"Warning: Using fallback summary for {jurisdiction} {chamber}")
    return generate_fallback_summary(bills_to_summarize, chamber)


def generate_fallback_summary(bills: List[Dict], chamber: str) -> List[str]:
    """Generate simple summary bullets without LLM."""
    summaries = []
    
    # Group by action type
    actions = {}
    for bill in bills:
        action = bill.get("action", "Activity")
        if action not in actions:
            actions[action] = []
        actions[action].append(bill)
    
    for action, action_bills in actions.items():
        if len(action_bills) == 1:
            b = action_bills[0]
            # Truncate title without ellipses
            short_title = b['short_title'][:80] if len(b['short_title']) > 80 else b['short_title']
            summaries.append(f"{b['bill']} was {action.lower()} on {b['date']}.")
        else:
            bill_nums = ", ".join(b["bill"] for b in action_bills[:5])
            if len(action_bills) > 5:
                bill_nums += f" and {len(action_bills) - 5} more"
            summaries.append(f"{len(action_bills)} {chamber} bills were {action.lower()}: {bill_nums}.")
    
    return summaries if summaries else [f"No significant {chamber} activity this week."]


def validate_output(output: Dict) -> bool:
    """Validate the output matches the required schema."""
    required_keys = ["week_start", "week_end", "model", "generated_at", "jurisdictions"]
    
    for key in required_keys:
        if key not in output:
            print(f"Validation failed: missing key '{key}'")
            return False
    
    if not isinstance(output["jurisdictions"], list):
        print("Validation failed: 'jurisdictions' must be a list")
        return False
    
    for jurisdiction in output["jurisdictions"]:
        if "name" not in jurisdiction or "sections" not in jurisdiction:
            print("Validation failed: jurisdiction missing 'name' or 'sections'")
            return False
        
        if not isinstance(jurisdiction["sections"], list):
            print("Validation failed: 'sections' must be a list")
            return False
        
        for section in jurisdiction["sections"]:
            if "title" not in section or "summary" not in section:
                print("Validation failed: section missing 'title' or 'summary'")
                return False
            
            if not isinstance(section["summary"], list):
                print("Validation failed: 'summary' must be a list")
                return False
            
            # Check for ellipses in summaries
            for s in section["summary"]:
                if "..." in s:
                    print(f"Validation failed: summary contains ellipses: {s[:50]}")
                    return False
    
    return True


def generate_weekly_summary() -> Optional[Dict]:
    """
    Generate the complete weekly summary.
    
    Returns the summary dict if successful, None on failure.
    """
    now = datetime.now(timezone.utc)
    week_end = now
    week_start = now - timedelta(days=7)
    
    print(f"Generating weekly summary for {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
    
    # Load bills
    kansas_bills = load_kansas_bills(now)
    congress_bills = load_congress_bills(now)
    
    # Generate summaries for each section
    print("\nGenerating Kansas House summary...")
    kansas_house_summary = generate_section_summary(
        kansas_bills["House"], "Kansas Legislature", "House"
    )
    
    print("Generating Kansas Senate summary...")
    kansas_senate_summary = generate_section_summary(
        kansas_bills["Senate"], "Kansas Legislature", "Senate"
    )
    
    print("Generating Congress House summary...")
    congress_house_summary = generate_section_summary(
        congress_bills["House of Representatives"], "U.S. Congress", "House of Representatives"
    )
    
    print("Generating Congress Senate summary...")
    congress_senate_summary = generate_section_summary(
        congress_bills["U.S. Senate"], "U.S. Congress", "U.S. Senate"
    )
    
    # Build output structure
    output = {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "model": "phi-3:mini",
        "prompt_version": PROMPT_VERSION,
        "generated_at": now.isoformat(),
        "jurisdictions": [
            {
                "name": "Kansas Legislature",
                "sections": [
                    {
                        "title": "House Bills",
                        "summary": kansas_house_summary,
                        "bill_count": len(kansas_bills["House"])
                    },
                    {
                        "title": "Senate Bills",
                        "summary": kansas_senate_summary,
                        "bill_count": len(kansas_bills["Senate"])
                    }
                ]
            },
            {
                "name": "U.S. Congress",
                "sections": [
                    {
                        "title": "House of Representatives",
                        "summary": congress_house_summary,
                        "bill_count": len(congress_bills["House of Representatives"])
                    },
                    {
                        "title": "U.S. Senate",
                        "summary": congress_senate_summary,
                        "bill_count": len(congress_bills["U.S. Senate"])
                    }
                ]
            }
        ]
    }
    
    # Validate output
    if not validate_output(output):
        print("ERROR: Output validation failed")
        return None
    
    return output


def main():
    """Main entry point."""
    print("=" * 60, flush=True)
    print("CivicWatch Weekly Summary Generator", flush=True)
    print(f"Prompt Version: {PROMPT_VERSION}", flush=True)
    print("=" * 60, flush=True)
    
    # Generate summary
    summary = generate_weekly_summary()
    
    if summary is None:
        print("\nERROR: Failed to generate valid summary")
        sys.exit(1)
    
    # Save output
    try:
        with open(WEEKLY_SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSuccessfully saved summary to {WEEKLY_SUMMARY_FILE}")
    except Exception as e:
        print(f"\nERROR: Failed to save summary: {e}")
        sys.exit(1)
    
    # Print summary stats
    print("\n" + "=" * 60)
    print("Summary Statistics:")
    for jurisdiction in summary["jurisdictions"]:
        print(f"\n{jurisdiction['name']}:")
        for section in jurisdiction["sections"]:
            print(f"  {section['title']}: {section.get('bill_count', 0)} bills, {len(section['summary'])} summary items")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
