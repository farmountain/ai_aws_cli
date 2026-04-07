"""MCP server for aaws — exposes AWS CLI tools to Claude Code.

Allows users with a Claude Code subscription to use aaws without
configuring any LLM provider. Claude Code handles natural language
translation; this server provides safety classification, command
execution, and output formatting.

Usage:
    claude mcp add --scope user aaws -- python -m aaws.mcp_server
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__

logger = logging.getLogger("aaws.mcp_server")

mcp = FastMCP(
    "aaws",
    instructions="AI-assisted AWS CLI — classify, execute, and format AWS commands safely.",
)

# ── Module-level config (loaded once in main()) ────────────────────────────

_config: Any = None  # AawsConfig instance, set in main()
_audit_config: Any = None  # AuditConfig instance for audit subsystem


def _get_config() -> Any:
    """Return the cached config, falling back to safe defaults."""
    global _config  # noqa: PLW0603
    if _config is None:
        from .config import AawsConfig  # noqa: PLC0415
        _config = AawsConfig()
    return _config


def _get_audit_config() -> Any:
    """Return the AuditConfig from the cached config."""
    global _audit_config  # noqa: PLW0603
    if _audit_config is not None:
        return _audit_config
    from .audit import AuditConfig  # noqa: PLC0415
    cfg = _get_config()
    audit_section = getattr(cfg, "audit", None)
    if audit_section is not None:
        _audit_config = AuditConfig(
            enabled=getattr(audit_section, "enabled", True),
            path=getattr(audit_section, "path", None),
            max_size_mb=getattr(audit_section, "max_size_mb", 10),
        )
    else:
        _audit_config = AuditConfig()
    return _audit_config


# ── Helpers ────────────────────────────────────────────────────────────────


def _extract_profile(command: str, default: str) -> str:
    """Parse --profile from the command string, returning the value if present.

    Uses shlex.split to handle quoting. Returns *default* when --profile
    is absent or has no value after the flag.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return default

    for i, token in enumerate(tokens):
        if token == "--profile" and i + 1 < len(tokens):
            return tokens[i + 1]
    return default


_TIER_LABELS = {0: "Read-only", 1: "Write", 2: "Destructive", 3: "Catastrophic"}


# ── Tool 1: classify_aws_command ─────────────────────────────────────────────


@mcp.tool()
def classify_aws_command(command: str) -> dict[str, Any]:
    """Preview the safety risk tier of an AWS CLI command (0-3).

    Use this as a lookahead tool to check the risk tier before presenting
    a command to the user. This does NOT execute the command.

    Tiers:
      0 = Read-only (describe, list, get) — safe to auto-execute
      1 = Write (create, put, update, start) — ask user to confirm
      2 = Destructive (delete, terminate, detach) — warn user strongly
      3 = Catastrophic (bulk delete, org-level ops) — refuse unless user insists

    Args:
        command: The full AWS CLI command string (must start with 'aws ')
    """
    from .safety.classifier import classify  # noqa: PLC0415

    tier = classify(command, llm_tier=1)  # Unknown commands default to Write (conservative)

    return {
        "command": command,
        "tier": tier,
        "tier_label": _TIER_LABELS.get(tier, "Unknown"),
        "should_confirm": tier >= 1,
        "is_catastrophic": tier == 3,
    }


# ── Tool 2: execute_aws_command ──────────────────────────────────────────────


