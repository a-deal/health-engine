#!/bin/bash
# Refresh briefing.json and garmin_daily.json for all user dashboards.
# Runs via crontab 4x daily (6am, 9am, noon, 6pm).

set -euo pipefail

cd ~/src/health-engine
PYTHON=.venv/bin/python3
DATA_DIR=./data
LOG_FILE="$DATA_DIR/refresh.log"

echo "[$(date)] Starting dashboard refresh" >> "$LOG_FILE"

# 1. Pull fresh Garmin daily series for Andrew (only user with Garmin)
$PYTHON cli.py pull garmin --history --history-days 90 >> "$LOG_FILE" 2>&1 || echo "[$(date)] Garmin pull failed" >> "$LOG_FILE"

# 2. Regenerate briefing.json for Andrew (default)
$PYTHON cli.py briefing > "$DATA_DIR/briefing.json.tmp" 2>> "$LOG_FILE" && mv "$DATA_DIR/briefing.json.tmp" "$DATA_DIR/briefing.json" || echo "[$(date)] Andrew briefing failed" >> "$LOG_FILE"

# 3. Regenerate briefing.json for each user with a config
for user_dir in $DATA_DIR/users/*/; do
  user_id=$(basename "$user_dir")
  config="$user_dir/config.yaml"
  if [ -f "$config" ]; then
    $PYTHON cli.py --config "$config" briefing > "$user_dir/briefing.json.tmp" 2>> "$LOG_FILE" && mv "$user_dir/briefing.json.tmp" "$user_dir/briefing.json" || echo "[$(date)] $user_id briefing failed" >> "$LOG_FILE"
  fi
done

# 4. Regenerate admin status
python3 scripts/admin_status.py >> "$LOG_FILE" 2>&1 || echo "[$(date)] Admin status failed" >> "$LOG_FILE"

echo "[$(date)] Dashboard refresh complete" >> "$LOG_FILE"

# Keep log from growing forever
tail -200 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
