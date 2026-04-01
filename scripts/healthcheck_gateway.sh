#!/bin/bash
# Gateway health check — validates that port 18800 serves the FULL gateway.
# Runs hourly via launchd. Alerts Andrew via Telegram on failure.

FAILURES=""

# Check 1: health endpoint
HEALTH=$(curl -sf http://localhost:18800/health 2>/dev/null)
if [ $? -ne 0 ]; then
    FAILURES="$FAILURES\n- Port 18800 not responding"
fi

# Check 2: /auth/garmin returns non-404
AUTH_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:18800/auth/garmin?user=probe&state=probe:garmin:0:0" 2>/dev/null)
if [ "$AUTH_STATUS" = "404" ] || [ "$AUTH_STATUS" = "000" ]; then
    FAILURES="$FAILURES\n- /auth/garmin returning $AUTH_STATUS (full gateway not running)"
fi

# Check 3: service name should NOT be kiso-v1
SERVICE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get(service,unknown))" 2>/dev/null)
if [ "$SERVICE" = "kiso-v1" ]; then
    FAILURES="$FAILURES\n- Port 18800 running v1-only API instead of full gateway"
fi

# Check 4: Cloudflare tunnel alive
CF_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "https://auth.mybaseline.health/health" 2>/dev/null)
if [ "$CF_STATUS" = "000" ] || [ "$CF_STATUS" = "502" ] || [ "$CF_STATUS" = "503" ]; then
    FAILURES="$FAILURES\n- Cloudflare tunnel down (HTTP $CF_STATUS)"
fi

if [ -n "$FAILURES" ]; then
    MSG="GATEWAY ALERT $(date +%H:%M):$(echo -e "$FAILURES")"
    echo "$MSG"
    # Alert via Telegram
    export PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH"
    openclaw agent --to 6460316634 --channel telegram --message "$MSG" 2>/dev/null
    exit 1
else
    echo "ok $(date)"
    exit 0
fi