@mcp.tool()
def execute_aws_command(
    command: str,
    profile: str = "default",
    region: str = "us-east-1",
) -> dict[str, Any]:
    """Execute an AWS CLI command with server-side safety enforcement.

    The command is classified before execution:
    - Tier 0 (read-only): executed immediately, result returned.
    - Tier >= 1: NOT executed. Returns classification with
      ``requires_confirmation: true`` so the agent can confirm with the user
      and then call ``execute_confirmed_aws_command``.

    The ``auto_execute_tier`` config setting is NOT applied in MCP mode —
    all tier >= 1 commands require explicit confirmation via
    ``execute_confirmed_aws_command``.

    Profile and region are injected as --profile and --region flags if not
    already present in the command.

    Args:
        command: The full AWS CLI command (must start with 'aws ')
        profile: AWS profile name to use
        region: AWS region to use
    """
    if not command.strip().startswith("aws "):
        return {
            "stdout": "",
            "stderr": "Error: command must start with 'aws '",
            "exit_code": 1,
            "success": False,
        }

    from .safety.classifier import classify, is_protected_profile  # noqa: PLC0415

    tier = classify(command, llm_tier=1)

    # Determine effective profile — embedded --profile takes precedence
    effective_profile = _extract_profile(command, profile)

    # Protected-profile check
    config = _get_config()
    protected_profiles: list[str] = list(
        getattr(getattr(config, "safety", None), "protected_profiles", [])
    )
    if tier > 0 and is_protected_profile(effective_profile, protected_profiles):
        return {
            "stdout": "",
            "stderr": f"Blocked: profile '{effective_profile}' is protected. "
                      f"Write/destructive operations are not allowed on this profile.",
            "exit_code": 1,
            "success": False,
            "tier": tier,
            "tier_label": _TIER_LABELS.get(tier, "Unknown"),
            "requires_confirmation": False,
            "executed": False,
            "blocked_by": "protected_profile",
        }

    # Tier >= 1: return classification, do NOT execute
    if tier >= 1:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "success": True,
            "tier": tier,
            "tier_label": _TIER_LABELS.get(tier, "Unknown"),
            "requires_confirmation": True,
            "is_catastrophic": tier == 3,
            "executed": False,
        }

    # Tier 0: execute and return
    from .executor import execute  # noqa: PLC0415

    # Inject --profile and --region if not already present
    if "--profile" not in command and profile != "default":
        command += f" --profile {profile}"
    if "--region" not in command:
        command += f" --region {region}"

    # Audit
    start = time.monotonic()
    exit_code = 0
    try:
        result = execute(command)
        exit_code = result.exit_code
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "success": result.success,
            "tier": tier,
            "tier_label": _TIER_LABELS.get(tier, "Unknown"),
            "requires_confirmation": False,
            "executed": True,
        }
    except KeyboardInterrupt:
        exit_code = -2
        raise
    except Exception:
        exit_code = -1
        raise
    finally:
        _audit_command(command, tier, effective_profile, region, exit_code, start)


# ── Tool 2b: execute_confirmed_aws_command ──────────────────────────────────


@mcp.tool()
def execute_confirmed_aws_command(
    command: str,
    profile: str = "default",
    region: str = "us-east-1",
) -> dict[str, Any]:
    """Execute an AWS CLI command after the user has confirmed.

    ONLY call this tool after:
    1. Calling ``execute_aws_command`` and receiving ``requires_confirmation: true``
    2. Showing the command and its risk tier to the user
    3. Receiving explicit user confirmation to proceed

    The command is re-classified for accurate audit logging. Protected-profile
    rules are enforced.

    Args:
        command: The full AWS CLI command (must start with 'aws ')
        profile: AWS profile name to use
        region: AWS region to use
    """
    if not command.strip().startswith("aws "):
        return {
            "stdout": "",
            "stderr": "Error: command must start with 'aws '",
            "exit_code": 1,
            "success": False,
        }

    from .safety.classifier import classify, is_protected_profile  # noqa: PLC0415

    tier = classify(command, llm_tier=1)

    # Determine effective profile — embedded --profile takes precedence
    effective_profile = _extract_profile(command, profile)

    # Protected-profile check
    config = _get_config()
    protected_profiles: list[str] = list(
        getattr(getattr(config, "safety", None), "protected_profiles", [])
    )
    if tier > 0 and is_protected_profile(effective_profile, protected_profiles):
        return {
            "stdout": "",
            "stderr": f"Blocked: profile '{effective_profile}' is protected. "
                      f"Write/destructive operations are not allowed on this profile.",
            "exit_code": 1,
            "success": False,
            "tier": tier,
            "tier_label": _TIER_LABELS.get(tier, "Unknown"),
            "blocked_by": "protected_profile",
        }

    from .executor import execute  # noqa: PLC0415

    # Inject --profile and --region if not already present
    if "--profile" not in command and profile != "default":
        command += f" --profile {profile}"
    if "--region" not in command:
        command += f" --region {region}"

    start = time.monotonic()
    exit_code = 0
    try:
        result = execute(command)
        exit_code = result.exit_code
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "success": result.success,
            "tier": tier,
            "tier_label": _TIER_LABELS.get(tier, "Unknown"),
        }
    except KeyboardInterrupt:
        exit_code = -2
        raise
    except Exception:
        exit_code = -1
        raise
    finally:
        _audit_command(command, tier, effective_profile, region, exit_code, start)


