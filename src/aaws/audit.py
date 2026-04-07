"""Append-only audit log for executed AWS CLI commands.

Writes one JSON object per line to a JSONL file. Supports file rotation
by size and concurrent-safe writes (O_APPEND on POSIX, msvcrt.locking
on Windows).

All I/O failures are logged via the ``aaws.audit`` logger and never
raised — audit must never break command execution.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from platformdirs import user_config_dir

logger = logging.getLogger("aaws.audit")


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    """Single audit record for an executed AWS command."""

    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    command: str = ""
    tier: int = -1
    profile: str = "default"
    region: str = "us-east-1"
    exit_code: int = 0  # 0=success, 1-255=AWS error, -1=crash, -2=interrupted
    success: bool = True
    mode: str = "cli"  # "cli", "session", "mcp"
    duration_ms: int = 0


@dataclass
class AuditConfig:
    """Configuration for the audit subsystem."""

    enabled: bool = True
    path: Optional[str] = None
    max_size_mb: int = 10

    def resolve_path(self) -> Path:
        """Return the effective audit file path."""
        if self.path:
            return Path(self.path)
        return Path(user_config_dir("aaws")) / "audit.jsonl"


# ── Write helpers ────────────────────────────────────────────────────────────


def _rotate(file_path: Path, max_size_bytes: int) -> None:
    """Rotate audit file if it exceeds the size threshold.

    Rotation scheme: audit.jsonl -> audit.jsonl.1 -> audit.jsonl.2 (discarded).
    """
    try:
        if not file_path.exists():
            return
        if file_path.stat().st_size < max_size_bytes:
            return

        rotated_2 = file_path.with_suffix(file_path.suffix + ".2")
        rotated_1 = file_path.with_suffix(file_path.suffix + ".1")

        # Discard .2 if it exists
        if rotated_2.exists():
            rotated_2.unlink()

        # .1 -> .2
        if rotated_1.exists():
            rotated_1.rename(rotated_2)

        # current -> .1
        file_path.rename(rotated_1)
    except OSError as exc:
        logger.warning("Audit log rotation failed: %s", exc)


def _write_line(file_path: Path, line: str) -> None:
    """Append a single line to the audit file with concurrent-write safety."""
    data = (line + "\n").encode("utf-8")

    if sys.platform == "win32":
        _write_line_windows(file_path, data)
    else:
        _write_line_posix(file_path, data)


def _write_line_posix(file_path: Path, data: bytes) -> None:
    """Append using O_APPEND for atomic writes on POSIX."""
    fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _write_line_windows(file_path: Path, data: bytes) -> None:
    """Append with msvcrt.locking on Windows."""
    import msvcrt  # noqa: PLC0415

    fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        try:
            os.write(fd, data)
        finally:
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
    finally:
        os.close(fd)


# ── Public API ───────────────────────────────────────────────────────────────


def append(entry: AuditEntry, config: AuditConfig) -> None:
    """Serialise an AuditEntry to JSONL and append to the audit file.

    Creates parent directories if needed. Rotates the file if it exceeds
    ``config.max_size_mb``. Never raises — logs warnings on failure.
    """
    try:
        file_path = config.resolve_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)

        max_size_bytes = config.max_size_mb * 1024 * 1024
        _rotate(file_path, max_size_bytes)

        line = json.dumps(asdict(entry), separators=(",", ":"))
        _write_line(file_path, line)
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)


def check_writable(config: AuditConfig) -> bool:
    """Test whether the audit path is writable. Returns True if writable."""
    try:
        file_path = config.resolve_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Try opening in append mode
        with file_path.open("a"):
            pass
        return True
    except Exception:
        return False
