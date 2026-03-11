# How Scoring Works

> For the full reasoning behind every scoring decision, see [METHODOLOGY.md](METHODOLOGY.md).

## Overview

The health engine scores a user profile across 20 health metrics in 2 tiers:

- **Tier 1: Foundation** (10 metrics, ~70% of total weight) — the essentials everyone should track
- **Tier 2: Enhanced** (10 metrics, ~30% of total weight) — deeper health intelligence

## Three Layers of Scoring

### 1. Clinical Zones (Primary Signal)
"Am I healthy?" — each metric assessed against evidence-based clinical thresholds (AHA, ADA, ESC, etc.). Zones: Optimal / Healthy / Borderline / Elevated.

### 2. Population Percentiles (Context)
"Where do I rank?" — NHANES 2017-2020 percentiles show where you stand vs age/sex peers. The 50th percentile = the median American (who is metabolically suboptimal). Being at the 60th percentile doesn't mean you're healthy — it means you're better than average in a sick population.

### 3. Coverage Score (Completeness)
"What percentage of high-ROI health data do you have?" — weighted by evidence strength x actionability, adjusted for **freshness** (data age) and **reliability** (measurement quality).

```
effective_weight = base_weight x freshness_fraction x reliability
```

A 7-day BP protocol from last week = full credit. A single BP reading from 4 months ago = partial credit. A lipid panel from 20 months ago = near zero credit. This is honest: old data really is less informative.

### Assessment Score
"For the data you have, where do you stand vs peers?"

Weighted average percentile using **standing weights** — which differ from coverage weights for Lp(a) (genetically fixed, can't act on it, reduced standing impact).

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
| # | Metric | Coverage Wt | Standing Wt | Source |
|---|--------|-------------|-------------|--------|
| 1 | Blood Pressure | 8 | 8 | Omron cuff / clinic |
| 2 | Lipid Panel + ApoB | 8 | 8 | Blood draw |
| 3 | Metabolic Panel | 8 | 8 | Blood draw |
| 4 | Family History | 6 | 6 | Self-report |
| 5 | Sleep Regularity | 6 | 6 | Wearable |
| 6 | Daily Steps | 4 | 4 | Phone / wearable |
| 7 | Resting Heart Rate | 4 | 4 | Wearable |
| 8 | Waist Circumference | 5 | 5 | Tape measure |
| 9 | Medication List | 3 | 3 | Self-report |
| 10 | Lp(a) | 8 | **4** | Blood draw (once) |

### Tier 2: Enhanced (26 pts)
| # | Metric | Weight | Source |
|---|--------|--------|--------|
| 11 | VO2 Max | 6 | Wearable estimate |
| 12 | HRV (7-day avg) | 2 | Wearable |
| 13 | hs-CRP | 3 | Blood draw |
| 14 | Liver Enzymes | 2 | Blood draw |
| 15 | CBC | 2 | Blood draw |
| 16 | Thyroid (TSH) | 2 | Blood draw |
| 17 | Vitamin D + Ferritin | 3 | Blood draw |
| 18 | Weight Trends | 2 | Scale |
| 19 | PHQ-9 | 2 | Questionnaire |
| 20 | Zone 2 Cardio | 2 | Wearable |

**Key weight changes:**
- VO2 Max 5→6: Strongest modifiable mortality predictor (Mandsager, JAMA 2018)
- Sleep 5→6: Regularity > duration for mortality (Phillips et al.)
- Medications 4→3: Context, not measurement
- Lp(a) standing 8→4: Genetically fixed — important to check, but shouldn't permanently penalize

## Gap Analysis

Metrics without data are ranked by coverage weight and presented as "next moves" — showing the highest-leverage gaps to close first, with estimated cost to acquire the data.
