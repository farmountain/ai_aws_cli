"""Tests for error routing, LLM interpretation, and handle_error."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aaws.errors import (
    ErrorType,
    classify_error,
    get_credential_message,
    handle_error,
    interpret_error,
)
from aaws.executor import ExecutionResult
from aaws.providers.base import LLMResponse


# ── handle_error routing ─────────────────────────────────────────────────────


@patch("aaws.formatter.render_error")
def test_handle_error_routes_credential_errors(mock_render):
    """Credential errors should get hardcoded message, no LLM call."""
    result = ExecutionResult(stdout="", stderr="ExpiredTokenException: token expired", exit_code=1)
    provider = MagicMock()

    handle_error("aws s3 ls", result, "default", provider)

    # LLM should NOT be called for credential errors
    provider.complete.assert_not_called()
    mock_render.assert_called_once()
    args, kwargs = mock_render.call_args
    suggestion = kwargs.get("suggestion") or (args[1] if len(args) > 1 else None)
    assert suggestion is not None
    assert "aws sso login" in suggestion


@patch("aaws.formatter.render_error")
def test_handle_error_routes_resource_errors_to_llm(mock_render):
    """Resource errors should be sent to LLM for interpretation."""
    result = ExecutionResult(
        stdout="", stderr="An error occurred (BucketNotEmpty) when calling DeleteBucket", exit_code=1
    )
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command="", explanation="The bucket is not empty. Empty it first.", risk_tier=0,
    )

    handle_error("aws s3 rb s3://my-bucket", result, "default", provider)

    provider.complete.assert_called_once()
    mock_render.assert_called_once()


@patch("aaws.formatter.render_error")
def test_handle_error_unknown_shows_raw_stderr(mock_render):
    """Unknown errors should just show raw stderr."""
    result = ExecutionResult(stdout="", stderr="Something completely unexpected", exit_code=1)
    provider = MagicMock()

    handle_error("aws s3 ls", result, "default", provider)

    provider.complete.assert_not_called()
    mock_render.assert_called_once()


# ── interpret_error ──────────────────────────────────────────────────────────


def test_interpret_error_calls_llm():
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command="", explanation="The bucket doesn't exist.", risk_tier=0,
    )

    result = interpret_error("aws s3 rb s3://no-bucket", "NoSuchBucket", provider)
    assert "doesn't exist" in result
    provider.complete.assert_called_once()


def test_interpret_error_handles_llm_failure():
    """If the LLM fails, should return raw stderr."""
    provider = MagicMock()
    provider.complete.side_effect = Exception("LLM unavailable")

    result = interpret_error("aws s3 ls", "Some error text", provider)
    assert result == "Some error text"


# ── Edge cases ───────────────────────────────────────────────────────────────


@patch("aaws.formatter.render_error")
def test_handle_error_no_credentials(mock_render):
    result = ExecutionResult(stdout="", stderr="Unable to locate credentials", exit_code=1)
    provider = MagicMock()

    handle_error("aws s3 ls", result, "default", provider)

    provider.complete.assert_not_called()
    args, kwargs = mock_render.call_args
    suggestion = kwargs.get("suggestion") or (args[1] if len(args) > 1 else None)
    assert "aws configure" in suggestion


@patch("aaws.formatter.render_error")
def test_handle_error_resource_not_found(mock_render):
    result = ExecutionResult(
        stdout="", stderr="An error occurred (NoSuchKey): The specified key does not exist.", exit_code=1
    )
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(
        command="", explanation="The S3 object key does not exist.", risk_tier=0,
    )

    handle_error("aws s3api get-object --bucket b --key k out.txt", result, "default", provider)

    provider.complete.assert_called_once()
