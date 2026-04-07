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
            # Bucket to threshold for dedup stability (120h and 124h both report as ">72h")
            WARNINGS+=("User '$user_id': data stale (>${STALE_HOURS}h)")
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

# ── Dedup: compare against last run ──
STATE_FILE="$PROJECT_DIR/data/admin/last_health_check.json"

# Build current findings as sorted text (one per line)
CURRENT_FINDINGS=""
for issue in "${ISSUES[@]}"; do CURRENT_FINDINGS+="ISSUE:$issue"$'\n'; done
for warning in "${WARNINGS[@]}"; do CURRENT_FINDINGS+="WARN:$warning"$'\n'; done
CURRENT_FINDINGS=$(echo "$CURRENT_FINDINGS" | sort)

PREVIOUS_FINDINGS=""
PREVIOUS_TS="never"
if [[ -f "$STATE_FILE" ]]; then
    PREVIOUS_FINDINGS=$(python3 -c "import json,sys; d=json.load(open('$STATE_FILE')); print('\n'.join(sorted(d.get('findings',[]))))" 2>/dev/null || true)
    PREVIOUS_TS=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('timestamp','?'))" 2>/dev/null || true)
fi

# Find new items not in previous run
NEW_ISSUES=()
NEW_WARNINGS=()
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if ! echo "$PREVIOUS_FINDINGS" | grep -qF "$line"; then
        case "$line" in
            ISSUE:*) NEW_ISSUES+=("${line#ISSUE:}") ;;
            WARN:*)  NEW_WARNINGS+=("${line#WARN:}") ;;
        esac
    fi
done <<< "$CURRENT_FINDINGS"

# Save current state for next run
mkdir -p "$(dirname "$STATE_FILE")"
echo "$CURRENT_FINDINGS" | python3 -c "
import json, sys
findings = [l for l in sys.stdin.read().strip().split('\n') if l]
json.dump({'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)', 'findings': sorted(findings)}, open(sys.argv[1], 'w'), indent=2)
" "$STATE_FILE"

# ── Report ──
echo ""
echo "================================"

if [[ ${#ISSUES[@]} -eq 0 && ${#WARNINGS[@]} -eq 0 ]]; then
    echo "ALL CLEAR. No issues detected."
    exit 0
fi

# If nothing new since last run, emit one-liner instead of full report
if [[ ${#NEW_ISSUES[@]} -eq 0 && ${#NEW_WARNINGS[@]} -eq 0 && "$PREVIOUS_FINDINGS" != "" ]]; then
    echo "No new issues since last check ($PREVIOUS_TS). ${#ISSUES[@]} issue(s), ${#WARNINGS[@]} warning(s) unchanged."
    echo "================================"
    # Still exit 1 if critical issues persist
    if [[ ${#ISSUES[@]} -gt 0 ]]; then exit 1; fi
    exit 0
fi

if [[ ${#NEW_ISSUES[@]} -gt 0 ]]; then
    echo "NEW CRITICAL ISSUES (${#NEW_ISSUES[@]}):"
    for issue in "${NEW_ISSUES[@]}"; do
        echo "  [!] $issue"
    done
fi

if [[ ${#NEW_WARNINGS[@]} -gt 0 ]]; then
    echo ""
    echo "NEW WARNINGS (${#NEW_WARNINGS[@]}):"
    for warning in "${NEW_WARNINGS[@]}"; do
        echo "  [~] $warning"
    done
fi

# Show persistent count for context
PERSISTENT_ISSUES=$(( ${#ISSUES[@]} - ${#NEW_ISSUES[@]} ))
PERSISTENT_WARNINGS=$(( ${#WARNINGS[@]} - ${#NEW_WARNINGS[@]} ))
if [[ $PERSISTENT_ISSUES -gt 0 || $PERSISTENT_WARNINGS -gt 0 ]]; then
    echo ""
    echo "UNCHANGED: $PERSISTENT_ISSUES issue(s), $PERSISTENT_WARNINGS warning(s) from previous check."
fi

echo "================================"

# Exit with error if critical issues found
if [[ ${#ISSUES[@]} -gt 0 ]]; then
    exit 1
fi
exit 0
