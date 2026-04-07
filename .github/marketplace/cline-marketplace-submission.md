# Cline MCP Marketplace Submission

## Issue Title

Add aaws - AI-Assisted AWS CLI with Safety Classification

## Issue Body

### Server Name

aaws

### Repository URL

https://github.com/farmountain/ai_aws_cli

### Description

AI-assisted AWS CLI that translates natural language into AWS commands with a 4-tier safety classification system (read-only, write, destructive, catastrophic). Provides six MCP tools for classifying, executing, and formatting AWS CLI operations with built-in risk assessment.

### Available Tools

| Tool | Description |
|------|-------------|
| `classify_aws_command` | Classify an AWS CLI command into a safety risk tier (0-3) |
| `execute_aws_command` | Execute an AWS CLI command with safety checks and optional profile/region |
| `execute_confirmed_aws_command` | Execute a pre-confirmed AWS CLI command after user approval |
| `format_aws_output` | Format raw AWS CLI JSON output into readable plain-text tables |
| `list_safety_tiers` | List safety tier classifications for known AWS CLI commands, optionally filtered by service |
| `check_aws_environment` | Check local AWS environment: CLI availability, active profile, region |

### Installation

Requires Python 3.11+ and the AWS CLI installed and configured.

```bash
pip install aaws[mcp]
```

Add to your MCP settings:

```json
{
  "mcpServers": {
    "aaws": {
      "command": "aaws-mcp"
    }
  }
}
```

### Category

Cloud Platforms

### Additional Information

- **Version:** 0.3.0
- **License:** MIT
- **LLM Providers:** OpenAI, AWS Bedrock
- **Safety Tiers:** Tier 0 (read-only), Tier 1 (write), Tier 2 (destructive), Tier 3 (catastrophic)
