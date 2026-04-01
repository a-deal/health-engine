#!/usr/bin/env python3
"""Context Aggregator v1

Searches available conversation sources for a person and generates a draft
context.md file suitable for the health-engine user directory.

Sources checked:
  1. WhatsApp exports in ~/Downloads/ (zip files and extracted dirs)
  2. OpenClaw session logs on Mac Mini via SSH
  3. Gmail (via inbox-ai token.json + Gmail API)

Usage:
  python3 scripts/context_aggregator.py "Manny"
  python3 scripts/context_aggregator.py "Manny" --save manny
  python3 scripts/context_aggregator.py "Dean" --email dean1wu@gmail.com
  python3 scripts/context_aggregator.py "Dean" --phone +16509636822
"""

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOWNLOADS_DIR = Path.home() / "Downloads"
USERS_YAML = Path.home() / "src" / "health-engine" / "workspace" / "users.yaml"
DATA_USERS_DIR = Path.home() / "src" / "health-engine" / "data" / "users"
INBOX_AI_DIR = Path.home() / "src" / "inbox-ai"
GMAIL_CREDENTIALS = INBOX_AI_DIR / "credentials.json"
GMAIL_TOKEN = INBOX_AI_DIR / "token.json"

MAC_MINI_HOST = "mac-mini"
OPENCLAW_LOGS_DIR = "/Users/andrew/.openclaw/logs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def load_users_yaml() -> dict:
    """Load the users.yaml registry to resolve names to phones/user_ids."""
    if not USERS_YAML.exists():
        return {}
    try:
        text = USERS_YAML.read_text()
        users = {}
        current_phone = None
        for line in text.splitlines():
            m = re.match(r'^\s+"([^"]+)":\s*$', line)
            if m:
                current_phone = m.group(1)
                users[current_phone] = {"phone": current_phone}
                continue
            if current_phone:
                kv = re.match(r'^\s+(\w+):\s*"?([^"]+)"?\s*$', line)
                if kv:
                    users[current_phone][kv.group(1).strip()] = kv.group(2).strip()
        return users
    except Exception as e:
        log(f"Warning: could not parse users.yaml: {e}")
        return {}


def find_user_in_registry(name: str, email: Optional[str], phone: Optional[str]) -> dict:
    """Look up a user in users.yaml by name, email, or phone."""
    users = load_users_yaml()
    name_lower = name.lower()
    for _, info in users.items():
        if phone and info.get("phone") == phone:
            return info
        if email and info.get("email", "").lower() == email.lower():
            return info
        if info.get("name", "").lower() == name_lower:
            return info
    return {}


# ---------------------------------------------------------------------------
# Source 1: WhatsApp exports
# ---------------------------------------------------------------------------

def search_whatsapp_exports(name: str) -> list[dict]:
    """Search ~/Downloads for WhatsApp chat exports matching a name.

    Looks for:
      - Directories like {name}-whatsapp-export*
      - Zip files like 'WhatsApp Chat - {Name}*.zip'
    """
    results = []
    name_lower = name.lower()

    if not DOWNLOADS_DIR.exists():
        log("WhatsApp: ~/Downloads not found, skipping")
        return results

    # 1. Named export directories (e.g. mike-whatsapp-export/)
    for d in sorted(DOWNLOADS_DIR.iterdir()):
        if d.is_dir() and name_lower in d.name.lower() and "whatsapp" in d.name.lower():
            chat_file = d / "_chat.txt"
            if chat_file.exists():
                results.append({
                    "source": f"whatsapp-dir:{d.name}",
                    "messages": _parse_whatsapp_chat(chat_file.read_text(errors="replace")),
                })

    # 2. Zip files like "WhatsApp Chat - Name*.zip"
    for f in sorted(DOWNLOADS_DIR.iterdir()):
        if not f.is_file() or f.suffix != ".zip":
            continue
        if "whatsapp chat" not in f.name.lower():
            continue
        m = re.match(r"WhatsApp Chat - (.+?)(?:\s*\(\d+\))?\.zip", f.name, re.IGNORECASE)
        if not m:
            continue
        contact = m.group(1).strip()
        if name_lower not in contact.lower():
            continue

        try:
            with zipfile.ZipFile(f, "r") as zf:
                chat_names = [n for n in zf.namelist() if n.endswith("_chat.txt")]
                if chat_names:
                    text = zf.read(chat_names[0]).decode("utf-8", errors="replace")
                    results.append({
                        "source": f"whatsapp-zip:{f.name}",
                        "messages": _parse_whatsapp_chat(text),
                    })
        except Exception as e:
            log(f"WhatsApp: failed to read {f.name}: {e}")

    return results


