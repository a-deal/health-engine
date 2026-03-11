"""Tests for cross-metric interaction pattern detection."""

from engine.models import Demographics, UserProfile
from engine.insights.patterns import detect_patterns


def _make_profile(**kwargs) -> UserProfile:
    return UserProfile(demographics=Demographics(age=45, sex="M"), **kwargs)


def test_no_data_no_patterns():
    profile = _make_profile()
    patterns = detect_patterns(profile)
    assert patterns == []


def test_metabolic_syndrome_5_of_5():
    profile = _make_profile(
        triglycerides=160, hdl_c=38, fasting_glucose=105,
        waist_circumference=42, systolic=135, diastolic=88,
    )
    patterns = detect_patterns(profile)
    metsyn = [p for p in patterns if "Metabolic syndrome" in p.title]
    assert len(metsyn) == 1
    assert metsyn[0].severity == "critical"
    assert "5/5" in metsyn[0].title


def test_metabolic_syndrome_3_of_5():
    profile = _make_profile(
        triglycerides=160, hdl_c=38, fasting_glucose=105,
    )
    patterns = detect_patterns(profile)
    metsyn = [p for p in patterns if "Metabolic syndrome" in p.title]
    assert len(metsyn) == 1
    assert "3/5" in metsyn[0].title


def test_metabolic_syndrome_2_of_5_no_trigger():
    profile = _make_profile(
        triglycerides=160, hdl_c=38,
    )
    patterns = detect_patterns(profile)
    metsyn = [p for p in patterns if "Metabolic syndrome" in p.title]
    assert len(metsyn) == 0


def test_metabolic_syndrome_female_thresholds():
    """Female HDL threshold is 50, male is 40."""
    profile = UserProfile(
        demographics=Demographics(age=45, sex="F"),
        triglycerides=160, hdl_c=45,  # Below 50 for F
        fasting_glucose=105,
    )
    patterns = detect_patterns(profile)
    metsyn = [p for p in patterns if "Metabolic syndrome" in p.title]
    assert len(metsyn) == 1


def test_atherogenic_dyslipidemia():
    profile = _make_profile(triglycerides=200, hdl_c=38)
    patterns = detect_patterns(profile)
    athero = [p for p in patterns if "Atherogenic" in p.title]
    assert len(athero) == 1
    assert athero[0].severity == "warning"
    assert "ratio" in athero[0].title.lower()


def test_atherogenic_not_triggered_normal_tg():
    profile = _make_profile(triglycerides=80, hdl_c=55)
    patterns = detect_patterns(profile)
    athero = [p for p in patterns if "Atherogenic" in p.title]
    assert len(athero) == 0


def test_insulin_resistance_pattern():
    profile = _make_profile(
        fasting_insulin=15, fasting_glucose=92,
        triglycerides=180, hdl_c=45,
    )
    patterns = detect_patterns(profile)
    ir = [p for p in patterns if "Insulin resistance" in p.title]
    assert len(ir) == 1
    assert "working overtime" in ir[0].body


def test_insulin_resistance_not_triggered_normal_insulin():
    profile = _make_profile(
        fasting_insulin=4, fasting_glucose=85,
    )
    patterns = detect_patterns(profile)
    ir = [p for p in patterns if "Insulin resistance" in p.title]
    assert len(ir) == 0


def test_recovery_stress_3_signals():
    profile = _make_profile()
    garmin = {"hrv_rmssd_avg": 48, "resting_hr": 62, "sleep_duration_avg": 5.5}
    patterns = detect_patterns(profile, garmin=garmin)
    recovery = [p for p in patterns if "Recovery stress" in p.title]
    assert len(recovery) == 1
    assert recovery[0].severity == "critical"


def test_recovery_stress_2_signals():
    profile = _make_profile()
    garmin = {"hrv_rmssd_avg": 48, "resting_hr": 62, "sleep_duration_avg": 7.5}
    patterns = detect_patterns(profile, garmin=garmin)
    recovery = [p for p in patterns if "Recovery stress" in p.title]
    assert len(recovery) == 1
    assert recovery[0].severity == "warning"


def test_recovery_stress_1_signal_no_trigger():
    profile = _make_profile()
    garmin = {"hrv_rmssd_avg": 48, "resting_hr": 52, "sleep_duration_avg": 7.5}
    patterns = detect_patterns(profile, garmin=garmin)
    recovery = [p for p in patterns if "Recovery stress" in p.title]
    assert len(recovery) == 0


def test_patterns_emit_pattern_category():
    """All pattern insights should have category='pattern'."""
    profile = _make_profile(
        triglycerides=160, hdl_c=38, fasting_glucose=105,
    )
    patterns = detect_patterns(profile)
    for p in patterns:
        assert p.category == "pattern"
