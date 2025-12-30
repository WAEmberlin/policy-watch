"""
Integration script to enhance weekly_overview.py with map-reduce summaries.

This can be run:
1. Locally (when laptop/GPU is on) to generate enhanced summaries
2. In GitHub Actions as an optional step (will skip if Ollama unavailable)
3. Manually to pre-generate summaries for committing to repo
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from civicwatch.integration import (
    check_ollama_available,
    generate_enhanced_summaries,
    integrate_with_weekly_overview,
    load_cached_summaries
)

# Import existing weekly overview
from src.processing.weekly_overview import (
    get_central_time,
    load_recent_items,
    generate_summary,
    WEEKLY_DIR,
    LATEST_JSON,
    WEEKLY_TEXT
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for enhanced weekly overview."""
    logger.info("Starting enhanced weekly overview generation...")
    
    # Get current time
    now = get_central_time()
    week_end = now
    week_start = week_end - timedelta(days=7)
    
    # Load recent items (same as weekly_overview.py)
    logger.info("Loading items from the last 7 days...")
    items = load_recent_items(now)
    
    congress_count = len(items["congress"])
    kansas_count = len(items["kansas"])
    va_count = len(items["va"])
    
    logger.info(f"Found {congress_count} Congress items, {kansas_count} Kansas items, {va_count} VA items")
    
    # Generate base summary (always works, no Ollama needed)
    logger.info("Generating base summary...")
    weekly_script = generate_summary(items, week_start, week_end)
    
    # Try to enhance with Ollama (optional)
    enhanced_summaries = {}
    if check_ollama_available():
        logger.info("Ollama available, generating enhanced summaries...")
        try:
            enhanced_summaries = generate_enhanced_summaries(
                items, week_start, week_end, max_items_per_category=3
            )
            if enhanced_summaries:
                logger.info(f"Generated enhanced summaries for {len(enhanced_summaries)} categories")
        except Exception as e:
            logger.warning(f"Error generating enhanced summaries: {e}")
            logger.info("Falling back to base summary only")
    else:
        logger.info("Ollama not available, using base summary only")
    
    # Integrate enhanced summaries
    enhanced_script = integrate_with_weekly_overview(
        weekly_script,
        enhanced_summaries,
        output_file=WEEKLY_DIR / "weekly_overview_enhanced.txt"
    )
    
    # Save base files (same as weekly_overview.py)
    with open(WEEKLY_TEXT, "w", encoding="utf-8") as f:
        f.write(weekly_script)
    logger.info(f"Saved base text script: {WEEKLY_TEXT}")
    
    # Update metadata
    metadata = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "item_counts": {
            "congress": congress_count,
            "kansas": kansas_count,
            "va": va_count
        },
        "script": weekly_script,
        "enhanced_available": bool(enhanced_summaries),
        "enhanced_categories": list(enhanced_summaries.keys()),
        "generated_at": now.isoformat()
    }
    
    # Add enhanced script if available
    if enhanced_summaries:
        metadata["enhanced_script"] = enhanced_script
    
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata: {LATEST_JSON}")
    
    logger.info("Weekly overview generation complete!")
    
    if enhanced_summaries:
        logger.info("Enhanced summaries available - check weekly_overview_enhanced.txt")
    else:
        logger.info("Base summary only (Ollama not available or no items to enhance)")


if __name__ == "__main__":
    main()

