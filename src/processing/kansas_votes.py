"""Normalize Kansas Legislature roll-call vote records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

KANSAS_BIENNIUM = "b2025_26"
MEMBER_BASE = f"https://www.kslegislature.gov/{KANSAS_BIENNIUM}/members"


def member_profile_url(kpid: str) -> str:
    if not kpid:
        return ""
    return f"{MEMBER_BASE}/{kpid}/"


def normalize_member_list(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            kpid = item.get("kpid") or ""
            name = item.get("name") or ""
            if name:
                out.append({"kpid": kpid, "name": name, "url": member_profile_url(kpid)})
    out.sort(key=lambda m: m["name"].lower())
    return out


def normalize_vote_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize list-endpoint vote row (may lack member names)."""
    journal = raw.get("journal_element") or {}
    return {
        "apn": raw.get("apn") or "",
        "bill_number": raw.get("bill_no") or raw.get("bill_number") or "",
        "chamber": (raw.get("chamber") or "").lower(),
        "rcs_num": raw.get("rcs_num") or "",
        "result": journal.get("action_label") or raw.get("action_label") or raw.get("motion") or "",
        "date": journal.get("occurred") or raw.get("occurred") or "",
        "tally": raw.get("tally") or raw.get("vote_tally") or {},
        "members": None,
    }


def normalize_vote_detail(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize detail-endpoint vote with per-member breakdown."""
    summary = normalize_vote_summary(raw)
    members_raw = raw.get("members") or {}
    if isinstance(members_raw, dict):
        summary["members"] = {
            "yea": normalize_member_list(members_raw.get("yea")),
            "nay": normalize_member_list(members_raw.get("nay")),
            "present": normalize_member_list(members_raw.get("present")),
            "absent": normalize_member_list(members_raw.get("absent")),
            "not_voting": normalize_member_list(members_raw.get("not_voting")),
        }
    return summary


def merge_vote_record(existing: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing or {})
    merged.update({k: v for k, v in new.items() if v is not None})
    if new.get("members"):
        merged["members"] = new["members"]
    return merged
