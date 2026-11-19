"""Bounded, thread-safe login attempt limiter for a single API process.

Use a shared store or an API gateway limit before multi-worker/public deployment.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import deque


class LoginRateLimiter:
    """Atomic sliding-window limits by client address and login identifier."""

    def __init__(
        self,
        *,
        window_seconds: int = 600,
        per_ip: int = 60,
        per_account: int = 12,
        max_buckets: int = 12000,
    ) -> None:
        self.window_seconds = window_seconds
        self.per_ip = per_ip
        self.per_account = per_account
        self.max_buckets = max_buckets
        self._attempts: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._checks = 0

    def _discard_expired(self, key: tuple[str, str], now: float) -> None:
        attempts = self._attempts.get(key)
        if attempts is None:
            return
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            del self._attempts[key]

    def _cleanup_old_buckets(self, now: float) -> None:
        for key in list(self._attempts):
            self._discard_expired(key, now)
        if len(self._attempts) >= self.max_buckets:
            # Bounded memory even when clients try many distinct login names.
            excess = len(self._attempts) - self.max_buckets + 2
            oldest = sorted(self._attempts, key=lambda key: self._attempts[key][-1])
            for key in oldest[:max(0, excess)]:
                del self._attempts[key]

    def reserve(self, client_ip: str, login_identifier: str, *, now: float | None = None) -> int:
        """Reserve an attempt; return seconds to wait, or 0 if allowed.

        Counts *all* login submissions, including successful ones, so even a
        burst of concurrent wrong-password requests cannot exceed the limit.
        """
        now = time.monotonic() if now is None else now
        ip = (client_ip or "unknown")[:256]
        normalized = login_identifier.strip().casefold()
        account_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        keys_and_limits = ((('ip', ip), self.per_ip), (('account', account_key), self.per_account))

        with self._lock:
            self._checks += 1
            if self._checks % 128 == 0 or len(self._attempts) >= self.max_buckets - 2:
                self._cleanup_old_buckets(now)
            for key, _ in keys_and_limits:
                self._discard_expired(key, now)

            retry_seconds = 0
            for key, limit in keys_and_limits:
                attempts = self._attempts.get(key)
                if attempts and len(attempts) >= limit:
                    wait = math.ceil(attempts[0] + self.window_seconds - now)
                    retry_seconds = max(retry_seconds, max(1, wait))
            if retry_seconds:
                return retry_seconds

            for key, _ in keys_and_limits:
                self._attempts.setdefault(key, deque()).append(now)
            return 0


login_rate_limiter = LoginRateLimiter()


# Reuse the same thread-safe rate-limit implementation for reset endpoints.
# These counters are process-local; production requires shared/gateway limits.
forgot_password_rate_limiter = LoginRateLimiter(
    window_seconds=900,
    per_ip=15,
    per_account=6,
)
reset_password_rate_limiter = LoginRateLimiter(
    window_seconds=900,
    per_ip=30,
    per_account=10,
)

# Limit account-creation bursts and password-hashing workload.
register_rate_limiter = LoginRateLimiter(
    window_seconds=3600,
    per_ip=20,
    per_account=5,
)
