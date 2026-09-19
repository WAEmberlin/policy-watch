#!/usr/bin/env python3
"""
Send Policy Watch email digests.

Recipients are assigned via GitHub secret EMAIL_DIGEST_RECIPIENTS (JSON).
policywatchadmin@gmail.com is always BCC'd on every digest.
Addresses are sent using BCC so recipients cannot see each other.

Legacy: EMAIL_TO still works as the recipient list for the "all" digest only.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from collections import Counter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.email_digest import (  # noqa: E402
    build_digest_html,
    infer_item_state,
    load_digest_config,
    load_recent_items,
    load_state_names,
    load_tomorrow_hearings,
    partition_by_state,
    partition_hearings,
)
from processing.fetch_kansas_rss import enrich_history_file  # noqa: E402

EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_FROM = os.environ.get("EMAIL_FROM") or EMAIL_USER
EMAIL_TO = os.environ.get("EMAIL_TO")  # legacy fallback for "all" digest
DEFAULT_OPS_ALERT = "policywatchadmin@gmail.com"
DEFAULT_DIGEST_RECIPIENT = DEFAULT_OPS_ALERT


def _dedupe_addresses(addrs: List[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for addr in addrs:
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(addr)
    return unique


def _with_default_digest_recipient(addrs: List[str]) -> List[str]:
    merged = list(addrs)
    if not any(addr.lower() == DEFAULT_DIGEST_RECIPIENT.lower() for addr in merged):
        merged.append(DEFAULT_DIGEST_RECIPIENT)
    return _dedupe_addresses(merged)


def parse_recipient_config() -> Dict[str, List[str]]:
    """
    Load recipient lists from EMAIL_DIGEST_RECIPIENTS (JSON secret).

    Digest IDs come from config/email_digests.yaml (each tracked state, federal, all).
    Also supports per-digest env vars: EMAIL_RECIPIENTS_KS, etc.
    policywatchadmin@gmail.com is always included on every digest.
    """
    digest_cfg = load_digest_config()
    recipients: Dict[str, List[str]] = {
        d["id"]: [] for d in digest_cfg.get("digests", []) if d.get("id")
    }
    if "federal" not in recipients:
        recipients["federal"] = []
    if "all" not in recipients:
        recipients["all"] = []

    raw = os.environ.get("EMAIL_DIGEST_RECIPIENTS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key, addrs in parsed.items():
                    key_lower = key.lower()
                    if key_lower not in recipients:
                        recipients[key_lower] = []
                    if isinstance(addrs, str):
                        recipients[key_lower] = [a.strip() for a in addrs.split(",") if a.strip()]
                    elif isinstance(addrs, list):
                        recipients[key_lower] = [str(a).strip() for a in addrs if str(a).strip()]
        except json.JSONDecodeError as exc:
            print(f"WARNING: EMAIL_DIGEST_RECIPIENTS is not valid JSON: {exc}")

    # Per-digest env var overrides (useful in GitHub Actions secrets)
    for digest_id in list(recipients.keys()):
        env_key = f"EMAIL_RECIPIENTS_{digest_id.upper()}"
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            recipients[digest_id] = [a.strip() for a in env_val.split(",") if a.strip()]

    # Legacy EMAIL_TO → "all" digest if not configured
    if EMAIL_TO and not recipients["all"]:
        recipients["all"] = [a.strip() for a in EMAIL_TO.split(",") if a.strip()]

    return {
        digest_id: _with_default_digest_recipient(addrs)
        for digest_id, addrs in recipients.items()
    }


def ops_alert_recipients() -> List[str]:
    raw = (os.environ.get("EMAIL_OPS_ALERT") or DEFAULT_OPS_ALERT).strip()
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_ops_alert(
    body: str,
    *,
    subject: str = "PolicyWatch email job: Open States restore failed",
    dry_run: bool = False,
) -> None:
    """Send a plain-text ops alert. Used when R2 restore fails but digests still send."""
    to_addrs = ops_alert_recipients()
    if not to_addrs:
        raise ValueError("No ops alert recipient (set EMAIL_OPS_ALERT)")
    if dry_run:
        print(f"[DRY RUN] Would send ops alert to {', '.join(to_addrs)}: {subject}")
        print(body)
        return
    if not all([EMAIL_HOST, EMAIL_USER, EMAIL_PASS, EMAIL_FROM]):
        raise ValueError("Missing SMTP configuration for ops alert")

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, to_addrs, msg.as_string())
    print(f"Sent ops alert to {len(to_addrs)} recipient(s) — subject: {subject}")


def send_digest_bcc(subject: str, html_body: str, bcc_recipients: List[str]) -> None:
    """Send email using BCC so recipients cannot see each other's addresses."""
    if not bcc_recipients:
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_FROM
    # Visible To line is the sending account only — real recipients are on BCC envelope
    msg["To"] = EMAIL_FROM
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    # Do not set Bcc header (avoids leaking addresses in some clients)
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, bcc_recipients, msg.as_string())