# ── Tool 3: format_aws_output ───────────────────────────────────────────────


@mcp.tool()
def format_aws_output(raw_json: str) -> str:
    """Format raw AWS CLI JSON output into a readable plain-text table or card.

    Pass the stdout from execute_aws_command to get formatted output.
    Detects the JSON shape (list of resources -> table, single resource -> card).
    Non-JSON output (e.g., plain text from 'aws s3 ls') is returned as-is.

    Args:
        raw_json: Raw output string from an AWS CLI command
    """
    from .formatter import format_to_string  # noqa: PLC0415

    return format_to_string(raw_json)


# ── Tool 4: list_safety_tiers ────────────────────────────────────────────────


@mcp.tool()
def list_safety_tiers(service: str = "") -> str:
    """List safety tier classifications for known AWS CLI commands.

    Shows which commands are read-only (tier 0), write (tier 1),
    destructive (tier 2), or catastrophic (tier 3).

    Optionally filter by AWS service name (e.g., 'ec2', 's3', 'iam').

    Args:
        service: Optional service filter (e.g., 'ec2', 's3', 'iam'). Empty for all.
    """
    from .safety.tier_table import TIER_TABLE  # noqa: PLC0415

    tier_labels = {0: "Read-only", 1: "Write", 2: "Destructive", 3: "Catastrophic"}

    entries = sorted(TIER_TABLE.items())
    if service:
        service_lower = service.lower()
        entries = [(k, v) for k, v in entries if service_lower in k.lower()]

    if not entries:
        return f"No tier entries found for service: {service!r}"

    lines = [f"{'Command Prefix':<55} {'Tier':<5} {'Label'}"]
    lines.append("-" * 75)
    for prefix, tier in entries:
        lines.append(f"{prefix:<55} {tier:<5} {tier_labels.get(tier, '?')}")

    return "\n".join(lines)


# ── Tool 5: check_aws_environment ────────────────────────────────────────────


@mcp.tool()
def check_aws_environment() -> dict[str, Any]:
    """Check the local AWS environment: CLI availability, active profile, region.

    Call this at the start of a session to verify the user's AWS setup
    before running any commands. Includes audit log health check.
    """
    aws_available = shutil.which("aws") is not None

    active_profile = os.environ.get(
        "AWS_PROFILE", os.environ.get("AWS_DEFAULT_PROFILE", "default")
    )

    active_region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION"))

    if not active_region and aws_available:
        try:
            result = subprocess.run(
                ["aws", "configure", "get", "region", "--profile", active_profile],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                active_region = result.stdout.strip()
        except Exception:
            pass

    # Audit health check
    from .audit import check_writable  # noqa: PLC0415
    audit_cfg = _get_audit_config()
    audit_writable = check_writable(audit_cfg) if audit_cfg.enabled else True

    return {
        "aws_cli_available": aws_available,
        "active_profile": active_profile,
        "active_region": active_region or "not configured",
        "audit_writable": audit_writable,
    }


# ── Audit helper ─────────────────────────────────────────────────────────────


def _audit_command(
    command: str,
    tier: int,
    profile: str,
    region: str,
    exit_code: int,
    start: float,
) -> None:
    """Write an audit entry if auditing is enabled."""
    audit_cfg = _get_audit_config()
    if not audit_cfg.enabled:
        return
    try:
        from .audit import AuditEntry, append  # noqa: PLC0415
        duration_ms = int((time.monotonic() - start) * 1000)
        entry = AuditEntry(
            command=command,
            tier=tier,
            profile=profile,
            region=region,
            exit_code=exit_code,
            success=exit_code == 0,
            mode="mcp",
            duration_ms=duration_ms,
        )
        append(entry, audit_cfg)
    except Exception as exc:
        logger.warning("MCP audit failed: %s", exc)


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for aaws-mcp command and python -m aaws.mcp_server."""
    global _config  # noqa: PLW0603

    # Load config once at startup, fall back to safe defaults
    try:
        from .config import load_config  # noqa: PLC0415
        _config = load_config()
    except Exception:
        from .config import AawsConfig  # noqa: PLC0415
        _config = AawsConfig()
        logger.warning("Config not found, using safe defaults")

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
