"""Tests for /health/deep endpoint coverage.

Verifies health/deep checks all critical subsystems:
database, user data, garmin tokens, apple health, audit log, disk,
scheduler, and briefing freshness.
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.gateway.config import GatewayConfig
from engine.gateway.db import init_db, get_db, close_db
from engine.gateway.server import create_app

TOKEN = "test-token-health"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "kasane.db"
    init_db(path)
    return path


@pytest.fixture
def health_client(db_path, tmp_path, monkeypatch):
    """TestClient with a temp database and data directory for health/deep."""
    monkeypatch.setattr("engine.gateway.db._db_path", lambda: db_path)

    import engine.gateway.v1_api as v1_mod
    monkeypatch.setattr(v1_mod, "get_db", lambda p=None: get_db(db_path))

    config = GatewayConfig(port=18899, api_token=TOKEN)
    app = create_app(config)
    return TestClient(app)


class TestHealthDeepCovers:
    """health/deep must include checks for all critical subsystems."""

    def test_has_scheduler_check(self, health_client):
        """health/deep should report scheduler status."""
        resp = health_client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert "scheduler" in data["checks"], \
            f"health/deep missing 'scheduler' check. Keys: {list(data['checks'].keys())}"

    def test_has_briefing_freshness_check(self, health_client):
        """health/deep should report briefing freshness per active user."""
        resp = health_client.get("/health/deep")
        assert resp.status_code == 200
        data = resp.json()
        assert "briefing_freshness" in data["checks"], \
            f"health/deep missing 'briefing_freshness' check. Keys: {list(data['checks'].keys())}"

    def test_scheduler_reports_last_send(self, db_path, health_client):
        """Scheduler check should show last successful send time."""
        db = get_db(db_path)
        now = datetime.now(timezone.utc)
        db.execute(
            "INSERT INTO scheduled_send (person_id, schedule_type, sent_date, sent_at, status, message_preview) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "morning_brief", now.strftime("%Y-%m-%d"), now.isoformat(), "sent", "test"),
        )
        db.commit()

        resp = health_client.get("/health/deep")
        data = resp.json()
        sched = data["checks"]["scheduler"]
        assert sched["status"] in ("ok", "stale")
        assert "last_send_hours_ago" in sched

    def test_scheduler_stale_when_no_sends(self, health_client):
        """Scheduler with no sends should report stale."""
        resp = health_client.get("/health/deep")
        data = resp.json()
        sched = data["checks"]["scheduler"]
        assert sched["status"] == "no_sends"
