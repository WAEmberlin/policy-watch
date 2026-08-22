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
# Color rows (Colorado tracker):
#   RED — benefits, disability ratings, VA healthcare, MST/IPV/suicide,
#         housing, survivor/burial, GI Bill, retroactive veteran benefits
#   YELLOW — employment preference, licensing, courts & diversion, generic mental health, military spouse
#   GREEN — recognition, memorials, honor resolutions, VA committee referrals
#           with no higher-impact keyword (default for veteran-related unmatched bills)
#
# Ambiguous terms (pension, diversion, honor, etc.) are CONTEXT-GATED: they only
# contribute to red/yellow/green after a veteran-related signal is established.
# Inherently veteran phrases (gi bill, veterans court, va health, …) always count.
SCORING_FACTORS: Dict[str, List[str]] = {
    "benefits_compensation": [
        "gi bill", "survivor benefit", "burial benefit", "va benefit", "veterans benefit",
        "veteran pension", "veterans pension", "veteran compensation", "veterans compensation",
        "dependency indemnity", "title 38",
        # Gated when used alone — require veteran context first:
        "compensation", "pension",
        "retroactive payment", "retroactive benefit", "retroactive benefits",
        "retroactive compensation",
    ],
    "healthcare_mental_health": [
        # VA clinical / veteran-specific conditions → RED; generic mental health → YELLOW.
        "va health", "veterans health", "va healthcare", "veterans healthcare",
        "military sexual trauma",
        # Gated clinical / mental-health terms:
        "ptsd", "tbi", "suicide prevention", "post-traumatic", "mental health",
    "sexual trauma", "intimate partner violence", "domestic violence",
    "suicidal ideation", "suicide",
    "retroactive payment", "retroactive benefit", "retroactive benefits",
    "retroactive compensation",
        "sexual trauma", "intimate partner violence", "domestic violence",
        "suicidal ideation", "suicide",
    ],
    "housing_homelessness": [
        "veteran housing", "homeless veteran", "shelter veteran",
        # Gated:
        "housing voucher",
    ],
    "disability_ratings": [
        "service-connected", "service connected",
        # Gated:
        "disability rating", "rating schedule",
    ],
    "employment_education": [
        "veteran preference", "veterans preference",
        "veteran hiring preference", "veterans hiring preference",
        "veteran employment preference", "veterans employment preference",
        "military spouse",
        # Gated:
        "hiring preference", "employment preference",
        "licensing", "certification", "apprenticeship",
    ],
    "criminal_justice_courts": [
        "veterans court", "veteran court",
        "veterans treatment court", "veteran treatment court",
        "veterans justice",
        # Gated:
        "diversion", "treatment court", "justice outreach",
    ],
    "appropriations_funding": [
        "take care of america",
        "military construction, veterans affairs",
        "military construction and veterans affairs",
        "veterans affairs appropriations",
        "va appropriations",
        "milcon-va",
        "appropriations for the department of veterans affairs",
        "appropriations for veterans affairs",
    ],
}

# Ambiguous color keywords — must NOT establish veteran-relatedness by themselves.
CONTEXT_GATED_KEYWORDS = frozenset({
    "compensation", "pension", "housing voucher",
    "disability rating", "rating schedule", "survivor", "burial",
    "ptsd", "tbi", "suicide prevention", "post-traumatic", "mental health",
    "sexual trauma", "intimate partner violence", "domestic violence",
    "suicidal ideation", "suicide",
    "retroactive payment", "retroactive benefit", "retroactive benefits",
    "retroactive compensation",
    "hiring preference", "employment preference",
    "licensing", "certification", "apprenticeship",
    "diversion", "treatment court", "justice outreach",
    "recognition", "memorial", "honor", "honoring", "ceremonial", "commemorative",
    "designate", "memorial highway", "memorial day",
    "resolution honoring", "honor resolution",
})

# Veteran-specific clinical / VA healthcare signals (RED). Generic "mental health" stays YELLOW.
# Bare "veterans affairs" is not red — committee referrals should color the card
# (default green) unless a more specific high-impact keyword matches.
RED_HEALTHCARE_SIGNALS = [
    "va health", "veterans health", "va healthcare", "veterans healthcare",
    "military sexual trauma",
    "ptsd", "tbi", "suicide prevention", "post-traumatic",
    "sexual trauma", "intimate partner violence", "domestic violence",
    "suicidal ideation", "suicide",
]

