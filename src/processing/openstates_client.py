"""Open States API v3 client with pagination, retry, and rate limiting."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Iterator, List, Optional

import requests

DEFAULT_BASE_URL = "https://v3.openstates.org"
DEFAULT_DELAY = 0.5
DEFAULT_MAX_RETRIES = 3
DEFAULT_PER_PAGE = 20


class OpenStatesClient:
    """HTTP client for Open States API v3."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        request_delay: float = DEFAULT_DELAY,
        max_retries: int = DEFAULT_MAX_RETRIES,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENSTATES_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.per_page = per_page
        self._last_request_at = 0.0

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        return headers

    @staticmethod
    def _format_include(include: Optional[List[str]]) -> Optional[str]:
        """Open States expects include as a comma-separated string, not repeated params."""
        if not include:
            return None
        return ",".join(include)

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = dict(params or {})

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=60,
                )
                self._last_request_at = time.time()

                if response.status_code == 429:
                    wait = min(60, 2 ** attempt)
                    print(f"Open States rate limited; waiting {wait}s (attempt {attempt})")
                    time.sleep(wait)
                    continue

                if response.status_code >= 400:
                    detail = response.text[:500]
                    print(f"Open States HTTP {response.status_code} for {url}: {detail}")

                response.raise_for_status()
                return response.json()

            except requests.HTTPError:
                raise
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise
                wait = 2 ** attempt
                print(f"Open States request failed ({exc}); retry in {wait}s")
                time.sleep(wait)

        return {"results": [], "pagination": {"page": 1, "max_page": 1, "total_items": 0}}

    def paginate(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        result_key: str = "results",
    ) -> Iterator[Dict[str, Any]]:
        """Yield all records across paginated API responses."""
        params = dict(params or {})
        params.setdefault("per_page", self.per_page)
        page = 1

        while True:
            params["page"] = page
            data = self._request("GET", path, params)
            results = data.get(result_key, [])
            if not isinstance(results, list):
                break

            for item in results:
                yield item

            pagination = data.get("pagination") or {}
            max_page = pagination.get("max_page", page)
            if page >= max_page or not results:
                break
            page += 1

    def fetch_bills(
        self,
        jurisdiction: str,
        updated_since: Optional[str] = None,
        include: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"jurisdiction": jurisdiction}
        if updated_since:
            params["updated_since"] = updated_since
        include_str = self._format_include(include)
        if include_str:
            params["include"] = include_str

        try:
            return list(self.paginate("/bills", params))
        except requests.HTTPError as exc:
            if include_str and exc.response is not None and exc.response.status_code in (400, 422):
                print("Bills fetch rejected include params; retrying without include...")
                params.pop("include", None)
                return list(self.paginate("/bills", params))
            raise

    def fetch_events(
        self,
        jurisdiction: str,
        updated_since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"jurisdiction": jurisdiction}
        if updated_since:
            params["updated_since"] = updated_since
        return list(self.paginate("/events", params))

    def fetch_committees(self, jurisdiction: str) -> List[Dict[str, Any]]:
        return list(self.paginate("/committees", {"jurisdiction": jurisdiction}))

    def fetch_legislators(
        self,
        jurisdiction: str,
        updated_since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"jurisdiction": jurisdiction}
        if updated_since:
            params["updated_since"] = updated_since
        return list(self.paginate("/people", params))
