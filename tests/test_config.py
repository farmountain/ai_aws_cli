"""Tests for configuration loading, env var resolution, and overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from aaws.config import _resolve_env_vars, load_config, AawsConfig


# ── _resolve_env_vars ─────────────────────────────────────────────────────────

def test_resolve_env_var_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MY_KEY", "abc123")
    assert _resolve_env_vars("${MY_KEY}") == "abc123"


def test_resolve_env_var_unset():
    # Should leave unresolved vars intact
    result = _resolve_env_vars("${DEFINITELY_NOT_SET_XYZ_AAWS_TEST}")
    assert result == "${DEFINITELY_NOT_SET_XYZ_AAWS_TEST}"


def test_resolve_env_var_mixed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KEY_ONE", "hello")
    result = _resolve_env_vars("prefix-${KEY_ONE}-suffix")
    assert result == "prefix-hello-suffix"


# ── load_config ───────────────────────────────────────────────────────────────

def test_load_config_defaults(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  provider: bedrock\n")
    config = load_config(cfg)
    assert config.llm.provider == "bedrock"
    assert config.llm.temperature == 0.1
    assert config.safety.auto_execute_tier == 0


def test_load_config_missing_raises(tmp_path: Path):
    from aaws.errors import ConfigNotFoundError

    with pytest.raises(ConfigNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_config_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  provider: bedrock\n")
    monkeypatch.setenv("AAWS_LLM_PROVIDER", "openai")
    config = load_config(cfg)
    assert config.llm.provider == "openai"


def test_load_config_env_var_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MY_API_KEY", "sk-test-value")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  provider: openai\n  api_key: ${MY_API_KEY}\n")
    config = load_config(cfg)
    assert config.llm.api_key == "sk-test-value"


def test_load_config_protected_profiles(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("safety:\n  protected_profiles:\n    - production\n    - prod-*\n")
    config = load_config(cfg)
    assert "production" in config.safety.protected_profiles
    assert "prod-*" in config.safety.protected_profiles


def test_load_config_empty_file_uses_defaults(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("")
    config = load_config(cfg)
    assert isinstance(config, AawsConfig)
    assert config.llm.provider == "bedrock"
