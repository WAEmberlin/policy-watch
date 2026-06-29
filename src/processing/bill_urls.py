"""Resolve official state/federal bill page URLs (not Open States mirrors)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

_SKIP_DOMAINS = (
    "openstates.org",
    "open.pluralpolicy.com",
    "pluralpolicy.com",
)


def _is_official(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return not any(domain in lower for domain in _SKIP_DOMAINS)


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
    official_bill_pages: List[str] = []
    other_official: List[str] = []

    for url in _iter_source_urls(bill):
        if not _is_official(url):
            continue
        lower = url.lower()
        if any(token in lower for token in ("/bills/", "/bill/", "congress.gov/bill")):
            if "/bill_files/" in lower or "/download" in lower:
                other_official.append(url)
            else:
                official_bill_pages.append(url)
        else:
            other_official.append(url)

    if official_bill_pages:
        return official_bill_pages[0]
    if other_official:
        return other_official[0]

    fallback = bill.get("openstates_url") or bill.get("url") or ""
    return fallback if _is_official(fallback) else fallback
