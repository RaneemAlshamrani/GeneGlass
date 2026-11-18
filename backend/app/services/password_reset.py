
"""Development password-reset token helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


# Temporary in-memory storage for development.
_reset_tokens: dict[str, tuple[int, datetime]] = {}


def create_reset_token(user_id: int) -> str:
    """Create a secure, single-use reset token valid for 15 minutes."""

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    _reset_tokens[token_hash] = (user_id, expires_at)

    return token


def consume_reset_token(token: str) -> int | None:
    """Validate and consume a reset token. Return its user ID if valid."""

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored_token = _reset_tokens.pop(token_hash, None)

    if stored_token is None:
        return None

    user_id, expires_at = stored_token

    if datetime.now(timezone.utc) >= expires_at:
        return None

    return user_id
