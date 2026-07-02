"""Veteran bill impact classification — CSV overrides plus keyword rules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
VETERANS_DATA_DIR = ROOT / "data" / "veterans"
CO_BILLS_FILE = VETERANS_DATA_DIR / "co_bills.json"

IMPACT_LEVELS = ("red", "yellow", "green")

# Scoring factor keyword groups (ordered by priority for tie-breaking).
SCORING_FACTORS: Dict[str, List[str]] = {
    "benefits_compensation": [
        "gi bill", "survivor benefit", "burial benefit", "va benefit", "veterans benefit",
        "compensation", "pension", "dependency indemnity", "title 38",
    ],
    "healthcare_mental_health": [
        "va health", "veterans health", "veterans affairs", "ptsd", "tbi",
        "mental health", "suicide prevention", "post-traumatic",
    ],
    "housing_homelessness": [
        "veteran housing", "homeless veteran", "housing voucher", "shelter veteran",
    ],
    "disability_ratings": [
        "disability rating", "service-connected", "service connected", "rating schedule",
    ],
    "employment_education": [
        "veteran preference", "hiring preference", "employment preference",
        "military spouse", "licensing", "certification", "apprenticeship",
    ],
    "criminal_justice_courts": [
        "veterans court", "veteran court", "diversion", "treatment court",
        "veterans justice", "justice outreach",
    ],
}

RED_SIGNALS = [
    *SCORING_FACTORS["benefits_compensation"],
    *SCORING_FACTORS["healthcare_mental_health"][:4],
    *SCORING_FACTORS["housing_homelessness"],
    *SCORING_FACTORS["disability_ratings"],
    "gi bill",
    "survivor",
    "burial",
]

YELLOW_SIGNALS = [
    *SCORING_FACTORS["employment_education"],
    *SCORING_FACTORS["criminal_justice_courts"],
    "mental health",
    "military spouse",
]

GREEN_SIGNALS = [
    "recognition", "memorial", "honor", "honoring", "ceremonial", "commemorative",
    "designate", "memorial highway", "memorial day", "purple heart day",
    "resolution honoring", "honor resolution",
]

CO_BILL_RE = re.compile(r"^([A-Z]+)26-(\d+)$", re.IGNORECASE)
GENERIC_BILL_RE = re.compile(r"^([A-Z]+)\s*(\d+)$", re.IGNORECASE)

VETERAN_MARKERS = [
    "veteran", "veterans", "military", "armed forces", "national guard",
    "servicemember", "service member", "title 38", "gi bill",
]


def _might_be_veteran_related(text: str) -> bool:
    text_lower = (text or "").lower()
    return any(marker in text_lower for marker in VETERAN_MARKERS)


def normalize_co_csv_bill_number(bill_number: str) -> Tuple[str, str]:
    """
    Convert tracker bill numbers to lookup keys.

    HB26-1002 -> (HB26-1002, HB 1002)
    """
    raw = (bill_number or "").strip().upper()
    match = CO_BILL_RE.match(raw.replace(" ", ""))
    if match:
        prefix, num = match.group(1), match.group(2)
        slug = f"{prefix}26-{num}"
        norm = f"{prefix} {num}"
        return slug, norm
    generic = GENERIC_BILL_RE.match(raw)
    if generic:
        prefix, num = generic.group(1), generic.group(2)
        return f"{prefix}26-{num}", f"{prefix} {num}"
    return raw, raw


def build_bill_lookup_key(state: Optional[str], bill_number: str) -> str:
    """Stable lookup key for site_data veteran_impact map."""
    st = (state or "Federal").upper()
    num = (bill_number or "").strip().upper()
    if st == "CO":
        slug, _ = normalize_co_csv_bill_number(num)
        return f"{st}|{slug}"
    generic = GENERIC_BILL_RE.match(num.replace("-", " "))
    if generic:
        num = f"{generic.group(1)} {generic.group(2)}"
    return f"{st}|{num}"


def detect_scoring_factors(text: str) -> List[str]:
    """Return human-readable scoring factor labels matched in text."""
    text_lower = text.lower()
    labels = {
        "benefits_compensation": "Benefits & Compensation",
        "healthcare_mental_health": "Healthcare & Mental Health",
        "housing_homelessness": "Housing & Homelessness",
        "disability_ratings": "Disability Ratings",
        "employment_education": "Employment & Education",
        "criminal_justice_courts": "Criminal Justice / Courts",
    }
    matched: List[str] = []
    for key, keywords in SCORING_FACTORS.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(labels[key])
    return matched


def classify_veteran_impact(
    text: str,
    csv_level: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Classify veteran impact level from bill text.

    Returns None when the bill does not appear veteran-related.
    """
    if csv_level:
        level = csv_level.strip().lower()
        if level in IMPACT_LEVELS:
            factors = detect_scoring_factors(text)
            return {
                "level": level,
                "factors": factors,
                "source": "csv",
                "veteran_related": True,
            }

    text_lower = (text or "").lower()
    if not text_lower.strip():
        return None

    veteran_markers = [
        "veteran", "veterans", "military", "armed forces", "national guard",
        "servicemember", "service member", "title 38", "gi bill",
    ]
    if not any(marker in text_lower for marker in veteran_markers):
        if not any(kw in text_lower for kw in RED_SIGNALS + YELLOW_SIGNALS):
            return None

    factors = detect_scoring_factors(text)
    if any(kw in text_lower for kw in RED_SIGNALS):
        level = "red"
    elif any(kw in text_lower for kw in YELLOW_SIGNALS):
        level = "yellow"
    elif any(kw in text_lower for kw in GREEN_SIGNALS):
        level = "green"
    elif "veteran" in text_lower or "military" in text_lower:
        level = "green"
    else:
        return None

    return {
        "level": level,
        "factors": factors,
        "source": "rules",
        "veteran_related": True,
    }


