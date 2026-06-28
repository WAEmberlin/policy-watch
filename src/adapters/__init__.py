"""Source adapters for CivicWatch unified legislative data."""

from .base import LegislativeSource, NormalizedBill, NormalizedEvent, NormalizedLegislator
from .congress_source import CongressSource
from .kansas_rss_source import KansasRSSSource
from .openstates_source import OpenStatesSource

__all__ = [
    "LegislativeSource",
    "NormalizedBill",
    "NormalizedEvent",
    "NormalizedLegislator",
    "CongressSource",
    "KansasRSSSource",
    "OpenStatesSource",
]
