"""Tests for subprocess execution of AWS CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aaws.executor import ExecutionResult, check_aws_cli, execute


# ── ExecutionResult ──────────────────────────────────────────────────────────


def test_execution_result_success():
    result = ExecutionResult(stdout="ok", stderr="", exit_code=0)
    assert result.success is True


def test_execution_result_failure():
    result = ExecutionResult(stdout="", stderr="error", exit_code=1)
    assert result.success is False


# ── execute ──────────────────────────────────────────────────────────────────


@patch("aaws.executor.subprocess.run")
def test_execute_returns_stdout(mock_run):
    mock_run.return_value = MagicMock(
        stdout='{"Buckets": []}', stderr="", returncode=0,
    )
    result = execute("aws s3api list-buckets --output json")
    assert result.success
    assert '{"Buckets": []}' in result.stdout
    # Verify shlex.split was used (list, not string)
    args = mock_run.call_args
    assert isinstance(args[0][0], list)


@patch("aaws.executor.subprocess.run")
def test_execute_captures_stderr(mock_run):
    mock_run.return_value = MagicMock(
        stdout="", stderr="AccessDenied", returncode=1,
    )
    result = execute("aws s3 ls")
    assert not result.success
    assert result.stderr == "AccessDenied"
    assert result.exit_code == 1


@patch("aaws.executor.subprocess.run")
def test_execute_tokenizes_command(mock_run):
    """Verify that commands are split into tokens, not passed as shell strings."""
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute("aws ec2 describe-instances --region us-east-1 --output json")
    tokens = mock_run.call_args[0][0]
    assert tokens == ["aws", "ec2", "describe-instances", "--region", "us-east-1", "--output", "json"]


@patch("aaws.executor.subprocess.run")
def test_execute_never_uses_shell(mock_run):
    """Verify shell=True is never passed."""
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute("aws s3 ls")
    kwargs = mock_run.call_args[1]
    assert kwargs.get("shell", False) is False


@patch("aaws.executor.subprocess.run")
def test_execute_captures_output(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute("aws s3 ls")
    kwargs = mock_run.call_args[1]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


# ── check_aws_cli ────────────────────────────────────────────────────────────


def test_check_aws_cli_present(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/aws")
    # Should not raise
    check_aws_cli()


def test_check_aws_cli_missing(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(SystemExit) as exc_info:
        check_aws_cli()
    assert exc_info.value.code == 1
