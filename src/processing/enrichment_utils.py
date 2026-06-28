"""Shared helpers for merging enrichment payloads into bill records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def normalize_bill_key(bill_number: str) -> str:
    """Normalize bill number to API key form: 'SB 498' -> 'SB498'."""
    return bill_number.replace(" ", "").upper().strip()


def apply_enrichment_to_bill(bill: Dict[str, Any], enrichment: Dict[str, Any]) -> Dict[str, Any]:
    """Merge enrichment fields into a normalized bill dict (non-destructive)."""
    if not enrichment:
        return bill

    merged = dict(bill)

    if enrichment.get("short_title") and not merged.get("title"):
        merged["title"] = enrichment["short_title"]
    elif enrichment.get("short_title"):
        merged["short_title"] = enrichment["short_title"]

    if enrichment.get("long_title"):
        merged["official_title"] = enrichment["long_title"]

    if enrichment.get("summary"):
        merged["summary"] = enrichment["summary"]
    elif enrichment.get("long_title") and not merged.get("summary"):
        merged["summary"] = enrichment["long_title"][:2000]

    if enrichment.get("status"):
        merged["status"] = enrichment["status"]

    if enrichment.get("latest_action"):
        merged["latest_action"] = enrichment["latest_action"]
    if enrichment.get("latest_action_date"):
        merged["latest_action_date"] = enrichment["latest_action_date"]

    if enrichment.get("sponsors"):
        merged["sponsors"] = enrichment["sponsors"]

    if enrichment.get("votes"):
        merged["votes"] = enrichment["votes"]

    if enrichment.get("committees"):
        merged["committees"] = enrichment["committees"]

    if enrichment.get("document_urls"):
        existing = set(merged.get("document_urls") or [])
        existing.update(enrichment["document_urls"])
        merged["document_urls"] = list(existing)

    if enrichment.get("history"):
        merged["action_history"] = enrichment["history"]

    if enrichment.get("hearings"):
        merged["events"] = enrichment["hearings"]

    merged["enrichment_source"] = enrichment.get("source", "unknown")
    merged["enriched_at"] = enrichment.get("enriched_at", "")
    return merged


def apply_enrichments_to_bills(
    bills: List[Dict[str, Any]],
    enrichments: Dict[str, Dict[str, Any]],
    state: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Apply enrichment map to a list of bills."""
    result = []
    for bill in bills:
        if state and bill.get("state") and bill.get("state") != state:
            result.append(bill)
            continue
        key = normalize_bill_key(bill.get("bill_number", ""))
        enrichment = enrichments.get(key) or enrichments.get(bill.get("id", ""))
        result.append(apply_enrichment_to_bill(bill, enrichment) if enrichment else bill)
    return result
