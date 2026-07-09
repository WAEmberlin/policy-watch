#!/usr/bin/env python3
"""Regenerate docs/bill_url_lookup.json from normalized bills."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from processing.bill_urls import build_ks_bill_url, pick_best_bill_url  # noqa: E402

BILLS_PATH = ROOT / "data" / "normalized" / "bills.json"
OUTPUT_PATH = ROOT / "docs" / "bill_url_lookup.json"


def main() -> None:
    bills = json.loads(BILLS_PATH.read_text(encoding="utf-8"))
    candidates: dict[str, list[str]] = {}
    for bill in bills:
        state = (bill.get("state") or "").upper()
        if not state:
            continue
        bill_number = re.sub(r"\s+", "", bill.get("bill_number") or "").upper()
        url = (bill.get("url") or "").strip()
        if not bill_number or not url:
            continue
        key = f"{state}:{bill_number}"
        candidates.setdefault(key, []).append(url)

    lookup: dict[str, str] = {}
    for key, urls in candidates.items():
        state, bill_number = key.split(":", 1)
        best = pick_best_bill_url(urls, state, bill_number)
        if best:
            lookup[key] = best
        elif state == "KS":
            built = build_ks_bill_url(bill_number)
            if built:
                lookup[key] = built

    OUTPUT_PATH.write_text(json.dumps(lookup, ensure_ascii=False), encoding="utf-8")
    ks_stale = sum(1 for k, u in lookup.items() if k.startswith("KS:") and "b2023_24" in u)
    ks_org = sum(1 for k, u in lookup.items() if k.startswith("KS:") and "kslegislature.org" in u)
    print(f"Wrote {len(lookup)} URLs to {OUTPUT_PATH}")
    print(f"KS stale b2023_24: {ks_stale}, kslegislature.org: {ks_org}")


if __name__ == "__main__":
    main()
