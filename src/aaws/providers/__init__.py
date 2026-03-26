"""LLM provider package — exports provider types and factory."""

from __future__ import annotations

from .base import LLMProvider, LLMResponse, Message, TOOL_SCHEMA
from .bedrock_provider import BedrockProvider
from .openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "Message",
    "TOOL_SCHEMA",
    "BedrockProvider",
    "OpenAIProvider",
    "get_provider",
]


def get_provider(config: object) -> LLMProvider:
    """Factory: return the configured LLM provider instance."""
    from ..errors import AawsError  # noqa: PLC0415

    llm = getattr(config, "llm", None)
    aws = getattr(config, "aws", None)
    provider_name: str = getattr(llm, "provider", "bedrock")
    model: str = getattr(llm, "model", "anthropic.claude-3-5-haiku-20241022-v1:0")
    temperature: float = float(getattr(llm, "temperature", 0.1))
    timeout: int = int(getattr(llm, "timeout", 30))

    if provider_name == "bedrock":
        profile = getattr(aws, "default_profile", None)
        region = getattr(aws, "default_region", None)
        return BedrockProvider(
            model=model,
            profile=profile,
            region=region,
            temperature=temperature,
            timeout=timeout,
        )

    if provider_name == "openai":
        import os  # noqa: PLC0415

        api_key: str | None = getattr(llm, "api_key", None)
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise AawsError(
                "OpenAI API key not found. "
                "Set OPENAI_API_KEY or configure llm.api_key in config."
            )
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o-mini",
            temperature=temperature,
            timeout=timeout,
        )

    raise AawsError(
        f"Unknown LLM provider: {provider_name!r}. Supported providers: bedrock, openai"
    )
