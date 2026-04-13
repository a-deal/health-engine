#!/usr/bin/env python3
"""Generate trends.md for a user from their Garmin daily data and weight log.

Runs before morning cron to give the coach context on what changed.
Usage: python3 scripts/update_trends.py <user_id>
"""

import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

def load_garmin_daily(user_dir):
    path = user_dir / "garmin_daily.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)

def load_weight_log(user_dir):
    path = user_dir / "weight_log.csv"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().strip().split('\n'):
        if line.startswith('date') or not line.strip():
            continue
        parts = line.split(',')
        if len(parts) >= 2:
            try:
                entries.append({'date': parts[0], 'weight': float(parts[1])})
            except ValueError:
                continue
    return entries

def load_habits(user_dir):
    path = user_dir / "daily_habits.csv"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().strip().split('\n'):
        if line.startswith('date') or not line.strip():
            continue
        parts = line.split(',')
        if len(parts) >= 2:
            entries.append({'date': parts[0], 'value': parts[1].strip()})
    return entries

def avg(values):
    if not values:
        return None
    return round(statistics.mean(values), 1)

def trend_arrow(current, previous):
    if current is None or previous is None:
        return ""
    diff = current - previous
    if abs(diff) < 0.5:
        return "steady"
    return f"{'up' if diff > 0 else 'down'} {abs(diff):.1f}"

def generate_trends(user_id):
    data_dir = Path(f"/Users/andrew/src/health-engine/data/users/{user_id}")
    if not data_dir.exists():
        print(f"No data dir for {user_id}")
        return

    garmin = load_garmin_daily(data_dir)
    weights = load_weight_log(data_dir)
    habits = load_habits(data_dir)

    today = datetime.now().strftime("%Y-%m-%d")

    # Split into this week (last 7 days) and prior week
    last_7 = garmin[-7:] if len(garmin) >= 7 else garmin
    prior_7 = garmin[-14:-7] if len(garmin) >= 14 else []

    lines = [f"# Trends for {user_id}", f"Updated: {today}", ""]

    # Sleep
    sleep_now = avg([d['sleep_hrs'] for d in last_7 if d.get('sleep_hrs')])
    sleep_prev = avg([d['sleep_hrs'] for d in prior_7 if d.get('sleep_hrs')]) if prior_7 else None
    lines.append("## Sleep")
    if sleep_now:
        lines.append(f"- 7-day avg: {sleep_now} hrs ({trend_arrow(sleep_now, sleep_prev)})")
    if last_7:
        recent_nights = [(d.get('date',''), d.get('sleep_hrs','?'), d.get('sleep_start','?')) for d in last_7[-3:]]
        for date, hrs, start in recent_nights:
            lines.append(f"- {date}: {hrs}hrs, bed at {start}")
    below_target = sum(1 for d in last_7 if d.get('sleep_hrs') and d['sleep_hrs'] < 7.0)
    if last_7:
        lines.append(f"- Nights below 7hrs: {below_target}/{len(last_7)}")
    lines.append("")

    # RHR
    rhr_now = avg([d['rhr'] for d in last_7 if d.get('rhr')])
    rhr_prev = avg([d['rhr'] for d in prior_7 if d.get('rhr')]) if prior_7 else None
    lines.append("## Resting Heart Rate")
    if rhr_now:
        lines.append(f"- 7-day avg: {rhr_now} bpm ({trend_arrow(rhr_now, rhr_prev)})")
    lines.append("")

    # HRV
    hrv_now = avg([d['hrv'] for d in last_7 if d.get('hrv')])
    hrv_prev = avg([d['hrv'] for d in prior_7 if d.get('hrv')]) if prior_7 else None
    lines.append("## HRV")
    if hrv_now:
        lines.append(f"- 7-day avg: {hrv_now} ms ({trend_arrow(hrv_now, hrv_prev)})")
    lines.append("")

    # Steps
    steps_now = avg([d['steps'] for d in last_7 if d.get('steps')])
    steps_prev = avg([d['steps'] for d in prior_7 if d.get('steps')]) if prior_7 else None
    lines.append("## Steps")
    if steps_now:
        lines.append(f"- 7-day avg: {int(steps_now)} ({trend_arrow(steps_now, steps_prev)})")
    lines.append("")

    # Weight
    lines.append("## Weight")
    if weights:
        latest = weights[-1]
        lines.append(f"- Latest: {latest['weight']} lbs ({latest['date']})")
        if len(weights) >= 7:
            recent_avg = avg([w['weight'] for w in weights[-7:]])
            prior_avg = avg([w['weight'] for w in weights[-14:-7]]) if len(weights) >= 14 else None
            lines.append(f"- 7-day avg: {recent_avg} lbs ({trend_arrow(recent_avg, prior_avg)})")
    else:
        lines.append("- No weight data yet")
    lines.append("")

    # Habits
    lines.append("## Habits")
    if habits:
        streak = 0
        for h in reversed(habits):
            if h['value'].lower() in ('y', 'yes', 'true', '1'):
                streak += 1
            else:
                break
        total_yes = sum(1 for h in habits if h['value'].lower() in ('y', 'yes', 'true', '1'))
        lines.append(f"- Kitchen closed: {total_yes}/{len(habits)} days, current streak: {streak}")
    else:
        lines.append("- No habit data yet")
    lines.append("")

    # Alerts
    lines.append("## Alerts")
    alerts = []
    if sleep_now and sleep_now < 6.0:
        alerts.append("Sleep critically low (under 6hrs avg). Prioritize bedtime.")
    if sleep_now and sleep_now < 7.0:
        alerts.append("Sleep below target (under 7hrs avg).")
    if rhr_now and rhr_now > 80:
        alerts.append(f"RHR elevated at {rhr_now} bpm. Check stress/recovery.")
    if hrv_now and hrv_now < 20:
        alerts.append(f"HRV critically low at {hrv_now} ms.")
    if not alerts:
        alerts.append("No alerts.")
    for a in alerts:
        lines.append(f"- {a}")

    output = "\n".join(lines)
    trends_path = data_dir / "trends.md"
    trends_path.write_text(output)
    print(f"Trends updated: {trends_path}")
    print(output)

if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "grigoriy"
    generate_trends(user_id)
