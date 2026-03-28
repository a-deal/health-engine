"""Progressive disclosure: filter metrics by user tenure and selected outcome.

Two dimensions:
1. Tenure: how long the user has been tracking (controls how much data)
2. Outcome: what goal the user selected (controls which data)
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# Map protocol names and goal IDs to outcome categories
PROTOCOL_TO_OUTCOME = {
    "sleep-stack": "sleep_better",
    "sleep-better": "sleep_better",
    "lose-weight": "lose_weight",
    "weight-loss": "lose_weight",
    "build-strength": "build_strength",
    "strength": "build_strength",
    "more-energy": "more_energy",
    "energy": "more_energy",
    "less-stress": "less_stress",
    "stress": "less_stress",
    "eat-healthier": "eat_healthier",
    "nutrition": "eat_healthier",
    "hair-recovery": "general",  # doesn't map to a health outcome
}

# Metric relevance per outcome: primary, secondary, hidden
# Primary: show in every check-in
# Secondary: show weekly or on-ask
# Hidden: only surface via alerts
OUTCOME_METRICS = {
    "sleep_better": {
        "primary": {"sleep_duration", "hrv_rmssd", "resting_hr"},
        "secondary": {"steps", "weight"},
        "hidden": {"protein_g"},
    },
    "lose_weight": {
        "primary": {"weight", "protein_g", "sleep_duration"},
        "secondary": {"steps", "resting_hr", "hrv_rmssd"},
        "hidden": set(),
    },
    "build_strength": {
        "primary": {"protein_g", "weight", "sleep_duration"},
        "secondary": {"hrv_rmssd", "resting_hr", "steps"},
        "hidden": set(),
    },
    "more_energy": {
        "primary": {"sleep_duration", "hrv_rmssd", "steps", "resting_hr"},
        "secondary": {"weight", "protein_g"},
        "hidden": set(),
    },
    "less_stress": {
        "primary": {"hrv_rmssd", "sleep_duration", "resting_hr"},
        "secondary": {"steps", "weight"},
        "hidden": {"protein_g"},
    },
    "eat_healthier": {
        "primary": {"protein_g", "weight"},
        "secondary": {"sleep_duration", "steps"},
        "hidden": {"hrv_rmssd", "resting_hr"},
    },
    "general": {
        "primary": {"weight", "sleep_duration", "resting_hr", "hrv_rmssd", "steps", "protein_g"},
        "secondary": set(),
        "hidden": set(),
    },
}

# Alert metric mapping (which alert metrics are relevant per outcome)
OUTCOME_ALERT_METRICS = {
    "sleep_better": {"sleep_duration", "sleep_regularity", "hrv_rmssd", "resting_hr", "habit", "body_battery"},
    "lose_weight": {"weight", "sleep_duration", "habit", "resting_hr", "hrv_rmssd", "body_battery"},
    "build_strength": {"hrv_rmssd", "resting_hr", "habit", "body_battery", "sleep_duration", "weight", "training_load"},
    "more_energy": {"sleep_duration", "hrv_rmssd", "resting_hr", "body_battery", "habit", "sleep_regularity"},
    "less_stress": {"hrv_rmssd", "sleep_duration", "resting_hr", "body_battery", "habit", "sleep_regularity"},
    "eat_healthier": {"weight", "habit", "sleep_duration"},
    "general": {"sleep_duration", "sleep_regularity", "hrv_rmssd", "resting_hr", "weight", "habit", "body_battery", "training_load"},
}


def get_tenure_days(data_dir: Path, person_created_at: str | None = None) -> int:
    """Calculate how many days the user has been tracking.

    Checks the earliest entry across all CSV files, or falls back
    to the person record creation date.
    """
    earliest = None

    # Check CSVs for earliest date
    for csv_name in ["weight_log.csv", "meal_log.csv", "daily_habits.csv", "bp_log.csv"]:
        csv_path = data_dir / csv_name
        if csv_path.exists():
            try:
                with open(csv_path) as f:
                    lines = f.readlines()
                if len(lines) > 1:
                    # First data line, first field is date
                    first_date_str = lines[1].split(",")[0].strip()
                    if first_date_str and len(first_date_str) >= 10:
                        d = datetime.strptime(first_date_str[:10], "%Y-%m-%d")
                        if earliest is None or d < earliest:
                            earliest = d
            except (ValueError, IndexError):
                pass

    # Fall back to person record
    if earliest is None and person_created_at:
        try:
            earliest = datetime.fromisoformat(person_created_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            pass

    if earliest is None:
        return 0

    return max(0, (datetime.now() - earliest).days)


def get_tenure_tier(days: int) -> str:
    """Return the tenure tier for progressive disclosure.

    - 'new' (days 1-14): minimal view
    - 'establishing' (days 15-56): moderate view
    - 'established' (day 57+): full view
    """
    if days < 15:
        return "new"
    elif days < 57:
        return "establishing"
    else:
        return "established"


def resolve_outcome(config: dict) -> str:
    """Determine the user's primary outcome from their config focus list.

    Reads the highest-priority protocol and maps it to an outcome category.
    Falls back to 'general' if no focus is set.
    """
    focus = config.get("focus", [])
    if not focus:
        return "general"

    # Sort by priority (lowest number = highest priority)
    sorted_focus = sorted(focus, key=lambda f: f.get("priority", 99))
    primary_protocol = sorted_focus[0].get("protocol", "")
    return PROTOCOL_TO_OUTCOME.get(primary_protocol, "general")


def filter_horizons(horizons: dict, outcome: str, tenure_tier: str) -> dict:
    """Filter horizons based on outcome relevance and tenure tier.

    Returns a filtered dict with the same structure, plus a 'meta' key
    indicating what was filtered and why.
    """
    if not horizons:
        return {}

    metrics_config = OUTCOME_METRICS.get(outcome, OUTCOME_METRICS["general"])
    primary = metrics_config["primary"]
    secondary = metrics_config["secondary"]

    filtered = {}

    if tenure_tier == "new":
        # Only show primary metrics, today + 7d avg only (no 30d, no trends)
        for key in primary:
            if key in horizons:
                h = horizons[key]
                filtered[key] = {
                    "today": h.get("today"),
                    "avg_7d": h.get("avg_7d"),
                }
    elif tenure_tier == "establishing":
        # Primary: full horizons. Secondary: today + 7d only.
        for key in primary:
            if key in horizons:
                filtered[key] = horizons[key]
        for key in secondary:
            if key in horizons:
                h = horizons[key]
                filtered[key] = {
                    "today": h.get("today"),
                    "avg_7d": h.get("avg_7d"),
                }
    else:
        # Established: everything, but tag relevance
        for key, h in horizons.items():
            entry = dict(h)
            if key in primary:
                entry["relevance"] = "primary"
            elif key in secondary:
                entry["relevance"] = "secondary"
            else:
                entry["relevance"] = "context"
            filtered[key] = entry

    return filtered


def filter_alerts(alerts: list[dict], outcome: str, tenure_tier: str) -> list[dict]:
    """Filter alerts based on outcome relevance and tenure tier.

    New users: no alerts (system is calibrating).
    Establishing: only primary metric alerts.
    Established: all relevant alerts.
    """
    if tenure_tier == "new":
        return []  # No alerts during calibration period

    relevant_metrics = OUTCOME_ALERT_METRICS.get(outcome, OUTCOME_ALERT_METRICS["general"])

    filtered = []
    for alert in alerts:
        metric = alert.get("metric", "")
        if metric in relevant_metrics:
            filtered.append(alert)
        elif tenure_tier == "established":
            # Established users see all alerts, but tag non-primary as context
            alert_copy = dict(alert)
            alert_copy["relevance"] = "context"
            filtered.append(alert_copy)

    return filtered
