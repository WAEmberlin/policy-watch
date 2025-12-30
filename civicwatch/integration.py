"""
Integration layer for CivicWatch map-reduce pipeline.

This module allows the Ollama-based summarization to work alongside
the existing weekly_overview.py system, with graceful fallback when
Ollama is not available (e.g., in GitHub Actions or when laptop is off).
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from civicwatch.config.settings import REDUCE_SUMMARIES_DIR
from civicwatch.normalizer.normalize import Normalizer
from civicwatch.chunker.chunk_text import TextChunker
from civicwatch.summarizer.map_summarize import MapSummarizer
from civicwatch.summarizer.reduce_summarize import ReduceSummarizer

logger = logging.getLogger(__name__)


def check_ollama_available() -> bool:
    """
    Check if Ollama is available and running.
    
    Returns:
        True if Ollama is accessible, False otherwise
    """
    try:
        import requests
        from civicwatch.config.settings import OLLAMA_BASE_URL
        
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def generate_enhanced_summaries(
    items: Dict[str, List[Dict]],
    week_start: datetime,
    week_end: datetime,
    max_items_per_category: int = 5
) -> Dict[str, str]:
    """
    Generate enhanced summaries for items using map-reduce pipeline.
    
    Only processes items if Ollama is available. Otherwise returns empty dict.
    
    Args:
        items: Dict with 'congress', 'kansas', 'va' lists
        week_start: Start of week
        week_end: End of week
        max_items_per_category: Max items to summarize per category
        
    Returns:
        Dict mapping category -> enhanced summary text
    """
    if not check_ollama_available():
        logger.info("Ollama not available, skipping enhanced summarization")
        return {}
    
    logger.info("Ollama available, generating enhanced summaries...")
    
    enhanced = {}
    normalizer = Normalizer()
    chunker = TextChunker()
    map_summarizer = MapSummarizer()
    reduce_summarizer = ReduceSummarizer()
    
    for category, item_list in items.items():
        if not item_list:
            continue
        
        # Limit items to avoid excessive processing
        items_to_process = item_list[:max_items_per_category]
        
        category_summaries = []
        
        for item in items_to_process:
            try:
                # Normalize item
                normalized = normalizer.normalize(item, source_type=category)
                doc_id = normalized["id"]
                text = normalized["text"]
                
                # Skip if text is too short
                if len(text) < 200:
                    continue
                
                # Chunk
                chunks = chunker.chunk(doc_id, text)
                if not chunks:
                    continue
                
                # Map summarize
                chunk_summaries = map_summarizer.summarize_chunks(chunks, force_rerun=False)
                if not chunk_summaries:
                    continue
                
                # Extract summary texts
                summary_texts = [s["summary"] for s in chunk_summaries]
                
                # Reduce
                title = normalized["title"]
                final_summary = reduce_summarizer.reduce(
                    doc_id, title, summary_texts, force_rerun=False
                )
                
                if final_summary:
                    category_summaries.append({
                        "title": title,
                        "summary": final_summary,
                        "url": item.get("url", "")
                    })
            
            except Exception as e:
                logger.warning(f"Error processing {category} item: {e}")
                continue
        
        if category_summaries:
            # Combine category summaries
            combined = "\n\n".join([
                f"**{s['title']}**: {s['summary']}"
                for s in category_summaries
            ])
            enhanced[category] = combined
    
    return enhanced


def integrate_with_weekly_overview(
    weekly_script: str,
    enhanced_summaries: Dict[str, str],
    output_file: Optional[Path] = None
) -> str:
    """
    Integrate enhanced summaries into weekly overview script.
    
    Args:
        weekly_script: Original weekly overview script
        enhanced_summaries: Dict of category -> enhanced summary
        output_file: Optional path to save enhanced version
        
    Returns:
        Enhanced weekly script
    """
    if not enhanced_summaries:
        return weekly_script
    
    # Add enhanced summaries section
    enhanced_section = "\n\n--- Enhanced Summaries (AI-Generated) ---\n\n"
    
    for category, summary in enhanced_summaries.items():
        category_name = category.capitalize()
        enhanced_section += f"{category_name}:\n{summary}\n\n"
    
    enhanced_script = weekly_script + enhanced_section
    
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(enhanced_script)
        logger.info(f"Saved enhanced weekly overview to {output_file}")
    
    return enhanced_script


def load_cached_summaries(doc_ids: List[str]) -> Dict[str, str]:
    """
    Load previously generated summaries from cache.
    
    Useful for committing summaries to repo so they're available
    even when Ollama isn't running.
    
    Args:
        doc_ids: List of document IDs to load
        
    Returns:
        Dict mapping doc_id -> summary text
    """
    summaries = {}
    
    for doc_id in doc_ids:
        filename = f"{doc_id}_final.json"
        filepath = REDUCE_SUMMARIES_DIR / filename
        
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    summaries[doc_id] = data.get("summary", "")
            except Exception as e:
                logger.warning(f"Error loading cached summary {filepath}: {e}")
    
    return summaries