def _parse_whatsapp_chat(text: str) -> list[dict]:
    """Parse WhatsApp _chat.txt into structured messages."""
    messages = []
    pattern = re.compile(
        r"\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M)\]\s+([^:]+):\s+(.*)"
    )
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            messages.append({
                "timestamp": m.group(1),
                "sender": m.group(2).strip(),
                "text": m.group(3).strip(),
            })
        elif messages:
            messages[-1]["text"] += "\n" + line
    return messages


# ---------------------------------------------------------------------------
# Source 2: OpenClaw logs on Mac Mini
# ---------------------------------------------------------------------------

def search_openclaw_logs(name: str, phone: Optional[str] = None) -> list[dict]:
    """SSH to mac-mini and grep OpenClaw logs for a name or phone number."""
    results = []
    search_terms = [name]
    if phone:
        search_terms.append(phone)
        if phone.startswith("+"):
            search_terms.append(phone[1:])

    for term in search_terms:
        try:
            cmd = [
                "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                MAC_MINI_HOST,
                f'grep -r -l "{term}" {OPENCLAW_LOGS_DIR}/ 2>/dev/null | head -20'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                files = result.stdout.strip().splitlines()
                log(f"OpenClaw: found {len(files)} log file(s) matching '{term}'")

                for log_file in files[:5]:
                    try:
                        cat_cmd = [
                            "ssh", "-o", "ConnectTimeout=5",
                            MAC_MINI_HOST,
                            f'grep -B2 -A5 "{term}" "{log_file}" | head -200'
                        ]
                        cat_result = subprocess.run(cat_cmd, capture_output=True, text=True, timeout=15)
                        if cat_result.stdout.strip():
                            results.append({
                                "source": f"openclaw-log:{os.path.basename(log_file)}",
                                "content": cat_result.stdout.strip(),
                            })
                    except Exception:
                        continue
        except subprocess.TimeoutExpired:
            log(f"OpenClaw: SSH timed out searching for '{term}'")
        except Exception as e:
            log(f"OpenClaw: error searching for '{term}': {e}")

    # Also try listing sessions
    if phone:
        try:
            cmd = [
                "ssh", "-o", "ConnectTimeout=5",
                MAC_MINI_HOST,
                'export PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH" && openclaw gateway call sessions.list 2>/dev/null'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.splitlines():
                    if phone in line or (phone.startswith("+") and phone[1:] in line):
                        results.append({
                            "source": "openclaw-sessions",
                            "content": line.strip(),
                        })
        except Exception as e:
            log(f"OpenClaw: session list failed: {e}")

    return results


# ---------------------------------------------------------------------------
# Source 3: Gmail
# ---------------------------------------------------------------------------

def search_gmail(name: str, email: Optional[str] = None, max_results: int = 20) -> list[dict]:
    """Search Gmail for messages to/from a person using the Gmail API."""
    if not GMAIL_CREDENTIALS.exists() or not GMAIL_TOKEN.exists():
        log("Gmail: credentials or token not found, skipping")
        return []

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import base64
    except ImportError:
        log("Gmail: google-api-python-client not installed, skipping")
        log("  Install with: pip install google-api-python-client google-auth-oauthlib")
        return []

    results = []
    try:
        scopes = [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
        ]
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN), scopes)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                GMAIL_TOKEN.write_text(creds.to_json())
            else:
                log("Gmail: token expired and no refresh token, skipping")
                return []

        service = build("gmail", "v1", credentials=creds)

        queries = []
        if email:
            queries.append(f"from:{email} OR to:{email}")
        queries.append(f'"{name}"')

        seen_ids = set()
        for query in queries:
            try:
                resp = service.users().messages().list(
                    userId="me", q=query, maxResults=max_results
                ).execute()

                for msg_meta in resp.get("messages", []):
                    msg_id = msg_meta["id"]
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)
                    try:
                        msg = service.users().messages().get(
                            userId="me", id=msg_id, format="full"
                        ).execute()
                        headers = {
                            h["name"].lower(): h["value"]
                            for h in msg["payload"].get("headers", [])
                        }
                        body = _extract_gmail_body(msg["payload"])
                        results.append({
                            "source": "gmail",
                            "subject": headers.get("subject", "(no subject)"),
                            "from": headers.get("from", ""),
                            "to": headers.get("to", ""),
                            "date": headers.get("date", ""),
                            "snippet": msg.get("snippet", ""),
                            "body": body[:2000],
                        })
                    except Exception:
                        continue
            except Exception as e:
                log(f"Gmail: query '{query}' failed: {e}")

    except Exception as e:
        log(f"Gmail: {e}")

    return results


