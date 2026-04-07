## Context

The `aaws` tool has two execution modes: standalone CLI and MCP server. The standalone CLI enforces a full safety pipeline (translate → classify → safety gate → execute → format). The MCP server exposes individual tools (`classify_aws_command`, `execute_aws_command`, etc.) but delegates safety sequencing to the calling agent via docstring instructions — no server-side enforcement.

The static tier table in `safety/tier_table.py` covers 15 AWS services (~120 entries). Unknown commands fall back to tier 1 in MCP mode (hardcoded in `mcp_server.py:51`) or to the LLM-assigned tier in standalone mode. Neither mode logs executed commands.

Key files:
- `src/aaws/mcp_server.py` — MCP tool definitions (5 tools, no safety gate)
- `src/aaws/safety/classifier.py` — `classify()`, `apply_safety_gate()`, `is_protected_profile()`
- `src/aaws/safety/tier_table.py` — `TIER_TABLE` dict, `TIER_3_SUBSTRINGS` list
- `src/aaws/executor.py` — `execute()` subprocess wrapper
- `src/aaws/config.py` — `AawsConfig` with `SafetyConfig` section
- `src/aaws/cli.py` — standalone CLI pipeline
- `src/aaws/session.py` — interactive REPL

## Goals / Non-Goals

**Goals:**
- MCP `execute_aws_command` enforces classification and protected-profile rules server-side, matching the standalone CLI's safety guarantees
- Tier table covers the most common AWS services where `delete-*` operations carry data-loss risk
- Every executed AWS command is logged to an append-only audit file across all three modes
- Changes are backward-compatible for MCP clients that already call classify before execute (they just get a richer response)

**Non-Goals:**
- Streaming/progress for long-running commands (separate concern, no safety implication)
- Session mode `--yes`/`--dry-run` flags (small scope, separate change)
- History persistence or adaptive bounding (UX polish, separate change)
- Cost/latency observability (can layer on audit log later, separate change)
- Authentication or encryption of the audit log (local file, same trust boundary as AWS credentials)

## Decisions

### Decision 1: Inline safety gate in `execute_aws_command` (not a token-based protocol)

**Chosen:** `execute_aws_command` will internally call `classify()` and `is_protected_profile()` before executing. For tier >= 1, it returns the classification and a `requires_confirmation: true` flag but does NOT execute. A separate tool `execute_confirmed_aws_command` accepts the same command and executes it unconditionally (tier-0 behavior), to be called only after the agent has confirmed with the user.

**Alternatives considered:**
- *Token-based protocol* — classify returns a signed token (HMAC of command + tier + timestamp), execute requires it. Prevents TOCTOU command substitution between tool calls. Implementation is ~8 lines (server-side secret via `os.urandom(32)` at startup, HMAC validation). However, tokens prevent accidental mutation but not intentional deception — the agent controls what it shows the user regardless of token binding. In MCP's stdio architecture, Claude Code's UI makes tool call arguments visible, so command substitution is not a stealth attack.
- *Single tool with `confirmed: bool` parameter* — simpler API surface, but agents could trivially pass `confirmed=true` without actually confirming. Two separate tools make the "must confirm" step structurally visible in the agent's tool-use trace.

**Rationale:** The threat model is an agent skipping or misunderstanding the safety flow, not a malicious actor injecting commands. Structural separation (two tools) makes the correct flow the path of least resistance. The `execute_confirmed_aws_command` tool will re-classify the command for accurate audit logging, catching any accidental mutation between calls (the audit trail shows what actually ran at what tier).

### Decision 2: MCP server loads config once at startup

**Chosen:** The MCP server will load `AawsConfig` via `load_config()` at module-level initialization (in the `main()` function) and cache it. Protected-profile patterns and `auto_execute_tier` are read from this cached config.

**Alternatives considered:**
- *Load config on every tool call* — correct but slow, filesystem I/O on every invocation.
- *Pass config values as tool parameters* — pushes config responsibility to the agent, which doesn't know the user's safety preferences.

**Rationale:** Config changes during a running MCP session are rare (the user restarts Claude Code). Module-level load is simple and matches the CLI's behavior (config loaded once per invocation).

### Decision 3: Audit log as JSONL, not SQLite

**Chosen:** Append-only JSONL file at `~/.config/aaws/audit.jsonl` (using `platformdirs.user_config_dir`). One JSON object per line. Rotation by renaming to `audit.jsonl.1` when the file exceeds a configurable `max_size_mb` (default 10 MB), keeping at most 2 rotated files.

**Alternatives considered:**
- *SQLite* — better for querying, but requires a dependency (already available in stdlib). However, append-only writes with potential concurrent access from multiple aaws processes (CLI + MCP) makes SQLite WAL mode necessary, adding complexity. JSONL with file-level locking is simpler.
- *No rotation* — simpler, but unbounded growth. At ~200 bytes per entry, 10 MB ≈ 50,000 entries, which is roughly 1-2 years of heavy usage.

**Rationale:** JSONL is the simplest format that supports append-only, concurrent-safe (with `O_APPEND`), greppable, and parseable. Rotation prevents unbounded growth without introducing database complexity.

### Decision 4: Tier table expansion strategy — prefix-based, same pattern

**Chosen:** Add entries to the existing `TIER_TABLE` dict following the established prefix-matching pattern. Add `TIER_3_SUBSTRINGS` entries for catastrophic patterns (e.g., `aws elasticache delete-replication-group` without `--retain-primary-cluster`).

No structural change to `classifier.py` — the longest-prefix-match algorithm handles new entries without modification.

**Services to add (prioritised by data-loss risk):**

