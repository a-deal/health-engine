"""ACWR (Acute:Chronic Workload Ratio) training load tracking.

Computes training load from session RPE x duration, then calculates
the ratio of acute (7-day) to chronic (28-day) load. Alerts when
the ratio indicates injury risk or detraining.

Sources:
- Gabbett (2016): ACWR sweet spot 0.8-1.3, danger >1.5
- EWMA preferred over rolling average for sensitivity
"""

import json
import math
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def compute_acwr(
    sessions: list[dict],
    acute_days: int = 7,
    chronic_days: int = 28,
) -> dict | None:
    """Compute ACWR from session data.

    Args:
        sessions: List of dicts with 'date', 'rpe' (1-10), 'duration_min'.
            Sessions without RPE are skipped.
        acute_days: Acute window (default 7 days).
        chronic_days: Chronic window (default 28 days).

    Returns:
        Dict with acwr, acute_load, chronic_load, zone, and alert info.
        None if insufficient data (< 28 days of history).
    """
    if not sessions:
        return None

    # Filter to sessions with both RPE and duration
    valid = []
    for s in sessions:
        rpe = s.get("rpe")
        dur = s.get("duration_min")
        date = s.get("date", "")
        if rpe is not None and dur is not None and date:
            try:
                valid.append({
                    "date": date,
                    "load": float(rpe) * float(dur),
                })
            except (ValueError, TypeError):
                pass

    if not valid:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    acute_cutoff = (datetime.now() - timedelta(days=acute_days)).strftime("%Y-%m-%d")
    chronic_cutoff = (datetime.now() - timedelta(days=chronic_days)).strftime("%Y-%m-%d")

    # Check we have enough history
    earliest = min(s["date"] for s in valid)
    days_of_data = (datetime.now() - datetime.strptime(earliest, "%Y-%m-%d")).days
    if days_of_data < chronic_days:
        return {
            "status": "calibrating",
            "days_of_data": days_of_data,
            "days_needed": chronic_days,
            "message": f"Need {chronic_days - days_of_data} more days of data before ACWR is meaningful.",
        }

    # Sum loads per day
    daily_loads = {}
    for s in valid:
        daily_loads[s["date"]] = daily_loads.get(s["date"], 0) + s["load"]

    # Compute acute and chronic weekly totals
    acute_load = sum(
        load for date, load in daily_loads.items()
        if date > acute_cutoff
    )
    chronic_weekly_loads = []
    for week_start in range(0, chronic_days, 7):
        week_cutoff_start = (datetime.now() - timedelta(days=week_start + 7)).strftime("%Y-%m-%d")
        week_cutoff_end = (datetime.now() - timedelta(days=week_start)).strftime("%Y-%m-%d")
        week_load = sum(
            load for date, load in daily_loads.items()
            if week_cutoff_start < date <= week_cutoff_end
        )
        chronic_weekly_loads.append(week_load)

    chronic_avg = statistics.mean(chronic_weekly_loads) if chronic_weekly_loads else 0

    if chronic_avg == 0:
        acwr = None
        zone = "no_baseline"
    else:
        acwr = round(acute_load / chronic_avg, 2)
        if acwr < 0.6:
            zone = "detraining"
        elif acwr <= 0.8:
            zone = "underloading"
        elif acwr <= 1.3:
            zone = "optimal"
        elif acwr <= 1.5:
            zone = "caution"
        else:
            zone = "danger"

    result = {
        "status": "active",
        "acwr": acwr,
        "acute_load": round(acute_load),
        "chronic_avg_weekly": round(chronic_avg),
        "zone": zone,
        "sessions_this_week": sum(1 for d in daily_loads if d > acute_cutoff),
        "sessions_total": len(valid),
    }

    return result


