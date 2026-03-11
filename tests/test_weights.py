"""Tests for weight adjustments (Phase 5)."""

from engine.scoring.tables import (
    TIER1_WEIGHTS, TIER2_WEIGHTS,
    TIER1_STANDING_WEIGHTS, TIER2_STANDING_WEIGHTS,
)


def test_vo2_max_weight_increased():
    assert TIER2_WEIGHTS["vo2_max"] == 6  # Was 5


def test_sleep_weight_increased():
    assert TIER1_WEIGHTS["sleep"] == 6  # Was 5


def test_medications_weight_decreased():
    assert TIER1_WEIGHTS["medications"] == 3  # Was 4


def test_lpa_coverage_weight_unchanged():
    assert TIER1_WEIGHTS["lpa"] == 8


def test_lpa_standing_weight_reduced():
    """Lp(a) standing weight should be less than coverage weight."""
    assert TIER1_STANDING_WEIGHTS["lpa"] == 4
    assert TIER1_STANDING_WEIGHTS["lpa"] < TIER1_WEIGHTS["lpa"]


def test_standing_weights_match_coverage_except_lpa():
    """All standing weights should match coverage weights except Lp(a)."""
    for key in TIER1_WEIGHTS:
        if key != "lpa":
            assert TIER1_STANDING_WEIGHTS[key] == TIER1_WEIGHTS[key], \
                f"Mismatch for {key}: standing={TIER1_STANDING_WEIGHTS[key]}, coverage={TIER1_WEIGHTS[key]}"
    for key in TIER2_WEIGHTS:
        assert TIER2_STANDING_WEIGHTS[key] == TIER2_WEIGHTS[key], \
            f"Mismatch for {key}: standing={TIER2_STANDING_WEIGHTS[key]}, coverage={TIER2_WEIGHTS[key]}"


def test_lpa_bifurcation_affects_percentile():
    """Lp(a) should have less influence on the standing composite than coverage."""
    from engine.models import Demographics, UserProfile
    from engine.scoring.engine import score_profile

    # Profile with only Lp(a) elevated (concerning)
    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        systolic=115,  # Optimal
        apob=72,       # Optimal
        lpa=200,       # Elevated (concerning)
    )
    output = score_profile(profile)

    # The avg_percentile should not be dragged down as much by Lp(a)
    # since standing weight is 4 vs coverage weight 8
    assessed = [r for r in output["results"] if r.percentile_approx is not None]
    lpa_result = [r for r in assessed if r.name == "Lp(a)"][0]
    assert lpa_result.percentile_approx is not None

    # Overall percentile should still be reasonable despite bad Lp(a)
    assert output["avg_percentile"] is not None
    assert output["avg_percentile"] > 30  # Not dragged too low
