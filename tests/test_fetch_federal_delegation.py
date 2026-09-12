"""Tests for federal delegation fetch targets and combined-file merges."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_federal_delegation import TARGET_STATES, merge_delegation  # noqa: E402


def test_georgia_is_a_federal_delegation_target():
    assert "GA" in TARGET_STATES


def test_kentucky_is_a_federal_delegation_target():
    assert "KY" in TARGET_STATES


def test_merge_delegation_replaces_requested_state_only():
    existing = [
        {"state": "KS", "chamber": "U.S. Senator", "district": "", "name": "Jerry Moran"},
        {"state": "GA", "chamber": "U.S. Senator", "district": "", "name": "Old Name"},
    ]
    incoming = [
        {"state": "GA", "chamber": "U.S. Senator", "district": "", "name": "Jon Ossoff"},
        {"state": "GA", "chamber": "U.S. Representative", "district": "5", "name": "Nikema Williams"},
    ]
    merged = merge_delegation(existing, incoming, ["GA"])
    by_state = {}
    for member in merged:
        by_state.setdefault(member["state"], []).append(member["name"])
    assert by_state["KS"] == ["Jerry Moran"]
    assert "Old Name" not in by_state["GA"]
    assert "Jon Ossoff" in by_state["GA"]
    assert "Nikema Williams" in by_state["GA"]


def test_committed_delegation_includes_georgia_house_and_senate():
    path = ROOT / "docs" / "data" / "federal" / "delegation.json"
    if not path.exists():
        return
    members = json.loads(path.read_text(encoding="utf-8"))
    ga = [member for member in members if member.get("state") == "GA"]
    reps = [member for member in ga if member.get("chamber") == "U.S. Representative"]
    senators = [member for member in ga if member.get("chamber") == "U.S. Senator"]
    assert len(reps) == 14
    assert len(senators) == 2
    districts = {str(member.get("district") or "") for member in reps}
    assert districts == {str(n) for n in range(1, 15)}


def test_committed_delegation_includes_kentucky_house_and_senate():
    path = ROOT / "docs" / "data" / "federal" / "delegation.json"
    if not path.exists():
        return
    members = json.loads(path.read_text(encoding="utf-8"))
    ky = [member for member in members if member.get("state") == "KY"]
    reps = [member for member in ky if member.get("chamber") == "U.S. Representative"]
    senators = [member for member in ky if member.get("chamber") == "U.S. Senator"]
    assert len(reps) == 6
    assert len(senators) == 2
    districts = {str(member.get("district") or "") for member in reps}
    assert districts == {str(n) for n in range(1, 7)}
