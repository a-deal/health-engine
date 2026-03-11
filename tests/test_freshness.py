"""Tests for freshness decay and reliability multipliers."""

from engine.scoring.freshness import (
    freshness_fraction, compute_freshness, freshness_label,
    reliability_factor,
)


# --- Freshness Fraction ---

def test_freshness_within_fresh_window():
    assert freshness_fraction(0, 6, 18) == 1.0
    assert freshness_fraction(3, 6, 18) == 1.0
    assert freshness_fraction(6, 6, 18) == 1.0


def test_freshness_decays_linearly():
    # Midpoint of decay: 6 + (18-6)/2 = 12 months -> 0.5
    frac = freshness_fraction(12, 6, 18)
    assert abs(frac - 0.5) < 0.01


def test_freshness_at_stale_boundary():
    assert freshness_fraction(18, 6, 18) == 0.0


def test_freshness_beyond_stale():
    assert freshness_fraction(24, 6, 18) == 0.0


def test_freshness_negative_months():
    # Future date = fresh
    assert freshness_fraction(-1, 6, 18) == 1.0


# --- Compute Freshness ---

def test_compute_freshness_recent_lab():
    """Lab from 2 months ago should be fully fresh for ApoB (6mo window)."""
    frac = compute_freshness("apob", "2026-01-10", as_of="2026-03-10")
    assert frac == 1.0


def test_compute_freshness_stale_lab():
    """Lab from 14 months ago should be partially fresh for ApoB."""
    frac = compute_freshness("apob", "2025-01-10", as_of="2026-03-10")
    assert 0.0 < frac < 1.0


def test_compute_freshness_expired_lab():
    """Lab from 24 months ago should be 0 for ApoB (18mo stale window)."""
    frac = compute_freshness("apob", "2024-03-10", as_of="2026-03-10")
    assert frac == 0.0


def test_compute_freshness_wearable():
    """Wearable data from 2 weeks ago should be partially fresh (7-day window)."""
    frac = compute_freshness("resting_hr", "2026-02-24", as_of="2026-03-10")
    assert 0.0 < frac < 1.0


def test_compute_freshness_no_date():
    """No date = assume fresh (don't penalize missing dates)."""
    assert compute_freshness("apob", None) == 1.0


def test_compute_freshness_lpa_never_stales():
    """Lp(a) is genetic — should always be fresh."""
    frac = compute_freshness("lpa", "2020-01-01", as_of="2026-03-10")
    assert frac == 1.0


def test_compute_freshness_unknown_metric():
    """Unknown metric key should return 1.0 (no penalty)."""
    assert compute_freshness("unknown_metric", "2024-01-01") == 1.0


# --- Freshness Label ---

def test_freshness_label():
    assert freshness_label(1.0) == "Fresh"
    assert freshness_label(0.8) == "Recent"
    assert freshness_label(0.5) == "Aging"
    assert freshness_label(0.3) == "Stale"
    assert freshness_label(0.1) == "Very stale"
    assert freshness_label(0.0) == "Expired"


# --- Reliability Factor ---

def test_reliability_hscrp_single():
    rel, note = reliability_factor("hscrp", reading_count=1)
    assert rel == 0.6
    assert "42%" in note


def test_reliability_hscrp_multi():
    rel, note = reliability_factor("hscrp", reading_count=2)
    assert rel == 1.0
    assert note == ""


def test_reliability_bp_single():
    rel, note = reliability_factor("bp", reading_count=1)
    assert rel == 0.5


def test_reliability_bp_multi():
    rel, note = reliability_factor("bp", reading_count=3)
    assert rel == 0.75


def test_reliability_bp_protocol():
    rel, note = reliability_factor("bp", reading_count=7, is_protocol=True)
    assert rel == 1.0
    assert "clinical-grade" in note.lower()


def test_reliability_fasting_insulin_single():
    rel, note = reliability_factor("fasting_insulin", reading_count=1)
    assert rel == 0.7


def test_reliability_triglycerides_single():
    rel, note = reliability_factor("triglycerides", reading_count=1)
    assert rel == 0.7


def test_reliability_unknown_metric():
    rel, note = reliability_factor("ldl_c", reading_count=1)
    assert rel == 1.0  # Not in reliability rules = full confidence
    assert note == ""


def test_reliability_vitamin_d_opposite_season():
    rel, note = reliability_factor("vitamin_d", season_match=False)
    assert rel == 0.7
    assert "seasonal" in note.lower()


def test_reliability_vitamin_d_same_season():
    rel, note = reliability_factor("vitamin_d", season_match=True)
    assert rel == 1.0


# --- Integration: Freshness affects coverage score ---

def test_stale_data_reduces_coverage():
    """Coverage should decrease when lab data is old."""
    from engine.models import Demographics, UserProfile
    from engine.scoring.engine import score_profile

    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        apob=72,
    )
    # Fresh data
    output_fresh = score_profile(profile, metric_dates={"apob": "2026-03-01"},
                                 as_of="2026-03-10")
    # Stale data (14 months old)
    output_stale = score_profile(profile, metric_dates={"apob": "2025-01-10"},
                                 as_of="2026-03-10")

    assert output_fresh["coverage_score"] > output_stale["coverage_score"]


def test_freshness_in_to_dict():
    """MetricResult.to_dict() should include freshness when < 1.0."""
    from engine.models import Demographics, UserProfile
    from engine.scoring.engine import score_profile

    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        apob=72,
    )
    output = score_profile(profile, metric_dates={"apob": "2025-06-01"},
                           as_of="2026-03-10")
    lipid_result = output["results"][1]  # Lipid Panel
    d = lipid_result.to_dict()
    assert "freshness_fraction" in d
    assert d["freshness_fraction"] < 1.0
