## Context

`aaws` is a new Python CLI tool built from scratch. There is no existing codebase — all decisions are greenfield. The core challenge is building a reliable, safe pipeline from natural language input to AWS CLI execution, where mistakes can have real (irreversible, costly) consequences.

The target user is a developer or DevOps engineer who already has the AWS CLI configured and wants to stop context-switching to documentation for syntax lookup.

## Goals / Non-Goals

**Goals:**
- Translate natural language to `aws` CLI commands using an LLM
- Gate destructive operations behind explicit user confirmation
- Format AWS CLI output into readable terminal UI
- Provide a conversational REPL mode (`aaws session`)
- Support AWS Bedrock (default) and OpenAI as LLM providers
- Ship as `pip install aaws` with PyPI distribution via GitHub Actions

**Non-Goals:**
- Agentic multi-step autonomous workflows (v1 is command-at-a-time)
- Direct boto3 API execution (v1 delegates entirely to `aws` CLI subprocess)
- Web UI or browser-based interface
- Team/org-shared configuration
- Persistent session history written to disk (v1 session state is in-process only)
- AWS cost estimation before execution
- Support for Python versions below 3.11

## Decisions

### D1: Subprocess over boto3 for execution

**Decision**: Execute commands by calling the `aws` CLI via `subprocess.run(shlex.split(command))`, never `shell=True`.

**Rationale**: The LLM produces a command string (e.g., `aws ec2 describe-instances --region us-east-1`). Subprocess keeps that string directly auditable — users can see and copy exactly what will run. The `aws` CLI also handles all credential resolution, pagination, endpoint configuration, and retry logic that would otherwise need to be reimplemented against boto3. Shell injection is prevented by using `shlex.split` to tokenize and passing a list (not a string) to `subprocess.run`.

**Alternatives considered**: Direct boto3 calls would remove the `aws` CLI dependency but require the LLM to produce structured `{service, method, params}` dicts — a harder structured output problem with a much larger surface area (300+ services). This fits v2 if agentic multi-step workflows become a priority.

---

### D2: Pluggable LLM provider with AWS Bedrock as default

**Decision**: Define a `LLMProvider` protocol and ship two concrete implementations: `BedrockProvider` (default) and `OpenAIProvider`. Do not use LiteLLM.

**Rationale**: Bedrock uses the same AWS credentials as everything else — no extra API key, no data leaving the AWS account, cost on the same bill. This aligns perfectly with the `aaws` user who already has AWS configured. OpenAI is supported as an alternative for users without Bedrock access. LiteLLM was rejected because it adds 50+ MB of dependencies to a CLI tool where startup time and install footprint matter.

**Alternatives considered**: Single provider (OpenAI only) — simpler but breaks the privacy story. LiteLLM — generic but too heavy. Anthropic direct SDK — added later if demand exists.

---

### D3: Structured output via tool/function calling

**Decision**: Use the LLM provider's tool/function calling mechanism (not free-form text prompting) to guarantee structured output. The tool schema defines: `command` (string), `explanation` (string), `risk_tier` (integer 0–3), `clarification` (string | null).

**Rationale**: Prompting the model to "respond in JSON" occasionally produces markdown-fenced JSON, trailing commentary, or malformed output. Function/tool calling constrains the model to emit a validated schema and is available on all supported providers (Bedrock Claude, OpenAI). Fallback: strip code fences and attempt JSON parse if tool calling is unavailable.

---

### D4: Three-tier safety classification with static table + LLM fallback

**Decision**: Classify commands into 4 tiers (0=read, 1=write, 2=destructive, 3=catastrophic). Classification uses a static lookup table as the fast path; if a command is not found, the LLM re-classifies using context. The LLM already provides `risk_tier` in its output (Decision D3).

**Rationale**: A static table handles 90%+ of common cases instantly with zero LLM cost. It also provides a deterministic safety floor that cannot be overridden by a confused LLM. Novel or complex commands fall through to LLM classification.

**Tier definitions and gates:**
- Tier 0 (read/list/describe): auto-execute
- Tier 1 (create/put/update): show command + confirm y/n
- Tier 2 (delete/terminate/detach): show + warn + require confirmation + offer `--dry-run` if supported
- Tier 3 (bulk-delete/IAM-nuke/account-level): refuse by default; require `--i-accept-responsibility` flag

---

### D5: Typer + Rich for CLI and terminal UI

**Decision**: Use [Typer](https://typer.tiangolo.com/) for CLI argument parsing and [Rich](https://rich.readthedocs.io/) for all terminal output (tables, panels, syntax highlighting, progress).

**Rationale**: Typer gives type-annotated CLI commands with minimal boilerplate. Rich is the standard library for terminal UI in Python and handles tables, markdown, JSON syntax highlighting, and styled panels with a clean API. Both are actively maintained with large communities.

---

### D6: Python 3.11+ minimum

**Decision**: Require Python 3.11 or higher.

**Rationale**: 3.11 is the lowest version that is both not EOL (EOL Oct 2027) and available by default on major platforms (Ubuntu 24.04, Amazon Linux 2023, Homebrew 2026). It gains `match/case` (useful for tier routing), `tomllib` in stdlib, and improved exception messages. Drops support for nothing in active use.

---

### D7: XDG-compliant config paths

**Decision**: Store config at `~/.config/aaws/config.yaml` on Linux/macOS and `%APPDATA%\aaws\config.yaml` on Windows. Support `AAWS_` prefixed environment variable overrides for all settings.

**Rationale**: XDG compliance is the expected standard on Linux for CLI tools. Environment variable overrides are essential for CI/CD (GitHub Actions, Jenkins) where file-based config is awkward. `python-platformdirs` provides the correct path per OS.

## Risks / Trade-offs

[LLM output quality is empirical] → Mitigation: Test prompt against a large suite of real AWS task descriptions. Keep temperature at 0.1 for determinism. Version the system prompt and track regressions.

[LLM can hallucinate flags] → Mitigation: Validate that output starts with `aws `, show the full command to the user before executing. Consider post-generation validation against `aws <service> help` output in v2.

[Shell injection via crafted NL input] → Mitigation: `shlex.split` + pass list to `subprocess.run(..., shell=False)`. Never interpolate user input into a shell string.

[Bedrock model access not enabled] → Mitigation: Detect `AccessDeniedException` on Bedrock calls, surface a specific error: "Enable model access for `<model>` in the AWS Console → Bedrock → Model access."

[aws CLI not installed] → Mitigation: Check for `aws` in PATH on startup; fail fast with clear install instructions if missing.

[Protected profile misconfiguration] → Mitigation: Case-insensitive and glob pattern matching for protected profile names (e.g., `prod-*` matches `prod-us-east-1`).
