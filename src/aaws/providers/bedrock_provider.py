"""AWS Bedrock LLM provider (default)."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
)

from ..errors import AawsError
from .base import LLMResponse, Message, TOOL_SCHEMA


class BedrockProvider:
    """Calls AWS Bedrock converse API with tool use for structured output."""

    def __init__(
        self,
        model: str,
        profile: str | None,
        region: str | None,
        temperature: float,
        timeout: int,
    ) -> None:
        self.model = model
        session = boto3.Session(
            profile_name=profile,
            region_name=region or "us-east-1",
        )
        self.client = session.client(
            "bedrock-runtime",
            config=BotocoreConfig(read_timeout=timeout, connect_timeout=10),
        )
        self.temperature = temperature

    def complete(self, messages: list[Message], tool_schema: dict[str, Any]) -> LLMResponse:
        # Convert messages to Bedrock converse format (alternating user/assistant)
        converse_messages = [
            {"role": m.role, "content": [{"text": m.content}]}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        # Convert TOOL_SCHEMA (OpenAI/Anthropic style) to Bedrock toolSpec
        bedrock_tool = {
            "toolSpec": {
                "name": tool_schema["name"],
                "description": tool_schema.get("description", ""),
                "inputSchema": {
                    "json": tool_schema.get("input_schema", tool_schema.get("parameters", {}))
                },
            }
        }

        try:
            response = self.client.converse(
                modelId=self.model,
                messages=converse_messages,
                inferenceConfig={"temperature": self.temperature},
                toolConfig={
                    "tools": [bedrock_tool],
                    "toolChoice": {"tool": {"name": tool_schema["name"]}},
                },
            )
        except (ReadTimeoutError, ConnectTimeoutError) as e:
            raise AawsError(
                "Request timed out. Check your network connection and try again."
            ) from e
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException", "ValidationException") and "model" in str(e).lower():
                raise AawsError(
                    f"Model access not enabled. Go to AWS Console → Bedrock → Model access "
                    f"to enable `{self.model}`."
                ) from e
            if code == "AccessDeniedException":
                raise AawsError(
                    f"Access denied calling Bedrock. Check your IAM permissions.\n{e}"
                ) from e
            raise AawsError(f"Bedrock error ({code}): {e}") from e

        # Extract tool use block from response
        output_message = response.get("output", {}).get("message", {})
        for block in output_message.get("content", []):
            if "toolUse" in block:
                tool_input = block["toolUse"]["input"]
                return LLMResponse(
                    command=str(tool_input.get("command", "")),
                    explanation=str(tool_input.get("explanation", "")),
                    risk_tier=int(tool_input.get("risk_tier", 1)),
                    clarification=tool_input.get("clarification") or None,
                )

        raise AawsError("Bedrock did not return a tool use response. Check model availability.")
