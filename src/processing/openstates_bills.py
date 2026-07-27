"""Load/save Open States bill caches with optional per-session file splitting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Stay under GitHub's 50 MB advisory limit (pretty-printed JSON).
MAX_MONOLITHIC_BYTES = 45 * 1024 * 1024
SESSION_FILE_RE = re.compile(r"^bills_(.+)\.json$")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def session_slug(session: Any) -> str:
    text = str(session or "unknown").strip()
    return text.replace("/", "-").replace("\\", "-")


def session_bill_paths(state_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in state_dir.glob("bills_*.json")
        if SESSION_FILE_RE.match(path.name)
    )


def uses_session_split(state_dir: Path) -> bool:
    return bool(session_bill_paths(state_dir))


def load_state_bills(state_dir: Path) -> List[Dict[str, Any]]:
    """Load bills from bills.json and/or bills_{session}.json (deduped by id)."""
    index: Dict[str, Dict[str, Any]] = {}

    legacy = state_dir / "bills.json"
    if legacy.exists():
        for bill in load_json(legacy, []):
            bill_id = bill.get("id")
            if bill_id:
                index[bill_id] = bill

    for path in session_bill_paths(state_dir):
        for bill in load_json(path, []):
            bill_id = bill.get("id")
            if bill_id:
                index[bill_id] = bill

    return list(index.values())


def _serialized_size(bills: List[Dict[str, Any]]) -> int:
    return len(json.dumps(bills, indent=2, ensure_ascii=False).encode("utf-8"))


def _group_by_session(bills: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for bill in bills:
        key = session_slug(bill.get("legislative_session"))
        grouped.setdefault(key, []).append(bill)
    return grouped


def _remove_legacy_monolith(state_dir: Path) -> None:
    legacy = state_dir / "bills.json"
    if legacy.exists():
        legacy.unlink()


def _remove_stale_session_files(state_dir: Path, keep: set[str]) -> None:
    for path in session_bill_paths(state_dir):
        if path.name not in keep:
            path.unlink()


def save_state_bills(state_dir: Path, bills: List[Dict[str, Any]]) -> List[str]:
    """
    Persist bills to state_dir.

    Uses a single bills.json when small enough; otherwise bills_{session}.json
    files so each chunk stays within GitHub size limits.

    Avoid json.dumps()-probing the full bill list when the cache is already
    session-split or clearly large — that doubles peak memory and OOMs CI
    runners for AZ/ME/NE/MD-sized datasets.
    """
    state_dir.mkdir(parents=True, exist_ok=True)

    # Prefer session files when already split or bill count is large enough that
    # a monolithic dump is unlikely to stay under GitHub's size limits.
    use_sessions = uses_session_split(state_dir) or len(bills) >= 3000
    if not use_sessions and _serialized_size(bills) <= MAX_MONOLITHIC_BYTES:
        save_json(state_dir / "bills.json", bills)
        for path in session_bill_paths(state_dir):
            path.unlink()
        return ["bills.json"]

    grouped = _group_by_session(bills)
    saved_names: set[str] = set()
    _remove_legacy_monolith(state_dir)

    for session in sorted(grouped):
        filename = f"bills_{session}.json"
        save_json(state_dir / filename, grouped[session])
        saved_names.add(filename)

    _remove_stale_session_files(state_dir, saved_names)
    return sorted(saved_names)


def state_bill_count(state_dir: Path) -> int:
    return len(load_state_bills(state_dir))
