# aaws - AI-Assisted AWS CLI

[![PyPI version](https://img.shields.io/pypi/v/aaws.svg)](https://pypi.org/project/aaws/)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/aaws.svg)](https://pypi.org/project/aaws/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Natural language in, AWS command out.**

`pip install aaws` -- [pypi.org/project/aaws](https://pypi.org/project/aaws/)

Stop context-switching to AWS docs. Describe what you want in plain English and `aaws` generates, explains, and safely executes the correct AWS CLI command.

```
$ aaws "list my S3 buckets"

Command: aws s3api list-buckets --output json
Lists all S3 buckets in your account.

 Name                 CreationDate
 my-app-assets        2024-03-15T10:22:00+00:00
 my-logs-bucket       2024-06-01T08:00:00+00:00
 staging-uploads      2025-01-10T14:30:00+00:00

3 result(s)
```

---

## Table of Contents

- [How It Works](#how-it-works)
- [Using with Claude Code (MCP)](#using-with-claude-code-mcp)
- [Value Stream: User-Initiated vs Agentic Actions](#value-stream-user-initiated-vs-agentic-actions)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Commands Reference](#commands-reference)
- [End-to-End Flows with Examples](#end-to-end-flows-with-examples)
- [Safety Model](#safety-model)
- [LLM Providers](#llm-providers)
- [Output Formatting](#output-formatting)
- [Error Recovery](#error-recovery)
- [Architecture](#architecture)
- [UX and Agent Experience Assessment](#ux-and-agent-experience-assessment)
- [Development](#development)
- [License](#license)

---

## How It Works

Every `aaws` invocation follows a six-stage pipeline. Some stages are **user-initiated** (you trigger them), and others are **agentic** (the system handles them autonomously). This separation is the core design principle.

```
 YOU                              aaws (AGENT)
 ───                              ────────────
 Type natural language ──────────> LLM translates to AWS CLI command
                                   Agent classifies risk tier (0-3)
                                   Agent selects safety gate
 Review command + confirm ───────> Agent executes via subprocess
                                   Agent detects output shape
                                   Agent formats as table/card/JSON
 Read formatted results <────────
                                   (on error) Agent classifies error
                                   (on error) Agent generates recovery advice
 Read error + suggestion <───────
```

---

## Using with Claude Code (MCP)

**Use `aaws` with your Claude Code subscription — no API keys, no LLM config, zero extra cost.**

Instead of `aaws` calling an LLM directly, Claude Code becomes the LLM. The `aaws` MCP server provides safety classification, command execution, and output formatting as tools that Claude Code calls.

```
 Standalone CLI:                     MCP Mode:
 User -> aaws -> LLM (you pay)      User -> Claude Code (subscription) -> aaws MCP tools
                -> AWS CLI                                               -> AWS CLI
```

### Setup

Prerequisite: AWS CLI v2 must be installed and configured (see [Installation](#step-1-install-aws-cli-v2) above).

```bash
# Install with MCP support
pip install aaws[mcp]

# Register with Claude Code (one-time)
claude mcp add --scope user aaws -- python -m aaws.mcp_server
```

Or add a project-scoped `.mcp.json` (version-controlled, shared with team):

```json
{
  "mcpServers": {
    "aaws": {
      "command": "python",
      "args": ["-m", "aaws.mcp_server"]
    }
  }
}
```

Verify with `/mcp` inside Claude Code to see the tools listed.

### Available MCP Tools

| Tool | Purpose | LLM Needed? |
|------|---------|-------------|
| `classify_aws_command` | Risk tier classification (0-3) for any AWS CLI command | No (static table) |
| `execute_aws_command` | Safe subprocess execution with profile/region injection | No |
| `format_aws_output` | JSON shape detection -> plain-text tables/cards | No |
| `list_safety_tiers` | Browse known command risk tiers by service | No |
| `check_aws_environment` | Verify AWS CLI, active profile, region | No |

### Example Conversation in Claude Code

```
You: List my S3 buckets in us-west-2

Claude Code:
  1. Calls check_aws_environment() -> {aws_cli_available: true, active_profile: "default"}
  2. Calls classify_aws_command("aws s3api list-buckets --output json")
     -> {tier: 0, tier_label: "Read-only", should_confirm: false}
  3. Calls execute_aws_command("aws s3api list-buckets --output json", region="us-west-2")
     -> {stdout: '{"Buckets": [...]}', success: true}
  4. Calls format_aws_output(stdout)
     -> Formatted table with bucket names and dates

You: Now delete the one named old-logs

Claude Code:
  1. Calls classify_aws_command("aws s3 rb s3://old-logs --force")
     -> {tier: 2, tier_label: "Destructive", should_confirm: true}
  2. Asks: "This is a destructive operation (tier 2). Delete bucket old-logs?"
  3. You confirm
  4. Calls execute_aws_command(...)
```

### What Changes vs Standalone CLI

| Aspect | Standalone CLI | MCP Mode |
|--------|---------------|----------|
| LLM provider | You configure (Bedrock/OpenAI) | Claude Code subscription (free) |
| NL translation | aaws translator.py | Claude Code LLM |
| Session memory | In-process, 10-turn limit | Claude Code built-in (full context) |
| Multi-step workflows | One command at a time | Claude Code orchestrates multiple |
| Error interpretation | LLM call per error | Claude Code reasons over stderr |
| Configuration | `aaws config init` required | Just register MCP server |

### AWS Cloud Engineering Lifecycle (MCP)

| Lifecycle Stage | Standalone CLI | + MCP with Claude Code |
|---|---|---|
| **Discovery** | Query-based | + Autonomous inventory, cross-service |
| **Provisioning** | Single-command | + Multi-step with dependency ordering |
| **Monitoring** | Snapshot queries | + Conversational drill-down |
| **Troubleshooting** | Hardcoded + LLM errors | + Autonomous log/metric investigation |
| **Maintenance** | Manual delete/resize | + Agent finds waste, suggests optimization |
| **Security** | CLI pass-through | + Permission auditing |
| **Disaster Recovery** | Single-command backup | + Orchestrated DR workflows |

---

## Value Stream: User-Initiated vs Agentic Actions

The following maps every activity in the development and usage lifecycle to who owns it: the **user** (manual, intentional) or the **agent** (autonomous, zero-touch).

### Setup Phase

| # | Activity | Owner | Description |
|---|----------|-------|-------------|
| 1 | Install `aaws` | User | `pip install aaws` |
| 2 | Run config wizard | User | `aaws config init` — choose provider, model, profile, region |
| 3 | Detect missing config | Agent | If no config exists, prints actionable message and exits |
| 4 | Validate config schema | Agent | Pydantic validates all fields, rejects bad values |
| 5 | Resolve `${ENV_VAR}` in config | Agent | Substitutes environment variable references in YAML values |
| 6 | Apply `AAWS_*` env overrides | Agent | Environment variables override file-based config (CI/CD friendly) |
| 7 | Detect AWS CLI presence | Agent | Checks `aws` in PATH on startup; fails fast with install link |

### One-Shot Command Flow

| # | Activity | Owner | Description |
|---|----------|-------|-------------|
| 8 | Write natural language request | User | `aaws "show my running EC2 instances"` |
| 9 | Resolve AWS profile + region | Agent | Merges `--profile`/`--region` flags > config > boto3 session > fallback |
| 10 | Build LLM prompt with context | Agent | Injects system prompt + profile/region context + user request |
| 11 | Call LLM via tool/function calling | Agent | Sends structured tool schema, forces tool use (no free-text) |
| 12 | Validate command starts with `aws ` | Agent | Rejects hallucinated non-AWS output |
| 13 | Auto-retry on invalid command | Agent | Sends corrective instruction, retries once, then fails with clear error |
| 14 | Return clarification if ambiguous | Agent | If request is vague, asks ONE clarifying question instead of guessing |
| 15 | Classify risk tier (static table) | Agent | Longest-prefix match against 100+ known command patterns |
| 16 | Fallback to LLM-assigned tier | Agent | Unknown commands use the LLM's risk assessment |
| 17 | Check protected profile | Agent | Blocks all writes on `prod-*` or user-defined glob patterns |
| 18 | Show command + explanation | Agent | Displays the generated command with plain-English explanation |
| 19 | Confirm or cancel execution | User | Tier 0: auto-run. Tier 1: y/n. Tier 2: type "yes". Tier 3: refused. `--yes` auto-confirms 1-2 |
| 20 | Offer `--dry-run` for EC2 | Agent | For destructive EC2 commands, offers to validate with `--dry-run` first |
| 21 | Execute via subprocess | Agent | `shlex.split()` + `subprocess.run(shell=False)` — no injection possible |
| 22 | Detect output shape | Agent | Inspects JSON: list -> table, dict -> card, empty -> "No results." |
| 23 | Render formatted output | Agent | Rich tables with column hints per resource type, or syntax-highlighted JSON |
| 24 | Classify error on failure | Agent | Regex matches for credential, permission, resource errors |
| 25 | Provide hardcoded fix for auth | Agent | Expired token -> `aws sso login`. No creds -> `aws configure` |
| 26 | LLM-interpret resource errors | Agent | Sends failed command + stderr to LLM for plain-English recovery steps |

### Interactive Session Flow

| # | Activity | Owner | Description |
|---|----------|-------|-------------|
| 27 | Start session | User | `aaws session [--profile X] [--region Y]` |
| 28 | Display session header | Agent | Shows active profile, region, exit instructions |
| 29 | Type follow-up requests | User | Conversational input referencing prior context |
| 30 | Maintain conversation history | Agent | Appends each exchange, bounded to last 10 for LLM context |
| 31 | Translate with history context | Agent | LLM sees prior conversation for multi-turn refinement |
| 32 | Rate-limit check | Agent | Token-bucket limiter throttles requests exceeding `max_per_minute`; shows retry delay |
| 33 | Full safety pipeline per turn | Agent | Every command goes through classify -> gate -> execute -> format |
| 34 | Exit session | User | Type `exit`/`quit` or Ctrl+C |
| 35 | Handle Ctrl+C gracefully | Agent | Catches KeyboardInterrupt, prints "Goodbye.", no stack trace |

### Utility Flows

| # | Activity | Owner | Description |
|---|----------|-------|-------------|
| 36 | Explain existing command | User | `aaws explain "aws ec2 describe-instances --filters ..."` |
| 37 | LLM generates explanation | Agent | Describes what the command does, each flag, and safety caveats |
| 38 | View resolved config | User | `aaws config show` — effective config with secrets masked |
| 39 | Use `--raw` for scripting | User | `aaws --raw "list my buckets" \| jq '.Buckets[].Name'` |
| 40 | Use `--dry-run` to preview | User | Shows generated command without executing |
| 41 | Override tier-3 refusal | User | `aaws --i-accept-responsibility "delete all IAM users"` |

### CI/CD and Automation

| # | Activity | Owner | Description |
|---|----------|-------|-------------|
| 42 | Configure via env vars only | User | Set `AAWS_LLM_PROVIDER`, `AAWS_AWS_REGION`, etc. — no config file needed |
| 43 | Pipe raw output to tools | User | `aaws --raw "..." \| jq ...` for scripted consumption |
| 44 | Tests on push (GitHub Actions) | Agent | Lint (ruff) + type check (mypy) + pytest across Python 3.11-3.13 |
| 45 | Publish to PyPI on tag | Agent | `hatch build` + trusted publishing on `v*` tags |

---

## Installation

### Step 1: Install AWS CLI v2

`aaws` requires the AWS CLI to be installed and in your PATH. It delegates all AWS operations to the `aws` command.

**macOS:**

```bash
brew install awscli
```

**Windows:**

Download and run the installer from https://awscli.amazonaws.com/AWSCLIV2.msi

Or via winget:

```bash
winget install Amazon.AWSCLI
```

**Linux (x86_64):**

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Verify:**

```bash
aws --version
# aws-cli/2.x.x Python/3.x.x ...
```

### Step 2: Configure AWS Credentials

You need at least one AWS profile configured with valid credentials.

**Option A: IAM Access Keys (simplest)**

```bash
aws configure
```

You'll be prompted for:

```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: us-east-1
Default output format [None]: json
```

**Option B: AWS SSO (recommended for organizations)**

```bash
aws configure sso
```

Follow the browser login flow. Then activate the session:

```bash
aws sso login --profile your-profile-name
```

**Option C: Environment Variables (CI/CD)**

```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1
```

**Verify credentials work:**

```bash
aws sts get-caller-identity
# Should return your account ID, ARN, and user ID
```

### Step 3: Install aaws

**Requirements:** Python 3.11+, AWS CLI v2 (configured above)

The package is published at [pypi.org/project/aaws](https://pypi.org/project/aaws/).

**Standalone CLI** (needs an LLM provider — Bedrock or OpenAI):

```bash
pip install aaws
```

**With Claude Code MCP support** (use your Anthropic subscription, no API key needed):

```bash
pip install aaws[mcp]
claude mcp add --scope user aaws -- python -m aaws.mcp_server
```

Verify the installation:

```bash
aaws --help
aws sts get-caller-identity   # confirm AWS creds work
```

### Upgrade to latest version

```bash
pip install --upgrade aaws
```

### Install from source (development)

```bash
git clone https://github.com/farmountain/ai_aws_cli.git
cd ai_aws_cli
pip install -e ".[dev,mcp]"
```

---

## Quick Start

### 1. Configure

```bash
aaws config init
```

The wizard walks you through:

```
aaws configuration wizard

LLM provider [bedrock/openai] (bedrock):
Bedrock model ID (anthropic.claude-3-5-haiku-20241022-v1:0):
Default AWS profile (default):
Default AWS region (us-east-1):

 Configuration saved to ~/.config/aaws/config.yaml
Run aaws "list my S3 buckets" to test.
```

### 2. Run your first command

```bash
aaws "list my S3 buckets"
```

### 3. Try more commands

```bash
# Read-only (auto-executes, no confirmation)
aaws "show my running EC2 instances in us-west-2"
aaws "how many Lambda functions do I have"
aaws "get the details of my RDS database named prod-db"

# Write operations (asks y/n)
aaws "create an S3 bucket named my-new-bucket in us-east-1"
aaws "tag instance i-abc123 with Environment=staging"

# Preview without executing
aaws --dry-run "terminate instance i-abc123"

# Explain an existing command
aaws explain "aws iam attach-role-policy --role-name MyRole --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess"

# Raw output for scripting
aaws --raw "list my S3 buckets" | jq '.Buckets[].Name'
```

---

## Configuration

### Config file location

| OS | Path |
|----|------|
| Linux/macOS | `~/.config/aaws/config.yaml` |
| Windows | `%APPDATA%\aaws\config.yaml` |

### Full config reference

```yaml
llm:
  provider: bedrock          # "bedrock" or "openai"
  model: anthropic.claude-3-5-haiku-20241022-v1:0
  api_key: ${OPENAI_API_KEY} # Only for OpenAI; supports ${ENV_VAR} syntax
  temperature: 0.1           # Low for deterministic output
  timeout: 30                # Seconds

aws:
  default_profile: default
  default_region: us-east-1

safety:
  auto_execute_tier: 0       # Auto-run commands at or below this tier (0=read-only)
  protected_profiles:        # Glob patterns — all writes blocked on these profiles
    - "prod-*"
    - "production"

output:
  format: auto               # "auto" detects tables/cards/JSON
  raw: false                 # true = always output raw JSON
  color: true

session:
  rate_limit:
    enabled: true            # Set to false to disable rate limiting
    max_per_minute: 20       # Max LLM translation requests per minute
    burst: 5                 # Initial burst capacity (rapid follow-ups)
```

### Environment variable overrides

Every config field can be overridden with `AAWS_`-prefixed env vars. Useful for CI/CD where file config is impractical.

| Env Var | Config Field |
|---------|-------------|
| `AAWS_LLM_PROVIDER` | `llm.provider` |
| `AAWS_LLM_MODEL` | `llm.model` |
| `AAWS_LLM_API_KEY` | `llm.api_key` |
| `AAWS_LLM_TEMPERATURE` | `llm.temperature` |
| `AAWS_LLM_TIMEOUT` | `llm.timeout` |
| `AAWS_AWS_PROFILE` | `aws.default_profile` |
| `AAWS_AWS_REGION` | `aws.default_region` |
| `AAWS_SAFETY_AUTO_EXECUTE_TIER` | `safety.auto_execute_tier` |
| `AAWS_OUTPUT_FORMAT` | `output.format` |
| `AAWS_OUTPUT_RAW` | `output.raw` |
| `AAWS_OUTPUT_COLOR` | `output.color` |
| `AAWS_SESSION_RATE_LIMIT_ENABLED` | `session.rate_limit.enabled` |
| `AAWS_SESSION_RATE_LIMIT_MAX_PER_MINUTE` | `session.rate_limit.max_per_minute` |
| `AAWS_SESSION_RATE_LIMIT_BURST` | `session.rate_limit.burst` |

---

## Commands Reference

### `aaws "<request>"`

Translate natural language to an AWS CLI command and run it.

```
aaws [OPTIONS] "<natural language request>"
```

| Flag | Description |
|------|-------------|
| `--profile`, `-p` | Override AWS profile for this invocation |
| `--region`, `-r` | Override AWS region for this invocation |
| `--raw` | Output raw JSON (no tables, no formatting) |
| `--dry-run` | Show the generated command without executing |
| `--yes`, `-y` | Auto-confirm tier 1-2 commands (skip interactive prompts) |
| `--i-accept-responsibility` | Override tier-3 catastrophic operation refusal |

### `aaws explain "<command>"`

Explain what an existing AWS CLI command does.

```bash
$ aaws explain "aws s3 rm s3://my-bucket --recursive"

Command: aws s3 rm s3://my-bucket --recursive

This command deletes all objects in the S3 bucket "my-bucket" recursively.
The --recursive flag means it will delete everything inside the bucket, not
just a single object. This is a destructive operation that cannot be undone.
Ensure you have backups before running this command.
```

### `aaws session`

Start an interactive REPL with conversation context.

```bash
$ aaws session --profile dev --region eu-west-1

 aaws interactive session
 Profile: dev  Region: eu-west-1
 Type 'exit' or 'quit' to end the session. Ctrl+C to abort.

[aaws]> show my EC2 instances
  ...table output...

[aaws]> now stop the one named web-server
  # LLM sees the prior context and knows which instance you mean

[aaws]> what's the status now?
  # Multi-turn conversation continues

[aaws]> exit
Goodbye.
```

### `aaws config init`

Interactive first-time setup wizard.

### `aaws config show`

Print the resolved effective config with secrets masked.

```bash
$ aaws config show
{
  "llm": {
    "provider": "bedrock",
    "model": "anthropic.claude-3-5-haiku-20241022-v1:0",
    "api_key": "***",
    "temperature": 0.1,
    "timeout": 30
  },
  ...
}
```

---

## End-to-End Flows with Examples

### Flow 1: Read-Only Query (Tier 0 - Fully Agentic)

Zero friction. You type, agent does everything.

```
$ aaws "what EC2 instances are running in us-east-1"
```

```
Pipeline:
  [User]  Types request
  [Agent] Translates -> "aws ec2 describe-instances --filters Name=instance-state-name,Values=running --region us-east-1 --output json"
  [Agent] Classifies -> tier 0 (aws ec2 describe = read-only)
  [Agent] Safety gate -> auto-execute (tier 0, no prompt)
  [Agent] Executes subprocess
  [Agent] Detects JSON shape -> Reservations -> flattens Instances -> table
  [Agent] Renders Rich table
  [User]  Reads formatted output
```

```
 InstanceId     InstanceType  State    PublicIpAddress  LaunchTime
 i-0abc123def   t3.micro      running  54.123.45.67     2025-03-01T...
 i-0def456ghi   t3.large      running  54.234.56.78     2025-03-15T...

2 result(s)
```

**User actions: 1** (type request). **Agent actions: 6** (translate, classify, gate, execute, detect, render).

---

### Flow 2: Write Operation (Tier 1 - User Confirms)

```
$ aaws "create an S3 bucket named analytics-2025 in us-west-2"
```

```
Pipeline:
  [User]  Types request
  [Agent] Translates -> "aws s3api create-bucket --bucket analytics-2025 --region us-west-2 --create-bucket-configuration LocationConstraint=us-west-2"
  [Agent] Classifies -> tier 1 (aws s3api create-bucket = write)
  [Agent] Shows command + explanation
  [User]  Confirms y/n
  [Agent] Executes, formats output
```

```
Command: aws s3api create-bucket --bucket analytics-2025 --region us-west-2 --create-bucket-configuration LocationConstraint=us-west-2
Creates a new S3 bucket named "analytics-2025" in us-west-2.

Run this command? [y/n]: y

 Location: http://analytics-2025.s3.amazonaws.com/
```

**User actions: 2** (type request, confirm). **Agent actions: 5**.

---

### Flow 3: Destructive Operation (Tier 2 - Warning + Explicit Confirm)

```
$ aaws "terminate instance i-0abc123def"
```

```
Pipeline:
  [User]  Types request
  [Agent] Translates -> "aws ec2 terminate-instances --instance-ids i-0abc123def"
  [Agent] Classifies -> tier 2 (aws ec2 terminate-instances = destructive)
  [Agent] Shows command + explanation
  [Agent] Shows WARNING panel
  [Agent] Offers --dry-run validation (EC2 commands support it)
  [User]  Chooses dry-run or types "yes" to confirm
  [Agent] Executes
```

```
Command: aws ec2 terminate-instances --instance-ids i-0abc123def
Terminates EC2 instance i-0abc123def. This permanently destroys the instance.

+---------- Destructive Operation ----------+
| WARNING  This operation is irreversible    |
| - it cannot be undone.                     |
+--------------------------------------------+

Validate first with --dry-run (no changes will be made)? [y/n]: y

Running: aws ec2 terminate-instances --instance-ids i-0abc123def --dry-run
Dry run succeeded - no changes were made.
```

**User actions: 2** (type request, choose dry-run or confirm). **Agent actions: 7** (translate, classify, gate, warn, offer dry-run, execute, render).

---

### Flow 4: Catastrophic Operation (Tier 3 - Refused by Default)

```
$ aaws "delete all objects in s3://production-data recursively"
```

```
Pipeline:
  [Agent] Translates -> "aws s3 rm s3://production-data --recursive"
  [Agent] Classifies -> tier 3 (aws s3 rm + --recursive = catastrophic)
  [Agent] REFUSES execution
```

```
+---------- Catastrophic Operation Blocked ----------+
| REFUSED  This operation is catastrophic and may     |
| permanently alter or destroy your AWS account.      |
|                                                     |
| If you are absolutely certain, re-run with          |
| --i-accept-responsibility.                          |
+-----------------------------------------------------+
```

To override (with full tier-2 confirmation flow):

```
$ aaws --i-accept-responsibility "delete all objects in s3://production-data recursively"
```

---

### Flow 5: Ambiguous Request (Agent Asks for Clarification)

```
$ aaws "stop that server"
```

```
Pipeline:
  [User]  Types vague request
  [Agent] Translates -> clarification needed (no resource ID)
  [Agent] Returns clarification question
  [User]  Reads question, re-runs with specifics
```

```
? Which EC2 instance would you like to stop? Please provide the instance ID
  (e.g., i-0abc123def) or a name tag to identify it.
```

In session mode, you can answer directly:

```
[aaws]> stop that server
? Which EC2 instance would you like to stop?

[aaws]> the one tagged Name=web-server
Command: aws ec2 stop-instances --instance-ids i-0abc123def
Run this command? [y/n]:
```

---

### Flow 6: Error Recovery (Agent Diagnoses + Suggests Fix)

```
$ aaws "delete S3 bucket old-logs"
```

```
Pipeline:
  [User]  Confirms deletion
  [Agent] Executes -> fails (BucketNotEmpty)
  [Agent] Classifies error -> resource error
  [Agent] Sends command + error to LLM for interpretation
  [Agent] Renders error panel with suggestion
```

```
+---------- Error ----------+
| An error occurred          |
| (BucketNotEmpty) when      |
| calling DeleteBucket:      |
| The bucket is not empty.   |
|                            |
| Suggestion: The bucket     |
| "old-logs" still contains  |
| objects. Empty it first:   |
|   aws s3 rm s3://old-logs  |
|     --recursive            |
| Then retry the delete.     |
+----------------------------+
```

### Flow 7: Credential Error (Agent Provides Hardcoded Fix)

```
+---------- Error ----------+
| ExpiredTokenException:     |
| The security token in the  |
| request has expired.       |
|                            |
| Suggestion: Your AWS       |
| session has expired.       |
| Refresh it with:           |
|   aws sso login            |
|     --profile default      |
+----------------------------+
```

No LLM call needed for credential errors -- instant, deterministic fix.

---

### Flow 8: Protected Profile (Agent Blocks Writes)

```yaml
# config.yaml
safety:
  protected_profiles:
    - "prod-*"
    - "production"
```

```
$ aaws --profile prod-us-east-1 "delete instance i-abc123"

Blocked: Profile 'prod-us-east-1' is protected (read-only). Switch profiles to make changes.
```

Read operations still work:

```
$ aaws --profile prod-us-east-1 "list my EC2 instances"
# Executes normally (tier 0, read-only)
```

---

### Flow 9: Interactive Multi-Turn Session

```
$ aaws session --profile dev

 aaws interactive session
 Profile: dev  Region: us-east-1
 Type 'exit' or 'quit' to end the session. Ctrl+C to abort.

[aaws]> show my security groups
  GroupId       GroupName      Description     VpcId
  sg-abc123     web-sg         Web servers     vpc-111
  sg-def456     db-sg          Database        vpc-111
  2 result(s)

[aaws]> what are the inbound rules for the web one?
  # Agent knows "the web one" = sg-abc123 from conversation history
  Command: aws ec2 describe-security-group-rules --filters Name=group-id,Values=sg-abc123 --output json
  ...rules table...

[aaws]> add port 443 to it
  Command: aws ec2 authorize-security-group-ingress --group-id sg-abc123 --protocol tcp --port 443 --cidr 0.0.0.0/0
  Run this command? [y/n]: y
  ...success...

[aaws]> exit
Goodbye.
```

History is bounded to the last 10 exchanges. Session state is in-memory only (never written to disk).

---

### Flow 10: Scripting and Piping (Raw Mode)

```bash
# Get instance IDs as plain text for scripting
INSTANCES=$(aaws --raw "list running EC2 instances" | jq -r '.Reservations[].Instances[].InstanceId')

# Use in a loop
for id in $INSTANCES; do
  echo "Processing $id..."
done

# Combine with other tools
aaws --raw "show my IAM users" | jq '.Users[] | select(.UserName | startswith("temp-"))' | wc -l
```

---

### Flow 11: CI/CD Automation with --yes Flag

```bash
# In a CI pipeline, skip interactive confirmations for tier 1-2 commands
aaws --yes "tag instance i-abc123 with Environment=staging"

# Combine with --raw for machine-readable output
aaws --yes --raw "create an S3 bucket named build-artifacts-$(date +%s)" | jq .

# Configure entirely via environment variables (no config file needed)
export AAWS_LLM_PROVIDER=bedrock
export AAWS_AWS_REGION=us-east-1
aaws --yes "create a CloudWatch alarm for high CPU on instance i-abc123"
```

Note: `--yes` auto-confirms tier 1 (write) and tier 2 (destructive) commands.
It does **NOT** bypass tier 3 (catastrophic) refusal -- that still requires `--i-accept-responsibility`.

---

## Safety Model

### Risk Tiers

| Tier | Label | Examples | Gate | User Action |
|------|-------|---------|------|-------------|
| **0** | Read-only | `describe`, `list`, `get`, `head` | Auto-execute | None |
| **1** | Write | `create`, `put`, `update`, `start`, `tag` | Show + y/n | Press `y` (or `--yes`) |
| **2** | Destructive | `delete`, `terminate`, `detach`, `rm` | Warn + type "yes" + dry-run offer | Type `yes` (or `--yes`) |
| **3** | Catastrophic | Bulk delete, org-level, IAM nuke | **Refused** | `--i-accept-responsibility` (not `--yes`) |

### Classification Strategy

1. **Tier 3 substring check** -- patterns like `aws s3 rm` + `--recursive` always match catastrophic
2. **Static tier table** -- 100+ command prefix-to-tier mappings (longest match wins). Deterministic, zero LLM cost, cannot be overridden by a confused model
3. **LLM fallback** -- for unknown/novel commands, the LLM's own `risk_tier` assessment is used

### Protected Profiles

Configure glob patterns in `safety.protected_profiles`. Any write operation (tier > 0) against a matching profile is blocked with a clear error. Case-insensitive matching via `fnmatch`.

### Shell Injection Prevention

Commands are **never** passed to a shell. `shlex.split()` tokenizes the command string and `subprocess.run()` receives a list with `shell=False`. This is enforced at the architecture level, not by convention.

---

## LLM Providers

### AWS Bedrock (default)

Uses your existing AWS credentials. No extra API key, no data leaving your AWS account.

```yaml
llm:
  provider: bedrock
  model: anthropic.claude-3-5-haiku-20241022-v1:0
```

Requires Bedrock model access to be enabled in the AWS Console. If not, `aaws` detects the `AccessDeniedException` and tells you exactly where to enable it.

### OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}
```

Or set `OPENAI_API_KEY` as an environment variable.

### Structured Output

Both providers use **tool/function calling** to guarantee structured responses (command, explanation, risk_tier, clarification). This eliminates JSON parsing failures from free-text prompting. A fallback JSON parser handles edge cases where tool calling is unavailable.

---

## Output Formatting

| JSON Shape | Rendered As | Example |
|-----------|-------------|---------|
| Top-level list of dicts | Rich table | EC2 instances, S3 buckets, IAM users |
| Single dict | Key-value card panel | Bucket details, instance metadata |
| Empty list/dict | "No results." | |
| Non-JSON text | Plain text passthrough | `aws s3 ls` text output |
| Any (with `--raw`) | Raw stdout | For piping to `jq`, `grep`, etc. |

Column hints are built in for 25+ AWS resource types (EC2 Instances, S3 Buckets, IAM Users/Roles/Policies, Lambda Functions, CloudFormation Stacks, ECS Clusters, RDS instances, etc.), ensuring the most useful columns appear first.

---

## Error Recovery

| Error Type | Detection | Recovery | LLM Call? |
|-----------|-----------|----------|-----------|
| Expired token | Regex on stderr | `aws sso login --profile <name>` | No |
| No credentials | Regex on stderr | `aws configure` | No |
| Access denied | Regex on stderr | Shows denied action + profile switch advice | No |
| Bucket not empty | Regex on stderr | LLM explains + suggests `aws s3 rm --recursive` | Yes |
| Resource not found | Regex on stderr | LLM interprets error + suggests fix | Yes |
| Resource conflict | Regex on stderr | LLM interprets error + suggests fix | Yes |
| Unknown error | Fallback | Raw stderr in styled error panel | No |
| LLM timeout | Exception catch | "Check your network connection and try again." | No |

Credential and permission errors use **hardcoded messages** (instant, free, deterministic). Resource errors are sent to the **LLM for interpretation** (contextual, actionable).

---

## Architecture

```
src/aaws/
  __init__.py          # Package version
  cli.py               # Typer entry point: root command, explain, session, config
  translator.py        # NL -> AWS CLI via LLM (system prompt, validation, retry)
  executor.py          # subprocess.run(shlex.split(cmd), shell=False)
  formatter.py         # JSON shape detection -> Rich tables/cards/JSON
  config.py            # Pydantic models, YAML loader, env var resolution
  errors.py            # Error classification, credential messages, LLM interpretation
  session.py           # Interactive REPL with bounded conversation history
  rate_limit.py        # Token-bucket rate limiter for session mode
  audit.py             # Audit logging (append-only JSONL)
  providers/
    __init__.py         # get_provider() factory
    base.py             # LLMProvider protocol, TOOL_SCHEMA, LLMResponse, Message
    bedrock_provider.py # AWS Bedrock converse API with tool use
    openai_provider.py  # OpenAI chat completions with function calling
  safety/
    __init__.py         # Package exports
    classifier.py       # classify(), apply_safety_gate(), is_protected_profile()
    tier_table.py       # Static dict: 100+ command prefix -> tier mappings
```

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution | `subprocess.run` over boto3 | Auditable commands, no 300+ service API to model |
| LLM output | Tool/function calling over prompting | Guaranteed structured schema, no JSON parse failures |
| Safety | Static table + LLM fallback | Deterministic floor (90%+ commands) + flexible fallback |
| CLI framework | Typer + Rich | Type-annotated CLI + production-grade terminal UI |
| Config | Pydantic + YAML + env vars | Validation, file-based defaults, CI/CD-friendly overrides |
| Provider | Bedrock default | Same creds, same account, no extra API key |
| Python | 3.11+ minimum | Not EOL until 2027, `match/case`, wide platform availability |

---

## UX and Agent Experience Assessment

### What works well

- **Zero-config for Bedrock users**: If you have AWS creds, you have an LLM. No signup, no API key.
- **Progressive disclosure of safety**: Tier 0 is frictionless, each tier adds exactly one more confirmation step. The escalation is proportional to risk.
- **Clarification over guessing**: The agent asks rather than hallucinating resource IDs -- this is a critical safety decision.
- **Deterministic safety floor**: The static tier table means `aws ec2 terminate-instances` is *always* tier 2, regardless of what the LLM says. The LLM can escalate but never downgrade.
- **Error recovery is contextual**: Credential errors get instant hardcoded fixes (no LLM latency/cost). Resource errors get LLM interpretation. This is the right split.
- **Session mode preserves context**: "stop the one tagged web-server" works because the agent remembers the prior listing.
- **Raw mode for composability**: `--raw` makes `aaws` a good Unix citizen that pipes into `jq` and scripts.

### Areas for improvement

- **No command history persistence**: Session history lives in memory only. Restarting loses all context. A `~/.aaws/history.json` with last N sessions would help.
- **No streaming output**: Long-running commands (e.g., `aws s3 sync`) show nothing until completion. Streaming stdout would improve perceived latency.
- **No command validation against AWS help**: The agent trusts the LLM to produce valid flags. A post-generation check against `aws <service> help` output would catch hallucinated flags.
- **Protected profile patterns are config-only**: No `aaws safety add-profile "prod-*"` command to manage them interactively.
- **Single-command-at-a-time**: No agentic multi-step workflows (acknowledged as v2 scope).

### Agent autonomy balance

The current split is well-calibrated for a CLI tool that runs real infrastructure commands:

- **High autonomy** for read-only operations and output formatting (no friction for safe actions)
- **Shared control** for writes and destructive operations (agent prepares, human decides)
- **Human-only** for catastrophic operations (agent refuses, human must explicitly override)
- **Full autonomy** for error recovery (agent diagnoses and suggests without asking)

This is the right balance. A more autonomous agent (auto-executing writes) would be dangerous for AWS operations. A less autonomous one (confirming reads) would be annoying.

---

## Development

### Setup

```bash
git clone https://github.com/farmountain/ai_aws_cli.git
cd ai_aws_cli
pip install -e ".[dev]"
```

### Run tests

```bash
pytest --tb=short -q
```

### Lint and type check

```bash
ruff check src/ tests/
mypy src/
```

### CI/CD

- **Push to `main`** or **PR**: runs tests on Python 3.11, 3.12, 3.13 + lint + type check
- **Push `v*` tag**: builds and publishes to PyPI via trusted publishing

### Publish a release

```bash
git tag v0.1.0
git push origin v0.1.0
# GitHub Actions builds and publishes to PyPI
```

---

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
