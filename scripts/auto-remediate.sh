#!/usr/bin/env bash
set -euo pipefail

# Auto-remediate known failure modes.
# Called by system-health-check when issues detected, or manually.
#
# Usage:
#   bash scripts/auto-remediate.sh [--dry-run]
#
# Remediations:
#   1. Re-trigger errored OpenClaw crons
#   2. Verify API is responding, restart if not
#   3. Check for zombie Python processes on API port

PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

DRY_RUN="${1:-}"
FIXED=0
FAILED=0

log() { echo "[$(date +%H:%M:%S)] $1"; }

# Time-sensitive cron guard: don't re-trigger scheduled crons outside their window.
# Evening crons: only 19:00-21:00. Morning crons: only 06:00-09:00.
# NOTE: uses Mac Mini local time, not per-user timezone. The Python scheduler
# handles per-user tz checks; this is a second gate to prevent 3 AM re-triggers.
_cron_in_window() {
    local cron_name="$1"
    local hour
    hour=$(date +%H | sed 's/^0//')
    case "$cron_name" in
        *evening*|*night*|*wind-down*)
            [[ $hour -ge 19 && $hour -lt 21 ]] && return 0
            log "  SKIP: $cron_name outside evening window (current hour: $hour, need 19-21)"
            return 1 ;;
        *morning*|*brief*)
            [[ $hour -ge 6 && $hour -lt 9 ]] && return 0
            log "  SKIP: $cron_name outside morning window (current hour: $hour, need 06-09)"
            return 1 ;;
        *)
            return 0 ;;  # Non-time-sensitive crons: always re-trigger
    esac
}

# ── 1. Re-trigger errored crons ──
log "Checking for errored crons..."
ERRORED_CRONS=$(openclaw cron list 2>&1 | grep "error" | awk '{print $1, $2}' || true)
SKIPPED=0

if [[ -n "$ERRORED_CRONS" ]]; then
    while IFS=' ' read -r cron_id cron_name; do
        if ! _cron_in_window "$cron_name"; then
            SKIPPED=$((SKIPPED + 1))
            continue
        fi
        if [[ "$DRY_RUN" == "--dry-run" ]]; then
            log "  [DRY RUN] Would re-trigger: $cron_name ($cron_id)"
        else
            log "  Re-triggering: $cron_name ($cron_id)"
            openclaw cron run "$cron_id" 2>/dev/null && FIXED=$((FIXED + 1)) || FAILED=$((FAILED + 1))
        fi
    done <<< "$ERRORED_CRONS"
else
    log "  No errored crons."
fi

# ── 2. Verify API health ──
log "Checking API health..."
API_OK=$(curl -sf http://localhost:18800/health 2>/dev/null && echo "yes" || echo "no")

if [[ "$API_OK" == "no" ]]; then
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log "  [DRY RUN] Would restart API"
    else
        log "  API not responding. Restarting..."
        bash "$PROJECT_DIR/scripts/restart-api.sh" 2>&1 | while IFS= read -r line; do
            log "    $line"
        done
        # Verify after restart
        sleep 3
        if curl -sf http://localhost:18800/health >/dev/null 2>&1; then
            log "  API recovered."
            FIXED=$((FIXED + 1))
        else
            log "  API still down after restart."
            FAILED=$((FAILED + 1))
        fi
    fi
else
    log "  API: OK"
fi

# ── 3. Check for zombie processes ──
log "Checking for zombie processes..."
PORT=18800
PIDS=$(lsof -ti :$PORT 2>/dev/null | sort -u)
PID_COUNT=$(echo "$PIDS" | grep -c '[0-9]' || true)

if [[ "$PID_COUNT" -gt 1 ]]; then
    log "  WARNING: $PID_COUNT processes on port $PORT"
    if [[ "$DRY_RUN" == "--dry-run" ]]; then
        log "  [DRY RUN] Would kill extras and restart"
    else
        log "  Killing all and restarting clean..."
        bash "$PROJECT_DIR/scripts/restart-api.sh" 2>&1 | while IFS= read -r line; do
            log "    $line"
        done
        FIXED=$((FIXED + 1))
    fi
else
    log "  No zombies."
fi

# ── Summary ──
log ""
log "Remediation complete. Fixed: $FIXED, Failed: $FAILED, Skipped (outside window): $SKIPPED"

if [[ $FAILED -gt 0 ]]; then
    exit 1
fi
exit 0