| Service | Entries | Priority |
|---------|---------|----------|
| logs (CloudWatch Logs) | ~6 | P1 |
| kinesis | ~5 | P1 |
| elasticache | ~6 | P1 |
| autoscaling | ~6 | P1 |
| cognito-idp | ~6 | P1 |
| redshift | ~5 | P1 |
| elbv2 | ~6 | P2 |
| apigateway | ~5 | P2 |
| sagemaker | ~6 | P2 |
| glue | ~5 | P2 |
| stepfunctions | ~4 | P3 |
| elasticbeanstalk | ~4 | P3 |
| sts | ~3 | P3 |

Total: ~67 new entries across 13 services.

### Decision 5: MCP ignores `auto_execute_tier` — agent trust model

**Chosen:** `execute_aws_command` in MCP mode always blocks tier >= 1 commands regardless of the `auto_execute_tier` config value. The config only applies to CLI and session modes (where a human sees each command before it runs).

**Alternatives considered:**
- *Respect auto_execute_tier in MCP* — would give parity with CLI, but `auto_execute_tier` was designed for human convenience ("don't make me type y/n"), not agent autonomy. The user set it before MCP existed. Inheriting it silently grants the agent write autonomy the user never intended.
- *Add separate `mcp_auto_execute_tier` config* — explicit control, but adds config complexity for a need no user has expressed yet. Can be added later (additive, non-breaking) if users request it.

**Rationale:** The `auto_execute_tier` setting was written for a human at a terminal who sees every command. In MCP mode, the agent decides what to run — the user expressed intent in natural language, not command-level approval. Granting agent autonomy should require explicit configuration, not inheritance from a human convenience setting. Users who want auto-approval in MCP mode can configure Claude Code's own permission system.

### Decision 6: Parse `--profile` from command string for protected-profile checks

**Chosen:** Both `execute_aws_command` and `execute_confirmed_aws_command` will parse the command string for an embedded `--profile` flag. The effective profile for safety checks is the embedded `--profile` value if present, otherwise the `profile` parameter. This is the authoritative profile used for `is_protected_profile()` and for the audit log entry.

**Alternatives considered:**
- *Check only the profile parameter* — misses embedded profiles. An agent could construct `"aws ec2 terminate-instances --profile prod-critical"` while passing `profile="dev"`, bypassing the protected-profile check.
- *Strip --profile from command and always inject from parameter* — single source of truth, but silently mutates the command (violates least surprise) and overrides the agent's explicit intent.
- *Check BOTH parameter and embedded --profile* — defence in depth, block if either matches. But this blocks commands where the agent correctly passes a protected profile in one place and an unprotected one in the other (arguably user error, not a valid flow).

**Rationale:** The embedded `--profile` is what `subprocess.run` actually uses — it determines which AWS account the command hits. The parameter is a hint for injection; the command string is ground truth. Parsing via `shlex.split` and searching for `--profile` is robust (handles both `--profile value` forms). Note: the CLI has the same theoretical vulnerability (LLM could embed a different profile), but it's mitigated because the LLM receives the correct profile as context and users see the command before confirming.

## Risks / Trade-offs

**[Risk] MCP breaking change for existing clients** → The `execute_aws_command` return shape changes (adds `tier`, `requires_confirmation` fields). Existing MCP clients that parse the response will see new fields but won't break (additive). Clients that call execute without classify will now get blocked for tier >= 1 instead of silent execution — this IS the desired behavior change, but it's breaking for agents that relied on the old permissive behavior.
*Mitigation:* Document in MCP tool descriptions. The old behavior was a safety bug, not a feature.

**[Risk] Config not found in MCP mode** → If the user hasn't run `aaws config init`, `load_config()` raises `ConfigNotFoundError`. MCP server must handle this gracefully.
*Mitigation:* Fall back to `AawsConfig()` defaults (empty protected profiles, auto_execute_tier=0). Log a warning in the audit log. The default config is safe (all writes require confirmation, no profiles are protected).

**[Risk] Audit log write failures** → Filesystem full, permissions, path doesn't exist.
*Mitigation:* `audit.append()` catches all exceptions and logs via Python `logging` module (not bare stderr, which is swallowed in MCP's stdio transport). Additionally, `check_aws_environment` will include an `audit_writable` boolean so agents can detect and surface the issue on session start.

**[Risk] Concurrent writes to audit log** → Multiple aaws processes (CLI session + MCP server) writing to the same file.
*Mitigation:* Use `O_APPEND` mode (atomic on POSIX for writes < PIPE_BUF). On Windows, use file locking via `msvcrt.locking`. Each write is a single line (< 1KB), well within atomic-write guarantees.

**[Risk] Concurrent rotation** → Two processes both see the file at the rotation threshold and attempt to rename simultaneously.
*Mitigation:* Accepted. Rotation occurs approximately once per 1-2 years of heavy usage. Concurrent rotation is vanishingly rare. In the worst case, one audit entry lands in a rotated file instead of the active file — no data corruption, no entry loss. Adding a lock file for rotation would add complexity for a non-problem.

**[Risk] TOCTOU command substitution** → Agent could pass a different command to `execute_confirmed_aws_command` than what was classified by `execute_aws_command`.
*Mitigation:* `execute_confirmed_aws_command` re-classifies the command and logs the actual tier in the audit entry. The substitution is detectable forensically. In MCP mode, Claude Code's UI makes tool call arguments visible, so substitution is not a stealth attack. Full prevention would require token binding (~8 lines of code), but the marginal benefit over re-classification is low given the threat model (agent error, not malice).

**[Risk] Interrupted/crashed executions not audited** → `KeyboardInterrupt` or `OSError` during `execute()` can skip the audit call.
*Mitigation:* Audit integration uses `try/finally` around `execute()`. Interrupted executions are logged with `exit_code: -2` (SIGINT), crashes with `exit_code: -1`. The `finally` block guarantees the audit entry is written even on exceptions.
