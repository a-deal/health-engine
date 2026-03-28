"""Alert detection for health metrics.

Checks rolling averages and daily series for threshold breaches.
Returns a list of alert dicts for the briefing response.
"""

import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def check_alerts(
    daily_series: list[dict] | None = None,
    weight_data: list[dict] | None = None,
    habit_data: list[dict] | None = None,
    garmin_today: dict | None = None,
    horizons: dict | None = None,
    targets: dict | None = None,
) -> list[dict]:
    """Run all alert checks and return triggered alerts.

    Args:
        daily_series: garmin_daily.json (90-day day-by-day RHR/HRV/sleep/steps)
        weight_data: Parsed weight_log.csv [{"date": ..., "weight": ...}, ...]
        habit_data: Parsed daily_habits.csv rows
        garmin_today: garmin_today.json (intraday snapshot)
        horizons: Pre-computed horizons dict from compute_rolling
        targets: User targets from config (weight_lbs, calories, etc.)

    Returns:
        List of alert dicts, sorted by severity (warning first, then info).
    """
    alerts = []
    targets = targets or {}

    if daily_series:
        alerts.extend(_check_rhr_spike(daily_series))
        alerts.extend(_check_hrv_suppression(daily_series))
        alerts.extend(_check_sleep_debt(daily_series))
        alerts.extend(_check_sleep_regularity(daily_series))

    if weight_data and targets.get("weight_lbs"):
        alerts.extend(_check_weight_plateau(weight_data))

    if habit_data:
        alerts.extend(_check_habit_dropoff(habit_data))

    if garmin_today:
        alerts.extend(_check_body_battery(garmin_today, daily_series))

    # Sort: warnings first, then info
    severity_order = {"warning": 0, "info": 1}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 2))

    return alerts


def _check_rhr_spike(series: list[dict]) -> list[dict]:
    """RHR 5+ bpm above 7-day average for 2+ consecutive days."""
    valid = [e for e in series if e.get("rhr") is not None]
    if len(valid) < 9:  # need 7 for avg + 2 for check
        return []

    avg_7d = statistics.mean(e["rhr"] for e in valid[-9:-2])
    recent = valid[-2:]  # last 2 days
    consecutive_above = 0
    max_delta = 0

    for day in recent:
        delta = day["rhr"] - avg_7d
        if delta >= 5:
            consecutive_above += 1
            max_delta = max(max_delta, delta)

    if consecutive_above >= 2:
        return [{
            "metric": "resting_hr",
            "type": "spike",
            "severity": "warning",
            "message": (
                f"RHR has been {max_delta:.0f} bpm above your 7-day average "
                f"for {consecutive_above} consecutive days. Could indicate illness "
                "onset, accumulated fatigue, or an acute stressor. Consider a rest day."
            ),
            "values": {
                "today": recent[-1]["rhr"],
                "avg_7d": round(avg_7d, 1),
                "delta": round(max_delta, 1),
                "consecutive_days": consecutive_above,
            },
        }]
    return []


def _check_hrv_suppression(series: list[dict]) -> list[dict]:
    """>1 SD below 7-day average for 3+ consecutive days."""
    valid = [e for e in series if e.get("hrv") is not None]
    if len(valid) < 10:  # need 7 for stats + 3 for check
        return []

    baseline = valid[-10:-3]
    baseline_vals = [e["hrv"] for e in baseline]
    avg = statistics.mean(baseline_vals)
    sd = statistics.stdev(baseline_vals) if len(baseline_vals) > 1 else 0
    threshold = avg - sd

    if sd == 0:
        return []

    recent = valid[-3:]
    consecutive_below = sum(1 for day in recent if day["hrv"] < threshold)

    if consecutive_below >= 3:
        today_hrv = recent[-1]["hrv"]
        return [{
            "metric": "hrv_rmssd",
            "type": "suppression",
            "severity": "warning",
            "message": (
                f"HRV has been suppressed for {consecutive_below} consecutive days "
                f"(below {threshold:.0f} ms, your baseline minus 1 SD). "
                "This suggests accumulated fatigue, poor sleep, or high stress. "
                "Prioritize recovery before high-intensity training."
            ),
            "values": {
                "today": today_hrv,
                "avg_7d": round(avg, 1),
                "sd": round(sd, 1),
                "threshold": round(threshold, 1),
                "consecutive_days": consecutive_below,
            },
        }]
    return []


