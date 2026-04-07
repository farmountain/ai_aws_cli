## 1. Configuration

- [x] 1.1 Add `RateLimitConfig` Pydantic model to `src/aaws/config.py` with fields: `enabled` (bool, default True), `max_per_minute` (int, default 20), `burst` (int, default 5)
- [x] 1.2 Add `SessionConfig` Pydantic model to `src/aaws/config.py` with field: `rate_limit` (RateLimitConfig)
- [x] 1.3 Add `session` field (SessionConfig) to `AawsConfig` model

## 2. Rate Limiter Implementation

- [x] 2.1 Create `src/aaws/rate_limit.py` with `RateLimiter` class implementing token-bucket algorithm using `time.monotonic()`
- [x] 2.2 Implement `try_acquire()` method returning `(allowed: bool, retry_after: float)` tuple
- [x] 2.3 Implement token refill logic at `max_per_minute / 60` tokens per second, capped at `burst`

## 3. Session Integration

- [x] 3.1 Import and instantiate `RateLimiter` in `src/aaws/session.py` `run_session()` using config values
- [x] 3.2 Add rate-limit check before `translate()` call in the REPL loop
- [x] 3.3 Display throttle message with seconds remaining when request is rate-limited

## 4. Tests

- [x] 4.1 Unit tests for `RateLimiter`: token consumption, refill, burst capacity, exhaustion
- [x] 4.2 Unit tests for `RateLimiter` with rate limiting disabled (always allows)
- [x] 4.3 Test config parsing with `session.rate_limit` section present and absent
- [x] 4.4 Integration test: session REPL skips `translate()` when rate-limited