def send_all_digests(digest_filter: str | None = None, dry_run: bool = False) -> int:
    if not dry_run and not all([EMAIL_HOST, EMAIL_USER, EMAIL_PASS]):
        missing = [k for k, v in {
            "EMAIL_HOST": EMAIL_HOST,
            "EMAIL_USER": EMAIL_USER,
            "EMAIL_PASS": EMAIL_PASS,
        }.items() if not v]
        raise ValueError(f"Missing required SMTP configuration: {', '.join(missing)}")

    print("Enriching Kansas bills with short titles...")
    try:
        enrich_history_file()
    except Exception as exc:
        print(f"Warning: Could not enrich Kansas bills: {exc}")

    cfg = load_digest_config()
    window = cfg.get("window_hours", 6)
    recipients = parse_recipient_config()
    state_names = load_state_names()

    items = load_recent_items(window_hours=window)
    hearings = load_tomorrow_hearings()
    items_by_state = partition_by_state(items)
    hearings_by_state = partition_hearings(hearings)
    jurisdiction_counts = Counter(infer_item_state(item) or "OTHER" for item in items)
    print(
        f"Loaded {len(items)} recent items by jurisdiction: "
        + ", ".join(f"{code}={count}" for code, count in sorted(jurisdiction_counts.items()))
    )

    sent_count = 0
    digest_ids = [d["id"] for d in cfg.get("digests", [])]
    if digest_filter:
        digest_ids = [digest_filter]

    for digest_id in digest_ids:
        bcc = recipients.get(digest_id, [])
        if not bcc:
            print(f"Skipping digest '{digest_id}' — no recipients configured")
            continue

        html, subject, total = build_digest_html(
            digest_id, items_by_state, hearings_by_state, state_names
        )
        if total == 0:
            print(f"Skipping digest '{digest_id}' — no items in window")
            continue

        if dry_run:
            print(f"[DRY RUN] Would send '{digest_id}' to {len(bcc)} recipient(s): subject={subject}")
            sent_count += 1
            continue

        try:
            send_digest_bcc(subject, html, bcc)
            print(f"Sent '{digest_id}' digest to {len(bcc)} recipient(s) — subject: {subject} ({total} items)")
            sent_count += 1
        except Exception as exc:
            print(f"ERROR sending '{digest_id}' digest: {exc}")
            raise

    if sent_count == 0:
        print("No digests sent. Configure EMAIL_DIGEST_RECIPIENTS or EMAIL_RECIPIENTS_* secrets.")
        print("See EMAIL_DIGEST_SETUP.md for instructions.")

    return sent_count


def _digest_ids() -> List[str]:
    cfg = load_digest_config()
    return [d["id"] for d in cfg.get("digests", []) if d.get("id")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Policy Watch email digests")
    parser.add_argument(
        "--digest",
        choices=_digest_ids(),
        help="Send only one digest type (default: send all configured digests)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent without emailing")
    parser.add_argument(
        "--ops-alert",
        action="store_true",
        help="Send an ops alert email instead of digests (used when R2 restore fails)",
    )
    parser.add_argument(
        "--ops-alert-file",
        help="Optional file whose contents are included in the ops alert body",
    )
    parser.add_argument(
        "--ops-alert-message",
        default="",
        help="Optional extra message for the ops alert body",
    )
    args = parser.parse_args()

    if args.ops_alert:
        parts = [
            args.ops_alert_message.strip(),
            "Open States bills.json could not be restored from R2.",
            "Digest email still ran using committed history/legislation/home_feed.",
            "State updates (MA/MO/IA and other Open States jurisdictions) may be missing.",
        ]
        if args.ops_alert_file:
            path = Path(args.ops_alert_file)
            if path.is_file():
                parts.append("Restore log:")
                parts.append(path.read_text(encoding="utf-8", errors="replace")[:4000])
        send_ops_alert("\n\n".join(part for part in parts if part), dry_run=args.dry_run)
        return

    sent = send_all_digests(digest_filter=args.digest, dry_run=args.dry_run)
    if sent == 0 and not args.dry_run:
        sys.exit(0)  # Not a failure — may simply have no recipients yet


if __name__ == "__main__":
    main()
