"""NHANES continuous percentile lookup.

Given a biomarker value, demographics, and the NHANES percentile tables,
returns the exact population percentile (0-100) via linear interpolation.
"""

import json
from pathlib import Path

import numpy as np

PERCENTILES_FILE = Path(__file__).parent.parent / "data" / "nhanes_percentiles.json"

_data = None


def _load():
    global _data
    if _data is None:
        with open(PERCENTILES_FILE) as f:
            _data = json.load(f)
    return _data


def get_percentile(metric_key: str, value: float, age_bucket: str, sex: str) -> float | None:
    """
    Look up the population percentile for a given biomarker value.

    Args:
        metric_key: Key in nhanes_percentiles.json (e.g., "fasting_insulin")
        value: The biomarker value
        age_bucket: e.g., "30-39"
        sex: "M" or "F"

    Returns:
        Percentile (0-100) or None if metric/group not found.
        The returned percentile always means "% of population you're better than."
    """
    data = _load()
    metric = data["metrics"].get(metric_key)
    if metric is None:
        return None

    group_key = f"{age_bucket}|{sex}"
    group = metric["groups"].get(group_key) or metric["groups"].get("universal")
    if group is None:
        return None

    lower_is_better = metric["lower_is_better"]
    pct_points = data["percentile_points"]
    pct_values = [group["percentiles"][str(p)] for p in pct_points]

    raw_percentile = float(np.interp(value, pct_values, pct_points))
    raw_percentile = max(1.0, min(99.0, raw_percentile))

    if lower_is_better:
        return round(100.0 - raw_percentile, 1)
    else:
        return round(raw_percentile, 1)


def get_standing(percentile: float) -> str:
    """Map a percentile to a standing label."""
    if percentile >= 85:
        return "Optimal"
    elif percentile >= 65:
        return "Good"
    elif percentile >= 35:
        return "Average"
    elif percentile >= 15:
        return "Below Average"
    else:
        return "Concerning"


def score_value(metric_key: str, value: float, age_bucket: str, sex: str) -> dict | None:
    """Full scoring: percentile + standing for a biomarker value."""
    pct = get_percentile(metric_key, value, age_bucket, sex)
    if pct is None:
        return None
    return {
        "percentile": pct,
        "standing": get_standing(pct),
    }
