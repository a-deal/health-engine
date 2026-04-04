#!/usr/bin/env python3
"""Backfill sleep_start/sleep_end in wearable_daily.

The Garmin timezone bug (fixed in 64d5843) stored sleep times 7 hours
early due to double-converting local timestamps. This script re-pulls
90 days of Garmin data using the fixed extraction code, which overwrites
the bad values via INSERT OR REPLACE.

Usage:
    python3 scripts/backfill_sleep_times.py [--days N] [--user USER_ID] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Backfill sleep times from Garmin")
    parser.add_argument("--days", type=int, default=90, help="Days of history to re-pull")
    parser.add_argument("--user", default="andrew", help="User ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without pulling")
    args = parser.parse_args()

    from engine.gateway.db import get_db, init_db
    init_db()
    db = get_db()

    # Show current bad data
    person_row = db.execute(
        "SELECT id FROM person WHERE health_engine_user_id = ?", (args.user,)
    ).fetchone()
    if not person_row:
        print(f"No person found for user_id={args.user}")
        sys.exit(1)

    person_id = person_row["id"]
    rows = db.execute(
        """SELECT date, sleep_start, sleep_end FROM wearable_daily
           WHERE person_id = ? AND source = 'garmin' AND sleep_start IS NOT NULL
           ORDER BY date DESC LIMIT ?""",
        (person_id, args.days),
    ).fetchall()

    print(f"Current sleep times for {args.user} ({len(rows)} rows with sleep data):")
    suspicious = 0
    for r in rows:
        start = r["sleep_start"]
        # Sleep start between 06:00-18:00 is suspicious (should be evening)
        h = int(start.split(":")[0]) if start else 0
        flag = " <-- SUSPICIOUS" if 6 <= h <= 18 else ""
        if flag:
            suspicious += 1
        print(f"  {r['date']}  start={start}  end={r['sleep_end']}{flag}")

    print(f"\n{suspicious}/{len(rows)} rows look wrong (sleep_start during daytime)")

    if args.dry_run:
        print("\n--dry-run: skipping re-pull")
        return

    if suspicious == 0:
        print("No suspicious rows found. Nothing to backfill.")
        return

    print(f"\nRe-pulling {args.days} days of Garmin history with fixed timezone code...")
    from engine.integrations.garmin import GarminClient
    from engine.gateway.token_store import TokenStore

    ts = TokenStore()
    if not ts.has_token("garmin", args.user):
        print(f"No Garmin tokens for {args.user}")
        sys.exit(1)

    token_dir = str(ts.garmin_token_dir(args.user))
    data_dir = Path.home() / "src" / "health-engine" / "data" / "users" / args.user
    client = GarminClient(
        token_dir=token_dir, token_store=ts, user_id=args.user,
        data_dir=str(data_dir),
    )
    result = client.pull_all(
        history=True, history_days=args.days, person_id=person_id,
    )
    ts.sync_garmin_tokens(args.user)
    series = result.get("daily_series", [])

    print(f"\nPulled {len(series)} days. Verifying fix...")

    # Show updated data
    rows_after = db.execute(
        """SELECT date, sleep_start, sleep_end FROM wearable_daily
           WHERE person_id = ? AND source = 'garmin' AND sleep_start IS NOT NULL
           ORDER BY date DESC LIMIT 10""",
        (person_id,),
    ).fetchall()

    fixed = 0
    for r in rows_after:
        start = r["sleep_start"]
        h = int(start.split(":")[0]) if start else 0
        status = "OK" if not (6 <= h <= 18) else "STILL BAD"
        if status == "OK":
            fixed += 1
        print(f"  {r['date']}  start={start}  end={r['sleep_end']}  [{status}]")

    print(f"\n{fixed}/{len(rows_after)} recent rows now have correct sleep times.")


if __name__ == "__main__":
    main()
