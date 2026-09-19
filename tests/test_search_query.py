"""Bill-number search queries match the number field only."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BILL_NUMBER_QUERY_RE = re.compile(
    r"^\d{2,6}[A-Za-z]?$|^[A-Za-z.]{1,10}\s*\d{1,6}[A-Za-z]?$",
    re.I,
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace(".", "")).strip()


def _number_haystack(bill_number: str) -> str:
    spaced = _normalize(bill_number)
    compact = spaced.replace(" ", "")
    return f"{spaced} {compact}" if compact and compact != spaced else spaced


def _number_matches(bill_number: str, query: str) -> bool:
    number_query = _normalize(query)
    hay = _number_haystack(bill_number)
    compact = number_query.replace(" ", "")
    return number_query in hay or (compact != number_query and compact in hay)


def test_bill_number_query_detection():
    for query in ("147", "HR 147", "hr147", "H.R. 147", "SJR11", "HB 147A"):
        assert BILL_NUMBER_QUERY_RE.match(query), query
    for query in ("veteran", "housing", "147th", "Medal of Honor", "VA healthcare"):
        assert not BILL_NUMBER_QUERY_RE.match(query), query


def test_bill_number_field_only_matching():
    assert _number_matches("HR 147", "147")
    assert _number_matches("H 1470", "147")
    assert _number_matches("SB 2147", "147")
    assert _number_matches("HR 147", "HR147")
    assert _number_matches("H.R. 147", "hr 147")
    assert not _number_matches("HR 100", "147")
    title_only = "A bill to study the 147th fighter wing"
    assert "147" in title_only.lower()
    assert not _number_matches("HR 100", "147")


def test_client_and_worker_use_number_only_path():
    script = (ROOT / "docs" / "script.js").read_text(encoding="utf-8")
    worker = (ROOT / "workers" / "policywatch-api" / "src" / "index.ts").read_text(encoding="utf-8")
    for source in (script, worker):
        assert "function isBillNumberQuery" in source
        assert "function billNumberSearchText" in source
        assert r"^\d{2,6}[A-Za-z]?$" in source
        assert "billMatchesQuery" in source or "billNumberQueryMatches" in source
    assert "if (numberOnly) return billNumberQueryMatches" in script
    assert "if (isBillNumberQuery(query))" in worker
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    vets = (ROOT / "docs" / "veterans.html").read_text(encoding="utf-8")
    assert "script.js?v=billnum1" in html
    assert "script.js?v=billnum1" in vets
    api_docs = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
    assert "bill number** field only" in api_docs
