"""Strength tracking — 1RM estimation, DOTS score, progression analysis."""

import math
from typing import Optional


def est_1rm(weight: float, reps: int, rpe: Optional[float] = None) -> float:
    """
    Estimate 1RM from a set using RPE-based method.

    Uses Epley formula with RPE adjustment:
    effective_reps = reps + RIR (reps in reserve)
    1RM = weight * (1 + effective_reps / 30)

    Args:
        weight: Weight lifted (lbs)
        reps: Repetitions performed
        rpe: Rate of Perceived Exertion (1-10). If provided, RIR = 10 - RPE.

    Returns:
        Estimated 1RM in lbs
    """
    rir = (10 - rpe) if rpe else 0
    effective_reps = reps + rir
    if effective_reps <= 0:
        return weight
    return round(weight * (1 + effective_reps / 30))


def dots_score(total: float, body_weight: float, sex: str = "M") -> float:
    """
    Calculate DOTS score (modern powerlifting relative strength metric).

    Args:
        total: Sum of best squat + bench + deadlift (lbs)
        body_weight: Body weight (lbs)
        sex: "M" or "F"

    Returns:
        DOTS score (higher is better)
    """
    bw_kg = body_weight * 0.453592
    total_kg = total * 0.453592

    if sex == "M":
        a = -307.75076
        b = 24.0900756
        c = -0.1918759221
        d = 0.0007391293
        e = -0.000001093
    else:
        a = -57.96288
        b = 13.6175032
        c = -0.1126655495
        d = 0.0005158568
        e = -0.0000010706

    denominator = a + b * bw_kg + c * bw_kg**2 + d * bw_kg**3 + e * bw_kg**4
    if denominator <= 0:
        return 0
    coefficient = 500 / denominator
    return round(total_kg * coefficient, 1)


def progression_summary(
    lift_history: list[dict],
    exercise: str,
) -> Optional[dict]:
    """
    Analyze progression for a specific lift.

    Args:
        lift_history: List of dicts with 'date', 'exercise', 'weight_lbs', 'reps', 'rpe'
        exercise: Normalized exercise name (e.g., 'deadlift', 'squat', 'bench_press')

    Returns:
        Dict with current_1rm, peak_1rm, peak_pct, recent_sets, or None
    """
    filtered = [s for s in lift_history if s.get("exercise") == exercise]
    if not filtered:
        return None

    # Calculate estimated 1RM for each set
    for s in filtered:
        try:
            weight = float(s.get("weight_lbs") or 0)
        except (ValueError, TypeError):
            weight = 0
        try:
            reps = int(float(s.get("reps") or 0))
        except (ValueError, TypeError):
            reps = 0
        rpe = None
        if s.get("rpe"):
            try:
                rpe = float(s["rpe"])
            except (ValueError, TypeError):
                pass
        if weight > 0 and reps > 0:
            s["est_1rm"] = est_1rm(weight, reps, rpe)
        else:
            s["est_1rm"] = 0

    # Sort by date
    filtered.sort(key=lambda s: s.get("date", ""))

    peak_1rm = max(s["est_1rm"] for s in filtered)
    recent = filtered[-5:]  # last 5 sets
    current_1rm = max(s["est_1rm"] for s in recent) if recent else 0

    return {
        "exercise": exercise,
        "current_1rm": current_1rm,
        "peak_1rm": peak_1rm,
        "peak_pct": round(current_1rm / peak_1rm * 100) if peak_1rm > 0 else 0,
        "total_sets": len(filtered),
        "recent_sets": recent,
    }
