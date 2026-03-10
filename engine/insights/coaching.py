"""Higher-level coaching signals — sleep debt, deficit impact, taper logic.

These go beyond threshold-based insights and look at compound effects
across multiple data streams.
"""

from typing import Optional

from engine.models import Insight


def assess_sleep_debt(
    sleep_hrs_avg: Optional[float],
    sleep_target: float = 7.0,
    days: int = 7,
) -> Optional[Insight]:
    """Estimate cumulative sleep debt over a period."""
    if sleep_hrs_avg is None:
        return None
    debt = (sleep_target - sleep_hrs_avg) * days
    if debt <= 0:
        return None
    if debt > 7:
        return Insight(
            severity="critical", category="sleep",
            title=f"~{debt:.0f}hr sleep debt accumulated this week",
            body=f"Averaging {sleep_hrs_avg:.1f}hrs vs {sleep_target}hr target = "
                 f"~{debt:.0f}hr debt over {days} days. This compounds — "
                 f"recovery capacity, training quality, and hunger signals all degrade. "
                 f"Prioritize 1-2 catch-up nights before pushing training.",
        )
    elif debt > 3.5:
        return Insight(
            severity="warning", category="sleep",
            title=f"~{debt:.1f}hr sleep debt this week",
            body=f"Averaging {sleep_hrs_avg:.1f}hrs vs {sleep_target}hr target. "
                 f"Not critical yet, but the deficit erodes HRV and willpower over time.",
        )
    return None


def assess_deficit_impact(
    weekly_loss_rate: Optional[float],
    hrv: Optional[float],
    rhr: Optional[float],
    weeks_in_deficit: Optional[int] = None,
) -> Optional[Insight]:
    """Assess whether the caloric deficit is sustainable given recovery markers."""
    if weekly_loss_rate is None:
        return None

    signals = []
    if hrv is not None and hrv < 55:
        signals.append(f"HRV at {hrv:.0f}ms (below 55)")
    if rhr is not None and rhr > 55:
        signals.append(f"RHR at {rhr:.0f}bpm (above 55)")

    if weekly_loss_rate > 2.0 and signals:
        body = (f"Losing {weekly_loss_rate:.1f} lbs/week with {' and '.join(signals)}. "
                f"The deficit may be too aggressive for current recovery capacity.")
        if weeks_in_deficit and weeks_in_deficit > 8:
            body += f" After {weeks_in_deficit} weeks in a deficit, fatigue accumulates — consider a diet break."
        return Insight(
            severity="critical", category="weight",
            title="Deficit may be unsustainable",
            body=body,
        )

    if weeks_in_deficit and weeks_in_deficit > 10 and not signals:
        return Insight(
            severity="neutral", category="weight",
            title=f"Week {weeks_in_deficit} of deficit — recovery holding",
            body=f"Recovery markers are stable through week {weeks_in_deficit}. "
                 f"If strength is maintained, current approach is working. "
                 f"Plan a transition to maintenance in the next 2-4 weeks.",
        )
    return None


def assess_taper_readiness(
    weeks_in_deficit: Optional[int],
    weight_current: Optional[float],
    weight_target: Optional[float],
    weekly_loss_rate: Optional[float],
) -> Optional[Insight]:
    """Suggest when to start tapering the deficit (reverse diet)."""
    if not all([weeks_in_deficit, weight_current, weight_target]):
        return None

    remaining = weight_current - weight_target
    if remaining <= 0:
        return Insight(
            severity="positive", category="weight",
            title="Target weight reached — time to reverse diet",
            body=f"You've hit {weight_target} lbs. Start reverse dieting: "
                 f"add 100-150 cal/week for 4-6 weeks. Expect 2-3 lbs of water/glycogen. "
                 f"Strength should start recovering within 2-3 weeks.",
        )

    if remaining <= 3 and weekly_loss_rate and weekly_loss_rate > 0:
        weeks_left = remaining / weekly_loss_rate
        return Insight(
            severity="neutral", category="weight",
            title=f"~{remaining:.1f} lbs to target — begin planning exit",
            body=f"At {weekly_loss_rate:.1f} lbs/week, ~{weeks_left:.0f} weeks remain. "
                 f"Start thinking about reverse diet strategy: calorie targets, "
                 f"training volume adjustments, new maintenance calories.",
        )

    return None
