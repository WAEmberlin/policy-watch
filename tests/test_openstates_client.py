"""Tests for Open States client with mocked HTTP."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_client import OpenStatesClient


def test_paginate_single_page():
    client = OpenStatesClient(api_key="test", request_delay=0)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [{"id": "1", "identifier": "HB 1"}],
        "pagination": {"page": 1, "max_page": 1, "total_items": 1},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("processing.openstates_client.requests.request", return_value=mock_response):
        results = client.fetch_bills("ocd-jurisdiction/country:us/state:ks/government")
        assert len(results) == 1
        assert results[0]["identifier"] == "HB 1"


def test_retry_on_rate_limit():
    client = OpenStatesClient(api_key="test", request_delay=0, max_retries=2)

    rate_limited = MagicMock()
    rate_limited.status_code = 429

    success = MagicMock()
    success.status_code = 200
    success.json.return_value = {
        "results": [],
        "pagination": {"page": 1, "max_page": 1},
    }
    success.raise_for_status = MagicMock()

    with patch("processing.openstates_client.requests.request", side_effect=[rate_limited, success]):
        with patch("processing.openstates_client.time.sleep"):
            results = client.fetch_bills("ocd-jurisdiction/country:us/state:ks/government")
            assert results == []
