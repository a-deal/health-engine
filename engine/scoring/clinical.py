"""Clinical threshold scoring — evidence-based zones independent of population percentiles.

Sources:
  - Blood Pressure: AHA/ACC 2017 Hypertension Guidelines
  - ApoB: ESC/EAS 2019 Dyslipidaemia Guidelines
  - LDL-C: ACC/AHA Cholesterol Guidelines
  - Fasting Glucose, HbA1c: ADA Standards of Medical Care 2023
  - Fasting Insulin: Literature consensus (Kraft, Reaven)
  - hs-CRP: AHA/CDC Scientific Statement
  - TSH: Endocrine Society Clinical Practice Guidelines
  - Vitamin D: Endocrine Society 2011
  - VO2 Max: ACSM Guidelines (age/sex stratified)
  - Triglycerides: AHA/ACC, NCEP ATP III
  - HDL-C: AHA/ACC
  - Waist: NHLBI/AHA metabolic syndrome criteria
"""

from typing import Optional


# Zone ordering: Optimal > Healthy > Borderline > Elevated
ZONE_ORDER = {"Optimal": 0, "Healthy": 1, "Borderline": 2, "Elevated": 3}

# Each entry: (metric_key, lower_is_better, thresholds_dict)
# Thresholds can be "universal" or keyed by (age_bucket, sex)
# Format: {"optimal": (lo, hi), "healthy": (lo, hi), "borderline": (lo, hi), "elevated": ...}
# For "lower_is_better": optimal < healthy < borderline < elevated
# For "higher_is_better": optimal > healthy > borderline > elevated

