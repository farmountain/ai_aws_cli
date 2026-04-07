# Capability: MCP Safety Gate

## Purpose

Server-side safety enforcement for MCP tool calls, ensuring risk classification, confirmation gating, protected profile enforcement, and audit health reporting.

## Requirements

### Requirement: execute_aws_command enforces classification server-side
The `execute_aws_command` MCP tool SHALL classify the command using `classify()` before execution. For tier 0 commands, it SHALL execute immediately and return the result. For tier >= 1 commands, it SHALL NOT execute the command and SHALL return a response containing the classification tier, tier label, and `requires_confirmation: true`. The `auto_execute_tier` config value SHALL NOT be applied in MCP mode — all tier >= 1 commands require confirmation regardless of config.

#### Scenario: Tier 0 command executes immediately
- **WHEN** an MCP client calls `execute_aws_command("aws s3 ls")`
- **THEN** the server classifies the command as tier 0, executes it, and returns `{success: true, stdout: ..., tier: 0, requires_confirmation: false, executed: true}`

#### Scenario: Tier 1 command is blocked pending confirmation
- **WHEN** an MCP client calls `execute_aws_command("aws ec2 run-instances --instance-type t3.micro")`
- **THEN** the server classifies the command as tier 1 and returns `{requires_confirmation: true, tier: 1, tier_label: "Write", executed: false}` without executing the command

#### Scenario: Tier 2 command is blocked pending confirmation
- **WHEN** an MCP client calls `execute_aws_command("aws ec2 terminate-instances --instance-ids i-abc123")`
- **THEN** the server returns `{requires_confirmation: true, tier: 2, tier_label: "Destructive", executed: false}` without executing the command

#### Scenario: Tier 3 command is refused
- **WHEN** an MCP client calls `execute_aws_command("aws s3 rm s3://bucket --recursive")`
- **THEN** the server returns `{requires_confirmation: true, tier: 3, tier_label: "Catastrophic", is_catastrophic: true, executed: false}` without executing the command

#### Scenario: auto_execute_tier is ignored in MCP mode
- **WHEN** the user config has `safety.auto_execute_tier: 1`
- **AND** an MCP client calls `execute_aws_command("aws ec2 run-instances --instance-type t3.micro")`
- **THEN** the server still returns `{requires_confirmation: true, tier: 1, executed: false}` — the auto_execute_tier setting only applies to CLI and session modes

### Requirement: execute_confirmed_aws_command tool for confirmed execution
The MCP server SHALL expose an `execute_confirmed_aws_command` tool that executes any valid AWS CLI command after re-classifying it for audit accuracy. This tool SHALL only be called by agents after the user has explicitly confirmed the operation. The tool SHALL call `classify()` on the command and include the tier in both its response and the audit log entry. The tool docstring SHALL instruct agents to only use it after user confirmation of a tier >= 1 command.

#### Scenario: Confirmed execution of a write command
- **WHEN** an MCP client calls `execute_confirmed_aws_command("aws ec2 run-instances --instance-type t3.micro")`
- **THEN** the server re-classifies (tier 1), executes the command, and returns `{success: true/false, stdout: ..., stderr: ..., exit_code: ..., tier: 1}`

#### Scenario: Non-AWS command rejected
- **WHEN** an MCP client calls `execute_confirmed_aws_command("rm -rf /")`
- **THEN** the server returns `{success: false, stderr: "Error: command must start with 'aws '"}` without executing

#### Scenario: Re-classification detects tier mismatch
- **WHEN** an MCP client calls `execute_confirmed_aws_command("aws ec2 terminate-instances --instance-ids i-abc")`
- **AND** the original `execute_aws_command` call classified a different command as tier 1
- **THEN** the server re-classifies this command as tier 2 and logs tier 2 in the audit entry (the actual tier of what ran, not the previously classified tier)

### Requirement: Protected profile enforcement in MCP mode
The `execute_aws_command` and `execute_confirmed_aws_command` tools SHALL enforce protected-profile rules. The effective profile for safety checks SHALL be determined by parsing `--profile` from the command string (via `shlex.split`); if not present in the command, the `profile` parameter is used. If the effective profile matches a protected pattern and the command tier > 0, the tool SHALL return an error without executing.

#### Scenario: Protected profile blocks write command via parameter
- **WHEN** the user config has `safety.protected_profiles: ["prod-*"]`
- **AND** an MCP client calls `execute_aws_command("aws ec2 run-instances ...", profile="prod-us-east-1")`
- **THEN** the server returns `{success: false, error: "Profile 'prod-us-east-1' is protected (read-only)", executed: false}`

#### Scenario: Protected profile blocks write command embedded in command string
- **WHEN** the user config has `safety.protected_profiles: ["prod-*"]`
- **AND** an MCP client calls `execute_aws_command("aws ec2 run-instances --profile prod-us-east-1", profile="dev")`
- **THEN** the server parses `--profile prod-us-east-1` from the command, determines the effective profile is `prod-us-east-1`, and returns `{success: false, error: "Profile 'prod-us-east-1' is protected (read-only)", executed: false}`

#### Scenario: Protected profile allows read command
- **WHEN** the user config has `safety.protected_profiles: ["prod-*"]`
- **AND** an MCP client calls `execute_aws_command("aws ec2 describe-instances", profile="prod-us-east-1")`
- **THEN** the server classifies as tier 0 and executes normally

