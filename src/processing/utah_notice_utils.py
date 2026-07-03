"""Parse Utah Legislature interim meeting notice HTML pages."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

USER_AGENT = "CivicWatch/1.0 (+https://github.com/WAEmberlin/policy-watch)"
INTERIM_NOTICE_RE = re.compile(r"/Interim/\d{4}/html/\d+\.htm", re.IGNORECASE)
COMMITTEE_STREAM_RE = re.compile(
    r"https?://le\.utah\.gov/committee/committee\.jsp\?[^\"'\s>]+",
    re.IGNORECASE,
)
NOTICE_FIELD_RE = re.compile(
    r"^\s*(DATE|TIME|PLACE)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def is_interim_notice_url(url: str) -> bool:
    return bool(url and INTERIM_NOTICE_RE.search(url))


def build_committee_stream_url(committee_code: str, year: str) -> str:
    if not committee_code:
        return ""
    return f"https://le.utah.gov/committee/committee.jsp?year={year}&com={committee_code}"


def parse_notice_html(html: str, fallback_stream_url: str = "") -> Dict[str, str]:
    """Extract DATE, TIME, PLACE, and livestream URL from a notice page."""
    details: Dict[str, str] = {
        "notice_date": "",
        "notice_time": "",
        "notice_place": "",
        "livestream_url": fallback_stream_url or "",
    }
    if not html.strip():
        return details

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\u00a0", " ", text)

    for match in NOTICE_FIELD_RE.finditer(text):
        label = match.group(1).upper()
        value = " ".join(match.group(2).split())
        if label == "DATE" and value:
            details["notice_date"] = value
        elif label == "TIME" and value:
            details["notice_time"] = value
        elif label == "PLACE" and value:
            details["notice_place"] = value

    stream_urls: List[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin("https://le.utah.gov/", anchor["href"])
        if "committee.jsp" in href.lower() and "com=" in href.lower():
            stream_urls.append(href)
    if not stream_urls:
        for match in COMMITTEE_STREAM_RE.finditer(html):
            stream_urls.append(match.group(0))
    if stream_urls:
        details["livestream_url"] = stream_urls[0]

    return details


def fetch_notice_details(
    notice_url: str,
    *,
    committee_code: str = "",
    session_year: str = "",
    timeout: int = 10,
) -> Dict[str, str]:
    """Fetch and parse a Utah interim notice page. Returns empty fields on failure."""
    fallback = build_committee_stream_url(committee_code, session_year)
    if not is_interim_notice_url(notice_url):
        return {
            "notice_date": "",
            "notice_time": "",
            "notice_place": "",
            "livestream_url": fallback,
        }

    try:
        response = requests.get(
            notice_url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        details = parse_notice_html(response.text, fallback_stream_url=fallback)
        if not details["livestream_url"]:
            details["livestream_url"] = fallback
        return details
    except requests.RequestException:
        return {
            "notice_date": "",
            "notice_time": "",
            "notice_place": "",
            "livestream_url": fallback,
        }


def filter_agenda_items(items: List[str]) -> List[str]:
    """Drop placeholder NOTICE lines from agenda lists."""
    return [item for item in items if item and item.strip().upper() != "NOTICE"]


def agenda_preview(items: List[str], fallback: str = "") -> str:
    filtered = filter_agenda_items(items)
    if filtered:
        return "; ".join(filtered[:3])
    return fallback if fallback and fallback.upper() != "NOTICE" else ""
