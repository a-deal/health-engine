"""Tests for Google Calendar OAuth gateway routes."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.gateway.config import GatewayConfig
from engine.gateway.server import create_app
import engine.gateway.server as _server_mod


@pytest.fixture
def google_secrets(tmp_path):
    """Write a fake Google client secrets file."""
    secrets_path = tmp_path / "client_secrets.json"
    secrets_path.write_text(json.dumps({
        "web": {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret",
            "redirect_uris": ["http://localhost:18899/auth/google/callback"],
        }
    }))
    return str(secrets_path)


@pytest.fixture
def config(tmp_path, google_secrets):
    return GatewayConfig(
        port=18899,
        api_token="test-token-123",
        hmac_secret="test-hmac-secret",
        google_client_secrets_path=google_secrets,
    )


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Clear rate limit state between tests."""
    _server_mod._rate_limits.clear()


@pytest.fixture
def client(config):
    from fastapi.testclient import TestClient
    app = create_app(config)
    return TestClient(app)


def _sign_state(secret: str, user_id: str, service: str) -> str:
    """Generate HMAC state matching the server's algorithm."""
    import hashlib
    import hmac
    bucket = str(int(time.time()) // 3600)
    payload = f"{user_id}:{service}:{bucket}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


class TestGoogleAuthStart:
    def test_valid_state_redirects_to_google(self, client, config):
        state = _sign_state(config.hmac_secret, "testuser", "google-calendar")
        resp = client.get(f"/auth/google?user=testuser&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "accounts.google.com/o/oauth2/v2/auth" in location
        assert "test-client-id.apps.googleusercontent.com" in location
        assert "code_challenge=" in location
        assert "S256" in location

    def test_invalid_state_returns_403(self, client):
        resp = client.get("/auth/google?user=testuser&state=bad:state:0:sig")
        assert resp.status_code == 403
        assert "expired" in resp.text.lower() or "invalid" in resp.text.lower()

    def test_mismatched_user_returns_403(self, client, config):
        state = _sign_state(config.hmac_secret, "alice", "google-calendar")
        resp = client.get(f"/auth/google?user=bob&state={state}")
        assert resp.status_code == 403

    def test_wrong_service_returns_403(self, client, config):
        state = _sign_state(config.hmac_secret, "testuser", "garmin")
        resp = client.get(f"/auth/google?user=testuser&state={state}")
        assert resp.status_code == 403

    def test_missing_secrets_returns_500(self, tmp_path):
        from fastapi.testclient import TestClient
        cfg = GatewayConfig(
            port=18899,
            api_token="test",
            hmac_secret="test-hmac-secret",
            google_client_secrets_path="",
        )
        app = create_app(cfg)
        tc = TestClient(app)
        state = _sign_state(cfg.hmac_secret, "testuser", "google-calendar")
        resp = tc.get(f"/auth/google?user=testuser&state={state}")
        assert resp.status_code == 500
        assert "not configured" in resp.text.lower()


class TestGoogleCallback:
    def test_error_param_returns_403(self, client):
        resp = client.get("/auth/google/callback?error=access_denied&state=x")
        assert resp.status_code == 403
        assert "denied" in resp.text.lower()

    def test_missing_code_returns_400(self, client):
        resp = client.get("/auth/google/callback?state=x")
        assert resp.status_code == 400

    def test_unknown_state_returns_403(self, client):
        resp = client.get("/auth/google/callback?code=authcode&state=unknown:state:0:sig")
        assert resp.status_code == 403
        assert "expired" in resp.text.lower()

    @patch("urllib.request.urlopen")
    def test_successful_callback_saves_tokens(self, mock_urlopen, client, config, tmp_path):
        """Full flow: start -> get state -> callback with code -> tokens saved."""
        # Step 1: Start the OAuth flow to register a pending flow
        state = _sign_state(config.hmac_secret, "testuser", "google-calendar")
        resp = client.get(f"/auth/google?user=testuser&state={state}", follow_redirects=False)
        assert resp.status_code == 302

        # Step 2: Mock Google's token endpoint response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "access_token": "ya29.new_access",
            "refresh_token": "1//0new_refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Step 3: Hit the callback
        resp = client.get(f"/auth/google/callback?code=test_auth_code&state={state}")
        assert resp.status_code == 200
        assert "Connected" in resp.text or "connected" in resp.text

        # Verify token exchange was called
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert b"test_auth_code" in req.data
        assert b"code_verifier" in req.data


class TestConnectGoogleCalendarTool:
    @patch("engine.gateway.token_store.TokenStore.has_token", return_value=False)
    @patch("engine.gateway.config.load_gateway_config")
    def test_returns_auth_url(self, mock_config, mock_has_token):
        mock_config.return_value = GatewayConfig(
            hmac_secret="test-secret",
            tunnel_domain="auth.mybaseline.health",
        )
        from mcp_server.tools import _connect_google_calendar
        result = _connect_google_calendar(user_id="paul")
        assert "auth_url" in result
        assert "auth.mybaseline.health/auth/google" in result["auth_url"]
        assert result["user_id"] == "paul"

    @patch("engine.gateway.token_store.TokenStore.has_token", return_value=True)
    @patch("engine.gateway.config.load_gateway_config")
    def test_already_connected(self, mock_config, mock_has_token):
        mock_config.return_value = GatewayConfig(hmac_secret="test-secret")
        from mcp_server.tools import _connect_google_calendar
        result = _connect_google_calendar(user_id="paul")
        assert result["already_connected"] is True
