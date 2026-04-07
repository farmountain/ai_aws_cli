## Why

The MCP server (`mcp_server.py`) exposes `execute_aws_command` with no server-side safety enforcement — any MCP client can execute tier-2/3 commands without classification, bypass protected-profile guards, and leave no record. The standalone CLI enforces all of this in code, but the agent-facing interface (the primary growth path) has none of it. Meanwhile, the static tier table covers 15 AWS services but misses ~13 common ones (including `kinesis`, `elasticache`, `cognito-idp`, `autoscaling`), and the MCP fallback hardcodes unknown commands to tier 1 — meaning destructive `delete-*` commands on uncovered services are under-classified. Finally, no mode (CLI, session, MCP) records what was executed, making incident response and compliance impossible.

## What Changes

- **MCP safety gate**: `execute_aws_command` will classify the command server-side, enforce protected-profile rules, and return a `requires_confirmation` flag for tier >= 1 instead of executing immediately. A new `execute_confirmed` flow will require a classification token before running tier >= 1 commands.
- **Tier table expansion**: Add static tier entries for ~13 missing AWS services (logs, kinesis, elasticache, autoscaling, elbv2, apigateway, sagemaker, glue, stepfunctions, elasticbeanstalk, cognito-idp, redshift, sts), prioritised by data-loss risk.
- **Audit logging**: Append-only JSONL log of every executed command (timestamp, NL input, command, tier, profile, region, confirmation status, exit code, mode, duration) across all three modes (CLI, session, MCP). Configurable path, rotation after size threshold.

## Capabilities

### New Capabilities
- `mcp-safety-gate`: Server-side safety enforcement for MCP mode — classify-before-execute sequencing, protected-profile checks, and confirmation-required signalling for tier >= 1 commands.
- `audit-log`: Append-only structured logging of every AWS command executed through any mode (CLI, session, MCP), with configurable storage path and log rotation.

### Modified Capabilities
<!-- No existing specs to modify — openspec/specs/ is empty -->

## Impact

- **mcp_server.py**: `execute_aws_command` signature and return shape change (**BREAKING** for MCP clients that call execute without classify). New `execute_confirmed_aws_command` tool added.
- **safety/tier_table.py**: ~60 new entries in `TIER_TABLE`, ~3 new entries in `TIER_3_SUBSTRINGS`.
- **New module**: `src/aaws/audit.py` — append/query/rotate functions.
- **config.py**: New `AuditConfig` section (path, max_size_mb, enabled).
- **cli.py, session.py, mcp_server.py**: Each gains an `audit.append()` call after command execution.
- **tests/**: New test files for MCP safety gate, expanded tier table, and audit logging. Existing MCP tests updated for new execute return shape.
