import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from app.config import settings


class RateLimiter(ABC):
    @abstractmethod
    def is_allowed(self, user_id: str) -> bool:
        """Returns True and consumes one unit of quota, or False if over the limit."""

    @abstractmethod
    def remaining(self, user_id: str) -> int:
        """Quota left in the current window, for surfacing to clients/headers."""


class InMemoryRateLimiter(RateLimiter):
    """Fixed-window counter per user. Fine for a single process; not shared across workers."""

    def __init__(self, limit: int, window_seconds: int = 3600) -> None:
        self.limit = limit
        self.window = window_seconds
        self._lock = threading.Lock()
        self._counters: Dict[str, Tuple[int, float]] = {}  # user_id -> (count, window_start)

    def _current(self, user_id: str) -> Tuple[int, float]:
        now = time.time()
        count, start = self._counters.get(user_id, (0, now))
        if now - start >= self.window:
            count, start = 0, now
        return count, start

    def is_allowed(self, user_id: str) -> bool:
        with self._lock:
            count, start = self._current(user_id)
            if count >= self.limit:
                self._counters[user_id] = (count, start)
                return False
            self._counters[user_id] = (count + 1, start)
            return True

    def remaining(self, user_id: str) -> int:
        with self._lock:
            count, _ = self._current(user_id)
            return max(0, self.limit - count)


class RedisRateLimiter(RateLimiter):
    """
    Fixed-window counter using INCR + EXPIRE. Shared correctly across every
    API process, which an in-memory limiter cannot do once you scale out.
    """

    def __init__(self, redis_client, limit: int, window_seconds: int = 3600) -> None:
        self.r = redis_client
        self.limit = limit
        self.window = window_seconds

    def _key(self, user_id: str) -> str:
        return f"notif:ratelimit:{user_id}"

    def is_allowed(self, user_id: str) -> bool:
        key = self._key(user_id)
        count = self.r.incr(key)
        if count == 1:
            self.r.expire(key, self.window)
        return count <= self.limit

    def remaining(self, user_id: str) -> int:
        raw = self.r.get(self._key(user_id))
        count = int(raw) if raw else 0
        return max(0, self.limit - count)


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is not None:
        return _rate_limiter

    if settings.queue_backend == "redis":
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        _rate_limiter = RedisRateLimiter(client, settings.rate_limit_per_hour)
    else:
        _rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_hour)
    return _rate_limiter


def reset_rate_limiter_for_tests(limiter: Optional[RateLimiter] = None) -> None:
    """Test-only helper: swap in a fresh/custom limiter."""
    global _rate_limiter
    _rate_limiter = limiter
