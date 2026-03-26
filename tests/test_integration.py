"""Integration test: full pipeline from NL → command → execute → format output."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from aaws.config import AawsConfig
from aaws.errors import AawsError
from aaws.executor import ExecutionResult
from aaws.formatter import format_output
from aaws.providers.base import LLMResponse
from aaws.safety.classifier import classify
from aaws.translator import translate


def _make_provider(command: str, explanation: str = "", risk_tier: int = 0) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command=command,
        explanation=explanation,
        risk_tier=risk_tier,
    )
    return provider


# ── End-to-end pipeline test ─────────────────────────────────────────────────

def test_full_pipeline_list_s3_buckets(capsys: pytest.CaptureFixture):
    """NL → translate → classify → execute (mocked) → format output."""
    provider = _make_provider(
        command="aws s3 ls --output json",
        explanation="Lists all S3 buckets",
        risk_tier=0,
    )

    fake_output = json.dumps(
        {"Buckets": [{"Name": "my-bucket", "CreationDate": "2024-01-01T00:00:00+00:00"}]}
    )

    with patch("aaws.executor.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=fake_output, stderr="", returncode=0
        )

        # 1. Translate
        response = translate("list my S3 buckets", "default", "us-east-1", [], provider)
        assert response.command == "aws s3 ls --output json"

        # 2. Classify
        tier = classify(response.command, response.risk_tier)
        assert tier == 0  # aws s3 ls → read-only

        # 3. Execute
        from aaws.executor import execute
        result = execute(response.command)
        assert result.success
        assert "my-bucket" in result.stdout

        # 4. Format
        format_output(result.stdout, raw=False)

    captured = capsys.readouterr()
    assert "my-bucket" in captured.out


def test_full_pipeline_clarification_returned(capsys: pytest.CaptureFixture):
    """Ambiguous input → clarification printed, nothing executed."""
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command="",
        explanation="",
        risk_tier=0,
        clarification="Which instance ID do you want to stop?",
    )

    response = translate("stop that one", "default", "us-east-1", [], provider)
    assert response.clarification == "Which instance ID do you want to stop?"

    # Nothing should be classified or executed
    assert not response.command


def test_full_pipeline_translate_retry_then_succeed():
    """First LLM call returns bad command, second succeeds."""
    provider = MagicMock()
    provider.complete.side_effect = [
        LLMResponse(command="invalid-command", explanation="", risk_tier=0),
        LLMResponse(command="aws ec2 describe-instances --output json", explanation="", risk_tier=0),
    ]

    response = translate("show my EC2 instances", "default", "us-east-1", [], provider)
    assert response.command == "aws ec2 describe-instances --output json"
    assert provider.complete.call_count == 2


def test_aws_cli_not_installed_exits(monkeypatch: pytest.MonkeyPatch):
    """check_aws_cli exits cleanly when aws is not in PATH."""
    import shutil
    import sys

    monkeypatch.setattr(shutil, "which", lambda _: None)

    from aaws.executor import check_aws_cli

    with pytest.raises(SystemExit) as exc_info:
        check_aws_cli()
    assert exc_info.value.code == 1


def test_format_output_raw_passthrough(capsys: pytest.CaptureFixture):
    """--raw flag bypasses all formatting and writes JSON directly."""
    payload = '{"Instances": [{"InstanceId": "i-xyz"}]}'
    format_output(payload, raw=True)
    captured = capsys.readouterr()
    assert captured.out == payload
