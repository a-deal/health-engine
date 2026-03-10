"""Date helper utilities."""

from datetime import datetime, date


def today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def fmt_date(date_str: str) -> str:
    """Format a date string as 'Mar 10' style."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%b %d").replace(" 0", " ")


def days_between(date1: str, date2: str) -> int:
    """Calculate days between two ISO date strings."""
    d1 = datetime.strptime(date1, "%Y-%m-%d")
    d2 = datetime.strptime(date2, "%Y-%m-%d")
    return abs((d2 - d1).days)
