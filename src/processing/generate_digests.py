#!/usr/bin/env python3
"""Generate weekly digests by jurisdiction."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.ai_enrichment import generate_detailed_summary, generate_impact_analysis  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"
NORMALIZED_DIR = ROOT / "data" / "normalized"
DIGESTS_DIR = ROOT / "data" / "digests"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_digest(
    bills: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    votes: List[Dict[str, Any]],
    label: str,
    state_filter: str | None = None,
    level_filter: str | None = None,
) -> Dict[str, Any]:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    def is_recent(item: Dict[str, Any], field: str) -> bool:
        val = item.get(field, "")
        if not val:
            return False
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= week_ago
        except ValueError:
            return False

    filtered_bills = bills
    if state_filter:
        filtered_bills = [b for b in filtered_bills if b.get("state") == state_filter]
    if level_filter:
        filtered_bills = [b for b in filtered_bills if b.get("level") == level_filter]

    recent_bills = [b for b in filtered_bills if is_recent(b, "latest_action_date") or is_recent(b, "updated_at")]
    recent_bills.sort(key=lambda x: x.get("latest_action_date", ""), reverse=True)

    filtered_events = events
    if state_filter:
        filtered_events = [e for e in filtered_events if e.get("state") == state_filter]
    if level_filter == "federal":
        filtered_events = [e for e in filtered_events if e.get("level") == "federal"]

    recent_events = [e for e in filtered_events if is_recent(e, "scheduled_date")]

    filtered_votes = votes
    if state_filter:
        filtered_votes = [v for v in filtered_votes if v.get("state") == state_filter]

    important_bills = recent_bills[:10]
    analysis_lines = []
    for bill in important_bills[:5]:
        analysis_lines.append(generate_impact_analysis(bill))

    return {
        "label": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": 7,
        "summary": {
            "total_bills": len(recent_bills),
            "total_events": len(recent_events),
            "total_votes": len(filtered_votes),
        },
        "important_bills": [
            {
                "bill_number": b.get("bill_number"),
                "title": b.get("title"),
                "latest_action": b.get("latest_action"),
                "url": b.get("url"),
                "ai_summary": generate_detailed_summary(b),
            }
            for b in important_bills
        ],
        "major_votes": filtered_votes[:10],
        "committee_activity": recent_events[:10],
        "ai_analysis": "\n".join(analysis_lines) if analysis_lines else "No significant activity this week.",
    }


def main() -> None:
    config = yaml.safe_load(open(CONFIG_PATH, encoding="utf-8"))
    bills = load_json(NORMALIZED_DIR / "bills.json", [])
    events = load_json(NORMALIZED_DIR / "events.json", [])
    votes = load_json(NORMALIZED_DIR / "votes.json", [])

    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)

    digests = {
        "federal": build_digest(bills, events, votes, "Federal Weekly Digest", level_filter="federal"),
    }

    for state_cfg in config.get("states", []):
        if not state_cfg.get("enabled"):
            continue
        code = state_cfg["code"].upper()
        digests[code.lower()] = build_digest(
            bills, events, votes,
            f"{state_cfg.get('name', code)} Weekly Digest",
            state_filter=code,
        )

    out_path = DIGESTS_DIR / "weekly.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(digests, f, indent=2, ensure_ascii=False)

    print(f"Generated weekly digests for {len(digests)} jurisdictions -> {out_path}")


if __name__ == "__main__":
    main()
