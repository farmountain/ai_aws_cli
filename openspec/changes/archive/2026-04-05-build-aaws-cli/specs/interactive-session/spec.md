## ADDED Requirements

### Requirement: Single invocations are stateless
The system SHALL treat each `aaws "<request>"` invocation as independent, with no shared state or memory between calls. Each call SHALL include only the current AWS profile/region as context.

#### Scenario: Pronoun resolution fails gracefully in one-shot mode
- **WHEN** the user runs `aaws "stop that instance"` with no prior session
- **THEN** the LLM returns a clarification request ("Which instance? Please provide the instance ID.")
- **THEN** the system displays the clarification and exits without executing

### Requirement: Session mode starts an interactive REPL
The system SHALL provide a `session` subcommand that launches an interactive REPL. The REPL SHALL display a header showing the active AWS profile and region, accept natural language input at a prompt, process each request through the full pipeline (NL → command → safety gate → execute → format output), and maintain the conversation history in-process for the duration of the session.

#### Scenario: Session mode launches REPL
- **WHEN** the user runs `aaws session`
- **THEN** a Rich header panel is displayed showing profile and region
- **THEN** an `[aaws]>` prompt is displayed
- **THEN** the user can enter natural language requests

#### Scenario: Session context enables pronoun resolution
- **WHEN** the user lists EC2 instances and then asks "show details about the t3.micro one"
- **THEN** the system includes the previous command and its output in the LLM context
- **THEN** the LLM resolves "the t3.micro one" to the correct instance ID

### Requirement: Session terminates cleanly on exit
The system SHALL exit the session REPL when the user types `exit`, `quit`, or presses `Ctrl+C`. All in-process session state is discarded on exit.

#### Scenario: Exit command terminates session
- **WHEN** the user types `exit` at the `[aaws]>` prompt
- **THEN** the REPL exits cleanly with no error

#### Scenario: Ctrl+C terminates session
- **WHEN** the user presses `Ctrl+C` during the session
- **THEN** the REPL exits with a goodbye message and no stack trace

### Requirement: Session context window is bounded
The system SHALL retain at most the last 10 command/response pairs in the in-process session context sent to the LLM. Older history is dropped (not persisted) to avoid exceeding context window limits.

#### Scenario: Old history is not sent to LLM
- **WHEN** the session has processed more than 10 exchanges
- **THEN** only the 10 most recent exchanges are included in the LLM context
- **THEN** no history is written to disk
