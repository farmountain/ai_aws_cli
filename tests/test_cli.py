"""Tests for CLI entry point commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from aaws.cli import app
from aaws.config import AawsConfig
from aaws.providers.base import LLMResponse

runner = CliRunner()


def _mock_config() -> AawsConfig:
    return AawsConfig()


def _mock_provider(
    command: str = "aws s3 ls --output json",
    explanation: str = "Lists S3 buckets",
    risk_tier: int = 0,
    clarification: str | None = None,
) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command=command,
        explanation=explanation,
        risk_tier=risk_tier,
        clarification=clarification,
    )
    return provider


# Lazy imports in cli.py mean we must patch at source module paths.
_P = {
    "check": "aaws.executor.check_aws_cli",
    "load": "aaws.cli._load_or_exit",
    "provider": "aaws.providers.get_provider",
    "execute": "aaws.executor.execute",
    "translate": "aaws.translator.translate",
    "classify": "aaws.safety.classifier.classify",
    "gate": "aaws.safety.classifier.apply_safety_gate",
    "dry_run": "aaws.safety.classifier.was_dry_run_requested",
    "format": "aaws.formatter.format_output",
}


# ── Root command ─────────────────────────────────────────────────────────────


@patch(_P["dry_run"], return_value=False)
@patch(_P["format"])
@patch(_P["execute"])
@patch(_P["gate"], return_value=True)
@patch(_P["classify"], return_value=0)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_root_command_tier0_auto_executes(
    mock_check, mock_load, mock_prov, mock_trans, mock_cls, mock_gate,
    mock_exec, mock_fmt, mock_dry,
):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="aws s3 ls --output json", explanation="Lists buckets", risk_tier=0,
    )
    mock_exec.return_value = MagicMock(
        stdout='{"Buckets": []}', stderr="", exit_code=0, success=True,
    )
    result = runner.invoke(app, ["list my S3 buckets"])
    assert result.exit_code == 0
    mock_exec.assert_called_once()


@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_root_command_dry_run(mock_check, mock_load, mock_prov, mock_trans):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="aws ec2 describe-instances --output json",
        explanation="Describes instances", risk_tier=0,
    )
    result = runner.invoke(app, ["--dry-run", "show my EC2 instances"])
    assert result.exit_code == 0
    assert "aws ec2 describe-instances" in result.output


@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_root_command_clarification(mock_check, mock_load, mock_prov, mock_trans):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="", explanation="", risk_tier=0, clarification="Which bucket?",
    )
    result = runner.invoke(app, ["delete that bucket"])
    assert result.exit_code == 0
    assert "Which bucket?" in result.output


@patch(_P["dry_run"], return_value=False)
@patch(_P["format"])
@patch(_P["execute"])
@patch(_P["gate"], return_value=True)
@patch(_P["classify"], return_value=1)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_root_command_yes_flag(
    mock_check, mock_load, mock_prov, mock_trans, mock_cls, mock_gate,
    mock_exec, mock_fmt, mock_dry,
):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="aws s3api create-bucket --bucket test",
        explanation="Creates bucket", risk_tier=1,
    )
    mock_exec.return_value = MagicMock(
        stdout='{"Location": "/test"}', stderr="", exit_code=0, success=True,
    )
    result = runner.invoke(app, ["--yes", "create bucket test"])
    assert result.exit_code == 0
    # Verify auto_confirm was passed to safety gate
    gate_kwargs = mock_gate.call_args[1]
    assert gate_kwargs["auto_confirm"] is True


def test_root_command_no_args():
    result = runner.invoke(app, [])
    # Typer shows help and exits with 0 (no_args_is_help=True)
    assert result.exit_code in (0, 2)  # Typer may return 2 for help display


@patch(_P["dry_run"], return_value=False)
@patch(_P["format"])
@patch(_P["execute"])
@patch(_P["gate"], return_value=True)
@patch(_P["classify"], return_value=0)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_root_command_raw_flag(
    mock_check, mock_load, mock_prov, mock_trans, mock_cls, mock_gate,
    mock_exec, mock_fmt, mock_dry,
):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="aws s3 ls", explanation="Lists", risk_tier=0,
    )
    mock_exec.return_value = MagicMock(
        stdout='{"Buckets": []}', stderr="", exit_code=0, success=True,
    )
    result = runner.invoke(app, ["--raw", "list my buckets"])
    assert result.exit_code == 0
    # format_output should be called with raw=True
    mock_fmt.assert_called_once()
    assert mock_fmt.call_args[1]["raw"] is True


# ── Profile / region override ────────────────────────────────────────────────


@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["load"], return_value=_mock_config())
@patch(_P["check"])
def test_profile_and_region_flags(mock_check, mock_load, mock_prov, mock_trans):
    mock_prov.return_value = _mock_provider()
    mock_trans.return_value = LLMResponse(
        command="aws s3 ls", explanation="Lists", risk_tier=0,
    )
    result = runner.invoke(
        app, ["--dry-run", "--profile", "prod", "--region", "eu-west-1", "list buckets"]
    )
    assert result.exit_code == 0


# ── explain command ──────────────────────────────────────────────────────────


@patch("aaws.providers.get_provider")
@patch("aaws.cli._load_or_exit", return_value=_mock_config())
def test_explain_command(mock_load, mock_prov):
    """Test explain subcommand via direct Typer invocation."""
    from aaws.cli import explain_command
    from typer import Typer

    provider = _mock_provider(
        command="aws s3 ls", explanation="Lists all S3 buckets in your account.",
    )
    mock_prov.return_value = provider

    # Build a standalone app to avoid root callback routing issues
    test_app = Typer()
    test_app.command()(explain_command)
    result = runner.invoke(test_app, ["aws s3 ls"])
    assert result.exit_code == 0
    assert "aws s3 ls" in result.output


# ── config show ──────────────────────────────────────────────────────────────


@patch("aaws.cli._load_or_exit", return_value=_mock_config())
def test_config_show(mock_load):
    """Test config show via the config sub-app directly."""
    from aaws.cli import config_app

    result = runner.invoke(config_app, ["show"])
    assert result.exit_code == 0
    assert "bedrock" in result.output
