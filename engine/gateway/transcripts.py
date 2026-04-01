"""Transcript viewer for OpenClaw agent sessions.

Reads JSONL session files from OpenClaw's sessions directory, parses messages,
and serves them as JSON API + HTML viewer.

Endpoints:
  GET /api/transcripts  — JSON: filtered session messages
  GET /transcripts      — HTML: mobile-friendly conversation viewer
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import yaml
from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("health-engine.transcripts")

# Default OpenClaw sessions directory
_DEFAULT_SESSIONS_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
_DEFAULT_USERS_YAML = os.path.expanduser("~/.openclaw/workspace/users.yaml")


def _load_users_map() -> dict[str, str]:
    """Load phone/user_id → name mapping from SQLite (canonical) with yaml fallback."""
    mapping = {}

    # Primary: SQLite
    try:
        from .db import get_active_users
        for u in get_active_users():
            name = u["name"]
            if u["phone"]:
                mapping[u["phone"]] = name
                clean = u["phone"].replace("+", "").replace(" ", "").replace("-", "")
                mapping[clean] = name
            if u["user_id"]:
                mapping[u["user_id"]] = name
            if u["channel_target"]:
                mapping[u["channel_target"]] = name
        if mapping:
            return mapping
    except Exception:
        pass

    # Fallback: users.yaml (for when DB isn't initialized)
    path = Path(_DEFAULT_USERS_YAML)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        users = data.get("users", data)
        for key, info in users.items():
            if isinstance(info, dict):
                name = info.get("name", key)
                clean = key.replace("+", "").replace(" ", "").replace("-", "")
                mapping[clean] = name
                mapping[key] = name
                uid = info.get("user_id", "")
                if uid:
                    mapping[uid] = name
        return mapping
    except Exception:
        return {}


def _parse_session_file(path: Path, users_map: dict) -> dict | None:
    """Parse an OpenClaw JSONL session file into structured messages.

    OpenClaw format: each line is a JSON object with a "type" field.
    - type=session: metadata (id, timestamp)
    - type=message: contains message.role and message.content
    - type=tool_result, model_change, etc.: skip
    """
    messages = []
    session_id = path.stem
    session_started = ""
    user_name = "Unknown"

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                timestamp = entry.get("timestamp", "")

                # Session metadata
                if entry_type == "session":
                    session_id = entry.get("id", path.stem)
                    session_started = timestamp
                    continue

                # Messages
                if entry_type != "message":
                    continue

                msg_data = entry.get("message", {})
                role = msg_data.get("role", "")
                content = msg_data.get("content", "")

                # Extract text from multipart content
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    content = "\n".join(text_parts)
                elif not isinstance(content, str):
                    content = str(content) if content else ""

                if not content or not role:
                    continue

                # Only show user/assistant text, skip system/tool
                if role in ("user", "assistant"):
                    # Try to identify user from message content (phone numbers)
                    if role == "user" and user_name == "Unknown":
                        for phone, name in users_map.items():
                            if phone in content:
                                user_name = name
                                break

                    messages.append({
                        "timestamp": timestamp,
                        "role": role,
                        "text": content[:5000],
                    })

    except Exception as e:
        logger.warning(f"Failed to parse {path}: {e}")
        return None

    if not messages:
        return None

    # Try to identify user from filename
    if user_name == "Unknown":
        stem = path.stem
        for phone, name in users_map.items():
            if phone in stem:
                user_name = name
                break

    if not session_started:
        session_started = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    return {
        "id": session_id,
        "started": session_started,
        "user": user_name,
        "file": path.name,
        "message_count": len(messages),
        "messages": messages,
    }


def _get_sessions_dir(config) -> Path:
    """Get sessions directory from config or default."""
    if config.sessions_dir:
        return Path(os.path.expanduser(config.sessions_dir))
    return Path(_DEFAULT_SESSIONS_DIR)


async def transcripts_api(
    request: Request,
    token: str = Query(...),
    user: str | None = None,
    date: str | None = None,
    limit: int = 50,
):
    """JSON API: list transcript sessions with messages."""
    config = request.app.state.config
    if not config.api_token or token != config.api_token:
        raise HTTPException(403, "Invalid token")

    sessions_dir = _get_sessions_dir(config)
    if not sessions_dir.exists():
        return JSONResponse({"sessions": [], "error": f"Sessions dir not found: {sessions_dir}"})

    users_map = _load_users_map()
    sessions = []

    # Collect all JSONL files
    files = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    for path in files[:limit * 2]:  # Read more than limit since some may be filtered out
        session = _parse_session_file(path, users_map)
        if session is None:
            continue

        # Filter by user
        if user and user.lower() not in session["user"].lower():
            continue

        # Filter by date
        if date:
            session_date = session.get("started", "")[:10]
            if session_date != date:
                # Also check file mtime
                file_date = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
                if file_date != date:
                    continue

        sessions.append(session)
        if len(sessions) >= limit:
            break

    return JSONResponse({"sessions": sessions, "count": len(sessions)})


async def transcripts_html(
    request: Request,
    token: str = Query(...),
    user: str | None = None,
    date: str | None = None,
):
    """HTML viewer: mobile-friendly conversation bubbles."""
    config = request.app.state.config
    if not config.api_token or token != config.api_token:
        return HTMLResponse(_error_html("Invalid or missing token."), status_code=403)

    # Build the API URL for JavaScript to fetch
    base_params = f"token={token}"
    if user:
        base_params += f"&user={user}"
    if date:
        base_params += f"&date={date}"

    return HTMLResponse(_viewer_html(base_params, token))


def _error_html(message: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Transcripts</title>
<style>
  body {{ font-family: system-ui; background: #09090b; color: #ef4444;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  .card {{ background: #111113; border: 1px solid #27272a; border-radius: 16px;
           padding: 40px; max-width: 400px; text-align: center; }}
</style></head>
<body><div class="card"><h2>Error</h2><p>{message}</p></div></body></html>"""


