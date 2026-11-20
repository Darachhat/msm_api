import math
import threading
import time
from collections import deque
from typing      import Deque, Dict, Tuple

from fastapi import HTTPException, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter for login brute-force protection."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts   = max_attempts
        self.window_seconds = window_seconds
        self._lock          = threading.Lock()
        self._attempts      : Dict[str, Deque[float]] = {}


    def _prune(self, bucket: Deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()


    def is_limited(self, key: str) -> Tuple[bool, int]:
        """Return (is_limited, retry_after_seconds) for a rate-limit key."""
        now = time.monotonic()
        with self._lock:
            bucket = self._attempts.get(key)
            if not bucket:
                return False, 0
            self._prune(bucket, now)
            if not bucket:
                del self._attempts[key]
                return False, 0
            if len(bucket) >= self.max_attempts:
                retry_after = max(1, math.ceil(self.window_seconds - (now - bucket[0])))
                return True, retry_after
            return False, 0


    def record_attempt(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._attempts.setdefault(key, deque())
            self._prune(bucket, now)
            bucket.append(now)


    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


    def enforce(self, keys: list[str]) -> None:
        """Raise HTTP 429 with Retry-After header if any key exceeds the sliding window limit."""
        max_retry = 0
        for key in keys:
            limited, retry_after = self.is_limited(key)
            if limited and retry_after > max_retry:
                max_retry = retry_after
        if max_retry > 0:
            raise HTTPException(
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
                , detail    = f"Too many login attempts. Please try again in {max_retry} seconds."
                , headers   = {"Retry-After": str(max_retry)}
            )


login_rate_limiter = SlidingWindowRateLimiter(
    max_attempts     = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    , window_seconds = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
)

forgot_password_rate_limiter = SlidingWindowRateLimiter(
    max_attempts     = 5
    , window_seconds = 900
)

register_rate_limiter = SlidingWindowRateLimiter(
    max_attempts     = 10
    , window_seconds = 900
)
