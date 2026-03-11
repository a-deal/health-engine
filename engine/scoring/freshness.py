"""Freshness decay and reliability multipliers for health metrics.

Freshness: Data ages. A lipid panel from 18 months ago shouldn't count
the same as one from last week. Uses plateau + linear decay model.

Reliability: Single readings of high-CVI metrics are noisy. hs-CRP has
42% CVI — a single reading is directional only, not definitive.

Together: effective_weight = base_weight × freshness × reliability

Sources:
  - CVI data from Ricos et al., Fraser & Harris biological variation databases
  - BP averaging: AHA recommends 7-day protocol for clinical decisions
  - Freshness windows calibrated from biological half-lives and clinical retest intervals
"""

from datetime import datetime, date
from typing import Optional


# --- Freshness Decay ---

# Per-metric freshness windows (months)
# fresh_window: full credit (1.0), stale_window: decays to 0.0
FRESHNESS_WINDOWS = {
    # Labs — lipids
    "apob":              {"fresh": 6,  "stale": 18},
    "ldl_c":             {"fresh": 6,  "stale": 18},
    "hdl_c":             {"fresh": 6,  "stale": 18},
    "triglycerides":     {"fresh": 3,  "stale": 9},
    "total_cholesterol": {"fresh": 6,  "stale": 18},

    # Labs — metabolic
    "fasting_glucose":   {"fresh": 3,  "stale": 12},
    "hba1c":             {"fresh": 6,  "stale": 18},
    "fasting_insulin":   {"fresh": 3,  "stale": 9},

    # Labs — inflammation
    "hscrp":             {"fresh": 6,  "stale": 12},

    # Labs — liver
    "alt":               {"fresh": 6,  "stale": 18},
    "ggt":               {"fresh": 6,  "stale": 18},

    # Labs — thyroid
    "tsh":               {"fresh": 6,  "stale": 18},

    # Labs — vitamins/minerals
    "vitamin_d":         {"fresh": 6,  "stale": 18},
    "ferritin":          {"fresh": 6,  "stale": 18},

    # Labs — CBC
    "hemoglobin":        {"fresh": 6,  "stale": 18},

    # Blood pressure
    "bp_single":         {"fresh": 1,  "stale": 6},
    "bp_protocol":       {"fresh": 3,  "stale": 12},

    # Wearable metrics — continuous
    "resting_hr":        {"fresh": 0.25, "stale": 1},    # 7 days / 30 days
    "hrv_rmssd_avg":     {"fresh": 0.25, "stale": 1},
    "daily_steps_avg":   {"fresh": 0.25, "stale": 1},
    "sleep_duration_avg":    {"fresh": 0.25, "stale": 1},
    "sleep_regularity_stddev": {"fresh": 0.25, "stale": 1},
    "vo2_max":           {"fresh": 1,  "stale": 3},
    "zone2_min_per_week": {"fresh": 0.25, "stale": 1},

    # Weight/body
    "weight_lbs":        {"fresh": 0.25, "stale": 1},
    "waist":             {"fresh": 1,  "stale": 6},

    # Genetic/lifetime — never stale
    "lpa":               {"fresh": 999, "stale": 9999},
    "family_history":    {"fresh": 999, "stale": 9999},

    # Config-level — always fresh
    "medications":       {"fresh": 999, "stale": 9999},
    "phq9":              {"fresh": 3,  "stale": 12},
}


def freshness_fraction(months_since: float, fresh_window: float,
                       stale_window: float) -> float:
    """
    Plateau + linear decay.

    Returns 1.0 if within fresh_window, decays linearly to 0.0 at stale_window.
    """
    if months_since <= fresh_window:
        return 1.0
    elif months_since <= stale_window:
        span = stale_window - fresh_window
        if span <= 0:
            return 0.0
        return 1.0 - (months_since - fresh_window) / span
    return 0.0


