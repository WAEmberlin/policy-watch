"""Rebuild legislator vote docs + bill lookups from full normalized/openstates data.

docs/legislator_votes.json and related lookups must not be derived from truncated
site_data.json. Normalized votes.json is often slimmed (no per-voter arrays), so
roll-call rebuild prefers data/openstates/*/votes.json for enabled states.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = ROOT / "data" / "normalized"
OPENSTATES_DIR = ROOT / "data" / "openstates"
DOCS_DIR = ROOT / "docs"

DEFAULT_MAX_PER_LEGISLATOR = 250


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data is not None else default
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not load {path}: {exc}")
        return default


def _save_json(path: Path, data: Any, *, compact: bool = False, indent: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    elif indent is not None:
        payload = json.dumps(data, ensure_ascii=False, indent=indent)
    else:
        payload = json.dumps(data, ensure_ascii=False)
    path.write_text(payload, encoding="utf-8")


def _enabled_state_codes() -> List[str]:
    from processing.legislators_directory import load_enabled_states

    codes = []
    for row in load_enabled_states() or []:
        code = str(row.get("code") or "").strip().lower()
        if code:
            codes.append(code)
    return codes


def load_legislators_for_votes() -> List[Dict[str, Any]]:
    """Prefer normalized legislators; fall back to per-state openstates caches."""
    normalized = _load_json(NORMALIZED_DIR / "legislators.json", [])
    if isinstance(normalized, list) and normalized:
        return [row for row in normalized if isinstance(row, dict)]

    rows: List[Dict[str, Any]] = []
    for code in _enabled_state_codes():
        raw = _load_json(OPENSTATES_DIR / code / "legislators.json", [])
        if not isinstance(raw, list):
            continue
        for leg in raw:
            if not isinstance(leg, dict):
                continue
            if not leg.get("state"):
                leg = {**leg, "state": code.upper()}
            rows.append(leg)
    return rows


def load_openstates_votes(
    state_codes: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Load raw roll calls (with voter arrays) from openstates caches."""
    codes = [c.lower() for c in (state_codes or _enabled_state_codes())]
    votes: List[Dict[str, Any]] = []
    per_state: Dict[str, int] = {}
    for code in codes:
        path = OPENSTATES_DIR / code / "votes.json"
        rows = _load_json(path, [])
        if not isinstance(rows, list) or not rows:
            continue
        usable = [row for row in rows if isinstance(row, dict)]
        # Ensure state is set — some caches omit it.
        for row in usable:
            if not row.get("state"):
                row["state"] = code.upper()
        votes.extend(usable)
        per_state[code.upper()] = len(usable)
        print(f"Loaded {len(usable)} openstates votes for {code.upper()}", flush=True)
    return votes, per_state


def merge_vote_indexes(
    parts: Iterable[Dict[str, List[Dict[str, Any]]]],
    *,
    max_per_legislator: int = DEFAULT_MAX_PER_LEGISLATOR,
) -> Dict[str, List[Dict[str, Any]]]:
    merged: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for part in parts:
        for leg_id, entries in (part or {}).items():
            if not leg_id or not isinstance(entries, list):
                continue
            merged[leg_id].extend(entries)
    trimmed: Dict[str, List[Dict[str, Any]]] = {}
    for leg_id, entries in merged.items():
        entries.sort(key=lambda row: row.get("date") or "", reverse=True)
        trimmed[leg_id] = entries[:max_per_legislator]
    return trimmed


