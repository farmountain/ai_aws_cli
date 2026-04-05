"""Tests for LLM provider implementations and factory."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from aaws.config import AawsConfig, LLMConfig
from aaws.errors import AawsError
from aaws.providers import get_provider
from aaws.providers.base import LLMResponse, Message, TOOL_SCHEMA, parse_json_response


# ── get_provider factory ─────────────────────────────────────────────────────


def test_get_provider_bedrock():
    config = AawsConfig(llm=LLMConfig(provider="bedrock"))
    with patch("aaws.providers.BedrockProvider") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider = get_provider(config)
    mock_cls.assert_called_once()


def test_get_provider_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = AawsConfig(llm=LLMConfig(provider="openai", model="gpt-4o-mini"))
    with patch("aaws.providers.OpenAIProvider") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider = get_provider(config)
    mock_cls.assert_called_once()


def test_get_provider_openai_missing_key():
    config = AawsConfig(llm=LLMConfig(provider="openai", api_key=None))
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(AawsError, match="API key"):
            get_provider(config)


def test_get_provider_unknown():
    config = AawsConfig(llm=LLMConfig(provider="claude-direct"))
    with pytest.raises(AawsError, match="Unknown LLM provider"):
        get_provider(config)


# ── BedrockProvider ──────────────────────────────────────────────────────────


def test_bedrock_provider_tool_use_response():
    """Test Bedrock response parsing when tool use block is returned."""
    from aaws.providers.bedrock_provider import BedrockProvider

    with patch("aaws.providers.bedrock_provider.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto.Session.return_value = mock_session

        provider = BedrockProvider(
            model="test-model", profile=None, region="us-east-1",
            temperature=0.1, timeout=30,
        )

        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "name": "aws_command",
                                "input": {
                                    "command": "aws s3 ls",
                                    "explanation": "Lists buckets",
                                    "risk_tier": 0,
                                },
                            }
                        }
                    ]
                }
            }
        }

        response = provider.complete(
            [Message(role="user", content="list buckets")], TOOL_SCHEMA
        )
        assert response.command == "aws s3 ls"
        assert response.risk_tier == 0


def test_bedrock_provider_no_tool_use_raises():
    """Test error when Bedrock returns no tool use block."""
    from aaws.providers.bedrock_provider import BedrockProvider

    with patch("aaws.providers.bedrock_provider.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto.Session.return_value = mock_session

        provider = BedrockProvider(
            model="test-model", profile=None, region="us-east-1",
            temperature=0.1, timeout=30,
        )

        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "plain text response"}]}}
        }

        with pytest.raises(AawsError, match="tool use"):
            provider.complete(
                [Message(role="user", content="test")], TOOL_SCHEMA
            )


def test_bedrock_provider_access_denied():
    """Test Bedrock AccessDeniedException produces actionable error."""
    from botocore.exceptions import ClientError

    from aaws.providers.bedrock_provider import BedrockProvider

    with patch("aaws.providers.bedrock_provider.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto.Session.return_value = mock_session

        provider = BedrockProvider(
            model="test-model", profile=None, region="us-east-1",
            temperature=0.1, timeout=30,
        )

        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "model access"}}
        mock_client.converse.side_effect = ClientError(error_response, "Converse")

        with pytest.raises(AawsError, match="Model access not enabled"):
            provider.complete(
                [Message(role="user", content="test")], TOOL_SCHEMA
            )


def test_bedrock_provider_timeout():
    """Test Bedrock timeout produces friendly error."""
    from botocore.exceptions import ReadTimeoutError

    from aaws.providers.bedrock_provider import BedrockProvider

    with patch("aaws.providers.bedrock_provider.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto.Session.return_value = mock_session

        provider = BedrockProvider(
            model="test-model", profile=None, region="us-east-1",
            temperature=0.1, timeout=30,
        )

        mock_client.converse.side_effect = ReadTimeoutError(endpoint_url="https://bedrock.us-east-1.amazonaws.com")

        with pytest.raises(AawsError, match="timed out"):
            provider.complete(
                [Message(role="user", content="test")], TOOL_SCHEMA
            )


# ── OpenAIProvider ───────────────────────────────────────────────────────────


def test_openai_provider_function_call_response():
    """Test OpenAI response parsing when function call is returned."""
    from aaws.providers.openai_provider import OpenAIProvider

    with patch("aaws.providers.openai_provider.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(
            api_key="sk-test", model="gpt-4o-mini", temperature=0.1, timeout=30,
        )

        mock_tool_call = MagicMock()
        mock_tool_call.function.arguments = json.dumps({
            "command": "aws ec2 describe-instances",
            "explanation": "Lists EC2 instances",
            "risk_tier": 0,
        })
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        response = provider.complete(
            [Message(role="user", content="show instances")], TOOL_SCHEMA
        )
        assert response.command == "aws ec2 describe-instances"
        assert response.risk_tier == 0


def test_openai_provider_no_tool_calls_raises():
    from aaws.providers.openai_provider import OpenAIProvider

    with patch("aaws.providers.openai_provider.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(
            api_key="sk-test", model="gpt-4o-mini", temperature=0.1, timeout=30,
        )

        mock_choice = MagicMock()
        mock_choice.message.tool_calls = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(AawsError, match="function call"):
            provider.complete(
                [Message(role="user", content="test")], TOOL_SCHEMA
            )


def test_openai_provider_timeout():
    from openai import APITimeoutError

    from aaws.providers.openai_provider import OpenAIProvider

    with patch("aaws.providers.openai_provider.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        provider = OpenAIProvider(
            api_key="sk-test", model="gpt-4o-mini", temperature=0.1, timeout=30,
        )

        mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())

        with pytest.raises(AawsError, match="timed out"):
            provider.complete(
                [Message(role="user", content="test")], TOOL_SCHEMA
            )


# ── parse_json_response fallback ─────────────────────────────────────────────


def test_parse_json_plain():
    text = '{"command": "aws s3 ls", "explanation": "Lists", "risk_tier": 0}'
    response = parse_json_response(text)
    assert response.command == "aws s3 ls"
    assert response.risk_tier == 0


def test_parse_json_with_code_fences():
    text = '```json\n{"command": "aws s3 ls", "explanation": "Lists", "risk_tier": 0}\n```'
    response = parse_json_response(text)
    assert response.command == "aws s3 ls"


def test_parse_json_with_clarification():
    text = '{"command": "", "explanation": "", "risk_tier": 0, "clarification": "Which one?"}'
    response = parse_json_response(text)
    assert response.clarification == "Which one?"


def test_parse_json_invalid_raises():
    with pytest.raises(Exception):
        parse_json_response("not json at all")
