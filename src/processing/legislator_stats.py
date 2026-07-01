"""Aggregate legislator demographics for dashboard display."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional


def _parse_birth_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _age_bucket(age: Optional[int]) -> str:
    if age is None:
        return "unknown"
    if age < 40:
        return "under_40"
    if age < 60:
        return "40_59"
    return "60_plus"


def _normalize_party(party: str) -> str:
    if not party:
        return "Unknown"
    lower = party.lower()
    if "democrat" in lower:
        return "Democratic"
    if "republican" in lower:
        return "Republican"
    if "independent" in lower or lower in {"i", "ind", "unaffiliated"}:
        return "Independent"
    if "libertarian" in lower:
        return "Libertarian"
    if "green" in lower:
        return "Green"
    return party.strip() or "Unknown"


def _normalize_chamber(chamber: str) -> str:
    if not chamber:
        return "Unknown"
    lower = chamber.lower()
    if lower in {"lower", "house", "h", "assembly"}:
        return "House"
    if lower in {"upper", "senate", "s"}:
        return "Senate"
    return chamber.strip() or "Unknown"


def build_legislator_stats(legislators: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build per-state demographic summaries from normalized legislator records."""
    by_state: Dict[str, Dict[str, Any]] = {}
    today = date.today()

    for leg in legislators:
        state = (leg.get("state") or "Unknown").upper()
        bucket = by_state.setdefault(
            state,
            {
                "total": 0,
                "party": {},
                "gender": {},
                "chamber": {},
                "age_buckets": {"under_40": 0, "40_59": 0, "60_plus": 0, "unknown": 0},
                "ages_known": 0,
                "age_sum": 0,
            },
        )
        bucket["total"] += 1

        party = _normalize_party(leg.get("party") or "")
        bucket["party"][party] = bucket["party"].get(party, 0) + 1

        gender = (leg.get("gender") or "Unknown").strip() or "Unknown"
        bucket["gender"][gender] = bucket["gender"].get(gender, 0) + 1

        chamber = _normalize_chamber(leg.get("chamber") or "")
        bucket["chamber"][chamber] = bucket["chamber"].get(chamber, 0) + 1

        birth = _parse_birth_date(leg.get("birth_date") or "")
        if birth:
            age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            bucket["ages_known"] += 1
            bucket["age_sum"] += age
            bucket["age_buckets"][_age_bucket(age)] += 1
        else:
            bucket["age_buckets"]["unknown"] += 1

    for state, bucket in by_state.items():
        known = bucket.pop("ages_known", 0)
        age_sum = bucket.pop("age_sum", 0)
        bucket["average_age"] = round(age_sum / known, 1) if known else None
        bucket["race_available"] = False

    return {
        "by_state": dict(sorted(by_state.items())),
        "data_notes": {
            "race": "Race and ethnicity are not included in Open States bulk legislator data for these states.",
            "age": "Average age and age ranges are computed from birth_date when provided.",
            "federal": "Congress members are not yet in the normalized legislator dataset.",
        },
    }
