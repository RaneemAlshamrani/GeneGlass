"""Password hashing and JWT token utilities."""

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


def create_access_token(user_id: int) -> tuple[str, int]:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> int | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        return int(subject) if subject is not None else None
    except (InvalidTokenError, TypeError, ValueError):
        return None
