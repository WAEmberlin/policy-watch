"""Build per-legislator vote history from Kansas API and Open States roll calls."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = ROOT / "data" / "normalized"
KANSAS_VOTES_FILE = ROOT / "data" / "kansas" / "vote_records.json"

KPID_RE = re.compile(r"/(?:members|legislators)/([^/]+)/?", re.IGNORECASE)

VOTE_OPTION_LABELS = {
    "yes": "Yes",
    "yea": "Yes",
    "no": "No",
    "nay": "No",
    "present": "Present",
    "absent": "Absent",
    "not voting": "Not voting",
    "not_voting": "Not voting",
    "excused": "Excused",
}

# Per-state lookup: key -> list of (leg_id, chamber_key, full_name, surname)
_LegEntry = Tuple[str, str, str, str]


def chamber_key(chamber: str = "", organization: str = "") -> str:
    text = f"{chamber} {organization}".lower()
    if any(token in text for token in ("house", "lower", "representative", "delegates")):
        return "lower"
    if any(token in text for token in ("senate", "upper", "senator", "legislature", "unicameral")):
        return "upper"
    return ""


def kpid_from_url(url: str) -> str:
    if not url:
        return ""
    match = KPID_RE.search(url)
    return match.group(1) if match else ""


def format_vote_option(option: str) -> str:
    key = (option or "").strip().lower().replace("_", " ")
    return VOTE_OPTION_LABELS.get(key, option or "-")


def _append_vote(index: Dict[str, List[Dict[str, Any]]], leg_id: str, entry: Dict[str, Any]) -> None:
    if not leg_id:
        return
    index[leg_id].append(entry)


def normalize_person_name(value: str) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s.,'-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def legislator_surname(leg: Dict[str, Any]) -> str:
    family = normalize_person_name(leg.get("family_name") or "")
    if family:
        return family
    full = normalize_person_name(leg.get("name") or "")
    parts = full.split()
    return parts[-1] if parts else ""


def voter_match_keys(voter_name: str, state: str) -> List[str]:
    raw = normalize_person_name(voter_name)
    if not raw:
        return []
    keys = [raw]
    lowered = (voter_name or "").lower()
    if state == "ME" and " of " in lowered:
        keys.append(normalize_person_name(voter_name.split(" of ")[0]))
    parts = raw.split()
    if parts:
        keys.append(parts[-1])
    if "," in raw:
        keys.append(raw.split(",", 1)[0].strip())
    return list(dict.fromkeys(key for key in keys if key))


def _build_state_name_index(legislators: List[Dict[str, Any]]) -> Dict[str, List[_LegEntry]]:
    """Map exact full-name / surname keys to legislator entries for O(1) matching."""
    index: Dict[str, List[_LegEntry]] = defaultdict(list)
    for leg in legislators:
        leg_id = leg.get("id")
        if not leg_id:
            continue
        full = normalize_person_name(leg.get("name") or "")
        surname = legislator_surname(leg)
        chamber = chamber_key(leg.get("chamber", ""))
        entry: _LegEntry = (leg_id, chamber, full, surname)
        if full:
            index[full].append(entry)
        if surname:
            index[surname].append(entry)
    return index


def _match_voter_name(
    voter_name: str,
    state: str,
    organization: str,
    legislators: List[Dict[str, Any]],
    name_index: Optional[Dict[str, List[_LegEntry]]] = None,
) -> Optional[str]:
    keys = voter_match_keys(voter_name, state)
    if not keys:
        return None
    target_chamber = chamber_key(organization=organization)
    matches: List[str] = []

    if name_index is not None:
        seen_ids: set[str] = set()
        candidates: List[_LegEntry] = []
        for key in keys:
            for entry in name_index.get(key) or []:
                if entry[0] in seen_ids:
                    continue
                seen_ids.add(entry[0])
                candidates.append(entry)
        # Fuzzy pass over a small candidate pool (same surname token), else skip.
        if not candidates:
            surname_keys = [k for k in keys if " " not in k]
            for key in surname_keys:
                for entry in name_index.get(key) or []:
                    if entry[0] not in seen_ids:
                        seen_ids.add(entry[0])
                        candidates.append(entry)
        for leg_id, leg_chamber, full, surname in candidates:
            if target_chamber and leg_chamber and leg_chamber != target_chamber:
                continue
            for key in keys:
                if key == full or (surname and key == surname):
                    matches.append(leg_id)
                    break
                if surname and key.endswith(f" {surname}"):
                    matches.append(leg_id)
                    break
                if full and (key == full or full.startswith(f"{key} ") or f" {key}" in f" {full}"):
                    matches.append(leg_id)
                    break
    else:
        for leg in legislators:
            if (leg.get("state") or "").upper() != state.upper():
                continue
            leg_chamber = chamber_key(leg.get("chamber", ""))
            if target_chamber and leg_chamber and leg_chamber != target_chamber:
                continue
            full = normalize_person_name(leg.get("name") or "")
            surname = legislator_surname(leg)
            for key in keys:
                if key == full or (surname and key == surname):
                    matches.append(leg["id"])
                    break
                if surname and key.endswith(f" {surname}"):
                    matches.append(leg["id"])
                    break
                if full and (key == full or full.startswith(f"{key} ") or f" {key}" in f" {full}"):
                    matches.append(leg["id"])
                    break

    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0]
    return None


def build_legislator_vote_index(
    legislators: List[Dict[str, Any]],
    votes: List[Dict[str, Any]],
    kansas_vote_records: Optional[Dict[str, Any]] = None,
    *,
    max_per_legislator: int = 1000,
    load_kansas_file: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_state: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    name_indexes: Dict[str, Dict[str, List[_LegEntry]]] = {}
    kpid_to_id: Dict[str, str] = {}

    for leg in legislators:
        state = (leg.get("state") or "").upper()
        if state:
            by_state[state].append(leg)
        kpid = kpid_from_url(leg.get("url") or "")
        if kpid and leg.get("id"):
            kpid_to_id[kpid] = leg["id"]

    for state, rows in by_state.items():
        name_indexes[state] = _build_state_name_index(rows)

    # None => optionally auto-load Kansas API file. Explicit {} skips that load
    # (used when merging per-state openstates passes).
    if kansas_vote_records is None:
        records: Dict[str, Any] = {}
        if load_kansas_file and KANSAS_VOTES_FILE.exists():
            with open(KANSAS_VOTES_FILE, encoding="utf-8") as f:
                records = json.load(f)
    else:
        records = kansas_vote_records

    for bill_number, vote_list in records.items():
        if bill_number.startswith("_") or not isinstance(vote_list, list):
            continue
        for vote in vote_list:
            members = vote.get("members") or {}
            if not isinstance(members, dict):
                continue
            for option, member_list in members.items():
                if not isinstance(member_list, list):
                    continue
                for member in member_list:
                    if not isinstance(member, dict):
                        continue
                    kpid = member.get("kpid") or kpid_from_url(member.get("url") or "")
                    leg_id = kpid_to_id.get(kpid)
                    if not leg_id:
                        continue
                    _append_vote(
                        index,
                        leg_id,
                        {
                            "source": "kansas_api",
                            "bill_number": vote.get("bill_number") or bill_number,
                            "date": vote.get("date") or "",
                            "motion": vote.get("result") or "",
                            "option": format_vote_option(option),
                            "chamber": vote.get("chamber") or "",
                            "rcs_num": vote.get("rcs_num") or "",
                        },
                    )

    for vote in votes:
        state = (vote.get("state") or "").upper()
        if not state:
            continue
        state_index = name_indexes.get(state)
        state_legs = by_state.get(state, [])
        for voter in vote.get("votes") or []:
            if not isinstance(voter, dict):
                continue
            leg_id = _match_voter_name(
                voter.get("voter_name") or voter.get("name") or "",
                state,
                vote.get("organization") or "",
                state_legs,
                name_index=state_index,
            )
            if not leg_id:
                continue
            _append_vote(
                index,
                leg_id,
                {
                    "source": "openstates",
                    "bill_number": vote.get("bill_number") or "",
                    "bill_id": vote.get("bill_id") or "",
                    "date": vote.get("date") or "",
                    "motion": vote.get("motion_text") or vote.get("result") or "",
                    "option": format_vote_option(voter.get("option") or ""),
                    "chamber": vote.get("organization") or "",
                },
            )

    trimmed: Dict[str, List[Dict[str, Any]]] = {}
    for leg_id, entries in index.items():
        entries.sort(key=lambda row: row.get("date") or "", reverse=True)
        trimmed[leg_id] = entries[:max_per_legislator]
    return trimmed


def load_and_build(
    *,
    max_per_legislator: int = 1000,
) -> Dict[str, List[Dict[str, Any]]]:
    legislators_path = NORMALIZED_DIR / "legislators.json"
    votes_path = NORMALIZED_DIR / "votes.json"
    legislators: List[Dict[str, Any]] = []
    votes: List[Dict[str, Any]] = []
    if legislators_path.exists():
        with open(legislators_path, encoding="utf-8") as f:
            legislators = json.load(f)
    if votes_path.exists():
        with open(votes_path, encoding="utf-8") as f:
            votes = json.load(f)
    return build_legislator_vote_index(legislators, votes, max_per_legislator=max_per_legislator)
