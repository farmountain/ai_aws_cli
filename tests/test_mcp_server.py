"""Tests for MCP server tool functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from aaws.mcp_server import (
    _extract_profile,
    classify_aws_command,
    check_aws_environment,
    execute_aws_command,
    execute_confirmed_aws_command,
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


# ── execute_aws_command — tier gating ────────────────────────────────────────


def test_execute_rejects_non_aws():
    result = execute_aws_command("rm -rf /")
    assert result["success"] is False
    assert "must start with 'aws" in result["stderr"]


@patch("aaws.mcp_server._get_config")
@patch("aaws.mcp_server._audit_command")
@patch("aaws.executor.subprocess.run")
def test_execute_tier0_executes(mock_run, mock_audit, mock_config):
    """Tier 0 commands are executed immediately."""
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    mock_run.return_value = MagicMock(stdout='{"Buckets": []}', stderr="", returncode=0)
    result = execute_aws_command("aws s3api list-buckets --output json")
    assert result["executed"] is True
    assert result["requires_confirmation"] is False
    assert result["tier"] == 0
    assert '{"Buckets": []}' in result["stdout"]


@patch("aaws.mcp_server._get_config")
def test_execute_tier1_blocked(mock_config):
    """Tier 1 commands return requires_confirmation, not executed."""
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    result = execute_aws_command("aws ec2 run-instances --instance-type t3.micro")
    assert result["requires_confirmation"] is True
    assert result["executed"] is False
    assert result["tier"] == 1


@patch("aaws.mcp_server._get_config")
def test_execute_tier2_blocked(mock_config):
    """Tier 2 commands return requires_confirmation, not executed."""
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    result = execute_aws_command("aws ec2 terminate-instances --instance-ids i-abc")
    assert result["requires_confirmation"] is True
    assert result["executed"] is False
    assert result["tier"] == 2


@patch("aaws.mcp_server._get_config")
def test_execute_tier3_blocked(mock_config):
    """Tier 3 commands return requires_confirmation, not executed."""
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    result = execute_aws_command("aws s3 rm s3://bucket --recursive")
    assert result["requires_confirmation"] is True
    assert result["executed"] is False
    assert result["tier"] == 3
    assert result["is_catastrophic"] is True


# ── auto_execute_tier ignored in MCP ─────────────────────────────────────────


@patch("aaws.mcp_server._get_config")
def test_auto_execute_tier_ignored_in_mcp(mock_config):
    """auto_execute_tier config should NOT apply in MCP mode."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(auto_execute_tier=1, protected_profiles=[])
    )
    result = execute_aws_command("aws ec2 run-instances --instance-type t3.micro")
    assert result["requires_confirmation"] is True
    assert result["executed"] is False


# ── Protected profile blocking ───────────────────────────────────────────────


@patch("aaws.mcp_server._get_config")
def test_execute_protected_profile_parameter(mock_config):
    """Protected profile via parameter blocks execution."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(protected_profiles=["prod*"])
    )
    result = execute_aws_command(
        "aws ec2 run-instances --instance-type t3.micro",
        profile="production",
    )
    assert result["success"] is False
    assert "protected" in result["stderr"].lower()
    assert result["blocked_by"] == "protected_profile"


@patch("aaws.mcp_server._get_config")
def test_execute_protected_profile_embedded(mock_config):
    """Protected profile embedded in command string blocks execution."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(protected_profiles=["prod*"])
    )
    result = execute_aws_command(
        "aws ec2 run-instances --profile production --instance-type t3.micro",
    )
    assert result["success"] is False
    assert "protected" in result["stderr"].lower()


@patch("aaws.mcp_server._get_config")
def test_execute_protected_profile_tier0_allowed(mock_config):
    """Protected profile allows tier 0 (read-only) commands."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(protected_profiles=["prod*"])
    )
    # Tier 0 should not be blocked even on protected profiles
    # The check is: tier > 0 AND protected
    # For tier 0: 0 > 0 is False, so it won't be blocked
    # It will try to execute since tier == 0
    with patch("aaws.executor.subprocess.run") as mock_run:
        with patch("aaws.mcp_server._audit_command"):
            mock_run.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            result = execute_aws_command(
                "aws ec2 describe-instances --profile production",
            )
            assert result["executed"] is True


@patch("aaws.mcp_server._get_config")
def test_confirmed_protected_profile_blocked(mock_config):
    """execute_confirmed also enforces protected-profile rules."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(protected_profiles=["prod*"])
    )
    result = execute_confirmed_aws_command(
        "aws ec2 run-instances --instance-type t3.micro",
        profile="production",
    )
    assert result["success"] is False
    assert "protected" in result["stderr"].lower()


