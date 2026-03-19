# Health Engine

Your health data is everywhere — except where it's useful.

Steps on your watch. Labs in a portal. Weight on a scale. Blood pressure in a drawer. None of it talks to each other. None of it tells you what it means together, or what to do next.

Health Engine connects all of it, scores it the way elite performance programs do, and coaches you forward.

## The same 20 metrics. A fraction of the cost.

F1 racing teams, NASA astronauts, and military special operations all monitor the same core health dimensions. Their programs cost $50K to over $1M per year. Health Engine scores you on the same framework for free.

| Program | Metrics Covered | Annual Cost |
|---------|:-:|---|
| NASA Astronaut Health | 20/20 | Millions (taxpayer-funded) |
| Special Operations (SOCOM) | 20/20 | $50-100K+ per operator |
| Peter Attia's Practice | 20/20 | $100K+ (concierge) |
| F1 Driver Programs | 18/20 | $500K+ (team-funded) |
| Function Health | 11/20 | $499-999/year |
| **Health Engine** | **20/20** | **Free** |

The difference isn't what they measure. It's that they have a system that connects everything, tracks it over time, and tells them what to do. That's what Health Engine does.

## What it actually measures

20 dimensions of health, organized by how much they matter:

| What we measure | What it tells you | How you get it |
|---|---|---|
| **Blood pressure** | Heart and artery health | $40 home cuff |
| **Cholesterol particle count** (ApoB) | How many particles can build plaque — more accurate than standard cholesterol | $30-50 lab add-on |
| **Blood sugar and insulin** | Whether your body handles energy well, years before diabetes shows up | $40-60 lab panel |
| **Sleep consistency** | Whether you go to bed and wake up at the same time — predicts health outcomes better than sleep duration alone | Free with any wearable |
| **Inherited cardiac risk** (Lp(a)) | A genetic marker you test once in your life. 1 in 5 people carry elevated levels and most doctors never order it | $30, one time |
| **Resting heart rate** | Cardiovascular fitness at rest | Free with wearable |
| **Daily movement** | Steps per day — a simple proxy for all-cause mortality risk | Free with phone |
| **Cardio fitness** (VO2 max) | How efficiently your body uses oxygen — the single strongest predictor of longevity | Free estimate from wearable |
| **Recovery** (HRV) | How well your nervous system is bouncing back day to day | Free with wearable |
| **Inflammation** (hs-CRP) | Low-grade systemic inflammation — linked to heart disease, cancer, metabolic dysfunction | $20 lab add-on |
| **Liver health** | Early warning for fatty liver, alcohol impact, or medication stress | Usually included in standard panels |
| **Blood cell health** (CBC) | Anemia, immune function, overall system health | Usually included in standard panels |
| **Thyroid function** (TSH) | Metabolism, energy, weight regulation | $20/year |
| **Iron and vitamin D** | Energy, bone health, immune function — two of the most common deficiencies | $40-60 lab add-on |
| **Waist measurement** | Visceral fat — the dangerous kind that wraps around your organs | $3 tape measure |
| **Aerobic base** (Zone 2) | Low-intensity cardio minutes per week — builds the metabolic engine | Free with HR wearable |
| **Weight trends** | Direction matters more than any single number | $20-50 smart scale |
| **Family history** | Heart disease before 60 in your parents changes your risk profile | Free, 10-minute conversation |
| **Medications** | What you're taking affects how every other metric should be read | Free, 5-minute list |
| **Mental health screen** (PHQ-9) | A validated 9-question depression check — often skipped, always relevant | Free, 3 minutes |

Going from 0% to full coverage costs under $300 and a couple hours of your time.

## How it works

You talk to Claude. It knows your health data.

- **"How am I doing?"** — Coaching read: what's improving, what needs attention, one thing to focus on today
- **"I weighed 192 this morning"** — Logged. Trend updated. No forms.
- **"What should I measure next?"** — Ranked by impact and cost. The highest-leverage gap first.
- **"Show me the dashboard"** — Visual snapshot of your full health picture

Every conversation picks up where the last one left off. Your data stays on your machine — nothing is uploaded, nothing is shared, nothing leaves your laptop.

## How scoring works

Your numbers are evaluated five ways:

**Are you healthy?** Each metric is compared against clinical guidelines from the American Heart Association, the American Diabetes Association, and the European Society of Cardiology — the same thresholds your cardiologist uses.

**Where do you rank?** Population percentiles from a CDC dataset of 300,000+ Americans. The 50th percentile is the median American — 42% of whom are obese and 38% prediabetic. "Better than average" is a low bar. We show you where you actually stand.

**Is your data current?** A blood panel from 18 months ago gets partial credit. Old data shouldn't anchor your current picture.

**Is your data reliable?** A single blood pressure reading is noisier than 7 days of readings. The engine accounts for that.

