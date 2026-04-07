## 1. Tier Table Expansion

- [x] 1.1 Add `logs` (CloudWatch Logs) entries to `TIER_TABLE`: `describe-*`/`get-*`/`list-*`/`filter-*` → 0, `create-*`/`put-*`/`tag-*` → 1, `delete-log-group`/`delete-log-stream` → 2
- [x] 1.2 Add `kinesis` entries: `describe-*`/`list-*`/`get-*` → 0, `create-stream`/`put-record`/`put-records`/`update-*`/`add-tags-*` → 1, `delete-stream`/`remove-tags-*` → 2
- [x] 1.3 Add `elasticache` entries: `describe-*`/`list-*` → 0, `create-*`/`modify-*`/`add-tags-*` → 1, `delete-cache-cluster`/`delete-replication-group`/`delete-snapshot` → 2
- [x] 1.4 Add `autoscaling` entries: `describe-*` → 0, `create-*`/`update-*`/`set-*`/`put-*`/`attach-*` → 1, `delete-auto-scaling-group`/`delete-launch-configuration`/`delete-policy`/`detach-*` → 2
- [x] 1.5 Add `cognito-idp` entries: `describe-*`/`list-*`/`get-*` → 0, `create-*`/`update-*`/`admin-create-*`/`set-*` → 1, `delete-user-pool`/`delete-user`/`admin-delete-*` → 2
- [x] 1.6 Add `redshift` entries: `describe-*`/`list-*` → 0, `create-cluster`/`modify-cluster`/`create-snapshot`/`restore-*` → 1, `delete-cluster`/`delete-snapshot` → 2
- [x] 1.7 Add `elbv2` entries: `describe-*` → 0, `create-*`/`modify-*`/`register-targets`/`set-*`/`add-*` → 1, `delete-load-balancer`/`delete-target-group`/`delete-listener`/`deregister-targets`/`remove-*` → 2
- [x] 1.8 Add `apigateway` entries: `get-*` → 0, `create-*`/`put-*`/`update-*`/`import-*` → 1, `delete-rest-api`/`delete-stage`/`delete-deployment`/`delete-resource` → 2
- [x] 1.9 Add `sagemaker` entries: `describe-*`/`list-*` → 0, `create-*`/`update-*`/`start-*` → 1, `delete-endpoint`/`delete-model`/`delete-notebook-instance`/`stop-*` → 2
- [x] 1.10 Add `glue` entries: `get-*`/`list-*`/`batch-get-*` → 0, `create-*`/`update-*`/`start-*`/`put-*` → 1, `delete-database`/`delete-table`/`delete-crawler`/`delete-job`/`batch-delete-*` → 2
- [x] 1.11 Add `stepfunctions` entries: `describe-*`/`list-*`/`get-*` → 0, `create-*`/`update-*`/`start-*`/`tag-*` → 1, `delete-state-machine`/`delete-activity`/`stop-execution`/`untag-*` → 2
- [x] 1.12 Add `elasticbeanstalk` entries: `describe-*`/`list-*` → 0, `create-*`/`update-*` → 1, `terminate-environment`/`delete-application`/`delete-application-version` → 2
- [x] 1.13 Add `sts` entries: `get-*`/`decode-*` → 0, `assume-role`/`assume-role-with-*`/`get-federation-token`/`get-session-token` → 1
- [x] 1.14 Add `TIER_3_SUBSTRINGS` entry for `("aws elasticache delete-replication-group", "")` when dangerous patterns warrant it (review during implementation)
- [x] 1.15 Write unit tests for all new tier entries: at least one read (tier 0), one write (tier 1), and one destructive (tier 2) test per service added

## 2. Audit Log Module

- [x] 2.1 Create `src/aaws/audit.py` with `AuditEntry` dataclass (timestamp, command, tier, profile, region, exit_code, success, mode, duration_ms) — exit_code is `int` where -1 = crash, -2 = interrupted, 0 = success, 1-255 = AWS CLI error
- [x] 2.2 Implement `append(entry: AuditEntry, config: AuditConfig)` that serialises to JSON line and appends to the audit file, creating parent dirs if needed
- [x] 2.3 Implement file rotation: before writing, check file size against `max_size_mb`; rotate `audit.jsonl` → `.1` → `.2`, discard `.2` if it exists (concurrent rotation is an accepted benign race)
- [x] 2.4 Implement concurrent write safety: `O_APPEND` on POSIX, `msvcrt.locking` on Windows
- [x] 2.5 Wrap all file I/O in `append()` with try/except, log warning via `logging.getLogger("aaws.audit").warning(...)`, never raise — use Python logging (not bare stderr) because stderr is swallowed in MCP stdio transport
- [x] 2.6 Add `AuditConfig` to `config.py`: `enabled: bool = True`, `path: Optional[str] = None`, `max_size_mb: int = 10`
- [x] 2.7 Write unit tests for `audit.append()`: entry written as valid JSONL, file created on first write, entries appended not overwritten
- [x] 2.8 Write unit tests for rotation: rotation triggered at threshold, oldest file discarded, new file created
- [x] 2.9 Write unit tests for failure handling: unwritable path produces logging warning, no exception raised
- [x] 2.10 Write unit tests for interrupted execution audit: exit_code -2 for KeyboardInterrupt, exit_code -1 for OSError

