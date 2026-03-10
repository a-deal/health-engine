"""Weight trend analysis — rolling averages, rate of loss, projections."""

import statistics
from datetime import datetime, timedelta
from typing import Optional


def rolling_average(weights: list[dict], window: int = 7) -> list[dict]:
    """
    Compute rolling average over a window of days.

    Args:
        weights: List of dicts with 'date' and 'weight' keys, chronologically ordered
        window: Number of days for rolling average

    Returns:
        List of dicts with 'date', 'weight', and 'rolling_avg' keys
    """
    result = []
    for i, w in enumerate(weights):
        start = max(0, i - window + 1)
        window_vals = [weights[j]["weight"] for j in range(start, i + 1)]
        result.append({
            "date": w["date"],
            "weight": w["weight"],
            "rolling_avg": round(statistics.mean(window_vals), 1),
        })
    return result


def weekly_rate(weights: list[dict]) -> Optional[float]:
    """
    Calculate weekly rate of weight change (lbs/week, positive = loss).

    Args:
        weights: List of dicts with 'date' and 'weight', chronologically ordered, >= 7 entries

    Returns:
        Rate in lbs/week (positive = losing), or None if insufficient data
    """
    if len(weights) < 7:
        return None
    recent = weights[-1]["weight"]
    week_ago = weights[max(0, len(weights) - 8)]["weight"]
    return round(week_ago - recent, 2)


def projected_date(
    current_weight: float,
    target_weight: float,
    weekly_rate: float,
) -> Optional[str]:
    """
    Project the date when target weight will be reached.

    Returns:
        ISO date string, or None if rate <= 0
    """
    if weekly_rate <= 0:
        return None
    remaining = current_weight - target_weight
    if remaining <= 0:
        return datetime.now().strftime("%Y-%m-%d")
    weeks_left = remaining / weekly_rate
    target_date = datetime.now() + timedelta(weeks=weeks_left)
    return target_date.strftime("%Y-%m-%d")


def rate_assessment(rate: float, body_weight: float) -> str:
    """
    Assess if weekly loss rate is in the safe zone.

    Safe zone: 0.5-1% of body weight per week.

    Returns:
        "safe", "aggressive", "very_aggressive", or "too_slow"
    """
    pct = (rate / body_weight) * 100
    if pct > 1.5:
        return "very_aggressive"
    elif pct > 1.0:
        return "aggressive"
    elif pct >= 0.5:
        return "safe"
    else:
        return "too_slow"
