#!/usr/bin/env python3
"""
Fetch Arizona bill updates from the Cactus Watch public API.

API docs: https://github.com/az-civic-tools/az-civic-tools/wiki/Cactus-Watch-API-Reference
Live API host: https://api.cactus.watch (not cactus.watch — that serves the web UI).

Writes:
  - data/arizona/enrichments.json  (latest bill snapshot keyed by bill number)
  - data/arizona/cactus_meta.json  (last sync timestamp)
  - src/output/history.json        (recent bill actions as feed items)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from processing.feed_history_utils import merge_with_history, save_history  # noqa: E402

CONFIG_PATH = ROOT / "config" / "state_feeds.yaml"
DATA_DIR = ROOT / "data" / "arizona"
ENRICHMENTS_FILE = DATA_DIR / "enrichments.json"
META_FILE = DATA_DIR / "cactus_meta.json"

USER_AGENT = "CivicWatch/1.0 (+https://github.com/WAEmberlin/policy-watch)"
BILL_NUMBER_RE = re.compile(r"^([A-Za-z]+)\s*(\d+[A-Za-z]?)$")


def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f).get("arizona_cactus", {})


def normalize_az_bill_number(raw: str) -> str:
    """HB2839 -> HB 2839 for CivicWatch lookup keys."""
    text = (raw or "").strip().upper().replace(".", "")
    match = BILL_NUMBER_RE.match(text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return text


def parse_api_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def bill_to_enrichment(bill: Dict[str, Any]) -> Dict[str, Any]:
    number = normalize_az_bill_number(bill.get("number", ""))
    return {
        "bill_number": number,
        "title": bill.get("short_title") or bill.get("description") or "",
        "summary": bill.get("overview") or bill.get("description") or "",
        "latest_action": bill.get("last_action") or "",
        "latest_action_date": parse_api_datetime(bill.get("last_action_date")),
        "status": bill.get("status") or "",
        "sponsor": bill.get("sponsor") or "",
        "chamber": bill.get("chamber") or "",
        "url": bill.get("azleg_url") or "",
        "source": "arizona_cactus",
        "updated_at": parse_api_datetime(bill.get("updated_at")),
        "has_hearing": bool(bill.get("has_hearing")),
    }


def bill_to_history_item(bill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    number = normalize_az_bill_number(bill.get("number", ""))
    url = bill.get("azleg_url") or ""
    if not number or not url:
        return None

    title_text = bill.get("short_title") or bill.get("description") or number
    published = (
        parse_api_datetime(bill.get("last_action_date"))
        or parse_api_datetime(bill.get("updated_at"))
        or datetime.now(timezone.utc).isoformat()
    )
    action = bill.get("last_action") or "Bill updated"
    item_id = f"az-cactus:{number}:{published[:19]}"

    return {
        "id": item_id,
        "title": f"{number}: {title_text}",
        "summary": action,
        "link": url,
        "published": published,
        "source": "State (Arizona)",
        "category": "Bills",
        "type": "state_legislation",
        "state": "AZ",
        "feed": "arizona_cactus",
        "bill_number": number,
        "bill_url": url,
        "latest_action": action,
    }


def fetch_sync_bills(base_url: str, sync_path: str, since_date: str) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{sync_path}"
    response = requests.get(
        url,
        params={"since": since_date},
        timeout=120,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()
    bills = payload.get("bills") if isinstance(payload, dict) else payload
    return bills if isinstance(bills, list) else []


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> None:
    cfg = load_config()
    base_url = cfg.get("base_url", "https://api.cactus.watch")
    sync_path = cfg.get("sync_path", "/api/bills/sync")
    initial_days = int(cfg.get("initial_sync_days", 30))

    meta = load_json(META_FILE, {})
    now = datetime.now(timezone.utc)
    last_sync = meta.get("last_sync")
    if last_sync:
        since_dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00")) - timedelta(days=1)
    else:
        since_dt = now - timedelta(days=initial_days)
    since_date = since_dt.date().isoformat()

    print(f"Fetching Arizona Cactus Watch sync since {since_date}...")
    bills = fetch_sync_bills(base_url, sync_path, since_date)
    print(f"Received {len(bills)} updated bills")

    enrichments = load_json(ENRICHMENTS_FILE, {})
    if not isinstance(enrichments, dict):
        enrichments = {}
    if "_meta" not in enrichments:
        enrichments["_meta"] = {}

    history_items: List[Dict[str, Any]] = []
    cutoff = since_dt
    for bill in bills:
        if not isinstance(bill, dict):
            continue
        number = normalize_az_bill_number(bill.get("number", ""))
        if not number:
            continue
        enrichments[number] = bill_to_enrichment(bill)

        action_dt_raw = bill.get("last_action_date")
        if not action_dt_raw:
            continue
        try:
            action_dt = datetime.fromisoformat(str(action_dt_raw).replace("Z", "+00:00"))
            if action_dt.tzinfo is None:
                action_dt = action_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if action_dt < cutoff:
            continue

        item = bill_to_history_item(bill)
        if item:
            history_items.append(item)

    enrichments["_meta"].update({
        "source": "cactus_watch",
        "api_base": base_url,
        "last_sync": now.isoformat(),
        "since_date": since_date,
        "bills_synced": len(bills),
        "bill_count": len([k for k in enrichments if not k.startswith("_")]),
    })
    save_json(ENRICHMENTS_FILE, enrichments)
    save_json(META_FILE, {"last_sync": now.isoformat(), "since_date": since_date, "count": len(bills)})

    if history_items:
        combined = merge_with_history(history_items)
        combined.sort(key=lambda x: x.get("published", ""), reverse=True)
        save_history(combined)

    print(f"Saved Arizona enrichments ({enrichments['_meta']['bill_count']} bills tracked)")


if __name__ == "__main__":
    main()
