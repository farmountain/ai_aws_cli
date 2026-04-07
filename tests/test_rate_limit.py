"""Tests for the token-bucket rate limiter."""

from __future__ import annotations

import pytest

from src.aaws.rate_limit import RateLimiter


class FakeClock:
    """Deterministic clock for testing."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def monotonic(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# ── Token consumption ─────────────────────────────────────────────────────────


class TestTokenConsumption:
    def test_first_request_allowed(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=5, _clock=clock)
        allowed, retry_after = rl.try_acquire()
        assert allowed is True
        assert retry_after == 0.0

    def test_burst_capacity_consumed(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        for _ in range(3):
            allowed, _ = rl.try_acquire()
            assert allowed is True

    def test_exhausted_after_burst(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        for _ in range(3):
            rl.try_acquire()
        allowed, retry_after = rl.try_acquire()
        assert allowed is False
        assert retry_after > 0


# ── Token refill ──────────────────────────────────────────────────────────────


class TestTokenRefill:
    def test_tokens_refill_over_time(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        # Exhaust all tokens
        for _ in range(3):
            rl.try_acquire()
        # Advance 1 second → 1 token refilled (60/60 = 1/s)
        clock.advance(1.0)
        allowed, _ = rl.try_acquire()
        assert allowed is True

    def test_tokens_capped_at_burst(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        # Advance a long time — tokens should cap at burst
        clock.advance(100.0)
        for i in range(3):
            allowed, _ = rl.try_acquire()
            assert allowed is True, f"request {i+1} should be allowed"
        allowed, _ = rl.try_acquire()
        assert allowed is False

    def test_retry_after_is_accurate(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=1, _clock=clock)
        rl.try_acquire()  # consume the 1 token
        _, retry_after = rl.try_acquire()
        # Need 1 token at 1/s rate → ~1 second
        assert pytest.approx(retry_after, abs=0.1) == 1.0

    def test_partial_refill(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=120, burst=2, _clock=clock)
        # Exhaust all tokens
        rl.try_acquire()
        rl.try_acquire()
        # Advance 0.5s → 1 token (120/60 = 2/s, 0.5s * 2 = 1)
        clock.advance(0.5)
        allowed, _ = rl.try_acquire()
        assert allowed is True


# ── Burst behavior ────────────────────────────────────────────────────────────


class TestBurst:
    def test_rapid_burst_of_five(self) -> None:
        """Spec scenario: 5 rapid requests with burst=5 all succeed."""
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=20, burst=5, _clock=clock)
        results = [rl.try_acquire()[0] for _ in range(5)]
        assert all(results)

    def test_sixth_rapid_request_throttled(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=20, burst=5, _clock=clock)
        for _ in range(5):
            rl.try_acquire()
        allowed, retry_after = rl.try_acquire()
        assert allowed is False
        assert retry_after > 0


# ── Disabled mode ─────────────────────────────────────────────────────────────


class TestDisabled:
    def test_disabled_always_allows(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=1, burst=1, enabled=False, _clock=clock)
        # Should allow unlimited requests even with tiny limits
        for _ in range(100):
            allowed, retry_after = rl.try_acquire()
            assert allowed is True
            assert retry_after == 0.0


# ── New session resets budget ─────────────────────────────────────────────────


class TestSessionReset:
    def test_new_instance_has_full_burst(self) -> None:
        clock = FakeClock()
        rl = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        # Exhaust
        for _ in range(3):
            rl.try_acquire()
        allowed, _ = rl.try_acquire()
        assert allowed is False

        # New instance = fresh budget
        rl2 = RateLimiter(max_per_minute=60, burst=3, _clock=clock)
        for _ in range(3):
            allowed, _ = rl2.try_acquire()
            assert allowed is True
