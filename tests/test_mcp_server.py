"""Tests for MCP server tool functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from aaws.mcp_server import (
    classify_aws_command,
    check_aws_environment,
    execute_aws_command,
    format_aws_output,
    list_safety_tiers,
)


# ── classify_aws_command ─────────────────────────────────────────────────────


def test_classify_read_only():
    result = classify_aws_command("aws ec2 describe-instances --output json")
    assert result["tier"] == 0
    assert result["tier_label"] == "Read-only"
    assert result["should_confirm"] is False
    assert result["is_catastrophic"] is False


def test_classify_write():
    result = classify_aws_command("aws ec2 run-instances --instance-type t3.micro")
    assert result["tier"] == 1
    assert result["tier_label"] == "Write"
    assert result["should_confirm"] is True


def test_classify_destructive():
    result = classify_aws_command("aws ec2 terminate-instances --instance-ids i-abc123")
    assert result["tier"] == 2
    assert result["tier_label"] == "Destructive"


def test_classify_catastrophic():
    result = classify_aws_command("aws s3 rm s3://bucket --recursive")
    assert result["tier"] == 3
    assert result["is_catastrophic"] is True


def test_classify_unknown_defaults_to_write():
    """Unknown commands should default to tier 1 (Write) for safety."""
    result = classify_aws_command("aws some-new-service do-something")
    assert result["tier"] == 1


def test_classify_return_shape():
    result = classify_aws_command("aws s3 ls")
    assert "command" in result
    assert "tier" in result
    assert "tier_label" in result
    assert "should_confirm" in result
    assert "is_catastrophic" in result


# ── execute_aws_command ──────────────────────────────────────────────────────


@patch("aaws.executor.subprocess.run")
def test_execute_success(mock_run):
    mock_run.return_value = MagicMock(stdout='{"Buckets": []}', stderr="", returncode=0)
    result = execute_aws_command("aws s3api list-buckets --output json")
    assert result["success"] is True
    assert '{"Buckets": []}' in result["stdout"]


@patch("aaws.executor.subprocess.run")
def test_execute_failure(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="AccessDenied", returncode=1)
    result = execute_aws_command("aws s3 ls")
    assert result["success"] is False
    assert result["stderr"] == "AccessDenied"
    assert result["exit_code"] == 1


def test_execute_rejects_non_aws():
    result = execute_aws_command("rm -rf /")
    assert result["success"] is False
    assert "must start with 'aws" in result["stderr"]


@patch("aaws.executor.subprocess.run")
def test_execute_injects_region(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute_aws_command("aws s3 ls", region="eu-west-1")
    tokens = mock_run.call_args[0][0]
    assert "--region" in tokens
    assert "eu-west-1" in tokens


@patch("aaws.executor.subprocess.run")
def test_execute_skips_region_if_present(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute_aws_command("aws s3 ls --region ap-southeast-1")
    tokens = mock_run.call_args[0][0]
    # Should only have one --region
    assert tokens.count("--region") == 1


@patch("aaws.executor.subprocess.run")
def test_execute_injects_profile_for_non_default(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute_aws_command("aws s3 ls", profile="prod")
    tokens = mock_run.call_args[0][0]
    assert "--profile" in tokens
    assert "prod" in tokens


@patch("aaws.executor.subprocess.run")
def test_execute_skips_profile_for_default(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute_aws_command("aws s3 ls", profile="default")
    tokens = mock_run.call_args[0][0]
    assert "--profile" not in tokens


# ── format_aws_output ────────────────────────────────────────────────────────


def test_format_empty():
    result = format_aws_output("")
    assert result == "No results."


def test_format_list_shape():
    data = json.dumps({"Buckets": [{"Name": "my-bucket", "CreationDate": "2024-01-01"}]})
    result = format_aws_output(data)
    assert isinstance(result, str)
    assert "my-bucket" in result


def test_format_non_json():
    result = format_aws_output("2024-01-01 my-bucket\n2024-02-01 other-bucket")
    assert "my-bucket" in result


def test_format_returns_string():
    data = json.dumps({"Instances": [{"InstanceId": "i-abc"}]})
    result = format_aws_output(data)
    assert isinstance(result, str)
    # Should not contain ANSI escape codes
    assert "\033[" not in result


def test_format_empty_list():
    data = json.dumps({"Buckets": []})
    result = format_aws_output(data)
    assert "No results" in result


# ── list_safety_tiers ────────────────────────────────────────────────────────


def test_list_all_tiers():
    result = list_safety_tiers()
    assert "Command Prefix" in result
    assert "aws ec2 describe" in result
    assert "aws s3 rm" in result


def test_list_filter_ec2():
    result = list_safety_tiers("ec2")
    assert "ec2" in result.lower()
    assert "aws s3" not in result


def test_list_filter_no_match():
    result = list_safety_tiers("nonexistent-service-xyz")
    assert "No tier entries found" in result


# ── check_aws_environment ────────────────────────────────────────────────────


def test_check_aws_present(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/aws")
    result = check_aws_environment()
    assert result["aws_cli_available"] is True


def test_check_aws_missing(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_aws_environment()
    assert result["aws_cli_available"] is False


def test_check_picks_up_profile_env(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("AWS_PROFILE", "my-profile")
    result = check_aws_environment()
    assert result["active_profile"] == "my-profile"


def test_check_picks_up_region_env(monkeypatch: pytest.MonkeyPatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    result = check_aws_environment()
    assert result["active_region"] == "ap-northeast-1"
