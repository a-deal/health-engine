"""Nutrition tracking — remaining-to-hit, daily totals, macro analysis."""

from typing import Optional


def remaining_to_hit(
    meals: list[dict],
    targets: dict,
) -> dict:
    """
    Calculate remaining macros to hit for the day.

    Args:
        meals: List of meal dicts with 'protein_g', 'carbs_g', 'fat_g', 'calories' keys
        targets: Dict with 'protein', 'carbs', 'fat', 'calories' keys

    Returns:
        Dict with remaining values for each macro (negative = over target)
    """
    eaten = daily_totals(meals)
    return {
        "protein_g": round(targets.get("protein", 0) - eaten["protein_g"], 1),
        "carbs_g": round(targets.get("carbs", 0) - eaten["carbs_g"], 1),
        "fat_g": round(targets.get("fat", 0) - eaten["fat_g"], 1),
        "calories": round(targets.get("calories", 0) - eaten["calories"], 1),
    }


def daily_totals(meals: list[dict]) -> dict:
    """
    Sum macros from a list of meals.

    Args:
        meals: List of meal dicts with numeric macro fields

    Returns:
        Dict with total protein_g, carbs_g, fat_g, calories
    """
    totals = {"protein_g": 0, "carbs_g": 0, "fat_g": 0, "calories": 0}
    for m in meals:
        totals["protein_g"] += _safe_float(m.get("protein_g"))
        totals["carbs_g"] += _safe_float(m.get("carbs_g"))
        totals["fat_g"] += _safe_float(m.get("fat_g"))
        totals["calories"] += _safe_float(m.get("calories"))
    return {k: round(v, 1) for k, v in totals.items()}


def protein_check(
    protein_eaten: float,
    protein_target: float,
    consecutive_low_days: int = 0,
) -> Optional[str]:
    """
    Check if protein intake needs attention.

    Returns warning message or None.
    """
    remaining = protein_target - protein_eaten
    if remaining > protein_target * 0.5:
        return f"Only {protein_eaten:.0f}g protein so far — {remaining:.0f}g remaining. Plan a high-protein meal."
    if consecutive_low_days >= 3:
        return f"Protein below {protein_target:.0f}g for {consecutive_low_days} consecutive days. Muscle retention at risk."
    return None


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
