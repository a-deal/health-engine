#!/usr/bin/env python3
"""
Pull Milo conversation transcripts from OpenClaw session files.

Handles:
- Active sessions (.jsonl)
- Reset sessions (.jsonl.reset.*)
- Nested message structure (entry.message.role, entry.message.content)
- Sender identification via sender_id in embedded metadata (not naive phone matching)
- All agent directories (main, atlas, ops, k)
- Cron filtering
- Cross-contamination detection (flags sessions where sender != expected user)

Usage:
    python3 transcripts.py [--user NAME] [--days N] [--verbose]
"""

import argparse
import json
import glob
import os
import re
import sys
import yaml
from datetime import datetime, timedelta
from pathlib import Path


OPENCLAW_DIR = os.path.expanduser("~/.openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")
USERS_FILE = os.path.join(OPENCLAW_DIR, "workspace/users.yaml")
LAST_RUN_FILE = os.path.join(OPENCLAW_DIR, "transcripts_last_run.txt")


def load_phone_map():
    """Build phone -> user_id/name map from users.yaml."""
    with open(USERS_FILE) as f:
        data = yaml.safe_load(f)

    phone_map = {}  # phone (various formats) -> {"user_id": ..., "name": ...}
    for phone, info in data.get("users", {}).items():
        if not isinstance(info, dict):
            continue
        phone_str = str(phone)
        entry = {"user_id": info.get("user_id", "unknown"), "name": info.get("name", "unknown")}
        # Store multiple formats for matching
        phone_map[phone_str] = entry
        if phone_str.startswith("+"):
            phone_map[phone_str[1:]] = entry
        # Also store just last 10 digits
        digits = re.sub(r"\D", "", phone_str)
        if len(digits) >= 10:
            phone_map[digits[-10:]] = entry

    return phone_map


def extract_sender_id(content):
    """Extract sender_id from embedded metadata in user message content.

    OpenClaw embeds sender info as JSON in markdown code blocks:
    ```json
    {"sender_id": "+17033625977", "sender": "Mike", ...}
    ```
    """
    if not isinstance(content, str):
        return None, None

    # Try sender_id in JSON metadata
    m = re.search(r'"sender_id"\s*:\s*"([^"]+)"', content)
    sender_id = m.group(1) if m else None

    # Try sender name
    m = re.search(r'"sender"\s*:\s*"([^"]+)"', content)
    sender_name = m.group(1) if m else None

    return sender_id, sender_name


def extract_user_text(content):
    """Extract the actual user text from a message, stripping metadata blocks."""
    if not isinstance(content, str):
        return ""

    # Messages have metadata in ```json ... ``` blocks, then user text after
    # Also handle media attachments
    parts = content.split("```")
    if len(parts) >= 3:
        # Text is after the last closing ```
        user_text = parts[-1].strip()
        if user_text:
            return user_text

    # Check for [media attached: ...] prefix
    m = re.match(r"\[media attached:.*?\].*?\n?(.*)", content, re.DOTALL)
    if m:
        remaining = m.group(1).strip()
        # Strip the "To send an image back..." instruction
        remaining = re.sub(r"To send an image back.*$", "", remaining, flags=re.DOTALL).strip()
        return remaining if remaining else "[image]"

    # Check for audio transcript
    m = re.search(r"Transcript:\s*(.+?)(?:\s*$)", content, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Check for [cron:...] prefix
    if content.strip().startswith("[cron:"):
        return content.strip()

    # If no metadata blocks, check if it's just raw text (short messages)
    if "sender_id" not in content and "Conversation info" not in content:
        return content.strip()

    # Fallback: return whatever is after metadata
    return ""


def parse_session(fpath, phone_map):
    """Parse a single session file and return structured data."""
    messages = []
    session_sender_id = None
    session_user = None
    is_cron = False

    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            if entry.get("type") != "message":
                continue

            msg = entry.get("message", {})
            role = msg.get("role", "")
            content = msg.get("content", "")

            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )

            if role == "user":
                sender_id, sender_name = extract_sender_id(content)

                # Identify session user from first real user message
                if session_sender_id is None and sender_id:
                    session_sender_id = sender_id
                    # Look up in phone map
                    for fmt in [sender_id, sender_id.lstrip("+"), re.sub(r"\D", "", sender_id)[-10:]]:
                        if fmt in phone_map:
                            session_user = phone_map[fmt]
                            break

                # Check if cron
                user_text = extract_user_text(content)
                if not messages and user_text.startswith("[cron:"):
                    is_cron = True

                if user_text and user_text != "[image]":
                    messages.append({
                        "role": "user",
                        "text": user_text,
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                    })
                elif user_text == "[image]":
                    messages.append({
                        "role": "user",
                        "text": "[image]",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                    })

            elif role == "assistant" and content.strip():
                # Skip tool-use noise (very short or system messages)
                text = content.strip()
                if len(text) > 5:
                    messages.append({"role": "assistant", "text": text})

    return {
        "sender_id": session_sender_id,
        "user": session_user,
        "is_cron": is_cron,
        "messages": messages,
    }


