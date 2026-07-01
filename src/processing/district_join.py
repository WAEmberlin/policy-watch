"""Join Census district GeoJSON features to normalized legislators."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

HOUSE_CHAMBERS = frozenset(
    {"representative", "lower", "house", "state representative", "state rep", "rep"}
)
SENATE_CHAMBERS = frozenset({"senator", "upper", "senate", "state senator", "sen"})


def normalize_chamber(chamber: Optional[str]) -> str:
    """Return 'house', 'senate', or a lowercased raw chamber label."""
    raw = (chamber or "").strip().lower().replace("_", " ")
    if raw in HOUSE_CHAMBERS:
        return "house"
    if raw in SENATE_CHAMBERS:
        return "senate"
    return raw


def normalize_district(district: Any) -> str:
    """Strip leading zeros from numeric district identifiers."""
    if district is None:
        return ""
    text = str(district).strip()
    if not text:
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def extract_district_from_feature(
    properties: Dict[str, Any],
    *,
    layer: str = "house",
) -> str:
    """Map Census properties to a legislator district key for the given layer."""
    props = properties or {}
    layer_key = (layer or "house").lower()

    if layer_key in ("congress", "cd", "cd119"):
        for key in ("BASENAME", "CD119", "DISTRICT"):
            value = props.get(key)
            if value not in (None, ""):
                return normalize_district(value)
        geoid = str(props.get("GEOID") or "")
        if len(geoid) >= 2 and geoid[-2:].isdigit():
            return normalize_district(geoid[-2:])
        return ""

    if layer_key in ("senate", "upper", "sldu"):
        for key in ("BASENAME", "SLDU", "DISTRICT", "SLDUST"):
            value = props.get(key)
            if value not in (None, ""):
                return normalize_district(value)
        geoid = str(props.get("GEOID") or "")
        if len(geoid) >= 2 and geoid[-2:].isdigit():
            return normalize_district(geoid[-2:])
        return ""

    for key in ("BASENAME", "SLDL", "DISTRICT", "SLDLST"):
        value = props.get(key)
        if value not in (None, ""):
            return normalize_district(value)
    geoid = str(props.get("GEOID") or "")
    if len(geoid) >= 3 and geoid[-3:].isdigit():
        return normalize_district(geoid[-3:])
    return ""


def is_house_legislator(legislator: Dict[str, Any], state: str = "KS") -> bool:
    if (legislator.get("state") or "").upper() != state.upper():
        return False
    return normalize_chamber(legislator.get("chamber")) == "house"


def build_district_legislator_index(
    legislators: List[Dict[str, Any]],
    *,
    state: str = "KS",
    chamber: str = "house",
) -> Dict[str, List[Dict[str, Any]]]:
    """Index legislators by normalized district number for a state/chamber."""
    target_chamber = normalize_chamber(chamber)
    index: Dict[str, List[Dict[str, Any]]] = {}
    for leg in legislators:
        if (leg.get("state") or "").upper() != state.upper():
            continue
        if normalize_chamber(leg.get("chamber")) != target_chamber:
            continue
        district = normalize_district(leg.get("district"))
        if not district:
            continue
        index.setdefault(district, []).append(leg)
    return index


def build_congressional_index(
    delegation: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Index U.S. House members by district from federal delegation payload."""
    index: Dict[str, List[Dict[str, Any]]] = {}
    for rep in delegation.get("representatives") or []:
        district = normalize_district(rep.get("district"))
        if not district:
            continue
        index.setdefault(district, []).append(rep)
    return index


def lookup_legislators_for_feature(
    properties: Dict[str, Any],
    index: Dict[str, List[Dict[str, Any]]],
    *,
    layer: str = "house",
) -> List[Dict[str, Any]]:
    """Return legislators matching a GeoJSON feature's district properties."""
    district = extract_district_from_feature(properties, layer=layer)
    if not district:
        return []
    return list(index.get(district, []))
