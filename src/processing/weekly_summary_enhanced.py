"""
Enhanced Weekly Summary Generator (No GPU Required)

Uses extractive summarization and better content selection to create
more informative summaries without requiring Ollama or GPU.
"""
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Try to import sumy for better summarization, but fall back to simple if not available
try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    from sumy.summarizers.text_rank import TextRankSummarizer
    SUMY_AVAILABLE = True
except ImportError:
    SUMY_AVAILABLE = False


def extract_key_sentences(text: str, max_sentences: int = 3) -> List[str]:
    """
    Extract key sentences from text using simple heuristics.
    
    Args:
        text: Input text
        max_sentences: Maximum number of sentences to extract
        
    Returns:
        List of key sentences
    """
    if not text or len(text.strip()) < 50:
        return []
    
    # Split into sentences (simple approach)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    if not sentences:
        return []
    
    # Score sentences by:
    # 1. Length (prefer medium-length sentences)
    # 2. Keyword density (common important words)
    # 3. Position (earlier sentences often more important)
    
    important_keywords = [
        'bill', 'act', 'law', 'legislation', 'committee', 'hearing',
        'passed', 'introduced', 'approved', 'voted', 'amendment',
        'budget', 'funding', 'policy', 'regulation', 'rule',
        'health', 'education', 'environment', 'economy', 'security'
    ]
    
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        if len(sentence) < 30 or len(sentence) > 300:
            continue
        
        # Score based on keyword matches
        sentence_lower = sentence.lower()
        keyword_score = sum(1 for kw in important_keywords if kw in sentence_lower)
        
        # Score based on position (earlier = better)
        position_score = 1.0 / (i + 1)
        
        # Score based on length (prefer 50-150 chars)
        length_score = 1.0
        if len(sentence) < 50:
            length_score = 0.7
        elif len(sentence) > 200:
            length_score = 0.8
        
        total_score = keyword_score * 2 + position_score + length_score
        scored_sentences.append((total_score, sentence))
    
    # Sort by score and return top sentences
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    return [s[1] for s in scored_sentences[:max_sentences]]


def summarize_with_sumy(text: str, max_sentences: int = 3) -> List[str]:
    """
    Use sumy library for extractive summarization if available.
    
    Args:
        text: Input text
        max_sentences: Maximum number of sentences
        
    Returns:
        List of summary sentences
    """
    if not SUMY_AVAILABLE or not text or len(text.strip()) < 100:
        return extract_key_sentences(text, max_sentences)
    
    try:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = TextRankSummarizer()
        summary = summarizer(parser.document, max_sentences)
        return [str(sentence) for sentence in summary]
    except Exception:
        # Fall back to simple extraction
        return extract_key_sentences(text, max_sentences)