#### Scenario: Protected profile blocks confirmed write
- **WHEN** the user config has `safety.protected_profiles: ["prod-*"]`
- **AND** an MCP client calls `execute_confirmed_aws_command("aws ec2 run-instances ...", profile="prod-us-east-1")`
- **THEN** the server returns an error — protected profiles are enforced even in execute_confirmed

#### Scenario: Unprotected profile allows confirmed write
- **WHEN** the user config has `safety.protected_profiles: ["prod-*"]`
- **AND** an MCP client calls `execute_confirmed_aws_command("aws ec2 run-instances ...", profile="dev")`
- **THEN** the server executes the command normally

### Requirement: MCP server loads config at startup with safe defaults
The MCP server SHALL attempt to load `AawsConfig` via `load_config()` during initialization. If the config file does not exist, it SHALL fall back to `AawsConfig()` defaults (empty protected profiles, `auto_execute_tier=0`). The config SHALL be cached for the lifetime of the server process.

#### Scenario: Config exists and is loaded
- **WHEN** the MCP server starts and `~/.config/aaws/config.yaml` exists with `safety.protected_profiles: ["prod"]`
- **THEN** the server uses those protected profile patterns for all subsequent tool calls

#### Scenario: Config does not exist
- **WHEN** the MCP server starts and no config file exists
- **THEN** the server uses default config (no protected profiles, auto_execute_tier=0) and does not error

### Requirement: classify_aws_command is a preview tool
The `classify_aws_command` tool docstring SHALL describe it as a preview/lookahead tool for checking risk tier before presenting a command to the user. It SHALL NOT state that it is mandatory before `execute_aws_command` (since execute now classifies internally). Its response shape is unchanged.

#### Scenario: Agent uses classify as preview before confirmed execution
- **WHEN** an MCP client calls `classify_aws_command("aws ec2 terminate-instances --instance-ids i-abc")`
- **THEN** the server returns `{tier: 2, tier_label: "Destructive", should_confirm: true, is_catastrophic: false}`
- **AND** the agent can present this to the user and then call `execute_confirmed_aws_command` directly (skipping `execute_aws_command`)

#### Scenario: Agent skips classify and uses execute directly
- **WHEN** an MCP client calls `execute_aws_command("aws ec2 run-instances ...")` without calling classify first
- **THEN** the server classifies internally and returns `{tier: 1, requires_confirmation: true, executed: false}` — classify was not needed

### Requirement: check_aws_environment includes audit health
The `check_aws_environment` MCP tool SHALL include an `audit_writable: bool` field in its response, indicating whether the audit log path is writable. This is a one-time health check at session start so agents can surface audit configuration problems to the user.

#### Scenario: Audit path is writable
- **WHEN** an MCP client calls `check_aws_environment()` and the audit log path exists and is writable
- **THEN** the response includes `{audit_writable: true}`

#### Scenario: Audit path is not writable
- **WHEN** an MCP client calls `check_aws_environment()` and the audit log path is not writable
- **THEN** the response includes `{audit_writable: false}`

### Requirement: Tier table covers priority AWS services
The `TIER_TABLE` in `safety/tier_table.py` SHALL include entries for the following services: `logs`, `kinesis`, `elasticache`, `autoscaling`, `cognito-idp`, `redshift`, `elbv2`, `apigateway`, `sagemaker`, `glue`, `stepfunctions`, `elasticbeanstalk`, `sts`. Each service SHALL have entries for read (tier 0), write (tier 1), and destructive (tier 2) command prefixes at minimum.

#### Scenario: CloudWatch Logs delete classified as destructive
- **WHEN** the classifier receives `"aws logs delete-log-group --log-group-name /app/prod"`
- **THEN** it returns tier 2

#### Scenario: Kinesis delete-stream classified as destructive
- **WHEN** the classifier receives `"aws kinesis delete-stream --stream-name prod-events"`
- **THEN** it returns tier 2

#### Scenario: Kinesis describe classified as read-only
- **WHEN** the classifier receives `"aws kinesis describe-stream --stream-name prod-events"`
- **THEN** it returns tier 0

#### Scenario: ElastiCache delete-replication-group classified as destructive
- **WHEN** the classifier receives `"aws elasticache delete-replication-group --replication-group-id prod-redis"`
- **THEN** it returns tier 2

#### Scenario: Cognito delete-user-pool classified as destructive
- **WHEN** the classifier receives `"aws cognito-idp delete-user-pool --user-pool-id us-east-1_abc"`
- **THEN** it returns tier 2

#### Scenario: STS assume-role classified as write
- **WHEN** the classifier receives `"aws sts assume-role --role-arn arn:aws:iam::123:role/admin"`
- **THEN** it returns tier 1

#### Scenario: STS get-caller-identity classified as read-only
- **WHEN** the classifier receives `"aws sts get-caller-identity"`
- **THEN** it returns tier 0

#### Scenario: ELBv2 delete-load-balancer classified as destructive
- **WHEN** the classifier receives `"aws elbv2 delete-load-balancer --load-balancer-arn arn:..."`
- **THEN** it returns tier 2

#### Scenario: Auto Scaling delete-auto-scaling-group classified as destructive
- **WHEN** the classifier receives `"aws autoscaling delete-auto-scaling-group --auto-scaling-group-name prod-asg"`
- **THEN** it returns tier 2