def _extract_gmail_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    import base64

    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                raw = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                return re.sub(r"<[^>]+>", " ", raw)

    return ""


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

def extract_health_context(wa_results: list, openclaw_results: list, gmail_results: list) -> dict:
    """Pull health-relevant signals from all conversation sources."""
    context = {
        "conditions": [],
        "goals": [],
        "medications": [],
        "injuries": [],
        "wearables": [],
        "preferences": [],
        "lifestyle": [],
    }

    all_text = []
    for wa in wa_results:
        for msg in wa.get("messages", []):
            all_text.append(msg.get("text", ""))
    for oc in openclaw_results:
        all_text.append(oc.get("content", ""))
    for gm in gmail_results:
        all_text.append(gm.get("body", ""))
        all_text.append(gm.get("snippet", ""))

    combined = "\n".join(all_text).lower()

    health_keywords = {
        "conditions": [
            "diabetes", "hypertension", "asthma", "anxiety", "depression",
            "adhd", "sleep apnea", "insomnia", "pcos", "thyroid",
            "pre-diabetic", "prediabetic", "high blood pressure",
        ],
        "goals": [
            "lose weight", "weight loss", "bulk", "cut", "gain muscle",
            "run a", "marathon", "sleep better", "quit smoking", "quit nicotine",
            "body comp", "body fat", "get stronger", "flexibility",
        ],
        "medications": [
            "tirzepatide", "ozempic", "metformin", "finasteride", "minoxidil",
            "creatine", "protein", "supplement", "vitamin", "mg/day", "mg daily",
            "prescription", "medication",
        ],
        "injuries": [
            "injury", "injured", "surgery", "torn", "sprain", "strain",
            "back pain", "knee", "shoulder", "hip replacement",
        ],
        "wearables": [
            "garmin", "apple watch", "whoop", "oura", "fitbit",
            "cgm", "glucose monitor", "lofta", "sleep tracker",
        ],
        "preferences": [
            "vegetarian", "vegan", "keto", "paleo", "gluten",
            "intermittent fasting", "meal prep", "macro", "calorie",
        ],
        "lifestyle": [
            "gym", "crossfit", "yoga", "running", "cycling", "swimming",
            "work schedule", "shift work", "travel", "kids", "parent",
        ],
    }

    for category, keywords in health_keywords.items():
        for kw in keywords:
            if kw in combined:
                for text_block in all_text:
                    for sentence in re.split(r"[.!?\n]", text_block):
                        if kw in sentence.lower() and len(sentence.strip()) > 10:
                            fact = sentence.strip()[:200]
                            if fact not in context[category]:
                                context[category].append(fact)
                            break

    return context


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def generate_context_md(
    name: str,
    user_info: dict,
    wa_results: list,
    openclaw_results: list,
    gmail_results: list,
    sources_checked: list,
) -> str:
    """Generate the draft context.md content."""

    health_context = extract_health_context(wa_results, openclaw_results, gmail_results)

    wa_msg_count = sum(len(r.get("messages", [])) for r in wa_results)
    oc_count = len(openclaw_results)
    gmail_count = len(gmail_results)

    channels = []
    if wa_results:
        channels.append("WhatsApp")
    if openclaw_results:
        channels.append("OpenClaw/Milo")
    if gmail_results:
        channels.append("Email")

    lines = []
    lines.append(f"# {name}")
    lines.append("")
    lines.append("## Basics")
    lines.append("- Age: (unknown)")

    sources_str = ", ".join(sources_checked) if sources_checked else "none"
    lines.append(f"- Sources checked: {sources_str}")

    if channels:
        lines.append(f"- Channel: {', '.join(channels)}")
    else:
        lines.append("- Channel: (no conversations found)")

    if user_info.get("phone"):
        lines.append(f"- Phone: {user_info['phone']}")
    if user_info.get("email"):
        lines.append(f"- Email: {user_info['email']}")
    if user_info.get("user_id"):
        lines.append(f"- User ID: {user_info['user_id']}")

    lines.append("- Signed up: (check registry)")
    lines.append(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Data Summary")
    lines.append(f"- WhatsApp messages found: {wa_msg_count} (across {len(wa_results)} export(s))")
    lines.append(f"- OpenClaw log matches: {oc_count}")
    lines.append(f"- Gmail messages found: {gmail_count}")
    lines.append("")

    lines.append("## What We Know")
    has_context = False
    for category, facts in health_context.items():
        if facts:
            has_context = True
            lines.append(f"### {category.title()}")
            for fact in facts[:5]:
                lines.append(f"- {fact}")
            lines.append("")

    if not has_context:
        lines.append("- (no health context extracted yet. Review raw conversations below.)")
        lines.append("")

    if wa_results:
        lines.append("## Recent WhatsApp Messages (sample)")
        for wa in wa_results[:2]:
            lines.append(f"### Source: {wa['source']}")
            msgs = wa.get("messages", [])
            for msg in msgs[-30:]:
                sender = msg["sender"]
                text = msg["text"][:300]
                ts = msg["timestamp"]
                lines.append(f"- [{ts}] **{sender}**: {text}")
            lines.append("")

    if gmail_results:
        lines.append("## Gmail Threads (sample)")
        for gm in gmail_results[:5]:
            lines.append(f"- **{gm.get('date', '')}** | {gm.get('subject', '')} | from: {gm.get('from', '')}")
            if gm.get("snippet"):
                lines.append(f"  > {gm['snippet'][:200]}")
        lines.append("")

    if openclaw_results:
        lines.append("## OpenClaw Log Excerpts")
        for oc in openclaw_results[:3]:
            lines.append(f"### {oc['source']}")
            lines.append("```")
            lines.append(oc["content"][:1000])
            lines.append("```")
            lines.append("")

    lines.append("## What to Start With")
    lines.append("- (review extracted context above and fill in)")
    lines.append("- (identify one habit or goal to focus on)")
    lines.append("")
    lines.append("## Andrew's Notes")
    lines.append("- (add personal observations after reviewing)")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Search conversation sources and generate a draft context.md for a user."
    )
    parser.add_argument("name", help="Person's name to search for")
    parser.add_argument("--save", metavar="USER_ID",
                        help="Save to data/users/<USER_ID>/context.md instead of stdout")
    parser.add_argument("--email", help="Email address to search Gmail")
    parser.add_argument("--phone", help="Phone number (e.g. +19255426289)")
    parser.add_argument("--skip-gmail", action="store_true", help="Skip Gmail search")
    parser.add_argument("--skip-openclaw", action="store_true", help="Skip OpenClaw SSH search")
    parser.add_argument("--skip-whatsapp", action="store_true", help="Skip WhatsApp export search")
    args = parser.parse_args()

    name = args.name
    print(f"\n=== Context Aggregator v1 ===", file=sys.stderr)
    print(f"Searching for: {name}", file=sys.stderr)

    # Look up user in registry
    user_info = find_user_in_registry(name, args.email, args.phone)
    if user_info:
        log(f"Found in users.yaml: {user_info}")
        if not args.phone and user_info.get("phone"):
            args.phone = user_info["phone"]
        if not args.email and user_info.get("email"):
            args.email = user_info["email"]

    sources_checked = []

    # Source 1: WhatsApp
    wa_results = []
    if not args.skip_whatsapp:
        log("Searching WhatsApp exports...")
        wa_results = search_whatsapp_exports(name)
        msg_count = sum(len(r.get("messages", [])) for r in wa_results)
        log(f"WhatsApp: {len(wa_results)} export(s), {msg_count} messages")
        sources_checked.append(f"WhatsApp exports ({len(wa_results)} found)")
    else:
        sources_checked.append("WhatsApp (skipped)")

    # Source 2: OpenClaw
    openclaw_results = []
    if not args.skip_openclaw:
        log("Searching OpenClaw logs on Mac Mini...")
        openclaw_results = search_openclaw_logs(name, args.phone)
        log(f"OpenClaw: {len(openclaw_results)} match(es)")
        sources_checked.append(f"OpenClaw logs ({len(openclaw_results)} found)")
    else:
        sources_checked.append("OpenClaw (skipped)")

    # Source 3: Gmail
    gmail_results = []
    if not args.skip_gmail:
        log("Searching Gmail...")
        gmail_results = search_gmail(name, args.email)
        log(f"Gmail: {len(gmail_results)} message(s)")
        sources_checked.append(f"Gmail ({len(gmail_results)} found)")
    else:
        sources_checked.append("Gmail (skipped)")

    # Generate output
    log("Generating context.md...")
    output = generate_context_md(
        name=name,
        user_info=user_info,
        wa_results=wa_results,
        openclaw_results=openclaw_results,
        gmail_results=gmail_results,
        sources_checked=sources_checked,
    )

    if args.save:
        save_dir = DATA_USERS_DIR / args.save
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / "context.md"
        save_path.write_text(output)
        log(f"Saved to {save_path}")
        print(f"\nSaved to {save_path}", file=sys.stderr)
    else:
        print(output)

    print(f"\nDone. Sources checked: {', '.join(sources_checked)}", file=sys.stderr)


if __name__ == "__main__":
    main()