CLINICAL_THRESHOLDS = {
    "bp_systolic": {
        "source": "AHA/ACC 2017",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 120),
            ("Healthy",    120, 130),   # Elevated per AHA
            ("Borderline", 130, 140),   # Stage 1 hypertension
            ("Elevated",   140, None),  # Stage 2 hypertension
        ],
    },
    "bp_diastolic": {
        "source": "AHA/ACC 2017",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 80),
            ("Healthy",    80, 85),
            ("Borderline", 85, 90),
            ("Elevated",   90, None),
        ],
    },
    "apob": {
        "source": "ESC/EAS 2019",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 80),
            ("Healthy",    80, 100),
            ("Borderline", 100, 120),
            ("Elevated",   120, None),
        ],
    },
    "ldl_c": {
        "source": "ACC/AHA",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 100),
            ("Healthy",    100, 130),
            ("Borderline", 130, 160),
            ("Elevated",   160, None),
        ],
    },
    "hdl_c": {
        "source": "AHA/ACC",
        "lower_is_better": False,
        "by_sex": {
            "M": [
                ("Optimal",    60, None),
                ("Healthy",    50, 60),
                ("Borderline", 40, 50),
                ("Elevated",   None, 40),  # "Low" = elevated risk
            ],
            "F": [
                ("Optimal",    70, None),
                ("Healthy",    60, 70),
                ("Borderline", 50, 60),
                ("Elevated",   None, 50),
            ],
        },
    },
    "triglycerides": {
        "source": "AHA/ACC, NCEP ATP III",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 100),
            ("Healthy",    100, 150),
            ("Borderline", 150, 200),
            ("Elevated",   200, None),
        ],
    },
    "fasting_glucose": {
        "source": "ADA 2023",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 90),
            ("Healthy",    90, 100),    # Normal but upper range
            ("Borderline", 100, 126),   # Prediabetes
            ("Elevated",   126, None),  # Diabetes threshold
        ],
    },
    "hba1c": {
        "source": "ADA 2023",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 5.2),
            ("Healthy",    5.2, 5.7),   # Normal
            ("Borderline", 5.7, 6.5),   # Prediabetes
            ("Elevated",   6.5, None),  # Diabetes threshold
        ],
    },
    "fasting_insulin": {
        "source": "Literature consensus",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 5),
            ("Healthy",    5, 12),
            ("Borderline", 12, 18),
            ("Elevated",   18, None),
        ],
    },
    "hscrp": {
        "source": "AHA/CDC",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 1.0),
            ("Healthy",    1.0, 2.0),
            ("Borderline", 2.0, 3.0),
            ("Elevated",   3.0, None),
        ],
    },
    "tsh": {
        "source": "Endocrine Society",
        "lower_is_better": None,  # Bidirectional
        "universal": [
            ("Optimal",    0.5, 2.5),
            ("Healthy",    2.5, 4.0),
            ("Borderline", 4.0, 10.0),
            ("Elevated",   10.0, None),  # Overt hypothyroidism
        ],
        "low_flag": 0.4,  # Below this = hyperthyroid concern
    },
    "vitamin_d": {
        "source": "Endocrine Society 2011",
        "lower_is_better": False,
        "universal": [
            ("Optimal",    40, None),
            ("Healthy",    30, 40),
            ("Borderline", 20, 30),    # Insufficiency
            ("Elevated",   None, 20),  # Deficiency
        ],
    },
    "vo2_max": {
        "source": "ACSM",
        "lower_is_better": False,
        "by_age_sex": {
            ("30-39", "M"): [
                ("Optimal",    50, None),
                ("Healthy",    44, 50),
                ("Borderline", 38, 44),
                ("Elevated",   None, 38),  # "Low" = elevated mortality risk
            ],
            ("20-29", "M"): [
                ("Optimal",    52, None),
                ("Healthy",    46, 52),
                ("Borderline", 40, 46),
                ("Elevated",   None, 40),
            ],
            ("40-49", "M"): [
                ("Optimal",    48, None),
                ("Healthy",    42, 48),
                ("Borderline", 36, 42),
                ("Elevated",   None, 36),
            ],
            ("50-59", "M"): [
                ("Optimal",    45, None),
                ("Healthy",    39, 45),
                ("Borderline", 33, 39),
                ("Elevated",   None, 33),
            ],
            ("60-69", "M"): [
                ("Optimal",    41, None),
                ("Healthy",    35, 41),
                ("Borderline", 29, 35),
                ("Elevated",   None, 29),
            ],
            ("70+", "M"): [
                ("Optimal",    37, None),
                ("Healthy",    31, 37),
                ("Borderline", 25, 31),
                ("Elevated",   None, 25),
            ],
            ("20-29", "F"): [
                ("Optimal",    46, None),
                ("Healthy",    40, 46),
                ("Borderline", 35, 40),
                ("Elevated",   None, 35),
            ],
            ("30-39", "F"): [
                ("Optimal",    44, None),
                ("Healthy",    38, 44),
                ("Borderline", 33, 38),
                ("Elevated",   None, 33),
            ],
            ("40-49", "F"): [
                ("Optimal",    41, None),
                ("Healthy",    35, 41),
                ("Borderline", 30, 35),
                ("Elevated",   None, 30),
            ],
            ("50-59", "F"): [
                ("Optimal",    38, None),
                ("Healthy",    32, 38),
                ("Borderline", 27, 32),
                ("Elevated",   None, 27),
            ],
            ("60-69", "F"): [
                ("Optimal",    35, None),
                ("Healthy",    29, 35),
                ("Borderline", 24, 29),
                ("Elevated",   None, 24),
            ],
            ("70+", "F"): [
                ("Optimal",    32, None),
                ("Healthy",    26, 32),
                ("Borderline", 21, 26),
                ("Elevated",   None, 21),
            ],
        },
    },
    "ferritin": {
        "source": "Clinical consensus",
        "lower_is_better": False,
        "by_sex": {
            "M": [
                ("Optimal",    100, 300),
                ("Healthy",    40, 100),
                ("Borderline", 20, 40),
                ("Elevated",   None, 20),  # Deficiency
            ],
            "F": [
                ("Optimal",    50, 200),
                ("Healthy",    20, 50),
                ("Borderline", 12, 20),
                ("Elevated",   None, 12),
            ],
        },
        "high_flag": {"M": 500, "F": 300},  # Iron overload concern
    },
    "hemoglobin": {
        "source": "WHO/Clinical",
        "lower_is_better": False,
        "by_sex": {
            "M": [
                ("Optimal",    15.0, 17.5),
                ("Healthy",    14.0, 15.0),
                ("Borderline", 13.0, 14.0),
                ("Elevated",   None, 13.0),  # Anemia
            ],
            "F": [
                ("Optimal",    13.5, 16.0),
                ("Healthy",    12.0, 13.5),
                ("Borderline", 11.0, 12.0),
                ("Elevated",   None, 11.0),
            ],
        },
    },
    "alt": {
        "source": "ACG 2017",
        "lower_is_better": True,
        "by_sex": {
            "M": [
                ("Optimal",    None, 25),
                ("Healthy",    25, 33),
                ("Borderline", 33, 50),
                ("Elevated",   50, None),
            ],
            "F": [
                ("Optimal",    None, 19),
                ("Healthy",    19, 25),
                ("Borderline", 25, 40),
                ("Elevated",   40, None),
            ],
        },
    },
    "ggt": {
        "source": "Clinical consensus",
        "lower_is_better": True,
        "by_sex": {
            "M": [
                ("Optimal",    None, 25),
                ("Healthy",    25, 40),
                ("Borderline", 40, 65),
                ("Elevated",   65, None),
            ],
            "F": [
                ("Optimal",    None, 20),
                ("Healthy",    20, 30),
                ("Borderline", 30, 50),
                ("Elevated",   50, None),
            ],
        },
    },
    "waist": {
        "source": "NHLBI/AHA",
        "lower_is_better": True,
        "by_sex": {
            "M": [
                ("Optimal",    None, 34),
                ("Healthy",    34, 37),
                ("Borderline", 37, 40),
                ("Elevated",   40, None),   # MetS cutoff
            ],
            "F": [
                ("Optimal",    None, 30),
                ("Healthy",    30, 33),
                ("Borderline", 33, 35),
                ("Elevated",   35, None),
            ],
        },
    },
    "rhr": {
        "source": "Clinical consensus",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 55),
            ("Healthy",    55, 65),
            ("Borderline", 65, 80),
            ("Elevated",   80, None),
        ],
    },
    "lpa": {
        "source": "EAS consensus",
        "lower_is_better": True,
        "universal": [
            ("Optimal",    None, 30),
            ("Healthy",    30, 75),
            ("Borderline", 75, 125),
            ("Elevated",   125, None),
        ],
    },
}