def build_legislator_votes_from_sources(
    *,
    max_per_legislator: int = DEFAULT_MAX_PER_LEGISLATOR,
    state_codes: Optional[Sequence[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Build per-legislator vote history from openstates roll calls (+ Kansas API)."""
    from processing.legislator_votes import build_legislator_vote_index

    legislators = load_legislators_for_votes()
    if not legislators:
        raise SystemExit(
            "No legislators found under data/normalized/legislators.json "
            "or data/openstates/*/legislators.json"
        )

    codes = [c.lower() for c in (state_codes or _enabled_state_codes())]
    parts: List[Dict[str, List[Dict[str, Any]]]] = []

    # Kansas official API records once (empty openstates slice).
    if "ks" in codes:
        parts.append(
            build_legislator_vote_index(
                legislators,
                [],
                max_per_legislator=max_per_legislator,
                load_kansas_file=True,
            )
        )

    # Process openstates votes one state at a time to limit peak memory.
    for code in codes:
        path = OPENSTATES_DIR / code / "votes.json"
        rows = _load_json(path, [])
        if not isinstance(rows, list) or not rows:
            print(f"No openstates votes for {code.upper()} ({path})", flush=True)
            continue
        usable = [row for row in rows if isinstance(row, dict)]
        for row in usable:
            if not row.get("state"):
                row["state"] = code.upper()
        print(f"Indexing {len(usable)} votes for {code.upper()}...", flush=True)
        parts.append(
            build_legislator_vote_index(
                legislators,
                usable,
                kansas_vote_records={},  # skip re-loading Kansas API file
                max_per_legislator=max_per_legislator,
                load_kansas_file=False,
            )
        )
        matched = len(parts[-1])
        print(f"  matched {matched} legislators for {code.upper()}", flush=True)
        del usable
        del rows

    index = merge_vote_indexes(parts, max_per_legislator=max_per_legislator)
    return index


def _bill_lookup_key(state: str, bill_number: str) -> Optional[str]:
    state_code = (state or "").strip().upper()
    number = re.sub(r"\s+", "", bill_number or "").upper()
    if not state_code or not number:
        return None
    return f"{state_code}:{number}"


def _urls_from_openstates_bill(bill: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for src in bill.get("sources") or []:
        url = src.get("url") if isinstance(src, dict) else str(src or "")
        if url:
            urls.append(url.strip())
    for version in bill.get("versions") or []:
        if not isinstance(version, dict):
            continue
        for link in version.get("links") or []:
            url = link.get("url") if isinstance(link, dict) else ""
            if url:
                urls.append(str(url).strip())
    openstates_url = (bill.get("openstates_url") or "").strip()
    if openstates_url:
        urls.append(openstates_url)
    # Preserve order, drop empties/dupes.
    return list(dict.fromkeys(u for u in urls if u))


def iter_bills_for_lookups(
    state_codes: Optional[Sequence[str]] = None,
) -> Iterable[Dict[str, Any]]:
    """Yield bill dicts with state/bill_number/title/url from normalized + openstates."""
    seen_keys: set[str] = set()

    normalized = _load_json(NORMALIZED_DIR / "bills.json", [])
    if isinstance(normalized, list):
        for bill in normalized:
            if not isinstance(bill, dict):
                continue
            key = _bill_lookup_key(bill.get("state") or "", bill.get("bill_number") or "")
            if key:
                seen_keys.add(key)
            yield bill

    from processing.openstates_bills import load_state_bills

    codes = [c.lower() for c in (state_codes or _enabled_state_codes())]
    for code in codes:
        state_dir = OPENSTATES_DIR / code
        if not state_dir.is_dir():
            continue
        try:
            raw_bills = load_state_bills(state_dir)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Warning: could not load bills for {code}: {exc}")
            continue
        added = 0
        for bill in raw_bills:
            if not isinstance(bill, dict):
                continue
            identifier = bill.get("bill_number") or bill.get("identifier") or ""
            key = _bill_lookup_key(code.upper(), identifier)
            if not key or key in seen_keys:
                continue
            urls = _urls_from_openstates_bill(bill)
            yield {
                "state": code.upper(),
                "bill_number": identifier,
                "title": (bill.get("title") or "").strip(),
                "short_title": "",
                "url": urls[0] if urls else "",
                "_url_candidates": urls,
            }
            seen_keys.add(key)
            added += 1
        if added:
            print(f"Added {added} openstates bill lookup rows for {code.upper()}")


def build_bill_lookups(
    bills: Optional[Iterable[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    from processing.bill_urls import build_ks_bill_url, pick_best_bill_url

    title_lookup: Dict[str, str] = {}
    url_candidates: Dict[str, List[str]] = {}

    source = bills if bills is not None else iter_bills_for_lookups()
    for bill in source:
        if not isinstance(bill, dict):
            continue
        key = _bill_lookup_key(bill.get("state") or "", bill.get("bill_number") or "")
        if not key:
            continue
        title = (bill.get("title") or bill.get("short_title") or "").strip()
        if title:
            title_lookup[key] = title
        candidates = list(bill.get("_url_candidates") or [])
        url = (bill.get("url") or "").strip()
        if url:
            candidates.append(url)
        if candidates:
            url_candidates.setdefault(key, []).extend(candidates)

    url_lookup: Dict[str, str] = {}
    for key, candidates in url_candidates.items():
        state, bill_number = key.split(":", 1)
        best = pick_best_bill_url(candidates, state, bill_number)
        if best:
            url_lookup[key] = best
        elif state == "KS":
            built = build_ks_bill_url(bill_number)
            if built:
                url_lookup[key] = built
    return title_lookup, url_lookup


def vote_counts_by_state(
    legislator_votes: Dict[str, List[Dict[str, Any]]],
    legislators: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, int]:
    legs = {
        row.get("id"): row
        for row in (legislators if legislators is not None else load_legislators_for_votes())
        if isinstance(row, dict) and row.get("id")
    }
    counts: Counter[str] = Counter()
    for leg_id, votes in (legislator_votes or {}).items():
        if not votes:
            continue
        state = ((legs.get(leg_id) or {}).get("state") or "??").upper()
        counts[state] += 1
    return dict(sorted(counts.items()))


def write_legislator_vote_docs(
    legislator_votes: Dict[str, List[Dict[str, Any]]],
    *,
    docs_dir: Path | None = None,
    normalized_dir: Path | None = None,
    write_normalized: bool = True,
) -> Dict[str, Any]:
    docs = docs_dir or DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)

    votes_path = docs / "legislator_votes.json"
    _save_json(votes_path, legislator_votes, compact=True)

    counts = {
        leg_id: len(votes)
        for leg_id, votes in (legislator_votes or {}).items()
        if votes
    }
    counts_path = docs / "legislator_vote_counts.json"
    _save_json(counts_path, counts, indent=2)

    if write_normalized:
        norm = normalized_dir or NORMALIZED_DIR
        norm.mkdir(parents=True, exist_ok=True)
        _save_json(norm / "legislator_votes.json", legislator_votes, compact=True)

    total_votes = sum(len(v) for v in (legislator_votes or {}).values())
    by_state = vote_counts_by_state(legislator_votes)
    print(
        f"Wrote {len(legislator_votes or {})} legislators with {total_votes} total votes "
        f"to {votes_path}"
    )
    print(f"Wrote {len(counts)} legislator vote counts to {counts_path}")
    print(f"Vote-count keys by state: {by_state}")
    return {
        "legislators_with_votes": len(counts),
        "total_votes": total_votes,
        "by_state": by_state,
        "votes_path": str(votes_path),
        "counts_path": str(counts_path),
    }


def write_bill_lookup_docs(
    title_lookup: Dict[str, str],
    url_lookup: Dict[str, str],
    *,
    docs_dir: Path | None = None,
) -> Dict[str, Any]:
    docs = docs_dir or DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)
    title_path = docs / "bill_title_lookup.json"
    url_path = docs / "bill_url_lookup.json"
    _save_json(title_path, title_lookup)
    _save_json(url_path, url_lookup)

    title_states = Counter(key.split(":", 1)[0] for key in title_lookup)
    print(f"Wrote {len(title_lookup)} bill titles to {title_path}")
    print(f"Wrote {len(url_lookup)} bill URLs to {url_path}")
    print(f"Bill title keys by state: {dict(sorted(title_states.items()))}")
    return {
        "titles": len(title_lookup),
        "urls": len(url_lookup),
        "title_states": dict(sorted(title_states.items())),
        "title_path": str(title_path),
        "url_path": str(url_path),
    }


def rebuild_vote_and_bill_docs(
    *,
    max_per_legislator: int = DEFAULT_MAX_PER_LEGISLATOR,
    state_codes: Optional[Sequence[str]] = None,
    write_normalized: bool = True,
) -> Dict[str, Any]:
    """Rebuild docs vote/lookup artifacts from openstates + normalized sources."""
    legislator_votes = build_legislator_votes_from_sources(
        max_per_legislator=max_per_legislator,
        state_codes=state_codes,
    )
    vote_stats = write_legislator_vote_docs(
        legislator_votes,
        write_normalized=write_normalized,
    )
    title_lookup, url_lookup = build_bill_lookups(iter_bills_for_lookups(state_codes))
    bill_stats = write_bill_lookup_docs(title_lookup, url_lookup)
    return {"votes": vote_stats, "bills": bill_stats}


def write_vote_docs_from_normalized(
    *,
    legislator_votes: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    bills: Optional[Iterable[Dict[str, Any]]] = None,
    rebuild_if_stale: bool = True,
    min_states: int = 8,
) -> Dict[str, Any]:
    """Write docs artifacts for summarize.py.

    If the provided/normalized vote index covers too few states, rebuild from
    openstates roll calls instead of publishing a truncated ME/MD/KS-only file.
    """
    votes = legislator_votes
    if votes is None:
        votes = _load_json(NORMALIZED_DIR / "legislator_votes.json", {})
    if not isinstance(votes, dict):
        votes = {}

    by_state = vote_counts_by_state(votes)
    if rebuild_if_stale and len(by_state) < min_states:
        print(
            f"Normalized legislator_votes covers {len(by_state)} states {list(by_state)}; "
            f"rebuilding from openstates votes (need >= {min_states})"
        )
        return rebuild_vote_and_bill_docs()

    vote_stats = write_legislator_vote_docs(votes, write_normalized=False)
    # Always supplement with openstates bill caches — normalized bills.json can lag.
    title_lookup, url_lookup = build_bill_lookups(iter_bills_for_lookups())
    bill_stats = write_bill_lookup_docs(title_lookup, url_lookup)
    return {"votes": vote_stats, "bills": bill_stats}
