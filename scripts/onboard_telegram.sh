#!/usr/bin/env bash
# Approve a Telegram pairing code and kick off Milo's onboarding flow.
# Usage: ./onboard_telegram.sh <pairing_code>

set -euo pipefail
export PATH="/opt/homebrew/bin:$HOME/Library/pnpm:$PATH"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <pairing_code>"
  exit 1
fi

PAIRING_CODE="$1"

echo "Approving Telegram pairing code: ${PAIRING_CODE} ..."
APPROVAL_OUTPUT=$(openclaw pairing approve telegram "$PAIRING_CODE" 2>&1)
APPROVAL_EXIT=$?

if [[ $APPROVAL_EXIT -ne 0 ]]; then
  echo "ERROR: Pairing approval failed (exit $APPROVAL_EXIT):"
  echo "$APPROVAL_OUTPUT"
  exit 1
fi

echo "$APPROVAL_OUTPUT"

# Extract the Telegram user ID from the approval output.
TELEGRAM_USER_ID=$(echo "$APPROVAL_OUTPUT" | grep -oiE '(user[_ ]?id[:\s]*|approved[:\s]*)\s*([0-9]+)' | grep -oE '[0-9]+' | head -1)

if [[ -z "$TELEGRAM_USER_ID" ]]; then
  # Fallback: grab the first long numeric string (Telegram IDs are typically 9-10 digits)
  TELEGRAM_USER_ID=$(echo "$APPROVAL_OUTPUT" | grep -oE '[0-9]{5,}' | head -1)
fi

if [[ -z "$TELEGRAM_USER_ID" ]]; then
  echo "ERROR: Could not extract Telegram user ID from approval output."
  echo "You may need to send the onboarding message manually."
  exit 1
fi

echo "Extracted Telegram user ID: ${TELEGRAM_USER_ID}"
echo "Waiting 2 seconds for session to initialize..."
sleep 2

echo "Sending onboarding prompt to Milo..."
openclaw agent \
  --to "$TELEGRAM_USER_ID" \
  --channel telegram \
  --message "New user just paired on Telegram. Start the onboarding flow per AGENTS.md Message 1."

echo "Done. Milo onboarding initiated for Telegram user ${TELEGRAM_USER_ID}."