# Clinical note templates — {value} and {source} are interpolated
CLINICAL_NOTES = {
    "bp_systolic": {
        "Optimal": "{value} mmHg — below the {source} threshold of 120. Excellent cardiovascular risk profile.",
        "Healthy": "{value} mmHg — elevated range per {source}. Not hypertension, but worth monitoring.",
        "Borderline": "{value} mmHg — Stage 1 hypertension per {source}. Lifestyle intervention recommended.",
        "Elevated": "{value} mmHg — Stage 2 hypertension per {source}. Clinical follow-up recommended.",
    },
    "apob": {
        "Optimal": "ApoB {value} is below the {source} target of 80 mg/dL for primary prevention.",
        "Healthy": "ApoB {value} is within normal range per {source}.",
        "Borderline": "ApoB {value} exceeds the {source} primary prevention target of 100. Particle-driven risk.",
        "Elevated": "ApoB {value} is significantly elevated per {source}. Strong predictor of atherosclerotic CVD.",
    },
    "fasting_glucose": {
        "Optimal": "Fasting glucose {value} — well within optimal range per {source}.",
        "Healthy": "Fasting glucose {value} — normal per {source}, upper portion of reference range.",
        "Borderline": "Fasting glucose {value} — prediabetic range per {source} (100-125 mg/dL).",
        "Elevated": "Fasting glucose {value} — meets {source} diabetes threshold (≥126 mg/dL).",
    },
    "hba1c": {
        "Optimal": "HbA1c {value}% — excellent glycemic control per {source}.",
        "Healthy": "HbA1c {value}% — normal per {source}.",
        "Borderline": "HbA1c {value}% — prediabetic range per {source} (5.7-6.4%).",
        "Elevated": "HbA1c {value}% — meets {source} diabetes threshold (≥6.5%).",
    },
    "fasting_insulin": {
        "Optimal": "Fasting insulin {value} — indicates excellent insulin sensitivity.",
        "Healthy": "Fasting insulin {value} — within healthy range.",
        "Borderline": "Fasting insulin {value} — suggests early insulin resistance. Glucose may still look normal.",
        "Elevated": "Fasting insulin {value} — significant insulin resistance. Metabolic intervention warranted.",
    },
    "hscrp": {
        "Optimal": "hs-CRP {value} — low cardiovascular inflammation risk per {source}.",
        "Healthy": "hs-CRP {value} — average risk per {source}.",
        "Borderline": "hs-CRP {value} — high risk category per {source}.",
        "Elevated": "hs-CRP {value} — very high. Rule out acute infection; if persistent, significant CVD risk factor.",
    },
    "tsh": {
        "Optimal": "TSH {value} — optimal thyroid function per {source}.",
        "Healthy": "TSH {value} — within reference range per {source}.",
        "Borderline": "TSH {value} — subclinical hypothyroidism range per {source}. Recheck in 6-12 weeks.",
        "Elevated": "TSH {value} — overt hypothyroidism per {source}. Clinical evaluation recommended.",
    },
    "vitamin_d": {
        "Optimal": "Vitamin D {value} ng/mL — sufficient per {source}.",
        "Healthy": "Vitamin D {value} ng/mL — adequate per {source}.",
        "Borderline": "Vitamin D {value} ng/mL — insufficient per {source}. Supplementation recommended.",
        "Elevated": "Vitamin D {value} ng/mL — deficient per {source}. 2000-5000 IU/day supplementation advised.",
    },
    "vo2_max": {
        "Optimal": "VO2 Max {value} — superior cardiorespiratory fitness. Strong mortality protection.",
        "Healthy": "VO2 Max {value} — good fitness level per {source}.",
        "Borderline": "VO2 Max {value} — below average per {source}. Room for significant improvement.",
        "Elevated": "VO2 Max {value} — low fitness level per {source}. Strongest modifiable mortality predictor.",
    },
}


