"""
Fix existing Kansas Legislature links in history.json that have example.com.

This script fixes links in the existing history.json file by replacing
example.com with www.kslegislature.gov while preserving the URL path.
"""
import json
import re
from pathlib import Path

OUTPUT_DIR = Path("src/output")
HISTORY_FILE = OUTPUT_DIR / "history.json"


def fix_link(link: str) -> str:
    """Fix a link by replacing example.com with www.kslegislature.gov."""
    if not link or "example.com" not in link:
        return link
    
    # Extract the path (everything after example.com) and preserve it
    # Match example.com and capture everything after it (including the path)
    match = re.search(r'https?://(?:www\.)?example\.com(/.*)?', link)
    if match:
        path = match.group(1) if match.group(1) else ""
        # Reconstruct with correct domain, preserving the path
        fixed = f"https://www.kslegislature.gov{path}"
    else:
        # Fallback: simple replace (shouldn't happen with proper URLs)
        fixed = link.replace("http://example.com", "https://www.kslegislature.gov")
        fixed = fixed.replace("https://example.com", "https://www.kslegislature.gov")
        fixed = fixed.replace("http://www.example.com", "https://www.kslegislature.gov")
        fixed = fixed.replace("https://www.example.com", "https://www.kslegislature.gov")
        fixed = fixed.replace("example.com", "www.kslegislature.gov")
        # Ensure https
        if fixed.startswith("http://"):
            fixed = fixed.replace("http://", "https://", 1)
    
    return fixed


def main():
    """Fix all Kansas Legislature links in history.json."""
    if not HISTORY_FILE.exists():
        print(f"History file not found: {HISTORY_FILE}")
        return
    
    print("Loading history.json...")
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if not isinstance(history, list):
            print("Error: history.json is not a list")
            return
        
        print(f"Loaded {len(history)} items")
        
        # Fix links
        fixed_count = 0
        for item in history:
            if item.get("source") == "Kansas Legislature" and "link" in item:
                original_link = item["link"]
                fixed_link = fix_link(original_link)
                if fixed_link != original_link:
                    item["link"] = fixed_link
                    fixed_count += 1
                    print(f"  Fixed: {original_link[:60]}... -> {fixed_link[:60]}...")
        
        if fixed_count == 0:
            print("No links needed fixing.")
            return
        
        # Save fixed history
        print(f"\nFixing {fixed_count} links...")
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        
        print(f"Successfully fixed {fixed_count} links in {HISTORY_FILE}")
        
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

