## ADDED Requirements

### Requirement: Commands are classified into risk tiers before execution
The system SHALL classify every generated command into one of four risk tiers: 0 (read-only), 1 (write/reversible), 2 (destructive/irreversible), 3 (catastrophic/account-level). Classification SHALL use a static lookup table as the primary source; if no match is found, the LLM-returned `risk_tier` value is used as fallback.

#### Scenario: Read command classified as tier 0
- **WHEN** the generated command is `aws ec2 describe-instances`
- **THEN** the risk tier is 0

#### Scenario: Destructive command classified as tier 2
- **WHEN** the generated command is `aws s3 rb s3://my-bucket --force`
- **THEN** the risk tier is 2

### Requirement: Tier 0 commands execute without confirmation
The system SHALL automatically execute tier 0 (read-only) commands without prompting the user for confirmation.

#### Scenario: Auto-execute read command
- **WHEN** the risk tier is 0
- **THEN** the system runs the command immediately and displays output

### Requirement: Tier 1 commands require confirmation before execution
The system SHALL display the generated command and its explanation, then prompt the user to confirm (`y/n`) before executing tier 1 commands.

#### Scenario: Confirm write command
- **WHEN** the risk tier is 1
- **THEN** the system shows the command and explanation
- **THEN** the system prompts "Run this command? [y/n]"
- **THEN** the command only executes if the user enters `y`

#### Scenario: Cancel write command
- **WHEN** the risk tier is 1 and the user enters `n`
- **THEN** the system exits without executing anything

### Requirement: Tier 2 commands show a risk warning and require explicit confirmation
The system SHALL display the command, a prominent risk warning explaining the irreversibility, and require the user to type `yes` (not just `y`) before executing tier 2 commands. The system SHALL offer `--dry-run` as an alternative if the AWS service supports it.

#### Scenario: Destructive command with confirmation
- **WHEN** the risk tier is 2
- **THEN** the system shows the command with a warning panel indicating the operation is irreversible
- **THEN** the system prompts 'Type "yes" to confirm, or press Enter to cancel'
- **THEN** the command only executes if the user types exactly `yes`

#### Scenario: Dry-run offered for supported services
- **WHEN** the risk tier is 2 and the command is an EC2 operation that supports `--dry-run`
- **THEN** the system offers "Run with --dry-run first? [y/n]" before the confirm prompt

### Requirement: Tier 3 commands are refused by default
The system SHALL refuse to execute tier 3 commands and display an explanation of why, unless the user explicitly passes the `--i-accept-responsibility` flag.

#### Scenario: Catastrophic command refused
- **WHEN** the risk tier is 3 and `--i-accept-responsibility` is not set
- **THEN** the system displays a refusal message and exits without executing

#### Scenario: Catastrophic command with override flag
- **WHEN** the risk tier is 3 and `--i-accept-responsibility` is passed
- **THEN** the system proceeds to the tier 2 confirmation flow (warning + type "yes")

### Requirement: Protected AWS profiles are enforced as read-only
The system SHALL refuse to execute any command with a risk tier above 0 when the active AWS profile matches a protected profile pattern defined in the configuration. Protected profile patterns support glob syntax (e.g., `prod-*`).

#### Scenario: Write blocked on protected profile
- **WHEN** the active AWS profile is `production` and `production` matches a configured protected pattern
- **THEN** the system refuses to execute any tier 1, 2, or 3 command
- **THEN** the system displays "Profile 'production' is protected (read-only). Switch profiles to make changes."

#### Scenario: Read allowed on protected profile
- **WHEN** the active AWS profile matches a protected pattern and the command is tier 0
- **THEN** the system executes the command normally
