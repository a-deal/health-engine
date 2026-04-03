#!/usr/bin/env python3
"""One-time migration: fix Grigoriy's mixed-unit weight entries and set unit_system=metric.

The Apr 2 entry (107.0) was stored as raw kg instead of being converted to lbs.
All other entries are already in lbs. Fix the outlier and set unit_system so
future ingestion converts automatically.

Usage:
    python3 scripts/fix_grigoriy_weight.py          # dry run
    python3 scripts/fix_grigoriy_weight.py --apply   # apply changes
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.gateway.db import init_db, get_db, KG_TO_LBS

THRESHOLD = 150  # lbs. Entries below this are likely raw kg values.


def main():
    apply = "--apply" in sys.argv
    init_db()
    db = get_db()

    person_row = db.execute(
        "SELECT id FROM person WHERE health_engine_user_id = 'grigoriy' AND deleted_at IS NULL"
    ).fetchone()
    if not person_row:
        print("Grigoriy not found in person table.")
        return

    person_id = person_row[0]

    # 1. Set unit_system to metric
    current = db.execute("SELECT unit_system FROM person WHERE id = ?", (person_id,)).fetchone()
    print(f"Current unit_system: {current[0] if current else 'N/A'}")
    if apply:
        db.execute("UPDATE person SET unit_system = 'metric' WHERE id = ?", (person_id,))
        print("Set unit_system = 'metric'")

    # 2. Fix weight entries that look like raw kg (below threshold)
    rows = db.execute(
        "SELECT id, date, weight_lbs FROM weight_entry WHERE person_id = ? ORDER BY date",
        (person_id,),
    ).fetchall()

    for row_id, date, weight in rows:
        if weight < THRESHOLD:
            converted = weight * KG_TO_LBS
            print(f"  {date}: {weight} -> {converted:.1f} lbs (was raw kg)")
            if apply:
                db.execute(
                    "UPDATE weight_entry SET weight_lbs = ? WHERE id = ?",
                    (converted, row_id),
                )
        else:
            print(f"  {date}: {weight} lbs (ok)")

    if apply:
        db.commit()
        print("\nApplied.")
    else:
        print("\nDry run. Pass --apply to commit changes.")


if __name__ == "__main__":
    main()