**What patterns emerge?** Individual numbers tell part of the story. When your triglycerides are high, HDL is low, and insulin is creeping up — that's a pattern called insulin resistance, and it matters more than any one metric alone. The engine detects metabolic syndrome, atherogenic dyslipidemia, and recovery stress automatically.

Full methodology: [docs/METHODOLOGY.md](docs/METHODOLOGY.md)

## Get started (2 minutes)

### Install

```bash
uvx health-engine
```

Add to your Claude Desktop or Claude Code config:

```json
{
  "mcpServers": {
    "health-engine": {
      "command": "uvx",
      "args": ["health-engine"]
    }
  }
}
```

Then say **"set me up"** in any Claude conversation. It walks you through everything.

### Or clone and run

```bash
git clone https://github.com/a-deal/health-engine.git
cd health-engine
pip install -e .
```

```json
{
  "mcpServers": {
    "health-engine": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/health-engine", "python3", "-m", "mcp_server"]
    }
  }
}
```

## Connect your wearable

**Garmin** — pulls heart rate, HRV, sleep, steps, VO2 max, and zone 2 minutes automatically. Say "connect my Garmin" in any Claude conversation.

**Apple Health** — export from your iPhone (Health app > profile > Export All Health Data), transfer the ZIP to your computer, and say "import my Apple Health data." Handles large exports.

## Dashboard

Say **"show me the dashboard"** to open a visual snapshot in your browser:

1. **Your Score** — Coverage ring, health assessment, coaching read
2. **Your Body** — Recovery trends, body composition, movement, nutrition, habits
3. **Your Actions** — Next 3 moves ranked by impact, pattern alerts

---

## For developers

### MCP Tools

14 tools available when connected to Claude:

| Tool | What it does |
|------|-------------|
| `checkin` | Full coaching briefing — scores, insights, weight, nutrition, habits, wearable data |
| `score` | Coverage %, percentiles for 20 metrics, tier breakdown, gap analysis |
| `onboard` | 20-metric coverage map, wearable connection status, ranked next steps |
| `get_protocols` | Active protocol progress — day, week, phase, habits, nudges |
| `log_weight` | Log a weight measurement |
| `log_bp` | Log blood pressure |
| `log_habits` | Log daily habits |
| `log_meal` | Log a meal with macros |
| `import_apple_health` | Import Apple Health export (ZIP/XML) with guided instructions |
| `connect_garmin` | Check Garmin connection status |
| `auth_garmin` | Authenticate with Garmin via secure browser form |
| `pull_garmin` | Pull fresh data from Garmin Connect |
| `open_dashboard` | Open the visual health dashboard in a browser |
| `setup_profile` | Create or update user profile |
| `get_status` | Data files inventory — what exists, last modified, row counts |

Plus a methodology resource (`health-engine://methodology`) with full scoring documentation.

### CLI

```bash
python3 cli.py score              # Score profile, show gaps
python3 cli.py briefing           # Full coaching snapshot (JSON)
python3 cli.py insights           # Health insights with explanations
python3 cli.py status             # What data exists, when last updated
python3 cli.py pull garmin --history --workouts  # 90-day trends + workouts
```

### Use as a library

```python
from engine.models import Demographics, UserProfile
from engine.scoring.engine import score_profile

profile = UserProfile(
    demographics=Demographics(age=35, sex="M"),
    resting_hr=52, hrv_rmssd_avg=62, vo2_max=47,
)
output = score_profile(profile)
print(f"Coverage: {output['coverage_score']}%")
```

### Tests

```bash
python3 -m pytest tests/ -v   # 121 tests
```

### Project structure

```
engine/
├── scoring/           # 20 metrics x population percentiles x clinical zones
├── insights/          # Rule-based coaching + compound pattern detection
├── coaching/          # Briefing builder, protocol engine
├── integrations/      # Garmin Connect API, Apple Health XML parser
├── tracking/          # Weight, nutrition, strength, habits
└── data/              # Percentile tables, methodology (ships with package)

mcp_server/            # MCP server (FastMCP) — tools + methodology resource
dashboard/             # Visual health dashboard (reads briefing.json locally)
```

### Docs

- [METHODOLOGY.md](docs/METHODOLOGY.md) — Why each metric, evidence sources, clinical thresholds
- [SCORING.md](docs/SCORING.md) — How the scoring engine works
- [METRICS.md](docs/METRICS.md) — 20-metric catalog with evidence
- [COVERAGE.md](docs/COVERAGE.md) — Path to 100% coverage, cost breakdown
- [ONBOARDING.md](docs/ONBOARDING.md) — Setup walkthrough
- [DATA_FORMATS.md](docs/DATA_FORMATS.md) — CSV/JSON schemas

## License

MIT
