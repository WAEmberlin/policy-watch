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
_ROOT = Path(__file__).resolve().parents[2]
_STATES_YAML = _ROOT / "config" / "states.yaml"

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


def load_enabled_states(
    config_path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Return enabled [{code, name}, ...] from config/states.yaml (stable order)."""
    path = Path(config_path) if config_path else _STATES_YAML
    if not path.is_file():
        return []
    try:
        import yaml
    except ImportError:
        return []
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    out: List[Dict[str, str]] = []
    for row in cfg.get("states") or []:
        if not isinstance(row, dict) or not row.get("enabled"):
            continue
        code = (row.get("code") or "").strip().lower()
        if not code:
            continue
        out.append({"code": code, "name": str(row.get("name") or code.upper())})
    return out


def resolve_directory_states(
    states: Optional[Sequence[Dict[str, Any]]] = None,
    legislators: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    config_path: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """States for the legislators dropdown: enabled jurisdictions that have rows.

    Prefer config/states.yaml over stale site_data.states. Keep yaml order, then
    append any unexpected legislator.state values not listed in config.
    """
    present = {
        str(leg.get("state") or "").strip().upper()
        for leg in (legislators or [])
        if isinstance(leg, dict)
    }
    present.discard("")
    present.discard("FEDERAL")

    enabled = [
        {"code": str(s.get("code") or "").strip().lower(), "name": str(s.get("name") or "")}
        for s in (states or [])
        if isinstance(s, dict) and (s.get("code") or "").strip()
    ]
    # site_data.states is often months behind states.yaml — always prefer yaml when present.
    from_yaml = load_enabled_states(config_path)
    if from_yaml:
        enabled = from_yaml

    resolved: List[Dict[str, str]] = []
    seen: set[str] = set()
    for row in enabled:
        code_u = row["code"].upper()
        if present and code_u not in present:
            continue
        if code_u in seen:
            continue
        seen.add(code_u)
        resolved.append({"code": row["code"], "name": row["name"] or code_u})

    for code_u in sorted(present - seen):
        resolved.append({"code": code_u.lower(), "name": code_u})
    return resolved


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
    resolved_states = resolve_directory_states(states, slim)
    return {
        "legislators_directory": True,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "states": resolved_states,
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
