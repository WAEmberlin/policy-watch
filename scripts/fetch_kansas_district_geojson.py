#!/usr/bin/env python3
"""Backward-compatible wrapper — fetches Kansas SLD lower only."""

from __future__ import annotations

from fetch_district_geojson import main

if __name__ == "__main__":
    raise SystemExit(main(["--states", "ks", "--layers", "sld-lower"]))
