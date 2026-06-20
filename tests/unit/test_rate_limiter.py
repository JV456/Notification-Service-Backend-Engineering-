from app.services.rate_limiter import InMemoryRateLimiter


def test_rate_limiter_allows_up_to_limit():
    limiter = InMemoryRateLimiter(limit=3, window_seconds=60)
    assert limiter.is_allowed("user1")
    assert limiter.is_allowed("user1")
    assert limiter.is_allowed("user1")
    assert not limiter.is_allowed("user1")


def test_rate_limiter_tracks_users_independently():
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60)
    assert limiter.is_allowed("a")
    assert limiter.is_allowed("b")
    assert not limiter.is_allowed("a")


def test_rate_limiter_remaining_decrements():
    limiter = InMemoryRateLimiter(limit=5, window_seconds=60)
    assert limiter.remaining("user1") == 5
    limiter.is_allowed("user1")
    assert limiter.remaining("user1") == 4
