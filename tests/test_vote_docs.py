"""Tests for vote/bill docs rebuild helpers."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.vote_docs import (  # noqa: E402
    build_bill_lookups,
    merge_vote_indexes,
    vote_counts_by_state,
    write_bill_lookup_docs,
    write_legislator_vote_docs,
)


def test_merge_vote_indexes_trims_and_sorts():
    a = {
        "leg-1": [
            {"date": "2026-01-01", "bill_number": "HB1"},
            {"date": "2026-03-01", "bill_number": "HB2"},
        ]
    }
    b = {"leg-1": [{"date": "2026-02-01", "bill_number": "HB3"}]}
    merged = merge_vote_indexes([a, b], max_per_legislator=2)
    assert [row["bill_number"] for row in merged["leg-1"]] == ["HB2", "HB3"]


def test_vote_counts_by_state():
    legislators = [
        {"id": "a", "state": "PA"},
        {"id": "b", "state": "md"},
        {"id": "c", "state": "PA"},
    ]
    votes = {"a": [{"x": 1}], "b": [{"x": 1}, {"x": 2}], "c": []}
    assert vote_counts_by_state(votes, legislators) == {"MD": 1, "PA": 1}


def test_write_legislator_vote_docs(tmp_path):
    docs = tmp_path / "docs"
    norm = tmp_path / "normalized"
    stats = write_legislator_vote_docs(
        {"leg-1": [{"date": "2026-01-01"}], "leg-2": []},
        docs_dir=docs,
        normalized_dir=norm,
        write_normalized=True,
    )
    assert stats["legislators_with_votes"] == 1
    counts = json.loads((docs / "legislator_vote_counts.json").read_text(encoding="utf-8"))
    assert counts == {"leg-1": 1}
    assert (norm / "legislator_votes.json").is_file()


def test_build_bill_lookups_prefers_official_url():
    titles, urls = build_bill_lookups(
        [
            {
                "state": "PA",
                "bill_number": "HB 1",
                "title": "Test bill",
                "url": "https://openstates.org/bills/x/",
                "_url_candidates": [
                    "https://openstates.org/bills/x/",
                    "https://www.palegis.us/legislation/bills/2025/hb1",
                ],
            }
        ]
    )
    assert titles["PA:HB1"] == "Test bill"
    assert "palegis.us" in urls["PA:HB1"]


def test_write_bill_lookup_docs(tmp_path):
    docs = tmp_path / "docs"
    stats = write_bill_lookup_docs({"PA:HB1": "Title"}, {"PA:HB1": "https://example.com"}, docs_dir=docs)
    assert stats["titles"] == 1
    assert (docs / "bill_title_lookup.json").is_file()