def smart_truncate(text: str, max_length: int = 150, suffix: str = "...") -> str:
    """
    Truncate text at word boundary, preserving readability.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    # Try to truncate at sentence boundary first
    truncated = text[:max_length - len(suffix)]
    last_period = truncated.rfind('.')
    last_exclamation = truncated.rfind('!')
    last_question = truncated.rfind('?')
    
    last_sentence = max(last_period, last_exclamation, last_question)
    if last_sentence > max_length * 0.7:  # Only use if we keep most of the text
        return truncated[:last_sentence + 1] + suffix
    
    # Otherwise truncate at word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        return truncated[:last_space] + suffix
    
    return truncated + suffix


def extract_summary_from_item(item: Dict) -> Optional[str]:
    """
    Extract or generate a summary from an item.
    
    Args:
        item: Item dict with title, summary, text, etc.
        
    Returns:
        Summary text or None
    """
    # Prefer existing summary if it's good
    summary = item.get("summary", "").strip()
    if summary and len(summary) > 30:
        return summary
    
    # Try to extract from text
    text = item.get("text", "").strip()
    if text and len(text) > 50:
        key_sentences = extract_key_sentences(text, max_sentences=2)
        if key_sentences:
            return " ".join(key_sentences)
    
    # Fall back to title if nothing else
    title = item.get("title", "").strip()
    if title:
        return title
    
    return None


def select_top_items(items: List[Dict], max_items: int = 5) -> List[Dict]:
    """
    Select top items based on relevance and recency.
    
    Args:
        items: List of items
        max_items: Maximum items to return
        
    Returns:
        Top items
    """
    if len(items) <= max_items:
        return items
    
    # Score items by:
    # 1. Has summary/text (more informative)
    # 2. Recency (more recent = better)
    # 3. Title length (not too short, not too long)
    
    scored = []
    for item in items:
        score = 0
        
        # Has content
        if item.get("summary") or item.get("text"):
            score += 10
        
        # Title quality
        title = item.get("title", "")
        if 30 <= len(title) <= 150:
            score += 5
        
        # Recency (items are already sorted by date, so earlier = more recent)
        # This is handled by the order in the list
        
        scored.append((score, item))
    
    # Sort by score, then take top items
    scored.sort(reverse=True, key=lambda x: x[0])
    return [item for _, item in scored[:max_items]]


def generate_enhanced_summary(
    items: Dict[str, List[Dict]],
    week_start: datetime,
    week_end: datetime,
    max_items_per_category: int = 5
) -> str:
    """
    Generate an enhanced weekly summary with more detail.
    
    Args:
        items: Dict with 'congress', 'kansas', 'va' lists
        week_start: Start of week
        week_end: End of week
        max_items_per_category: Max items to include per category
        
    Returns:
        Enhanced summary text
    """
    congress_count = len(items["congress"])
    kansas_count = len(items["kansas"])
    va_count = len(items["va"])
    
    # Format week range
    week_start_str = week_start.strftime("%B %d")
    week_end_str = week_end.strftime("%B %d")
    if week_start.year != week_end.year:
        week_start_str += f", {week_start.year}"
    week_end_str += f", {week_end.year}"
    
    lines = []
    
    # Intro
    lines.append(f"Here is your CivicWatch weekly overview for the week of {week_start_str} through {week_end_str}.")
    lines.append("")
    
    # Congress section
    congress_bills = [item for item in items["congress"] if item.get("category") != "hearing"]
    congress_hearings = [item for item in items["congress"] if item.get("category") == "hearing"]
    
    if congress_bills or congress_hearings:
        lines.append("=== CONGRESSIONAL ACTIVITY ===")
        lines.append("")
        
        if congress_bills:
            lines.append(f"**Bills ({len(congress_bills)} total):**")
            lines.append("")
            
            top_bills = select_top_items(congress_bills, max_items_per_category)
            for i, bill in enumerate(top_bills, 1):
                title = bill.get("title", "Untitled Bill")
                title = smart_truncate(title, max_length=120)
                
                summary = extract_summary_from_item(bill)
                if summary and summary != title:
                    summary = smart_truncate(summary, max_length=200)
                    lines.append(f"{i}. {title}")
                    lines.append(f"   {summary}")
                else:
                    lines.append(f"{i}. {title}")
                
                # Add bill number if available
                bill_num = bill.get("bill_number", "")
                bill_type = bill.get("bill_type", "")
                if bill_num and bill_type:
                    lines.append(f"   ({bill_type} {bill_num})")
                
                lines.append("")
            
            if len(congress_bills) > max_items_per_category:
                lines.append(f"... and {len(congress_bills) - max_items_per_category} more bills.")
                lines.append("")
        
        if congress_hearings:
            lines.append(f"**Hearings ({len(congress_hearings)} total):**")
            lines.append("")
            
            top_hearings = select_top_items(congress_hearings, max_items_per_category)
            for i, hearing in enumerate(top_hearings, 1):
                title = hearing.get("title", "Congressional Hearing")
                title = smart_truncate(title, max_length=120)
                
                scheduled_date = hearing.get("scheduled_date", "")
                committee = hearing.get("committee", "")
                
                lines.append(f"{i}. {title}")
                if scheduled_date:
                    lines.append(f"   Scheduled: {scheduled_date}")
                if committee:
                    lines.append(f"   Committee: {committee}")
                lines.append("")
            
            if len(congress_hearings) > max_items_per_category:
                lines.append(f"... and {len(congress_hearings) - max_items_per_category} more hearings.")
                lines.append("")
    else:
        lines.append("=== CONGRESSIONAL ACTIVITY ===")
        lines.append("No new congressional activity was tracked this week.")
        lines.append("")
    
    # Kansas section
    if kansas_count > 0:
        lines.append("=== KANSAS LEGISLATURE ===")
        lines.append("")
        
        top_kansas = select_top_items(items["kansas"], max_items_per_category)
        for i, item in enumerate(top_kansas, 1):
            title = item.get("title", "Legislative Item")
            title = smart_truncate(title, max_length=120)
            
            summary = extract_summary_from_item(item)
            if summary and summary != title:
                summary = smart_truncate(summary, max_length=200)
                lines.append(f"{i}. {title}")
                lines.append(f"   {summary}")
            else:
                lines.append(f"{i}. {title}")
            lines.append("")
        
        if kansas_count > max_items_per_category:
            lines.append(f"... and {kansas_count - max_items_per_category} more items.")
            lines.append("")
    else:
        lines.append("=== KANSAS LEGISLATURE ===")
        lines.append("No new Kansas legislative activity was tracked this week.")
        lines.append("")
    
    # VA section
    if va_count > 0:
        lines.append("=== VETERANS AFFAIRS ===")
        lines.append("")
        
        top_va = select_top_items(items["va"], max_items_per_category)
        for i, item in enumerate(top_va, 1):
            title = item.get("title", "VA News")
            title = smart_truncate(title, max_length=120)
            
            summary = extract_summary_from_item(item)
            if summary and summary != title:
                summary = smart_truncate(summary, max_length=200)
                lines.append(f"{i}. {title}")
                lines.append(f"   {summary}")
            else:
                lines.append(f"{i}. {title}")
            lines.append("")
        
        if va_count > max_items_per_category:
            lines.append(f"... and {va_count - max_items_per_category} more items.")
            lines.append("")
    else:
        lines.append("=== VETERANS AFFAIRS ===")
        lines.append("No new veterans-related updates were tracked this week.")
        lines.append("")
    
    # Closing
    lines.append("---")
    lines.append("Explore full details and sources at CivicWatch.")
    
    return "\n".join(lines)

