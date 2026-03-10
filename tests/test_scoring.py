"""Tests for the scoring engine."""

import json
from pathlib import Path

from engine.models import Demographics, UserProfile, Standing
from engine.scoring.engine import score_profile, assess, age_bucket, percentile_to_standing
from engine.scoring.tables import BP_SYSTOLIC, LDL_C, HDL_C, FASTING_INSULIN


FIXTURES = Path(__file__).parent / "fixtures"


def test_age_bucket():
    assert age_bucket(25) == "20-29"
    assert age_bucket(35) == "30-39"
    assert age_bucket(45) == "40-49"
    assert age_bucket(55) == "50-59"
    assert age_bucket(65) == "60-69"
    assert age_bucket(75) == "70+"


def test_percentile_to_standing():
    assert percentile_to_standing(90) == Standing.OPTIMAL
    assert percentile_to_standing(85) == Standing.OPTIMAL
    assert percentile_to_standing(70) == Standing.GOOD
    assert percentile_to_standing(50) == Standing.AVERAGE
    assert percentile_to_standing(20) == Standing.BELOW_AVG
    assert percentile_to_standing(10) == Standing.CONCERNING


def test_assess_lower_is_better():
    demo = Demographics(age=35, sex="M")
    # BP 110 should be optimal (<=110 first cutoff)
    standing, pct = assess(110, BP_SYSTOLIC, demo, nhanes_key="bp_systolic")
    assert standing in (Standing.OPTIMAL, Standing.GOOD)
    assert pct is not None


def test_assess_higher_is_better():
    demo = Demographics(age=35, sex="M")
    # HDL 65 should be good or optimal
    standing, pct = assess(65, HDL_C, demo, nhanes_key="hdl_c")
    assert standing in (Standing.OPTIMAL, Standing.GOOD)


def test_assess_none_value():
    demo = Demographics(age=35, sex="M")
    standing, pct = assess(None, BP_SYSTOLIC, demo)
    assert standing == Standing.UNKNOWN
    assert pct is None


def test_score_empty_profile():
    """Scoring an empty profile should return 0% coverage."""
    profile = UserProfile(demographics=Demographics(age=35, sex="M"))
    output = score_profile(profile)
    assert output["coverage_score"] == 0
    assert output["avg_percentile"] is None
    assert len(output["gaps"]) == 20  # all metrics are gaps


def test_score_full_profile():
    """Scoring a fully populated profile should return 100% coverage."""
    with open(FIXTURES / "sample_profile.json") as f:
        data = json.load(f)
    demo_data = data.pop("demographics")
    profile = UserProfile(
        demographics=Demographics(**demo_data),
        **{k: v for k, v in data.items() if hasattr(UserProfile, k)},
    )
    output = score_profile(profile)
    assert output["coverage_score"] == 100
    assert output["avg_percentile"] is not None
    assert len(output["gaps"]) == 0


def test_score_partial_profile():
    """Scoring with just BP + lipids should give partial coverage."""
    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        systolic=120,
        diastolic=75,
        ldl_c=100,
    )
    output = score_profile(profile)
    assert 0 < output["coverage_score"] < 100
    assert output["avg_percentile"] is not None
    assert len(output["gaps"]) > 0


def test_results_have_required_fields():
    """Each MetricResult should have the expected fields."""
    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        resting_hr=52,
    )
    output = score_profile(profile)
    for r in output["results"]:
        assert hasattr(r, "name")
        assert hasattr(r, "tier")
        assert hasattr(r, "rank")
        assert hasattr(r, "has_data")
        assert hasattr(r, "standing")
        d = r.to_dict()
        assert "name" in d
        assert "standing" in d
