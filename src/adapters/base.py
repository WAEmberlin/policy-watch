"""Base classes and unified schema for legislative source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedBill:
    id: str
    source: str  # congress | kansas_rss | openstates
    level: str  # federal | state
    state: Optional[str]
    bill_number: str
    title: str
    summary: str = ""
    classification: List[str] = field(default_factory=list)
    sponsors: List[Dict[str, Any]] = field(default_factory=list)
    latest_action: str = ""
    latest_action_date: str = ""
    status: str = ""
    chamber: str = ""
    votes: List[Dict[str, Any]] = field(default_factory=list)
    committees: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    document_urls: List[str] = field(default_factory=list)
    updated_at: str = ""
    url: str = ""
    ai_summary_short: str = ""
    ai_summary_detailed: str = ""
    ai_impact_analysis: str = ""
    ai_topics: List[str] = field(default_factory=list)
    ai_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedEvent:
    id: str
    source: str
    level: str
    state: Optional[str]
    title: str
    description: str = ""
    scheduled_date: str = ""
    scheduled_time: str = ""
    location: str = ""
    chamber: str = ""
    committees: List[str] = field(default_factory=list)
    url: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedLegislator:
    id: str
    source: str
    level: str
    state: Optional[str]
    name: str
    party: str = ""
    district: str = ""
    chamber: str = ""
    committees: List[str] = field(default_factory=list)
    sponsored_bills: List[str] = field(default_factory=list)
    cosponsored_bills: List[str] = field(default_factory=list)
    voting_history: List[Dict[str, Any]] = field(default_factory=list)
    url: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LegislativeSource(ABC):
    """Abstract base for all legislative data sources."""

    source_name: str = "unknown"

    @abstractmethod
    def fetch_bills(self) -> List[Dict[str, Any]]:
        """Return raw bill records from this source."""

    def fetch_votes(self) -> List[Dict[str, Any]]:
        return []

    def fetch_events(self) -> List[Dict[str, Any]]:
        return []

    def fetch_committees(self) -> List[Dict[str, Any]]:
        return []

    def fetch_legislators(self) -> List[Dict[str, Any]]:
        return []

    @abstractmethod
    def normalize_bills(self, raw_bills: List[Dict[str, Any]]) -> List[NormalizedBill]:
        """Convert raw records to unified schema."""

    def normalize_events(self, raw_events: List[Dict[str, Any]]) -> List[NormalizedEvent]:
        return []

    def normalize_legislators(self, raw_legislators: List[Dict[str, Any]]) -> List[NormalizedLegislator]:
        return []
