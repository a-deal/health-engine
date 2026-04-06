"""Tests for engagement state tracking.

The scheduler must back off based on user engagement:
- active (<48h since last reply): full schedule
- drifting (2-5 days): morning only, skip evening
- cold (5-14 days): skip all scheduled sends
- gone (14+ days or never replied): full stop

Source of truth: conversation_message table, role='user' rows.
"""

from datetime import datetime, timedelta, timezone

import pytest

from engine.gateway.db import init_db, get_db, close_db


@pytest.fixture
def engagement_db(tmp_path, monkeypatch):
    """Fresh DB with conversation_message table and person table."""
    close_db()
    monkeypatch.setattr("engine.gateway.scheduler.PROJECT_ROOT", tmp_path, raising=False)

    db_path = tmp_path / "data" / "kasane.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(str(db_path))
    db = get_db(str(db_path))

    yield db
    close_db()


def _insert_message(db, user_id, role, content, hours_ago):
    """Insert a conversation_message at a given number of hours ago."""
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    db.execute(
        "INSERT INTO conversation_message "
        "(user_id, role, content, sender_name, channel, session_key, timestamp, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, role, content, "test", "whatsapp", "sess", ts, ts),
    )
    db.commit()


class TestEngagementState:
    """_engagement_state returns correct state based on last user reply."""

    def test_active_recent_reply(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "andrew", "user", "morning check-in", hours_ago=12)
        _insert_message(engagement_db, "andrew", "assistant", "Looking good!", hours_ago=11)

        state = _engagement_state(engagement_db, "andrew")
        assert state["state"] == "active"
        assert state["last_reply_hours"] < 24

    def test_drifting_2_to_5_days(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "paul", "user", "logged eggs", hours_ago=72)
        _insert_message(engagement_db, "paul", "assistant", "Nice!", hours_ago=71)
        # 3 outbound since reply
        _insert_message(engagement_db, "paul", "assistant", "Morning brief", hours_ago=48)
        _insert_message(engagement_db, "paul", "assistant", "Evening checkin", hours_ago=36)
        _insert_message(engagement_db, "paul", "assistant", "Morning brief", hours_ago=24)

        state = _engagement_state(engagement_db, "paul")
        assert state["state"] == "drifting"
        assert state["messages_since_reply"] == 4  # includes the immediate reply + 3 scheduled

    def test_cold_5_to_14_days(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "grigoriy", "user", "wrong timezone", hours_ago=168)
        # 10 outbound since
        for i in range(10):
            _insert_message(engagement_db, "grigoriy", "assistant", f"msg {i}", hours_ago=160 - i * 12)

        state = _engagement_state(engagement_db, "grigoriy")
        assert state["state"] == "cold"
        assert state["messages_since_reply"] == 10

    def test_gone_14_plus_days(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "dean", "user", "hello", hours_ago=400)

        state = _engagement_state(engagement_db, "dean")
        assert state["state"] == "gone"

    def test_never_replied(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        # Only outbound messages, user never sent anything
        _insert_message(engagement_db, "manny", "assistant", "Welcome!", hours_ago=100)
        _insert_message(engagement_db, "manny", "assistant", "How are you?", hours_ago=72)

        state = _engagement_state(engagement_db, "manny")
        assert state["state"] == "gone"
        assert state["last_reply_hours"] is None
        assert state["messages_since_reply"] == 2

    def test_no_messages_at_all(self, engagement_db):
        from engine.gateway.scheduler import _engagement_state

        state = _engagement_state(engagement_db, "nobody")
        assert state["state"] == "gone"
        assert state["last_reply_hours"] is None
        assert state["messages_since_reply"] == 0


class TestSchedulerEngagementGate:
    """_run_schedule respects engagement state and skips/reduces sends."""

    def test_cold_user_skipped(self, engagement_db, monkeypatch):
        """A cold user should be skipped for morning and evening."""
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "grigoriy", "user", "hi", hours_ago=168)

        state = _engagement_state(engagement_db, "grigoriy")
        assert state["state"] == "cold"

    def test_drifting_user_skips_evening(self, engagement_db):
        """A drifting user should skip evening check-ins."""
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "paul", "user", "logged food", hours_ago=72)

        state = _engagement_state(engagement_db, "paul")
        assert state["state"] == "drifting"


class TestCheckEngagementMCP:
    """The check_engagement MCP tool returns engagement state."""

    def test_single_user(self, engagement_db, monkeypatch):
        from engine.gateway.scheduler import _engagement_state

        _insert_message(engagement_db, "andrew", "user", "check-in", hours_ago=6)

        state = _engagement_state(engagement_db, "andrew")
        assert state["state"] == "active"
        assert "last_reply_hours" in state
        assert "messages_since_reply" in state
