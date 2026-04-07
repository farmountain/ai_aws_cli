# Capability: output-formatting

## Purpose

Render AWS CLI output in human-friendly formats (Rich tables, key-value panels, error panels) with a raw mode bypass for piping and scripting.

## Requirements

### Requirement: List-shaped AWS output is rendered as a Rich table
The system SHALL detect when `aws` CLI JSON output contains a top-level key whose value is a list, and render it as a Rich table. Column selection SHALL prefer a predefined set of "interesting" columns per resource type; if the resource type is unrecognized, the first N columns are used (where N fits terminal width).

#### Scenario: EC2 instances rendered as table
- **WHEN** `aws ec2 describe-instances` returns JSON with a list of Reservations/Instances
- **THEN** the output is displayed as a table with columns: Instance ID, Type, State, Region

#### Scenario: Unknown list resource falls back to first N columns
- **WHEN** the output contains a list of unrecognized objects
- **THEN** the system renders a table using the first keys of the first object as column headers

### Requirement: Single-resource output is rendered as a key-value card
The system SHALL detect when `aws` CLI JSON output contains a top-level singular key (e.g., `User`, `Bucket`, `Instance`) and render it as a Rich key-value panel.

#### Scenario: IAM user displayed as card
- **WHEN** `aws iam get-user` returns `{"User": {...}}`
- **THEN** the output is displayed as a Rich panel with key: value rows

### Requirement: Error output is rendered as a styled error panel with suggestions
The system SHALL detect when the `aws` CLI exits with a non-zero exit code and render stderr in a red Rich error panel. If the error includes a known AWS error code, the system SHALL append a suggestion for resolution.

#### Scenario: BucketNotEmpty error with suggestion
- **WHEN** the command fails with `BucketNotEmpty` in stderr
- **THEN** the error is displayed in a styled error panel
- **THEN** the suggestion "Run `aws s3 rm s3://<bucket> --recursive` first, then retry" is appended

#### Scenario: Generic error rendered without suggestion
- **WHEN** the command fails with an unrecognized error code
- **THEN** the error is displayed in a styled error panel without a suggestion

### Requirement: Raw output mode bypasses all formatting
The system SHALL pass AWS CLI output directly to stdout without modification when the `--raw` flag is provided. This enables piping to `jq`, `grep`, or other tools.

#### Scenario: Raw flag pipes unformatted JSON
- **WHEN** the user runs `aaws --raw "list my S3 buckets"`
- **THEN** stdout contains the exact JSON returned by `aws s3 ls --output json`
- **THEN** no Rich formatting is applied

### Requirement: Empty output is acknowledged
The system SHALL display a "No results." message when the `aws` CLI returns an empty list or empty response, rather than displaying an empty table or blank output.

#### Scenario: No instances returns message
- **WHEN** `aws ec2 describe-instances` returns zero instances
- **THEN** the system displays "No results." instead of an empty table
