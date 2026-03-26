"""Tests for NL-to-command translation including validation and retry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aaws.errors import TranslationError
from aaws.providers.base import LLMResponse
from aaws.translator import translate


def _make_provider(
    command: str = "aws s3 ls",
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


# ── Happy paths ───────────────────────────────────────────────────────────────

def test_translate_returns_valid_command():
    provider = _make_provider(command="aws s3 ls --output json")
    response = translate("list my buckets", "default", "us-east-1", [], provider)
    assert response.command == "aws s3 ls --output json"
    assert provider.complete.call_count == 1


def test_translate_clarification_returned():
    provider = _make_provider(command="", clarification="Which instance do you mean?")
    response = translate("stop that instance", "default", "us-east-1", [], provider)
    assert response.clarification == "Which instance do you mean?"
    assert provider.complete.call_count == 1


def test_translate_injects_profile_and_region():
    provider = _make_provider(command="aws ec2 describe-instances --region eu-west-1")
    translate("list EC2 instances", "prod", "eu-west-1", [], provider)
    call_args = provider.complete.call_args
    messages = call_args[0][0]
    context_message = messages[-1].content
    assert "prod" in context_message
    assert "eu-west-1" in context_message


def test_translate_history_bounded_to_10():
    provider = _make_provider(command="aws s3 ls")
    history = [{"role": "user", "content": f"message {i}"} for i in range(20)]
    translate("new request", "default", "us-east-1", history, provider)
    call_args = provider.complete.call_args
    messages = call_args[0][0]
    # messages = [system_prompt] + last 10 history + user_message = 12 max
    assert len(messages) <= 12


# ── Retry / validation ────────────────────────────────────────────────────────

def test_translate_retries_on_invalid_command():
    provider = MagicMock()
    provider.complete.side_effect = [
        LLMResponse(command="not-aws stuff", explanation="", risk_tier=0),
        LLMResponse(command="aws s3 ls", explanation="Lists buckets", risk_tier=0),
    ]
    response = translate("list stuff", "default", "us-east-1", [], provider)
    assert response.command == "aws s3 ls"
    assert provider.complete.call_count == 2


def test_translate_raises_after_two_failures():
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command="garbage", explanation="", risk_tier=0
    )
    with pytest.raises(TranslationError):
        translate("gibberish request", "default", "us-east-1", [], provider)


def test_translate_empty_command_triggers_retry():
    provider = MagicMock()
    provider.complete.side_effect = [
        LLMResponse(command="", explanation="", risk_tier=0),
        LLMResponse(command="aws iam list-users", explanation="Lists users", risk_tier=0),
    ]
    response = translate("show all iam users", "default", "us-east-1", [], provider)
    assert response.command.startswith("aws ")
