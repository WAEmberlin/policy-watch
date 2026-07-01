"""Open States API adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import LegislativeSource, NormalizedBill, NormalizedEvent, NormalizedLegislator
from processing.bill_urls import resolve_official_bill_url
from processing.legislator_urls import resolve_legislator_profile_url
from processing.youtube_utils import is_youtube_url


def _state_from_jurisdiction(jurisdiction: str) -> str:
    """Extract state code from OCD jurisdiction ID."""
    parts = jurisdiction.split("/")
    for part in parts:
        if part.startswith("state:"):
            return part.split(":")[-1].upper()
    return ""


_STREAM_NOTE_HINTS = ("stream", "video", "live", "watch", "broadcast", "webcast")
_MEDIA_CLASS_HINTS = ("video", "live", "stream", "webcast")


def _link_looks_like_stream(url: str, note: str = "") -> bool:
    if not url:
        return False
    if is_youtube_url(url):
        return True
    lowered = url.lower()
    if any(token in lowered for token in ("livestream", "live-stream", "harmony", "webcast", "coloradochannel")):
        return True
    note_lower = (note or "").lower()
    return any(token in note_lower for token in _STREAM_NOTE_HINTS)


def _event_stream_url(event: Dict[str, Any]) -> str:
    for item in event.get("media") or []:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        classification = " ".join(item.get("classification") or []).lower()
        if url and (
            is_youtube_url(url)
            or any(token in classification for token in _MEDIA_CLASS_HINTS)
            or _link_looks_like_stream(url)
        ):
            return url

    for link in event.get("links") or []:
        if isinstance(link, dict):
            url = (link.get("url") or "").strip()
            note = link.get("note") or ""
        else:
            url = str(link).strip()
            note = ""
        if url and _link_looks_like_stream(url, note):
            return url
    return ""


def _collect_document_urls(bill: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for src in bill.get("sources") or []:
        url = src.get("url") if isinstance(src, dict) else str(src)
        if url and url not in urls:
            urls.append(url)
    for version in bill.get("versions") or []:
        for link in version.get("links") or []:
            url = link.get("url") or ""
            if url and url not in urls:
                urls.append(url)
    openstates_url = bill.get("openstates_url") or ""
    if openstates_url and openstates_url not in urls:
        urls.append(openstates_url)
    return urls


class OpenStatesSource(LegislativeSource):
    source_name = "openstates"

    def __init__(self, state_code: str, jurisdiction: str) -> None:
        self.state_code = state_code.upper()
        self.jurisdiction = jurisdiction
        self._bills: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []
        self._committees: List[Dict[str, Any]] = []
        self._legislators: List[Dict[str, Any]] = []

    def set_data(
        self,
        bills: List[Dict[str, Any]],
        events: Optional[List[Dict[str, Any]]] = None,
        committees: Optional[List[Dict[str, Any]]] = None,
        legislators: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._bills = bills
        self._events = events or []
        self._committees = committees or []
        self._legislators = legislators or []

    def fetch_bills(self) -> List[Dict[str, Any]]:
        return self._bills

    def fetch_events(self) -> List[Dict[str, Any]]:
        return self._events

    def fetch_committees(self) -> List[Dict[str, Any]]:
        return self._committees

    def fetch_legislators(self) -> List[Dict[str, Any]]:
        return self._legislators

    def normalize_bills(self, raw_bills: List[Dict[str, Any]]) -> List[NormalizedBill]:
        normalized: List[NormalizedBill] = []
        for bill in raw_bills:
            bill_id = bill.get("id") or bill.get("openstates_url", "")
            identifier = bill.get("identifier", "")
            latest_action = ""
            latest_action_date = ""
            actions = bill.get("actions") or []
            if actions:
                last = actions[-1]
                latest_action = last.get("description", "")
                latest_action_date = last.get("date", "")

            sponsors = []
            for sponsor in bill.get("sponsorships") or []:
                person = sponsor.get("person") or {}
                sponsors.append({
                    "name": person.get("name", sponsor.get("name", "")),
                    "party": person.get("party", ""),
                    "role": sponsor.get("primary", False) and "primary" or "cosponsor",
                })

            chamber = ""
            from_org = bill.get("from_organization") or {}
            org_name = (from_org.get("name") or "").lower()
            if "house" in org_name:
                chamber = "House"
            elif "senate" in org_name:
                chamber = "Senate"

            doc_urls = _collect_document_urls(bill)
            official_url = resolve_official_bill_url({**bill, "document_urls": doc_urls})

            normalized.append(
                NormalizedBill(
                    id=bill_id,
                    source="openstates",
                    level="state",
                    state=self.state_code,
                    bill_number=identifier,
                    title=bill.get("title", ""),
                    summary=(bill.get("abstract") or "")[:2000],
                    classification=bill.get("classification") or bill.get("subject") or [],
                    sponsors=sponsors,
                    latest_action=latest_action,
                    latest_action_date=latest_action_date or bill.get("updated_at", ""),
                    status=latest_action,
                    chamber=chamber,
                    committees=[{"name": c.get("name", "")} for c in (bill.get("committees") or [])],
                    document_urls=doc_urls,
                    updated_at=bill.get("updated_at", ""),
                    url=official_url,
                )
            )
        return normalized

    def normalize_events(self, raw_events: List[Dict[str, Any]]) -> List[NormalizedEvent]:
        normalized: List[NormalizedEvent] = []
        for event in raw_events:
            committees = []
            for participant in event.get("participants") or []:
                name = participant.get("name", "")
                if name:
                    committees.append(name)

            page_url = event.get("links", [{}])[0].get("url", "") if event.get("links") else ""
            stream_url = _event_stream_url(event)

            normalized.append(
                NormalizedEvent(
                    id=event.get("id", ""),
                    source="openstates",
                    level="state",
                    state=self.state_code,
                    title=event.get("name", ""),
                    description=event.get("description", ""),
                    scheduled_date=event.get("start_date", ""),
                    scheduled_time="",
                    location=(event.get("location") or {}).get("name", "") if isinstance(event.get("location"), dict) else str(event.get("location") or ""),
                    chamber="",
                    committees=committees,
                    url=page_url,
                    stream_url=stream_url,
                    updated_at=event.get("updated_at", event.get("start_date", "")),
                )
            )
        return normalized

    def normalize_legislators(self, raw_legislators: List[Dict[str, Any]]) -> List[NormalizedLegislator]:
        normalized: List[NormalizedLegislator] = []
        for person in raw_legislators:
            current_role = (person.get("current_role") or {})
            committees = [m.get("organization", {}).get("name", "") for m in (person.get("memberships") or [])]
            profile_url = resolve_legislator_profile_url({**person, "state": self.state_code})

            normalized.append(
                NormalizedLegislator(
                    id=person.get("id", ""),
                    source="openstates",
                    level="state",
                    state=self.state_code,
                    name=person.get("name", ""),
                    party=person.get("party") or person.get("current_party", ""),
                    district=current_role.get("district", ""),
                    chamber=current_role.get("title", "") or current_role.get("chamber", ""),
                    committees=[c for c in committees if c],
                    url=profile_url,
                    gender=person.get("gender", ""),
                    birth_date=person.get("birth_date", ""),
                    image=person.get("image", ""),
                    updated_at=person.get("updated_at", ""),
                )
            )
        return normalized
