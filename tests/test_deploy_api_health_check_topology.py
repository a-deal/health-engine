"""Test for the deploy-api.sh steps 9/10 topology bug.

Source: 2026-04-13 0744 handoff, follow-up #2.

Bug: deploy-api.sh defaults HEALTH_URL=http://localhost:18800/health and
steps 9 (curl_health) and 10 (assert_commit_matches) curl that URL from
the laptop shell, not via ssh. The API binds to localhost:18800 on Mac
Mini, so from the laptop this always connection-refuses. `set -e` +
`curl -fsS` propagates the failure before the intended ABORT message
can print, so the script exits at step 9 with curl's exit 7, not the
intended exit 4. Every laptop-initiated deploy hits this.

Fix: the curl in step_curl_health and step_assert_commit_matches must
run inside `ssh "$REMOTE"` so it resolves on Mac Mini.

The DRY_RUN state-machine tests cannot catch this because DRY_RUN skips
step function bodies entirely. A structural test reads the script text
and asserts each health-check step function dispatches its curl through
ssh on $REMOTE.
"""

import re
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "deploy-api.sh"


def _extract_function_body(source: str, name: str) -> str:
    """Return the body of a bash function `name() { ... }` from source.

    Assumes the opening `{` is on the same line as the function header
    (which is the style used throughout deploy-api.sh) and tracks brace
    depth to find the matching close.
    """
    header = re.search(rf"^{re.escape(name)}\(\)\s*\{{", source, re.MULTILINE)
    assert header, f"function {name} not found in deploy-api.sh"
    start = header.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"unbalanced braces in {name}"
    return source[start : i - 1]


def test_curl_health_runs_via_ssh_on_remote():
    source = SCRIPT.read_text()
    body = _extract_function_body(source, "step_curl_health")
    assert "curl" in body, "step_curl_health should curl /health"
    # Every curl line must be dispatched via `ssh "$REMOTE"` so it
    # resolves localhost:18800 on Mac Mini, not on the laptop.
    for line in body.splitlines():
        if "curl" in line and not line.strip().startswith("#"):
            assert 'ssh "$REMOTE"' in line or "ssh $REMOTE" in line, (
                f"step_curl_health invokes curl without ssh wrapper: {line.strip()!r}\n"
                f"This is the 0744 handoff topology bug — curl on the laptop "
                f"cannot reach localhost:18800 on Mac Mini."
            )


def test_assert_commit_matches_runs_curl_via_ssh_on_remote():
    source = SCRIPT.read_text()
    body = _extract_function_body(source, "step_assert_commit_matches")
    assert "curl" in body, "step_assert_commit_matches should curl /health"
    for line in body.splitlines():
        if "curl" in line and not line.strip().startswith("#"):
            assert 'ssh "$REMOTE"' in line or "ssh $REMOTE" in line, (
                f"step_assert_commit_matches invokes curl without ssh wrapper: "
                f"{line.strip()!r}\n"
                f"This is the 0744 handoff topology bug — curl on the laptop "
                f"cannot reach localhost:18800 on Mac Mini."
            )
