"""Rolling averages for multi-timescale health metrics.

Computes 7-day and 30-day rolling averages for any time series data,
plus trend direction (week-over-week change). Used by the briefing
builder to give Milo context beyond single-day values.
"""

import statistics
from datetime import datetime, timedelta
from typing import Optional


def compute_rolling(
    series: list[dict],
    value_key: str,
    date_key: str = "date",
    windows: tuple[int, ...] = (7, 30),
) -> dict:
    """Compute rolling averages and trends for a daily time series.

    Args:
        series: List of dicts with date and value keys, chronologically ordered.
        value_key: Key to average (e.g., "weight", "rhr", "sleep_hrs").
        date_key: Key for the date field.
        windows: Tuple of window sizes in days.

    Returns:
        Dict with today's value, rolling averages, and trends:
        {
            "today": 193.3,
            "avg_7d": 193.8,
            "avg_30d": 194.2,
            "trend_7d": -0.5,   # change in 7d avg vs prior 7d avg
            "trend_30d": -0.3,  # change in 30d avg vs prior 30d avg
            "n_days": 45,       # total data points available
        }
    """
    if not series:
        return {}

    # Filter to entries that have the value
    valid = [
        e for e in series
        if e.get(value_key) is not None
    ]
    if not valid:
        return {}

    today_val = valid[-1].get(value_key)
    result = {
        "today": _round(today_val),
        "n_days": len(valid),
    }

    for w in windows:
        key_avg = f"avg_{w}d"
        key_trend = f"trend_{w}d"

        # Current window average
        current_window = valid[-w:] if len(valid) >= w else valid
        current_vals = [e[value_key] for e in current_window]
        avg = statistics.mean(current_vals)
        result[key_avg] = _round(avg)

        # Prior window average (for trend)
        if len(valid) >= w * 2:
            prior_window = valid[-(w * 2):-w]
            prior_vals = [e[value_key] for e in prior_window]
            prior_avg = statistics.mean(prior_vals)
            result[key_trend] = _round(avg - prior_avg)
        elif len(valid) > w:
            # Not enough for full prior window, use what we have
            prior_window = valid[:-w]
            prior_vals = [e[value_key] for e in prior_window]
            prior_avg = statistics.mean(prior_vals)
            result[key_trend] = _round(avg - prior_avg)
        else:
            result[key_trend] = None

    return result


def compute_rolling_from_csv(
    rows: list[dict],
    value_key: str,
    date_key: str = "date",
    windows: tuple[int, ...] = (7, 30),
) -> dict:
    """Same as compute_rolling but handles CSV rows where values are strings."""
    converted = []
    for row in rows:
        val = row.get(value_key)
        if val is not None and val != "":
            try:
                converted.append({
                    date_key: row.get(date_key, ""),
                    value_key: float(val),
                })
            except (ValueError, TypeError):
                pass
    return compute_rolling(converted, value_key, date_key, windows)


def compute_protein_rolling(
    meal_rows: list[dict],
    date_key: str = "date",
    windows: tuple[int, ...] = (7, 30),
) -> dict:
    """Compute rolling average daily protein from meal log.

    Aggregates meals per day first, then computes rolling averages
    of daily protein totals.
    """
    # Aggregate protein by day
    daily = {}
    for row in meal_rows:
        d = row.get(date_key, "")
        protein = row.get("protein_g")
        if d and protein:
            try:
                daily[d] = daily.get(d, 0) + float(protein)
            except (ValueError, TypeError):
                pass

    if not daily:
        return {}

    # Convert to sorted series
    series = [
        {"date": d, "protein_g": v}
        for d, v in sorted(daily.items())
    ]
    return compute_rolling(series, "protein_g", windows=windows)


def _round(val, decimals=1):
    """Round a value, handling None."""
    if val is None:
        return None
    return round(val, decimals)
