## ADDED Requirements

### Requirement: LLM provider is configurable via config file and environment variables
The system SHALL read LLM provider configuration from `~/.config/aaws/config.yaml` (Linux/macOS) or `%APPDATA%\aaws\config.yaml` (Windows). All settings SHALL be overridable via environment variables with the `AAWS_` prefix. Environment variables take precedence over file-based config.

#### Scenario: Provider loaded from config file
- **WHEN** `config.yaml` contains `llm.provider: openai` and `llm.model: gpt-4o-mini`
- **THEN** the system uses the OpenAI provider with the gpt-4o-mini model

#### Scenario: Environment variable overrides config file
- **WHEN** `config.yaml` sets `llm.provider: bedrock` and `AAWS_LLM_PROVIDER=openai` is set
- **THEN** the system uses the OpenAI provider

### Requirement: AWS Bedrock is the default LLM provider
The system SHALL use AWS Bedrock with `anthropic.claude-3-5-haiku-20241022-v1:0` as the default LLM provider when no provider is configured. Bedrock SHALL use the active AWS profile credentials (same as all other AWS operations).

#### Scenario: Default provider requires no extra credentials
- **WHEN** `config.yaml` does not specify a provider and `~/.aws/credentials` is configured
- **THEN** the system uses Bedrock with the active AWS profile without requiring a separate API key

#### Scenario: Bedrock access denied surfaces actionable error
- **WHEN** Bedrock returns `AccessDeniedException` for the configured model
- **THEN** the system displays: "Model access not enabled. Go to AWS Console → Bedrock → Model access to enable `<model>`."

### Requirement: OpenAI provider is supported with API key authentication
The system SHALL support OpenAI as an LLM provider when `llm.provider: openai` is configured. The API key SHALL be read from `llm.api_key` in config (supports `${ENV_VAR}` syntax) or from the `OPENAI_API_KEY` environment variable.

#### Scenario: OpenAI API key from environment variable
- **WHEN** `config.yaml` sets `llm.api_key: ${OPENAI_API_KEY}` and the env var is set
- **THEN** the system resolves the env var reference and uses it as the API key

#### Scenario: Missing OpenAI API key surfaces clear error
- **WHEN** `llm.provider: openai` is configured but no API key is available
- **THEN** the system displays: "OpenAI API key not found. Set OPENAI_API_KEY or configure llm.api_key in config."

### Requirement: LLM calls use structured output via tool/function calling
The system SHALL invoke the LLM using the provider's tool/function calling API to guarantee a structured response schema: `{ command, explanation, risk_tier, clarification }`. The system SHALL NOT rely on free-form text prompting for parsing the command.

#### Scenario: Structured response is parsed directly
- **WHEN** the LLM responds via tool call with the defined schema
- **THEN** the system extracts `command`, `explanation`, `risk_tier`, and `clarification` directly without string parsing

#### Scenario: Fallback for providers without tool calling
- **WHEN** the configured provider does not support tool calling
- **THEN** the system falls back to JSON-in-prompt mode and strips markdown code fences before parsing

### Requirement: LLM temperature is set to 0.1 by default
The system SHALL use a temperature of 0.1 for all LLM calls to maximize command determinism. Temperature SHALL be configurable via `llm.temperature` in config.

#### Scenario: Low temperature produces consistent output
- **WHEN** the same NL input is submitted multiple times
- **THEN** the LLM produces the same command on each invocation (within model non-determinism bounds)

### Requirement: First-run config initializes interactively
The system SHALL detect when no config file exists and run a first-run wizard that prompts the user to select a provider and enter required credentials, then write the config file.

#### Scenario: First run without config
- **WHEN** `aaws` is invoked for the first time with no config file present
- **THEN** the system prompts: "No configuration found. Run `aaws config init` to set up."