RED_SIGNALS = [
    *SCORING_FACTORS["benefits_compensation"],
    *RED_HEALTHCARE_SIGNALS,
    *SCORING_FACTORS["housing_homelessness"],
    *SCORING_FACTORS["disability_ratings"],
    *SCORING_FACTORS["appropriations_funding"],
    "survivor",
    "burial",
]

YELLOW_SIGNALS = [
    *SCORING_FACTORS["employment_education"],
    *SCORING_FACTORS["criminal_justice_courts"],
    "mental health",
]

GREEN_SIGNALS = [
    "recognition", "memorial", "honor", "honoring", "ceremonial", "commemorative",
    "designate", "memorial highway", "memorial day", "purple heart day",
    "resolution honoring", "honor resolution",
]

# Phrases that are inherently veteran/military (establish relatedness without generic terms).
INHERENT_VETERAN_SIGNALS = [
    kw for kw in (RED_SIGNALS + YELLOW_SIGNALS + GREEN_SIGNALS)
    if kw not in CONTEXT_GATED_KEYWORDS
]

VA_FACILITY_TYPES = (
    "community-based outpatient clinic",
    "outpatient clinic",
    "multispecialty clinic",
    "va clinic",
    "veterans affairs clinic",
    "va medical center",
    "veterans affairs medical center",
    "veterans affairs multispecialty clinic",
)
VA_FACILITY_NAMING_RES = (
    re.compile(
        rf"\b(to\s+)?(designate|name|rename|redesignate)\b.{{0,160}}\b({'|'.join(map(re.escape, VA_FACILITY_TYPES))})\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bcommunity-based outpatient clinic\b.{0,120}\bas the\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bdepartment of veterans affairs\b.{0,160}\bclinic\b.{0,120}\bas the\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

CO_BILL_RE = re.compile(r"^([A-Z]+)26-(\d+)$", re.IGNORECASE)
GENERIC_BILL_RE = re.compile(r"^([A-Z]+)\s*(\d+)$", re.IGNORECASE)

VETERAN_MARKERS = [
    "veteran", "veterans", "military", "armed forces", "national guard",
    "servicemember", "service member", "title 38", "gi bill",
    "va health", "va healthcare", "va benefit", "va clinic", "va medical",
    "va appropriations", "milcon-va",
    "military sexual trauma",
    "committee on veterans", "veterans' affairs committee",
    "veterans affairs committee", "veterans and military affairs",
    "military and veterans affairs", "military affairs and veterans",
]

VETERAN_TAG_PATTERN = re.compile(
    r"veteran|veterans|military|armed forces|national guard|servicemember|service member",
    re.IGNORECASE,
)

BILL_TEXT_FIELDS = (
    "title", "summary", "latest_action", "short_title", "official_title",
    "notes", "committee", "committees", "last_action",
)


def _flatten_text_value(value: Any) -> str:
    """Join committee lists/dicts and other nested fields into searchable text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(
            str(value.get(key) or "")
            for key in ("name", "committee", "title", "text")
            if value.get(key)
        )
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text_value(part) for part in value)
    return str(value)


def _item_has_veteran_tagging(item: Optional[Dict[str, Any]]) -> bool:
    if not item:
        return False
    if item.get("veteran_related") is True:
        return True
    for field in ("ai_topics", "classification", "topics"):
        for tag in item.get(field) or []:
            if VETERAN_TAG_PATTERN.search(str(tag)):
                return True
    return False


def _bill_text_from_record(record: Dict[str, Any]) -> str:
    return " ".join(
        _flatten_text_value(record.get(field)) for field in BILL_TEXT_FIELDS
    )


def _text_has_veteran_context(text_lower: str) -> bool:
    """True when text has a real veteran/military signal (not a gated generic term)."""
    if not text_lower.strip():
        return False
    if any(marker in text_lower for marker in VETERAN_MARKERS):
        return True
    if any(kw in text_lower for kw in INHERENT_VETERAN_SIGNALS):
        return True
    return is_va_facility_naming(text_lower)


def _might_be_veteran_related(text: str, item: Optional[Dict[str, Any]] = None) -> bool:
    if _item_has_veteran_tagging(item):
        return True
    return _text_has_veteran_context((text or "").lower())


def infer_item_state(item: Dict[str, Any]) -> str:
    """Infer state code or 'Federal' from a feed or bill record."""
    if item.get("level") == "federal":
        return "Federal"
    if item.get("state"):
        return str(item["state"]).upper()
    src = (item.get("source") or "").lower()
    if any(token in src for token in ("congress", "federal", "u.s.")):
        return "Federal"
    for code, name in (
        ("KS", "kansas"), ("CO", "colorado"), ("AZ", "arizona"),
        ("UT", "utah"), ("ME", "maine"), ("NE", "nebraska"), ("MD", "maryland"),
        ("PA", "pennsylvania"), ("MA", "massachusetts"), ("WV", "west virginia"),
        ("TN", "tennessee"), ("NC", "north carolina"), ("MO", "missouri"),
        ("IA", "iowa"),
    ):
        if name in src:
            return code
    return ""


def _extract_bill_number(record: Dict[str, Any]) -> str:
    bill_number = (record.get("bill_number") or "").strip()
    if bill_number and re.search(r"\d", bill_number):
        return bill_number
    bill_type = (record.get("bill_type") or "").strip()
    bill_num = str(record.get("number") or bill_number or "").strip()
    if bill_type and bill_num:
        combined = f"{bill_type} {bill_num}".strip()
        if re.search(r"\d", combined):
            return combined
    title = record.get("title") or ""
    match = re.match(r"^([A-Za-z]+\s*\d+[A-Za-z]?)\s*:", title)
    if match:
        return match.group(1).strip()
    return bill_num


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


def is_va_facility_naming(text: str) -> bool:
    """True when the bill only names or renames a VA clinic/outpatient center."""
    hay = (text or "").lower()
    if not hay.strip():
        return False
    return any(pattern.search(hay) for pattern in VA_FACILITY_NAMING_RES)


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
        "appropriations_funding": "Appropriations & Funding",
    }
    matched: List[str] = []
    for key, keywords in SCORING_FACTORS.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(labels[key])
    return matched


def _matched_keywords(text_lower: str, keywords: List[str], limit: int = 5) -> List[str]:
    """Return unique keywords from *keywords* that appear in *text_lower*."""
    matched: List[str] = []
    for kw in keywords:
        if kw in text_lower and kw not in matched:
            matched.append(kw)
            if len(matched) >= limit:
                break
    return matched


_LEVEL_LABELS = {
    "red": "red (high impact)",
    "yellow": "yellow (moderate impact)",
    "green": "green (ceremonial / general)",
}


def build_impact_reason(
    level: str,
    *,
    source: str = "rules",
    factors: Optional[List[str]] = None,
    matched_keywords: Optional[List[str]] = None,
    special: Optional[str] = None,
) -> str:
    """Build a human-readable explanation for an impact classification."""
    label = _LEVEL_LABELS.get(level, level)
    factors = factors or []
    matched_keywords = matched_keywords or []

    if source == "csv":
        parts = [f"Impact level set from Colorado veteran tracker (CSV) as {label}."]
        if factors:
            parts.append(f"Matched topics: {', '.join(factors)}.")
        return " ".join(parts)

    if special == "facility_naming":
        return (
            "Classified green because this bill names or renames a VA clinic "
            "or outpatient facility."
        )

    if special == "veteran_marker":
        marker_note = ""
        if matched_keywords:
            marker_note = f" Matched markers: {', '.join(matched_keywords)}."
        return (
            f"Classified {label} as veteran-related without high or moderate "
            f"impact keyword signals.{marker_note}"
        )

    sentence = f"Classified {label}"
    if matched_keywords:
        sentence += f" based on matched keywords: {', '.join(matched_keywords)}"
    sentence += "."
    if factors:
        sentence += f" Scoring factors: {', '.join(factors)}."
    return sentence


def classify_veteran_impact(
    text: str,
    csv_level: Optional[str] = None,
    *,
    has_veteran_tagging: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Classify veteran impact level from bill text.

    Gate: require a veteran-related signal (markers, inherent phrases, VA facility
    naming, or AI/topic tagging) before applying red/yellow/green keywords.
    Context-gated generics (pension, diversion, honor, …) never establish relatedness alone.

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
                "reason": build_impact_reason(level, source="csv", factors=factors),
            }

    text_lower = (text or "").lower()
    if not text_lower.strip():
        return None

    # Step 1: veteran-relatedness gate (markers / inherent phrases / tagging).
    if not has_veteran_tagging and not _text_has_veteran_context(text_lower):
        return None

    if is_va_facility_naming(text_lower):
        factors = ["Facility Naming"]
        return {
            "level": "green",
            "factors": factors,
            "source": "rules",
            "veteran_related": True,
            "reason": build_impact_reason(
                "green", factors=factors, special="facility_naming",
            ),
        }

    # Step 2: color scoring (inherent + context-gated keywords).
    factors = detect_scoring_factors(text)
    matched_red = _matched_keywords(text_lower, RED_SIGNALS)
    matched_yellow = _matched_keywords(text_lower, YELLOW_SIGNALS)
    matched_green = _matched_keywords(text_lower, GREEN_SIGNALS)
    matched_markers = _matched_keywords(text_lower, VETERAN_MARKERS)

    if matched_red:
        level, matched, special = "red", matched_red, None
    elif matched_yellow:
        level, matched, special = "yellow", matched_yellow, None
    elif matched_green:
        level, matched, special = "green", matched_green, None
    elif matched_markers or has_veteran_tagging:
        level, matched, special = "green", matched_markers, "veteran_marker"
    else:
        return None

    return {
        "level": level,
        "factors": factors,
        "source": "rules",
        "veteran_related": True,
        "reason": build_impact_reason(
            level,
            factors=factors,
            matched_keywords=matched,
            special=special,
        ),
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


def _bill_recency(record: Dict[str, Any]) -> str:
    """ISO-ish date string for comparing bill freshness (lexicographic)."""
    return str(
        record.get("latest_action_date")
        or record.get("updated_at")
        or record.get("published")
        or ""
    )


def _normalize_impact_title(title: str) -> str:
    """Normalize titles for cross-session lookup comparison."""
    text = re.sub(r"\s+", " ", str(title or "").strip().lower())
    text = re.sub(r"^(?:[a-z]+\s*\d+[a-z]?\s*:\s*)", "", text)
    return text.strip(" .:;-")


def lookup_entry_matches_item(
    entry: Optional[Dict[str, Any]],
    item: Dict[str, Any],
) -> bool:
    """
    True when a lookup entry is about the same bill text as *item*.

    Bill numbers reuse across sessions (e.g. MA H 2463), so title must agree
    before trusting a cached impact level.
    """
    if not entry:
        return False
    entry_title = _normalize_impact_title(entry.get("title") or "")
    item_title = _normalize_impact_title(
        item.get("title") or item.get("short_title") or ""
    )
    if not entry_title or not item_title:
        return False
    return (
        entry_title == item_title
        or entry_title in item_title
        or item_title in entry_title
    )


def _lookup_keys_for_bill(state: Optional[str], bill_number: str) -> List[str]:
    if not bill_number:
        return []
    st = str(state or "Federal").upper()
    lookup_state = None if st == "FEDERAL" else st
    keys = [build_bill_lookup_key(lookup_state, bill_number)]
    if st == "CO":
        slug, _ = normalize_co_csv_bill_number(bill_number)
        keys.append(f"CO|{slug.upper()}")
    return [key for key in keys if key]


def _store_lookup_entry(
    lookup: Dict[str, Dict[str, Any]],
    recency_by_key: Dict[str, str],
    state: Optional[str],
    bill_number: str,
    entry: Optional[Dict[str, Any]],
    recency: str = "",
) -> None:
    """
    Store or clear lookup entries for a bill number.

    Newer bills win for reused numbers. A newer non-veteran bill clears a stale
    older veteran classification for the same state|number key.
    """
    for key in _lookup_keys_for_bill(state, bill_number):
        existing_recency = recency_by_key.get(key, "")
        if key in recency_by_key and recency < existing_recency:
            continue
        # Always advance recency so an older bill cannot overwrite a newer one,
        # even when the newer bill is not veteran-related (no lookup entry).
        recency_by_key[key] = recency
        if entry:
            lookup[key] = entry
        elif key in lookup:
            del lookup[key]


def _classify_bill_record(
    record: Dict[str, Any],
    csv_level: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    text = _bill_text_from_record(record)
    if not _might_be_veteran_related(text, record):
        return None
    return classify_veteran_impact(
        text,
        csv_level=csv_level,
        has_veteran_tagging=_item_has_veteran_tagging(record),
    )


def collect_feed_bills_for_veteran_lookup(
    history_items: Optional[List[Dict[str, Any]]] = None,
    legislation_items: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Collect bill-like feed records for veteran impact classification."""
    seen: set = set()
    feed_bills: List[Dict[str, Any]] = []

    def add_item(item: Dict[str, Any]) -> None:
        bill_number = _extract_bill_number(item)
        if not bill_number:
            return
        dedup_key = (
            (item.get("state") or item.get("source") or ""),
            bill_number.upper(),
            item.get("link") or item.get("url") or "",
        )
        if dedup_key in seen:
            return
        seen.add(dedup_key)
        feed_bills.append(item)

    for item in history_items or []:
        if item.get("feed") == "conference_committees":
            continue
        add_item(item)

    for bill in legislation_items or []:
        add_item({
            **bill,
            "bill_number": f"{bill.get('bill_type', '')} {bill.get('bill_number', '')}".strip(),
            "source": "Congress.gov API",
            "level": "federal",
        })

    return feed_bills


def build_veteran_impact_lookup(
    co_data: Optional[Dict[str, Any]] = None,
    normalized_bills: Optional[List[Dict[str, Any]]] = None,
    feed_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Build frontend lookup map keyed by state|bill_number.

    CO bills use CSV as source of truth; other states and federal use keyword rules.
    When the same bill number appears in multiple sessions, the newest record wins;
    a newer non-veteran bill clears a stale older classification.
    """
    lookup: Dict[str, Dict[str, Any]] = {}
    recency_by_key: Dict[str, str] = {}

    co_payload = co_data if co_data is not None else load_co_bills()
    for slug, record in (co_payload.get("bills") or {}).items():
        if not isinstance(record, dict):
            continue
        level = (record.get("impact_level") or "").strip().lower()
        if level not in IMPACT_LEVELS and not record.get("veteran_related"):
            continue
        classified = _classify_bill_record(record, csv_level=level or None)
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
        recency_by_key[f"CO|{slug.upper()}"] = _bill_recency(record)
        norm = record.get("bill_number_norm") or ""
        if norm:
            _store_lookup_entry(
                lookup, recency_by_key, "CO", norm, entry, _bill_recency(record),
            )

    for bill in (normalized_bills or []) + (feed_items or []):
        state = infer_item_state(bill)
        bill_number = _extract_bill_number(bill)
        if not bill_number:
            continue
        if state == "CO":
            continue

        is_federal = (
            bill.get("level") == "federal"
            or state == "Federal"
            or (not bill.get("state") and state == "Federal")
        )
        if not is_federal and not state:
            continue

        classified = _classify_bill_record(bill)
        entry = None
        if classified:
            entry = {
                **classified,
                "title": bill.get("title", "") or bill.get("short_title", ""),
                "bill_number_norm": bill_number,
            }
        lookup_state = None if is_federal else state
        _store_lookup_entry(
            lookup,
            recency_by_key,
            lookup_state,
            bill_number,
            entry,
            _bill_recency(bill),
        )

    return lookup


def resolve_veteran_impact_for_item(
    item: Dict[str, Any],
    lookup: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Resolve veteran impact metadata for a feed or search item."""
    if item.get("veteran_impact"):
        return item["veteran_impact"]

    state = infer_item_state(item)
    bill_number = _extract_bill_number(item)
    tagged = _item_has_veteran_tagging(item)
    text = _bill_text_from_record(item)

    if bill_number:
        is_federal = state == "Federal" or item.get("level") == "federal"
        keys = _lookup_keys_for_bill(None if is_federal else state, bill_number)
        for key in keys:
            hit = lookup.get(key)
            if hit and lookup_entry_matches_item(hit, item):
                if hit.get("source") == "csv":
                    return hit
                rescored = classify_veteran_impact(text, has_veteran_tagging=tagged)
                return rescored or hit

    # Lookup miss or cross-session collision: re-score from this item's text.
    return classify_veteran_impact(text, has_veteran_tagging=tagged)
