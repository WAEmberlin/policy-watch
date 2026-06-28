"""Kansas Legislature RSS adapter — preserves existing history.json schema."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .base import LegislativeSource, NormalizedBill, NormalizedEvent

OUTPUT_DIR = "src/output"
HISTORY_FILE = os.path.join(OUTPUT_DIR, "history.json")


class KansasRSSSource(LegislativeSource):
    source_name = "kansas_rss"

    def __init__(self, history_path: str = HISTORY_FILE) -> None:
        self.history_path = history_path

    def _load_history(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.history_path):
            return []
        with open(self.history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def fetch_bills(self) -> List[Dict[str, Any]]:
        return [
            item for item in self._load_history()
            if item.get("type") == "state_legislation"
            and item.get("state") == "KS"
            and item.get("feed") != "conference_committees"
        ]

    def fetch_events(self) -> List[Dict[str, Any]]:
        return [
            item for item in self._load_history()
            if item.get("type") == "state_legislation"
            and item.get("state") == "KS"
            and item.get("feed") == "conference_committees"
        ]

    def normalize_bills(self, raw_bills: List[Dict[str, Any]]) -> List[NormalizedBill]:
        normalized: List[NormalizedBill] = []
        for item in raw_bills:
            bill_number = item.get("bill_number", "")
            chamber = ""
            if bill_number.upper().startswith("HB") or bill_number.upper().startswith("HR"):
                chamber = "House"
            elif bill_number.upper().startswith("SB") or bill_number.upper().startswith("SR"):
                chamber = "Senate"
            elif item.get("category") == "House":
                chamber = "House"
            elif item.get("category") == "Senate":
                chamber = "Senate"

            normalized.append(
                NormalizedBill(
                    id=item.get("id") or item.get("link", ""),
                    source="kansas_rss",
                    level="state",
                    state="KS",
                    bill_number=bill_number,
                    title=item.get("short_title") or item.get("title", ""),
                    summary=item.get("summary", ""),
                    classification=[item.get("category", "")] if item.get("category") else [],
                    sponsors=[],
                    latest_action=item.get("title", ""),
                    latest_action_date=item.get("published", ""),
                    status=item.get("category", ""),
                    chamber=chamber,
                    document_urls=[item.get("bill_url") or item.get("link", "")],
                    updated_at=item.get("published", ""),
                    url=item.get("bill_url") or item.get("link", ""),
                )
            )
        return normalized

    def normalize_events(self, raw_events: List[Dict[str, Any]]) -> List[NormalizedEvent]:
        normalized: List[NormalizedEvent] = []
        for item in raw_events:
            committees = item.get("committees")
            committee_list = [committees] if isinstance(committees, str) else (committees or [])

            normalized.append(
                NormalizedEvent(
                    id=item.get("id") or item.get("link", ""),
                    source="kansas_rss",
                    level="state",
                    state="KS",
                    title=item.get("title", ""),
                    description=item.get("summary", ""),
                    scheduled_date=item.get("scheduled_date", ""),
                    scheduled_time=item.get("scheduled_time", ""),
                    location=item.get("location", ""),
                    chamber="",
                    committees=committee_list,
                    url=item.get("link", ""),
                    updated_at=item.get("published", ""),
                )
            )
        return normalized