def _viewer_html(api_params: str, token: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Milo Transcripts</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
  *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'DM Sans', sans-serif;
    background: #09090b; color: #fafafa;
    min-height: 100vh; padding: 16px;
  }}
  .header {{
    display: flex; align-items: center; gap: 12px;
    padding: 12px 0; margin-bottom: 12px;
    border-bottom: 1px solid #27272a;
  }}
  .header h1 {{ font-size: 1.1rem; font-weight: 600; }}
  .filters {{
    display: flex; gap: 8px; flex-wrap: wrap;
    margin-bottom: 16px;
  }}
  .filters input, .filters select {{
    padding: 8px 12px; background: #18181b; border: 1px solid #27272a;
    border-radius: 8px; color: #fafafa; font-family: inherit; font-size: 0.85rem;
  }}
  .filters input:focus, .filters select:focus {{ border-color: #3b82f6; outline: none; }}
  .session {{
    background: #111113; border: 1px solid #27272a; border-radius: 12px;
    margin-bottom: 12px; overflow: hidden;
  }}
  .session-header {{
    padding: 12px 16px; cursor: pointer; display: flex;
    justify-content: space-between; align-items: center;
    border-bottom: 1px solid transparent;
  }}
  .session-header:hover {{ background: #18181b; }}
  .session-header.open {{ border-bottom-color: #27272a; }}
  .session-meta {{ font-size: 0.8rem; color: #71717a; }}
  .session-user {{ font-weight: 600; font-size: 0.9rem; }}
  .messages {{ padding: 12px 16px; display: none; }}
  .messages.open {{ display: block; }}
  .msg {{
    margin-bottom: 10px; padding: 10px 14px;
    border-radius: 12px; max-width: 85%;
    font-size: 0.85rem; line-height: 1.5;
    white-space: pre-wrap; word-break: break-word;
  }}
  .msg.user {{
    background: #1e3a5f; margin-left: auto;
    border-bottom-right-radius: 4px;
  }}
  .msg.assistant {{
    background: #1a1a2e;
    border-bottom-left-radius: 4px;
  }}
  .msg-time {{
    font-size: 0.65rem; color: #52525b;
    margin-top: 4px;
  }}
  .empty {{
    text-align: center; color: #71717a; padding: 40px;
    font-size: 0.9rem;
  }}
  .count {{ font-size: 0.75rem; color: #52525b; }}
  .badge {{
    display: inline-block; padding: 2px 8px;
    background: #27272a; border-radius: 10px;
    font-size: 0.7rem; color: #a1a1aa;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>Milo Transcripts</h1>
  </div>
  <div class="filters">
    <input type="date" id="dateFilter" placeholder="Date">
    <input type="text" id="userFilter" placeholder="User name..." value="">
    <button onclick="loadTranscripts()" style="padding:8px 16px;background:#3b82f6;border:none;border-radius:8px;color:#fff;cursor:pointer;font-family:inherit;">Load</button>
  </div>
  <div id="sessions"></div>

<script>
const TOKEN = '{token}';

async function loadTranscripts() {{
  const date = document.getElementById('dateFilter').value;
  const user = document.getElementById('userFilter').value;
  let url = `/api/transcripts?token=${{TOKEN}}&limit=30`;
  if (date) url += `&date=${{date}}`;
  if (user) url += `&user=${{encodeURIComponent(user)}}`;

  const container = document.getElementById('sessions');
  container.innerHTML = '<div class="empty">Loading...</div>';

  try {{
    const resp = await fetch(url);
    const data = await resp.json();

    if (!data.sessions || data.sessions.length === 0) {{
      container.innerHTML = '<div class="empty">No transcripts found.</div>';
      return;
    }}

    container.innerHTML = data.sessions.map((s, i) => `
      <div class="session">
        <div class="session-header" onclick="toggleSession(${{i}})">
          <div>
            <span class="session-user">${{s.user}}</span>
            <span class="badge">${{s.message_count}} msgs</span>
          </div>
          <div class="session-meta">${{formatDate(s.started)}}</div>
        </div>
        <div class="messages" id="msgs-${{i}}">
          ${{s.messages.map(m => `
            <div class="msg ${{m.role}}">
              ${{escapeHtml(m.text)}}
              <div class="msg-time">${{formatTime(m.timestamp)}}</div>
            </div>
          `).join('')}}
        </div>
      </div>
    `).join('');
  }} catch (e) {{
    container.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`;
  }}
}}

function toggleSession(i) {{
  const msgs = document.getElementById(`msgs-${{i}}`);
  const header = msgs.previousElementSibling;
  msgs.classList.toggle('open');
  header.classList.toggle('open');
}}

function formatDate(ts) {{
  if (!ts) return '';
  try {{ return new Date(ts).toLocaleDateString('en-US', {{month:'short', day:'numeric', hour:'numeric', minute:'2-digit'}}); }}
  catch {{ return ts.slice(0, 16); }}
}}

function formatTime(ts) {{
  if (!ts) return '';
  try {{ return new Date(ts).toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit'}}); }}
  catch {{ return ts; }}
}}

function escapeHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

// Auto-load on page open
loadTranscripts();
</script>
</body>
</html>"""
