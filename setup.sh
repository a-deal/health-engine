#!/usr/bin/env bash
# Interactive setup for health-engine
# Creates config.yaml, installs dependencies, and verifies everything works.

set -e

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[32m'
CYAN='\033[36m'
YELLOW='\033[33m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}  health-engine setup${RESET}"
echo -e "${DIM}  ─────────────────────────────────────${RESET}"
echo ""

# ── Step 1: Python check ──
if ! command -v python3 &>/dev/null; then
  echo -e "${YELLOW}  Python 3 not found. Install it first:${RESET}"
  echo "    brew install python3  (macOS)"
  echo "    sudo apt install python3  (Linux)"
  exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  Python: ${GREEN}${PY_VERSION}${RESET}"

# ── Step 2: Install dependencies ──
echo ""
echo -e "${BOLD}  Installing dependencies...${RESET}"
python3 -m pip install -e . -q 2>&1 | tail -1

read -p "  Install Garmin integration? (y/n) [y]: " GARMIN_INSTALL
GARMIN_INSTALL=${GARMIN_INSTALL:-y}
if [[ "$GARMIN_INSTALL" =~ ^[Yy] ]]; then
  python3 -m pip install -e ".[garmin]" -q 2>&1 | tail -1
  echo -e "  Garmin: ${GREEN}installed${RESET}"
fi

# ── Step 3: Create config.yaml ──
echo ""
if [ -f config.yaml ]; then
  read -p "  config.yaml already exists. Overwrite? (y/n) [n]: " OVERWRITE
  OVERWRITE=${OVERWRITE:-n}
  if [[ ! "$OVERWRITE" =~ ^[Yy] ]]; then
    echo "  Keeping existing config.yaml"
    SKIP_CONFIG=true
  fi
fi

if [ "$SKIP_CONFIG" != "true" ]; then
  echo -e "${BOLD}  Let's set up your profile.${RESET}"
  echo ""

  read -p "  Your age: " AGE
  AGE=${AGE:-35}

  read -p "  Sex (M/F): " SEX
  SEX=${SEX:-M}

  echo ""
  echo -e "${DIM}  Targets are optional — press Enter to skip any.${RESET}"
  read -p "  Target weight (lbs): " TARGET_WEIGHT
  read -p "  Daily protein target (g): " TARGET_PROTEIN
  read -p "  Training day calories: " CAL_TRAINING
  read -p "  Rest day calories: " CAL_REST

  GARMIN_EMAIL=""
  GARMIN_PASSWORD=""
  if [[ "$GARMIN_INSTALL" =~ ^[Yy] ]]; then
    echo ""
    echo -e "${DIM}  Garmin credentials (stored in config.yaml, which is gitignored).${RESET}"
    echo -e "${DIM}  You can also set GARMIN_EMAIL/GARMIN_PASSWORD env vars instead.${RESET}"
    read -p "  Garmin email (or Enter to skip): " GARMIN_EMAIL
    if [ -n "$GARMIN_EMAIL" ]; then
      read -s -p "  Garmin password: " GARMIN_PASSWORD
      echo ""
    fi
  fi

  cat > config.yaml <<EOF
# health-engine config — $(date +%Y-%m-%d)
# This file is gitignored. Your data stays local.

profile:
  age: ${AGE}
  sex: ${SEX}

targets:
  weight_lbs: ${TARGET_WEIGHT:-""}
  protein_g: ${TARGET_PROTEIN:-""}
  calories_training: ${CAL_TRAINING:-""}
  calories_rest: ${CAL_REST:-""}

garmin:
  email: "${GARMIN_EMAIL}"
  password: "${GARMIN_PASSWORD}"
  token_dir: ~/.config/health-engine/garmin-tokens

data_dir: ./data

exercise_name_map:
  barbell deadlift: deadlift
  sumo deadlift: deadlift
  deadlift: deadlift
  barbell bench press: bench_press
  dumbbell bench press: bench_press
  bench press: bench_press
  barbell back squat: squat
  back squat: squat
  belt squat: squat
  squat: squat
  barbell squat: squat

insights:
  thresholds_file: engine/insights/rules.yaml
EOF

  echo -e "  ${GREEN}config.yaml created${RESET}"
fi

# ── Step 4: Create data directory ──
mkdir -p data
echo -e "  ${GREEN}data/ directory ready${RESET}"

# ── Step 5: Verify ──
echo ""
echo -e "${BOLD}  Verifying installation...${RESET}"

python3 -c "from engine.scoring.engine import score_profile; print('  ✓ Scoring engine')"
python3 -c "from engine.insights.engine import generate_insights; print('  ✓ Insights engine')"
python3 -c "from engine.tracking.weight import rolling_average; print('  ✓ Tracking utilities')"

if [[ "$GARMIN_INSTALL" =~ ^[Yy] ]]; then
  python3 -c "from engine.integrations.garmin import GarminClient; print('  ✓ Garmin integration')"
fi

TEST_RESULT=$(python3 -m pytest tests/ -q 2>&1 | tail -1)
echo "  ✓ Tests: $TEST_RESULT"

# ── Done ──
echo ""
echo -e "${BOLD}${GREEN}  Setup complete!${RESET}"
echo ""
echo -e "  ${CYAN}Try these next:${RESET}"
echo ""
echo "    python3 cli.py score                    # Score your profile (gaps only)"
echo "    python3 cli.py score --profile tests/fixtures/sample_profile.json  # Score sample data"
echo "    python3 cli.py status                   # Check what data you have"

if [[ "$GARMIN_INSTALL" =~ ^[Yy] ]] && [ -n "$GARMIN_EMAIL" ]; then
  echo "    python3 cli.py pull garmin              # Pull your Garmin data"
  echo "    python3 cli.py insights                 # Generate insights from Garmin data"
fi

echo ""
echo -e "  ${DIM}Using Claude Code? Just open this directory and ask Claude anything.${RESET}"
echo -e "  ${DIM}The CLAUDE.md file gives it full project context.${RESET}"
echo ""