def compute_freshness(metric_key: str, observed_date: Optional[str],
                      as_of: Optional[str] = None) -> float:
    """
    Compute freshness fraction for a metric given its observation date.

    Args:
        metric_key: Key into FRESHNESS_WINDOWS
        observed_date: ISO date string (YYYY-MM-DD) or None
        as_of: Reference date (defaults to today)

    Returns:
        float 0.0-1.0
    """
    if observed_date is None:
        # No date known — assume reasonably fresh (don't penalize)
        return 1.0

    windows = FRESHNESS_WINDOWS.get(metric_key)
    if windows is None:
        return 1.0  # Unknown metric — no decay

    try:
        obs = datetime.strptime(observed_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1.0

    if as_of:
        ref = datetime.strptime(as_of, "%Y-%m-%d").date()
    else:
        ref = date.today()

    days = (ref - obs).days
    if days < 0:
        return 1.0  # Future date, treat as fresh

    months = days / 30.44  # Average days per month
    return freshness_fraction(months, windows["fresh"], windows["stale"])


def freshness_label(fraction: float, observed_date: Optional[str] = None) -> str:
    """Human-readable freshness label."""
    if fraction >= 0.99:
        return "Fresh"
    elif fraction >= 0.75:
        return "Recent"
    elif fraction >= 0.50:
        return "Aging"
    elif fraction >= 0.25:
        return "Stale"
    elif fraction > 0:
        return "Very stale"
    else:
        return "Expired"


# --- Reliability Multipliers ---

# Based on CVI (within-subject biological variation coefficient)
# High CVI = noisy = single reading is unreliable
RELIABILITY_RULES = {
    "hscrp": {
        "single": 0.6,   # 42% CVI — single reading is directional only
        "multi": 1.0,
        "cvi_pct": 42.2,
        "note_single": "Single hs-CRP reading (42% CVI) — directional only",
    },
    "bp": {
        "single": 0.5,   # AHA recommends 7-day avg
        "multi": 0.75,
        "protocol": 1.0,  # 7-day protocol
        "note_single": "Single BP reading — varies 20+ mmHg through the day",
        "note_multi": "Multiple readings averaged — more reliable than single",
        "note_protocol": "7-day protocol — clinical-grade reliability",
    },
    "fasting_insulin": {
        "single": 0.7,   # 21-25% CVI, pulsatile secretion
        "multi": 1.0,
        "cvi_pct": 23,
        "note_single": "Single fasting insulin (23% CVI) — pulsatile secretion adds noise",
    },
    "triglycerides": {
        "single": 0.7,   # 19.9% CVI, fasting state matters
        "multi": 1.0,
        "cvi_pct": 19.9,
        "note_single": "Single triglyceride reading (20% CVI) — fasting compliance varies",
    },
    "vitamin_d": {
        "opposite_season": 0.7,  # 30% seasonal penalty
        "same_season": 1.0,
        "note_opposite": "Vitamin D measured in opposite season — 30% seasonal variation expected",
    },
}


def reliability_factor(metric_key: str, reading_count: int = 1,
                       is_protocol: bool = False,
                       season_match: bool = True) -> tuple[float, str]:
    """
    Compute reliability multiplier for a metric.

    Args:
        metric_key: Key into RELIABILITY_RULES
        reading_count: Number of readings (1 = single, 2+ = averaged)
        is_protocol: Whether reading follows a protocol (e.g., 7-day BP)
        season_match: For vitamin D — whether draw season matches current season

    Returns:
        (reliability_float, note_string)
    """
    rules = RELIABILITY_RULES.get(metric_key)
    if rules is None:
        return 1.0, ""

    # Special case: vitamin D seasonality
    if metric_key == "vitamin_d":
        if not season_match:
            return rules["opposite_season"], rules.get("note_opposite", "")
        return rules["same_season"], ""

    # BP has three tiers
    if metric_key == "bp":
        if is_protocol:
            return rules["protocol"], rules.get("note_protocol", "")
        elif reading_count >= 2:
            return rules["multi"], rules.get("note_multi", "")
        else:
            return rules["single"], rules.get("note_single", "")

    # General: single vs multi
    if reading_count >= 2:
        return rules.get("multi", 1.0), ""
    return rules["single"], rules.get("note_single", "")
