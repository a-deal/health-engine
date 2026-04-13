"""Tests for the `commit` field on /health.

Source: 2026-04-12 accidental-deploy incident + Task B deploy-api.sh 10-step
state machine. Step 10 of the new state machine asserts that the /health
endpoint returns a `commit` field matching the git HEAD that was just
deployed. Without this, there is no way to catch "the pull was fast-forwarded
but gunicorn is still running old bytecode" (zombie worker) or
"deploy restarted but the wrong commit is live" drift. This test pins the
contract so future deploys can assert on it.
"""

import re
import subprocess

from fastapi.testclient import TestClient

from engine.gateway.config import GatewayConfig
from engine.gateway.server import create_app

TOKEN = "test-token-commit-field"


def _current_git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()


def test_health_returns_commit_field():
    app = create_app(GatewayConfig(port=18900, api_token=TOKEN))
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "commit" in body, f"/health must return a `commit` field, got {body}"


def test_health_commit_field_matches_git_head():
    app = create_app(GatewayConfig(port=18901, api_token=TOKEN))
    client = TestClient(app)
    body = client.get("/health").json()
    sha = body["commit"]
    # Must be a 40-char hex sha, OR the short form (7-12 chars), OR "unknown"
    # if git isn't available. Accept short + full; reject anything else.
    assert isinstance(sha, str) and sha, f"commit field must be a non-empty string, got {sha!r}"
    if sha != "unknown":
        assert re.fullmatch(r"[0-9a-f]{7,40}", sha), (
            f"commit field must be a git sha or 'unknown', got {sha!r}"
        )
        # If we have a real sha, it should match git rev-parse HEAD (at least by prefix)
        head = _current_git_sha()
        assert head.startswith(sha) or sha.startswith(head[: len(sha)]), (
            f"commit field {sha!r} does not match git HEAD {head!r}"
        )


def test_health_still_returns_status_and_timestamp():
    """Adding `commit` must not drop the existing fields."""
    app = create_app(GatewayConfig(port=18902, api_token=TOKEN))
    client = TestClient(app)
    body = client.get("/health").json()
    assert body.get("status") == "ok"
    assert "timestamp" in body
