#!/usr/bin/env python3
"""Diagnose Garmin auth failures for a user.

Analyzes OpenClaw session logs, token state, gateway logs, and Garmin API
reachability to produce a root cause analysis.

Usage:
    python3 scripts/diagnose_garmin_auth.py grigoriy
    python3 scripts/diagnose_garmin_auth.py grigoriy --fix  # attempt a test connection
    python3 scripts/diagnose_garmin_auth.py --all           # check all users
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = Path(os.path.expanduser("~/.openclaw/agents/main/sessions"))
USERS_YAML = Path(os.path.expanduser("~/.openclaw/workspace/users.yaml"))
TOKEN_BASE = Path(os.path.expanduser("~/.config/health-engine/tokens/garmin"))
GATEWAY_LOG = Path(os.path.expanduser("~/Library/Logs/health-engine/gateway.log"))


def load_users() -> dict:
    if not USERS_YAML.exists():
        return {}
    with open(USERS_YAML) as f:
        data = yaml.safe_load(f) or {}
    return {
        info.get("user_id", ""): info
        for info in data.get("users", {}).values()
        if info.get("user_id")
    }


def check_token_state(user_id: str) -> dict:
    """Check if Garmin tokens exist and are valid."""
    token_dir = TOKEN_BASE / user_id
    result = {
        "token_dir_exists": token_dir.exists(),
        "files": [],
        "oauth2_present": False,
        "oauth1_present": False,
        "token_age_hours": None,
    }
    if not token_dir.exists():
        return result

    for f in token_dir.iterdir():
        stat = f.stat()
        age_h = (datetime.now().timestamp() - stat.st_mtime) / 3600
        result["files"].append({
            "name": f.name,
            "size": stat.st_size,
            "age_hours": round(age_h, 1),
        })
        if f.name == "oauth2_token.json":
            result["oauth2_present"] = True
            result["token_age_hours"] = round(age_h, 1)
        if f.name == "oauth1_token.json":
            result["oauth1_present"] = True

    return result


def scan_session_logs(user_id: str, phone: str, days: int = 14) -> dict:
    """Scan OpenClaw sessions for Garmin auth attempts and failures."""
    cutoff = datetime.now().timestamp() - (days * 86400)
    stats = {
        "sessions_scanned": 0,
        "auth_attempts": 0,
        "rate_limit_429": 0,
        "bad_credentials_401": 0,
        "forbidden_403": 0,
        "mfa_errors": 0,
        "network_errors": 0,
        "unknown_errors": 0,
        "successes": 0,
        "connect_wearable_calls": 0,
        "pull_garmin_calls": 0,
        "first_attempt": None,
        "last_attempt": None,
        "error_timeline": [],
    }

    phone_clean = phone.replace("+", "")

    if not SESSIONS_DIR.exists():
        return stats

    for fpath in SESSIONS_DIR.iterdir():
        if not fpath.name.endswith(".jsonl"):
            continue
        if fpath.stat().st_mtime < cutoff:
            continue

        try:
            text = fpath.read_text()
        except Exception:
            continue

        if phone_clean not in text and user_id not in text:
            continue

        stats["sessions_scanned"] += 1

        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue

            if entry.get("type") != "message":
                continue

            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            ts = entry.get("timestamp", "")

            cl = content.lower()

            if "connect_wearable" in cl and "garmin" in cl:
                stats["connect_wearable_calls"] += 1
            if "pull_garmin" in cl:
                stats["pull_garmin_calls"] += 1

            if "auth/garmin/submit" in cl or ("authenticated" in cl and "garmin" in cl):
                stats["auth_attempts"] += 1
                if not stats["first_attempt"]:
                    stats["first_attempt"] = ts
                stats["last_attempt"] = ts

            if "429" in content and "garmin" in cl:
                stats["rate_limit_429"] += 1
                stats["error_timeline"].append({"ts": ts, "type": "429"})
            elif "401" in content and "garmin" in cl:
                stats["bad_credentials_401"] += 1
                stats["error_timeline"].append({"ts": ts, "type": "401"})
            elif "403" in content and "garmin" in cl:
                stats["forbidden_403"] += 1
                stats["error_timeline"].append({"ts": ts, "type": "403"})
            elif "mfa" in cl and "garmin" in cl:
                stats["mfa_errors"] += 1
                stats["error_timeline"].append({"ts": ts, "type": "mfa"})
            elif "authenticated" in cl and "true" in cl and "garmin" in cl:
                stats["successes"] += 1
                stats["error_timeline"].append({"ts": ts, "type": "success"})

    return stats


def check_garmin_reachability() -> dict:
    """Test if sso.garmin.com is reachable from this machine."""
    result = {"reachable": False, "latency_ms": None, "error": None}
    try:
        import urllib.request
        start = datetime.now()
        req = urllib.request.Request(
            "https://sso.garmin.com/sso/signin",
            method="HEAD",
        )
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        elapsed = (datetime.now() - start).total_seconds() * 1000
        result["reachable"] = True
        result["latency_ms"] = round(elapsed)
        result["status_code"] = resp.status
    except Exception as e:
        result["error"] = str(e)[:200]
    return result


def check_api_health() -> dict:
    """Check if the local gateway API is up."""
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://localhost:18800/health", timeout=5)
        data = json.loads(resp.read())
        return {"status": "ok", "api_response": data}
    except Exception as e:
        return {"status": "down", "error": str(e)[:200]}


def diagnose(user_id: str, users: dict) -> dict:
    """Run full diagnosis for a user."""
    user_info = users.get(user_id, {})
    phone = ""
    for uid, info in users.items():
        if uid == user_id:
            # Find the phone from the original yaml structure
            break

    # Re-read to get phone
    if USERS_YAML.exists():
        with open(USERS_YAML) as f:
            raw = yaml.safe_load(f) or {}
        for ph, info in raw.get("users", {}).items():
            if info.get("user_id") == user_id:
                phone = ph
                break

    report = {
        "user_id": user_id,
        "phone": phone,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_state": check_token_state(user_id),
        "session_analysis": scan_session_logs(user_id, phone),
        "garmin_reachability": check_garmin_reachability(),
        "api_health": check_api_health(),
        "diagnosis": [],
        "recommended_actions": [],
    }

    # --- Root cause analysis ---
    tokens = report["token_state"]
    sessions = report["session_analysis"]
    reach = report["garmin_reachability"]

    if tokens["oauth2_present"] and tokens["token_age_hours"] is not None:
        if tokens["token_age_hours"] < 168:
            report["diagnosis"].append(
                f"Garmin tokens exist and are {tokens['token_age_hours']}h old. Auth is working."
            )
        else:
            report["diagnosis"].append(
                f"Garmin tokens are stale ({tokens['token_age_hours']}h). May need refresh."
            )
            report["recommended_actions"].append("Run pull_garmin to test if tokens still work. Re-auth if they fail.")
    else:
        report["diagnosis"].append("No Garmin tokens found. User has never successfully authenticated.")

    if sessions["rate_limit_429"] > 0:
        report["diagnosis"].append(
            f"Hit Garmin 429 rate limit {sessions['rate_limit_429']} times. "
            f"First attempt: {sessions['first_attempt']}, last: {sessions['last_attempt']}."
        )
        if sessions["connect_wearable_calls"] > 3:
            report["diagnosis"].append(
                f"Milo called connect_wearable {sessions['connect_wearable_calls']} times, "
                f"generating multiple auth links. Each link attempt may have contributed to rate limiting."
            )
        if sessions["pull_garmin_calls"] > 0 and not tokens["oauth2_present"]:
            report["diagnosis"].append(
                f"pull_garmin was called {sessions['pull_garmin_calls']} times without valid tokens. "
                "This likely used another user's tokens (cross-user fallback bug, now fixed) "
                "and burned rate limit budget before the real auth attempt."
            )
            report["recommended_actions"].append(
                "Verify _garmin_token_dir has no cross-user fallback (fixed in f6d5066)."
            )

        # Calculate cooldown status
        if sessions["last_attempt"]:
            try:
                last = datetime.fromisoformat(sessions["last_attempt"].replace("Z", "+00:00"))
                hours_since = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                if hours_since > 2:
                    report["diagnosis"].append(
                        f"Last attempt was {hours_since:.1f}h ago. Rate limit should be cleared."
                    )
                    report["recommended_actions"].append(
                        "Generate ONE fresh auth link and have user try once. Do not retry if it 429s again."
                    )
                else:
                    report["diagnosis"].append(
                        f"Last attempt was only {hours_since:.1f}h ago. Rate limit may still be active."
                    )
                    report["recommended_actions"].append(
                        f"Wait at least {max(0, 2 - hours_since):.1f}h before retrying."
                    )
            except Exception:
                pass

    if sessions["bad_credentials_401"] > 0:
        report["diagnosis"].append(
            f"Got {sessions['bad_credentials_401']} credential errors (401). User may have wrong password."
        )
        report["recommended_actions"].append(
            "Ask user to log into connect.garmin.com in their browser first to verify credentials work."
        )

    if sessions["mfa_errors"] > 0:
        report["diagnosis"].append("MFA is enabled on this Garmin account. Web auth flow doesn't support MFA.")
        report["recommended_actions"].append(
            "User needs to temporarily disable MFA on connect.garmin.com, auth here, then re-enable."
        )

    if not reach["reachable"]:
        report["diagnosis"].append(f"Cannot reach sso.garmin.com: {reach['error']}")
        report["recommended_actions"].append("Check network connectivity and DNS from this machine.")
    elif reach["latency_ms"] and reach["latency_ms"] > 5000:
        report["diagnosis"].append(f"sso.garmin.com latency is high: {reach['latency_ms']}ms")

    if report["api_health"]["status"] != "ok":
        report["diagnosis"].append("Local gateway API is down.")
        report["recommended_actions"].append("Restart API: bash scripts/restart-api.sh")

    if not report["diagnosis"]:
        report["diagnosis"].append("No issues detected. Auth should work on next attempt.")

    return report


def print_report(report: dict) -> None:
    """Print human-readable diagnostic report."""
    print(f"\n{'='*60}")
    print(f"GARMIN AUTH DIAGNOSIS: {report['user_id']}")
    print(f"{'='*60}")
    print(f"Time: {report['timestamp']}")
    print(f"Phone: {report['phone']}")

    print(f"\n--- Token State ---")
    t = report["token_state"]
    if t["oauth2_present"]:
        print(f"  Tokens: PRESENT (age: {t['token_age_hours']}h)")
        for f in t["files"]:
            print(f"    {f['name']}: {f['size']}B, {f['age_hours']}h old")
    else:
        print("  Tokens: MISSING")

    print(f"\n--- Session Analysis (last 14 days) ---")
    s = report["session_analysis"]
    print(f"  Sessions scanned: {s['sessions_scanned']}")
    print(f"  Auth attempts: {s['auth_attempts']}")
    print(f"  429 rate limits: {s['rate_limit_429']}")
    print(f"  401 bad creds: {s['bad_credentials_401']}")
    print(f"  403 forbidden: {s['forbidden_403']}")
    print(f"  MFA errors: {s['mfa_errors']}")
    print(f"  Successes: {s['successes']}")
    print(f"  connect_wearable calls: {s['connect_wearable_calls']}")
    print(f"  pull_garmin calls: {s['pull_garmin_calls']}")
    if s["first_attempt"]:
        print(f"  First attempt: {s['first_attempt']}")
        print(f"  Last attempt: {s['last_attempt']}")

    if s["error_timeline"]:
        print(f"\n  Error timeline:")
        for e in s["error_timeline"][-10:]:
            print(f"    {e['ts'][:19]} -> {e['type']}")

    print(f"\n--- Garmin Reachability ---")
    r = report["garmin_reachability"]
    if r["reachable"]:
        print(f"  sso.garmin.com: OK ({r['latency_ms']}ms)")
    else:
        print(f"  sso.garmin.com: UNREACHABLE ({r['error']})")

    print(f"\n--- API Health ---")
    a = report["api_health"]
    print(f"  Gateway: {a['status']}")

    print(f"\n--- Diagnosis ---")
    for d in report["diagnosis"]:
        print(f"  * {d}")

    if report["recommended_actions"]:
        print(f"\n--- Recommended Actions ---")
        for i, a in enumerate(report["recommended_actions"], 1):
            print(f"  {i}. {a}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Diagnose Garmin auth failures")
    parser.add_argument("user_id", nargs="?", help="User ID to diagnose")
    parser.add_argument("--all", action="store_true", help="Check all users")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    users = load_users()

    if args.all:
        user_ids = list(users.keys())
    elif args.user_id:
        user_ids = [args.user_id]
    else:
        parser.error("Provide a user_id or use --all")
        return

    reports = []
    for uid in user_ids:
        report = diagnose(uid, users)
        reports.append(report)
        if not args.json:
            print_report(report)

    if args.json:
        print(json.dumps(reports, indent=2, default=str))


if __name__ == "__main__":
    main()
