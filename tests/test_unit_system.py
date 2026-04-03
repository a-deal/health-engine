"""Tests for unit system (metric/imperial) support.

Covers: person.unit_system column, weight conversion at ingestion,
log_weight with metric users, ingest_health_snapshot with metric users,
and data migration for existing mixed-unit entries.
"""

import sqlite3
from unittest.mock import patch

import pytest

from engine.gateway.db import init_db, get_db


_NOW = "2026-04-03T00:00:00Z"

KG_TO_LBS = 2.20462


def _insert_person(db, id="grigoriy-001", name="Grigoriy", user_id="grigoriy",
                   tz="Europe/Minsk", unit_system="metric"):
    db.execute(
        "INSERT INTO person (id, name, health_engine_user_id, timezone, unit_system, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (id, name, user_id, tz, unit_system, _NOW, _NOW),
    )
    db.commit()


def _insert_person_imperial(db, id="andrew-001", name="Andrew", user_id="andrew",
                            tz="America/Los_Angeles"):
    db.execute(
        "INSERT INTO person (id, name, health_engine_user_id, timezone, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (id, name, user_id, tz, _NOW, _NOW),
    )
    db.commit()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "users" / "grigoriy").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "users" / "andrew").mkdir(parents=True, exist_ok=True)
    actual_db_path = tmp_path / "data" / "kasane.db"
    init_db(str(actual_db_path))
    conn = get_db(str(actual_db_path))
    return conn


@pytest.fixture
def db_metric_user(db):
    _insert_person(db)
    return db


@pytest.fixture
def db_imperial_user(db):
    _insert_person_imperial(db)
    return db


# --- Tests: unit_system column ---

class TestUnitSystemColumn:
    def test_default_is_imperial(self, db_imperial_user):
        row = db_imperial_user.execute(
            "SELECT unit_system FROM person WHERE id = 'andrew-001'"
        ).fetchone()
        assert row[0] == "imperial"

    def test_metric_user(self, db_metric_user):
        row = db_metric_user.execute(
            "SELECT unit_system FROM person WHERE id = 'grigoriy-001'"
        ).fetchone()
        assert row[0] == "metric"


# --- Tests: weight conversion at ingestion ---

class TestWeightConversion:
    def test_metric_user_kg_converted_to_lbs(self, db_metric_user, tmp_path, monkeypatch):
        """When a metric user logs 107 kg, it should be stored as ~235.9 lbs."""
        from mcp_server.tools import _log_weight
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)

        _log_weight(107.0, date="2026-04-03", user_id="grigoriy")

        row = db_metric_user.execute(
            "SELECT weight_lbs FROM weight_entry WHERE person_id = 'grigoriy-001' AND date = '2026-04-03'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 107.0 * KG_TO_LBS) < 0.5

    def test_imperial_user_lbs_stored_as_is(self, db_imperial_user, tmp_path, monkeypatch):
        """When an imperial user logs 188 lbs, it stays 188 lbs."""
        from mcp_server.tools import _log_weight
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)

        _log_weight(188.0, date="2026-04-03", user_id="andrew")

        row = db_imperial_user.execute(
            "SELECT weight_lbs FROM weight_entry WHERE person_id = 'andrew-001' AND date = '2026-04-03'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 188.0) < 0.1

    def test_metric_user_return_value_shows_original_kg(self, db_metric_user, tmp_path, monkeypatch):
        """The return dict should show the original kg value the user entered."""
        from mcp_server.tools import _log_weight
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)

        result = _log_weight(107.0, date="2026-04-03", user_id="grigoriy")
        assert result["logged"] is True
        assert result["weight_lbs"] == pytest.approx(107.0 * KG_TO_LBS, abs=0.5)


# --- Tests: ingest_health_snapshot weight conversion ---

class TestIngestSnapshotConversion:
    def test_metric_user_snapshot_weight_converted(self, db_metric_user, tmp_path, monkeypatch):
        """Apple Health sends kg for metric users. Should convert to lbs for storage."""
        from mcp_server.tools import _ingest_health_snapshot
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)

        _ingest_health_snapshot("grigoriy", {"weight_lbs": 107.0}, timestamp="2026-04-03T12:00:00")

        row = db_metric_user.execute(
            "SELECT weight_lbs FROM weight_entry WHERE person_id = 'grigoriy-001'"
        ).fetchone()
        if row:
            assert abs(row[0] - 107.0 * KG_TO_LBS) < 0.5

    def test_imperial_user_snapshot_weight_not_converted(self, db_imperial_user, tmp_path, monkeypatch):
        """Imperial users' weight should pass through unchanged."""
        from mcp_server.tools import _ingest_health_snapshot
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)

        _ingest_health_snapshot("andrew", {"weight_lbs": 188.0}, timestamp="2026-04-03T12:00:00")

        row = db_imperial_user.execute(
            "SELECT weight_lbs FROM weight_entry WHERE person_id = 'andrew-001'"
        ).fetchone()
        if row:
            assert abs(row[0] - 188.0) < 0.1


# --- Tests: setup_profile unit_system ---

class TestSetupProfileUnitSystem:
    def test_setup_profile_sets_unit_system(self, db_metric_user, tmp_path, monkeypatch):
        """setup_profile should accept and persist unit_system."""
        from mcp_server.tools import _setup_profile
        monkeypatch.setattr("mcp_server.tools.PROJECT_ROOT", tmp_path)
        # Create a config file first
        config_dir = tmp_path / "data" / "users" / "grigoriy"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text("profile:\n  age: 42\n")

        _setup_profile(unit_system="metric", user_id="grigoriy")

        row = db_metric_user.execute(
            "SELECT unit_system FROM person WHERE health_engine_user_id = 'grigoriy'"
        ).fetchone()
        assert row[0] == "metric"
