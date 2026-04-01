#!/usr/bin/env bash
# Approve a pairing code on any channel and kick off Milo's onboarding flow.
# Usage: ./approve_and_welcome.sh <channel> <pairing_code>
# Example: ./approve_and_welcome.sh telegram ABC123
#          ./approve_and_welcome.sh whatsapp DEF456

set -euo pipefail
export PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH"

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <channel> <pairing_code>"
  echo "  channel: telegram, whatsapp, etc."
  exit 1
fi

CHANNEL="$1"
PAIRING_CODE="$2"

echo "Approving ${CHANNEL} pairing code: ${PAIRING_CODE} ..."
APPROVAL_OUTPUT=$(openclaw pairing approve "$CHANNEL" "$PAIRING_CODE" 2>&1)
APPROVAL_EXIT=$?

if [[ $APPROVAL_EXIT -ne 0 ]]; then
  echo "ERROR: Pairing approval failed (exit $APPROVAL_EXIT):"
  echo "$APPROVAL_OUTPUT"
  exit 1
fi

echo "$APPROVAL_OUTPUT"

# Extract the user ID from the approval output.
USER_ID=$(echo "$APPROVAL_OUTPUT" | grep -oiE '(user[_ ]?id[:\s]*|approved[:\s]*)\s*([0-9]+)' | grep -oE '[0-9]+' | head -1)

if [[ -z "$USER_ID" ]]; then
  # Fallback: grab the first long numeric string
  USER_ID=$(echo "$APPROVAL_OUTPUT" | grep -oE '[0-9]{5,}' | head -1)
fi

if [[ -z "$USER_ID" ]]; then
  echo "ERROR: Could not extract user ID from approval output."
  echo "You may need to send the onboarding message manually:"
  echo "  openclaw agent --to <user_id> --channel ${CHANNEL} --message '...'"
  exit 1
fi

echo "Extracted ${CHANNEL} user ID: ${USER_ID}"
echo "Waiting 2 seconds for session to initialize..."
sleep 2

echo "Sending onboarding prompt to Milo..."
openclaw agent \
  --to "$USER_ID" \
  --channel "$CHANNEL" \
  --message "New user just paired on ${CHANNEL}. Start the onboarding flow per AGENTS.md Message 1."

echo "Done. Milo onboarding initiated for ${CHANNEL} user ${USER_ID}."
