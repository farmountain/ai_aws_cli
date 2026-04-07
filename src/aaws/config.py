"""Configuration loading, validation, and persistence for aaws."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel

from .errors import ConfigNotFoundError


# ── Pydantic models ────────────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: str = "bedrock"
    model: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    api_key: Optional[str] = None
    temperature: float = 0.1
    timeout: int = 30


class AWSConfig(BaseModel):
    default_profile: Optional[str] = None
    default_region: Optional[str] = None


class SafetyConfig(BaseModel):
    auto_execute_tier: int = 0
    protected_profiles: list[str] = []


class OutputConfig(BaseModel):
    format: str = "auto"
    raw: bool = False
    color: bool = True


class AuditConfig(BaseModel):
    enabled: bool = True
    path: Optional[str] = None
    max_size_mb: int = 10


class RateLimitConfig(BaseModel):
    enabled: bool = True
    max_per_minute: int = 20
    burst: int = 5


class SessionConfig(BaseModel):
    rate_limit: RateLimitConfig = RateLimitConfig()


class AawsConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    aws: AWSConfig = AWSConfig()
    safety: SafetyConfig = SafetyConfig()
    output: OutputConfig = OutputConfig()
    audit: AuditConfig = AuditConfig()
    session: SessionConfig = SessionConfig()


# ── Env var helpers ───────────────────────────────────────────────────────────

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str) -> str:
    """Resolve ${ENV_VAR} references in a string. Leaves unset vars as-is."""

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return _ENV_VAR_RE.sub(replacer, value)


def _resolve_recursive(obj: object) -> object:
    """Recursively resolve ${ENV_VAR} in all string values of a nested structure."""
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _resolve_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_recursive(i) for i in obj]
    return obj


# Map from AAWS_ env var → (section, field) in the config dict
_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "AAWS_LLM_PROVIDER": ("llm", "provider"),
    "AAWS_LLM_MODEL": ("llm", "model"),
    "AAWS_LLM_API_KEY": ("llm", "api_key"),
    "AAWS_LLM_TEMPERATURE": ("llm", "temperature"),
    "AAWS_LLM_TIMEOUT": ("llm", "timeout"),
    "AAWS_AWS_PROFILE": ("aws", "default_profile"),
    "AAWS_AWS_REGION": ("aws", "default_region"),
    "AAWS_SAFETY_AUTO_EXECUTE_TIER": ("safety", "auto_execute_tier"),
    "AAWS_OUTPUT_FORMAT": ("output", "format"),
    "AAWS_OUTPUT_RAW": ("output", "raw"),
    "AAWS_OUTPUT_COLOR": ("output", "color"),
    "AAWS_SESSION_RATE_LIMIT_ENABLED": ("session", "rate_limit.enabled"),
    "AAWS_SESSION_RATE_LIMIT_MAX_PER_MINUTE": ("session", "rate_limit.max_per_minute"),
    "AAWS_SESSION_RATE_LIMIT_BURST": ("session", "rate_limit.burst"),
}


def _apply_env_overrides(config_dict: dict) -> dict:  # type: ignore[type-arg]
    """Apply AAWS_-prefixed environment variables, overriding file-based config."""
    for env_key, (section, field) in _ENV_OVERRIDES.items():
        val = os.environ.get(env_key)
        if val is not None:
            if section not in config_dict:
                config_dict[section] = {}
            # Support dotted field paths (e.g. "rate_limit.enabled")
            parts = field.split(".")
            target = config_dict[section]
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = val
    return config_dict


# ── Path helpers ──────────────────────────────────────────────────────────────

def config_path() -> Path:
    """Return the OS-appropriate config file path."""
    return Path(user_config_dir("aaws")) / "config.yaml"


# ── Public API ────────────────────────────────────────────────────────────────

def load_config(path: Path | None = None) -> AawsConfig:
    """
    Load config from YAML file, resolve ${ENV_VAR} references, apply
    AAWS_-prefixed env var overrides, and return a validated AawsConfig.

    Raises ConfigNotFoundError if the file does not exist.
    """
    resolved_path = path or config_path()

    if not resolved_path.exists():
        raise ConfigNotFoundError(str(resolved_path))

    with resolved_path.open() as f:
        raw: dict = yaml.safe_load(f) or {}  # type: ignore[assignment]

    raw = _resolve_recursive(raw)  # type: ignore[assignment]
    raw = _apply_env_overrides(raw)  # type: ignore[arg-type]

    return AawsConfig.model_validate(raw)


def write_config(config: AawsConfig, path: Path | None = None) -> Path:
    """Serialize config to YAML, creating parent directories as needed."""
    resolved_path = path or config_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude_none=True)
    with resolved_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return resolved_path
