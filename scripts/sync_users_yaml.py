#!/usr/bin/env python3
"""Sync user registry from SQLite to OpenClaw's users.yaml.

SQLite (person table) is the canonical source of truth.
users.yaml is generated for OpenClaw's routing layer.

Usage:
    python3 scripts/sync_users_yaml.py           # write to ~/.openclaw/workspace/users.yaml
    python3 scripts/sync_users_yaml.py --dry-run  # print without writing
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from engine.gateway.db import get_active_users, init_db

USERS_YAML = Path.home() / ".openclaw" / "workspace" / "users.yaml"


def generate_users_yaml() -> str:
    """Generate users.yaml content from SQLite person table."""
    init_db()
    users = get_active_users()

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
        "# Canonical source: data/kasane.db → person table\n\n"
    )
    body = yaml.dump({"users": yaml_users}, default_flow_style=False, sort_keys=False)
    return header + body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    content = generate_users_yaml()

    if args.dry_run:
        print(content)
        return

    USERS_YAML.parent.mkdir(parents=True, exist_ok=True)
    USERS_YAML.write_text(content)
    print(f"Wrote {USERS_YAML}")


if __name__ == "__main__":
    main()
