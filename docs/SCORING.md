# How Scoring Works

## Overview

The health engine scores a user profile across 20 health metrics in 2 tiers:

- **Tier 1: Foundation** (10 metrics, 60% of total weight) — the essentials everyone should track
- **Tier 2: Enhanced** (10 metrics, 25% of total weight) — deeper health intelligence

## Two Scores

### Coverage Score
"What percentage of high-ROI health data do you have?"

Each metric has a **coverage weight** reflecting its relative importance (evidence strength × actionability). If you have data for a metric, its weight counts toward your coverage score.

### Assessment Score
"For the data you have, where do you stand vs peers?"

Each metric with actual values is scored against population data, producing a **percentile** (0-100, where higher = better). The assessment score is the average percentile across all assessed metrics.

## Percentile Sources

1. **Primary: NHANES continuous** — Survey-weighted percentile tables from NHANES 2017-March 2020 Pre-Pandemic. Linear interpolation gives exact percentiles.
2. **Fallback: Manual cutoff tables** — 5-bucket approximation for metrics without NHANES data (VO2 max, HRV, sleep regularity, daily steps, Lp(a)).

## Standing Tiers

| Percentile | Standing | Description |
|-----------|----------|-------------|
| ≥85th | Optimal | Top tier, maintain current behaviors |
| 65-84th | Good | Solid, minor optimizations possible |
| 35-64th | Average | Population norm, room for improvement |
| 15-34th | Below Average | Needs attention, actionable changes recommended |
| <15th | Concerning | Flag for discussion with healthcare provider |

## Metric Catalog

### Tier 1: Foundation (60 pts)
| # | Metric | Weight | Source |
|---|--------|--------|--------|
| 1 | Blood Pressure | 8 | Omron cuff / clinic |
| 2 | Lipid Panel + ApoB | 8 | Blood draw |
| 3 | Metabolic Panel | 8 | Blood draw |
| 4 | Family History | 6 | Self-report |
| 5 | Sleep Regularity | 5 | Wearable |
| 6 | Daily Steps | 4 | Phone / wearable |
| 7 | Resting Heart Rate | 4 | Wearable |
| 8 | Waist Circumference | 5 | Tape measure |
| 9 | Medication List | 4 | Self-report |
| 10 | Lp(a) | 8 | Blood draw (once) |

### Tier 2: Enhanced (25 pts)
| # | Metric | Weight | Source |
|---|--------|--------|--------|
| 11 | VO2 Max | 5 | Wearable estimate |
| 12 | HRV (7-day avg) | 2 | Wearable |
| 13 | hs-CRP | 3 | Blood draw |
| 14 | Liver Enzymes | 2 | Blood draw |
| 15 | CBC | 2 | Blood draw |
| 16 | Thyroid (TSH) | 2 | Blood draw |
| 17 | Vitamin D + Ferritin | 3 | Blood draw |
| 18 | Weight Trends | 2 | Scale |
| 19 | PHQ-9 | 2 | Questionnaire |
| 20 | Zone 2 Cardio | 2 | Wearable |

## Gap Analysis

Metrics without data are ranked by coverage weight and presented as "next moves" — showing the highest-leverage gaps to close first, with estimated cost to acquire the data.