## 3. MCP Safety Gate

- [x] 3.1 Add config loading to MCP server `main()`: call `load_config()` with fallback to `AawsConfig()` defaults, cache as module-level variable
- [x] 3.2 Implement `_extract_profile(command: str, default: str) -> str` helper that parses `--profile` from the command string via `shlex.split` and returns the embedded profile value if present, otherwise the default
- [x] 3.3 Modify `execute_aws_command` to call `classify()` on the command before execution; for tier 0, execute and return result with added `tier`/`requires_confirmation: false`/`executed: true` fields
- [x] 3.4 For tier >= 1 in `execute_aws_command`, return `{requires_confirmation: true, tier: N, tier_label: "...", executed: false}` without executing — `auto_execute_tier` config is NOT applied in MCP mode
- [x] 3.5 Add protected-profile check to `execute_aws_command` using `_extract_profile()` to determine effective profile from command string (authoritative) or parameter (fallback); block if `is_protected_profile(effective_profile, config.safety.protected_profiles)` and tier > 0
- [x] 3.6 Create `execute_confirmed_aws_command` MCP tool: accepts command/profile/region, validates starts with `"aws "`, re-classifies command via `classify()`, checks protected profile via `_extract_profile()`, injects profile/region if not present, executes, returns result including `tier` field. Docstring instructs agents to only call after user confirmation.
- [x] 3.7 Update `classify_aws_command` docstring from "IMPORTANT: Always call this BEFORE execute_aws_command" to describe it as a preview/lookahead tool for checking risk tier before presenting a command to the user
- [x] 3.8 Add `audit_writable: bool` field to `check_aws_environment()` response — test-write to audit path, report health
- [x] 3.9 Write unit tests for `execute_aws_command` tier gating: tier 0 executes, tier 1/2/3 return without executing
- [x] 3.10 Write unit tests for `auto_execute_tier` ignored in MCP: config set to 1, tier 1 command still returns `requires_confirmation: true`
- [x] 3.11 Write unit tests for protected-profile blocking in both `execute_aws_command` and `execute_confirmed_aws_command` — test both parameter profile and embedded `--profile` in command string
- [x] 3.12 Write unit tests for `execute_confirmed_aws_command`: valid command executes with re-classification, non-aws command rejected, tier included in response
- [x] 3.13 Write unit test for config fallback: MCP server starts without config file, uses safe defaults
- [x] 3.14 Write unit test for `_extract_profile`: parses `--profile value`, returns default when absent, handles edge cases (no value after flag)
- [x] 3.15 Write unit test for `check_aws_environment` includes `audit_writable` field
- [x] 3.16 Update existing MCP tests that call `execute_aws_command` to account for new return shape

## 4. Audit Integration

- [x] 4.1 Add audit integration in `cli.py` using try/finally wrapper: `start = time.monotonic()`, try execute, except KeyboardInterrupt (exit_code=-2) and Exception (exit_code=-1), finally `audit.append(...)` with `mode="cli"`, then re-raise
- [x] 4.2 Add audit integration in `session.py` using same try/finally pattern with `mode="session"`
- [x] 4.3 Add audit integration in `mcp_server.py` for `execute_aws_command` (tier 0 path) and `execute_confirmed_aws_command` using try/finally with `mode="mcp"` — profile in audit entry uses `_extract_profile()` value
- [x] 4.4 Ensure audit is skipped when `config.audit.enabled is False`
- [x] 4.5 Write integration test: full pipeline (translate → classify → execute → format) produces an audit entry with correct fields
- [x] 4.6 Write integration test: MCP execute_confirmed path produces an audit entry with re-classified tier
- [x] 4.7 Write integration test: KeyboardInterrupt during execute produces audit entry with exit_code -2
