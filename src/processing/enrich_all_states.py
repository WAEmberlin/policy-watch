#!/usr/bin/env python3
"""Orchestrate state-level enrichment pipelines."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.enrich_kansas_api import enrich_kansas_bills  # noqa: E402
from processing.enrich_openstates_detail import enrich_all_openstates  # noqa: E402

CONFIG_PATH = ROOT / "config" / "states.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all configured state enrichments")
    parser.add_argument("--kansas-max", type=int, default=75)
    parser.add_argument("--skip-kansas", action="store_true")
    parser.add_argument("--skip-openstates", action="store_true")
    args = parser.parse_args()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not args.skip_kansas:
        print("=== Kansas official API enrichment ===")
        enrich_kansas_bills(max_per_run=args.kansas_max)

    if not args.skip_openstates:
        print("\n=== Open States detail enrichment (CO, AZ, UT) ===")
        enrich_all_openstates()

    print("\nAll enrichments complete.")


if __name__ == "__main__":
    main()
