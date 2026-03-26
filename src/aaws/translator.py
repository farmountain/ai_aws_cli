"""Natural language → AWS CLI command translation."""

from __future__ import annotations

from .errors import TranslationError
from .providers.base import LLMProvider, LLMResponse, Message, TOOL_SCHEMA

# ── System prompt ──────────────────────────────────────────────────────────────
# Versioned here so regression testing can catch prompt changes.

SYSTEM_PROMPT = """\
You are an AWS CLI assistant. Translate natural language requests into valid AWS CLI commands.

Always invoke the aws_command tool to return your response. Never respond with plain text.

Rules:
1. The command field MUST start with "aws " and be a complete, valid AWS CLI invocation.
2. Use the provided AWS profile and region context when constructing commands.
3. Never invent resource IDs, bucket names, or ARNs — ask for clarification if needed.
4. Include --output json on commands that produce structured output, unless the user specifies otherwise.
5. If the request is ambiguous or missing required information, set the clarification field to
   your question and leave command as an empty string. Ask only ONE question at a time.
6. Assign risk_tier accurately:
   - 0: read-only   (describe, list, get, head)
   - 1: write       (create, put, update, tag, start, copy, sync)
   - 2: destructive (delete, terminate, detach, remove, rb, rm)
   - 3: catastrophic (bulk-delete, account-level IAM changes, org-level operations)
"""

_CORRECTION_SUFFIX = (
    "\n\nThe command you returned did not start with 'aws '. "
    "Use the aws_command tool and return a valid AWS CLI command that begins with 'aws '."
)


def translate(
    nl_input: str,
    profile: str,
    region: str,
    history: list[dict[str, str]],
    provider: LLMProvider,
) -> LLMResponse:
    """
    Translate a natural language request to a structured LLMResponse.

    Args:
        nl_input:  The user's natural language request.
        profile:   Active AWS profile name (injected as context).
        region:    Active AWS region (injected as context).
        history:   Bounded list of previous exchanges [{role, content}, ...].
                   Only the last 10 entries are included in the LLM context.
        provider:  The LLMProvider implementation to call.

    Returns:
        LLMResponse with command + metadata, or clarification if input is ambiguous.

    Raises:
        TranslationError: if two consecutive LLM calls fail to produce a valid command.
    """
    messages = _build_messages(nl_input, profile, region, history)
    response = provider.complete(messages, TOOL_SCHEMA)

    # If the LLM is asking a clarification question, accept immediately
    if response.clarification:
        return response

    # Validate that the command is a real AWS CLI invocation
    if not _is_valid_command(response.command):
        # Retry once with a corrective message
        messages.append(
            Message(role="assistant", content=response.command or "(empty)")
        )
        messages.append(Message(role="user", content=_CORRECTION_SUFFIX))
        response = provider.complete(messages, TOOL_SCHEMA)

        if not _is_valid_command(response.command) and not response.clarification:
            raise TranslationError(
                f"Could not generate a valid AWS CLI command for: {nl_input!r}\n"
                f"Last attempt: {response.command!r}"
            )

    return response


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_valid_command(command: str | None) -> bool:
    return bool(command and command.strip().startswith("aws "))


def _build_messages(
    nl_input: str,
    profile: str,
    region: str,
    history: list[dict[str, str]],
) -> list[Message]:
    """Assemble the message list for the LLM call."""
    messages: list[Message] = [
        Message(role="user", content=SYSTEM_PROMPT),
    ]

    # Inject bounded history (last 10 exchanges)
    for entry in history[-10:]:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append(Message(role=role, content=content))

    user_message = (
        f"Context:\n"
        f"  AWS Profile: {profile}\n"
        f"  Region: {region}\n\n"
        f"Request: {nl_input}"
    )
    messages.append(Message(role="user", content=user_message))
    return messages
