## MODIFIED Requirements

### Requirement: Session mode starts an interactive REPL
The system SHALL provide a `session` subcommand that launches an interactive REPL. The REPL SHALL display a header showing the active AWS profile and region, accept natural language input at a prompt, process each request through the full pipeline (NL → command → safety gate → execute → format output), maintain the conversation history in-process for the duration of the session, and enforce rate limiting on LLM translation requests before each `translate()` call.

#### Scenario: Session mode launches REPL
- **WHEN** the user runs `aaws session`
- **THEN** a Rich header panel is displayed showing profile and region
- **THEN** an `[aaws]>` prompt is displayed
- **THEN** the user can enter natural language requests

#### Scenario: Session context enables pronoun resolution
- **WHEN** the user lists EC2 instances and then asks "show details about the t3.micro one"
- **THEN** the system includes the previous command and its output in the LLM context
- **THEN** the LLM resolves "the t3.micro one" to the correct instance ID

#### Scenario: Throttled request shows feedback and re-prompts
- **WHEN** the user enters a request that exceeds the rate limit
- **THEN** the system displays a throttle message with seconds remaining
- **THEN** the REPL re-prompts without calling the LLM provider