def _check_sleep_debt(series: list[dict]) -> list[dict]:
    """7-day average sleep duration below 6 hours."""
    valid = [e for e in series if e.get("sleep_hrs") is not None]
    if len(valid) < 7:
        return []

    recent_7 = valid[-7:]
    avg = statistics.mean(e["sleep_hrs"] for e in recent_7)

    if avg < 6.0:
        # Calculate accumulated debt vs 7hr target
        debt = sum(max(0, 7.0 - e["sleep_hrs"]) for e in recent_7)
        return [{
            "metric": "sleep_duration",
            "type": "debt",
            "severity": "warning",
            "message": (
                f"Averaging {avg:.1f} hours of sleep over the past week. "
                f"Accumulated sleep debt is ~{debt:.1f} hours vs a 7-hour target. "
                "Cognitive and metabolic effects compound. "
                "Prioritize an earlier wind-down tonight."
            ),
            "values": {
                "avg_7d": round(avg, 1),
                "debt_hours": round(debt, 1),
                "worst_night": round(min(e["sleep_hrs"] for e in recent_7), 1),
            },
        }]
    return []


def _check_sleep_regularity(series: list[dict]) -> list[dict]:
    """Bedtime standard deviation > 45 minutes over 14-day window."""
    valid = [e for e in series if e.get("sleep_start") is not None]
    if len(valid) < 14:
        return []

    recent_14 = valid[-14:]
    bedtimes_min = []
    for e in recent_14:
        try:
            parts = e["sleep_start"].split(":")
            h, m = int(parts[0]), int(parts[1])
            minutes = h * 60 + m
            if minutes < 720:  # before noon = after midnight
                minutes += 1440
            bedtimes_min.append(minutes)
        except (ValueError, IndexError):
            pass

    if len(bedtimes_min) < 7:
        return []

    sd = statistics.stdev(bedtimes_min)

    if sd > 45:
        return [{
            "metric": "sleep_regularity",
            "type": "irregular",
            "severity": "info",
            "message": (
                f"Bedtime varies by +/-{sd:.0f} minutes over the past 2 weeks. "
                "Target is under 30 minutes. Sleep regularity is a stronger "
                "mortality predictor than duration. A consistent wake time is "
                "the single most effective fix."
            ),
            "values": {
                "bedtime_sd_min": round(sd, 1),
                "target_sd_min": 30,
            },
        }]
    return []


def _check_weight_plateau(weight_data: list[dict]) -> list[dict]:
    """7-day average unchanged for 14+ days during active deficit."""
    if len(weight_data) < 21:  # need 3 weeks
        return []

    # Compute weekly averages for the last 3 weeks
    week1 = weight_data[-7:]
    week2 = weight_data[-14:-7]
    week3 = weight_data[-21:-14]

    avg1 = statistics.mean(e["weight"] for e in week1)
    avg2 = statistics.mean(e["weight"] for e in week2)
    avg3 = statistics.mean(e["weight"] for e in week3)

    # Plateau = last two weeks within 0.5 lbs of each other
    # but prior week was different (so it's not just stable maintenance)
    if abs(avg1 - avg2) < 0.5 and abs(avg3 - avg2) > 0.5:
        return [{
            "metric": "weight",
            "type": "plateau",
            "severity": "info",
            "message": (
                f"Weight has been flat for ~2 weeks "
                f"(this week: {avg1:.1f}, last week: {avg2:.1f}). "
                "If you're in an active deficit, the deficit may not be real. "
                "Check: are you logging all meals? Has NEAT dropped? "
                "Consider a 2-day diet break then resume."
            ),
            "values": {
                "avg_this_week": round(avg1, 1),
                "avg_last_week": round(avg2, 1),
                "avg_2_weeks_ago": round(avg3, 1),
                "stall_weeks": 2,
            },
        }]
    return []


