#!/usr/bin/env python3
"""Package Georgia + Kentucky Open States caches for seed-ga-ky-r2.yml."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GA_MIN_BILLS = 8_000
KY_MIN_BILLS = 4_000
NORMALIZED_MIN_BILLS = 200_000


def _bill_count(search_index: dict, state: str) -> int:
    code = state.upper()
    return sum(
        1
        for bill in search_index.get("bills") or []
        if (bill.get("state") or "").upper() == code
    )


def _validate() -> None:
    errors: list[str] = []
    for st in ("ga", "ky"):
        cache = ROOT / "data" / "openstates" / st
        meta_path = cache / "meta.json"
        if not meta_path.is_file():
            errors.append(f"missing {meta_path}")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        bills = int((meta.get("counts") or {}).get("bills") or 0)
        if bills <= 0:
            errors.append(f"{st}: meta.json reports 0 bills")
        bill_files = list(cache.glob("bills_*.json"))
        if not bill_files:
            errors.append(f"{st}: no bills_*.json under data/openstates/{st}/")
        votes = cache / "votes.json"
        if not votes.is_file() or votes.stat().st_size < 1_000_000:
            errors.append(f"{st}: missing or tiny data/openstates/{st}/votes.json")

    norm_meta = ROOT / "data" / "normalized" / "meta.json"
    norm_index = ROOT / "data" / "normalized" / "search_index.json"
    norm_bills = ROOT / "data" / "normalized" / "bills.json"
    for path in (norm_meta, norm_index, norm_bills):
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
    if errors:
        raise SystemExit("\n".join(["Validation failed:"] + [f"  - {e}" for e in errors]))

    meta = json.loads(norm_meta.read_text(encoding="utf-8"))
    total = int((meta.get("counts") or {}).get("bills") or 0)
    if total < NORMALIZED_MIN_BILLS:
        errors.append(
            f"normalized meta counts.bills={total}; expected >= {NORMALIZED_MIN_BILLS}. "
            "Re-run normalize_data.py after importing GA and KY."
        )

    index = json.loads(norm_index.read_text(encoding="utf-8"))
    ga = _bill_count(index, "GA")
    ky = _bill_count(index, "KY")
    if ga < GA_MIN_BILLS:
        errors.append(
            f"normalized search_index has GA={ga}; expected >= {GA_MIN_BILLS}. "
            "Run: python src/processing/import_openstates_bulk.py --states ga && "
            "python src/processing/normalize_data.py --skip-ai"
        )
    if ky < KY_MIN_BILLS:
        errors.append(
            f"normalized search_index has KY={ky}; expected >= {KY_MIN_BILLS}. "
            "Run: python src/processing/import_openstates_bulk.py --states ky && "
            "python src/processing/normalize_data.py --skip-ai"
        )
    if errors:
        raise SystemExit("\n".join(["Validation failed:"] + [f"  - {e}" for e in errors]))

    print(f"OK: GA={ga} KY={ky} normalized_total={total}")


def _collect_files() -> list[Path]:
    paths: list[Path] = []
    for st in ("ga", "ky"):
        cache = ROOT / "data" / "openstates" / st
        paths.extend(sorted(p for p in cache.iterdir() if p.is_file()))
    norm_dir = ROOT / "data" / "normalized"
    paths.extend(sorted(p for p in norm_dir.glob("*.json") if p.is_file()))
    return paths


def package(output: Path) -> None:
    _validate()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _collect_files()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arc = path.relative_to(ROOT).as_posix()
            zf.write(path, arc)
            print(f"  + {arc} ({path.stat().st_size / (1024 * 1024):.1f} MB)")
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Wrote {output} ({size_mb:.1f} MB, {len(files)} files)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "openstates-ga-ky.zip",
        help="Output zip path (default: openstates-ga-ky.zip in repo root)",
    )
    args = parser.parse_args(argv)
    package(args.output.resolve())


if __name__ == "__main__":
    main(sys.argv[1:])
