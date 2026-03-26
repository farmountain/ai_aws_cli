"""Subprocess execution of AWS CLI commands."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0


def check_aws_cli() -> None:
    """
    Verify the aws CLI is present in PATH.
    Exits with code 1 and an actionable message if not found.
    """
    if shutil.which("aws") is None:
        from rich.console import Console  # noqa: PLC0415

        Console().print(
            "[bold red]Error:[/bold red] AWS CLI not found in PATH.\n"
            "Install it from: "
            "https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
        )
        sys.exit(1)


def execute(command: str) -> ExecutionResult:
    """
    Execute an AWS CLI command via subprocess.

    Security: never uses shell=True. The command string is tokenised with
    shlex.split and passed as a list to subprocess.run, preventing shell
    injection regardless of what the LLM produced.
    """
    tokens = shlex.split(command)
    result = subprocess.run(tokens, capture_output=True, text=True)
    return ExecutionResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.returncode,
    )