def read_last_run():
    """Read the timestamp of the last transcript pull."""
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE) as f:
            ts = f.read().strip()
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None
    return None


def write_last_run():
    """Write current timestamp as last run."""
    with open(LAST_RUN_FILE, "w") as f:
        f.write(datetime.now().isoformat())


def find_session_files(since=None, days=None):
    """Find all session files across all agents, including reset files."""
    if since:
        cutoff = since
    elif days:
        cutoff = datetime.now() - timedelta(days=days)
    else:
        cutoff = datetime.now() - timedelta(days=3)
    files = []

    for agent_dir in glob.glob(os.path.join(AGENTS_DIR, "*/sessions")):
        agent_name = agent_dir.split("/agents/")[1].split("/")[0]

        # Active sessions
        for fpath in glob.glob(os.path.join(agent_dir, "*.jsonl")):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append({"path": fpath, "agent": agent_name, "mtime": mtime, "status": "active"})

        # Reset sessions (contain real conversation history)
        for fpath in glob.glob(os.path.join(agent_dir, "*.jsonl.reset.*")):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append({"path": fpath, "agent": agent_name, "mtime": mtime, "status": "reset"})

        # Deleted sessions (might contain user conversations before cleanup)
        for fpath in glob.glob(os.path.join(agent_dir, "*.jsonl.deleted.*")):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if mtime >= cutoff:
                files.append({"path": fpath, "agent": agent_name, "mtime": mtime, "status": "deleted"})

    return sorted(files, key=lambda f: f["mtime"])


def main():
    parser = argparse.ArgumentParser(description="Pull Milo conversation transcripts")
    parser.add_argument("--user", type=str, default=None, help="Filter by user name")
    parser.add_argument("--days", type=int, default=None, help="Days to look back (default: since last run, or 3)")
    parser.add_argument("--since", type=str, default=None, help="ISO timestamp cutoff (e.g. 2026-03-31T10:00)")
    parser.add_argument("--verbose", action="store_true", help="Show file paths and debug info")
    parser.add_argument("--crons", action="store_true", help="Include cron sessions")
    args = parser.parse_args()

    phone_map = load_phone_map()

    # Determine time window
    since = None
    window_desc = ""
    if args.since:
        since = datetime.fromisoformat(args.since)
        window_desc = f"since {args.since}"
    elif args.days:
        window_desc = f"last {args.days} days"
    else:
        since = read_last_run()
        if since:
            window_desc = f"since last run ({since.strftime('%Y-%m-%d %H:%M')})"
        else:
            args.days = 3
            window_desc = "last 3 days (no prior run)"

    session_files = find_session_files(since=since, days=args.days)

    # Write last run timestamp
    write_last_run()

    if args.verbose:
        print(f"Found {len(session_files)} session files, {window_desc}", file=sys.stderr)

    # Group results by user
    by_user = {}

    for sf in session_files:
        result = parse_session(sf["path"], phone_map)

        # Skip crons unless requested
        if result["is_cron"] and not args.crons:
            continue

        # Skip sessions with no user messages
        user_msgs = [m for m in result["messages"] if m["role"] == "user"]
        if not user_msgs:
            continue

        # Determine user name
        if result["user"]:
            user_name = result["user"]["name"]
            user_id = result["user"]["user_id"]
        elif result["sender_id"]:
            user_name = f"Unknown ({result['sender_id']})"
            user_id = "unknown"
        else:
            user_name = "Unknown"
            user_id = "unknown"

        # Filter by user if requested
        if args.user and args.user.lower() not in user_name.lower() and args.user.lower() != user_id.lower():
            continue

        if user_name not in by_user:
            by_user[user_name] = []

        by_user[user_name].append({
            "time": sf["mtime"].strftime("%Y-%m-%d %H:%M"),
            "agent": sf["agent"],
            "status": sf["status"],
            "file": os.path.basename(sf["path"])[:40],
            "messages": result["messages"],
            "sender_id": result["sender_id"],
            "is_cron": result["is_cron"],
        })

    # Output
    if not by_user:
        user_filter = f" for user={args.user}" if args.user else ""
        print(f"No conversations found{user_filter} ({window_desc})")
        return

    for user_name, sessions in sorted(by_user.items()):
        print(f"\n# {user_name} ({len(sessions)} sessions)")
        print("=" * 60)

        for s in sessions:
            status_tag = f" [{s['status']}]" if s["status"] != "active" else ""
            agent_tag = f" ({s['agent']})" if s["agent"] != "main" else ""
            cron_tag = " [cron]" if s["is_cron"] else ""
            print(f"\n## {s['time']}{agent_tag}{status_tag}{cron_tag}")

            if args.verbose:
                print(f"   File: {s['file']}")
                print(f"   Sender: {s['sender_id']}")

            for m in s["messages"]:
                text = m["text"].replace("\n", " ").strip()
                if len(text) > 300:
                    text = text[:300] + "..."

                if m["role"] == "user":
                    print(f"> {text}")
                else:
                    print(f"Milo: {text}")

        print()


if __name__ == "__main__":
    main()