def load_co_bills(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load Colorado tracker import payload."""
    file_path = path or CO_BILLS_FILE
    if not file_path.exists():
        return {"bills": {}, "_meta": {}}
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"bills": {}, "_meta": {}}
    return data


def build_veteran_impact_lookup(
    co_data: Optional[Dict[str, Any]] = None,
    normalized_bills: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build frontend lookup map keyed by state|bill_number.

    CO bills use CSV as source of truth; other states use keyword rules.
    """
    lookup: Dict[str, Dict[str, Any]] = {}

    co_payload = co_data if co_data is not None else load_co_bills()
    for slug, record in (co_payload.get("bills") or {}).items():
        if not isinstance(record, dict):
            continue
        level = (record.get("impact_level") or "").strip().lower()
        if level not in IMPACT_LEVELS and not record.get("veteran_related"):
            continue
        text = " ".join(
            str(record.get(field, "") or "")
            for field in ("title", "notes", "committee", "last_action")
        )
        classified = classify_veteran_impact(text, csv_level=level or None)
        if not classified and record.get("veteran_related"):
            classified = classify_veteran_impact(text)
        if not classified:
            continue

        entry = {
            **classified,
            "title": record.get("title", ""),
            "status": record.get("status", ""),
            "endorsement": record.get("endorsement", ""),
            "openstates_id": record.get("openstates_id", ""),
            "bill_number_csv": record.get("bill_number_csv", slug),
            "bill_number_norm": record.get("bill_number_norm", ""),
        }
        lookup[f"CO|{slug.upper()}"] = entry
        norm = record.get("bill_number_norm") or ""
        if norm:
            lookup[build_bill_lookup_key("CO", norm)] = entry

    if not normalized_bills:
        return lookup

    for bill in normalized_bills:
        state = bill.get("state")
        if not state or str(state).upper() == "CO":
            continue
        text = " ".join(
            str(bill.get(field, "") or "")
            for field in ("title", "summary", "latest_action")
        )
        if not _might_be_veteran_related(text):
            continue
        classified = classify_veteran_impact(text)
        if not classified:
            continue
        key = build_bill_lookup_key(state, bill.get("bill_number", ""))
        if key in lookup:
            continue
        lookup[key] = {
            **classified,
            "title": bill.get("title", ""),
            "bill_number_norm": bill.get("bill_number", ""),
        }

    # Federal bills from normalized data
    for bill in normalized_bills:
        if bill.get("level") != "federal" and bill.get("state"):
            continue
        text = " ".join(
            str(bill.get(field, "") or "")
            for field in ("title", "summary", "latest_action")
        )
        if not _might_be_veteran_related(text):
            continue
        classified = classify_veteran_impact(text)
        if not classified:
            continue
        key = build_bill_lookup_key(None, bill.get("bill_number", ""))
        if key in lookup:
            continue
        lookup[key] = {
            **classified,
            "title": bill.get("title", ""),
            "bill_number_norm": bill.get("bill_number", ""),
        }

    return lookup


def resolve_veteran_impact_for_item(
    item: Dict[str, Any],
    lookup: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve veteran impact metadata for a feed or search item."""
    if item.get("veteran_impact"):
        return item["veteran_impact"]

    state = item.get("state") or ""
    if not state:
        src = (item.get("source") or "").lower()
        if "congress" in src or "federal" in src:
            state = "Federal"
        elif "colorado" in src:
            state = "CO"
        elif "kansas" in src:
            state = "KS"

    bill_number = item.get("bill_number") or ""
    if not bill_number:
        title = item.get("title") or ""
        match = re.match(r"^([A-Za-z]+\s*\d+[A-Za-z]?)\s*:", title)
        if match:
            bill_number = match.group(1)

    if not bill_number:
        return None

    st = "Federal" if str(state).lower() in ("federal", "us", "") and (
        "congress" in (item.get("source") or "").lower()
        or item.get("level") == "federal"
    ) else str(state).upper()

    keys = [build_bill_lookup_key(st if st != "FEDERAL" else None, bill_number)]
    if st == "CO":
        slug, _ = normalize_co_csv_bill_number(bill_number)
        keys.append(f"CO|{slug.upper()}")

    for key in keys:
        hit = lookup.get(key)
        if hit:
            return hit

    text = " ".join(
        str(item.get(field, "") or "")
        for field in ("title", "summary", "latest_action", "short_title")
    )
    return classify_veteran_impact(text)
