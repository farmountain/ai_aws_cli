"""Custom exceptions and error types for aaws."""

from __future__ import annotations

import re
from enum import Enum, auto


class ErrorType(Enum):
    EXPIRED_TOKEN = auto()
    NO_CREDENTIALS = auto()
    ACCESS_DENIED = auto()
    BUCKET_NOT_EMPTY = auto()
    NO_SUCH_BUCKET = auto()
    RESOURCE_NOT_FOUND = auto()
    RESOURCE_CONFLICT = auto()
    TIMEOUT = auto()
    UNKNOWN = auto()


class AawsError(Exception):
    """Base exception for aaws errors."""


class TranslationError(AawsError):
    """Raised when the LLM fails to produce a valid AWS CLI command after retries."""


class ProtectedProfileError(AawsError):
    """Raised when a write operation is attempted against a protected AWS profile."""

    def __init__(self, profile: str) -> None:
        super().__init__(
            f"Profile '{profile}' is protected (read-only). Switch profiles to make changes."
        )
        self.profile = profile


class ConfigNotFoundError(AawsError):
    """Raised when no aaws config file exists."""


# ── Credential / permission pattern matching ──────────────────────────────────

_CREDENTIAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ExpiredTokenException|ExpiredToken|Token.*expired", re.I),
        "Your AWS session has expired. Refresh it with: aws sso login --profile {profile}",
    ),
    (
        re.compile(r"Unable to locate credentials|NoCredentialsError|no credentials", re.I),
        "No AWS credentials found. Configure them with: aws configure",
    ),
]

_ACCESS_DENIED_RE = re.compile(
    r"is not authorized to perform:\s*(\S+)", re.I
)

_RESOURCE_PATTERNS: list[tuple[re.Pattern[str], ErrorType]] = [
    (re.compile(r"BucketNotEmpty", re.I), ErrorType.BUCKET_NOT_EMPTY),
    (re.compile(r"NoSuchBucket", re.I), ErrorType.NO_SUCH_BUCKET),
    (re.compile(r"AccessDeniedException|is not authorized", re.I), ErrorType.ACCESS_DENIED),
    (
        re.compile(r"NoSuchKey|NoSuchEntity|does not exist|not found", re.I),
        ErrorType.RESOURCE_NOT_FOUND,
    ),
    (
        re.compile(r"AlreadyExists|BucketAlreadyOwned|ResourceConflict", re.I),
        ErrorType.RESOURCE_CONFLICT,
    ),
    (
        re.compile(r"ExpiredTokenException|ExpiredToken|Token.*expired", re.I),
        ErrorType.EXPIRED_TOKEN,
    ),
    (
        re.compile(r"Unable to locate credentials|NoCredentialsError", re.I),
        ErrorType.NO_CREDENTIALS,
    ),
]


def classify_error(stderr: str) -> ErrorType:
    """Classify an AWS CLI error from stderr content."""
    for pattern, error_type in _RESOURCE_PATTERNS:
        if pattern.search(stderr):
            return error_type
    return ErrorType.UNKNOWN


def get_credential_message(stderr: str, profile: str) -> str | None:
    """Return a hardcoded actionable message for credential/auth errors, or None."""
    for pattern, message in _CREDENTIAL_PATTERNS:
        if pattern.search(stderr):
            return message.format(profile=profile)

    match = _ACCESS_DENIED_RE.search(stderr)
    if match:
        action = match.group(1) if match.lastindex and match.group(1) else "the required action"
        return (
            f"Access denied: {action}\n"
            "Check your IAM permissions or switch to a profile with the required access."
        )

    return None


def interpret_error(command: str, stderr: str, provider: object) -> str:
    """Use the LLM to interpret a resource error and suggest next steps."""
    from .providers.base import Message, TOOL_SCHEMA  # noqa: PLC0415

    messages = [
        Message(
            role="user",
            content=(
                f"The following AWS CLI command failed:\n"
                f"  {command}\n\n"
                f"Error output:\n  {stderr.strip()}\n\n"
                "Explain what went wrong in plain English and suggest the exact command(s) "
                "needed to fix or work around this issue."
            ),
        )
    ]

    try:
        response = provider.complete(messages, TOOL_SCHEMA)  # type: ignore[union-attr]
        return response.explanation or "Unable to interpret error."
    except Exception:
        return stderr.strip()


def handle_error(command: str, result: object, profile: str, provider: object) -> None:
    """Route AWS CLI errors to appropriate handler and render for the user."""
    from rich.console import Console  # noqa: PLC0415

    from .formatter import render_error  # noqa: PLC0415

    console = Console()
    stderr: str = getattr(result, "stderr", "")

    # Credential/auth errors → hardcoded actionable message (no LLM call)
    cred_msg = get_credential_message(stderr, profile)
    if cred_msg:
        render_error(stderr, suggestion=cred_msg)
        return

    error_type = classify_error(stderr)

    if error_type in (
        ErrorType.BUCKET_NOT_EMPTY,
        ErrorType.NO_SUCH_BUCKET,
        ErrorType.RESOURCE_NOT_FOUND,
        ErrorType.RESOURCE_CONFLICT,
    ):
        try:
            interpretation = interpret_error(command, stderr, provider)
            render_error(stderr, suggestion=interpretation)
        except Exception:
            render_error(stderr)
    else:
        render_error(stderr)
