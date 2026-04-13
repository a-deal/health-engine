#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# deploy-api.sh — 10-step deploy state machine for health-engine on Mac Mini
# =============================================================================
#
# Source: 2026-04-12 accidental-deploy incident + 2026-04-13 Task B rewrite.
# The old script was a flat sequence (push → pull → restart) with no pre-deploy
# backup, no post-deploy SHA assertion, and no per-step dry-run marker. This
# version is a 10-step state machine where each step is a named function. Under
# DRY_RUN each step logs a STEP:<name> marker to $DEPLOY_DRY_RUN_LOG and skips
# its side effect, so the whole flow is testable without touching prod.
#
# The 10 steps:
#   1.  local_head_check       — record local git HEAD sha (what we're deploying)
#   2.  remote_head_check      — ssh and record remote git HEAD sha (pre-pull)
#   3.  abort_if_remote_dirty  — fail fast if Mac Mini working tree is dirty
#   4.  git_push               — push origin master from the laptop
#   5.  vacuum_backup          — VACUUM INTO on Mac Mini's kasane.db before pull
#   6.  git_pull               — ssh mac-mini git pull --ff-only + uv sync
#   7.  remote_head_assert     — remote HEAD now matches local pre-push sha
#   8.  restart_api            — ssh mac-mini bash scripts/restart-api.sh --hard
#   9.  curl_health            — curl /health, require status=ok
#   10. assert_commit_matches  — /health `commit` field matches local HEAD
#
# Usage:
#   ./scripts/deploy-api.sh              # Run tests + full 10-step deploy
#   ./scripts/deploy-api.sh --skip-tests # Skip pre-deploy pytest
#   ./scripts/deploy-api.sh --reload     # Soft HUP reload instead of --hard
#   ./scripts/deploy-api.sh --cold       # Cold restart (dep changes)
#
# Dry-run contract (HARD RULE #9):
#   DRY_RUN={1,true,TRUE,yes,y,t,on,…} with surrounding whitespace is detected
#   and treated as truthy. Under DRY_RUN every step is a no-op logger. Default
#   log is /tmp/deploy-dry-run.$$.log (PID-namespaced for CI parallel safety).
# =============================================================================

# -----------------------------------------------------------------------------
# DRY_RUN detection (must run BEFORE any side effect)
# -----------------------------------------------------------------------------
_dry_run_raw="${DRY_RUN:-}"
# Strip leading/trailing whitespace.
_dry_run_stripped="${_dry_run_raw#"${_dry_run_raw%%[![:space:]]*}"}"
_dry_run_stripped="${_dry_run_stripped%"${_dry_run_stripped##*[![:space:]]}"}"
_dry_run_lc="$(printf '%s' "$_dry_run_stripped" | tr '[:upper:]' '[:lower:]')"
DRY_RUN_ACTIVE=0
case "$_dry_run_lc" in
    1|t|true|y|yes|on) DRY_RUN_ACTIVE=1 ;;
esac
unset _dry_run_raw _dry_run_stripped _dry_run_lc

DEPLOY_DRY_RUN_LOG="${DEPLOY_DRY_RUN_LOG:-/tmp/deploy-dry-run.$$.log}"
export DEPLOY_DRY_RUN_LOG

REMOTE="mac-mini"
REMOTE_DIR="~/src/health-engine"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESTART_FLAG="--hard"
RUN_TESTS=true
HEALTH_URL="${HEALTH_URL:-http://localhost:18800/health}"

# Parse flags
for arg in "$@"; do
    case $arg in
        --test-first) RUN_TESTS=true ;;
        --skip-tests) RUN_TESTS=false ;;
        --reload)     RESTART_FLAG="--reload" ;;
        --cold)       RESTART_FLAG="--cold" ;;
    esac
done

