#!/usr/bin/env python3
"""
Fetch legislative district boundaries from U.S. Census TIGER/Line.

Layers (Legislative MapServer):
  0 — Congressional districts (119th Congress, CD119)
  1 — State legislative districts upper (SLDU)
  2 — State legislative districts lower (SLDL)

State outlines (State_County MapServer layer 0) are used for statewide U.S. Senate views.

Writes canonical GeoJSON under data/geo/ and docs/data/geo/.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

STATES: Dict[str, Dict[str, str]] = {
    "ks": {"fips": "20", "name": "Kansas"},
    "co": {"fips": "08", "name": "Colorado"},
    "az": {"fips": "04", "name": "Arizona"},
    "ut": {"fips": "49", "name": "Utah"},
    "me": {"fips": "23", "name": "Maine"},
    "ne": {"fips": "31", "name": "Nebraska"},
    "md": {"fips": "24", "name": "Maryland"},
    "pa": {"fips": "42", "name": "Pennsylvania"},
    "ma": {"fips": "25", "name": "Massachusetts"},
    "wv": {"fips": "54", "name": "West Virginia"},
    "tn": {"fips": "47", "name": "Tennessee"},
    "nc": {"fips": "37", "name": "North Carolina"},
    "mo": {"fips": "29", "name": "Missouri"},
    "ia": {"fips": "19", "name": "Iowa"},
}

LAYERS: Dict[str, Dict[str, object]] = {
    "cd119": {
        "server": "legislative",
        "layer_id": 0,
        "district_field": "CD119",
        "out_suffix": "cd119",
    },
    "sld-upper": {
        "server": "legislative",
        "layer_id": 1,
        "district_field": "SLDU",
        "out_suffix": "sld-upper",
    },
    "sld-lower": {
        "server": "legislative",
        "layer_id": 2,
        "district_field": "SLDL",
        "out_suffix": "sld-lower",
    },
    "state": {
        "server": "state",
        "layer_id": 0,
        "district_field": None,
        "out_suffix": "state",
    },
}

LEGISLATIVE_BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"
)
STATE_BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer"

SIMPLIFY_TOLERANCE = 0.001  # degrees (~100 m)


def _build_query_url(layer_key: str, state_fips: str) -> str:
    layer = LAYERS[layer_key]
    if layer["server"] == "legislative":
        base = f"{LEGISLATIVE_BASE}/{layer['layer_id']}/query"
        district_field = layer["district_field"]
        out_fields = f"GEOID,{district_field},NAME,BASENAME,STATE"
    else:
        base = f"{STATE_BASE}/{layer['layer_id']}/query"
        out_fields = "GEOID,NAME,STATE"

    return (
        f"{base}?where=STATE%3D%27{state_fips}%27"
        f"&outFields={out_fields}"
        "&returnGeometry=true&outSR=4326&f=geojson"
    )


def _fetch_geojson(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "policy-watch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _simplify_feature_collection(data: dict, district_field: str | None) -> dict:
    try:
        from shapely.geometry import mapping, shape
    except ImportError:
        print("WARNING: shapely not installed; skipping geometry simplification", file=sys.stderr)
        return data

    features = []
    for feature in data.get("features", []):
        geom = shape(feature["geometry"]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        props = feature.get("properties") or {}
        clean = {
            "GEOID": props.get("GEOID"),
            "NAME": props.get("NAME"),
            "BASENAME": props.get("BASENAME"),
            "STATE": props.get("STATE"),
        }
        if district_field:
            clean[district_field] = props.get(district_field)
        features.append(
            {
                "type": "Feature",
                "properties": {k: v for k, v in clean.items() if v is not None},
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _output_paths(state_code: str, suffix: str) -> List[Path]:
    filename = f"{state_code}-{suffix}.geojson"
    return [
        ROOT / "data" / "geo" / filename,
        ROOT / "docs" / "data" / "geo" / filename,
    ]


def fetch_layer(state_code: str, layer_key: str) -> Tuple[int, int]:
    state_code = state_code.lower()
    if state_code not in STATES:
        raise ValueError(f"Unknown state code: {state_code}")

    layer = LAYERS[layer_key]
    state_fips = STATES[state_code]["fips"]
    url = _build_query_url(layer_key, state_fips)
    data = _fetch_geojson(url)

    count = len(data.get("features", []))
    if count == 0:
        raise RuntimeError(f"Census returned no features for {state_code.upper()} {layer_key}")

    district_field = layer.get("district_field")
    data = _simplify_feature_collection(data, district_field if isinstance(district_field, str) else None)
    payload = json.dumps(data, separators=(",", ":"))
    size_kb = len(payload) / 1024

    for path in _output_paths(state_code, str(layer["out_suffix"])):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"Wrote {path} ({count} features, {size_kb:.1f} KB)")

    return count, int(size_kb)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Census TIGER district GeoJSON")
    parser.add_argument(
        "--states",
        default=",".join(STATES.keys()),
        help="Comma-separated state codes (default: all configured states)",
    )
    parser.add_argument(
        "--layers",
        default="sld-lower,sld-upper,cd119,state",
        help="Comma-separated layer keys: sld-lower, sld-upper, cd119, state",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    state_codes = [s.strip().lower() for s in args.states.split(",") if s.strip()]
    layer_keys = [layer.strip() for layer in args.layers.split(",") if layer.strip()]

    unknown_layers = [layer for layer in layer_keys if layer not in LAYERS]
    if unknown_layers:
        print(f"ERROR: Unknown layers: {', '.join(unknown_layers)}", file=sys.stderr)
        return 1

    errors = 0
    for state_code in state_codes:
        if state_code not in STATES:
            print(f"ERROR: Unknown state code: {state_code}", file=sys.stderr)
            errors += 1
            continue
        for layer_key in layer_keys:
            # Nebraska is unicameral — Census has upper (SLDU) districts only.
            if state_code == "ne" and layer_key == "sld-lower":
                print(f"Skipping {state_code.upper()} {layer_key} (unicameral legislature)")
                continue
            try:
                fetch_layer(state_code, layer_key)
            except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print(f"ERROR: {state_code.upper()} {layer_key}: {exc}", file=sys.stderr)
                errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
