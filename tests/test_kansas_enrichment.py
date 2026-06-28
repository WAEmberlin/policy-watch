"""Tests for Kansas API enrichment."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.enrich_kansas_api import parse_bill_status, extract_bill_number_from_item, to_api_bill_no
from processing.enrichment_utils import apply_enrichment_to_bill


SAMPLE_STATUS = {
    "BILLNO": "SB498",
    "SHORTTITLE": "Tax credit bill",
    "LONGTITLE": "AN ACT concerning taxation",
    "STATUS": "Dead / Failed",
    "SPONSOR_NAMES": ["Senate Committee on Assessment and Taxation"],
    "HISTORY": [
        {
            "status": "Died in House Committee",
            "occurred_datetime": "2026-04-27T15:42:55",
            "committee_names": ["Committee on Taxation"],
        }
    ],
    "versions": [{"document": "/bills/download/?apn=test.pdf"}],
}


def test_to_api_bill_no():
    assert to_api_bill_no("SB 498") == "SB498"
    assert to_api_bill_no("HB 2001") == "HB2001"


def test_extract_bill_number_from_title():
    item = {"title": "Senate: SB498: Introduced", "type": "state_legislation", "state": "KS"}
    assert extract_bill_number_from_item(item) == "SB498"


def test_parse_bill_status():
    record = parse_bill_status(SAMPLE_STATUS, votes=[], hearings=[])
    assert record["bill_number"] == "SB498"
    assert record["status"] == "Dead / Failed"
    assert record["latest_action"] == "Died in House Committee"
    assert len(record["sponsors"]) == 1
    assert record["document_urls"][0].startswith("https://kslegislature.gov")


def test_apply_enrichment_to_bill():
    bill = {
        "bill_number": "SB 498",
        "title": "Senate: SB498: Introduced",
        "source": "kansas_rss",
        "level": "state",
        "state": "KS",
    }
    enrichment = parse_bill_status(SAMPLE_STATUS, [], [])
    merged = apply_enrichment_to_bill(bill, enrichment)
    assert merged["short_title"] == "Tax credit bill"
    assert merged["status"] == "Dead / Failed"
    assert merged["enrichment_source"] == "kansas_api"
