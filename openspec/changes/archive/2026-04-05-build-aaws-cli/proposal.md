## Why

AWS CLI is powerful but requires exact syntax knowledge that creates friction — users waste time in docs looking up flags, misremember service names, and accidentally run destructive commands without understanding the impact. `aaws` removes that friction by letting users describe what they want in plain English, generating the correct AWS CLI command, explaining it, and gating dangerous operations behind explicit confirmation.

## What Changes

- New Python CLI package `aaws` published to PyPI (`pip install aaws`)
- Users invoke `aaws "<natural language>"` instead of memorizing exact CLI syntax
- Commands are shown before execution with explanation and risk level
- Destructive operations require confirmation; catastrophic ones are blocked by default
- Output is automatically formatted into readable tables and cards (raw JSON opt-in)
- `aaws session` provides an interactive REPL with conversational context
- `aaws explain "<command>"` explains any existing AWS CLI command
- LLM provider is configurable (Bedrock default, OpenAI supported)
- Configuration stored in OS-appropriate config directory with env var overrides

## Capabilities

### New Capabilities

- `nl-to-aws-command`: Translate natural language input to a valid `aws` CLI command string using an LLM, with structured output (command, explanation, risk tier, clarification request)
- `command-safety`: Classify commands by risk tier (0=read, 1=write, 2=destructive, 3=catastrophic), enforce confirmation gates per tier, and enforce read-only mode on protected AWS profiles
- `output-formatting`: Detect shape of AWS CLI JSON output and render as Rich tables, key-value cards, or syntax-highlighted JSON; passthrough `--raw` mode for scripting
- `interactive-session`: REPL mode (`aaws session`) with in-process conversation history for multi-turn refinement; stateless one-shot mode as default
- `llm-provider`: Pluggable LLM provider abstraction supporting AWS Bedrock (default) and OpenAI; structured output via tool/function calling; configuration via YAML file and env vars
- `error-recovery`: Pattern-match AWS CLI stderr for credential/permission/resource errors and feed back to LLM for plain-English interpretation and actionable next steps

### Modified Capabilities

## Impact

- New Python package: `aaws` (requires Python 3.11+, `aws` CLI installed)
- Runtime dependencies: `typer`, `rich`, `boto3`, `openai`, `pyyaml`, `pydantic`
- No changes to existing AWS CLI or AWS account configuration
- GitHub Actions workflow for PyPI publishing on git tag
- Users must configure an LLM provider (Bedrock via existing AWS creds, or OpenAI API key)
