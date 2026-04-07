## Why

The interactive session mode (`aaws session`) currently has no rate limiting, meaning a user or automated script could send unlimited LLM translation requests in rapid succession. This creates risk of unexpected cloud costs (LLM API calls are billed per token), potential API throttling from the LLM provider, and no protection against runaway loops. Adding rate limiting provides cost guardrails and prevents accidental abuse.

## What Changes

- Add a configurable rate limiter to the session REPL loop that throttles requests per time window
- Introduce a new `session` config section with rate-limiting knobs (requests per minute, burst allowance)
- Display a clear message when a request is throttled, including time until the next request is allowed
- Track request timestamps in-memory (no disk persistence needed — resets on session restart)

## Capabilities

### New Capabilities
- `session-rate-limiting`: Token-bucket or sliding-window rate limiter for session mode requests, with configurable limits and user-facing throttle feedback

### Modified Capabilities
- `interactive-session`: Session REPL loop gains rate-limit enforcement before each translation call

## Impact

- **Code**: `src/aaws/session.py` (enforce rate limit), `src/aaws/config.py` (new `SessionConfig` model)
- **Config**: New optional `session.rate_limit` section in `config.yaml`
- **Dependencies**: None — pure Python stdlib implementation (no new packages)
- **APIs**: No external API changes; internal only
