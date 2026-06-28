"""Tests for Open States client with mocked HTTP."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.openstates_client import OpenStatesClient


def test_per_page_capped_at_api_max():
    client = OpenStatesClient(api_key="test", request_delay=0, per_page=50)
    assert client.per_page == 20


def test_normalize_date_param():
    assert OpenStatesClient._normalize_date_param("2026-06-21T00:00:00Z") == "2026-06-21"
    assert OpenStatesClient._normalize_date_param("2026-06-21") == "2026-06-21"
    assert OpenStatesClient._normalize_date_param(None) is None


def test_fetch_bills_passes_include_list_and_date():
    client = OpenStatesClient(api_key="test", request_delay=0)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [],
        "pagination": {"page": 1, "max_page": 1},
    }
    mock_response.raise_for_status = MagicMock()

    with patch("processing.openstates_client.requests.request", return_value=mock_response) as req:
        client.fetch_bills(
            "CO",
            updated_since="2026-06-21T00:00:00Z",
            include=["sponsorships", "actions"],
        )
        _, kwargs = req.call_args
        params = kwargs["params"]
        assert params["updated_since"] == "2026-06-21"
        assert params["include"] == ["sponsorships", "actions"]


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
    rate_limited.headers = {}

    with patch("processing.openstates_client.requests.request", return_value=rate_limited):
        with patch("processing.openstates_client.time.sleep"):
            with pytest.raises(requests.HTTPError):
                client.fetch_bills("CO")
