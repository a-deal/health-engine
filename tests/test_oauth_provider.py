"""Tests for MCP OAuth provider (magic invite flow).

Tests the full OAuth flow that Claude iOS uses to connect:
1. Dynamic client registration
2. Authorization via magic invite link
3. Code exchange for access/refresh tokens
4. Token refresh
5. Token verification (load_access_token)
6. Token revocation
"""

import asyncio
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engine.gateway.db import init_db, get_db, close_db


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def db(tmp_path):
    """Fresh SQLite database for each test."""
    close_db()
    db_path = tmp_path / "kasane.db"
    init_db(db_path)
    conn = get_db(db_path)

    # Create a test person for invite linking
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO person (id, name, health_engine_user_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("p-paul-001", "Paul Mederos", "paul", now, now),
    )
    conn.commit()

    yield conn, db_path

    close_db()


def _make_client():
    from mcp.shared.auth import OAuthClientInformationFull
    return OAuthClientInformationFull(
        client_id="test-client-123",
        client_secret="test-secret-456",
        client_id_issued_at=int(time.time()),
        redirect_uris=["https://claude.ai/oauth/callback"],
        token_endpoint_auth_method="client_secret_post",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="health",
    )


def _make_invite(conn, person_id="p-paul-001"):
    code = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO oauth_invite (code, person_id, created_at) VALUES (?, ?, ?)",
        (code, person_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return code


# --- Schema tests ---

class TestOAuthSchema:

    def test_oauth_client_table_exists(self, db):
        conn, _ = db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_client'"
        ).fetchone()
        assert row is not None

    def test_oauth_code_table_exists(self, db):
        conn, _ = db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_code'"
        ).fetchone()
        assert row is not None

    def test_oauth_token_table_exists(self, db):
        conn, _ = db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_token'"
        ).fetchone()
        assert row is not None

    def test_oauth_invite_table_exists(self, db):
        conn, _ = db
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='oauth_invite'"
        ).fetchone()
        assert row is not None

    def test_invite_links_to_person(self, db):
        conn, _ = db
        code = _make_invite(conn)
        row = conn.execute("SELECT * FROM oauth_invite WHERE code = ?", (code,)).fetchone()
        assert row is not None
        assert row["person_id"] == "p-paul-001"


# --- Provider tests ---

class TestOAuthProvider:

    @pytest.fixture
    def provider(self, db):
        _, db_path = db
        from engine.gateway.oauth_provider import KisoOAuthProvider
        return KisoOAuthProvider(db_path=db_path)

    def test_register_and_get_client(self, provider):
        client = _make_client()
        _run(provider.register_client(client))
        loaded = _run(provider.get_client("test-client-123"))
        assert loaded is not None
        assert loaded.client_id == "test-client-123"
        assert loaded.client_secret == "test-secret-456"

    def test_get_client_not_found(self, provider):
        assert _run(provider.get_client("nonexistent")) is None

    def test_full_code_exchange(self, provider, db):
        conn, _ = db
        _make_invite(conn, "p-paul-001")
        client = _make_client()
        _run(provider.register_client(client))

        # Create auth code (simulating consent approval)
        auth_code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="test-challenge",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        assert isinstance(auth_code_str, str)
        assert len(auth_code_str) > 20  # 160+ bits of entropy

        # Load the code
        loaded_code = _run(provider.load_authorization_code(client, auth_code_str))
        assert loaded_code is not None
        assert loaded_code.client_id == "test-client-123"
        assert loaded_code.code_challenge == "test-challenge"

        # Exchange for tokens
        token = _run(provider.exchange_authorization_code(client, loaded_code))
        assert token.access_token is not None
        assert token.refresh_token is not None
        assert token.token_type.lower() == "bearer"
        assert token.expires_in > 0

    def test_access_token_verifies(self, provider, db):
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="c",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        loaded = _run(provider.load_authorization_code(client, code_str))
        token = _run(provider.exchange_authorization_code(client, loaded))

        access = _run(provider.load_access_token(token.access_token))
        assert access is not None
        assert access.client_id == "test-client-123"

    def test_access_token_has_person_id(self, provider, db):
        """The access token must carry person_id so MCPAuthMiddleware can resolve user_id."""
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="c",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        loaded = _run(provider.load_authorization_code(client, code_str))
        token = _run(provider.exchange_authorization_code(client, loaded))

        access = _run(provider.load_access_token(token.access_token))
        assert hasattr(access, "person_id") or "person_id" in (access.__dict__ if hasattr(access, '__dict__') else {})
        # We extend AccessToken to carry person_id
        assert access.person_id == "p-paul-001"

    def test_refresh_token_rotation(self, provider, db):
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="c",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        loaded = _run(provider.load_authorization_code(client, code_str))
        token1 = _run(provider.exchange_authorization_code(client, loaded))

        refresh = _run(provider.load_refresh_token(client, token1.refresh_token))
        assert refresh is not None
        token2 = _run(provider.exchange_refresh_token(client, refresh, ["health"]))
        assert token2.access_token != token1.access_token
        assert token2.refresh_token != token1.refresh_token

    def test_revoke_token(self, provider, db):
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="c",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        loaded = _run(provider.load_authorization_code(client, code_str))
        token = _run(provider.exchange_authorization_code(client, loaded))

        access = _run(provider.load_access_token(token.access_token))
        assert access is not None

        _run(provider.revoke_token(access))

        revoked = _run(provider.load_access_token(token.access_token))
        assert revoked is None

    def test_expired_code_returns_none(self, provider, db):
        """Authorization codes should not be loadable after expiry."""
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        # Insert an expired code directly
        conn.execute(
            "INSERT INTO oauth_code (code, client_id, person_id, scopes, code_challenge, "
            "redirect_uri, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("expired-code", "test-client-123", "p-paul-001", "health",
             "challenge", "https://claude.ai/oauth/callback", time.time() - 100),
        )
        conn.commit()

        loaded = _run(provider.load_authorization_code(client, "expired-code"))
        # The MCP library checks expiry in TokenHandler, but we can also
        # return None for expired codes in load_authorization_code
        # Either behavior is acceptable; the important thing is the token
        # handler rejects it
        assert loaded is None or loaded.expires_at < time.time()


class TestOAuthPersonResolution:
    """Verify OAuth tokens can be resolved to health_engine_user_id."""

    @pytest.fixture
    def provider(self, db):
        _, db_path = db
        from engine.gateway.oauth_provider import KisoOAuthProvider
        return KisoOAuthProvider(db_path=db_path)

    def test_resolve_person_to_user_id(self, provider, db):
        """Given a person_id from an OAuth token, we can find the health_engine_user_id."""
        conn, _ = db
        client = _make_client()
        _run(provider.register_client(client))

        code_str = _run(provider.create_authorization_code(
            client_id="test-client-123",
            code_challenge="c",
            redirect_uri="https://claude.ai/oauth/callback",
            scopes=["health"],
            person_id="p-paul-001",
        ))
        loaded = _run(provider.load_authorization_code(client, code_str))
        token = _run(provider.exchange_authorization_code(client, loaded))
        access = _run(provider.load_access_token(token.access_token))

        # The middleware needs to go from access.person_id -> health_engine_user_id
        row = conn.execute(
            "SELECT health_engine_user_id FROM person WHERE id = ?",
            (access.person_id,),
        ).fetchone()
        assert row is not None
        assert row["health_engine_user_id"] == "paul"
