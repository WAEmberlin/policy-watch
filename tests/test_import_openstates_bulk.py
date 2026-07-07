"""Tests for Open States bulk JSON import."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.import_openstates_bulk import (
    bill_latest_action_date,
    convert_bulk_bill,
    discover_bill_files,
    parse_state_from_bills_path,
)


def test_parse_state_from_bills_path():
    path = Path("data/historic/ME_132_json_hash/ME/132/ME_132_bills.json")
    assert parse_state_from_bills_path(path) == "me"


def test_bill_latest_action_date():
    bill = {"actions": [{"date": "2026-01-01"}, {"date": "2026-04-15"}]}
    assert bill_latest_action_date(bill) == "2026-04-15"


def test_convert_bulk_bill_maps_sponsors_and_chamber():
    raw = {
        "id": "ocd-bill/test-id",
        "identifier": "LD 100",
        "title": "An Act To Test",
        "chamber": "upper",
        "legislative_session": "132",
        "actions": [{"description": "Passed", "date": "2026-04-01"}],
        "sponsors": [{"name": "Jane Doe", "primary": True, "classification": "primary"}],
        "abstracts": [{"abstract": "Summary text"}],
    }
    converted = convert_bulk_bill(raw, "me")
    assert converted["identifier"] == "LD 100"
    assert converted["sponsorships"][0]["person"]["name"] == "Jane Doe"
    assert converted["from_organization"]["name"] == "Senate"
    assert converted["updated_at"] == "2026-04-01"
    assert converted["abstract"] == "Summary text"


def test_discover_bill_files_skips_us(tmp_path):
    us_dir = tmp_path / "US_119_json_x" / "US" / "119"
    us_dir.mkdir(parents=True)
    (us_dir / "US_119_bills.json").write_text("[]", encoding="utf-8")

    me_dir = tmp_path / "ME_132_json_x" / "ME" / "132"
    me_dir.mkdir(parents=True)
    (me_dir / "ME_132_bills.json").write_text("[]", encoding="utf-8")

    found = discover_bill_files([tmp_path])
    assert len(found) == 1
    assert found[0][0] == "me"


def test_parse_state_from_nebraska_bills_path():
    path = Path("data/nebraska/NE_109_json_hash/NE/109/NE_109_bills.json")
    assert parse_state_from_bills_path(path) == "ne"


def test_parse_state_from_maryland_bills_path():
    path = Path("data/maryland/MD_2025_json_hash/MD/2025/MD_2025_bills.json")
    assert parse_state_from_bills_path(path) == "md"
