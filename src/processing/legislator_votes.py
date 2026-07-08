"""Build per-legislator vote history from Kansas API and Open States roll calls."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = ROOT / "data" / "normalized"
KANSAS_VOTES_FILE = ROOT / "data" / "kansas" / "vote_records.json"

KPID_RE = re.compile(r"/members/([^/]+)/?", re.IGNORECASE)

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
    return VOTE_OPTION_LABELS.get(key, option or "—")


def _append_vote(index: Dict[str, List[Dict[str, Any]]], leg_id: str, entry: Dict[str, Any]) -> None:
    if not leg_id:
        return
    index[leg_id].append(entry)


def _match_voter_name(
    voter_name: str,
    state: str,
    organization: str,
    legislators: List[Dict[str, Any]],
) -> Optional[str]:
    needle = (voter_name or "").strip().lower()
    if not needle:
        return None
    target_chamber = chamber_key(organization=organization)
    matches: List[str] = []
    for leg in legislators:
        if (leg.get("state") or "").upper() != state.upper():
            continue
        leg_chamber = chamber_key(leg.get("chamber", ""))
        if target_chamber and leg_chamber and leg_chamber != target_chamber:
            continue
        family = (leg.get("family_name") or "").strip().lower()
        full = (leg.get("name") or "").strip().lower()
        parts = full.split()
        if needle == family or needle == full:
            matches.append(leg["id"])
            continue
        if family and needle == family:
            matches.append(leg["id"])
            continue
        if parts and needle == parts[-1]:
            matches.append(leg["id"])
            continue
        if full.startswith(f"{needle} ") or f" {needle}" in f" {full}":
            matches.append(leg["id"])
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
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    by_state: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    kpid_to_id: Dict[str, str] = {}

    for leg in legislators:
        state = (leg.get("state") or "").upper()
        if state:
            by_state[state].append(leg)
        kpid = kpid_from_url(leg.get("url") or "")
        if kpid and leg.get("id"):
            kpid_to_id[kpid] = leg["id"]

    records = kansas_vote_records or {}
    if not records and KANSAS_VOTES_FILE.exists():
        with open(KANSAS_VOTES_FILE, encoding="utf-8") as f:
            records = json.load(f)

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
        for voter in vote.get("votes") or []:
            if not isinstance(voter, dict):
                continue
            leg_id = _match_voter_name(
                voter.get("voter_name") or voter.get("name") or "",
                state,
                vote.get("organization") or "",
                by_state.get(state, []),
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
