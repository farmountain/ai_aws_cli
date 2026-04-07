# Capability: nl-to-aws-command

## Purpose

Translate natural language input into valid AWS CLI commands using an LLM, with structured output, validation, and context-aware command generation.

## Requirements

### Requirement: Natural language input is translated to an AWS CLI command
The system SHALL accept a natural language string as input and produce a valid `aws` CLI command string by invoking the configured LLM provider. The returned command SHALL begin with `aws ` and be a syntactically valid AWS CLI invocation.

#### Scenario: Simple read request
- **WHEN** the user runs `aaws "list all my S3 buckets"`
- **THEN** the system returns a command equivalent to `aws s3 ls`

#### Scenario: Request with implicit context
- **WHEN** the user runs `aaws "show running EC2 instances"` with AWS profile set to `default` and region `us-east-1`
- **THEN** the system includes the appropriate `--region us-east-1` flag in the generated command

### Requirement: LLM returns structured output with command metadata
The system SHALL use the LLM provider's tool/function calling mechanism to produce structured output containing: `command` (string), `explanation` (string), `risk_tier` (integer 0-3), and `clarification` (string or null).

#### Scenario: Structured output for a clear request
- **WHEN** the NL input maps unambiguously to a single command
- **THEN** the structured response has `clarification: null` and `command` is a complete, executable AWS CLI string

#### Scenario: Structured output for an ambiguous request
- **WHEN** the NL input is ambiguous (e.g., "delete the old stuff")
- **THEN** the structured response has a non-null `clarification` string asking for more information and `command` is null or empty

### Requirement: Invalid LLM output is rejected and retried
The system SHALL validate that the `command` field starts with `aws `. If validation fails, the system SHALL retry the LLM call once with an error correction instruction before surfacing an error to the user.

#### Scenario: LLM returns non-AWS command
- **WHEN** the LLM produces a command that does not begin with `aws `
- **THEN** the system retries once with a corrective prompt
- **THEN** if the retry also fails, the system displays an error message to the user without executing anything

### Requirement: AWS profile and region context is injected into the LLM prompt
The system SHALL include the active AWS profile name and region in the LLM system context so that generated commands are profile- and region-aware.

#### Scenario: Profile and region injected
- **WHEN** the active AWS profile is `production` and region is `eu-west-1`
- **THEN** the generated command includes `--region eu-west-1` where applicable
- **THEN** the LLM explanation references the `production` profile if relevant
