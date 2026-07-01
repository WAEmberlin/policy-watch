"""HTTP client for Kansas Legislature REST API v1."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

DEFAULT_BASE_URL = "https://kslegislature.gov/api/v1"
DEFAULT_DELAY = 2.1  # ~28 req/min — under 30/min anonymous limit
DEFAULT_MAX_RETRIES = 3


class KansasApiClient:
    """Read-only client for kslegislature.gov/api/v1."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        request_delay: float = DEFAULT_DELAY,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key or os.environ.get("KANSAS_LEGISLATURE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.request_delay = 0.25 if self.api_key else request_delay
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Api-Key {self.api_key}"
        return headers

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = params or {}

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = requests.get(url, params=params, headers=self._headers(), timeout=60)
                self._last_request_at = time.time()

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print(f"Kansas API rate limited; waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 404:
                    return {}

                response.raise_for_status()
                return response.json()

            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise
                wait = 2 ** attempt
                print(f"Kansas API request failed ({exc}); retry in {wait}s")
                time.sleep(wait)

        return {}

    def get_bill_status(self, bill_no: str, biennium: Optional[str] = None) -> Dict[str, Any]:
        """Fetch composite bill status for one bill (e.g. SB498, HB2001)."""
        params = {}
        if biennium:
            params["biennium"] = biennium
        data = self._request(f"/bill_status/{bill_no}/", params)
        results = data.get("results") or []
        return results[0] if results else {}

    def get_votes(self, bill_no: str) -> list:
        data = self._request("/votes/", {"bill_no": bill_no})
        return data.get("results") or []

    def get_hearings(self, bill_no: str, upcoming: bool = False) -> list:
        params: Dict[str, Any] = {"bill": bill_no}
        if upcoming:
            params["upcoming"] = "true"
        data = self._request("/hearings/", params)
        return data.get("results") or []

    def list_hearings(
        self,
        *,
        upcoming: bool = False,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch committee hearings (global schedule, not filtered by bill)."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if upcoming:
            params["upcoming"] = "true"
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._request("/hearings/", params)

    def get_now(self) -> Dict[str, Any]:
        """Current chamber/committee activity snapshot from /api/v1/now/."""
        return self._request("/now/")

    def list_committees(
        self,
        *,
        status: Optional[str] = None,
        committee_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List committees; filter by status (Active/Inactive) or committee_type."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if committee_type:
            params["committee_type"] = committee_type
        return self._request("/committees/", params)
