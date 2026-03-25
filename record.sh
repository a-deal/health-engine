#!/bin/bash
# Video recording script — run once, narrate over it
# Usage: ./record.sh

cd "$(dirname "$0")"

clear

# Pause for your opening narration over a clean screen
sleep 12

# Check-in appears
python3 cli.py checkin

# Pause while you walk through the output
sleep 35

# Regenerate briefing so dashboard has fresh data
python3 cli.py briefing > data/briefing.json 2>/dev/null

# Dashboard opens
open http://localhost:8789/dashboard/light.html
