"""One-time OAuth flow for Google Calendar.

Usage:
    python3 cli.py auth google-calendar --secrets /path/to/client_secret.json
"""

from pathlib import Path

from engine.gateway.token_store import TokenStore
from engine.integrations.gcal import SCOPES, SERVICE_NAME


def run_auth_flow(
    client_secrets_path: str,
    user_id: str = "default",
    token_store: TokenStore | None = None,
) -> Path:
    """Run interactive OAuth flow and save tokens.

    Args:
        client_secrets_path: Path to Google OAuth client_secret.json.
        user_id: User identifier for multi-user support.
        token_store: Optional TokenStore instance.

    Returns:
        Path to the saved token directory.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets_path = Path(client_secrets_path)
    if not secrets_path.exists():
        raise FileNotFoundError(f"Client secrets file not found: {secrets_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)

    store = token_store or TokenStore()
    token_data = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }

    saved_dir = store.save_token(SERVICE_NAME, user_id, token_data)
    print(f"Google Calendar tokens saved to {saved_dir}")
    return saved_dir
