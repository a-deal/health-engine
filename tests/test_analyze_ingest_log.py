"""Tests for scripts/analyze_ingest_log.py.

The analysis script reads the JSONL ingest observability log written by
_ingest_health_snapshot and surfaces sparse-payload entries — the
diagnostic surface the 2026-03-25 Apple Health incident lacked.
"""

import json
import sys
from pathlib import Path

import pytest

# scripts/ is not a package; add it to sys.path to import the module
_REPO_ROOT = Path(__file__).parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import analyze_ingest_log  # noqa: E402


def _write_log(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _entry(ts: str, user_id: str, metric_count: int, keys: list[str] | None = None) -> dict:
    return {
        "ts": ts,
        "user_id": user_id,
        "metric_count": metric_count,
        "metric_keys": keys or [],
        "payload_timestamp": ts,
    }


class TestAnalyzeIngestLog:

    def test_flags_sparse_entries_below_threshold(self, tmp_path):
        log = tmp_path / "ingest_log.jsonl"
        _write_log(log, [
            _entry("2026-04-13T10:00:00", "paul", 1, ["resting_hr"]),
            _entry("2026-04-13T11:00:00", "andrew", 5,
                   ["resting_hr", "steps", "hrv_sdnn", "sleep_hours", "vo2_max"]),
            _entry("2026-04-13T12:00:00", "paul", 2, ["resting_hr", "steps"]),
        ])

        result = analyze_ingest_log.analyze(log, threshold=3)

        assert result["total_entries"] == 3
        assert result["sparse_count"] == 2
        assert result["sparse_users"] == {"paul": 2}
        assert "andrew" not in result["sparse_users"]

    def test_empty_log_returns_zeroes(self, tmp_path):
        log = tmp_path / "ingest_log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("")

        result = analyze_ingest_log.analyze(log, threshold=3)

        assert result["total_entries"] == 0
        assert result["sparse_count"] == 0
        assert result["sparse_users"] == {}

    def test_missing_log_file_returns_empty(self, tmp_path):
        log = tmp_path / "does_not_exist.jsonl"

        result = analyze_ingest_log.analyze(log, threshold=3)

        assert result["total_entries"] == 0
        assert result["sparse_count"] == 0
        assert result["sparse_users"] == {}

    def test_threshold_respected(self, tmp_path):
        log = tmp_path / "ingest_log.jsonl"
        _write_log(log, [
            _entry("2026-04-13T10:00:00", "a", 4),
            _entry("2026-04-13T11:00:00", "b", 5),
            _entry("2026-04-13T12:00:00", "c", 6),
        ])

        # At threshold=5, only metric_count<5 counts as sparse
        result_strict = analyze_ingest_log.analyze(log, threshold=5)
        assert result_strict["sparse_count"] == 1
        assert result_strict["sparse_users"] == {"a": 1}

        # At threshold=3, nothing counts as sparse
        result_loose = analyze_ingest_log.analyze(log, threshold=3)
        assert result_loose["sparse_count"] == 0

    def test_malformed_lines_skipped_not_fatal(self, tmp_path):
        """A garbled line in the log must not crash analysis — observability
        is best-effort and the script runs against live prod data."""
        log = tmp_path / "ingest_log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(
            json.dumps(_entry("2026-04-13T10:00:00", "paul", 1)) + "\n"
            + "this is not json\n"
            + json.dumps(_entry("2026-04-13T11:00:00", "paul", 2)) + "\n"
        )

        result = analyze_ingest_log.analyze(log, threshold=3)
        assert result["total_entries"] == 2  # garbled line skipped
        assert result["sparse_count"] == 2

    def test_reports_metric_key_frequency(self, tmp_path):
        """Analysis surfaces which metrics are most often present in sparse
        payloads — useful for diagnosing which HealthKit permission failed."""
        log = tmp_path / "ingest_log.jsonl"
        _write_log(log, [
            _entry("2026-04-13T10:00:00", "paul", 1, ["resting_hr"]),
            _entry("2026-04-13T11:00:00", "paul", 1, ["resting_hr"]),
            _entry("2026-04-13T12:00:00", "paul", 2, ["resting_hr", "steps"]),
        ])

        result = analyze_ingest_log.analyze(log, threshold=3)
        assert result["sparse_key_frequency"]["resting_hr"] == 3
        assert result["sparse_key_frequency"]["steps"] == 1
