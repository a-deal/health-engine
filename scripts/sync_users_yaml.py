#!/usr/bin/env python3
"""Sync user registry from SQLite to OpenClaw config files.

SQLite (person table) is the canonical source of truth.
This script generates:
  1. ~/.openclaw/workspace/users.yaml  — user routing for the agent
  2. Updates openclaw.json channel allowlists — who can message on which channel

Each user has exactly ONE channel. If channel=telegram, they're in the
Telegram allowlist only. If channel=whatsapp, WhatsApp only.

Usage:
    python3 scripts/sync_users_yaml.py           # write everything
    python3 scripts/sync_users_yaml.py --dry-run  # print without writing
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from engine.gateway.db import get_active_users, init_db

USERS_YAML = Path.home() / ".openclaw" / "workspace" / "users.yaml"
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"


def generate_users_yaml(users: list[dict]) -> str:
    """Generate users.yaml content from user list."""
    yaml_users = {}
    for u in users:
        phone = u["phone"]
        if not phone:
            continue

        entry = {"user_id": u["user_id"], "name": u["name"]}

        if u["role"] and u["role"] != "user":
            entry["role"] = u["role"]
        if u["email"]:
            entry["email"] = u["email"]
        if u["channel"]:
            entry["channel"] = u["channel"]
        if u["channel_target"]:
            entry["channel_target"] = u["channel_target"]
        if u["timezone"] and u["timezone"] != "America/Los_Angeles":
            entry["timezone"] = u["timezone"]

        yaml_users[phone] = entry

    header = (
        "# User registry — auto-generated from SQLite (person table).\n"
        "# Do not edit manually. Run: python3 scripts/sync_users_yaml.py\n"
        "# Canonical source: data/kasane.db -> person table\n\n"
    )
    body = yaml.dump({"users": yaml_users}, default_flow_style=False, sort_keys=False)
    return header + body


def update_openclaw_allowlists(users: list[dict], dry_run: bool = False) -> dict:
    """Update openclaw.json channel allowlists from SQLite user data.

    Each user appears in exactly one channel's allowFrom list,
    based on their person.channel value.

    Returns summary of changes.
    """
    if not OPENCLAW_JSON.exists():
        return {"error": "openclaw.json not found"}

    with open(OPENCLAW_JSON) as f:
        config = json.load(f)

    channels = config.get("channels", {})
    changes = {}

    # Build allowlists from SQLite
    whatsapp_allow = []
    telegram_allow = []

    for u in users:
        if u["channel"] == "whatsapp" and u["phone"]:
            whatsapp_allow.append(u["phone"])
        elif u["channel"] == "telegram" and u["channel_target"]:
            telegram_allow.append(u["channel_target"])

    # Compare and update WhatsApp
    if "whatsapp" in channels:
        old = set(channels["whatsapp"].get("allowFrom", []))
        new = set(whatsapp_allow)
        if old != new:
            added = new - old
            removed = old - new
            changes["whatsapp"] = {
                "added": list(added),
                "removed": list(removed),
            }
            if not dry_run:
                channels["whatsapp"]["allowFrom"] = whatsapp_allow

    # Compare and update Telegram
    if "telegram" in channels:
        old = set(channels["telegram"].get("allowFrom", []))
        new = set(telegram_allow)
        if old != new:
            added = new - old
            removed = old - new
            changes["telegram"] = {
                "added": list(added),
                "removed": list(removed),
            }
            if not dry_run:
                channels["telegram"]["allowFrom"] = telegram_allow

    if not dry_run and changes:
        config["channels"] = channels
        with open(OPENCLAW_JSON, "w") as f:
            json.dump(config, f, indent=2)

    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    users = get_active_users()

    # 1. Generate users.yaml
    content = generate_users_yaml(users)
    if args.dry_run:
        print("=== users.yaml ===")
        print(content)
    else:
        USERS_YAML.parent.mkdir(parents=True, exist_ok=True)
        USERS_YAML.write_text(content)
        print("Wrote %s" % USERS_YAML)

    # 2. Update openclaw.json allowlists
    changes = update_openclaw_allowlists(users, dry_run=args.dry_run)
    if changes:
        if "error" in changes:
            print("Allowlist update skipped: %s" % changes["error"])
        else:
            for ch, diff in changes.items():
                if diff.get("added"):
                    print("%s allowlist added: %s" % (ch, ", ".join(diff["added"])))
                if diff.get("removed"):
                    print("%s allowlist removed: %s" % (ch, ", ".join(diff["removed"])))
            if args.dry_run:
                print("(dry run, no changes written)")
            else:
                print("Updated %s" % OPENCLAW_JSON)
    else:
        print("Allowlists already in sync.")


if __name__ == "__main__":
    main()
