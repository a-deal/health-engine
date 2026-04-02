#!/usr/bin/env python3
"""One-time backfill: parse OpenClaw session files into conversation_message table.

Uses the same parsing logic as transcripts.py but writes to kasane.db instead of stdout.
Safe to run multiple times (skips duplicates by checking message content + timestamp).
"""

import json
import glob
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

OPENCLAW_DIR = os.path.expanduser("~/.openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")
USERS_FILE = os.path.join(OPENCLAW_DIR, "workspace/users.yaml")
DB_PATH = Path(__file__).parent.parent / "data" / "kasane.db"


def load_phone_map():
    import yaml
    with open(USERS_FILE) as f:
        data = yaml.safe_load(f)
    phone_map = {}
    for phone, info in data.get("users", {}).items():
        if not isinstance(info, dict):
            continue
        phone_str = str(phone)
        entry = {"user_id": info.get("user_id", "unknown"), "name": info.get("name", "unknown")}
        phone_map[phone_str] = entry
        if phone_str.startswith("+"):
            phone_map[phone_str[1:]] = entry
        digits = re.sub(r"\D", "", phone_str)
        if len(digits) >= 10:
            phone_map[digits[-10:]] = entry
    return phone_map


def extract_sender_id(content):
    if not isinstance(content, str):
        return None, None
    m = re.search(r'"sender_id"\s*:\s*"([^"]+)"', content)
    sender_id = m.group(1) if m else None
    m = re.search(r'"sender"\s*:\s*"([^"]+)"', content)
    sender_name = m.group(1) if m else None
    return sender_id, sender_name


def extract_user_text(content):
    if not isinstance(content, str):
        return ""
    parts = content.split("```")
    if len(parts) >= 3:
        user_text = parts[-1].strip()
        if user_text:
            return user_text
    m = re.match(r"\[media attached:.*?\].*?\n?(.*)", content, re.DOTALL)
    if m:
        remaining = m.group(1).strip()
        remaining = re.sub(r"To send an image back.*$", "", remaining, flags=re.DOTALL).strip()
        return remaining if remaining else "[image]"
    m = re.search(r"Transcript:\s*(.+?)(?:\s*$)", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    if content.strip().startswith("[cron:"):
        return ""  # Skip crons
    if "sender_id" not in content and "Conversation info" not in content:
        return content.strip()
    return ""


def extract_channel(session_key):
    """Extract channel from session key like agent:main:whatsapp:direct:+17033625977"""
    if not session_key:
        return ""
    parts = session_key.split(":")
    if len(parts) >= 3:
        return parts[2]  # whatsapp, telegram, etc.
    return ""


def resolve_user_id(sender_id, phone_map):
    if not sender_id:
        return None
    for fmt in [sender_id, sender_id.lstrip("+"), re.sub(r"\D", "", sender_id)[-10:]]:
        if fmt in phone_map:
            return phone_map[fmt]["user_id"]
    return None


def find_all_session_files():
    files = []
    for agent_dir in glob.glob(os.path.join(AGENTS_DIR, "*/sessions")):
        agent_name = agent_dir.split("/agents/")[1].split("/")[0]
        for pattern in ["*.jsonl", "*.jsonl.reset.*", "*.jsonl.deleted.*"]:
            for fpath in glob.glob(os.path.join(agent_dir, pattern)):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                files.append({"path": fpath, "agent": agent_name, "mtime": mtime})
    return sorted(files, key=lambda f: f["mtime"])


def parse_and_insert(conn, fpath, agent, phone_map):
    """Parse a session file and insert messages into DB. Returns count of inserted rows."""
    inserted = 0
    session_key = ""

    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            # Extract session key from session entry
            if entry.get("type") == "session":
                # Session key isn't directly in here, but we can construct it
                pass

            if entry.get("type") != "message":
                continue

            msg = entry.get("message", {})
            role = msg.get("role", "")
            content = msg.get("content", "")
            ts = entry.get("timestamp")

            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )

            if role == "user":
                sender_id, sender_name = extract_sender_id(content)
                user_text = extract_user_text(content)

                # Skip crons and empty messages
                if not user_text or user_text.startswith("[cron:"):
                    continue

                user_id = resolve_user_id(sender_id, phone_map)

                # Check for duplicate
                existing = conn.execute(
                    "SELECT 1 FROM conversation_message WHERE timestamp = ? AND sender_id = ? AND role = 'user' LIMIT 1",
                    (ts, sender_id or ""),
                ).fetchone()
                if existing:
                    continue

                conn.execute(
                    """INSERT INTO conversation_message
                       (user_id, role, content, sender_id, sender_name, channel, session_key, message_id, timestamp, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, "user", user_text, sender_id or "", sender_name or "",
                     "", "", "", ts or "", datetime.now(timezone.utc).isoformat()),
                )
                inserted += 1

            elif role == "assistant" and content.strip():
                text = content.strip()
                if len(text) <= 5:
                    continue

                # Check for duplicate
                existing = conn.execute(
                    "SELECT 1 FROM conversation_message WHERE timestamp = ? AND role = 'assistant' AND content = ? LIMIT 1",
                    (ts, text[:500]),
                ).fetchone()
                if existing:
                    continue

                conn.execute(
                    """INSERT INTO conversation_message
                       (user_id, role, content, sender_id, sender_name, channel, session_key, message_id, timestamp, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (None, "assistant", text, "milo", "Milo",
                     "", "", "", ts or "", datetime.now(timezone.utc).isoformat()),
                )
                inserted += 1

    return inserted


def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found")
        sys.exit(1)

    phone_map = load_phone_map()
    session_files = find_all_session_files()
    print(f"Found {len(session_files)} session files across all agents")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    total_inserted = 0
    files_with_data = 0

    for sf in session_files:
        count = parse_and_insert(conn, sf["path"], sf["agent"], phone_map)
        if count > 0:
            files_with_data += 1
            total_inserted += count
            if total_inserted % 50 == 0:
                conn.commit()
                print(f"  ... {total_inserted} messages inserted so far")

    conn.commit()
    conn.close()

    print(f"\nBackfill complete: {total_inserted} messages from {files_with_data} session files")

    # Summary
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT user_id, role, count(*) as cnt FROM conversation_message GROUP BY user_id, role ORDER BY user_id, role"
    ).fetchall()
    print("\nMessage counts:")
    for r in rows:
        print(f"  {r[0] or 'unknown':15} {r[1]:10} {r[2]}")
    conn.close()


if __name__ == "__main__":
    main()
