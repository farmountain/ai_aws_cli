"""Output formatting: detect AWS CLI response shapes and render with Rich."""

from __future__ import annotations

import json
import sys
from io import StringIO
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()

# ── Column hints ──────────────────────────────────────────────────────────────
# Maps the top-level list key from AWS CLI JSON to preferred table columns.
# Falls back to first MAX_COLUMNS keys for unrecognised resource types.

COLUMN_HINTS: dict[str, list[str]] = {
    "Instances": ["InstanceId", "InstanceType", "State", "PublicIpAddress", "LaunchTime"],
    "Reservations": ["InstanceId", "InstanceType", "State"],
    "Buckets": ["Name", "CreationDate"],
    "Users": ["UserId", "UserName", "Arn", "CreateDate"],
    "Roles": ["RoleName", "RoleId", "Arn", "CreateDate"],
    "Groups": ["GroupName", "GroupId", "Arn"],
    "Policies": ["PolicyName", "Arn", "IsAttachable", "UpdateDate"],
    "Functions": ["FunctionName", "Runtime", "MemorySize", "LastModified"],
    "Stacks": ["StackName", "StackStatus", "CreationTime"],
    "Clusters": ["clusterArn", "clusterName", "status"],
    "DBInstances": ["DBInstanceIdentifier", "DBInstanceClass", "DBInstanceStatus", "Engine"],
    "HostedZones": ["Name", "Id", "Config"],
    "Volumes": ["VolumeId", "VolumeType", "Size", "State", "AvailabilityZone"],
    "SecurityGroups": ["GroupId", "GroupName", "Description", "VpcId"],
    "KeyPairs": ["KeyName", "KeyType", "CreateTime"],
    "Images": ["ImageId", "Name", "State", "Architecture"],
    "Snapshots": ["SnapshotId", "VolumeId", "State", "StartTime"],
    "Subnets": ["SubnetId", "VpcId", "CidrBlock", "AvailabilityZone", "State"],
    "Vpcs": ["VpcId", "CidrBlock", "State", "IsDefault"],
    "LoadBalancers": ["LoadBalancerName", "DNSName", "Scheme", "State"],
    "TargetGroups": ["TargetGroupName", "Protocol", "Port"],
    "Repositories": ["repositoryName", "repositoryUri", "createdAt"],
    "Parameters": ["Name", "Type", "LastModifiedDate"],
    "SecretList": ["Name", "ARN", "LastChangedDate"],
    "Alarms": ["AlarmName", "AlarmDescription", "StateValue"],
    "Topics": ["TopicArn"],
    "Streams": ["StreamArn", "StreamStatus"],
}

MAX_COLUMNS = 6


# ── Public API ────────────────────────────────────────────────────────────────

def format_output(stdout: str, *, raw: bool = False) -> None:
    """
    Detect AWS CLI output shape and render with Rich.

    raw=True writes stdout directly to sys.stdout (for piping to jq etc.).
    """
    if raw:
        sys.stdout.write(stdout)
        return

    if not stdout or not stdout.strip():
        console.print("[dim]No results.[/dim]")
        return

    # Try JSON; fall back to plain text (e.g. `aws s3 ls` without --output json)
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        console.print(stdout.rstrip())
        return

    _render_value(data)


def format_to_string(stdout: str) -> str:
    """Format AWS CLI output to a plain-text string (for MCP / non-terminal use).

    Reuses all existing rendering logic but captures output to a string
    instead of printing to the terminal. No ANSI escape codes in output.
    """
    global console  # noqa: PLW0602

    if not stdout or not stdout.strip():
        return "No results."

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.rstrip()

    buf = StringIO()
    old_console = console
    console = Console(file=buf, force_terminal=False, no_color=True, width=120)  # type: ignore[assignment]
    try:
        _render_value(data)
    finally:
        console = old_console  # type: ignore[assignment]

    return buf.getvalue().rstrip()


def render_error(stderr: str, suggestion: str | None = None) -> None:
    """Render an AWS CLI error in a red panel, with an optional suggestion."""
    body = stderr.strip()
    if suggestion:
        body += f"\n\n[bold yellow]Suggestion:[/bold yellow] {suggestion}"
    console.print(Panel(body, title="[bold red]Error[/bold red]", border_style="red"))


# ── Internal rendering ────────────────────────────────────────────────────────

def _render_value(data: Any) -> None:
    if isinstance(data, list):
        _render_list(data, resource_type=None)
        return

    if isinstance(data, dict):
        if not data:
            console.print("[dim]No results.[/dim]")
            return

        # Check for Reservations → flatten Instances (EC2 describe-instances)
        if "Reservations" in data:
            instances = [
                inst
                for r in data["Reservations"]
                for inst in r.get("Instances", [])
            ]
            if not instances:
                console.print("[dim]No results.[/dim]")
            else:
                _render_list(instances, resource_type="Instances")
            return

        # Look for first list value → table
        for key, value in data.items():
            if isinstance(value, list):
                if not value:
                    console.print("[dim]No results.[/dim]")
                    return
                _render_list(value, resource_type=key)
                return

        # Look for single dict value → card
        for key, value in data.items():
            if isinstance(value, dict):
                _render_card(value, title=key)
                return

        # Flat dict  → card
        _render_card(data)
        return

    # Scalar or other → syntax-highlighted JSON
    console.print(Syntax(json.dumps(data, indent=2, default=str), "json"))


def _render_list(items: list[Any], resource_type: str | None) -> None:
    if not items:
        console.print("[dim]No results.[/dim]")
        return

    # Non-dict items (e.g. SQS queue URLs)
    if not isinstance(items[0], dict):
        for item in items:
            console.print(f"  • {item}")
        console.print(f"[dim]{len(items)} result(s)[/dim]")
        return

    # Determine columns
    hint_cols = COLUMN_HINTS.get(resource_type or "", []) if resource_type else []
    available_keys = list(items[0].keys())

    if hint_cols:
        columns = [c for c in hint_cols if c in available_keys]
        for k in available_keys:
            if k not in columns and len(columns) < MAX_COLUMNS:
                columns.append(k)
    else:
        columns = available_keys[:MAX_COLUMNS]

    table = Table(show_header=True, header_style="bold cyan", expand=False)
    for col in columns:
        table.add_column(col, overflow="fold", max_width=40, no_wrap=False)

    for item in items:
        row: list[str] = []
        for col in columns:
            val = item.get(col, "")
            val = _flatten(val)
            row.append(val)
        table.add_row(*row)

    console.print(table)
    console.print(f"[dim]{len(items)} result(s)[/dim]")


def _render_card(data: dict[str, Any], title: str = "") -> None:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2, default=str)
        lines.append(f"[bold cyan]{key}:[/bold cyan] {value}")
    console.print(Panel("\n".join(lines), title=title, border_style="cyan"))


def _flatten(val: Any) -> str:
    """Convert a dict or list cell value to a compact string."""
    if val is None:
        return ""
    if isinstance(val, dict):
        # Try common summary keys
        for k in ("Name", "Value", "Code", "Status", "State"):
            if k in val:
                return str(val[k])
        return json.dumps(val, default=str)
    if isinstance(val, list):
        return f"[{len(val)} items]"
    return str(val)
