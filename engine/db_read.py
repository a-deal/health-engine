"""SQLite read functions for health data.

Migration layer: reads from SQLite, falls back to CSV if SQLite
returns no data (for users who haven't been backfilled yet).
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine.utils.csv_io import read_csv

_DB_PATH = Path(__file__).parent.parent / "data" / "kasane.db"


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(str(_DB_PATH))
    db.row_factory = sqlite3.Row
    return db


def _person_id_for_user(user_id: str | None) -> str | None:
    """Map health-engine user_id to kasane person_id."""
    if not user_id or user_id == "default":
        return "andrew-deal-001"
    mapping = {
        "andrew": "andrew-deal-001",
        "grigoriy": "grigoriy-001",
    }
    return mapping.get(user_id, user_id)


def get_weights(user_id: str | None = None, data_dir: Path | None = None) -> list[dict]:
    """Return weight entries sorted by date. Falls back to CSV."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        rows = db.execute(
            "SELECT date, weight_lbs, source FROM weight_entry WHERE person_id = ? ORDER BY date",
            (pid,)
        ).fetchall()
        db.close()
        if rows:
            return [{"date": r["date"], "weight_lbs": str(r["weight_lbs"]), "source": r["source"] or ""} for r in rows]
    except Exception:
        pass
    # Fallback to CSV
    if data_dir:
        csv_path = data_dir / "weight_log.csv"
        if csv_path.exists():
            return read_csv(csv_path)
    return []


def get_bp(user_id: str | None = None, data_dir: Path | None = None) -> list[dict]:
    """Return BP entries sorted by date. Falls back to CSV."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        rows = db.execute(
            "SELECT date, systolic, diastolic, source FROM bp_entry WHERE person_id = ? ORDER BY date",
            (pid,)
        ).fetchall()
        db.close()
        if rows:
            return [{"date": r["date"], "systolic": str(r["systolic"]), "diastolic": str(r["diastolic"]), "source": r["source"] or ""} for r in rows]
    except Exception:
        pass
    if data_dir:
        csv_path = data_dir / "bp_log.csv"
        if csv_path.exists():
            return read_csv(csv_path)
    return []


def get_meals(user_id: str | None = None, date: str | None = None, days: int = 1, data_dir: Path | None = None) -> list[dict]:
    """Return meal entries. If date given, returns that date (+ days range). Falls back to CSV."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        if date:
            from datetime import timedelta
            start = date
            if days > 1:
                end_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=days - 1)
                end = end_dt.strftime("%Y-%m-%d")
            else:
                end = date
            rows = db.execute(
                "SELECT date, description, protein_g, carbs_g, fat_g, calories FROM meal_entry WHERE person_id = ? AND date BETWEEN ? AND ? ORDER BY date, meal_num",
                (pid, start, end)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT date, description, protein_g, carbs_g, fat_g, calories FROM meal_entry WHERE person_id = ? ORDER BY date, meal_num",
                (pid,)
            ).fetchall()
        db.close()
        if rows:
            return [{"date": r["date"], "description": r["description"], "protein_g": str(r["protein_g"] or ""), "carbs_g": str(r["carbs_g"] or ""), "fat_g": str(r["fat_g"] or ""), "calories": str(r["calories"] or "")} for r in rows]
    except Exception:
        pass
    if data_dir:
        csv_path = data_dir / "meal_log.csv"
        if csv_path.exists():
            all_rows = read_csv(csv_path)
            if date:
                return [r for r in all_rows if r.get("date") == date]
            return all_rows
    return []


def get_habits(user_id: str | None = None, date: str | None = None, data_dir: Path | None = None) -> list[dict]:
    """Return habit log entries. Falls back to CSV.
    
    Returns in 'long' format: [{date, habit_name, completed}, ...]
    """
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        if date:
            rows = db.execute(
                "SELECT date, habit_name, completed FROM habit_log WHERE person_id = ? AND date = ? ORDER BY date",
                (pid, date)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT date, habit_name, completed FROM habit_log WHERE person_id = ? ORDER BY date",
                (pid,)
            ).fetchall()
        db.close()
        if rows:
            return [{"date": r["date"], "habit": r["habit_name"], "completed": "y" if r["completed"] else "n"} for r in rows]
    except Exception:
        pass
    if data_dir:
        csv_path = data_dir / "daily_habits.csv"
        if csv_path.exists():
            return read_csv(csv_path)
    return []


def get_sleep(user_id: str | None = None, data_dir: Path | None = None) -> list[dict]:
    """Return sleep log entries. Falls back to CSV."""
    # Sleep log is manual entries only (not wearable). Check CSV first since
    # there's no dedicated sleep table yet — sleep comes from wearable_daily or manual CSV.
    if data_dir:
        csv_path = data_dir / "sleep_log.csv"
        if csv_path.exists():
            return read_csv(csv_path)
    return []


def get_wearable_daily(user_id: str | None = None, days: int = 7) -> list[dict]:
    """Return recent wearable daily summaries from SQLite."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        rows = db.execute(
            "SELECT * FROM wearable_daily WHERE person_id = ? ORDER BY date DESC LIMIT ?",
            (pid, days)
        ).fetchall()
        db.close()
        if rows:
            return [dict(r) for r in rows]
    except Exception:
        pass
    return []


def get_labs(user_id: str | None = None, data_dir: Path | None = None) -> dict:
    """Return lab results. Falls back to JSON file."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        draws = db.execute(
            "SELECT id, date, source FROM lab_draw WHERE person_id = ? ORDER BY date",
            (pid,)
        ).fetchall()
        if draws:
            result = {"draws": [], "latest": {}}
            for draw in draws:
                results = db.execute(
                    "SELECT marker, value, unit, reference_low, reference_high, flag FROM lab_result WHERE draw_id = ?",
                    (draw["id"],)
                ).fetchall()
                draw_data = {
                    "date": draw["date"],
                    "source": draw["source"],
                    "results": {r["marker"]: r["value"] for r in results},
                }
                result["draws"].append(draw_data)
                # Latest values
                for r in results:
                    result["latest"][r["marker"]] = r["value"]
            db.close()
            return result
    except Exception:
        pass
    db.close() if 'db' in dir() else None
    # Fallback to JSON
    if data_dir:
        lab_path = data_dir / "lab_results.json"
        if lab_path.exists():
            with open(lab_path) as f:
                return json.load(f)
    return {}


def get_strength(user_id: str | None = None, data_dir: Path | None = None) -> list[dict]:
    """Return strength log entries. Falls back to CSV."""
    pid = _person_id_for_user(user_id)
    try:
        db = _db()
        rows = db.execute(
            "SELECT s.date, s.exercise, s.weight_lbs, s.reps, s.rpe "
            "FROM strength_set s WHERE s.person_id = ? ORDER BY s.date",
            (pid,)
        ).fetchall()
        db.close()
        if rows:
            return [{"date": r["date"], "exercise": r["exercise"], "weight_lbs": str(r["weight_lbs"]), "reps": str(r["reps"]), "rpe": str(r["rpe"] or "")} for r in rows]
    except Exception:
        pass
    if data_dir:
        csv_path = data_dir / "strength_log.csv"
        if csv_path.exists():
            return read_csv(csv_path)
    return []
