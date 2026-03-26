"""LLM provider protocol, shared types, and tool schema."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Tool / function calling schema ───────────────────────────────────────────
# This is the single source of truth used by all providers.

TOOL_SCHEMA: dict[str, Any] = {
    "name": "aws_command",
    "description": (
        "Return the AWS CLI command matching the user's request. "
        "Always use this tool — never respond with plain text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": (
                    "The complete aws CLI command to run (must start with 'aws '). "
                    "Empty string when clarification is needed."
                ),
            },
            "explanation": {
                "type": "string",
                "description": "Plain English explanation of what the command does.",
            },
            "risk_tier": {
                "type": "integer",
                "enum": [0, 1, 2, 3],
                "description": (
                    "Risk level: 0=read-only, 1=write/reversible, "
                    "2=destructive/irreversible, 3=catastrophic/account-level"
                ),
            },
            "clarification": {
                "type": "string",
                "description": (
                    "If the request is ambiguous, ask this question. "
                    "Omit or leave empty when the command is clear."
                ),
            },
        },
        "required": ["command", "explanation", "risk_tier"],
    },
}


# ── Shared data types ─────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str


@dataclass
class LLMResponse:
    command: str
    explanation: str
    risk_tier: int
    clarification: str | None = None


# ── Provider protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, messages: list[Message], tool_schema: dict[str, Any]) -> LLMResponse:
        ...


# ── Fallback JSON parsing (providers without tool calling) ────────────────────

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_response(text: str) -> LLMResponse:
    """
    Parse a free-form JSON response when tool calling is unavailable.
    Strips markdown code fences before parsing.
    """
    stripped = text.strip()
    fence_match = _CODE_FENCE_RE.search(stripped)
    if fence_match:
        stripped = fence_match.group(1)

    data: dict[str, Any] = json.loads(stripped)
    return LLMResponse(
        command=str(data.get("command", "")),
        explanation=str(data.get("explanation", "")),
        risk_tier=int(data.get("risk_tier", 1)),
        clarification=data.get("clarification") or None,
    )
