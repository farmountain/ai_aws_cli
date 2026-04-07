## Context

The `aaws session` command launches an interactive REPL (`src/aaws/session.py`) that translates natural language to AWS CLI commands via an LLM provider. Each user input triggers a `translate()` call, which makes an API call to Bedrock or OpenAI. There is currently no throttle on how frequently these calls can be made, exposing users to unbounded API costs and potential provider-side throttling.

Configuration lives in `src/aaws/config.py` as Pydantic models loaded from `~/.config/aaws/config.yaml`. The session module already imports config and uses it for audit settings.

## Goals / Non-Goals

**Goals:**
- Prevent runaway LLM API costs during interactive sessions
- Provide sensible defaults that don't interfere with normal human usage
- Give clear feedback when a request is throttled (time remaining)
- Make limits configurable via the existing config system

**Non-Goals:**
- Rate limiting single-shot CLI invocations (out of scope — each is independent)
- Persisting rate-limit state across sessions (in-memory only)
- Per-command or per-tier differentiated limits
- Server-side or distributed rate limiting

## Decisions

### 1. Token-bucket algorithm over sliding window

**Choice**: Token bucket with configurable capacity and refill rate.

**Rationale**: Token bucket is simpler to implement, allows natural bursting (e.g., a few rapid follow-ups), and needs only two state variables (tokens remaining, last refill timestamp). A sliding window requires storing individual request timestamps and is more complex for negligible benefit in a single-user REPL.

**Alternative considered**: Sliding window — more precise per-minute accounting but unnecessary complexity for a local CLI tool.

### 2. Configuration under `session.rate_limit` section

**Choice**: Add a new `SessionConfig` with nested `RateLimitConfig` to the config model.

```yaml
session:
  rate_limit:
    enabled: true
    max_per_minute: 20
    burst: 5
```

**Rationale**: Groups session-specific settings together. `max_per_minute` is intuitive. `burst` controls the token bucket capacity, defaulting to 5 to allow short bursts of follow-up queries. `enabled: true` by default — rate limiting should be opt-out, not opt-in.

**Alternative considered**: Flat top-level keys (`rate_limit_max`, etc.) — less organized, mixes concerns.

### 3. Pure in-memory implementation, no new dependencies

**Choice**: Implement a `RateLimiter` class in `src/aaws/session.py` (or a small `src/aaws/rate_limit.py` module) using `time.monotonic()`.

**Rationale**: The rate limiter is only needed during a running session. No persistence needed. `time.monotonic()` is immune to wall-clock adjustments. No external packages required.

### 4. Enforcement point: before `translate()` call

**Choice**: Check the rate limiter immediately before calling `translate()` in the REPL loop. If throttled, print a message and `continue` (skip to next prompt).

**Rationale**: This is the expensive operation (LLM API call). Checking before the call prevents wasted API spend. User still gets the prompt back immediately with feedback on when they can retry.

## Risks / Trade-offs

- **[Overly restrictive defaults]** → Default of 20/min with burst 5 should be generous for human typing speed. Users can increase or disable via config.
- **[No persistence across sessions]** → A user who restarts sessions rapidly gets a fresh budget each time. Acceptable trade-off — persisting state adds complexity for an edge case.
- **[Config migration]** → Existing configs without `session` section will use defaults (Pydantic handles this). No migration needed.
