"""MCP server for aaws — exposes AWS CLI tools to Claude Code.

Allows users with a Claude Code subscription to use aaws without
configuring any LLM provider. Claude Code handles natural language
translation; this server provides safety classification, command
execution, and output formatting.

Usage:
    claude mcp add --scope user aaws -- python -m aaws.mcp_server
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import __version__

mcp = FastMCP(
    "aaws",
    instructions="AI-assisted AWS CLI — classify, execute, and format AWS commands safely.",
)


# ── Tool 1: classify_aws_command ─────────────────────────────────────────────


@mcp.tool()
def classify_aws_command(command: str) -> dict[str, Any]:
    """Classify an AWS CLI command into a safety risk tier (0-3).

    Tiers:
      0 = Read-only (describe, list, get) — safe to auto-execute
      1 = Write (create, put, update, start) — ask user to confirm
      2 = Destructive (delete, terminate, detach) — warn user strongly
      3 = Catastrophic (bulk delete, org-level ops) — refuse unless user insists

    IMPORTANT: Always call this BEFORE execute_aws_command to check risk level.
    For tier >= 1, confirm with the user before executing.
    For tier 3, refuse unless the user explicitly insists.

    Args:
        command: The full AWS CLI command string (must start with 'aws ')
    """
    from .safety.classifier import classify  # noqa: PLC0415

    tier = classify(command, llm_tier=1)  # Unknown commands default to Write (conservative)
    tier_labels = {0: "Read-only", 1: "Write", 2: "Destructive", 3: "Catastrophic"}

    return {
        "command": command,
        "tier": tier,
        "tier_label": tier_labels.get(tier, "Unknown"),
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
    """Execute an AWS CLI command and return stdout, stderr, and exit code.

    IMPORTANT SAFETY RULES — always call classify_aws_command first:
    - Tier 0 (read-only): safe to execute without asking
    - Tier 1 (write): ask the user for confirmation before executing
    - Tier 2 (destructive): warn the user strongly, explain consequences
    - Tier 3 (catastrophic): REFUSE to execute unless user explicitly insists

    The command must start with 'aws'. Profile and region are injected as
    --profile and --region flags if not already present.

    Args:
        command: The full AWS CLI command (must start with 'aws ')
        profile: AWS profile name to use
        region: AWS region to use
    """
    from .executor import execute  # noqa: PLC0415

    if not command.strip().startswith("aws "):
        return {
            "stdout": "",
            "stderr": "Error: command must start with 'aws '",
            "exit_code": 1,
            "success": False,
        }

    # Inject --profile and --region if not already present
    if "--profile" not in command and profile != "default":
        command += f" --profile {profile}"
    if "--region" not in command:
        command += f" --region {region}"

    result = execute(command)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "success": result.success,
    }


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
    before running any commands.
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

    return {
        "aws_cli_available": aws_available,
        "active_profile": active_profile,
        "active_region": active_region or "not configured",
    }


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for aaws-mcp command and python -m aaws.mcp_server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
