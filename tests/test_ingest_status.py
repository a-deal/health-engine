"""Tests for get_ingest_status MCP tool."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from engine.gateway.config import GatewayConfig
from engine.gateway.server import create_app


@pytest.fixture
def setup_db(tmp_path):
    """Fresh SQLite database with schema, returns (db, tmp_path)."""
    os.environ.setdefault("GATEWAY_API_TOKEN", "test-token")
    (tmp_path / "data").mkdir(exist_ok=True)
    db_path = str(tmp_path / "data" / "kasane.db")
    from engine.gateway.db import init_db, get_db
    init_db(db_path)
    db = get_db(db_path)

    # Insert a test person
    db.execute(
        "INSERT INTO person (id, name, health_engine_user_id, channel, channel_target, timezone, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("p-andrew", "Andrew", "andrew", "whatsapp", "+1234", "America/Los_Angeles",
         "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    db.commit()
    return db, tmp_path


def _insert_wearable(db, person_id, date, source, rhr=None, hrv=None, sleep_hrs=None, steps=None):
    """Helper to insert a wearable_daily row."""
    import uuid
    rid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO wearable_daily (id, person_id, date, source, rhr, hrv, sleep_hrs, steps, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rid, person_id, date, source, rhr, hrv, sleep_hrs, steps, now, now),
    )
    db.commit()


class TestGetIngestStatus:

    def test_registered_in_tool_registry(self):
        from mcp_server.tools import TOOL_REGISTRY, _get_ingest_status
        assert "get_ingest_status" in TOOL_REGISTRY
        assert TOOL_REGISTRY["get_ingest_status"] is _get_ingest_status

    def test_no_data(self, setup_db):
        db, tmp_path = setup_db
        from mcp_server.tools import _get_ingest_status
        with patch("mcp_server.tools.PROJECT_ROOT", tmp_path):
            result = _get_ingest_status(user_id="andrew")
        assert result["has_data_today"] is False
        assert result["sources"] == {}

    def test_garmin_only_today(self, setup_db):
        db, tmp_path = setup_db
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        _insert_wearable(db, "p-andrew", today, "garmin", rhr=48.5, hrv=65.0, sleep_hrs=6.2, steps=5000)

        from mcp_server.tools import _get_ingest_status
        with patch("mcp_server.tools.PROJECT_ROOT", tmp_path):
            result = _get_ingest_status(user_id="andrew")

        assert result["has_data_today"] is True
        assert "garmin" in result["sources"]
        assert result["sources"]["garmin"]["last_date"] == today
        assert result["sources"]["garmin"]["metrics_today"] == ["hrv", "rhr", "sleep_hrs", "steps"]

    def test_apple_health_missing_today(self, setup_db):
        db, tmp_path = setup_db
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        # Garmin data today
        _insert_wearable(db, "p-andrew", today, "garmin", rhr=48.5, steps=5000)
        # Apple Health data only yesterday
        _insert_wearable(db, "p-andrew", yesterday, "apple_health", rhr=49.0, sleep_hrs=7.0)

        from mcp_server.tools import _get_ingest_status
        with patch("mcp_server.tools.PROJECT_ROOT", tmp_path):
            result = _get_ingest_status(user_id="andrew")

        assert result["has_data_today"] is True
        assert result["sources"]["garmin"]["last_date"] == today
        assert result["sources"]["apple_health"]["last_date"] == yesterday
        assert "apple_health" not in [s for s, v in result["sources"].items() if v["last_date"] == today]

    def test_multi_day_history(self, setup_db):
        db, tmp_path = setup_db
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for i in range(5):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            _insert_wearable(db, "p-andrew", d, "garmin", rhr=48.0 + i, steps=5000 + i * 100)

        from mcp_server.tools import _get_ingest_status
        with patch("mcp_server.tools.PROJECT_ROOT", tmp_path):
            result = _get_ingest_status(user_id="andrew")

        assert result["sources"]["garmin"]["days_with_data"] == 5
        assert result["sources"]["garmin"]["last_date"] == today

    def test_unknown_user(self, setup_db):
        db, tmp_path = setup_db
        from mcp_server.tools import _get_ingest_status
        with patch("mcp_server.tools.PROJECT_ROOT", tmp_path):
            result = _get_ingest_status(user_id="nobody")
        assert result["has_data_today"] is False
        assert "error" not in result
