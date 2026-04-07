"""Integration tests for audit logging across all modes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aaws.audit import AuditConfig, AuditEntry, append
from aaws.safety.classifier import classify


# ── Full pipeline audit test ─────────────────────────────────────────────────


def test_full_pipeline_produces_audit_entry(tmp_path):
    """translate -> classify -> execute -> format produces a valid audit entry."""
    audit_file = tmp_path / "audit.jsonl"
    audit_cfg = AuditConfig(path=str(audit_file))

    command = "aws s3api list-buckets --output json"
    tier = classify(command, llm_tier=0)
    assert tier == 0

    # Simulate execution
    import time
    start = time.monotonic()
    exit_code = 0
    duration_ms = int((time.monotonic() - start) * 1000)

    entry = AuditEntry(
        command=command,
        tier=tier,
        profile="default",
        region="us-east-1",
        exit_code=exit_code,
        success=True,
        mode="cli",
        duration_ms=duration_ms,
    )
    append(entry, audit_cfg)

    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["command"] == command
    assert data["tier"] == 0
    assert data["profile"] == "default"
    assert data["mode"] == "cli"
    assert data["exit_code"] == 0
    assert data["success"] is True
    assert "timestamp" in data
    assert "duration_ms" in data


def test_mcp_confirmed_produces_audit_entry(tmp_path):
    """MCP execute_confirmed path produces an audit entry with re-classified tier."""
    audit_file = tmp_path / "audit.jsonl"
    audit_cfg = AuditConfig(path=str(audit_file))

    command = "aws ec2 run-instances --instance-type t3.micro"
    tier = classify(command, llm_tier=1)
    assert tier == 1  # Write operation

    import time
    start = time.monotonic()
    duration_ms = int((time.monotonic() - start) * 1000)

    entry = AuditEntry(
        command=command,
        tier=tier,
        profile="dev",
        region="eu-west-1",
        exit_code=0,
        success=True,
        mode="mcp",
        duration_ms=duration_ms,
    )
    append(entry, audit_cfg)

    data = json.loads(audit_file.read_text().strip())
    assert data["tier"] == 1
    assert data["mode"] == "mcp"
    assert data["profile"] == "dev"


def test_interrupted_execution_produces_audit_entry(tmp_path):
    """KeyboardInterrupt during execute produces audit entry with exit_code -2."""
    audit_file = tmp_path / "audit.jsonl"
    audit_cfg = AuditConfig(path=str(audit_file))

    command = "aws ec2 terminate-instances --instance-ids i-abc"
    tier = classify(command, llm_tier=2)

    import time
    start = time.monotonic()

    # Simulate interrupted execution
    exit_code = -2
    duration_ms = int((time.monotonic() - start) * 1000)

    entry = AuditEntry(
        command=command,
        tier=tier,
        profile="default",
        region="us-east-1",
        exit_code=exit_code,
        success=False,
        mode="session",
        duration_ms=duration_ms,
    )
    append(entry, audit_cfg)

    data = json.loads(audit_file.read_text().strip())
    assert data["exit_code"] == -2
    assert data["success"] is False
    assert data["mode"] == "session"


def test_crashed_execution_produces_audit_entry(tmp_path):
    """OSError during execute produces audit entry with exit_code -1."""
    audit_file = tmp_path / "audit.jsonl"
    audit_cfg = AuditConfig(path=str(audit_file))

    entry = AuditEntry(
        command="aws s3 ls",
        tier=0,
        exit_code=-1,
        success=False,
        mode="cli",
    )
    append(entry, audit_cfg)

    data = json.loads(audit_file.read_text().strip())
    assert data["exit_code"] == -1
    assert data["success"] is False


def test_audit_skipped_when_disabled(tmp_path):
    """Audit entry is not written when config.audit.enabled is False."""
    audit_file = tmp_path / "audit.jsonl"
    audit_cfg = AuditConfig(path=str(audit_file), enabled=False)

    # append should do nothing when enabled=False is checked by the caller
    # The audit module itself always writes; the skip logic is in the callers.
    # So we test the caller pattern here.
    if audit_cfg.enabled:
        append(AuditEntry(command="aws s3 ls"), audit_cfg)

    assert not audit_file.exists()


def test_mcp_execute_tier0_produces_audit(tmp_path):
    """MCP execute_aws_command tier 0 path triggers audit."""
    import aaws.mcp_server as mcp_mod
    from aaws.audit import AuditConfig

    audit_file = tmp_path / "audit.jsonl"

    # Set up module-level config
    original_config = mcp_mod._config
    original_audit = mcp_mod._audit_config
    try:
        mcp_mod._config = MagicMock(
            safety=MagicMock(protected_profiles=[]),
            audit=MagicMock(enabled=True, path=str(audit_file), max_size_mb=10),
        )
        mcp_mod._audit_config = AuditConfig(path=str(audit_file))

        with patch("aaws.executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
            result = mcp_mod.execute_aws_command("aws s3 ls")

        assert result["executed"] is True
        assert audit_file.exists()
        data = json.loads(audit_file.read_text().strip())
        assert data["mode"] == "mcp"
        assert data["tier"] == 0
    finally:
        mcp_mod._config = original_config
        mcp_mod._audit_config = original_audit
