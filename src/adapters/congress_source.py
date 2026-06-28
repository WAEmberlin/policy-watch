"""Congress.gov API adapter — read-only compatibility layer."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .base import LegislativeSource, NormalizedBill, NormalizedEvent

OUTPUT_DIR = "src/output"
LEGISLATION_FILE = os.path.join(OUTPUT_DIR, "legislation.json")
HEARINGS_FILE = os.path.join(OUTPUT_DIR, "hearings.json")


def fix_hearing_url(hearing: Dict[str, Any]) -> None:
    """Rewrite broken Congress.gov API URLs to public event URLs."""
    url = hearing.get("url") or hearing.get("link") or ""
    event_id = hearing.get("event_id")
    congress = hearing.get("congress", 119)
    chamber = (hearing.get("chamber") or "house").lower()

    if event_id and ("committee-meeting" in url or "api.congress.gov" in url or not url):
        public_url = f"https://www.congress.gov/event/{congress}th-congress/{chamber}-event/{event_id}"
        hearing["url"] = public_url
        hearing["link"] = public_url


class CongressSource(LegislativeSource):
    source_name = "congress"

    def __init__(
        self,
        legislation_path: str = LEGISLATION_FILE,
        hearings_path: str = HEARINGS_FILE,
    ) -> None:
        self.legislation_path = legislation_path
        self.hearings_path = hearings_path

    def _load_json(self, path: str, default: Any) -> Any:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_bills(self) -> List[Dict[str, Any]]:
        data = self._load_json(self.legislation_path, [])
        return data if isinstance(data, list) else []

    def fetch_events(self) -> List[Dict[str, Any]]:
        data = self._load_json(self.hearings_path, [])
        if isinstance(data, dict):
            return data.get("items", [])
        return data if isinstance(data, list) else []

    def normalize_bills(self, raw_bills: List[Dict[str, Any]]) -> List[NormalizedBill]:
        normalized: List[NormalizedBill] = []
        for bill in raw_bills:
            bill_type = bill.get("bill_type", "")
            bill_number = bill.get("bill_number", "")
            bill_id = f"{bill.get('congress', 119)}-{bill_type}-{bill_number}".strip("-")

            sponsors = []
            if bill.get("sponsor_name"):
                sponsors.append({
                    "name": bill["sponsor_name"],
                    "party": bill.get("sponsor_party", ""),
                    "state": bill.get("sponsor_state", ""),
                    "role": "primary",
                })
            for cosponsor in bill.get("cosponsors") or []:
                sponsors.append({
                    "name": cosponsor.get("name", ""),
                    "party": cosponsor.get("party", ""),
                    "state": cosponsor.get("state", ""),
                    "role": "cosponsor",
                })

            chamber = ""
            bt = bill_type.upper()
            if bt.startswith("H"):
                chamber = "House"
            elif bt.startswith("S") and not bt.startswith("SR"):
                chamber = "Senate"

            normalized.append(
                NormalizedBill(
                    id=bill_id or bill.get("url", ""),
                    source="congress",
                    level="federal",
                    state=None,
                    bill_number=f"{bill_type} {bill_number}".strip(),
                    title=bill.get("short_title") or bill.get("title", ""),
                    summary=bill.get("summary", ""),
                    classification=bill.get("policy_areas") or [],
                    sponsors=sponsors,
                    latest_action=bill.get("latest_action", ""),
                    latest_action_date=bill.get("latest_action_date") or bill.get("published", ""),
                    status=bill.get("status") or bill.get("latest_action", ""),
                    chamber=chamber,
                    votes=bill.get("votes") or [],
                    committees=[{"name": c.get("name", c) if isinstance(c, dict) else str(c)} for c in (bill.get("committees") or [])],
                    document_urls=[bill.get("url", "")] if bill.get("url") else [],
                    updated_at=bill.get("latest_action_date") or bill.get("published", ""),
                    url=bill.get("url", ""),
                )
            )
        return normalized

    def normalize_events(self, raw_events: List[Dict[str, Any]]) -> List[NormalizedEvent]:
        normalized: List[NormalizedEvent] = []
        for event in raw_events:
            fix_hearing_url(event)
            committees = event.get("committees") or event.get("committee") or []
            if isinstance(committees, str):
                committees = [committees]

            normalized.append(
                NormalizedEvent(
                    id=event.get("event_id") or event.get("url") or event.get("link", ""),
                    source="congress",
                    level="federal",
                    state=None,
                    title=event.get("title", ""),
                    description=event.get("summary", ""),
                    scheduled_date=event.get("scheduled_date", ""),
                    scheduled_time=event.get("scheduled_time", ""),
                    location=event.get("location", ""),
                    chamber=event.get("chamber", ""),
                    committees=committees if isinstance(committees, list) else [str(committees)],
                    url=event.get("url") or event.get("link", ""),
                    updated_at=event.get("scheduled_date", ""),
                )
            )
        return normalized
