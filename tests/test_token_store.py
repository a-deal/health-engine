"""Tests for TokenStore encryption."""

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def token_dir(tmp_path):
    return tmp_path / "tokens"


@pytest.fixture
def key_path(tmp_path):
    return tmp_path / "token.key"


@pytest.fixture
def store_encrypted(token_dir, key_path, monkeypatch):
    """TokenStore with Fernet encryption enabled."""
    monkeypatch.setattr("engine.gateway.token_store._BASE_DIR", token_dir)
    monkeypatch.setattr("engine.gateway.token_store._KEY_PATH", key_path)
    # Clear any env var so key is auto-generated
    monkeypatch.delenv("HE_TOKEN_KEY", raising=False)
    from engine.gateway.token_store import TokenStore
    return TokenStore(base_dir=token_dir)


@pytest.fixture
def store_no_crypto(token_dir, monkeypatch):
    """TokenStore with cryptography unavailable."""
    monkeypatch.setattr("engine.gateway.token_store._BASE_DIR", token_dir)

    import engine.gateway.token_store as mod
    original = mod._get_fernet

    def _no_fernet():
        return None

    monkeypatch.setattr(mod, "_get_fernet", _no_fernet)
    from engine.gateway.token_store import TokenStore
    store = TokenStore(base_dir=token_dir)
    store._fernet = None
    return store


def test_encrypt_decrypt_roundtrip(store_encrypted):
    """Tokens saved encrypted can be loaded back."""
    data = {
        "access_token": "ya29.test",
        "refresh_token": "1//0test",
        "client_id": "test.apps.googleusercontent.com",
        "client_secret": "secret123",
    }
    store_encrypted.save_token("google-calendar", "testuser", data)
    loaded = store_encrypted.load_token("google-calendar", "testuser")
    assert loaded == data


def test_encrypted_file_is_not_plaintext(store_encrypted, token_dir):
    """The raw file on disk should not contain plaintext tokens."""
    data = {"access_token": "ya29.plaintext_check", "refresh_token": "1//0refresh"}
    store_encrypted.save_token("google-calendar", "testuser", data)

    raw = (token_dir / "google-calendar" / "testuser" / "token.json").read_bytes()
    assert b"ya29.plaintext_check" not in raw
    assert raw.startswith(b"gAAAAA")  # Fernet prefix


def test_backward_compat_plaintext_load(store_encrypted, token_dir):
    """Plaintext JSON files from before encryption can still be loaded."""
    td = token_dir / "google-calendar" / "legacy"
    td.mkdir(parents=True)
    data = {"access_token": "old_token", "refresh_token": "old_refresh"}
    (td / "token.json").write_text(json.dumps(data))

    loaded = store_encrypted.load_token("google-calendar", "legacy")
    assert loaded == data


def test_no_crypto_saves_plaintext(store_no_crypto, token_dir):
    """Without cryptography, tokens are saved as plaintext JSON."""
    data = {"access_token": "plain", "refresh_token": "text"}
    store_no_crypto.save_token("test-service", "user1", data)

    raw = (token_dir / "test-service" / "user1" / "token.json").read_bytes()
    assert b"plain" in raw
    loaded = store_no_crypto.load_token("test-service", "user1")
    assert loaded == data


def test_has_token(store_encrypted):
    """has_token returns True after saving."""
    assert not store_encrypted.has_token("svc", "u1")
    store_encrypted.save_token("svc", "u1", {"token": "val"})
    assert store_encrypted.has_token("svc", "u1")


def test_load_missing_returns_none(store_encrypted):
    assert store_encrypted.load_token("nonexistent", "nobody") is None


def test_key_auto_generated(key_path, token_dir, monkeypatch):
    """Key file is auto-generated on first use."""
    monkeypatch.setattr("engine.gateway.token_store._BASE_DIR", token_dir)
    monkeypatch.setattr("engine.gateway.token_store._KEY_PATH", key_path)
    monkeypatch.delenv("HE_TOKEN_KEY", raising=False)

    assert not key_path.exists()
    from engine.gateway.token_store import _get_fernet
    f = _get_fernet()
    assert f is not None
    assert key_path.exists()
    # Key file should be 600 permissions
    mode = oct(key_path.stat().st_mode)[-3:]
    assert mode == "600"


def test_env_var_key(token_dir, monkeypatch):
    """HE_TOKEN_KEY env var is used when set."""
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    monkeypatch.setenv("HE_TOKEN_KEY", key.decode())
    monkeypatch.setattr("engine.gateway.token_store._BASE_DIR", token_dir)

    from engine.gateway.token_store import _get_fernet
    f = _get_fernet()
    assert f is not None
    # Verify it works
    ct = f.encrypt(b"test")
    assert f.decrypt(ct) == b"test"
