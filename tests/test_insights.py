"""Tests for the insights engine."""

from engine.insights.engine import generate_insights


def test_no_data_no_insights():
    """No data should produce no insights."""
    insights = generate_insights()
    assert insights == []


def test_low_hrv_critical():
    """HRV below critical threshold should produce critical insight."""
    garmin = {"hrv_rmssd_avg": 45}
    insights = generate_insights(garmin=garmin)
    assert len(insights) >= 1
    hrv_insights = [i for i in insights if i.category == "hrv"]
    assert len(hrv_insights) == 1
    assert hrv_insights[0].severity == "critical"


def test_high_hrv_positive():
    """HRV above healthy threshold should produce positive insight."""
    garmin = {"hrv_rmssd_avg": 70}
    insights = generate_insights(garmin=garmin)
    hrv_insights = [i for i in insights if i.category == "hrv"]
    assert len(hrv_insights) == 1
    assert hrv_insights[0].severity == "positive"


def test_low_sleep_warning():
    """Sleep below target should produce warning."""
    garmin = {"sleep_duration_avg": 5.5, "hrv_rmssd_avg": 55}
    insights = generate_insights(garmin=garmin)
    sleep_insights = [i for i in insights if i.category == "sleep"]
    assert len(sleep_insights) >= 1
    assert sleep_insights[0].severity == "warning"


def test_elevated_rhr():
    """RHR above threshold should produce critical insight."""
    garmin = {"resting_hr": 60}
    insights = generate_insights(garmin=garmin)
    rhr_insights = [i for i in insights if i.category == "rhr"]
    assert len(rhr_insights) == 1
    assert rhr_insights[0].severity == "critical"


def test_excellent_rhr():
    """RHR below excellent threshold should produce positive insight."""
    garmin = {"resting_hr": 48}
    insights = generate_insights(garmin=garmin)
    rhr_insights = [i for i in insights if i.category == "rhr"]
    assert len(rhr_insights) == 1
    assert rhr_insights[0].severity == "positive"


def test_zone2_strong():
    """Zone 2 above target should produce positive insight."""
    garmin = {"zone2_min_per_week": 180}
    insights = generate_insights(garmin=garmin)
    z2_insights = [i for i in insights if i.category == "zone2"]
    assert len(z2_insights) == 1
    assert z2_insights[0].severity == "positive"


def test_bp_normal():
    """Normal BP should produce positive insight."""
    bp = [{"sys": 115, "dia": 72}]
    insights = generate_insights(bp_readings=bp)
    bp_insights = [i for i in insights if i.category == "bp"]
    assert len(bp_insights) == 1
    assert bp_insights[0].severity == "positive"


def test_custom_thresholds():
    """Custom rules should override defaults."""
    garmin = {"hrv_rmssd_avg": 52}  # Above default critical (50) but below custom (55)
    custom_rules = {
        "hrv": {"critical_low": 55, "warning_low": 60, "healthy_high": 70},
        "rhr": {}, "sleep": {}, "zone2": {}, "weight": {}, "bp": {},
    }
    insights = generate_insights(garmin=garmin, rules=custom_rules)
    hrv_insights = [i for i in insights if i.category == "hrv"]
    assert len(hrv_insights) == 1
    assert hrv_insights[0].severity == "critical"


def test_fast_loss_low_hrv_interaction():
    """Fast weight loss + low HRV should trigger compound insight."""
    garmin = {"hrv_rmssd_avg": 48}
    weights = [{"weight": 200 - i * 0.4} for i in range(10)]  # ~2.8 lbs/week
    insights = generate_insights(garmin=garmin, weights=weights)
    weight_insights = [i for i in insights if i.category == "weight"]
    assert len(weight_insights) >= 1
    assert weight_insights[0].severity == "critical"
