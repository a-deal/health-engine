#!/usr/bin/env bash
set -euo pipefail

# System health check for Kiso + OpenClaw + user data pipelines.
# Catches issues before users report them.
#
# Usage (on Mac Mini):
#   bash scripts/system-health-check.sh
#
# Usage (from laptop):
#   ssh mac-mini 'cd ~/src/health-engine && bash scripts/system-health-check.sh'
#
# Designed to run as an OpenClaw cron every 4 hours.

PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

ISSUES=()
WARNINGS=()

echo "=== Kiso System Health Check ==="
echo "$(date)"
echo ""

# ── 1. API Health ──
echo "Checking API..."
API_RESP=$(curl -sf http://localhost:18800/health 2>/dev/null || echo "FAIL")
if [[ "$API_RESP" == "FAIL" ]]; then
    ISSUES+=("API: Not responding on port 18800")
else
    echo "  API: OK"
fi

# ── 2. OpenClaw Gateway ──
echo "Checking OpenClaw gateway..."
GW_STATUS=$(openclaw gateway status 2>&1 | grep -c "running" || true)
if [[ "$GW_STATUS" -eq 0 ]]; then
    ISSUES+=("Gateway: Not running")
else
    echo "  Gateway: OK"
fi

# ── 3. Agent Routing ──
echo "Checking agent routing..."
BINDINGS=$(openclaw agents bindings 2>&1)

# Verify K only matches Andrew's Telegram
if echo "$BINDINGS" | grep -q "k <- telegram peer=dm:80135247"; then
    echo "  K routing: OK (Andrew only)"
else
    ISSUES+=("K routing: Missing or incorrect binding for Andrew Telegram")
fi

# Verify main catches all other Telegram
if echo "$BINDINGS" | grep -q "main <- telegram"; then
    echo "  Milo fallback: OK"
else
    ISSUES+=("Milo routing: Missing Telegram fallback binding")
fi

# ── 4. Session Routing Verification ──
echo "Checking session routing..."
SESSION_ISSUES=$(openclaw sessions --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
issues = []
for s in d.get('sessions', []):
    key = s.get('key', '')
    agent = key.split(':')[1] if ':' in key else '?'
    # Grigoriy must be on main
    if '6460316634' in key and agent != 'main':
        issues.append(f'Grigoriy on {agent} instead of main: {key}')
    # Andrew Telegram should be on k
    if '80135247' in key and 'telegram' in key and agent != 'k':
        issues.append(f'Andrew Telegram on {agent} instead of k: {key}')
for i in issues:
    print(i)
" 2>&1)

if [[ -n "$SESSION_ISSUES" ]]; then
    while IFS= read -r line; do
        ISSUES+=("Session: $line")
    done <<< "$SESSION_ISSUES"
else
    echo "  Sessions: OK"
fi

# ── 5. Cron Health ──
echo "Checking cron jobs..."
CRON_ERRORS=$(openclaw cron list 2>&1 | grep "error" || true)
if [[ -n "$CRON_ERRORS" ]]; then
    while IFS= read -r line; do
        CRON_NAME=$(echo "$line" | awk '{print $2}')
        WARNINGS+=("Cron '$CRON_NAME' in error state")
    done <<< "$CRON_ERRORS"
else
    echo "  Crons: All OK"
fi

# ── 6. Per-User Data Freshness ──
echo "Checking user data freshness..."
USERS_DIR="$PROJECT_DIR/data/users"
STALE_HOURS=72  # Alert if no data in 72 hours

for user_dir in "$USERS_DIR"/*/; do
    user_id=$(basename "$user_dir")
    # Skip test users
    [[ "$user_id" == test_* || "$user_id" == default || "$user_id" == "--params" ]] && continue

    # Check for any recent data file modification
    LATEST_MOD=$(find "$user_dir" -name "*.json" -o -name "*.csv" | xargs stat -f "%m" 2>/dev/null | sort -rn | head -1)
    if [[ -n "$LATEST_MOD" ]]; then
        NOW=$(date +%s)
        AGE_HOURS=$(( (NOW - LATEST_MOD) / 3600 ))
        if [[ $AGE_HOURS -gt $STALE_HOURS ]]; then
            WARNINGS+=("User '$user_id': No data update in ${AGE_HOURS}h (>${STALE_HOURS}h)")
        else
            echo "  $user_id: Data fresh (${AGE_HOURS}h ago)"
        fi
    else
        WARNINGS+=("User '$user_id': No data files found")
    fi
done

# ── 7. Garmin Token Health ──
echo "Checking Garmin tokens..."
if [[ -d "$HOME/.config/health-engine/garmin-tokens" ]]; then
    TOKEN_AGE=$(stat -f "%m" "$HOME/.config/health-engine/garmin-tokens/oauth2_token.json" 2>/dev/null || echo "0")
    if [[ "$TOKEN_AGE" != "0" ]]; then
        NOW=$(date +%s)
        TOKEN_HOURS=$(( (NOW - TOKEN_AGE) / 3600 ))
        if [[ $TOKEN_HOURS -gt 168 ]]; then  # 7 days
            WARNINGS+=("Garmin tokens: ${TOKEN_HOURS}h old, may need refresh")
        else
            echo "  Garmin tokens: OK (${TOKEN_HOURS}h old)"
        fi
    fi
else
    WARNINGS+=("Garmin tokens: Directory not found")
fi

# ── 8. Cloudflare Tunnel ──
echo "Checking Cloudflare tunnel..."
TUNNEL_RESP=$(curl -sf https://auth.mybaseline.health/health 2>/dev/null || echo "FAIL")
if [[ "$TUNNEL_RESP" == "FAIL" ]]; then
    ISSUES+=("Cloudflare tunnel: auth.mybaseline.health not responding")
else
    echo "  Tunnel: OK"
fi

# ── 9. Disk Space ──
echo "Checking disk space..."
DISK_USED=$(df -h /Users/andrew 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
if [[ -n "$DISK_USED" && "$DISK_USED" -gt 90 ]]; then
    ISSUES+=("Disk: ${DISK_USED}% used")
else
    echo "  Disk: ${DISK_USED:-?}% used"
fi

# ── 10. MCP Server ──
echo "Checking MCP server..."
MCP_PID=$(pgrep -f "mcp_server.server" 2>/dev/null | head -1)
if [[ -n "$MCP_PID" ]]; then
    echo "  MCP server: Running (PID $MCP_PID)"
else
    WARNINGS+=("MCP server: Not running (OpenClaw may restart it on demand)")
fi

# ── Report ──
echo ""
echo "================================"

if [[ ${#ISSUES[@]} -eq 0 && ${#WARNINGS[@]} -eq 0 ]]; then
    echo "ALL CLEAR. No issues detected."
    exit 0
fi

if [[ ${#ISSUES[@]} -gt 0 ]]; then
    echo "CRITICAL ISSUES (${#ISSUES[@]}):"
    for issue in "${ISSUES[@]}"; do
        echo "  [!] $issue"
    done
fi

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo ""
    echo "WARNINGS (${#WARNINGS[@]}):"
    for warning in "${WARNINGS[@]}"; do
        echo "  [~] $warning"
    done
fi

echo "================================"

# Exit with error if critical issues found
if [[ ${#ISSUES[@]} -gt 0 ]]; then
    exit 1
fi
exit 0
