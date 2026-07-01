#!/usr/bin/env python3
"""
Fetch Kansas State House (SLD lower) district boundaries from U.S. Census TIGER/Line.

Source: Census TIGERweb Legislative MapServer layer 2 (2024 SLD lower, Jan 2025 vintage).
  https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/2

Writes:
  - data/geo/ks-sld-lower.geojson (canonical)
  - docs/data/geo/ks-sld-lower.geojson (served by static site)

Manual fallback if automated download is blocked:
  1. Open the Census query URL below in a browser and save the JSON response.
  2. Place it at data/geo/ks-sld-lower.geojson and copy to docs/data/geo/.
  3. Or download tl_2024_20_sldl.zip from
     https://www2.census.gov/geo/tiger/TIGER2024/SLDL/ and convert with ogr2ogr:
       ogr2ogr -f GeoJSON -t_srs EPSG:4326 ks-sld-lower.geojson tl_2024_20_sldl.shp
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATHS = [
    ROOT / "data" / "geo" / "ks-sld-lower.geojson",
    ROOT / "docs" / "data" / "geo" / "ks-sld-lower.geojson",
]

CENSUS_QUERY = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/2/query"
    "?where=STATE%3D%2720%27"
    "&outFields=GEOID,SLDL,NAME,BASENAME,STATE"
    "&returnGeometry=true&outSR=4326&f=geojson"
)

SIMPLIFY_TOLERANCE = 0.001  # degrees (~100 m); keeps file ~200 KB


def _fetch_geojson() -> dict:
    req = urllib.request.Request(CENSUS_QUERY, headers={"User-Agent": "policy-watch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _simplify_feature_collection(data: dict) -> dict:
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
                "properties": {
                    "GEOID": props.get("GEOID"),
                    "SLDL": props.get("SLDL"),
                    "NAME": props.get("NAME"),
                    "BASENAME": props.get("BASENAME"),
                    "STATE": props.get("STATE"),
                },
                "geometry": mapping(geom),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main() -> int:
    try:
        data = _fetch_geojson()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"ERROR: Census download failed: {exc}", file=sys.stderr)
        print("See script docstring for manual fallback.", file=sys.stderr)
        return 1

    count = len(data.get("features", []))
    if count == 0:
        print("ERROR: Census returned no features for Kansas SLD lower.", file=sys.stderr)
        return 1

    data = _simplify_feature_collection(data)
    payload = json.dumps(data, separators=(",", ":"))

    for path in OUTPUT_PATHS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"Wrote {path} ({count} features, {len(payload) / 1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
