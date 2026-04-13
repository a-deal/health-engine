"""The DRY_RUN=1 guard in deploy-api.sh must short-circuit before any side effect.

Source: 2026-04-12 accidental-deploy incident. A prior test invoked
deploy-api.sh against the real Mac Mini because the script had no
DRY_RUN guard and treated the env var as noise. This test pins the
contract that DRY_RUN=1 is an early exit with no git/ssh/curl calls,
so future tests (the full 10-step dry-run harness in Task B) can run
safely against the real script.

This is HARD RULE #9 in ~/.claude/CLAUDE.md: side-effecting scripts
must be no-op by default. The guard is commit #1 before any tests
that exercise deploy logic.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "deploy-api.sh"


@pytest.fixture
def sandboxed_env(tmp_path):
    """PATH points at shims that explode if ssh/git/curl are invoked.

    If the DRY_RUN guard works, none of these shims should ever run.
    If the guard is missing or broken, the shim exits non-zero with
    a loud message, which fails the test — safely, without touching
    the real remote.
    """
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    for cmd in ("ssh", "git", "curl"):
        shim = shim_dir / cmd
        shim.write_text(
            f'#!/usr/bin/env bash\n'
            f'echo "FATAL: {cmd} invoked while DRY_RUN=1 — guard failed" >&2\n'
            f'exit 87\n'
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env["DRY_RUN"] = "1"
    env["DEPLOY_DRY_RUN_LOG"] = str(tmp_path / "deploy-dry-run.log")
    return env, tmp_path


def test_deploy_script_with_dry_run_does_not_invoke_ssh_git_or_curl(sandboxed_env):
    env, tmp_path = sandboxed_env
    result = subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # If the guard works, exit is 0 and the shims never ran (no exit 87).
    assert result.returncode == 0, (
        f"deploy-api.sh with DRY_RUN=1 must exit 0 without side effects.\n"
        f"returncode={result.returncode}\n"
        f"stdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )
    # The shims write "FATAL:" to stderr if they're ever invoked.
    assert "FATAL:" not in result.stderr, (
        f"a sandboxed shim was invoked during DRY_RUN — guard is not early "
        f"enough. stderr={result.stderr}"
    )


def test_deploy_script_with_dry_run_writes_marker_to_log(sandboxed_env):
    """The guard should leave a trace so test harnesses can tell it fired."""
    env, tmp_path = sandboxed_env
    log_path = Path(env["DEPLOY_DRY_RUN_LOG"])
    subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert log_path.exists(), (
        f"DRY_RUN guard must write a marker to $DEPLOY_DRY_RUN_LOG "
        f"({log_path}) so harnesses can assert the guard fired."
    )
    contents = log_path.read_text()
    assert "DRY_RUN" in contents, (
        f"dry-run log should mention DRY_RUN, got: {contents!r}"
    )


# --- Task B (2026-04-13) widen-match flags from W review ---
#
# The initial DRY_RUN guard matched only the literal string "1". The W
# review flagged this as too narrow: DRY_RUN=true, DRY_RUN=yes, DRY_RUN=TRUE,
# and DRY_RUN="1 " (trailing space) all fell through to a real deploy.
# The class of bug is "test sets an env var the script ignores," which is
# EXACTLY what caused the 2026-04-12 accidental-deploy incident. Widen the
# match and pin the contract with a test per truthy form.


@pytest.mark.parametrize(
    "dry_run_value",
    ["1", "true", "TRUE", "True", "yes", "YES", "y", "Y", "t", "T", "1 ", " 1", "  true  "],
)
def test_dry_run_guard_accepts_truthy_forms(tmp_path, dry_run_value):
    """All standard truthy forms of DRY_RUN must short-circuit."""
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    for cmd in ("ssh", "git", "curl"):
        shim = shim_dir / cmd
        shim.write_text(
            f'#!/usr/bin/env bash\n'
            f'echo "FATAL: {cmd} invoked while DRY_RUN={dry_run_value!r} — guard failed" >&2\n'
            f'exit 87\n'
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env["DRY_RUN"] = dry_run_value
    env["DEPLOY_DRY_RUN_LOG"] = str(tmp_path / "deploy-dry-run.log")

    result = subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"DRY_RUN={dry_run_value!r} must short-circuit cleanly.\n"
        f"returncode={result.returncode}\nstderr={result.stderr}"
    )
    assert "FATAL:" not in result.stderr, (
        f"DRY_RUN={dry_run_value!r} let a shim fire: {result.stderr}"
    )


@pytest.mark.parametrize(
    "dry_run_value",
    ["", "0", "false", "FALSE", "no", "N", "off"],
)
def test_dry_run_guard_rejects_falsy_forms(tmp_path, dry_run_value):
    """Falsy forms must NOT short-circuit — they fall through to real deploy.

    We still shim ssh/git/curl, so if the guard correctly lets these through,
    the script will try to git push and hit the shim, exiting 87 or similar.
    The assertion is that the guard does NOT silently eat these values; the
    script must proceed past the guard.
    """
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    for cmd in ("ssh", "git", "curl"):
        shim = shim_dir / cmd
        shim.write_text(
            f'#!/usr/bin/env bash\n'
            f'echo "shim-{cmd}-fired" >&2\n'
            f'exit 87\n'
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    if dry_run_value:
        env["DRY_RUN"] = dry_run_value
    else:
        env.pop("DRY_RUN", None)
    env["DEPLOY_DRY_RUN_LOG"] = str(tmp_path / "deploy-dry-run.log")

    result = subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # With a falsy DRY_RUN, the script should proceed and hit a shim.
    # It should NOT exit 0 (which would mean the guard silently ate it).
    assert result.returncode != 0, (
        f"DRY_RUN={dry_run_value!r} must NOT be treated as truthy. "
        f"Script exited 0 without hitting any shim, meaning the guard "
        f"silently accepted a falsy value.\nstderr={result.stderr}"
    )


def test_dry_run_log_default_path_is_pid_namespaced(tmp_path):
    """When $DEPLOY_DRY_RUN_LOG is unset, default must include $$ (PID).

    The previous default was /tmp/deploy-dry-run.log — a single shared file
    that races under CI parallelism. W review flagged this. New default:
    /tmp/deploy-dry-run.<PID>.log.

    We can't easily grep the script's internal variable from the outside,
    so this test exercises the behavior: run the script with DRY_RUN
    truthy and no $DEPLOY_DRY_RUN_LOG, then verify the PID-namespaced file
    exists in /tmp.
    """
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    for cmd in ("ssh", "git", "curl"):
        shim = shim_dir / cmd
        shim.write_text(
            f'#!/usr/bin/env bash\necho "FATAL: {cmd}" >&2\nexit 87\n'
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env["DRY_RUN"] = "1"
    env.pop("DEPLOY_DRY_RUN_LOG", None)

    # Snapshot /tmp before, run, then look for a new file matching the pattern.
    tmp = Path("/tmp")
    before = set(p.name for p in tmp.glob("deploy-dry-run.*.log"))
    result = subprocess.run(
        ["bash", str(SCRIPT), "--skip-tests"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"guard should have fired: {result.stderr}"
    after = set(p.name for p in tmp.glob("deploy-dry-run.*.log"))
    new_files = after - before
    assert new_files, (
        f"expected a new /tmp/deploy-dry-run.<PID>.log file; "
        f"before={before} after={after}"
    )
    # Clean up — don't leave litter in /tmp.
    for name in new_files:
        try:
            (tmp / name).unlink()
        except OSError:
            pass
