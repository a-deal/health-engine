"""CSV parse/write utilities."""

import csv
from pathlib import Path


def parse_csv(text: str) -> list[dict]:
    """Parse a CSV string into a list of dicts (matching JS parseCSV behavior)."""
    lines = text.strip().split("\n")
    if not lines:
        return []
    headers = [h.strip() for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = line.split(",")
        row = {}
        for i, h in enumerate(headers):
            row[h] = vals[i].strip() if i < len(vals) else ""
        rows.append(row)
    return rows


def read_csv(path: str | Path) -> list[dict]:
    """Read a CSV file into a list of dicts."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: list[dict], fieldnames: list[str] | None = None):
    """Write a list of dicts to a CSV file."""
    if not rows:
        return
    p = Path(path)
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(p, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