def _age_bucket(age: int) -> str:
    if age < 30:
        return "20-29"
    elif age < 40:
        return "30-39"
    elif age < 50:
        return "40-49"
    elif age < 60:
        return "50-59"
    elif age < 70:
        return "60-69"
    return "70+"


def _match_zone(value: float, zones: list) -> Optional[str]:
    """Match a value against a list of (zone_name, lo, hi) tuples."""
    for zone_name, lo, hi in zones:
        if lo is None and hi is None:
            continue
        if lo is None:
            if value < hi:
                return zone_name
        elif hi is None:
            if value >= lo:
                return zone_name
        else:
            if lo <= value < hi:
                return zone_name
    return None


def clinical_assess(metric_key: str, value: Optional[float],
                    age: int = 35, sex: str = "M") -> tuple[str, str]:
    """
    Assess a metric value against clinical thresholds.

    Returns:
        (clinical_zone, clinical_note) — zone is one of
        "Optimal"/"Healthy"/"Borderline"/"Elevated"/""
        note is a human-readable interpretation with source citation.
    """
    if value is None or metric_key not in CLINICAL_THRESHOLDS:
        return "", ""

    config = CLINICAL_THRESHOLDS[metric_key]
    source = config["source"]

    # Handle TSH low flag (hyperthyroid)
    if metric_key == "tsh" and value < config.get("low_flag", 0):
        return "Elevated", f"TSH {value} — below {config['low_flag']}, suggests hyperthyroidism per {source}."

    # Handle ferritin high flag (iron overload)
    if metric_key == "ferritin":
        high_flags = config.get("high_flag", {})
        threshold = high_flags.get(sex)
        if threshold and value > threshold:
            return "Elevated", f"Ferritin {value} — above {threshold}, iron overload concern."

    # Get the right zone list
    if "universal" in config:
        zones = config["universal"]
    elif "by_sex" in config:
        zones = config["by_sex"].get(sex)
        if not zones:
            return "", ""
    elif "by_age_sex" in config:
        bucket = _age_bucket(age)
        zones = config["by_age_sex"].get((bucket, sex))
        if not zones:
            return "", ""
    else:
        return "", ""

    zone = _match_zone(value, zones)
    if not zone:
        return "", ""

    # Build note
    notes_for_metric = CLINICAL_NOTES.get(metric_key, {})
    note_template = notes_for_metric.get(zone, "")
    if note_template:
        note = note_template.format(value=value, source=source)
    else:
        note = f"{metric_key} {value} — {zone} per {source}."

    return zone, note
