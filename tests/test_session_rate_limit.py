"""Integration test: session REPL skips translate() when rate-limited."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestSessionRateLimitIntegration:
    def test_throttled_request_skips_translate(self) -> None:
        """When rate limiter denies a request, translate() is never called."""
        mock_config = MagicMock()
        mock_config.audit.enabled = False
        mock_config.session.rate_limit.enabled = True
        mock_config.session.rate_limit.max_per_minute = 60
        mock_config.session.rate_limit.burst = 1  # Only 1 request allowed
        mock_config.output.raw = False

        mock_provider = MagicMock()

        inputs = iter(["list buckets", "list instances", "exit"])

        with (
            patch("src.aaws.providers.get_provider", return_value=mock_provider),
            patch("src.aaws.translator.translate") as mock_translate,
            patch("src.aaws.session.console") as mock_console,
        ):
            mock_console.input = MagicMock(side_effect=lambda _: next(inputs))

            # Set up translate to return a clarification so we don't need executor
            mock_response = MagicMock()
            mock_response.clarification = "Which buckets?"
            mock_response.command = None
            mock_translate.return_value = mock_response

            from src.aaws.session import run_session
            run_session(mock_config, "default", "us-east-1")

            # translate should only be called once (first request uses the 1 burst token)
            # second request should be throttled
            assert mock_translate.call_count == 1

            # Check that throttle message was shown
            throttle_calls = [
                call for call in mock_console.print.call_args_list
                if "Rate limited" in str(call)
            ]
            assert len(throttle_calls) == 1