# -----------------------------------------------------------------------------
# dry-run log bootstrap
# -----------------------------------------------------------------------------
if [ "$DRY_RUN_ACTIVE" = "1" ]; then
    mkdir -p "$(dirname "$DEPLOY_DRY_RUN_LOG")"
    {
        echo "DRY_RUN invoked at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "args: $*"
        echo "cwd: $(pwd)"
        echo "target remote: $REMOTE ($REMOTE_DIR)"
        echo "STEP:dry_run_guard_fired"
    } >> "$DEPLOY_DRY_RUN_LOG"
fi

# Shared state between steps.
LOCAL_HEAD=""
REMOTE_HEAD_PRE=""
REMOTE_HEAD_POST=""

# -----------------------------------------------------------------------------
# step dispatcher: in dry-run, log a marker and return 0. In real mode, call
# the step function, which carries out its side effect.
# -----------------------------------------------------------------------------
run_step() {
    local name="$1"
    if [ "$DRY_RUN_ACTIVE" = "1" ]; then
        echo "STEP:$name" >> "$DEPLOY_DRY_RUN_LOG"
        return 0
    fi
    "step_$name"
}

# -----------------------------------------------------------------------------
# step 1: local_head_check — what sha is the laptop pointing at?
# -----------------------------------------------------------------------------
step_local_head_check() {
    cd "$LOCAL_DIR"
    LOCAL_HEAD=$(git rev-parse HEAD)
    echo "local HEAD: $LOCAL_HEAD"
}

# -----------------------------------------------------------------------------
# step 2: remote_head_check — what sha is Mac Mini's working tree at BEFORE
# we pull? Recorded so we know what we're rolling forward from.
# -----------------------------------------------------------------------------
step_remote_head_check() {
    REMOTE_HEAD_PRE=$(ssh "$REMOTE" "cd $REMOTE_DIR && git rev-parse HEAD")
    echo "remote HEAD (pre-pull): $REMOTE_HEAD_PRE"
}

# -----------------------------------------------------------------------------
# step 3: abort_if_remote_dirty — if Mac Mini has uncommitted changes, STOP.
# We do not resolve conflicts via a deploy script. Human intervention required.
# -----------------------------------------------------------------------------
step_abort_if_remote_dirty() {
    local dirty
    dirty=$(ssh "$REMOTE" "cd $REMOTE_DIR && git status --porcelain")
    if [ -n "$dirty" ]; then
        echo "ABORT: Mac Mini working tree is dirty:" >&2
        echo "$dirty" >&2
        exit 2
    fi
    echo "remote working tree clean."
}

# -----------------------------------------------------------------------------
# step 4: git_push — push local master to origin.
# -----------------------------------------------------------------------------
step_git_push() {
    cd "$LOCAL_DIR"
    git push origin master
}

# -----------------------------------------------------------------------------
# step 5: vacuum_backup — pre-deploy snapshot of kasane.db via VACUUM INTO.
# VACUUM INTO forces a WAL checkpoint and writes a consistent atomic snapshot,
# unlike file copy. Backup path: data/kasane.db.pre-deploy.<utc-timestamp>.
# Belt-and-suspenders for HARD RULE #1: every destructive operation needs a
# named rollback point. Even though pulls on Mac Mini aren't destructive per se,
# the restart is — a bad commit + zombie worker can corrupt on-disk state.
# -----------------------------------------------------------------------------
step_vacuum_backup() {
    local ts
    ts=$(date -u +%Y%m%dT%H%M%SZ)
    local backup_name="data/kasane.db.pre-deploy.$ts"
    ssh "$REMOTE" "cd $REMOTE_DIR && sqlite3 data/kasane.db \"VACUUM INTO '$backup_name'\""
    echo "backup: $backup_name"
}

# -----------------------------------------------------------------------------
# step 6: git_pull — fast-forward pull on Mac Mini + dep sync.
# --ff-only refuses a merge if the remote has diverged (which step 3 already
# forbade, but belt-and-suspenders).
# -----------------------------------------------------------------------------
step_git_pull() {
    ssh "$REMOTE" "cd $REMOTE_DIR && git pull --ff-only && export PATH=\$HOME/.local/bin:\$PATH && uv sync --all-extras"
}

