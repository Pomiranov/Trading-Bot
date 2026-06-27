"""Per-user rate limiter to prevent API abuse and flood."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque


class RateLimiter:
    """Token bucket: max `limit` calls per `window_seconds` per user."""

    def __init__(self, limit: int = 30, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._calls: dict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        now = time.monotonic()
        calls = self._calls[user_id]
        cutoff = now - self._window
        while calls and calls[0] < cutoff:
            calls.popleft()
        if len(calls) >= self._limit:
            return False
        calls.append(now)
        return True

    def remaining(self, user_id: int) -> int:
        now = time.monotonic()
        calls = self._calls[user_id]
        cutoff = now - self._window
        active = sum(1 for t in calls if t >= cutoff)
        return max(0, self._limit - active)


rate_limiter = RateLimiter(limit=30, window_seconds=60.0)
