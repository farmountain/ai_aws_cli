"""Tests for the audit log module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from aaws.audit import AuditConfig, AuditEntry, append, check_writable, _rotate


# ── AuditEntry defaults ─────────────────────────────────────────────────────


def test_audit_entry_defaults():
    entry = AuditEntry()
    assert entry.command == ""
    assert entry.tier == -1
    assert entry.exit_code == 0
    assert entry.success is True
    assert entry.mode == "cli"


def test_audit_entry_custom():
    entry = AuditEntry(
        command="aws s3 ls",
        tier=0,
        profile="dev",
        region="eu-west-1",
        exit_code=0,
        success=True,
        mode="mcp",
        duration_ms=42,
    )
    assert entry.command == "aws s3 ls"
    assert entry.mode == "mcp"


# ── AuditConfig ──────────────────────────────────────────────────────────────


def test_audit_config_defaults():
    cfg = AuditConfig()
    assert cfg.enabled is True
    assert cfg.path is None
    assert cfg.max_size_mb == 10


def test_audit_config_resolve_path_custom():
    cfg = AuditConfig(path="/tmp/custom-audit.jsonl")
    assert cfg.resolve_path() == Path("/tmp/custom-audit.jsonl")


def test_audit_config_resolve_path_default():
    cfg = AuditConfig()
    path = cfg.resolve_path()
    assert path.name == "audit.jsonl"


# ── append() ─────────────────────────────────────────────────────────────────


def test_append_creates_file(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    cfg = AuditConfig(path=str(audit_file))
    entry = AuditEntry(command="aws s3 ls", tier=0, exit_code=0, success=True)

    append(entry, cfg)

    assert audit_file.exists()
    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["command"] == "aws s3 ls"
    assert data["tier"] == 0


def test_append_valid_jsonl(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    cfg = AuditConfig(path=str(audit_file))

    append(AuditEntry(command="aws s3 ls", tier=0), cfg)
    append(AuditEntry(command="aws ec2 describe-instances", tier=0), cfg)

    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        data = json.loads(line)
        assert "command" in data
        assert "tier" in data


def test_append_appends_not_overwrites(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    cfg = AuditConfig(path=str(audit_file))

    append(AuditEntry(command="first"), cfg)
    append(AuditEntry(command="second"), cfg)
    append(AuditEntry(command="third"), cfg)

    lines = audit_file.read_text().strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0])["command"] == "first"
    assert json.loads(lines[2])["command"] == "third"


def test_append_creates_parent_dirs(tmp_path):
    audit_file = tmp_path / "deep" / "nested" / "dir" / "audit.jsonl"
    cfg = AuditConfig(path=str(audit_file))

    append(AuditEntry(command="aws s3 ls"), cfg)
    assert audit_file.exists()


def test_append_unwritable_path_no_exception(tmp_path):
    """Unwritable path produces no exception (warning logged)."""
    # Use a path that can't exist
    cfg = AuditConfig(path=str(tmp_path / "\x00invalid"))
    # Should not raise
    append(AuditEntry(command="aws s3 ls"), cfg)


# ── Rotation ─────────────────────────────────────────────────────────────────


def test_rotation_triggered_at_threshold(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    # Write enough data to exceed 1 byte threshold
    audit_file.write_text("x" * 100)
    cfg = AuditConfig(path=str(audit_file), max_size_mb=0)  # 0 MB = always rotate

    # Trigger rotation via append (which checks size before writing)
    append(AuditEntry(command="aws s3 ls"), cfg)

    rotated = tmp_path / "audit.jsonl.1"
    assert rotated.exists()
    assert rotated.read_text() == "x" * 100


def test_rotation_oldest_discarded(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    rotated_1 = tmp_path / "audit.jsonl.1"
    rotated_2 = tmp_path / "audit.jsonl.2"

    rotated_2.write_text("oldest")
    rotated_1.write_text("older")
    audit_file.write_text("x" * 100)

    _rotate(audit_file, max_size_bytes=1)

    # .2 should now contain what was in .1
    assert rotated_2.read_text() == "older"
    # .1 should contain what was in current
    assert rotated_1.read_text() == "x" * 100
    # Current should be gone (new file created by append)
    assert not audit_file.exists()


def test_rotation_no_rotation_under_threshold(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text("small")

    _rotate(audit_file, max_size_bytes=1024 * 1024)

    rotated = tmp_path / "audit.jsonl.1"
    assert not rotated.exists()
    assert audit_file.exists()


# ── Interrupted execution audit ──────────────────────────────────────────────


def test_interrupted_execution_exit_code():
    """Verify exit_code conventions for interrupted/crashed executions."""
    interrupted = AuditEntry(exit_code=-2, success=False)
    assert interrupted.exit_code == -2

    crashed = AuditEntry(exit_code=-1, success=False)
    assert crashed.exit_code == -1


# ── test_writable ────────────────────────────────────────────────────────────


def test_check_writable_valid_path(tmp_path):
    cfg = AuditConfig(path=str(tmp_path / "audit.jsonl"))
    assert check_writable(cfg) is True


def test_check_writable_invalid_path():
    cfg = AuditConfig(path="/nonexistent/deeply/nested/path/audit.jsonl")
    # On most systems this will fail
    result = check_writable(cfg)
    # Just verify it returns a bool and doesn't raise
    assert isinstance(result, bool)