# -----------------------------------------------------------------------------
# step 7: remote_head_assert — after the pull, Mac Mini's HEAD must equal
# the laptop's pre-push HEAD. If not, someone else pushed between step 4 and
# step 6, or the pull failed silently. STOP.
# -----------------------------------------------------------------------------
step_remote_head_assert() {
    REMOTE_HEAD_POST=$(ssh "$REMOTE" "cd $REMOTE_DIR && git rev-parse HEAD")
    if [ "$REMOTE_HEAD_POST" != "$LOCAL_HEAD" ]; then
        echo "ABORT: remote HEAD post-pull ($REMOTE_HEAD_POST) != local HEAD ($LOCAL_HEAD)" >&2
        exit 3
    fi
    echo "remote HEAD assert ok: $REMOTE_HEAD_POST"
}

# -----------------------------------------------------------------------------
# step 8: restart_api — blue/green USR2 restart by default (--hard).
# -----------------------------------------------------------------------------
step_restart_api() {
    ssh "$REMOTE" "cd $REMOTE_DIR && bash scripts/restart-api.sh $RESTART_FLAG"
}

# -----------------------------------------------------------------------------
# step 9: curl_health — verify the API is reachable and status=ok post-restart.
# -----------------------------------------------------------------------------
step_curl_health() {
    local body
    body=$(curl -fsS "$HEALTH_URL")
    echo "$body"
    if ! printf '%s' "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
        echo "ABORT: /health did not report status=ok" >&2
        exit 4
    fi
}

# -----------------------------------------------------------------------------
# step 10: assert_commit_matches — /health's `commit` field must match the
# sha we just deployed. Catches zombie-worker drift (old bytecode, new git).
# -----------------------------------------------------------------------------
step_assert_commit_matches() {
    local body reported
    body=$(curl -fsS "$HEALTH_URL")
    reported=$(printf '%s' "$body" | sed -n 's/.*"commit"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    if [ -z "$reported" ]; then
        echo "ABORT: /health response has no commit field" >&2
        echo "body: $body" >&2
        exit 5
    fi
    # Accept prefix match so short or full shas both work.
    case "$LOCAL_HEAD" in
        "$reported"*) ;;
        *)
            case "$reported" in
                "$LOCAL_HEAD"*) ;;
                *)
                    echo "ABORT: /health commit=$reported does not match local HEAD=$LOCAL_HEAD" >&2
                    exit 6
                    ;;
            esac
            ;;
    esac
    echo "commit assert ok: /health commit=$reported matches local HEAD=$LOCAL_HEAD"
}

# -----------------------------------------------------------------------------
# test gate (not part of the 10 steps — runs before the state machine)
# -----------------------------------------------------------------------------
if [ "$DRY_RUN_ACTIVE" != "1" ] && [ "$RUN_TESTS" = true ]; then
    echo "Running tests..."
    cd "$LOCAL_DIR" && .venv/bin/python3 -m pytest tests/ -x -q --tb=short || {
        echo "Tests failed. Aborting deploy."
        exit 1
    }
    echo ""
fi

# -----------------------------------------------------------------------------
# run the 10-step state machine
# -----------------------------------------------------------------------------
run_step local_head_check
run_step remote_head_check
run_step abort_if_remote_dirty
run_step git_push
run_step vacuum_backup
run_step git_pull
run_step remote_head_assert
run_step restart_api
run_step curl_health
run_step assert_commit_matches

if [ "$DRY_RUN_ACTIVE" = "1" ]; then
    echo "STEP:done" >> "$DEPLOY_DRY_RUN_LOG"
    echo "dry-run complete — see $DEPLOY_DRY_RUN_LOG"
else
    echo ""
    echo "Deploy complete."
fi
