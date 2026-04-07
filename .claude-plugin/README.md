# aaws - Claude Code Plugin

AI-Assisted AWS CLI plugin for Claude Code. Provides a natural language
interface to AWS with built-in safety tiers.

## What it provides

Six MCP tools exposed via stdio transport:

| Tool | Purpose |
|------|---------|
| `classify_aws_command` | Risk tier classification (0 = read-only, 1 = write, 2 = destructive, 3 = catastrophic) |
| `execute_aws_command` | Safe subprocess execution of AWS CLI commands |
| `execute_confirmed_aws_command` | Execute a pre-confirmed command after user approval |
| `format_aws_output` | Convert JSON output to readable tables/cards |
| `list_safety_tiers` | Browse known command risk tiers |
| `check_aws_environment` | Verify AWS CLI installation and credentials |

## Prerequisites

- Python >= 3.11
- AWS CLI installed and configured (`aws configure`)
- The `aaws` package installed with MCP extras: `pip install aaws[mcp]`

## Installation

### Option 1: Project-scoped (via .mcp.json)

A `.mcp.json` file is included at the project root. Claude Code will
detect it automatically when you open the project.

### Option 2: User-scoped (via claude mcp add)

```bash
claude mcp add --scope user aaws -- python -m aaws.mcp_server
```

### Option 3: Plugin directory

Copy the `.claude-plugin` directory into your project or link it so
Claude Code discovers the plugin manifest.

## Safety model

Every command is classified before execution. Tier 0 commands run
freely; tier 1+ commands require user confirmation; tier 3 commands
are refused unless the user explicitly insists.
