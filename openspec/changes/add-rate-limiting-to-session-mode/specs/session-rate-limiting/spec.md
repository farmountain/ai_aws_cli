## ADDED Requirements

### Requirement: Session rate limiter enforces request frequency
The system SHALL implement a token-bucket rate limiter that limits the number of LLM translation requests per minute during an interactive session. The rate limiter SHALL be configurable via the `session.rate_limit` config section with `max_per_minute` (default: 20), `burst` (default: 5), and `enabled` (default: true) parameters.

#### Scenario: Request within budget succeeds normally
- **WHEN** the user enters a request and the rate limiter has available tokens
- **THEN** the request proceeds through the normal translation pipeline with no delay or message

#### Scenario: Request exceeding rate limit is throttled
- **WHEN** the user enters a request and the rate limiter has no available tokens
- **THEN** the system displays a message indicating the request was throttled and the number of seconds until the next request is allowed
- **THEN** the system returns to the prompt without calling the LLM provider

#### Scenario: Burst allows rapid follow-ups
- **WHEN** the user sends 5 requests in rapid succession at the start of a session (with default burst=5)
- **THEN** all 5 requests are processed without throttling
- **THEN** subsequent rapid requests are throttled until tokens refill

### Requirement: Rate limiter tokens refill over time
The system SHALL refill rate limiter tokens at a rate of `max_per_minute / 60` tokens per second, up to the `burst` capacity. The refill SHALL use monotonic time to avoid issues with wall-clock adjustments.

#### Scenario: Tokens refill after waiting
- **WHEN** the rate limiter has 0 tokens and 3 seconds elapse (with default max_per_minute=20)
- **THEN** approximately 1 token is available (20/60 * 3 = 1.0)
- **THEN** the next request proceeds without throttling

### Requirement: Rate limiter resets on session start
The system SHALL create a new rate limiter instance at the start of each session with full burst capacity. Rate limit state SHALL NOT persist across sessions.

#### Scenario: New session has full budget
- **WHEN** a user exits a session after exhausting the rate limit and starts a new session
- **THEN** the new session starts with full burst capacity available

### Requirement: Rate limiting can be disabled via config
The system SHALL allow rate limiting to be disabled by setting `session.rate_limit.enabled` to `false` in the configuration.

#### Scenario: Disabled rate limiter allows unlimited requests
- **WHEN** the config has `session.rate_limit.enabled: false`
- **THEN** no rate limiting is applied and all requests proceed immediately regardless of frequency