@patch("aaws.mcp_server._get_config")
def test_confirmed_protected_profile_embedded(mock_config):
    """execute_confirmed catches embedded --profile in command string."""
    mock_config.return_value = MagicMock(
        safety=MagicMock(protected_profiles=["prod*"])
    )
    result = execute_confirmed_aws_command(
        "aws ec2 run-instances --profile production --instance-type t3.micro",
    )
    assert result["success"] is False
    assert "protected" in result["stderr"].lower()


# ── execute_confirmed_aws_command ────────────────────────────────────────────


def test_confirmed_rejects_non_aws():
    result = execute_confirmed_aws_command("rm -rf /")
    assert result["success"] is False
    assert "must start with 'aws" in result["stderr"]


@patch("aaws.mcp_server._get_config")
@patch("aaws.mcp_server._audit_command")
@patch("aaws.executor.subprocess.run")
def test_confirmed_executes_with_reclassification(mock_run, mock_audit, mock_config):
    """execute_confirmed re-classifies and includes tier in response."""
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    mock_run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
    result = execute_confirmed_aws_command("aws ec2 run-instances --instance-type t3.micro")
    assert result["success"] is True
    assert result["tier"] == 1
    assert result["tier_label"] == "Write"


@patch("aaws.mcp_server._get_config")
@patch("aaws.mcp_server._audit_command")
@patch("aaws.executor.subprocess.run")
def test_confirmed_injects_region(mock_run, mock_audit, mock_config):
    mock_config.return_value = MagicMock(safety=MagicMock(protected_profiles=[]))
    mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
    execute_confirmed_aws_command("aws s3 ls", region="eu-west-1")
    tokens = mock_run.call_args[0][0]
    assert "--region" in tokens
    assert "eu-west-1" in tokens


# ── _extract_profile ─────────────────────────────────────────────────────────


def test_extract_profile_present():
    assert _extract_profile("aws s3 ls --profile prod --region us-east-1", "default") == "prod"


def test_extract_profile_absent():
    assert _extract_profile("aws s3 ls --region us-east-1", "default") == "default"


def test_extract_profile_no_value_after_flag():
    """--profile at end of command with no value returns default."""
    assert _extract_profile("aws s3 ls --profile", "default") == "default"


def test_extract_profile_quoted_value():
    assert _extract_profile('aws s3 ls --profile "my-profile"', "default") == "my-profile"


def test_extract_profile_empty_command():
    assert _extract_profile("", "fallback") == "fallback"


def test_extract_profile_malformed_quotes():
    """Malformed quoting returns default rather than raising."""
    assert _extract_profile("aws s3 ls --profile 'unclosed", "default") == "default"


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


@patch("aaws.mcp_server._get_audit_config")
def test_check_aws_present(mock_audit_cfg, monkeypatch: pytest.MonkeyPatch):
    import shutil
    from aaws.audit import AuditConfig
    mock_audit_cfg.return_value = AuditConfig(enabled=False)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/aws")
    result = check_aws_environment()
    assert result["aws_cli_available"] is True


@patch("aaws.mcp_server._get_audit_config")
def test_check_aws_missing(mock_audit_cfg, monkeypatch: pytest.MonkeyPatch):
    import shutil
    from aaws.audit import AuditConfig
    mock_audit_cfg.return_value = AuditConfig(enabled=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_aws_environment()
    assert result["aws_cli_available"] is False


@patch("aaws.mcp_server._get_audit_config")
def test_check_picks_up_profile_env(mock_audit_cfg, monkeypatch: pytest.MonkeyPatch):
    import shutil
    from aaws.audit import AuditConfig
    mock_audit_cfg.return_value = AuditConfig(enabled=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("AWS_PROFILE", "my-profile")
    result = check_aws_environment()
    assert result["active_profile"] == "my-profile"


@patch("aaws.mcp_server._get_audit_config")
def test_check_picks_up_region_env(mock_audit_cfg, monkeypatch: pytest.MonkeyPatch):
    import shutil
    from aaws.audit import AuditConfig
    mock_audit_cfg.return_value = AuditConfig(enabled=False)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    result = check_aws_environment()
    assert result["active_region"] == "ap-northeast-1"


@patch("aaws.mcp_server._get_audit_config")
def test_check_includes_audit_writable(mock_audit_cfg, tmp_path, monkeypatch: pytest.MonkeyPatch):
    import shutil
    from aaws.audit import AuditConfig
    mock_audit_cfg.return_value = AuditConfig(path=str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_aws_environment()
    assert "audit_writable" in result
    assert isinstance(result["audit_writable"], bool)


# ── Config fallback ──────────────────────────────────────────────────────────


def test_config_fallback_safe_defaults():
    """MCP server uses safe defaults when config is not loaded."""
    import aaws.mcp_server as mcp_mod
    # Reset module-level config to test fallback
    original = mcp_mod._config
    try:
        mcp_mod._config = None
        config = mcp_mod._get_config()
        assert config is not None
        assert config.safety.auto_execute_tier == 0
        assert config.safety.protected_profiles == []
    finally:
        mcp_mod._config = original