def build_session_list(
    garmin_workouts: list[dict] | None = None,
    strength_log: list[dict] | None = None,
    session_log: list[dict] | None = None,
) -> list[dict]:
    """Merge sessions from multiple sources into a unified list.

    Each source contributes date, duration, RPE (if available), and type.
    Deduplicates by date + approximate time match.
    """
    sessions = []
    seen = set()

    # Garmin workouts (have duration, may have RPE from session_log)
    if garmin_workouts:
        for w in garmin_workouts:
            date = w.get("date", "")
            dur = w.get("duration_min", 0)
            activity_id = w.get("activity_id")
            key = f"{date}:{activity_id}" if activity_id else f"{date}:{dur}"
            if key not in seen:
                sessions.append({
                    "date": date,
                    "duration_min": dur,
                    "rpe": None,  # filled from session_log if available
                    "type": w.get("type", "unknown"),
                    "name": w.get("name", ""),
                    "source": "garmin",
                    "activity_id": activity_id,
                })
                seen.add(key)

    # Strength log (has RPE for some entries)
    if strength_log:
        # Group by date, take max RPE and sum estimated duration
        by_date = {}
        for s in strength_log:
            date = s.get("date", "")
            if not date:
                continue
            if date not in by_date:
                by_date[date] = {"rpe": None, "sets": 0}
            by_date[date]["sets"] += 1
            rpe = s.get("rpe")
            if rpe and rpe != "":
                try:
                    rpe_val = float(rpe)
                    if by_date[date]["rpe"] is None or rpe_val > by_date[date]["rpe"]:
                        by_date[date]["rpe"] = rpe_val
                except (ValueError, TypeError):
                    pass

        for date, info in by_date.items():
            # Check if we already have a Garmin workout for this date
            existing = [s for s in sessions if s["date"] == date]
            if existing:
                # Merge RPE into existing session
                if info["rpe"] is not None and existing[0]["rpe"] is None:
                    existing[0]["rpe"] = info["rpe"]
            else:
                # Estimate duration from set count (~3 min per set including rest)
                est_duration = info["sets"] * 3
                sessions.append({
                    "date": date,
                    "duration_min": est_duration,
                    "rpe": info["rpe"],
                    "type": "strength_training",
                    "name": "Strength",
                    "source": "strength_log",
                })

    # Explicit session log (always has RPE)
    if session_log:
        for s in session_log:
            date = s.get("date", "")
            rpe = s.get("rpe")
            if not date or rpe is None:
                continue
            # Match to existing session by date
            existing = [sess for sess in sessions if sess["date"] == date]
            if existing:
                try:
                    existing[0]["rpe"] = float(rpe)
                except (ValueError, TypeError):
                    pass
            else:
                sessions.append({
                    "date": date,
                    "duration_min": float(s.get("duration_min", 60)),
                    "rpe": float(rpe),
                    "type": s.get("type", "training"),
                    "name": s.get("name", "Session"),
                    "source": "session_log",
                })

    sessions.sort(key=lambda s: s["date"])
    return sessions


def acwr_alert(acwr_result: dict | None) -> list[dict]:
    """Generate alert from ACWR result if in danger or detraining zone."""
    if not acwr_result or acwr_result.get("status") != "active":
        return []

    zone = acwr_result.get("zone")
    acwr = acwr_result.get("acwr")

    if zone == "danger":
        return [{
            "metric": "training_load",
            "type": "spike",
            "severity": "warning",
            "message": (
                f"Training load spike: ACWR is {acwr} (danger zone >1.5). "
                f"This week's load ({acwr_result['acute_load']}) is significantly higher "
                f"than your 4-week average ({acwr_result['chronic_avg_weekly']}). "
                "Injury risk is elevated. Consider reducing intensity or volume today."
            ),
            "values": acwr_result,
        }]
    elif zone == "detraining":
        return [{
            "metric": "training_load",
            "type": "detraining",
            "severity": "info",
            "message": (
                f"Training load is low: ACWR is {acwr} (detraining zone <0.6). "
                f"This week's load ({acwr_result['acute_load']}) is well below "
                f"your 4-week average ({acwr_result['chronic_avg_weekly']}). "
                "If intentional (deload week), this is fine. Otherwise, time to get moving."
            ),
            "values": acwr_result,
        }]
    return []
