"""Build slim legislators directory so legislators.html need not load site_data.json.

The directory page only needs filterable card fields plus legislator_stats for the
Stats tab. Photos/images and other bulky person fields are omitted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

LEGISLATORS_DIRECTORY_FILENAME = "legislators_directory.json"

# Fields used by renderLegislatorCard / vote modal open — not images.
_SLIM_KEYS = ("id", "name", "party", "state", "chamber", "district", "url")


def slim_legislator(leg: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only directory-card fields from a search_index legislator row."""
    return {key: leg.get(key) or "" for key in _SLIM_KEYS}


def build_slim_legislators(
    search_index: Optional[Dict[str, Any]] = None,
    *,
    legislators: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Compact legislator rows for the directory page."""
    source = list(legislators) if legislators is not None else list(
        (search_index or {}).get("legislators") or []
    )
    return [slim_legislator(leg) for leg in source if isinstance(leg, dict)]


def build_legislators_directory(
    *,
    search_index: Optional[Dict[str, Any]] = None,
    legislators: Optional[Sequence[Dict[str, Any]]] = None,
    legislator_stats: Optional[Dict[str, Any]] = None,
    states: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the legislators page JSON payload (no full site_data / search_index)."""
    slim = build_slim_legislators(search_index, legislators=legislators)
    return {
        "legislators_directory": True,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "states": list(states or []),
        "legislators": slim,
        "legislator_stats": legislator_stats if isinstance(legislator_stats, dict) else {},
        "stats": {
            "legislator_count": len(slim),
        },
    }


def write_legislators_directory(
    docs_dir: str | Path,
    payload: Dict[str, Any],
) -> Path:
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    out = docs / LEGISLATORS_DIRECTORY_FILENAME
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return out


def write_legislators_directory_artifacts(
    docs_dir: str | Path,
    *,
    search_index: Optional[Dict[str, Any]] = None,
    legislators: Optional[Sequence[Dict[str, Any]]] = None,
    legislator_stats: Optional[Dict[str, Any]] = None,
    states: Optional[List[Dict[str, Any]]] = None,
    generated_at: Optional[str] = None,
) -> tuple[Path, Dict[str, Any]]:
    """Write docs/legislators_directory.json and return (path, payload)."""
    payload = build_legislators_directory(
        search_index=search_index,
        legislators=legislators,
        legislator_stats=legislator_stats,
        states=states,
        generated_at=generated_at,
    )
    path = write_legislators_directory(docs_dir, payload)
    return path, payload
