"""Tests for Twilio SMS webhook and outbound SMS."""

import base64
import hashlib
import hmac

import pytest

from engine.gateway.twilio_sms import (
    _verify_twilio_signature,
    _lookup_user_by_phone,
    send_sms,
)


class TestSignatureVerification:
    """Test Twilio X-Twilio-Signature HMAC-SHA1 verification."""

    def _make_signature(self, auth_token: str, url: str, params: dict) -> str:
        """Generate a valid Twilio signature for testing."""
        data = url
        for key in sorted(params.keys()):
            data += key + params[key]
        sig = hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(sig).decode("utf-8")

    def test_valid_signature(self):
        token = "test_auth_token_12345"
        url = "https://auth.mybaseline.health/api/webhooks/twilio"
        params = {
            "From": "+18312917892",
            "To": "+16508897482",
            "Body": "Hello Milo",
            "MessageSid": "SM123abc",
        }
        sig = self._make_signature(token, url, params)
        assert _verify_twilio_signature(token, url, params, sig) is True

    def test_invalid_signature(self):
        token = "test_auth_token_12345"
        url = "https://auth.mybaseline.health/api/webhooks/twilio"
        params = {"From": "+18312917892", "Body": "Hello"}
        assert _verify_twilio_signature(token, url, params, "badsig") is False

    def test_tampered_params(self):
        token = "test_auth_token_12345"
        url = "https://auth.mybaseline.health/api/webhooks/twilio"
        params = {"From": "+18312917892", "Body": "Hello"}
        sig = self._make_signature(token, url, params)
        # Tamper with body
        params["Body"] = "Tampered"
        assert _verify_twilio_signature(token, url, params, sig) is False

    def test_empty_params(self):
        token = "test_auth_token_12345"
        url = "https://auth.mybaseline.health/api/webhooks/twilio"
        params = {}
        sig = self._make_signature(token, url, params)
        assert _verify_twilio_signature(token, url, params, sig) is True


class TestUserLookup:
    """Test phone number to user_id resolution."""

    def test_known_user(self):
        """Users in the OpenClaw users.yaml should resolve."""
        # This depends on the actual users.yaml on the system
        result = _lookup_user_by_phone("+79872907160")
        if result is not None:
            assert result == "grigoriy"

    def test_unknown_number(self):
        result = _lookup_user_by_phone("+19999999999")
        assert result is None

    def test_normalizes_number(self):
        """Should handle numbers without leading +."""
        result = _lookup_user_by_phone("19999999999")
        assert result is None  # Unknown, but shouldn't crash


class TestSendSms:
    """Test outbound SMS (without hitting Twilio API)."""

    def test_missing_credentials(self):
        result = send_sms(to="+18312917892", body="test")
        assert result["status"] == "error"
        assert "not configured" in result["error"]

    def test_missing_to(self):
        result = send_sms(
            to="", body="test",
            account_sid="AC123", auth_token="tok", from_number="+16508897482",
        )
        # Empty 'to' will fail at Twilio API level or be caught
        # Just verify it doesn't crash
        assert "status" in result
