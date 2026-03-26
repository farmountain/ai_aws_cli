"""OpenAI LLM provider."""

from __future__ import annotations

import json
from typing import Any

from openai import APITimeoutError, OpenAI

from ..errors import AawsError
from .base import LLMResponse, Message


class OpenAIProvider:
    """Calls OpenAI chat completions API with function calling."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
        timeout: int,
    ) -> None:
        self.client = OpenAI(api_key=api_key, timeout=float(timeout))
        self.model = model
        self.temperature = temperature

    def complete(self, messages: list[Message], tool_schema: dict[str, Any]) -> LLMResponse:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Convert TOOL_SCHEMA to OpenAI function format
        function_def = {
            "name": tool_schema["name"],
            "description": tool_schema.get("description", ""),
            # OpenAI uses "parameters"; our schema uses "input_schema"
            "parameters": tool_schema.get("input_schema", tool_schema.get("parameters", {})),
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=oai_messages,  # type: ignore[arg-type]
                tools=[{"type": "function", "function": function_def}],
                tool_choice={"type": "function", "function": {"name": tool_schema["name"]}},
                temperature=self.temperature,
            )
        except APITimeoutError as e:
            raise AawsError(
                "Request timed out. Check your network connection and try again."
            ) from e

        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            raise AawsError("OpenAI did not return a function call response.")

        args = json.loads(tool_calls[0].function.arguments)
        return LLMResponse(
            command=str(args.get("command", "")),
            explanation=str(args.get("explanation", "")),
            risk_tier=int(args.get("risk_tier", 1)),
            clarification=args.get("clarification") or None,
        )
