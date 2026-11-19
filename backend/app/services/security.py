"""Password hashing and JWT token utilities."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def session_stamp(user_id: int, password_hash: str) -> str:
    """Bind JWT sessions to the current stored password hash without exposing it."""
    secret = get_settings().jwt_secret_key.encode("utf-8")
    message = f"geneglass-session-v1:{user_id}:{password_hash}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def matches_session_stamp(user_id: int, password_hash: str | None, stamp: str) -> bool:
    """Invalidate previously issued JWTs when an account password changes."""
    if not password_hash:
        return False
    return hmac.compare_digest(session_stamp(user_id, password_hash), stamp)


def create_access_token(user_id: int, password_hash: str) -> tuple[str, int]:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "sv": session_stamp(user_id, password_hash),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> tuple[int, str] | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        stamp = payload.get("sv")
        if subject is None or not isinstance(stamp, str) or len(stamp) != 64:
            return None
        return int(subject), stamp
    except (InvalidTokenError, TypeError, ValueError):
        return None
