#!/usr/bin/env bash
# One-shot: purge ghost user directories under data/users/.
#
# Context: mcp_server/tools.py:_user_dir was eagerly mkdir'ing directories
# for any slug passed to it. Commit `ed84010` closed the leak. This script
# clears the existing debt from prod (Mac Mini) so the invariant
# "every data/users/<slug>/ corresponds to a real person record" holds.
#
# Slugs to purge (confirmed on Mac Mini 2026-04-13):
#   patrick, tommy            — never onboarded, no person row
#   test_cleanup, test_onboard, test_upload, test_user  — test scratch
#   default                   — sentinel-like, no real user
#   --params                  — CLI parsing accident
#   230b25d3-4352-551d-b3e1-c8484d454db8  — paul's UUID as a literal
#                                            dirname (dup of paul/)
#
# Slugs to KEEP: andrew, paul, dad, dean, grigoriy, manny, mike, yusuf.
# These have person rows. Not in scope for this session.
#
# HARD RULE #9: DRY_RUN=1 is the DEFAULT. The script must refuse to
# delete anything unless DRY_RUN=0 is passed explicitly. Running the
# test suite must never touch the filesystem outside the backup dir.
#
# Usage:
#   DRY_RUN=1 ./scripts/one-shot/20260413-purge-user-cruft.sh    # preview
#   DRY_RUN=0 ./scripts/one-shot/20260413-purge-user-cruft.sh    # execute
#
# The script creates a tarball backup before any rm. Reversible via:
#   tar xzf ~/backups/data-users-cruft-YYYYMMDD-HHMMSS.tar.gz -C /

set -euo pipefail

: "${DRY_RUN:=1}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
USERS_DIR="$REPO_ROOT/data/users"
BACKUP_DIR="$HOME/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_TAR="$BACKUP_DIR/data-users-cruft-${TIMESTAMP}.tar.gz"

CRUFT_SLUGS=(
    patrick
    tommy
    test_cleanup
    test_onboard
    test_upload
    test_user
    default
    --params
    230b25d3-4352-551d-b3e1-c8484d454db8
)

echo "=== purge-user-cruft.sh ==="
echo "repo root:  $REPO_ROOT"
echo "users dir:  $USERS_DIR"
echo "backup tar: $BACKUP_TAR"
echo "DRY_RUN:    $DRY_RUN"
echo

if [ ! -d "$USERS_DIR" ]; then
    echo "no data/users/ directory — nothing to do"
    exit 0
fi

echo "candidates (existing dirs only):"
EXISTING=()
for slug in "${CRUFT_SLUGS[@]}"; do
    target="$USERS_DIR/$slug"
    if [ -e "$target" ]; then
        size="$(du -sh "$target" 2>/dev/null | cut -f1)"
        echo "  [FOUND]   $slug  ($size)"
        EXISTING+=("$slug")
    else
        echo "  [absent]  $slug"
    fi
done
echo

if [ "${#EXISTING[@]}" -eq 0 ]; then
    echo "no cruft directories found — nothing to purge"
    exit 0
fi

if [ "$DRY_RUN" = "1" ]; then
    echo "DRY_RUN=1 — not creating backup, not deleting anything"
    echo "re-run with DRY_RUN=0 to execute"
    exit 0
fi

# Real run from here on.
mkdir -p "$BACKUP_DIR"
echo "creating backup tarball..."
tar czf "$BACKUP_TAR" -C "$USERS_DIR" "${EXISTING[@]}"
echo "backup created: $BACKUP_TAR ($(du -h "$BACKUP_TAR" | cut -f1))"
echo

echo "deleting ${#EXISTING[@]} directories..."
for slug in "${EXISTING[@]}"; do
    target="$USERS_DIR/$slug"
    rm -rf "$target"
    echo "  removed $slug"
done
echo
echo "done. verify with: ls $USERS_DIR"
echo "restore with: tar xzf $BACKUP_TAR -C $USERS_DIR"
