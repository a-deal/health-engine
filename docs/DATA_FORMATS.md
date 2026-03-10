# Data Formats

## CSV Schemas

### weight_log.csv
```
date,weight_lbs,source
2026-01-23,203.0,scale
2026-01-24,202.4,scale
```

### meal_log.csv
```
date,time_of_day,description,protein_g,carbs_g,fat_g,calories
2026-01-23,morning,Protein shake + banana,32,30,4,280
2026-01-23,lunch,Chipotle bowl (double steak),54,73,15,605
```

### strength_log.csv
```
date,exercise,weight_lbs,reps,rpe,notes
2026-01-23,deadlift,405,5,8,garmin:12345678
2026-01-23,bench_press,225,8,7,
```

### bp_log.csv
```
date,systolic,diastolic
2026-01-23,118,72
2026-01-24,115,70
```

### daily_habits.csv
```
date,habit,completed
2026-01-23,creatine,yes
2026-01-23,sleep_by_11,no
```

## JSON Schemas

### garmin_latest.json
```json
{
  "last_updated": "2026-01-23T10:30:00",
  "resting_hr": 52.0,
  "daily_steps_avg": 8500,
  "sleep_regularity_stddev": 35.0,
  "sleep_duration_avg": 6.8,
  "vo2_max": 47.0,
  "hrv_rmssd_avg": 62.0,
  "zone2_min_per_week": 180
}
```

### garmin_daily.json
```json
[
  {"date": "2026-01-23", "rhr": 51.0, "hrv": 64.0, "steps": 9200},
  {"date": "2026-01-24", "rhr": 53.0, "hrv": 58.0, "steps": 7100}
]
```

### Profile JSON (for `cli.py score --profile`)
```json
{
  "demographics": {"age": 35, "sex": "M", "ethnicity": "white"},
  "systolic": 118,
  "diastolic": 72,
  "ldl_c": 95,
  "hdl_c": 55,
  "resting_hr": 52,
  "vo2_max": 47
}
```
See `tests/fixtures/sample_profile.json` for a complete example.
