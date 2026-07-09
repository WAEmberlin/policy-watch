"""Resolve official state/federal bill page URLs (not Open States mirrors)."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from processing.kansas_votes import KANSAS_BIENNIUM

_SKIP_DOMAINS = (
    "openstates.org",
    "open.pluralpolicy.com",
    "pluralpolicy.com",
)

_KS_HOST = "https://www.kslegislature.gov"
_KS_RESOLUTION_PREFIXES = ("HCR", "SCR", "HR", "SR")
_KS_MEASURES_RE = re.compile(
    r"https?://(?:www\.)?kslegislature\.(?:gov|org)(?:/li)?/b\d{4}_\d{2}/measures/([a-z0-9]+)/?",
    re.I,
)
_KS_LEGACY_MEASURES_RE = re.compile(
    r"https?://(?:www\.)?kslegislature\.(?:gov|org)/li/b\d{4}_\d{2}/measures/([a-z0-9]+)/?",
    re.I,
)


def _is_official(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return not any(domain in lower for domain in _SKIP_DOMAINS)


def _normalize_bill_number(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def _bill_kind(bill_number: str) -> str:
    """Return 'resolution' or 'bill' for Kansas URL routing."""
    normalized = _normalize_bill_number(bill_number)
    if any(normalized.startswith(prefix) for prefix in _KS_RESOLUTION_PREFIXES):
        return "resolution"
    return "bill"


def build_ks_bill_url(bill_number: str, biennium: str = KANSAS_BIENNIUM) -> str:
    """Build a Kansas Legislature bill page URL for the current biennium."""
    normalized = _normalize_bill_number(bill_number)
    if not normalized:
        return ""
    if _bill_kind(normalized) == "resolution":
        return f"{_KS_HOST}/{biennium}/resolutions/{normalized}/"
    return f"{_KS_HOST}/{biennium}/bills/{normalized}"


def normalize_bill_url(url: str, state: str = "", bill_number: str = "") -> str:
    """Upgrade stale or legacy bill URLs to working legislature pages."""
    state = (state or "").upper()
    bill_number = bill_number or ""
    normalized_number = _normalize_bill_number(bill_number)

    if state == "KS":
        if not normalized_number and url:
            match = _KS_MEASURES_RE.search(url) or _KS_LEGACY_MEASURES_RE.search(url)
            if match:
                normalized_number = match.group(1).upper()
        if normalized_number:
            rebuilt = build_ks_bill_url(normalized_number)
            if not url:
                return rebuilt
            lower = url.lower()
            if "b2023_24" in lower or "kslegislature.org" in lower or "/measures/" in lower:
                return rebuilt
            if "b2025_26" not in lower and "/bills/" not in lower and "/resolutions/" not in lower:
                return rebuilt
        if url and "kslegislature.org" in url.lower():
            return url.replace("http://kslegislature.org", _KS_HOST, 1).replace(
                "https://kslegislature.org", _KS_HOST, 1
            )

    return url or ""


def _url_quality(url: str, state: str = "", bill_number: str = "") -> int:
    """Higher score = better URL for lookup deduplication."""
    if not url:
        return 0
    score = 1
    lower = url.lower()
    if _is_official(url):
        score += 2
    if any(token in lower for token in ("/bills/", "/bill/", "/resolutions/", "congress.gov/bill")):
        score += 4
    if "/bill_files/" in lower or lower.endswith(".pdf"):
        score -= 2
    if state == "KS":
        if KANSAS_BIENNIUM in lower:
            score += 8
        if "b2023_24" in lower or "kslegislature.org" in lower:
            score -= 10
        if "/measures/" in lower:
            score -= 1
    normalized = normalize_bill_url(url, state, bill_number)
    if normalized and normalized != url:
        score -= 5
    return score


def pick_best_bill_url(candidates: Iterable[str], state: str = "", bill_number: str = "") -> str:
    """Choose the best official URL from duplicates, then normalize it."""
    best_url = ""
    best_score = -1
    for url in candidates:
        if not url:
            continue
        score = _url_quality(url, state, bill_number)
        if score > best_score:
            best_score = score
            best_url = url
    return normalize_bill_url(best_url, state, bill_number)


def _iter_source_urls(bill: Dict[str, Any]) -> Iterable[str]:
    for src in bill.get("sources") or []:
        if isinstance(src, dict):
            url = src.get("url") or ""
        else:
            url = str(src)
        if url:
            yield url

    for version in bill.get("versions") or []:
        for link in version.get("links") or []:
            url = link.get("url") or ""
            if url:
                yield url

    for doc in bill.get("documents") or []:
        if isinstance(doc, dict):
            url = doc.get("url") or ""
            if url:
                yield url

    for url in bill.get("document_urls") or []:
        if url:
            yield url

    fallback = bill.get("openstates_url") or bill.get("url") or ""
    if fallback:
        yield fallback


def resolve_official_bill_url(bill: Dict[str, Any]) -> str:
    """Prefer the state legislature (or Congress.gov) page over Open States."""
    state = (bill.get("state") or "").upper()
    bill_number = bill.get("bill_number") or ""
    official_bill_pages: List[str] = []
    other_official: List[str] = []

    for url in _iter_source_urls(bill):
        if not _is_official(url):
            continue
        lower = url.lower()
        if any(token in lower for token in ("/bills/", "/bill/", "/resolutions/", "congress.gov/bill")):
            if "/bill_files/" in lower or "/download" in lower:
                other_official.append(url)
            else:
                official_bill_pages.append(url)
        else:
            other_official.append(url)

    candidates = official_bill_pages or other_official
    if candidates:
        return pick_best_bill_url(candidates, state, bill_number)

    fallback = bill.get("openstates_url") or bill.get("url") or ""
    if state == "KS" and bill_number and (not fallback or not _is_official(fallback)):
        return build_ks_bill_url(bill_number)
    return normalize_bill_url(fallback if _is_official(fallback) else fallback, state, bill_number)
