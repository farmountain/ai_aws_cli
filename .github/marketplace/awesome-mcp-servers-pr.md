# awesome-mcp-servers PR Submission Draft

Target repo: https://github.com/punkpeye/awesome-mcp-servers

---

## Entry to add

Add the following line to the **Cloud Platforms** category (alphabetical order):

```
- [aaws](https://github.com/farmountain/ai_aws_cli) - Natural language AWS CLI with 4-tier safety model for command execution.
```

---

## PR title

```
Add aaws — natural language AWS CLI MCP server
```

---

## PR description body

```markdown
## New server: aaws

- **Name:** aaws
- **URL:** https://github.com/farmountain/ai_aws_cli
- **Description:** Natural language AWS CLI with 4-tier safety model for command execution.
- **Category:** Cloud Platforms
- **License:** MIT
- **Language:** Python

### What it does

aaws is an AI-assisted AWS CLI that translates plain English into AWS CLI
commands. Its built-in MCP server (v0.3.0) exposes 6 tools:

| Tool | Purpose |
|------|---------|
| `classify_aws_command` | Classify a command into one of 4 safety tiers |
| `execute_aws_command` | Execute an AWS CLI command with safety checks |
| `execute_confirmed_aws_command` | Execute a pre-confirmed command after user approval |
| `format_aws_output` | Format AWS CLI JSON output into readable tables |
| `list_safety_tiers` | List the safety tier definitions |
| `check_aws_environment` | Verify AWS CLI and credentials are configured |

### Safety model

Commands are classified into 4 tiers before execution:

1. **Safe** — read-only operations (e.g., list, describe)
2. **Moderate** — reversible writes (e.g., tag, enable versioning)
3. **Sensitive** — significant changes (e.g., create, modify)
4. **Critical** — destructive or irreversible (e.g., delete, terminate)

Higher tiers require explicit user confirmation.

### Installation

```bash
pip install aaws
```
```
