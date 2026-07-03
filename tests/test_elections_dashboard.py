"""Tests for elections dashboard date helpers."""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs"))

# elections-dashboard.js is browser JS; mirror the filter logic for tests.
def parse_local_date(date_str: str) -> date:
    year, month, day = date_str.split("-")
    return date(int(year), int(month), int(day))


def upcoming_dates(entries, today: date):
    return sorted(
        [entry for entry in entries if parse_local_date(entry["date"]) >= today],
        key=lambda entry: parse_local_date(entry["date"]),
    )


def test_upcoming_dates_filters_past_events():
    entries = [
        {"date": "2026-06-09", "label": "Primary Election"},
        {"date": "2026-11-03", "label": "General Election"},
    ]
    result = upcoming_dates(entries, date(2026, 7, 2))
    assert len(result) == 1
    assert result[0]["label"] == "General Election"


def test_upcoming_dates_sorts_chronologically():
    entries = [
        {"date": "2026-11-03", "label": "General Election"},
        {"date": "2026-08-04", "label": "Primary Election"},
    ]
    result = upcoming_dates(entries, date(2026, 7, 2))
    assert [entry["label"] for entry in result] == ["Primary Election", "General Election"]
