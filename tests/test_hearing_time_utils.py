"""Tests for federal hearing time formatting."""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.email_digest import render_hearing  # noqa: E402
from processing.hearing_time_utils import (  # noqa: E402
    federal_datetime_fields,
    format_federal_hearing_time,
)


def test_federal_datetime_fields_converts_utc_to_eastern():
    dt = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)
    scheduled_date, scheduled_time, published = federal_datetime_fields(dt)
    assert scheduled_date == "2026-07-22"
    assert scheduled_time == "2:00 PM ET"
    assert published == "2026-07-22T18:00:00+00:00"


def test_format_federal_hearing_time_from_legacy_record():
    hearing = {
        "published": "2026-07-22T18:00:00+00:00",
        "scheduled_time": "18:00",
        "source": "Federal (US Congress)",
    }
    assert format_federal_hearing_time(hearing) == "2:00 PM ET"


def test_render_hearing_shows_eastern_time_in_email():
    hearing = {
        "title": "Markup on Veterans Legislation",
        "committee": "House Veterans' Affairs",
        "chamber": "House",
        "published": "2026-07-22T18:00:00+00:00",
        "scheduled_time": "18:00",
        "source": "Federal (US Congress)",
        "level": "federal",
    }
    html = render_hearing(hearing)
    assert "2:00 PM ET" in html
    assert "18:00" not in html
