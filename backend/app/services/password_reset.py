"""Persistent, hashed, single-use password-reset tokens for GeneGlass.

Only SHA-256 token digests and user IDs are stored in a separate local SQLite DB.
The reset link survives a backend reload; successful use removes the token.
"""

from __future__ import annotations


import hashlib
import secrets
import sqlite3
import time
from pathlib import Path

from app.core.config import get_settings

RESET_TTL_SECONDS = 15 * 60
REQUEST_COOLDOWN_SECONDS = 60


def _database_path() -> Path:
    db_dir = get_settings().database_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "password_reset_tokens.sqlite3"


def _connect():
    connection = sqlite3.connect(str(_database_path()), timeout=10)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS password_reset_tokens ("
        "token_hash TEXT PRIMARY KEY, "
        "user_id INTEGER NOT NULL, "
        "expires_at INTEGER NOT NULL, "
        "issued_at INTEGER NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS reset_tokens_by_user "
        "ON password_reset_tokens(user_id)"
    )
    return connection


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_reset_token(user_id: int) -> str | None:
    """Generate a token, limited to one request per user per 60 seconds."""
    now = int(time.time())
    with _connect() as connection:
        connection.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ?", (now,))
        latest = connection.execute(
            "SELECT MAX(issued_at) FROM password_reset_tokens WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if latest is not None and now - latest < REQUEST_COOLDOWN_SECONDS:
            return None

        token = secrets.token_urlsafe(32)
        # Issue only the newest link for this user.
        connection.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        connection.execute(
            "INSERT INTO password_reset_tokens(token_hash, user_id, expires_at, issued_at) "
            "VALUES (?, ?, ?, ?)",
            (_digest(token), user_id, now + RESET_TTL_SECONDS, now),
        )
    return token


def get_reset_token_user_id(token: str) -> int | None:
    """Check the token without spending it (needed for password validation)."""
    if not token or len(token) > 256:
        return None
    with _connect() as connection:
        result = connection.execute(
            "SELECT user_id, expires_at FROM password_reset_tokens WHERE token_hash = ?",
            (_digest(token),),
        ).fetchone()
    if result is None or result[1] <= int(time.time()):
        return None
    return result[0]


def consume_reset_token(token: str) -> int | None:
    """Atomically spend the token so it cannot be used twice."""
    if not token or len(token) > 256:
        return None
    now = int(time.time())
    with _connect() as connection:
        result = connection.execute(
            "SELECT user_id, expires_at FROM password_reset_tokens WHERE token_hash = ?",
            (_digest(token),),
        ).fetchone()
        connection.execute("DELETE FROM password_reset_tokens WHERE token_hash = ?", (_digest(token),))
        if result is None or result[1] <= now:
            return None
        # Revoke all previously issued links for the same account.
        connection.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (result[0],))
        return result[0]


def invalidate_reset_token(token: str) -> None:
    """Discard a link if SMTP delivery fails."""
    with _connect() as connection:
        connection.execute("DELETE FROM password_reset_tokens WHERE token_hash = ?", (_digest(token),))
