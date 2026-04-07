"""Tests for session rate-limit configuration parsing."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.aaws.config import AawsConfig, RateLimitConfig, SessionConfig, load_config


class TestRateLimitConfigDefaults:
    def test_default_values(self) -> None:
        cfg = RateLimitConfig()
        assert cfg.enabled is True
        assert cfg.max_per_minute == 20
        assert cfg.burst == 5

    def test_session_config_default(self) -> None:
        cfg = SessionConfig()
        assert cfg.rate_limit.enabled is True

    def test_aaws_config_has_session(self) -> None:
        cfg = AawsConfig()
        assert cfg.session.rate_limit.max_per_minute == 20
        assert cfg.session.rate_limit.burst == 5


class TestConfigParsing:
    def test_config_without_session_section(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(textwrap.dedent("""\
            llm:
              provider: bedrock
              model: anthropic.claude-3-5-haiku-20241022-v1:0
        """))
        cfg = load_config(config_file)
        # Should use defaults
        assert cfg.session.rate_limit.enabled is True
        assert cfg.session.rate_limit.max_per_minute == 20
        assert cfg.session.rate_limit.burst == 5

    def test_config_with_session_rate_limit(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(textwrap.dedent("""\
            llm:
              provider: bedrock
            session:
              rate_limit:
                enabled: false
                max_per_minute: 50
                burst: 10
        """))
        cfg = load_config(config_file)
        assert cfg.session.rate_limit.enabled is False
        assert cfg.session.rate_limit.max_per_minute == 50
        assert cfg.session.rate_limit.burst == 10

    def test_env_var_overrides_rate_limit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(textwrap.dedent("""\
            llm:
              provider: bedrock
        """))
        monkeypatch.setenv("AAWS_SESSION_RATE_LIMIT_ENABLED", "false")
        monkeypatch.setenv("AAWS_SESSION_RATE_LIMIT_MAX_PER_MINUTE", "99")
        monkeypatch.setenv("AAWS_SESSION_RATE_LIMIT_BURST", "10")
        cfg = load_config(config_file)
        assert cfg.session.rate_limit.enabled is False
        assert cfg.session.rate_limit.max_per_minute == 99
        assert cfg.session.rate_limit.burst == 10

    def test_env_var_overrides_partial(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(textwrap.dedent("""\
            llm:
              provider: bedrock
            session:
              rate_limit:
                max_per_minute: 30
        """))
        monkeypatch.setenv("AAWS_SESSION_RATE_LIMIT_BURST", "8")
        cfg = load_config(config_file)
        # File value preserved
        assert cfg.session.rate_limit.max_per_minute == 30
        # Env var overrides default
        assert cfg.session.rate_limit.burst == 8
        # Default preserved
        assert cfg.session.rate_limit.enabled is True

    def test_config_with_partial_rate_limit(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(textwrap.dedent("""\
            llm:
              provider: bedrock
            session:
              rate_limit:
                max_per_minute: 30
        """))
        cfg = load_config(config_file)
        # Specified value overrides default
        assert cfg.session.rate_limit.max_per_minute == 30
        # Unspecified values use defaults
        assert cfg.session.rate_limit.enabled is True
        assert cfg.session.rate_limit.burst == 5
