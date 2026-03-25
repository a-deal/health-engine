"""Generate a daily family summary for a person's health data.

Queries the SQLite database for habits, check-ins, and health metrics,
then returns a structured summary suitable for email or MCP tool response.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "kasane.db"


def _get_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Get a read-only connection to the Kasane database."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def generate_family_summary(
    person_id: str,
    db_path: Path = DB_PATH,
) -> dict:
    """Generate a structured summary of a person's habits and health data.

    Returns a dict with:
        person_name: str
        person_id: str
        generated_at: str (ISO timestamp)
        habits: list of habit dicts with check-in status
        streak_days: int (consecutive days with at least one check-in)
        recent_notes: list of note strings from last 24 hours
        health_data: dict or None
        summary_text: str (formatted plain text for email)
    """
    conn = _get_db(db_path)
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Get person
    person = conn.execute(
        "SELECT * FROM person WHERE id = ? AND deleted_at IS NULL",
        (person_id,),
    ).fetchone()
    if not person:
        conn.close()
        return {"error": f"Person not found: {person_id}"}

    person_name = person["name"]

    # Get all habits (active + graduated, not deleted)
    habits_rows = conn.execute(
        "SELECT * FROM habit WHERE person_id = ? AND deleted_at IS NULL ORDER BY sort_order",
        (person_id,),
    ).fetchall()

    habit_summaries = []
    all_checkin_dates = set()
    recent_notes = []

    for h in habits_rows:
        habit_id = h["id"]
        title = h["title"]
        state = h["state"]
        emoji = h["emoji"] or ""
        graduated_at = h["graduated_at"]

        # Get check-ins for this habit in the last 7 days
        checkins = conn.execute(
            "SELECT * FROM check_in WHERE habit_id = ? AND deleted_at IS NULL "
            "AND date >= ? ORDER BY date DESC",
            (habit_id, week_ago),
        ).fetchall()

        # Track dates for streak calculation
        for ci in checkins:
            if ci["completed"]:
                all_checkin_dates.add(ci["date"])

        # Find most recent check-in
        last_checkin = None
        last_checkin_date = None
        for ci in checkins:
            if ci["completed"]:
                last_checkin_date = ci["date"]
                last_checkin = ci
                break

        # Determine status text
        if last_checkin_date == today:
            status = "checked in today"
        elif last_checkin_date == yesterday:
            status = "checked in yesterday"
        elif last_checkin_date:
            days_ago = (datetime.now() - datetime.strptime(last_checkin_date, "%Y-%m-%d")).days
            status = f"last check-in {days_ago} days ago"
        else:
            if state == "graduated":
                status = "practicing (no recent check-in)"
            else:
                status = "no check-in this week"

        # Add state info for graduated habits
        if state == "graduated" and graduated_at:
            status += f" (graduated {graduated_at})"

        # Collect notes from last 24 hours
        for ci in checkins:
            if ci["note"] and ci["date"] >= yesterday:
                recent_notes.append(f"{title}: {ci['note']}")

        habit_summaries.append({
            "title": title,
            "emoji": emoji,
            "state": state,
            "status": status,
            "last_checkin_date": last_checkin_date,
        })

    # Calculate streak (consecutive days with at least one check-in, counting back from today)
    streak = 0
    check_date = datetime.now()
    for _ in range(30):  # look back up to 30 days
        date_str = check_date.strftime("%Y-%m-%d")
        if date_str in all_checkin_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Check for health measurements
    health_rows = conn.execute(
        "SELECT type_identifier, value, unit, date FROM health_measurement "
        "WHERE person_id = ? AND deleted_at IS NULL ORDER BY date DESC LIMIT 10",
        (person_id,),
    ).fetchall()

    health_data = None
    if health_rows:
        health_data = [
            {
                "type": r["type_identifier"],
                "value": r["value"],
                "unit": r["unit"],
                "date": r["date"],
            }
            for r in health_rows
        ]

    # Check for workout records
    workout_rows = conn.execute(
        "SELECT workout_type, duration, calories, date FROM workout_record "
        "WHERE person_id = ? AND deleted_at IS NULL AND date >= ? ORDER BY date DESC",
        (person_id, week_ago),
    ).fetchall()

    workouts = None
    if workout_rows:
        workouts = [
            {
                "type": r["workout_type"],
                "duration_min": round(r["duration"] / 60, 1) if r["duration"] else None,
                "calories": r["calories"],
                "date": r["date"],
            }
            for r in workout_rows
        ]

    conn.close()

    result = {
        "person_name": person_name,
        "person_id": person_id,
        "generated_at": datetime.now().isoformat(),
        "habits": habit_summaries,
        "streak_days": streak,
        "recent_notes": recent_notes,
        "health_data": health_data,
        "workouts": workouts,
    }

    # Generate formatted text
    result["summary_text"] = _format_summary_text(result)

    return result


def _format_summary_text(data: dict) -> str:
    """Format the summary dict into plain text for email body."""
    lines = []

    # Habits section
    lines.append("HABITS")
    if data["habits"]:
        for h in data["habits"]:
            emoji = f"{h['emoji']} " if h["emoji"] else "  "
            lines.append(f"  {emoji}{h['title']}: {h['status']}")
    else:
        lines.append("  No habits tracked yet.")

    lines.append("")

    # Streak
    if data["streak_days"] > 0:
        day_word = "day" if data["streak_days"] == 1 else "days"
        lines.append(f"STREAK: {data['streak_days']} {day_word} active")
    else:
        lines.append("STREAK: No recent activity")

    lines.append("")

    # Notes
    lines.append("NOTES")
    if data["recent_notes"]:
        for note in data["recent_notes"]:
            lines.append(f"  {note}")
    else:
        lines.append("  No notes in the last 24 hours.")

    lines.append("")

    # Workouts
    if data["workouts"]:
        lines.append("WORKOUTS (last 7 days)")
        for w in data["workouts"]:
            duration_str = f" ({w['duration_min']} min)" if w["duration_min"] else ""
            lines.append(f"  {w['date']}: {w['type']}{duration_str}")
        lines.append("")

    # Health data
    lines.append("HEALTH DATA")
    if data["health_data"]:
        for m in data["health_data"][:5]:  # show last 5
            lines.append(f"  {m['type']}: {m['value']} {m['unit'] or ''} ({m['date']})")
    else:
        lines.append("  No wearable connected yet.")

    return "\n".join(lines)


def format_email(
    summary: dict,
    recipient_name: str,
    person_name: str,
) -> tuple[str, str]:
    """Format the summary into an email subject and body.

    Returns (subject, body) tuple.
    """
    today_str = datetime.now().strftime("%B %d")
    subject = f"{person_name} - Daily Summary ({today_str})"

    body_lines = [
        f"Hey {recipient_name},",
        "",
        f"Here's how {person_name} is doing:",
        "",
        summary["summary_text"],
        "",
        "This summary is generated daily. Reply to this email if you have questions.",
        "",
        "Milo",
        "Your Health Coach at Baseline",
    ]

    return subject, "\n".join(body_lines)


def format_email_html(
    summary: dict,
    recipient_name: str,
    person_name: str,
) -> tuple[str, str, str]:
    """Format the summary into subject, plain text body, and HTML body.

    Returns (subject, text_body, html_body) tuple.
    """
    subject, text_body = format_email(summary, recipient_name, person_name)
    today_str = datetime.now().strftime("%B %d")

    # Build habits HTML
    habits_html = ""
    for h in summary.get("habits", []):
        emoji = h.get("emoji", "")
        title = h["title"]
        status = h["status"]

        if "checked in today" in status or "checked in yesterday" in status:
            color = "#2d6a4f"
            bg = "#f2f8f5"
        elif "practicing" in status:
            color = "#b8860b"
            bg = "#fef9ef"
        else:
            color = "#78716c"
            bg = "#f9f8f6"

        habits_html += f"""
        <tr>
          <td style="padding: 12px 16px; border-bottom: 1px solid #f3f0eb;">
            <span style="font-size: 18px; margin-right: 8px;">{emoji}</span>
            <span style="font-weight: 500; color: #1c1917;">{title}</span>
          </td>
          <td style="padding: 12px 16px; border-bottom: 1px solid #f3f0eb; text-align: right;">
            <span style="font-size: 13px; color: {color}; background: {bg}; padding: 4px 10px; border-radius: 6px;">{status}</span>
          </td>
        </tr>"""

    # Streak
    if summary["streak_days"] > 0:
        day_word = "day" if summary["streak_days"] == 1 else "days"
        streak_html = f'<span style="font-weight: 700; color: #2d6a4f; font-size: 24px;">{summary["streak_days"]}</span> <span style="color: #78716c;">{day_word} active</span>'
    else:
        streak_html = '<span style="color: #78716c;">No recent activity</span>'

    # Notes
    notes_html = ""
    if summary["recent_notes"]:
        for note in summary["recent_notes"]:
            notes_html += f'<p style="margin: 4px 0; font-size: 14px; color: #1c1917; padding: 8px 12px; background: #fef9ef; border-radius: 6px;">{note}</p>'
    else:
        notes_html = '<p style="margin: 0; font-size: 14px; color: #a8a29e;">No notes in the last 24 hours.</p>'

    # Health data
    health_html = ""
    if summary["health_data"]:
        for m in summary["health_data"][:5]:
            health_html += f'<p style="margin: 4px 0; font-size: 14px; color: #1c1917;">{m["type"]}: {m["value"]} {m["unit"] or ""} <span style="color: #a8a29e;">({m["date"]})</span></p>'
    else:
        health_html = '<p style="margin: 0; font-size: 14px; color: #a8a29e;">No wearable connected yet.</p>'

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 20px; background: #faf9f6;">

      <p style="font-size: 13px; color: #b8860b; letter-spacing: 1px; text-transform: uppercase; margin: 0 0 8px 0;">Daily Summary</p>
      <h1 style="font-size: 28px; font-weight: 600; color: #1c1917; margin: 0 0 4px 0;">{person_name}</h1>
      <p style="font-size: 14px; color: #a8a29e; margin: 0 0 32px 0;">{today_str}</p>

      <p style="font-size: 15px; color: #1c1917; margin: 0 0 24px 0;">Hey {recipient_name},</p>

      <div style="background: #ffffff; border-radius: 12px; overflow: hidden; margin-bottom: 24px; border: 1px solid #f3f0eb;">
        <div style="padding: 12px 16px; background: #f9f8f6; border-bottom: 1px solid #f3f0eb;">
          <span style="font-size: 12px; font-weight: 600; color: #78716c; letter-spacing: 0.5px; text-transform: uppercase;">Habits</span>
        </div>
        <table style="width: 100%; border-collapse: collapse;">
          {habits_html}
        </table>
      </div>

      <div style="display: flex; gap: 16px; margin-bottom: 24px;">
        <div style="background: #ffffff; border-radius: 12px; padding: 16px 20px; flex: 1; border: 1px solid #f3f0eb;">
          <p style="font-size: 11px; font-weight: 600; color: #78716c; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 8px 0;">Streak</p>
          <p style="margin: 0;">{streak_html}</p>
        </div>
      </div>

      <div style="background: #ffffff; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; border: 1px solid #f3f0eb;">
        <p style="font-size: 11px; font-weight: 600; color: #78716c; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 8px 0;">Notes</p>
        {notes_html}
      </div>

      <div style="background: #ffffff; border-radius: 12px; padding: 16px 20px; margin-bottom: 32px; border: 1px solid #f3f0eb;">
        <p style="font-size: 11px; font-weight: 600; color: #78716c; letter-spacing: 0.5px; text-transform: uppercase; margin: 0 0 8px 0;">Health Data</p>
        {health_html}
      </div>

      <p style="font-size: 13px; color: #a8a29e; margin: 0 0 4px 0;">This summary is generated daily.</p>
      <p style="font-size: 13px; color: #a8a29e; margin: 0 0 24px 0;">Reply to this email if you have questions.</p>

      <p style="font-size: 14px; color: #1c1917; margin: 0;">Milo</p>
      <p style="font-size: 13px; color: #a8a29e; margin: 0;">Your Health Coach at Baseline</p>
    </div>"""

    return subject, text_body, html_body
