"""Tests for the rate limiter (SE-003)."""
import time

import pytest

from ollama_console.rate_limiter import RateLimiter


class TestRateLimiter:
    """Unit tests for RateLimiter sliding-window logic."""

    def test_allows_requests_within_limit(self):
        limiter = RateLimiter(limit=5, window=60)
        for _ in range(5):
            allowed, remaining, reset = limiter.is_allowed("127.0.0.1")
            assert allowed is True
        assert remaining == 0

    def test_blocks_request_beyond_limit(self):
        limiter = RateLimiter(limit=3, window=60)
        for _ in range(3):
            limiter.is_allowed("127.0.0.1")
        allowed, remaining, reset = limiter.is_allowed("127.0.0.1")
        assert allowed is False
        assert remaining == 0
        assert reset > 0

    def test_different_ips_are_independent(self):
        limiter = RateLimiter(limit=2, window=60)
        limiter.is_allowed("1.1.1.1")
        limiter.is_allowed("1.1.1.1")
        # 1.1.1.1 is now at limit, but 2.2.2.2 should still be allowed
        blocked, _, _ = limiter.is_allowed("1.1.1.1")
        allowed, _, _ = limiter.is_allowed("2.2.2.2")
        assert blocked is False
        assert allowed is True

    def test_remaining_decrements_correctly(self):
        limiter = RateLimiter(limit=5, window=60)
        for expected_remaining in [4, 3, 2, 1, 0]:
            _, remaining, _ = limiter.is_allowed("127.0.0.1")
            assert remaining == expected_remaining

    def test_window_expiry_allows_new_requests(self):
        """Requests older than the window should be dropped."""
        limiter = RateLimiter(limit=2, window=1)  # 1-second window
        limiter.is_allowed("127.0.0.1")
        limiter.is_allowed("127.0.0.1")
        # Both slots used — should be blocked now
        blocked, _, _ = limiter.is_allowed("127.0.0.1")
        assert blocked is False

        # Wait for window to expire
        time.sleep(1.1)
        allowed, remaining, _ = limiter.is_allowed("127.0.0.1")
        assert allowed is True
        assert remaining == 1

    def test_reset_seconds_is_positive(self):
        limiter = RateLimiter(limit=1, window=60)
        limiter.is_allowed("127.0.0.1")
        _, _, reset = limiter.is_allowed("127.0.0.1")
        assert reset > 0

    def test_cleanup_removes_expired_entries(self):
        limiter = RateLimiter(limit=100, window=1)
        for i in range(5):
            limiter.is_allowed(f"10.0.0.{i}")
        time.sleep(1.1)
        # Force cleanup by lowering threshold
        limiter.cleanup(max_entries=1)
        assert len(limiter._buckets) == 0

    def test_thread_safety(self):
        """Concurrent requests from multiple threads should not raise."""
        import threading
        limiter = RateLimiter(limit=1000, window=60)
        errors = []

        def make_requests():
            try:
                for _ in range(50):
                    limiter.is_allowed("127.0.0.1")
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=make_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
