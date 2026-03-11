"""Cross-metric interaction pattern detection.

Detects clinically meaningful compound patterns that are invisible when
metrics are scored independently. These are insight-layer additions —
they don't change individual scores, they surface interpretive flags.

Patterns:
  - Metabolic syndrome (NCEP ATP III / IDF harmonized criteria)
  - Atherogenic dyslipidemia (TG/HDL ratio proxy)
  - Insulin resistance pattern (compensatory hyperinsulinemia)
  - Recovery stress (wearable composite signal)
"""

from typing import Optional
from engine.models import Insight, UserProfile


def detect_patterns(profile: UserProfile,
                    garmin: Optional[dict] = None) -> list[Insight]:
    """
    Detect cross-metric interaction patterns from a scored profile.

    Returns list of Insight objects with category="pattern".
    """
    insights = []

    metsyn = _detect_metabolic_syndrome(profile)
    if metsyn:
        insights.append(metsyn)

    athero = _detect_atherogenic_dyslipidemia(profile)
    if athero:
        insights.append(athero)

    ir = _detect_insulin_resistance(profile)
    if ir:
        insights.append(ir)

    recovery = _detect_recovery_stress(profile, garmin)
    if recovery:
        insights.append(recovery)

    return insights


def _detect_metabolic_syndrome(profile: UserProfile) -> Optional[Insight]:
    """
    Metabolic syndrome: >= 3 of 5 criteria (NCEP ATP III harmonized).
      1. TG >= 150 mg/dL
      2. HDL < 40 (M) or < 50 (F)
      3. Fasting glucose >= 100 mg/dL
      4. Waist > 40" (M) or > 35" (F)
      5. BP >= 130/85
    """
    criteria_met = 0
    criteria_detail = []
    sex = profile.demographics.sex

    if profile.triglycerides is not None and profile.triglycerides >= 150:
        criteria_met += 1
        criteria_detail.append(f"TG {profile.triglycerides}")

    if profile.hdl_c is not None:
        hdl_threshold = 40 if sex == "M" else 50
        if profile.hdl_c < hdl_threshold:
            criteria_met += 1
            criteria_detail.append(f"HDL {profile.hdl_c}")

    if profile.fasting_glucose is not None and profile.fasting_glucose >= 100:
        criteria_met += 1
        criteria_detail.append(f"glucose {profile.fasting_glucose}")

    if profile.waist_circumference is not None:
        waist_threshold = 40 if sex == "M" else 35
        if profile.waist_circumference > waist_threshold:
            criteria_met += 1
            criteria_detail.append(f"waist {profile.waist_circumference}\"")

    if profile.systolic is not None and profile.diastolic is not None:
        if profile.systolic >= 130 or profile.diastolic >= 85:
            criteria_met += 1
            criteria_detail.append(f"BP {profile.systolic}/{profile.diastolic}")

    if criteria_met >= 3:
        detail = ", ".join(criteria_detail)
        return Insight(
            severity="critical",
            category="pattern",
            title=f"Metabolic syndrome pattern ({criteria_met}/5 criteria)",
            body=(
                f"Criteria met: {detail}. "
                "These metrics individually may look borderline, but together they signal "
                "metabolic syndrome — a compound risk that's worse than the sum of parts. "
                "Linked to 2x CVD risk and 5x diabetes risk. "
                "Lifestyle intervention (Zone 2, weight management, sleep) is first-line treatment."
            ),
        )
    return None


def _detect_atherogenic_dyslipidemia(profile: UserProfile) -> Optional[Insight]:
    """
    Atherogenic dyslipidemia: High TG + low HDL + proxy for small dense LDL.
    Proxy: TG/HDL ratio > 3.5 suggests elevated particle number.
    """
    if profile.triglycerides is None or profile.hdl_c is None:
        return None
    if profile.hdl_c <= 0:
        return None

    ratio = profile.triglycerides / profile.hdl_c

    if ratio > 3.5 and profile.triglycerides >= 130:
        return Insight(
            severity="warning",
            category="pattern",
            title=f"Atherogenic dyslipidemia pattern (TG/HDL ratio {ratio:.1f})",
            body=(
                f"TG {profile.triglycerides} / HDL {profile.hdl_c} = ratio {ratio:.1f} (threshold: 3.5). "
                "This pattern suggests elevated small dense LDL particle number despite potentially "
                "normal LDL-C. ApoB measurement would confirm — it's a better predictor than LDL-C "
                "when TG is elevated."
            ),
        )
    return None


def _detect_insulin_resistance(profile: UserProfile) -> Optional[Insight]:
    """
    Insulin resistance pattern: fasting insulin elevated while glucose still "normal".
    The hallmark of early IR — glucose is the last thing to move.
    Also uses TG/HDL ratio as a secondary proxy.
    """
    if profile.fasting_insulin is None:
        return None

    glucose_normal = (profile.fasting_glucose is not None and profile.fasting_glucose < 100)
    insulin_elevated = profile.fasting_insulin > 12

    # TG/HDL ratio as supporting signal
    tg_hdl_elevated = False
    if profile.triglycerides is not None and profile.hdl_c is not None and profile.hdl_c > 0:
        tg_hdl_elevated = (profile.triglycerides / profile.hdl_c) > 2.5

    if insulin_elevated and glucose_normal:
        body = (
            f"Fasting insulin {profile.fasting_insulin} µIU/mL is elevated while "
            f"glucose {profile.fasting_glucose} mg/dL looks normal. "
            "This is early insulin resistance — the pancreas is working overtime to maintain "
            "glucose homeostasis. This is the marker that standard panels miss."
        )
        if tg_hdl_elevated:
            body += (
                f" TG/HDL ratio {profile.triglycerides / profile.hdl_c:.1f} "
                "further supports the insulin resistance pattern."
            )
        return Insight(
            severity="warning",
            category="pattern",
            title="Insulin resistance pattern — glucose masking",
            body=body,
        )
    return None


def _detect_recovery_stress(profile: UserProfile,
                            garmin: Optional[dict] = None) -> Optional[Insight]:
    """
    Recovery stress: HRV declining + RHR rising + sleep short.
    Wearable composite signal of accumulated physiological stress.
    """
    g = garmin or {}
    hrv = g.get("hrv_rmssd_avg") or (profile.hrv_rmssd_avg if profile.hrv_rmssd_avg else None)
    rhr = g.get("resting_hr") or (profile.resting_hr if profile.resting_hr else None)
    sleep = g.get("sleep_duration_avg") or (profile.sleep_duration_avg if profile.sleep_duration_avg else None)

    if hrv is None or rhr is None or sleep is None:
        return None

    # Thresholds for "stressed" state
    hrv_low = hrv < 55
    rhr_high = rhr > 58
    sleep_short = sleep < 6.5

    signals = sum([hrv_low, rhr_high, sleep_short])

    if signals >= 2:
        parts = []
        if hrv_low:
            parts.append(f"HRV {hrv:.0f}ms (low)")
        if rhr_high:
            parts.append(f"RHR {rhr:.0f}bpm (elevated)")
        if sleep_short:
            parts.append(f"sleep {sleep:.1f}hrs (short)")

        severity = "critical" if signals == 3 else "warning"
        return Insight(
            severity=severity,
            category="pattern",
            title=f"Recovery stress pattern — {', '.join(parts)}",
            body=(
                "Your body is accumulating stress. "
                f"{' + '.join(parts)} — these compound. "
                "Consider a deload, extra sleep, or a temporary caloric bump. "
                "Recovery deficit builds silently and shows up as plateaus, illness, or injury."
            ),
        )
    return None
