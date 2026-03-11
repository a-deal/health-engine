"""Tests for clinical threshold scoring."""

from engine.scoring.clinical import clinical_assess


def test_apob_optimal():
    zone, note = clinical_assess("apob", 72)
    assert zone == "Optimal"
    assert "ESC" in note


def test_apob_borderline():
    zone, note = clinical_assess("apob", 115)
    assert zone == "Borderline"


def test_apob_elevated():
    zone, note = clinical_assess("apob", 125)
    assert zone == "Elevated"


def test_fasting_glucose_optimal():
    zone, note = clinical_assess("fasting_glucose", 78)
    assert zone == "Optimal"
    assert "ADA" in note


def test_fasting_glucose_prediabetic():
    zone, note = clinical_assess("fasting_glucose", 110)
    assert zone == "Borderline"
    assert "prediabetic" in note.lower()


def test_fasting_glucose_diabetic():
    zone, note = clinical_assess("fasting_glucose", 130)
    assert zone == "Elevated"


def test_hba1c_optimal():
    zone, note = clinical_assess("hba1c", 5.0)
    assert zone == "Optimal"


def test_hba1c_prediabetic():
    zone, note = clinical_assess("hba1c", 6.0)
    assert zone == "Borderline"


def test_tsh_optimal():
    zone, note = clinical_assess("tsh", 1.5)
    assert zone == "Optimal"


def test_tsh_hyperthyroid():
    zone, note = clinical_assess("tsh", 0.3)
    assert zone == "Elevated"
    assert "hyperthyroid" in note.lower()


def test_tsh_subclinical_hypo():
    zone, note = clinical_assess("tsh", 5.0)
    assert zone == "Borderline"


def test_vitamin_d_deficient():
    zone, note = clinical_assess("vitamin_d", 15)
    assert zone == "Elevated"  # "Elevated risk" — deficient
    assert "deficient" in note.lower()


def test_vitamin_d_optimal():
    zone, note = clinical_assess("vitamin_d", 45)
    assert zone == "Optimal"


def test_hscrp_optimal():
    zone, note = clinical_assess("hscrp", 0.5)
    assert zone == "Optimal"


def test_hscrp_elevated():
    zone, note = clinical_assess("hscrp", 4.0)
    assert zone == "Elevated"


def test_bp_optimal():
    zone, note = clinical_assess("bp_systolic", 115)
    assert zone == "Optimal"


def test_bp_stage1():
    zone, note = clinical_assess("bp_systolic", 135)
    assert zone == "Borderline"


def test_none_value_returns_empty():
    zone, note = clinical_assess("apob", None)
    assert zone == ""
    assert note == ""


def test_unknown_metric_returns_empty():
    zone, note = clinical_assess("made_up_metric", 42)
    assert zone == ""
    assert note == ""


def test_vo2_max_by_age_sex():
    # 35M with VO2 52 should be optimal
    zone, note = clinical_assess("vo2_max", 52, age=35, sex="M")
    assert zone == "Optimal"

    # 35M with VO2 35 should be borderline
    zone, note = clinical_assess("vo2_max", 35, age=35, sex="M")
    assert zone == "Elevated"  # Below borderline threshold

    # 55F with VO2 35 should be healthy
    zone, note = clinical_assess("vo2_max", 35, age=55, sex="F")
    assert zone == "Healthy"


def test_hdl_by_sex():
    zone_m, _ = clinical_assess("hdl_c", 55, sex="M")
    zone_f, _ = clinical_assess("hdl_c", 55, sex="F")
    assert zone_m == "Healthy"
    assert zone_f == "Borderline"  # Higher threshold for women


def test_waist_by_sex():
    zone_m, _ = clinical_assess("waist", 38, sex="M")
    zone_f, _ = clinical_assess("waist", 38, sex="F")
    assert zone_m in ("Borderline", "Elevated")
    assert zone_f == "Elevated"


def test_clinical_zone_in_score_output():
    """Clinical zone should appear in score_profile results."""
    from engine.models import Demographics, UserProfile
    from engine.scoring.engine import score_profile

    profile = UserProfile(
        demographics=Demographics(age=35, sex="M"),
        systolic=118,
        apob=72,
        fasting_glucose=78,
    )
    output = score_profile(profile)
    bp_result = output["results"][0]  # Blood Pressure is rank 1
    assert bp_result.clinical_zone == "Optimal"
    assert "AHA" in bp_result.clinical_note

    lipid_result = output["results"][1]  # Lipid Panel
    assert lipid_result.clinical_zone == "Optimal"
    assert "ESC" in lipid_result.clinical_note

    # Check to_dict includes clinical fields
    d = bp_result.to_dict()
    assert "clinical_zone" in d
    assert d["clinical_zone"] == "Optimal"
