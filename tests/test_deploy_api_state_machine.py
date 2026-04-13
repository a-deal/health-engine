"""Tests for the 10-step deploy-api.sh state machine (Task B).

Source: 2026-04-12 accidental-deploy incident + baseline-consolidation
sprint plan. The old script was a flat sequence (push → pull → restart)
with no pre-deploy backup, no post-deploy SHA assertion, and no per-step
dry-run marker. The new state machine is 10 explicit steps, each callable
as a no-op under DRY_RUN so we can test the order without touching prod.

The 10 steps, in order:
  1.  local_head_check       — record local git HEAD sha
  2.  remote_head_check      — ssh mac-mini and record remote git HEAD sha
  3.  abort_if_remote_dirty  — fail fast if Mac Mini working tree is dirty
  4.  git_push               — push origin master
  5.  vacuum_backup          — sqlite3 VACUUM INTO data/kasane.db.pre-deploy.<ts>
  6.  git_pull               — ssh mac-mini git pull --ff-only
  7.  remote_head_assert     — assert remote HEAD now matches local pre-push sha
  8.  restart_api            — ssh mac-mini bash scripts/restart-api.sh --hard
  9.  curl_health            — curl local /health and check status=ok
  10. assert_commit_matches  — assert /health `commit` field matches local HEAD

Each test runs the real script with DRY_RUN=1 behind a sandboxed $PATH
of exit-87 shims for ssh/git/curl, so if a step accidentally performs a
side effect the test blows up loudly instead of quietly doing it.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "deploy-api.sh"

EXPECTED_STEPS = [
    "local_head_check",
    "remote_head_check",
    "abort_if_remote_dirty",
    "git_push",
    "vacuum_backup",
    "git_pull",
    "remote_head_assert",
    "restart_api",
    "curl_health",
    "assert_commit_matches",
]


@pytest.fixture
def dry_run_env(tmp_path):
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    for cmd in ("ssh", "git", "curl", "sqlite3"):
        shim = shim_dir / cmd
        shim.write_text(
            f'#!/usr/bin/env bash\n'
            f'echo "FATAL: {cmd} invoked in DRY_RUN — side effect leak" >&2\n'
            f'exit 87\n'
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env["DRY_RUN"] = "1"
    env["DEPLOY_DRY_RUN_LOG"] = str(tmp_path / "deploy-dry-run.log")
    return env, Path(env["DEPLOY_DRY_RUN_LOG"])


def _run(env):
    return subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_dry_run_emits_all_ten_step_markers(dry_run_env):
    env, log_path = dry_run_env
    result = _run(env)
    assert result.returncode == 0, (
        f"dry run should exit 0. rc={result.returncode} stderr={result.stderr}"
    )
    assert "FATAL:" not in result.stderr, (
        f"a shim fired — side effect leaked. stderr={result.stderr}"
    )
    contents = log_path.read_text()
    for step in EXPECTED_STEPS:
        assert f"STEP:{step}" in contents, (
            f"missing STEP:{step} marker in dry-run log.\n"
            f"full log:\n{contents}"
        )


def test_dry_run_steps_are_in_order(dry_run_env):
    env, log_path = dry_run_env
    _run(env)
    contents = log_path.read_text()
    positions = []
    for step in EXPECTED_STEPS:
        marker = f"STEP:{step}"
        pos = contents.find(marker)
        assert pos >= 0, f"missing {marker}"
        positions.append((step, pos))
    # Positions must be strictly increasing.
    for (prev_step, prev_pos), (next_step, next_pos) in zip(positions, positions[1:]):
        assert prev_pos < next_pos, (
            f"step {next_step!r} appears before {prev_step!r} in dry-run log — "
            f"state machine ordering broken.\nfull log:\n{contents}"
        )


def test_dry_run_does_not_invoke_side_effects(dry_run_env):
    """Under DRY_RUN no shim for ssh/git/curl/sqlite3 should fire."""
    env, _log = dry_run_env
    result = _run(env)
    assert result.returncode == 0
    # If any shim fired, the test file would contain "FATAL:" on stderr.
    assert "FATAL:" not in result.stderr


def test_dry_run_log_includes_target_remote_info(dry_run_env):
    """The dry-run log should record which remote host the script would target.

    This is a smoke test that the log is actually useful for debugging,
    not just a list of step names with no context.
    """
    env, log_path = dry_run_env
    _run(env)
    contents = log_path.read_text()
    assert "mac-mini" in contents, (
        f"dry-run log should mention target remote 'mac-mini' for "
        f"debuggability. got:\n{contents}"
    )
