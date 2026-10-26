from datetime import date

from repo_digest.guards import RateLimiter, TokenBudget, TTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_allows_up_to_limit_then_reports_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window=60, clock=clock)

    assert limiter.acquire("a") is None
    clock.now += 10
    assert limiter.acquire("a") is None
    clock.now += 10
    assert limiter.acquire("a") == 40  # the first request leaves the window in 40s
    assert limiter.acquire("b") is None  # other visitors are unaffected


def test_rate_limiter_window_slides() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window=60, clock=clock)
    assert limiter.acquire("a") is None
    clock.now += 60
    assert limiter.acquire("a") is None


def test_rejected_requests_do_not_extend_the_wait() -> None:
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window=60, clock=clock)
    limiter.acquire("a")
    for _ in range(5):
        clock.now += 10
        limiter.acquire("a")
    assert limiter.acquire("a") == 10


def test_cache_expires_entries() -> None:
    clock = FakeClock()
    cache = TTLCache[str, int](ttl=30, clock=clock)
    cache.set("k", 1)
    clock.now += 29
    assert cache.get("k") == 1
    clock.now += 1
    assert cache.get("k") is None


def test_cache_evicts_least_recently_used() -> None:
    cache = TTLCache[str, int](ttl=60, max_entries=2, clock=FakeClock())
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # a is now more recent than b
    cache.set("c", 3)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_token_budget_resets_each_day() -> None:
    day = [date(2026, 10, 26)]
    budget = TokenBudget(daily_limit=100, today=lambda: day[0])

    budget.charge(60)
    assert budget.has_room()
    budget.charge(40)
    assert not budget.has_room()

    day[0] = date(2026, 10, 27)
    assert budget.has_room()
    assert budget.used == 0
