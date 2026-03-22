"""Google Calendar integration — list, create, and search calendar events.

Requires: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
Auth: Run `python3 cli.py auth google-calendar` for one-time OAuth setup.
"""

from datetime import datetime, timezone
from pathlib import Path

from engine.gateway.token_store import TokenStore

SERVICE_NAME = "google_calendar"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TZ = "America/Los_Angeles"


class GoogleCalendarClient:
    """Wrapper around Google Calendar API with auto-refreshing tokens."""

    def __init__(self, user_id: str = "default", token_store: TokenStore | None = None):
        self.user_id = user_id
        self.store = token_store or TokenStore()
        self._service = None

    def _get_credentials(self):
        """Load credentials from token store, refresh if expired."""
        from google.oauth2.credentials import Credentials

        token_data = self.store.load_token(SERVICE_NAME, self.user_id)
        if not token_data:
            raise RuntimeError(
                f"No Google Calendar tokens found for user '{self.user_id}'. "
                "Run: python3 cli.py auth google-calendar"
            )

        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", SCOPES),
        )

        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            # Save refreshed tokens
            token_data["access_token"] = creds.token
            self.store.save_token(SERVICE_NAME, self.user_id, token_data)

        return creds

    def _get_service(self):
        """Build or return cached Calendar API service."""
        if self._service is None:
            from googleapiclient.discovery import build

            creds = self._get_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def list_events(
        self,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 10,
        query: str | None = None,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """List upcoming events from a calendar.

        Args:
            time_min: Start of time range (ISO 8601). Defaults to now.
            time_max: End of time range (ISO 8601). Optional.
            max_results: Max events to return (default 10).
            query: Free-text search filter.
            calendar_id: Calendar ID (default "primary").
        """
        service = self._get_service()

        if not time_min:
            time_min = datetime.now(timezone.utc).isoformat()
        else:
            time_min = _ensure_tz(time_min)

        kwargs = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeZone": DEFAULT_TZ,
        }
        if time_max:
            kwargs["timeMax"] = _ensure_tz(time_max)
        if query:
            kwargs["q"] = query

        result = service.events().list(**kwargs).execute()
        return [_format_event(e) for e in result.get("items", [])]

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str = "primary",
    ) -> dict:
        """Create a new calendar event.

        Args:
            summary: Event title.
            start: Start time (ISO 8601 datetime or YYYY-MM-DD for all-day).
            end: End time (ISO 8601 datetime or YYYY-MM-DD for all-day).
            description: Optional event description.
            location: Optional event location.
            calendar_id: Calendar ID (default "primary").
        """
        service = self._get_service()

        event_body = {
            "summary": summary,
            "start": _parse_time(start),
            "end": _parse_time(end),
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location

        created = service.events().insert(
            calendarId=calendar_id, body=event_body
        ).execute()
        return _format_event(created)

    def search_events(
        self,
        query: str,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 10,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Search events by text query. Wrapper around list_events with query."""
        return self.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
            query=query,
            calendar_id=calendar_id,
        )


def _parse_time(dt_str: str) -> dict:
    """Convert a datetime or date string to Google Calendar time format.

    Date-only (YYYY-MM-DD) → all-day event.
    Datetime (with T) → timed event in America/Los_Angeles.
    """
    if "T" in dt_str:
        return {"dateTime": dt_str, "timeZone": DEFAULT_TZ}
    else:
        return {"date": dt_str}


def _ensure_tz(dt_str: str) -> str:
    """Ensure a datetime string has timezone info for the API.

    If already has Z or offset, return as-is.
    If date-only, append T00:00:00.
    Otherwise append the default timezone offset.
    """
    if "T" not in dt_str:
        dt_str = dt_str + "T00:00:00"
    # If already has timezone info, return as-is
    if dt_str.endswith("Z") or "+" in dt_str[10:] or dt_str[10:].count("-") > 0:
        return dt_str
    # Append Z to let Google interpret with timeZone param
    return dt_str


def _format_event(event: dict) -> dict:
    """Flatten a Google Calendar event to a clean dict."""
    start = event.get("start", {})
    end = event.get("end", {})

    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(no title)"),
        "start": start.get("dateTime") or start.get("date", ""),
        "end": end.get("dateTime") or end.get("date", ""),
        "location": event.get("location", ""),
        "description": event.get("description", ""),
        "status": event.get("status", ""),
        "html_link": event.get("htmlLink", ""),
    }
