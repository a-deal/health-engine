# Onboarding — Get Running in 5 Minutes

## Prerequisites

- Python 3.11+
- A Garmin Connect account (optional, for wearable data)

## Step 1: Install

```bash
git clone <repo-url> && cd health-engine
python3 -m pip install -e .
```

For Garmin integration:
```bash
python3 -m pip install -e ".[garmin]"
```

## Step 2: Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:
- Set your age and sex
- Set macro/calorie targets (optional)
- Add Garmin credentials if you have a Garmin wearable

## Step 3: Score

Score with defaults (empty profile shows your gaps):
```bash
python3 cli.py score --config config.yaml
```

Score with a profile JSON:
```bash
python3 cli.py score --config config.yaml --profile tests/fixtures/sample_profile.json
```

## Step 4: Pull Garmin Data (optional)

```bash
# Set credentials (first time only)
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your-password"

# Pull metrics
python3 cli.py pull garmin --config config.yaml

# Pull with workout history
python3 cli.py pull garmin --config config.yaml --workouts

# Pull with 90-day trend data
python3 cli.py pull garmin --config config.yaml --history
```

## Step 5: Generate Insights

```bash
python3 cli.py insights --config config.yaml
```

This reads whatever data is in your `data/` directory (Garmin JSON, weight CSVs, etc.) and generates actionable health insights.

## Step 6: Check Status

```bash
python3 cli.py status --config config.yaml
```

Shows which data files are present and when they were last updated.

## Data Files

All personal data lives in `data/` (gitignored). Supported formats:

| File | Format | Description |
|------|--------|-------------|
| `garmin_latest.json` | JSON | Latest Garmin metrics (auto-created by `pull`) |
| `garmin_daily.json` | JSON | Daily RHR/HRV/steps series (auto-created by `pull --history`) |
| `weight_log.csv` | CSV | Daily weigh-ins: `date,weight_lbs,source` |
| `meal_log.csv` | CSV | Meal entries: `date,time_of_day,description,protein_g,carbs_g,fat_g,calories` |
| `strength_log.csv` | CSV | Lift entries: `date,exercise,weight_lbs,reps,rpe,notes` |
| `bp_log.csv` | CSV | BP readings: `date,systolic,diastolic` |

## Customizing Thresholds

Edit `engine/insights/rules.yaml` to adjust insight thresholds for your needs. For example, if you want HRV warnings at different levels:

```yaml
hrv:
  critical_low: 45   # your personal threshold
  warning_low: 50
  healthy_high: 60
```

## Using as a Python Library

```python
from engine.models import Demographics, UserProfile
from engine.scoring.engine import score_profile
from engine.insights.engine import generate_insights

# Score a profile
profile = UserProfile(
    demographics=Demographics(age=35, sex="M"),
    resting_hr=52,
    hrv_rmssd_avg=62,
)
output = score_profile(profile)

# Generate insights
insights = generate_insights(garmin={"resting_hr": 52, "hrv_rmssd_avg": 62})
```
