#!/usr/bin/env bash
#
# install-git-hooks.sh: copy tracked git hooks into .git/hooks/
#
# Run this once after cloning dotfiles, or after any change to
# scripts/git-hooks/. Idempotent: safe to re-run.
#
# Tracked hooks live in scripts/git-hooks/ (committed to the repo).
# .git/hooks/ is per-clone and not tracked, so we need to copy on install.
#
# Usage:
#   bash scripts/install-git-hooks.sh

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$REPO_ROOT" ]; then
    echo "install-git-hooks: not inside a git repository" >&2
    exit 1
fi

SRC_DIR="$REPO_ROOT/scripts/git-hooks"
DST_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$SRC_DIR" ]; then
    echo "install-git-hooks: source dir $SRC_DIR not found" >&2
    exit 1
fi

installed=0
for hook in "$SRC_DIR"/*; do
    [ -f "$hook" ] || continue
    name=$(basename "$hook")
    cp "$hook" "$DST_DIR/$name"
    chmod +x "$DST_DIR/$name"
    echo "installed: $name"
    installed=$((installed + 1))
done

if [ "$installed" -eq 0 ]; then
    echo "install-git-hooks: no hooks found in $SRC_DIR" >&2
    exit 1
fi

echo "done. $installed hook(s) installed in $DST_DIR"
