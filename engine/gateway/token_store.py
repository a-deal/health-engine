"""Unified token storage for wearable services.

Tokens are stored at:
  ~/.config/health-engine/tokens/<service>/<user_id>/

Garmin tokens stay in garth format (oauth1_token.json, oauth2_token.json)
for backward compatibility. Other services use a single token.json.

Tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC).
Key source: HE_TOKEN_KEY env var, or auto-generated at
~/.config/health-engine/token.key.
"""

import json
import os
from pathlib import Path


_BASE_DIR = Path(os.path.expanduser("~/.config/health-engine/tokens"))
_KEY_PATH = Path(os.path.expanduser("~/.config/health-engine/token.key"))


def _get_fernet():
    """Get a Fernet instance for token encryption/decryption.

    Returns None if cryptography is not installed (graceful degradation).
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None

    key_env = os.environ.get("HE_TOKEN_KEY")
    if key_env:
        return Fernet(key_env.encode() if isinstance(key_env, str) else key_env)

    if _KEY_PATH.exists():
        key = _KEY_PATH.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEY_PATH.write_bytes(key)
        os.chmod(_KEY_PATH, 0o600)
    return Fernet(key)


class TokenStore:
    """Manage wearable auth tokens per service and user."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else _BASE_DIR
        self._fernet = _get_fernet()

    def _token_dir(self, service: str, user_id: str) -> Path:
        return self.base_dir / service / user_id

    def save_token(self, service: str, user_id: str, data: dict) -> Path:
        """Save token data, encrypted at rest. Returns the directory path."""
        td = self._token_dir(service, user_id)
        td.mkdir(parents=True, exist_ok=True)
        token_path = td / "token.json"
        raw = json.dumps(data, indent=2).encode()
        if self._fernet:
            raw = self._fernet.encrypt(raw)
        with open(token_path, "wb") as f:
            f.write(raw)
        return td

    def load_token(self, service: str, user_id: str) -> dict | None:
        """Load token data, decrypting if encrypted. Returns None if not found.

        Backward compatible: if the file is plaintext JSON (no Fernet prefix),
        it is loaded as-is and re-saved encrypted on next write.
        """
        token_path = self._token_dir(service, user_id) / "token.json"
        if not token_path.exists():
            return None
        raw = token_path.read_bytes()
        if self._fernet and raw.startswith(b"gAAAAA"):
            # Fernet-encrypted token
            raw = self._fernet.decrypt(raw)
        data = json.loads(raw)
        return data

    def has_token(self, service: str, user_id: str) -> bool:
        """Check if tokens exist for a service/user combo."""
        td = self._token_dir(service, user_id)
        if not td.exists():
            return False
        # Garmin uses garth format (multiple files), others use token.json
        return any(td.iterdir())

    def garmin_token_dir(self, user_id: str = "default") -> Path:
        """Get the garth-compatible token directory for Garmin.

        Garmin tokens are stored as garth dumps (oauth1_token.json,
        oauth2_token.json) directly in the directory, not wrapped in
        a single token.json.
        """
        td = self._token_dir("garmin", user_id)
        td.mkdir(parents=True, exist_ok=True)
        return td
