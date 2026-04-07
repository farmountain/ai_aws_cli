"""Token-bucket rate limiter for session mode."""

from __future__ import annotations

import time


class RateLimiter:
    """Token-bucket rate limiter.

    Allows up to `burst` requests immediately, then refills at
    `max_per_minute / 60` tokens per second.
    """

    def __init__(
        self,
        max_per_minute: int = 20,
        burst: int = 5,
        enabled: bool = True,
        _clock: object | None = None,
    ) -> None:
        self._enabled = enabled
        self._max_per_minute = max_per_minute
        self._burst = burst
        self._tokens = float(burst)
        self._clock = _clock or time
        self._last_refill: float = self._clock.monotonic()  # type: ignore[union-attr]

    def _refill(self) -> None:
        now: float = self._clock.monotonic()  # type: ignore[union-attr]
        elapsed = now - self._last_refill
        refill_rate = self._max_per_minute / 60.0
        self._tokens = min(self._burst, self._tokens + elapsed * refill_rate)
        self._last_refill = now

    def try_acquire(self) -> tuple[bool, float]:
        """Attempt to consume one token.

        Returns:
            (allowed, retry_after) — if allowed is False, retry_after
            is the number of seconds until the next token is available.
        """
        if not self._enabled:
            return True, 0.0

        self._refill()

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True, 0.0

        # How long until one token refills?
        refill_rate = self._max_per_minute / 60.0
        deficit = 1.0 - self._tokens
        retry_after = deficit / refill_rate if refill_rate > 0 else 0.0
        return False, retry_after
