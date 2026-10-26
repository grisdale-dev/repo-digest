"""Protections for the public demo: per-visitor rate limiting, a result cache, a daily token budget.

All three are in-memory and thread-safe, which is enough for a single-instance deployment.
State resets when the process restarts. That's acceptable here because the LLM account is
prepaid, so the most the demo can ever spend is the account balance.
"""

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Hashable
from datetime import UTC, date, datetime


class RateLimiter:
    """Sliding-window limit: at most `max_requests` per `window` seconds for each key."""

    def __init__(
        self, max_requests: int, window: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.max_requests = max_requests
        self.window = window
        self._clock = clock
        self._hits: dict[Hashable, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: Hashable) -> float | None:
        """Record a request. Returns None if allowed, else seconds until the next one is."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return hits[0] + self.window - now
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle visitors so memory stays bounded
                self._hits = {
                    k: v for k, v in self._hits.items() if v and v[-1] > now - self.window
                }
            return None


class TTLCache[K: Hashable, V]:
    """A small LRU cache whose entries expire after `ttl` seconds."""

    def __init__(
        self, ttl: float, max_entries: int = 500, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl = ttl
        self.max_entries = max_entries
        self._clock = clock
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= self._clock():
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._items[key] = (self._clock() + self.ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


class TokenBudget:
    """Caps LLM tokens per UTC day.

    Checked before each LLM call and charged after it. Concurrent requests can overshoot by
    at most one request's worth of tokens each, which is fine for a demo.
    """

    def __init__(self, daily_limit: int, today: Callable[[], date] | None = None) -> None:
        self.daily_limit = daily_limit
        self._today = today or (lambda: datetime.now(UTC).date())
        self._day = self._today()
        self._used = 0
        self._lock = threading.Lock()

    def _roll_over(self) -> None:
        today = self._today()
        if today != self._day:
            self._day, self._used = today, 0

    @property
    def used(self) -> int:
        with self._lock:
            self._roll_over()
            return self._used

    def has_room(self) -> bool:
        return self.used < self.daily_limit

    def charge(self, tokens: int) -> None:
        with self._lock:
            self._roll_over()
            self._used += tokens
