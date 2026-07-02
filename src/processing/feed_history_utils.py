"""Shared helpers for merging feed items into history.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parents[2]
HISTORY_FILE = ROOT / "src" / "output" / "history.json"


def load_history() -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history: List[Dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def merge_with_history(new_items: List[Dict]) -> List[Dict]:
    """Append feed items to history, deduplicating by id and link."""
    history = load_history()
    initial_count = len(history)
    existing: Set[str] = set()
    for item in history:
        if item.get("id"):
            existing.add(str(item["id"]))
        if item.get("link"):
            existing.add(str(item["link"]))

    added = 0
    for item in new_items:
        item_id = str(item.get("id") or "")
        item_link = str(item.get("link") or "")
        if item_id and item_id in existing:
            continue
        if item_link and item_link in existing:
            continue
        history.append(item)
        if item_id:
            existing.add(item_id)
        if item_link:
            existing.add(item_link)
        added += 1

    if initial_count > 0 and len(history) < initial_count:
        raise ValueError(f"History preservation failed: lost {initial_count - len(history)} items")

    print(f"Added {added} new feed items to history (total: {len(history)})")
    return history
