#!/usr/bin/env python3
"""
Fetch Kansas district boundaries from U.S. Census TIGER/Line.

Layers (Legislative MapServer):
  2 — 2024 State Legislative Districts - Lower (Kansas House, 125)
  1 — 2024 State Legislative Districts - Upper (Kansas Senate, 40)
  0 — 119th Congressional Districts (U.S. House, 4)

State outline (State_County MapServer layer 0) — used for U.S. Senate statewide view.

Writes canonical copies under data/geo/ and served copies under docs/data/geo/.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

SIMPLIFY_TOLERANCE = 0.001  # degrees (~100 m)

LAYERS: Tuple[Tuple[str, int, str, Tuple[str, ...]], ...] = (
    (
        "ks-sld-lower",
        2,
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/{layer}/query"
        "?where=STATE%3D%2720%27&outFields=GEOID,SLDL,NAME,BASENAME,STATE"
        "&returnGeometry=true&outSR=4326&f=geojson",
        ("GEOID", "SLDL", "NAME", "BASENAME", "STATE"),
    ),
    (
        "ks-sld-upper",
        1,
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/{layer}/query"
        "?where=STATE%3D%2720%27&outFields=GEOID,SLDU,NAME,BASENAME,STATE"
        "&returnGeometry=true&outSR=4326&f=geojson",
        ("GEOID", "SLDU", "NAME", "BASENAME", "STATE"),
    ),
    (
        "ks-cd119",
        0,
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/{layer}/query"
        "?where=STATE%3D%2720%27&outFields=GEOID,CD119,NAME,BASENAME,STATE"
        "&returnGeometry=true&outSR=4326&f=geojson",
        ("GEOID", "CD119", "NAME", "BASENAME", "STATE"),
    ),
)

STATE_LAYER_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0/query"
    "?where=STATE%3D%2720%27&outFields=GEOID,STUSAB,NAME&returnGeometry=true&outSR=4326&f=geojson"
)


def _output_paths(stem: str) -> List[Path]:
    return [
        ROOT / "data" / "geo" / f"{stem}.geojson",
        ROOT / "docs" / "data" / "geo" / f"{stem}.geojson",
    ]


def _fetch_geojson(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "policy-watch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _simplify_feature_collection(data: dict, prop_keys: Iterable[str]) -> dict:
    try:
        from shapely.geometry import mapping, shape
    except ImportError:
        print("WARNING: shapely not installed; skipping geometry simplification", file=sys.stderr)
        return data

    features = []
    for feature in data.get("features", []):
        geom = shape(feature["geometry"]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        props = feature.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "properties": {key: props.get(key) for key in prop_keys},
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _write_geojson(stem: str, data: dict) -> None:
    count = len(data.get("features", []))
    payload = json.dumps(data, separators=(",", ":"))
    for path in _output_paths(stem):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"Wrote {path} ({count} features, {len(payload) / 1024:.1f} KB)")


def main() -> int:
    errors = 0
    for stem, layer_id, url_template, prop_keys in LAYERS:
        url = url_template.format(layer=layer_id)
        try:
            data = _fetch_geojson(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"ERROR: Census download failed for {stem}: {exc}", file=sys.stderr)
            errors += 1
            continue
        if not data.get("features"):
            print(f"ERROR: Census returned no features for {stem}.", file=sys.stderr)
            errors += 1
            continue
        data = _simplify_feature_collection(data, prop_keys)
        _write_geojson(stem, data)

    try:
        state_data = _fetch_geojson(STATE_LAYER_URL)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"ERROR: Kansas state outline download failed: {exc}", file=sys.stderr)
        errors += 1
    else:
        if state_data.get("features"):
            state_data = _simplify_feature_collection(state_data, ("GEOID", "STUSAB", "NAME"))
            _write_geojson("ks-state", state_data)
        else:
            print("ERROR: Census returned no features for ks-state.", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
