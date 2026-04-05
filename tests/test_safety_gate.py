"""Tests for apply_safety_gate — interactive confirmation tiers 0-3."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from aaws.config import AawsConfig, SafetyConfig
from aaws.errors import ProtectedProfileError
from aaws.safety.classifier import apply_safety_gate, was_dry_run_requested


def _config(**kwargs) -> AawsConfig:
    safety = SafetyConfig(**kwargs)
    return AawsConfig(safety=safety)


# ── Tier 0: auto-execute ────────────────────────────────────────────────────


def test_tier0_auto_executes():
    result = apply_safety_gate(
        "aws s3 ls", 0, "Lists buckets", "default", _config()
    )
    assert result is True


def test_tier0_no_prompt_needed():
    # Should not call any Rich prompt
    result = apply_safety_gate(
        "aws ec2 describe-instances", 0, "Describes instances", "default", _config()
    )
    assert result is True


# ── Tier 1: simple y/n ──────────────────────────────────────────────────────


@patch("rich.prompt.Confirm.ask", return_value=True)
def test_tier1_confirm_yes(mock_confirm):
    result = apply_safety_gate(
        "aws s3api create-bucket --bucket test", 1, "Creates bucket", "default", _config()
    )
    assert result is True
    mock_confirm.assert_called_once()


@patch("rich.prompt.Confirm.ask", return_value=False)
def test_tier1_confirm_no(mock_confirm):
    result = apply_safety_gate(
        "aws s3api create-bucket --bucket test", 1, "Creates bucket", "default", _config()
    )
    assert result is False


def test_tier1_auto_confirm_with_yes_flag():
    result = apply_safety_gate(
        "aws s3api create-bucket --bucket test", 1, "Creates bucket", "default",
        _config(), auto_confirm=True,
    )
    assert result is True


# ── Tier 2: warning + type "yes" ────────────────────────────────────────────


@patch("rich.prompt.Prompt.ask", return_value="yes")
@patch("rich.prompt.Confirm.ask", return_value=False)  # decline dry-run
def test_tier2_confirm_yes(mock_dry, mock_prompt):
    result = apply_safety_gate(
        "aws ec2 terminate-instances --instance-ids i-abc", 2,
        "Terminates instance", "default", _config(),
    )
    assert result is True


@patch("rich.prompt.Prompt.ask", return_value="")
@patch("rich.prompt.Confirm.ask", return_value=False)  # decline dry-run
def test_tier2_confirm_cancel(mock_dry, mock_prompt):
    result = apply_safety_gate(
        "aws ec2 terminate-instances --instance-ids i-abc", 2,
        "Terminates instance", "default", _config(),
    )
    assert result is False


def test_tier2_auto_confirm_with_yes_flag():
    result = apply_safety_gate(
        "aws ec2 terminate-instances --instance-ids i-abc", 2,
        "Terminates instance", "default", _config(), auto_confirm=True,
    )
    assert result is True


@patch("rich.prompt.Confirm.ask", return_value=True)  # accept dry-run
def test_tier2_dry_run_offered_for_ec2(mock_confirm):
    result = apply_safety_gate(
        "aws ec2 terminate-instances --instance-ids i-abc", 2,
        "Terminates instance", "default", _config(),
    )
    # When dry-run is accepted, returns False and sets the sentinel
    assert result is False
    assert was_dry_run_requested() is True


@patch("rich.prompt.Prompt.ask", return_value="yes")
def test_tier2_no_dry_run_for_non_ec2(mock_prompt):
    # S3 delete should NOT offer --dry-run
    result = apply_safety_gate(
        "aws s3 rb s3://my-bucket", 2, "Removes bucket", "default", _config(),
    )
    assert result is True


# ── Tier 3: refuse / override ────────────────────────────────────────────────


def test_tier3_refused_by_default():
    result = apply_safety_gate(
        "aws s3 rm s3://bucket --recursive", 3,
        "Deletes all objects", "default", _config(),
    )
    assert result is False


@patch("rich.prompt.Prompt.ask", return_value="yes")
def test_tier3_override_with_accept_responsibility(mock_prompt):
    result = apply_safety_gate(
        "aws s3 rm s3://bucket --recursive", 3,
        "Deletes all objects", "default", _config(),
        accept_responsibility=True,
    )
    assert result is True


@patch("rich.prompt.Prompt.ask", return_value="")
def test_tier3_override_but_cancel(mock_prompt):
    result = apply_safety_gate(
        "aws s3 rm s3://bucket --recursive", 3,
        "Deletes all objects", "default", _config(),
        accept_responsibility=True,
    )
    assert result is False


def test_tier3_yes_flag_does_not_override():
    """--yes should NOT bypass tier 3 refusal."""
    result = apply_safety_gate(
        "aws s3 rm s3://bucket --recursive", 3,
        "Deletes all objects", "default", _config(),
        auto_confirm=True,
    )
    assert result is False


# ── auto_execute_tier config ─────────────────────────────────────────────────


def test_auto_execute_tier_1():
    """If auto_execute_tier=1, tier 1 commands should auto-execute."""
    result = apply_safety_gate(
        "aws s3api create-bucket --bucket test", 1, "Creates bucket", "default",
        _config(auto_execute_tier=1),
    )
    assert result is True


def test_auto_execute_tier_does_not_bypass_tier2():
    """auto_execute_tier=1 should NOT auto-execute tier 2."""
    # Will need interactive prompt, so we mock it
    with patch("rich.prompt.Prompt.ask", return_value="yes"):
        result = apply_safety_gate(
            "aws s3 rb s3://bucket", 2, "Removes bucket", "default",
            _config(auto_execute_tier=1),
        )
    assert result is True


# ── Protected profiles ───────────────────────────────────��───────────────────


def test_protected_profile_blocks_writes():
    config = _config(protected_profiles=["prod-*"])
    with pytest.raises(ProtectedProfileError):
        apply_safety_gate(
            "aws s3api create-bucket --bucket test", 1, "Creates bucket",
            "prod-us-east-1", config,
        )


def test_protected_profile_allows_reads():
    config = _config(protected_profiles=["prod-*"])
    result = apply_safety_gate(
        "aws s3 ls", 0, "Lists buckets", "prod-us-east-1", config,
    )
    assert result is True


def test_unprotected_profile_allows_writes():
    config = _config(protected_profiles=["prod-*"])
    with patch("rich.prompt.Confirm.ask", return_value=True):
        result = apply_safety_gate(
            "aws s3api create-bucket --bucket test", 1, "Creates bucket",
            "dev", config,
        )
    assert result is True
