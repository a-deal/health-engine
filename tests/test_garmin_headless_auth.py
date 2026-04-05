"""Tests for headless Garmin auth (remote users who can't open a browser)."""

import inspect
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestHeadlessGarminAuth:
    """_auth_garmin with email+password should skip browser and auth directly."""

    def _mock_garmin(self, succeed=True):
        mock = MagicMock()
        if succeed:
            mock.login.return_value = None
            mock.garth.dump = lambda d: (
                Path(d).mkdir(parents=True, exist_ok=True),
                (Path(d) / "oauth1_token.json").write_text('{"t": "1"}'),
                (Path(d) / "oauth2_token.json").write_text('{"t": "2"}'),
            )
        else:
            mock.login.side_effect = Exception("401 Client Error")
        return mock

    def test_headless_auth_success(self):
        """When email and password are provided, auth succeeds without browser."""
        with patch("garminconnect.Garmin", return_value=self._mock_garmin()), \
             patch("mcp_server.tools._get_token_store") as mock_ts:
            mock_ts.return_value = MagicMock()

            from mcp_server.tools import _auth_garmin
            result = _auth_garmin(user_id="mike", email="mike@example.com", password="secret123")

        assert result["authenticated"] is True

    def test_headless_auth_bad_credentials(self):
        """When credentials are wrong, returns error without browser."""
        with patch("garminconnect.Garmin", return_value=self._mock_garmin(succeed=False)), \
             patch("mcp_server.tools._get_token_store") as mock_ts:
            mock_ts.return_value = MagicMock()

            from mcp_server.tools import _auth_garmin
            result = _auth_garmin(user_id="mike", email="mike@example.com", password="wrong")

        assert result["authenticated"] is False
        assert "error" in result

    def test_headless_auth_syncs_to_token_store(self):
        """After headless auth, tokens should be synced to SQLite TokenStore."""
        mock_store = MagicMock()

        with patch("garminconnect.Garmin", return_value=self._mock_garmin()), \
             patch("mcp_server.tools._get_token_store") as mock_ts:
            mock_ts.return_value = mock_store

            from mcp_server.tools import _auth_garmin
            result = _auth_garmin(user_id="mike", email="mike@example.com", password="secret123")

        assert result["authenticated"] is True
        mock_store.sync_garmin_tokens.assert_called_once_with("mike")

    def test_no_credentials_falls_back_to_browser(self):
        """When no email/password, should use browser flow as before."""
        with patch("mcp_server.garmin_auth.run_auth_flow") as mock_browser, \
             patch("mcp_server.tools._get_token_store") as mock_ts:
            mock_browser.return_value = {"authenticated": True, "message": "done"}
            mock_ts.return_value = MagicMock()

            from mcp_server.tools import _auth_garmin
            result = _auth_garmin(user_id="andrew")

        mock_browser.assert_called_once()
        assert result["authenticated"] is True

    def test_signature_accepts_email_password(self):
        """_auth_garmin should accept email and password params."""
        from mcp_server.tools import _auth_garmin
        sig = inspect.signature(_auth_garmin)
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        # Both should be optional (default None)
        assert sig.parameters["email"].default is None
        assert sig.parameters["password"].default is None
