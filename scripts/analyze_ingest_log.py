#!/usr/bin/env python3
"""Analyze the ingest observability log for sparse payloads.

Reads data/admin/ingest_log.jsonl (written by _ingest_health_snapshot for
every accepted ingest) and surfaces entries whose metric_count is below a
threshold — the diagnostic signal the 2026-03-25 Apple Health near-empty
payload incident lacked.

Usage:
    python3 scripts/analyze_ingest_log.py                 # default threshold=3
    python3 scripts/analyze_ingest_log.py --threshold 5
    python3 scripts/analyze_ingest_log.py --log path/to/ingest_log.jsonl

Programmatic use (also covered by tests/test_analyze_ingest_log.py):
    from analyze_ingest_log import analyze
    result = analyze(Path("data/admin/ingest_log.jsonl"), threshold=3)
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


DEFAULT_LOG_PATH = Path("data/admin/ingest_log.jsonl")
DEFAULT_THRESHOLD = 3


def analyze(log_path: Path, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """Parse the JSONL log and return summary stats.

    Returns a dict with:
      total_entries: int         — lines successfully parsed
      sparse_count: int          — entries with metric_count < threshold
      sparse_users: dict[str,int]— per-user count of sparse entries
      sparse_key_frequency: dict — which metric keys appear most in sparse entries
      sample_sparse: list        — up to 10 raw sparse entries for inspection

    Missing or empty files return zero-valued dicts. Malformed JSONL lines
    are skipped (observability must not crash analysis).
    """
    log_path = Path(log_path)
    if not log_path.exists():
        return _empty_result()

    total = 0
    sparse_users: Counter = Counter()
    key_freq: Counter = Counter()
    sample: list[dict] = []

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            mc = entry.get("metric_count", 0)
            if mc < threshold:
                user = entry.get("user_id", "<unknown>")
                sparse_users[user] += 1
                for k in entry.get("metric_keys", []):
                    key_freq[k] += 1
                if len(sample) < 10:
                    sample.append(entry)

    return {
        "total_entries": total,
        "sparse_count": sum(sparse_users.values()),
        "sparse_users": dict(sparse_users),
        "sparse_key_frequency": dict(key_freq),
        "sample_sparse": sample,
        "threshold": threshold,
    }


def _empty_result() -> dict:
    return {
        "total_entries": 0,
        "sparse_count": 0,
        "sparse_users": {},
        "sparse_key_frequency": {},
        "sample_sparse": [],
        "threshold": DEFAULT_THRESHOLD,
    }


def _format_report(result: dict) -> str:
    lines = [
        f"Ingest log analysis (threshold={result['threshold']}):",
        f"  Total entries:  {result['total_entries']}",
        f"  Sparse entries: {result['sparse_count']} (metric_count < {result['threshold']})",
    ]
    if result["sparse_users"]:
        lines.append("  Sparse by user:")
        for user, count in sorted(result["sparse_users"].items(), key=lambda x: -x[1]):
            lines.append(f"    {user}: {count}")
    if result["sparse_key_frequency"]:
        lines.append("  Metric keys present in sparse payloads (which HealthKit reads did succeed):")
        for key, count in sorted(result["sparse_key_frequency"].items(), key=lambda x: -x[1]):
            lines.append(f"    {key}: {count}")
    if result["sample_sparse"]:
        lines.append(f"  Sample sparse entries (first {len(result['sample_sparse'])}):")
        for entry in result["sample_sparse"]:
            lines.append(
                f"    {entry.get('ts', '?')}  user={entry.get('user_id', '?')}  "
                f"count={entry.get('metric_count', '?')}  keys={entry.get('metric_keys', [])}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH,
                        help=f"Path to ingest_log.jsonl (default: {DEFAULT_LOG_PATH})")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Sparse threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON instead of formatted report")
    args = parser.parse_args(argv)

    result = analyze(args.log, threshold=args.threshold)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
