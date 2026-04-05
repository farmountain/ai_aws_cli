"""Tests for interactive session mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aaws.config import AawsConfig
from aaws.executor import ExecutionResult
from aaws.providers.base import LLMResponse


def _config() -> AawsConfig:
    return AawsConfig()


# Lazy imports in session.py mean we must patch at source module paths.
_P = {
    "provider": "aaws.providers.get_provider",
    "translate": "aaws.translator.translate",
    "classify": "aaws.safety.classifier.classify",
    "gate": "aaws.safety.classifier.apply_safety_gate",
    "execute": "aaws.executor.execute",
    "format": "aaws.formatter.format_output",
    "console": "aaws.session.console",
}


# ── Session exit ─────────────────────────────────────────────────────────────


@patch(_P["provider"])
@patch(_P["console"])
def test_session_exit_command(mock_console, mock_prov):
    mock_prov.return_value = MagicMock()
    mock_console.input.return_value = "exit"

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Goodbye" in c for c in calls)


@patch(_P["provider"])
@patch(_P["console"])
def test_session_quit_command(mock_console, mock_prov):
    mock_prov.return_value = MagicMock()
    mock_console.input.return_value = "quit"

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Goodbye" in c for c in calls)


@patch(_P["provider"])
@patch(_P["console"])
def test_session_ctrl_c_exits_gracefully(mock_console, mock_prov):
    mock_prov.return_value = MagicMock()
    mock_console.input.side_effect = KeyboardInterrupt

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Goodbye" in c for c in calls)


@patch(_P["provider"])
@patch(_P["console"])
def test_session_eof_exits_gracefully(mock_console, mock_prov):
    mock_prov.return_value = MagicMock()
    mock_console.input.side_effect = EOFError

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Goodbye" in c for c in calls)


# ── Empty input ignored ─────────────────────────────────────────────────────


@patch(_P["provider"])
@patch(_P["console"])
def test_session_empty_input_skipped(mock_console, mock_prov):
    provider = MagicMock()
    mock_prov.return_value = provider
    mock_console.input.side_effect = ["", "  ", "exit"]

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    # translate should never be called (provider.complete not called)
    provider.complete.assert_not_called()


# ── Translation + execution ──────────────────────────────────────────────────


@patch(_P["format"])
@patch(_P["execute"])
@patch(_P["gate"], return_value=True)
@patch(_P["classify"], return_value=0)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["console"])
def test_session_executes_tier0_command(
    mock_console, mock_prov, mock_trans, mock_cls, mock_gate, mock_exec, mock_fmt,
):
    mock_prov.return_value = MagicMock()
    mock_trans.return_value = LLMResponse(
        command="aws s3 ls --output json", explanation="Lists buckets", risk_tier=0,
    )
    mock_exec.return_value = ExecutionResult(
        stdout='{"Buckets": []}', stderr="", exit_code=0,
    )
    mock_console.input.side_effect = ["list my buckets", "exit"]

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    mock_exec.assert_called_once_with("aws s3 ls --output json")


# ── Clarification flow ───────────────────────────────────────────────────────


@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["console"])
def test_session_clarification_printed(mock_console, mock_prov, mock_trans):
    mock_prov.return_value = MagicMock()
    mock_trans.return_value = LLMResponse(
        command="", explanation="", risk_tier=0, clarification="Which one?",
    )
    mock_console.input.side_effect = ["stop server", "exit"]

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Which one?" in c for c in calls)


# ── History includes output ──────────────────────────────────────────────────


@patch(_P["format"])
@patch(_P["execute"])
@patch(_P["gate"], return_value=True)
@patch(_P["classify"], return_value=0)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["console"])
def test_session_second_command_gets_history_with_output(
    mock_console, mock_prov, mock_trans, mock_cls, mock_gate, mock_exec, mock_fmt,
):
    mock_prov.return_value = MagicMock()
    mock_trans.return_value = LLMResponse(
        command="aws s3 ls --output json", explanation="Lists buckets", risk_tier=0,
    )
    mock_exec.return_value = ExecutionResult(
        stdout='{"Buckets": [{"Name": "my-bucket"}]}', stderr="", exit_code=0,
    )
    mock_console.input.side_effect = ["list my buckets", "show details", "exit"]

    from aaws.session import run_session
    run_session(_config(), "default", "us-east-1")

    # Second translate call should have history with output from first command
    assert mock_trans.call_count == 2
    second_call_args = mock_trans.call_args_list[1]
    history = second_call_args[0][3]  # 4th positional arg = history
    assert len(history) == 2  # user + assistant
    assert history[0]["role"] == "user"
    assert "list my buckets" in history[0]["content"]
    assert history[1]["role"] == "assistant"
    # Output should be in the assistant history entry
    assert "my-bucket" in history[1]["content"]


# ── Safety gate cancellation ─────────────────────────────────────────────────


@patch(_P["gate"], return_value=False)
@patch(_P["classify"], return_value=2)
@patch(_P["translate"])
@patch(_P["provider"])
@patch(_P["console"])
def test_session_cancelled_command_not_executed(
    mock_console, mock_prov, mock_trans, mock_cls, mock_gate,
):
    mock_prov.return_value = MagicMock()
    mock_trans.return_value = LLMResponse(
        command="aws ec2 terminate-instances --instance-ids i-abc",
        explanation="Terminates", risk_tier=2,
    )
    mock_console.input.side_effect = ["terminate i-abc", "exit"]

    with patch(_P["execute"]) as mock_exec:
        from aaws.session import run_session
        run_session(_config(), "default", "us-east-1")
        mock_exec.assert_not_called()

    calls = [str(c) for c in mock_console.print.call_args_list]
    assert any("Cancelled" in c for c in calls)
