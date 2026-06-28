"""AI enrichment for normalized bill records — integrates with existing summary pipeline."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

# Topic keyword maps for classification (rule-based fallback when no LLM available)
TOPIC_RULES = {
    "veterans": ["veteran", "va ", "military", "armed forces"],
    "education": ["education", "school", "university", "student", "teacher"],
    "property_tax": ["property tax", "mill levy", "assessment"],
    "ai_technology": ["artificial intelligence", " ai ", "technology", "data privacy", "cybersecurity"],
    "public_safety": ["public safety", "police", "crime", "fire", "emergency"],
    "healthcare": ["health", "medicaid", "medicare", "hospital"],
    "taxation": ["tax", "revenue", "appropriation"],
    "environment": ["environment", "climate", "water", "energy"],
}


def classify_topics(text: str) -> List[str]:
    """Rule-based topic classification."""
    text_lower = text.lower()
    topics = []
    for topic, keywords in TOPIC_RULES.items():
        if any(kw in text_lower for kw in keywords):
            topics.append(topic.replace("_", " ").title())
    return topics


def suggest_tags(bill: Dict[str, Any]) -> List[str]:
    """Generate suggested tags from bill metadata."""
    tags = set()
    if bill.get("level"):
        tags.add(bill["level"])
    if bill.get("state"):
        tags.add(bill["state"])
    if bill.get("chamber"):
        tags.add(bill["chamber"])
    for topic in bill.get("ai_topics") or []:
        tags.add(topic)
    for cls in bill.get("classification") or []:
        if isinstance(cls, str):
            tags.add(cls)
    return sorted(tags)


def generate_short_summary(bill: Dict[str, Any]) -> str:
    """One-sentence summary from available fields."""
    title = bill.get("title", "Untitled bill")
    action = bill.get("latest_action", "")
    bill_num = bill.get("bill_number", "")
    state = bill.get("state") or "Federal"

    if action:
        return f"{state} {bill_num}: {title} — Latest: {action[:120]}"
    return f"{state} {bill_num}: {title}"


def generate_detailed_summary(bill: Dict[str, Any]) -> str:
    """Detailed summary from title, summary, and action history."""
    parts = []
    if bill.get("bill_number"):
        parts.append(f"Bill {bill['bill_number']}")
    if bill.get("title"):
        parts.append(bill["title"])
    if bill.get("summary"):
        summary = re.sub(r"<[^>]+>", "", bill["summary"])[:500]
        parts.append(summary)
    if bill.get("latest_action"):
        parts.append(f"Latest action: {bill['latest_action']}")
    sponsors = bill.get("sponsors") or []
    if sponsors:
        names = ", ".join(s.get("name", "") for s in sponsors[:3] if s.get("name"))
        if names:
            parts.append(f"Sponsors: {names}")
    return " ".join(parts)


def generate_impact_analysis(bill: Dict[str, Any]) -> str:
    """Basic impact analysis from classification and topics."""
    topics = bill.get("ai_topics") or classify_topics(
        f"{bill.get('title', '')} {bill.get('summary', '')}"
    )
    if not topics:
        return "Impact analysis pending — insufficient classification data."
    topic_str = ", ".join(topics)
    level = bill.get("level", "legislative")
    state = bill.get("state") or "federal"
    return (
        f"This {level}-level {state} bill relates to {topic_str}. "
        f"Status: {bill.get('status') or bill.get('latest_action', 'unknown')}."
    )


def enrich_bills(bills: List[Dict[str, Any]], use_llm: bool = False) -> List[Dict[str, Any]]:
    """
    Enrich bills with AI summaries and classifications.
    Uses rule-based generation by default; set use_llm=True to attempt Ollama.
    """
    enriched = []
    for bill in bills:
        b = dict(bill)
        text = f"{b.get('title', '')} {b.get('summary', '')} {b.get('latest_action', '')}"

        b["ai_topics"] = b.get("ai_topics") or classify_topics(text)
        b["ai_tags"] = b.get("ai_tags") or suggest_tags(b)
        b["ai_summary_short"] = b.get("ai_summary_short") or generate_short_summary(b)
        b["ai_summary_detailed"] = b.get("ai_summary_detailed") or generate_detailed_summary(b)
        b["ai_impact_analysis"] = b.get("ai_impact_analysis") or generate_impact_analysis(b)

        if use_llm and os.environ.get("OLLAMA_HOST"):
            # Future: call Ollama for richer summaries (matches existing daily-summary pattern)
            pass

        enriched.append(b)
    return enriched
