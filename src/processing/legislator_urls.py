"""Resolve official legislator profile URLs (state legislature sites, not Open States)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

_SKIP_DOMAINS = (
    "openstates.org",
    "open.pluralpolicy.com",
    "pluralpolicy.com",
    "ballotpedia.org",
    "votesmart.org",
    "wikipedia.org",
    "wikidata.org",
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "youtube.com",
)

_STATE_PROFILE_DOMAINS = {
    "KS": ("kslegislature.gov",),
    "CO": ("leg.colorado.gov",),
    "UT": ("le.utah.gov", "utah.gov"),
    "AZ": ("azleg.gov",),
    "ME": ("legislature.maine.gov",),
    "FEDERAL": ("congress.gov", "house.gov", "senate.gov"),
}

_PROFILE_PATH_HINTS = (
    "/legislator",
    "/legislators/",
    "/member",
    "/members/",
    "/house-member",
    "/senate-member",
    "/memberprofiles/",
    "/MemberProfiles/",
)


def _is_official(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    return not any(domain in lower for domain in _SKIP_DOMAINS)


def _parse_links(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        urls: List[str] = []
        for item in raw:
            if isinstance(item, dict):
                url = (item.get("url") or "").strip()
            else:
                url = str(item).strip()
            if url:
                urls.append(url)
        return urls
    if isinstance(raw, str):
        return [part.strip() for part in raw.replace(",", ";").split(";") if part.strip()]
    return []


def resolve_legislator_profile_url(legislator: Dict[str, Any]) -> str:
    """Prefer the state legislature (or Congress.gov) member page."""
    state = (legislator.get("state") or "").upper()
    preferred_domains = _STATE_PROFILE_DOMAINS.get(state, ())

    candidates: List[str] = []
    for url in _parse_links(legislator.get("links")):
        candidates.append(url)
    for url in _parse_links(legislator.get("sources")):
        candidates.append(url)

    existing = (legislator.get("url") or legislator.get("openstates_url") or "").strip()
    if existing:
        candidates.insert(0, existing)

    for domain in preferred_domains:
        for url in candidates:
            if domain in url.lower() and _is_official(url):
                return url

    profile_pages: List[str] = []
    other_official: List[str] = []
    for url in candidates:
        if not _is_official(url):
            continue
        lower = url.lower()
        if any(hint in lower for hint in _PROFILE_PATH_HINTS):
            profile_pages.append(url)
        else:
            other_official.append(url)

    if profile_pages:
        return profile_pages[0]
    if other_official:
        return other_official[0]
    return existing if _is_official(existing) else existing