def _check_habit_dropoff(habit_data: list[dict], max_alerts: int = 3) -> list[dict]:
    """Habits below 70% completion over a 14-day window.

    Only reports the top N worst-performing habits to avoid alert fatigue.
    Skips internal/meta habits (prefixed with _).
    """
    if not habit_data:
        return []

    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    recent = [h for h in habit_data if h.get("date", "") >= cutoff]

    if not recent:
        return []

    candidates = []
    sample = recent[0]

    # Skip internal columns
    skip_cols = {"date", "notes"}
    skip_prefixes = ("_",)

    # Detect format: wide vs long
    if "habit" in sample and "completed" in sample:
        habit_names = set(h["habit"] for h in recent)
        for name in sorted(habit_names):
            if name.startswith(skip_prefixes):
                continue
            entries = [h for h in recent if h["habit"] == name]
            completed = sum(
                1 for h in entries
                if h.get("completed", "").lower() in ("yes", "true", "1", "y")
            )
            total = len(entries)
            if total >= 7:
                rate = completed / total * 100
                if rate < 70:
                    candidates.append((rate, name, completed, total))
    else:
        habit_names = [
            k for k in sample.keys()
            if k.lower() not in skip_cols and not k.startswith(skip_prefixes)
        ]
        dates_in_window = sorted(set(h.get("date", "") for h in recent))
        if len(dates_in_window) < 7:
            return []
        for name in habit_names:
            entries = [h for h in recent if h.get(name)]
            completed = sum(
                1 for h in entries
                if (h.get(name) or "").lower() in ("yes", "true", "1", "y")
            )
            total = len(dates_in_window)
            rate = completed / total * 100
            if rate < 70:
                candidates.append((rate, name, completed, total))

    # Sort by completion rate ascending (worst first), take top N
    candidates.sort(key=lambda x: x[0])
    alerts = []
    for rate, name, completed, total in candidates[:max_alerts]:
        alerts.append(_habit_alert(name, rate, completed, total))

    return alerts


def _habit_alert(name: str, rate: float, completed: int, total: int) -> dict:
    display_name = name.replace("_", " ")
    return {
        "metric": "habit",
        "type": "dropoff",
        "severity": "info",
        "message": (
            f"'{display_name}' is at {rate:.0f}% over the past 14 days "
            f"({completed}/{total}). Below 70% means the habit may be too hard "
            "or poorly cued. Consider simplifying or re-anchoring it."
        ),
        "values": {
            "habit": name,
            "completion_rate": round(rate, 1),
            "completed": completed,
            "total": total,
        },
    }


def _check_body_battery(garmin_today: dict, daily_series: list[dict] | None) -> list[dict]:
    """Body battery below 25 for 2+ consecutive days."""
    bb_today = garmin_today.get("body_battery")
    if bb_today is None:
        return []

    # Check yesterday from daily series
    if not daily_series or len(daily_series) < 2:
        return []

    # Body battery isn't in garmin_daily.json (it's intraday only)
    # We can only check today from garmin_today. For consecutive-day check,
    # we'd need to persist daily body battery. For now, just flag critically low today.
    if bb_today < 25:
        return [{
            "metric": "body_battery",
            "type": "depleted",
            "severity": "warning",
            "message": (
                f"Body Battery is at {bb_today}. You're running on empty. "
                "Skip intensity today. Focus on sleep, nutrition, and low-stress movement."
            ),
            "values": {
                "body_battery": bb_today,
                "threshold": 25,
            },
        }]
    return []
