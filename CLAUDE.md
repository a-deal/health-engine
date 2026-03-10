# health-engine — Project Instructions for Claude

## What This Is

A standalone health intelligence engine that scores a user's health profile against population data (NHANES percentiles), generates actionable insights from wearable/lab data, and integrates with Garmin Connect.

This is a **library + CLI tool**, not a web app. It's designed to be imported by other projects (iOS apps, dashboards, web apps) or used directly from the terminal.

## Quick Reference

```bash
python3 cli.py score                           # Score (empty profile → shows gaps)
python3 cli.py score --profile path/to.json    # Score a profile JSON
python3 cli.py insights                        # Generate insights from data/
python3 cli.py pull garmin                     # Pull Garmin Connect data
python3 cli.py status                          # Show what data files exist
python3 -m pytest tests/ -v                    # Run tests (24 tests)
```

## Architecture

```
engine/
├── models.py              # Core types: Demographics, UserProfile, MetricResult, Insight
├── scoring/
│   ├── engine.py          # score_profile() — main entry point, 20 metrics across 2 tiers
│   ├── tables.py          # Cutoff tables (BP, lipids, metabolic, etc.)
│   └── nhanes.py          # NHANES continuous percentile lookup (numpy interp)
├── insights/
│   ├── engine.py          # generate_insights() — threshold-based rules
│   ├── rules.yaml         # Configurable thresholds (HRV, RHR, sleep, etc.)
│   └── coaching.py        # Higher-level: sleep debt, deficit impact, taper readiness
├── integrations/
│   └── garmin.py          # GarminClient class — pull RHR, HRV, sleep, steps, VO2, workouts
├── tracking/
│   ├── weight.py          # Rolling avg, weekly rate, projected date, rate assessment
│   ├── nutrition.py       # Remaining-to-hit, daily totals, protein check
│   ├── strength.py        # est_1rm(), dots_score(), progression_summary()
│   └── habits.py          # streak(), gap_analysis()
└── data/
    └── nhanes_percentiles.json  # Pre-built NHANES tables (ships with package)
```

JS ports live in `js/` for client-side use.

## Key Concepts

- **Coverage score**: What % of high-ROI health data do you have? (0-100%)
- **Assessment score**: For data you have, where do you stand vs peers? (percentile)
- **Gap analysis**: What's missing, ranked by leverage (coverage weight)
- **Insights**: Threshold-based rules that flag HRV drops, sleep debt, fast weight loss, etc.

## Config

All personal data lives in `config.yaml` (gitignored). Template: `config.example.yaml`.
Data files live in `data/` (gitignored). See `docs/DATA_FORMATS.md` for CSV/JSON schemas.

## Rules

- Never hardcode personal data (names, ages, weights, credentials) in source files
- All thresholds go in `rules.yaml`, not in code
- Exercise name mappings go in `config.yaml`, not hardcoded
- Garmin credentials via config or env vars, never in code
- Run tests after changes: `python3 -m pytest tests/ -v`
- Use `python3` not `python`

## Helping Users Get Started

If someone asks how to get started:
1. Run `./setup.sh` for interactive setup
2. Or manually: `cp config.example.yaml config.yaml`, edit it, `python3 -m pip install -e .`
3. Point them to `docs/ONBOARDING.md` for the full walkthrough

## Docs

- `docs/ONBOARDING.md` — Setup guide (5 minutes)
- `docs/SCORING.md` — How scoring works (tiers, weights, percentiles)
- `docs/METRICS.md` — Full 20-metric catalog with evidence
- `docs/DATA_FORMATS.md` — CSV/JSON schemas for data files
