#!/usr/bin/env python3
"""Score a health profile in 10 lines."""

from engine.models import Demographics, UserProfile
from engine.scoring.engine import score_profile, print_report

# Create a profile with whatever data you have
profile = UserProfile(
    demographics=Demographics(age=35, sex="M"),
    systolic=118,
    diastolic=72,
    resting_hr=52,
    hrv_rmssd_avg=62,
    vo2_max=47,
    daily_steps_avg=8500,
)

# Score it
output = score_profile(profile)
print_report(output)

# Access individual results programmatically
for r in output["results"]:
    if r.has_data:
        print(f"  {r.name}: {r.standing.value} (~{r.percentile_approx}th percentile)")
