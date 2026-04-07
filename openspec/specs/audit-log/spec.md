# Capability: Audit Log

## Purpose

Append-only JSONL audit trail capturing every executed AWS CLI command across all modes (CLI, session, MCP), with configurable rotation and fault-tolerant writes.

## Requirements

### Requirement: Audit log captures every executed command
The system SHALL append an audit entry to a JSONL file for every AWS CLI command that is executed, regardless of mode (CLI, session, MCP). Each entry SHALL contain: `timestamp` (ISO 8601), `command` (the AWS CLI command string), `tier` (risk tier 0-3), `profile` (effective profile — parsed from command string `--profile` flag, falling back to resolved profile parameter), `region` (AWS region used), `exit_code` (subprocess return code, or -1 for crash, -2 for interrupt), `success` (boolean), `mode` (one of `"cli"`, `"session"`, `"mcp"`), and `duration_ms` (execution time in milliseconds).

#### Scenario: CLI mode logs a successful read command
- **WHEN** a user runs `aaws "list my S3 buckets"` and the command `aws s3api list-buckets` succeeds
- **THEN** the audit log contains an entry with `mode: "cli"`, `command: "aws s3api list-buckets ..."`, `tier: 0`, `success: true`, `exit_code: 0`, and a valid `timestamp` and `duration_ms`

#### Scenario: Session mode logs a failed command
- **WHEN** a user runs a command in session mode and it fails with exit code 1
- **THEN** the audit log contains an entry with `mode: "session"`, `success: false`, `exit_code: 1`

#### Scenario: MCP mode logs an executed command
- **WHEN** an MCP client calls `execute_aws_command` or `execute_confirmed_aws_command` and the command is executed
- **THEN** the audit log contains an entry with `mode: "mcp"` and the command details

#### Scenario: Blocked commands are not logged as executed
- **WHEN** `execute_aws_command` returns `requires_confirmation: true` without executing
- **THEN** no audit entry is written (the command was not executed)

### Requirement: Interrupted and crashed executions are audited
The audit integration SHALL use a `try/finally` wrapper around `execute()` to guarantee logging even when execution is interrupted or crashes. Interrupted executions (KeyboardInterrupt) SHALL be logged with `exit_code: -2`. Crashed executions (any other exception from `execute()`) SHALL be logged with `exit_code: -1`. The `finally` block SHALL re-raise the original exception after logging.

#### Scenario: User interrupts a long-running command with Ctrl+C
- **WHEN** a user presses Ctrl+C during execution of `aws cloudformation deploy ...`
- **THEN** the audit log contains an entry with `exit_code: -2`, `success: false`, and a `duration_ms` reflecting how long the command ran before interruption
- **AND** the KeyboardInterrupt propagates normally after logging

#### Scenario: Execution crashes with OSError
- **WHEN** `execute()` raises an `OSError` (e.g., too many open files)
- **THEN** the audit log contains an entry with `exit_code: -1`, `success: false`
- **AND** the OSError propagates normally after logging

#### Scenario: Normal execution logs in finally block
- **WHEN** a command executes successfully
- **THEN** the audit entry is written in the `finally` block with the actual `exit_code` and `duration_ms`

### Requirement: Audit log stored as append-only JSONL
The audit log SHALL be stored at `{user_config_dir}/aaws/audit.jsonl` (using `platformdirs.user_config_dir`). Each entry SHALL be a single JSON object on one line, terminated by a newline. The file SHALL be opened in append mode for each write.

#### Scenario: Audit file is created on first write
- **WHEN** the audit log file does not exist and a command is executed
- **THEN** the file is created with the parent directory, and the first entry is written

#### Scenario: Entries are appended, not overwritten
- **WHEN** two commands are executed sequentially
- **THEN** the audit file contains two lines, each a valid JSON object, in chronological order

### Requirement: Audit log rotation by size
The audit module SHALL rotate the log file when it exceeds `max_size_mb` (configurable, default 10 MB). Rotation SHALL rename `audit.jsonl` to `audit.jsonl.1` (and `audit.jsonl.1` to `audit.jsonl.2` if it exists). At most 2 rotated files SHALL be retained. Rotation SHALL occur before writing a new entry when the file size exceeds the threshold. Concurrent rotation from multiple processes is accepted as a benign race condition (worst case: one entry lands in a rotated file, no corruption or data loss).

#### Scenario: Log rotated when exceeding max size
- **WHEN** `audit.jsonl` exceeds 10 MB and a new command is executed
- **THEN** `audit.jsonl` is renamed to `audit.jsonl.1` and a new `audit.jsonl` is created with the new entry

#### Scenario: Oldest rotated file is discarded
- **WHEN** `audit.jsonl.1` and `audit.jsonl.2` both exist and rotation is triggered
- **THEN** `audit.jsonl.2` is deleted, `audit.jsonl.1` is renamed to `audit.jsonl.2`, and `audit.jsonl` is renamed to `audit.jsonl.1`

### Requirement: Audit config section in AawsConfig
The `AawsConfig` model SHALL include an `AuditConfig` section with fields: `enabled` (bool, default `true`), `path` (optional string, overrides default path), `max_size_mb` (int, default 10). The audit module SHALL respect the `enabled` flag and skip logging when it is `false`.

#### Scenario: Audit disabled in config
- **WHEN** the config has `audit.enabled: false` and a command is executed
- **THEN** no audit entry is written

#### Scenario: Custom audit path
- **WHEN** the config has `audit.path: "/var/log/aaws/audit.jsonl"` and a command is executed
- **THEN** the audit entry is written to `/var/log/aaws/audit.jsonl` instead of the default location

#### Scenario: Default config enables audit
- **WHEN** no audit section is present in config
- **THEN** audit logging is enabled with default path and 10 MB rotation

### Requirement: Audit write failures do not block execution
The `audit.append()` function SHALL catch all exceptions during file I/O and log a warning via Python's `logging` module (`logging.getLogger("aaws.audit").warning(...)`). Command execution SHALL never be blocked or delayed by audit log failures. Python `logging` is used instead of bare `print(file=sys.stderr)` because stderr is not reliably visible in MCP's stdio transport.

#### Scenario: Filesystem full during audit write
- **WHEN** the filesystem is full and `audit.append()` is called
- **THEN** a warning is logged via `logging.warning` and the function returns without raising

#### Scenario: Audit path not writable
- **WHEN** the audit log path is not writable and a command is executed
- **THEN** the command executes successfully, a warning is logged, and no exception propagates

### Requirement: Concurrent write safety
The audit module SHALL use `O_APPEND` mode on POSIX systems and file locking on Windows to ensure concurrent writes from multiple aaws processes do not corrupt the log. Each write SHALL be a single line under 1 KB.

#### Scenario: Two processes write simultaneously
- **WHEN** a CLI process and an MCP server process both execute commands at the same time
- **THEN** both audit entries are written as complete, valid JSON lines with no interleaving or corruption
